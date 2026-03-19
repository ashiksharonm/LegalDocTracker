"""
Clause document store backed by MongoDB.

Collection schema:
    {
        "_id":             ObjectId,
        "contract_id":     int,
        "clause_number":   int,
        "clause_text":     str,
        "clause_type":     str,
        "flagged_keywords": [str],
        "created_at":      datetime
    }
"""
import logging
from datetime import datetime, timezone
from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

from .client import get_db

logger = logging.getLogger(__name__)

COLLECTION_NAME = "contract_clauses"


class ClauseStoreError(Exception):
    """Raised when a MongoDB clause operation fails."""


class ClauseStore:
    """
    Data-access layer for contract clause documents in MongoDB.

    All methods raise ClauseStoreError on MongoDB-level failures.
    """

    def __init__(self) -> None:
        """Initialise the clause store, ensuring indexes are created."""
        self._collection: Collection = get_db()[COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Create indexes for efficient clause retrieval."""
        try:
            self._collection.create_index(
                [("contract_id", 1), ("clause_number", 1)],
                unique=True,
                name="contract_clause_unique",
            )
            self._collection.create_index("contract_id", name="contract_id_idx")
        except PyMongoError as exc:
            logger.warning("Could not ensure MongoDB indexes: %s", exc)

    def add_clause(
        self,
        *,
        contract_id: int,
        clause_number: int,
        clause_text: str,
        clause_type: str,
        flagged_keywords: list[str] | None = None,
    ) -> ObjectId:
        """
        Insert a new clause document for a contract.

        Args:
            contract_id: PostgreSQL pk of the parent contract.
            clause_number: Sequential clause number within the contract.
            clause_text: Full text content of the clause.
            clause_type: Category string (e.g. INDEMNITY, LIABILITY).
            flagged_keywords: Optional list of риски keywords found in the clause.

        Returns:
            The MongoDB ObjectId of the inserted document.

        Raises:
            ClauseStoreError: If insertion fails (e.g. duplicate clause number).
        """
        document: dict[str, Any] = {
            "contract_id": contract_id,
            "clause_number": clause_number,
            "clause_text": clause_text,
            "clause_type": clause_type,
            "flagged_keywords": flagged_keywords or [],
            "created_at": datetime.now(tz=timezone.utc),
        }
        try:
            result = self._collection.insert_one(document)
            logger.debug(
                "Clause inserted: contract=%s clause_number=%s id=%s",
                contract_id,
                clause_number,
                result.inserted_id,
            )
            return result.inserted_id
        except PyMongoError as exc:
            raise ClauseStoreError(
                f"Failed to insert clause {clause_number} for contract {contract_id}: {exc}"
            ) from exc

    def get_clauses(self, contract_id: int) -> list[dict[str, Any]]:
        """
        Retrieve all clause documents for a contract, sorted by clause_number.

        Args:
            contract_id: PostgreSQL pk of the contract.

        Returns:
            List of clause dictionaries with ``_id`` serialised to string.

        Raises:
            ClauseStoreError: On MongoDB query failure.
        """
        try:
            cursor = self._collection.find(
                {"contract_id": contract_id},
                sort=[("clause_number", 1)],
            )
            clauses = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                # Serialise datetime for JSON
                if isinstance(doc.get("created_at"), datetime):
                    doc["created_at"] = doc["created_at"].isoformat()
                clauses.append(doc)
            return clauses
        except PyMongoError as exc:
            raise ClauseStoreError(
                f"Failed to retrieve clauses for contract {contract_id}: {exc}"
            ) from exc

    def count_clauses(self, contract_id: int) -> int:
        """
        Count the number of clause documents for a contract.

        Args:
            contract_id: PostgreSQL pk of the contract.

        Returns:
            Integer count.
        """
        try:
            return self._collection.count_documents({"contract_id": contract_id})
        except PyMongoError as exc:
            logger.warning("Failed to count clauses for contract %s: %s", contract_id, exc)
            return 0

    def delete_clauses_for_contract(self, contract_id: int) -> int:
        """
        Delete all clause documents for a given contract.

        Used primarily in tests for cleanup.

        Args:
            contract_id: PostgreSQL pk of the contract.

        Returns:
            Number of documents deleted.
        """
        try:
            result = self._collection.delete_many({"contract_id": contract_id})
            logger.debug("Deleted %s clauses for contract %s", result.deleted_count, contract_id)
            return result.deleted_count
        except PyMongoError as exc:
            raise ClauseStoreError(
                f"Failed to delete clauses for contract {contract_id}: {exc}"
            ) from exc
