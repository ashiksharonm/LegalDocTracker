"""
API views for the contracts application.

Layered architecture: View → Serializer → Service → Model
"""
import logging
from typing import Any

from django.utils.dateparse import parse_datetime
from rest_framework import status as http_status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import APIException
from rest_framework import exceptions as drf_exceptions

from mongo_store.clause_store import ClauseStore

from .models import Contract
from .serializers import (
    ClauseCreateSerializer,
    ContractCreateSerializer,
    ContractDetailSerializer,
    ContractListSerializer,
    ContractStatusUpdateSerializer,
)
from .services import (
    ContractNotFoundError,
    ContractStatusError,
    create_contract,
    get_contract_with_clause_count,
    get_expiring_soon,
    list_contracts,
    transition_status,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exception handler
# ---------------------------------------------------------------------------


def custom_exception_handler(exc: Exception, context: dict) -> Response | None:
    """
    Custom DRF exception handler that adds a `status` field to all errors.

    Returns a Response with a consistent error structure:
    {
        "status": "error",
        "detail": "...",
        "errors": {...}   # only for validation errors
    }
    """
    from rest_framework.views import exception_handler

    response = exception_handler(exc, context)

    if response is not None:
        payload: dict[str, Any] = {"status": "error"}
        if isinstance(exc, drf_exceptions.ValidationError):
            payload["detail"] = "Validation failed."
            payload["errors"] = response.data
        else:
            payload["detail"] = response.data.get("detail", str(exc))
        response.data = payload

    return response


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_contract_or_404(contract_id: int) -> Contract:
    """Fetch a contract by PK or raise DRF NotFound."""
    try:
        return Contract.objects.select_related("owner").get(pk=contract_id)
    except Contract.DoesNotExist:
        raise NotFound(detail=f"Contract {contract_id} not found.")


# ---------------------------------------------------------------------------
# Contract list and create
# ---------------------------------------------------------------------------


class ContractListCreateView(APIView):
    """
    GET  /api/contracts/  — list contracts with optional filters.
    POST /api/contracts/  — create a new contract.
    """

    def get(self, request: Request) -> Response:
        """
        List contracts.

        Query params:
            status         — filter by status string
            expires_before — ISO datetime; filter contracts expiring before this
        """
        raw_status = request.query_params.get("status")
        expires_before_raw = request.query_params.get("expires_before")

        expires_before = None
        if expires_before_raw:
            expires_before = parse_datetime(expires_before_raw)
            if expires_before is None:
                raise ValidationError(
                    {"expires_before": "Must be a valid ISO 8601 datetime string."}
                )

        contracts = list_contracts(
            status=raw_status,
            expires_before=expires_before,
        )
        serializer = ContractListSerializer(contracts, many=True)
        return Response({"status": "ok", "count": contracts.count(), "results": serializer.data})

    def post(self, request: Request) -> Response:
        """Create a new contract owned by the authenticated user."""
        serializer = ContractCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated = serializer.validated_data
        contract = create_contract(
            title=validated["title"],
            parties=validated["parties"],
            status=validated.get("status", "DRAFT"),
            expires_at=validated.get("expires_at"),
            owner=request.user,
        )

        out = ContractCreateSerializer(contract)
        return Response(
            {"status": "ok", "data": out.data},
            status=http_status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Contract detail
# ---------------------------------------------------------------------------


class ContractDetailView(APIView):
    """
    GET /api/contracts/{id}/ — retrieve a single contract with clause count.
    """

    def get(self, request: Request, contract_id: int) -> Response:
        """Return full contract detail including MongoDB clause count."""
        try:
            contract = get_contract_with_clause_count(contract_id)
        except ContractNotFoundError:
            raise NotFound(detail=f"Contract {contract_id} not found.")

        serializer = ContractDetailSerializer(contract)
        return Response({"status": "ok", "data": serializer.data})


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------


class ContractStatusUpdateView(APIView):
    """
    PATCH /api/contracts/{id}/status/ — update contract status with validation.
    """

    def patch(self, request: Request, contract_id: int) -> Response:
        """
        Attempt a status transition.

        Body: { "status": "REVIEW", "notes": "Optional audit note" }
        """
        contract = _get_contract_or_404(contract_id)

        serializer = ContractStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]
        notes = serializer.validated_data.get("notes", "")

        try:
            updated = transition_status(
                contract=contract,
                new_status=new_status,
                notes=notes,
                actor=request.user,
            )
        except ContractStatusError as exc:
            raise ValidationError({"status": str(exc)})

        out = ContractDetailSerializer(updated)
        return Response({"status": "ok", "data": out.data})


# ---------------------------------------------------------------------------
# Expiring soon
# ---------------------------------------------------------------------------


class ContractExpiringSoonView(APIView):
    """
    GET /api/contracts/expiring-soon/ — contracts expiring within 7 days.
    """

    def get(self, request: Request) -> Response:
        """Return contracts expiring in the next 7 days (active statuses only)."""
        contracts = get_expiring_soon(days=7)
        serializer = ContractListSerializer(contracts, many=True)
        return Response({"status": "ok", "count": contracts.count(), "results": serializer.data})


# ---------------------------------------------------------------------------
# Clause (MongoDB) endpoints
# ---------------------------------------------------------------------------


class ContractClauseView(APIView):
    """
    POST /api/contracts/{id}/clauses/ — add a clause document to MongoDB.
    GET  /api/contracts/{id}/clauses/ — retrieve all clauses for a contract.
    """

    def _get_contract_or_404(self, contract_id: int) -> Contract:
        """Fetch contract from PostgreSQL or raise 404."""
        try:
            return Contract.objects.get(pk=contract_id)
        except Contract.DoesNotExist:
            raise NotFound(detail=f"Contract {contract_id} not found.")

    def post(self, request: Request, contract_id: int) -> Response:
        """
        Add a clause document to MongoDB for the given contract.

        Body: {
            "clause_number": 1,
            "clause_text": "...",
            "clause_type": "INDEMNITY",
            "flagged_keywords": ["liability"]
        }
        """
        contract = self._get_contract_or_404(contract_id)

        serializer = ClauseCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        store = ClauseStore()

        clause_id = store.add_clause(
            contract_id=contract.pk,
            clause_number=data["clause_number"],
            clause_text=data["clause_text"],
            clause_type=data["clause_type"],
            flagged_keywords=data.get("flagged_keywords", []),
        )

        logger.info("Clause added to MongoDB: contract=%s clause_id=%s", contract.pk, clause_id)
        return Response(
            {"status": "ok", "inserted_id": str(clause_id)},
            status=http_status.HTTP_201_CREATED,
        )

    def get(self, request: Request, contract_id: int) -> Response:
        """Retrieve all clause documents for a contract from MongoDB."""
        self._get_contract_or_404(contract_id)

        store = ClauseStore()
        clauses = store.get_clauses(contract_id)

        return Response(
            {"status": "ok", "count": len(clauses), "results": clauses},
        )
