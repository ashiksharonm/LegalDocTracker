"""
Test suite for LegalDocTracker — 17 tests covering:

1.  Contract creation (authenticated)
2.  Contract creation (unauthenticated → 401)
3.  Contract creation with invalid parties
4.  Contract creation with past expiry date
5.  Contract list endpoint
6.  Contract list filtered by status
7.  Contract list filtered by expires_before
8.  Contract detail endpoint with clause count
9.  Contract detail — 404 for missing contract
10. Status transition: DRAFT → REVIEW (valid)
11. Status transition: REVIEW → SIGNED (valid)
12. Status transition: SIGNED → DRAFT (invalid)
13. Status transition: EXPIRED → any (terminal)
14. Expiring-soon endpoint
15. Add clause to MongoDB
16. Get clauses from MongoDB (multiple)
17. Clause endpoint returns 404 for missing contract
"""
import pytest
from django.utils import timezone
from datetime import timedelta
from rest_framework import status

from contracts.models import Contract, ContractStatus, ContractEvent


# ===========================================================================
# 1. Contract creation — authenticated
# ===========================================================================


@pytest.mark.django_db
def test_create_contract_authenticated(auth_client, user):
    """Authenticated user should create a contract and get 201."""
    payload = {
        "title": "Vendor Agreement 2025",
        "parties": [{"name": "Vendor Inc"}, {"name": "Buyer Corp"}],
        "expires_at": (timezone.now() + timedelta(days=60)).isoformat(),
    }
    response = auth_client.post("/api/contracts/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED, response.data
    assert response.data["status"] == "ok"
    assert response.data["data"]["title"] == "Vendor Agreement 2025"
    assert response.data["data"]["status"] == ContractStatus.DRAFT

    # Verify DB record
    assert Contract.objects.filter(title="Vendor Agreement 2025").exists()

    # Verify audit event was created
    contract_id = response.data["data"]["id"]
    assert ContractEvent.objects.filter(contract_id=contract_id, event_type="CREATED").exists()


# ===========================================================================
# 2. Contract creation — unauthenticated (should 401)
# ===========================================================================


@pytest.mark.django_db
def test_create_contract_unauthenticated(api_client):
    """Unauthenticated requests should be rejected with 401."""
    payload = {
        "title": "Unauthorized Contract",
        "parties": [{"name": "Anon"}],
    }
    response = api_client.post("/api/contracts/", payload, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ===========================================================================
# 3. Contract creation — invalid parties (empty list)
# ===========================================================================


@pytest.mark.django_db
def test_create_contract_empty_parties(auth_client):
    """Creating a contract with an empty parties list should fail with 400."""
    payload = {
        "title": "Bad Contract",
        "parties": [],
    }
    response = auth_client.post("/api/contracts/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "parties" in str(response.data)


# ===========================================================================
# 4. Contract creation — past expiry date
# ===========================================================================


@pytest.mark.django_db
def test_create_contract_past_expiry(auth_client):
    """A contract with an expiry date in the past should be rejected."""
    payload = {
        "title": "Past Expiry Contract",
        "parties": [{"name": "Someone"}],
        "expires_at": (timezone.now() - timedelta(days=1)).isoformat(),
    }
    response = auth_client.post("/api/contracts/", payload, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "expires_at" in str(response.data)


# ===========================================================================
# 5. Contract list endpoint
# ===========================================================================


@pytest.mark.django_db
def test_list_contracts(auth_client, contract):
    """List endpoint should return all contracts for the authenticated user."""
    response = auth_client.get("/api/contracts/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == "ok"
    assert response.data["count"] >= 1

    titles = [c["title"] for c in response.data["results"]]
    assert contract.title in titles


# ===========================================================================
# 6. Contract list — filter by status
# ===========================================================================


@pytest.mark.django_db
def test_list_contracts_filter_by_status(auth_client, contract, signed_contract):
    """List endpoint should apply status filter correctly."""
    response = auth_client.get("/api/contracts/?status=DRAFT")
    assert response.status_code == status.HTTP_200_OK

    returned_statuses = {c["status"] for c in response.data["results"]}
    assert returned_statuses == {"DRAFT"}


# ===========================================================================
# 7. Contract list — filter by expires_before
# ===========================================================================


@pytest.mark.django_db
def test_list_contracts_filter_expires_before(auth_client, expiring_contract, contract):
    """List endpoint should filter by expires_before datetime."""
    # Use strftime with explicit 'Z' (UTC) — avoids the '+' sign that gets
    # decoded as a space in query strings, breaking parse_datetime → 400.
    cutoff = (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    response = auth_client.get(f"/api/contracts/?expires_before={cutoff}")
    assert response.status_code == status.HTTP_200_OK

    ids = [c["id"] for c in response.data["results"]]
    assert expiring_contract.id in ids
    assert contract.id not in ids  # expires in 30 days


# ===========================================================================
# 8. Contract detail with clause count (mock MongoDB)
# ===========================================================================


@pytest.mark.django_db
def test_contract_detail_with_clause_count(auth_client, contract, mock_clause_store):
    """Detail endpoint should return the contract and its clause count."""
    mock_store, storage = mock_clause_store

    # Populate the in-memory store with 3 dummy clauses so count_clauses returns 3
    # (setting .return_value fails because the fixture sets a .side_effect)
    storage[contract.id] = [{}, {}, {}]

    response = auth_client.get(f"/api/contracts/{contract.id}/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"]["id"] == contract.id
    assert response.data["data"]["clause_count"] == 3


# ===========================================================================
# 9. Contract detail — 404 for missing contract
# ===========================================================================


@pytest.mark.django_db
def test_contract_detail_not_found(auth_client):
    """Requesting a non-existent contract should return 404."""
    response = auth_client.get("/api/contracts/99999/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ===========================================================================
# 10. Status transition: DRAFT → REVIEW (valid)
# ===========================================================================


@pytest.mark.django_db
def test_status_transition_draft_to_review(auth_client, contract):
    """Valid DRAFT → REVIEW transition should succeed."""
    response = auth_client.patch(
        f"/api/contracts/{contract.id}/status/",
        {"status": "REVIEW", "notes": "Moving to legal review."},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"]["status"] == "REVIEW"

    contract.refresh_from_db()
    assert contract.status == ContractStatus.REVIEW
    assert ContractEvent.objects.filter(
        contract=contract, event_type="STATUS_CHANGED"
    ).exists()


# ===========================================================================
# 11. Status transition: REVIEW → SIGNED (valid)
# ===========================================================================


@pytest.mark.django_db
def test_status_transition_review_to_signed(auth_client, db, user):
    """Valid REVIEW → SIGNED transition should succeed."""
    c = Contract.objects.create(
        title="Review Contract",
        parties=[{"name": "X"}],
        status=ContractStatus.REVIEW,
        owner=user,
    )
    response = auth_client.patch(
        f"/api/contracts/{c.id}/status/",
        {"status": "SIGNED"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["data"]["status"] == "SIGNED"


# ===========================================================================
# 12. Status transition: SIGNED → DRAFT (invalid)
# ===========================================================================


@pytest.mark.django_db
def test_status_transition_signed_to_draft_forbidden(auth_client, signed_contract):
    """Attempting SIGNED → DRAFT should return 400 with error detail."""
    response = auth_client.patch(
        f"/api/contracts/{signed_contract.id}/status/",
        {"status": "DRAFT"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "status" in response.data.get("errors", {}) or "error" in str(response.data)


# ===========================================================================
# 13. Status transition: EXPIRED is a terminal state
# ===========================================================================


@pytest.mark.django_db
def test_status_transition_from_expired_is_terminal(auth_client, expired_contract):
    """No transitions from EXPIRED should be allowed."""
    for target in ["DRAFT", "REVIEW", "SIGNED"]:
        response = auth_client.patch(
            f"/api/contracts/{expired_contract.id}/status/",
            {"status": target},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST, (
            f"Expected 400 for EXPIRED → {target}"
        )


# ===========================================================================
# 14. Expiring-soon endpoint
# ===========================================================================


@pytest.mark.django_db
def test_expiring_soon_endpoint(auth_client, expiring_contract, contract):
    """Expiring-soon should return contracts due within 7 days, excluding EXPIRED."""
    response = auth_client.get("/api/contracts/expiring-soon/")
    assert response.status_code == status.HTTP_200_OK

    ids = [c["id"] for c in response.data["results"]]
    assert expiring_contract.id in ids
    # contract expires in 30 days — should not appear
    assert contract.id not in ids


# ===========================================================================
# 15. Add clause to MongoDB
# ===========================================================================


@pytest.mark.django_db
def test_add_clause_to_contract(auth_client, contract, mock_clause_store):
    """POST /api/contracts/{id}/clauses/ should insert a clause document."""
    payload = {
        "clause_number": 1,
        "clause_text": "The vendor shall deliver goods within 30 days.",
        "clause_type": "DELIVERY",
        "flagged_keywords": ["30 days", "deliver"],
    }
    response = auth_client.post(
        f"/api/contracts/{contract.id}/clauses/",
        payload,
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == "ok"
    assert "inserted_id" in response.data


# ===========================================================================
# 16. Get clauses from MongoDB (multiple)
# ===========================================================================


@pytest.mark.django_db
def test_get_clauses_for_contract(auth_client, contract, mock_clause_store):
    """GET /api/contracts/{id}/clauses/ should return all stored clauses."""
    mock_store, storage = mock_clause_store

    # Pre-populate storage
    storage[contract.id] = [
        {"_id": "abc", "contract_id": contract.id, "clause_number": 1, "clause_text": "Clause 1", "clause_type": "PAYMENT", "flagged_keywords": []},
        {"_id": "def", "contract_id": contract.id, "clause_number": 2, "clause_text": "Clause 2", "clause_type": "TERMINATION", "flagged_keywords": ["terminate"]},
    ]

    response = auth_client.get(f"/api/contracts/{contract.id}/clauses/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 2
    clause_types = {c["clause_type"] for c in response.data["results"]}
    assert clause_types == {"PAYMENT", "TERMINATION"}


# ===========================================================================
# 17. Clause endpoint — 404 for missing contract
# ===========================================================================


@pytest.mark.django_db
def test_add_clause_contract_not_found(auth_client):
    """Adding a clause to a non-existent contract should return 404."""
    payload = {
        "clause_number": 1,
        "clause_text": "Some text",
        "clause_type": "MISC",
    }
    response = auth_client.post("/api/contracts/99999/clauses/", payload, format="json")
    assert response.status_code == status.HTTP_404_NOT_FOUND
