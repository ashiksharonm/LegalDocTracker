"""
Service layer for the contracts application.

All business logic is centralised here — views and serializers
delegate complex operations to this module.
"""
import logging
from datetime import timedelta
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .models import Contract, ContractStatus, ContractEvent, ContractEventType

logger = logging.getLogger(__name__)

User = get_user_model()

# ---------------------------------------------------------------------------
# Status transition matrix
# key   → current status
# value → allowed next statuses
# ---------------------------------------------------------------------------

ALLOWED_TRANSITIONS: dict[str, list[str]] = {
    ContractStatus.DRAFT: [ContractStatus.REVIEW, ContractStatus.EXPIRED],
    ContractStatus.REVIEW: [ContractStatus.SIGNED, ContractStatus.DRAFT, ContractStatus.EXPIRED],
    ContractStatus.SIGNED: [ContractStatus.EXPIRED],
    ContractStatus.EXPIRED: [],  # terminal state
}


class ContractStatusError(Exception):
    """Raised when an invalid status transition is attempted."""


class ContractNotFoundError(Exception):
    """Raised when a contract cannot be located."""


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


def create_contract(
    *,
    title: str,
    parties: list[Any],
    status: str = ContractStatus.DRAFT,
    expires_at: Optional[Any] = None,
    owner: Any,
) -> Contract:
    """
    Create a new contract and record a CREATED event.

    Args:
        title: Human-readable contract title.
        parties: List of party identifiers/descriptors (stored as JSON).
        status: Initial status (defaults to DRAFT).
        expires_at: Optional expiry datetime.
        owner: User instance that owns the contract.

    Returns:
        The newly created Contract instance.
    """
    with transaction.atomic():
        contract = Contract.objects.create(
            title=title,
            parties=parties,
            status=status,
            expires_at=expires_at,
            owner=owner,
        )
        ContractEvent.objects.create(
            contract=contract,
            event_type=ContractEventType.CREATED,
            notes=f"Contract '{title}' created by {owner.username}.",
        )
        logger.info("Contract created: id=%s title=%r owner=%s", contract.pk, title, owner.username)
    return contract


def get_contract_with_clause_count(contract_id: int) -> Contract:
    """
    Fetch a single contract and annotate it with the clause count from MongoDB.

    The clause_count is attached as an attribute on the returned object.

    Args:
        contract_id: Primary key of the contract.

    Returns:
        Contract instance with a ``clause_count`` attribute.

    Raises:
        ContractNotFoundError: If no contract with the given ID exists.
    """
    from mongo_store.clause_store import ClauseStore

    try:
        contract = Contract.objects.select_related("owner").get(pk=contract_id)
    except Contract.DoesNotExist as exc:
        raise ContractNotFoundError(f"Contract {contract_id} not found.") from exc

    store = ClauseStore()
    contract.clause_count = store.count_clauses(contract_id)
    return contract


def list_contracts(
    *,
    status: Optional[str] = None,
    expires_before: Optional[Any] = None,
    owner: Optional[Any] = None,
) -> Any:
    """
    Return a queryset of contracts with optional filters.

    Args:
        status: Filter by contract status string.
        expires_before: Filter contracts expiring before this datetime.
        owner: Optionally restrict to contracts owned by this user.

    Returns:
        Django QuerySet of Contract objects.
    """
    qs = Contract.objects.select_related("owner").all()

    if status:
        qs = qs.filter(status=status)
    if expires_before:
        qs = qs.filter(expires_at__lte=expires_before)
    if owner:
        qs = qs.filter(owner=owner)

    return qs


def get_expiring_soon(days: int = 7) -> Any:
    """
    Return contracts expiring within the next ``days`` days.

    Args:
        days: Look-ahead window in days (default 7).

    Returns:
        Django QuerySet of Contract objects.
    """
    now = timezone.now()
    cutoff = now + timedelta(days=days)
    return (
        Contract.objects.select_related("owner")
        .filter(
            expires_at__gte=now,
            expires_at__lte=cutoff,
        )
        .exclude(status=ContractStatus.EXPIRED)
    )


# ---------------------------------------------------------------------------
# Status transitions
# ---------------------------------------------------------------------------


def transition_status(
    *,
    contract: Contract,
    new_status: str,
    notes: str = "",
    actor: Optional[Any] = None,
) -> Contract:
    """
    Attempt to transition ``contract`` to ``new_status``.

    Validates the transition using the ALLOWED_TRANSITIONS matrix.
    On success, updates the database and records a STATUS_CHANGED event.

    Args:
        contract: The contract instance to update.
        new_status: Target status value.
        notes: Optional human-readable note for the audit event.
        actor: User performing the transition (for logging).

    Returns:
        The updated Contract instance.

    Raises:
        ContractStatusError: If the transition is not permitted.
    """
    current = contract.status
    allowed = ALLOWED_TRANSITIONS.get(current, [])

    if new_status not in allowed:
        raise ContractStatusError(
            f"Transition from '{current}' to '{new_status}' is not allowed. "
            f"Permitted transitions: {allowed or 'none (terminal state)'}."
        )

    with transaction.atomic():
        contract.status = new_status
        contract.save(update_fields=["status", "updated_at"])

        actor_name = actor.username if actor else "system"
        event_notes = notes or f"Status changed from {current} to {new_status} by {actor_name}."
        ContractEvent.objects.create(
            contract=contract,
            event_type=ContractEventType.STATUS_CHANGED,
            notes=event_notes,
        )
        logger.info(
            "Contract %s status: %s → %s (actor=%s)",
            contract.pk,
            current,
            new_status,
            actor_name,
        )

    return contract
