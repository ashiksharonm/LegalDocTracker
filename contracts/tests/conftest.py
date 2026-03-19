"""
pytest-django fixtures and test configuration for the contracts test suite.

Uses factory_boy for model creation and mongomock (or real MongoDB) for clause store.
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from contracts.models import Contract, Party, ContractEvent, ContractStatus, PartyRole

User = get_user_model()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def user(db):
    """Create a regular authenticated user."""
    return User.objects.create_user(
        username="testuser",
        email="testuser@example.com",
        password="SecurePass123!",
    )


@pytest.fixture
def other_user(db):
    """Create a second user for ownership tests."""
    return User.objects.create_user(
        username="otheruser",
        email="otheruser@example.com",
        password="SecurePass123!",
    )


@pytest.fixture
def admin_user(db):
    """Create a superuser for admin tests."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
    )


# ---------------------------------------------------------------------------
# API client fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def api_client():
    """Return an unauthenticated DRF test client."""
    from rest_framework.test import APIClient
    return APIClient()


@pytest.fixture
def auth_client(api_client, user):
    """Return a DRF test client authenticated as `user` via JWT."""
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")
    return api_client


# ---------------------------------------------------------------------------
# Contract fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def contract(db, user):
    """Create a basic DRAFT contract."""
    return Contract.objects.create(
        title="Sample NDA Agreement",
        parties=[{"name": "Acme Corp"}, {"name": "Beta Ltd"}],
        status=ContractStatus.DRAFT,
        owner=user,
        expires_at=timezone.now() + timedelta(days=30),
    )


@pytest.fixture
def signed_contract(db, user):
    """Create a SIGNED contract."""
    return Contract.objects.create(
        title="Signed Service Agreement",
        parties=[{"name": "Alpha Inc"}],
        status=ContractStatus.SIGNED,
        owner=user,
        expires_at=timezone.now() + timedelta(days=90),
    )


@pytest.fixture
def expiring_contract(db, user):
    """Create a contract expiring in 3 days."""
    return Contract.objects.create(
        title="Expiring Soon Contract",
        parties=[{"name": "Gamma LLC"}],
        status=ContractStatus.REVIEW,
        owner=user,
        expires_at=timezone.now() + timedelta(days=3),
    )


@pytest.fixture
def expired_contract(db, user):
    """Create a contract that has already expired."""
    return Contract.objects.create(
        title="Lapsed Contract",
        parties=[{"name": "Delta Co"}],
        status=ContractStatus.EXPIRED,
        owner=user,
        expires_at=timezone.now() - timedelta(days=1),
    )


# ---------------------------------------------------------------------------
# Party fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def party(db):
    """Create a basic party."""
    return Party.objects.create(
        name="Acme Corp",
        email="legal@acme.com",
        role=PartyRole.INITIATOR,
    )


# ---------------------------------------------------------------------------
# MongoDB mock fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_clause_store(monkeypatch):
    """
    Monkeypatches ClauseStore to use an in-memory dict store during tests.

    Avoids requiring a live MongoDB instance in CI.
    """
    from unittest.mock import MagicMock
    from bson import ObjectId

    storage: dict[int, list[dict]] = {}

    mock_store = MagicMock()

    def _add_clause(*, contract_id, clause_number, clause_text, clause_type, flagged_keywords=None):
        oid = ObjectId()
        storage.setdefault(contract_id, []).append({
            "_id": str(oid),
            "contract_id": contract_id,
            "clause_number": clause_number,
            "clause_text": clause_text,
            "clause_type": clause_type,
            "flagged_keywords": flagged_keywords or [],
        })
        return oid

    def _get_clauses(contract_id):
        return sorted(storage.get(contract_id, []), key=lambda c: c["clause_number"])

    def _count_clauses(contract_id):
        return len(storage.get(contract_id, []))

    def _delete_clauses(contract_id):
        deleted = len(storage.get(contract_id, []))
        storage.pop(contract_id, None)
        return deleted

    mock_store.add_clause.side_effect = _add_clause
    mock_store.get_clauses.side_effect = _get_clauses
    mock_store.count_clauses.side_effect = _count_clauses
    mock_store.delete_clauses_for_contract.side_effect = _delete_clauses

    monkeypatch.setattr(
        "mongo_store.clause_store.ClauseStore",
        lambda: mock_store,
    )
    monkeypatch.setattr(
        "contracts.views.ClauseStore",
        lambda: mock_store,
    )
    monkeypatch.setattr(
        "contracts.services.ClauseStore",
        lambda: mock_store,
    )

    return mock_store, storage
