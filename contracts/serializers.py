"""
Serializers for the contracts application.

Handles validation, representation, and transformation of contract data.
"""
import logging
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from .models import Contract, Party, ContractEvent, ContractStatus

logger = logging.getLogger(__name__)


class PartySerializer(serializers.ModelSerializer):
    """Serializer for Party model."""

    class Meta:
        model = Party
        fields = ["id", "name", "email", "role", "created_at"]
        read_only_fields = ["id", "created_at"]


class ContractEventSerializer(serializers.ModelSerializer):
    """Serializer for ContractEvent model."""

    class Meta:
        model = ContractEvent
        fields = ["id", "contract", "event_type", "timestamp", "notes"]
        read_only_fields = ["id", "timestamp"]


class ContractCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating a new contract.

    The `owner` field is set automatically from the authenticated user.
    """

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "parties",
            "status",
            "expires_at",
            "created_at",
            "updated_at",
            "owner",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "owner"]

    def validate_expires_at(self, value: Any) -> Any:
        """Ensure expiry date is in the future."""
        if value and value <= timezone.now():
            raise serializers.ValidationError("expires_at must be a future date/time.")
        return value

    def validate_parties(self, value: Any) -> Any:
        """Ensure parties is a non-empty list."""
        if not isinstance(value, list) or len(value) == 0:
            raise serializers.ValidationError("parties must be a non-empty list.")
        return value


class ContractDetailSerializer(serializers.ModelSerializer):
    """
    Full contract detail serializer including clause count from MongoDB.
    """

    owner_username = serializers.SerializerMethodField()
    clause_count = serializers.IntegerField(read_only=True, default=0)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "parties",
            "status",
            "created_at",
            "updated_at",
            "expires_at",
            "owner",
            "owner_username",
            "clause_count",
            "is_expired",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "owner"]

    def get_owner_username(self, obj: Contract) -> str:
        """Return the username of the contract owner."""
        return obj.owner.username


class ContractListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for list views.
    """

    owner_username = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Contract
        fields = [
            "id",
            "title",
            "status",
            "created_at",
            "expires_at",
            "owner",
            "owner_username",
            "is_expired",
        ]
        read_only_fields = fields

    def get_owner_username(self, obj: Contract) -> str:
        """Return the username of the contract owner."""
        return obj.owner.username


class ContractStatusUpdateSerializer(serializers.Serializer):
    """Serializer for PATCH /contracts/{id}/status/ endpoint."""

    status = serializers.ChoiceField(choices=ContractStatus.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ClauseCreateSerializer(serializers.Serializer):
    """Serializer for adding a clause to a contract's MongoDB document."""

    clause_number = serializers.IntegerField(min_value=1)
    clause_text = serializers.CharField(min_length=1)
    clause_type = serializers.CharField(max_length=128)
    flagged_keywords = serializers.ListField(
        child=serializers.CharField(max_length=128),
        required=False,
        default=list,
    )

    def validate_clause_text(self, value: str) -> str:
        """Strip leading/trailing whitespace from clause text."""
        return value.strip()
