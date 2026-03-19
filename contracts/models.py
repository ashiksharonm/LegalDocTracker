"""
Django ORM models for the contracts application.

All relational data is stored in PostgreSQL. MongoDB is used separately
(via mongo_store) for unstructured clause documents.
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)

User = get_user_model()


class ContractStatus(models.TextChoices):
    """Enumeration of valid contract lifecycle states."""

    DRAFT = "DRAFT", "Draft"
    REVIEW = "REVIEW", "Under Review"
    SIGNED = "SIGNED", "Signed"
    EXPIRED = "EXPIRED", "Expired"


class PartyRole(models.TextChoices):
    """Roles a party can play in a contract."""

    INITIATOR = "INITIATOR", "Initiator"
    COUNTERPARTY = "COUNTERPARTY", "Counterparty"
    WITNESS = "WITNESS", "Witness"


class Contract(models.Model):
    """
    Represents a legal contract in the system.

    Stores relational metadata; raw clause text lives in MongoDB.
    """

    title = models.CharField(max_length=512, help_text="Descriptive title of the contract.")
    parties = models.JSONField(
        default=list,
        help_text="JSON list of party identifiers involved in the contract.",
    )
    status = models.CharField(
        max_length=10,
        choices=ContractStatus.choices,
        default=ContractStatus.DRAFT,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Optional expiry date/time in UTC.",
    )
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="contracts",
        help_text="User who created / owns this contract.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
        ]
        verbose_name = "Contract"
        verbose_name_plural = "Contracts"

    def __str__(self) -> str:
        return f"[{self.status}] {self.title}"

    @property
    def is_expired(self) -> bool:
        """Return True if the contract has passed its expiry date."""
        if self.expires_at is None:
            return False
        return timezone.now() > self.expires_at


class Party(models.Model):
    """
    Represents an individual or organisation that participates in contracts.
    """

    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    role = models.CharField(
        max_length=15,
        choices=PartyRole.choices,
        default=PartyRole.COUNTERPARTY,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Party"
        verbose_name_plural = "Parties"

    def __str__(self) -> str:
        return f"{self.name} ({self.role})"


class ContractEventType(models.TextChoices):
    """Types of events that can be recorded on a contract."""

    CREATED = "CREATED", "Created"
    STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"
    CLAUSE_ADDED = "CLAUSE_ADDED", "Clause Added"
    REVIEWED = "REVIEWED", "Reviewed"
    SIGNED = "SIGNED", "Signed"
    EXPIRED = "EXPIRED", "Expired"
    CUSTOM = "CUSTOM", "Custom"


class ContractEvent(models.Model):
    """
    Audit log entry for a contract.

    Immutable once created — events are append-only.
    """

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="events",
    )
    event_type = models.CharField(
        max_length=20,
        choices=ContractEventType.choices,
        default=ContractEventType.CUSTOM,
        db_index=True,
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Contract Event"
        verbose_name_plural = "Contract Events"

    def __str__(self) -> str:
        return f"{self.event_type} @ {self.timestamp:%Y-%m-%d %H:%M} on Contract #{self.contract_id}"
