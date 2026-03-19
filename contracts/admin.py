"""
Django Admin configuration for the contracts application.

Provides full CRUD with rich list displays, filters, and search.
"""
import logging

from django.contrib import admin
from django.utils.html import format_html

from .models import Contract, ContractEvent, Party

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Inline: ContractEvent inside Contract admin
# ---------------------------------------------------------------------------


class ContractEventInline(admin.TabularInline):
    """Inline display of contract events within the Contract admin."""

    model = ContractEvent
    extra = 0
    readonly_fields = ["event_type", "timestamp", "notes"]
    can_delete = False
    ordering = ["-timestamp"]
    max_num = 50


# ---------------------------------------------------------------------------
# Contract Admin
# ---------------------------------------------------------------------------


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    """Admin interface for the Contract model."""

    list_display = [
        "id",
        "title",
        "status_badge",
        "owner",
        "created_at",
        "expires_at",
        "is_expired_display",
    ]
    list_filter = ["status", "created_at", "expires_at"]
    search_fields = ["title", "owner__username", "owner__email"]
    readonly_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"
    inlines = [ContractEventInline]

    fieldsets = [
        (
            "Contract Information",
            {
                "fields": ["title", "parties", "status", "owner"],
            },
        ),
        (
            "Dates",
            {
                "fields": ["expires_at", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]

    @admin.display(description="Status")
    def status_badge(self, obj: Contract) -> str:
        """Render a coloured badge for the contract status."""
        colour_map = {
            "DRAFT": "#6c757d",
            "REVIEW": "#fd7e14",
            "SIGNED": "#198754",
            "EXPIRED": "#dc3545",
        }
        colour = colour_map.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:4px;">{}</span>',
            colour,
            obj.get_status_display(),
        )

    @admin.display(description="Expired?", boolean=True)
    def is_expired_display(self, obj: Contract) -> bool:
        """Return True if the contract has expired."""
        return obj.is_expired


# ---------------------------------------------------------------------------
# Party Admin
# ---------------------------------------------------------------------------


@admin.register(Party)
class PartyAdmin(admin.ModelAdmin):
    """Admin interface for the Party model."""

    list_display = ["id", "name", "email", "role", "created_at"]
    list_filter = ["role", "created_at"]
    search_fields = ["name", "email"]
    readonly_fields = ["created_at"]
    ordering = ["name"]


# ---------------------------------------------------------------------------
# ContractEvent Admin
# ---------------------------------------------------------------------------


@admin.register(ContractEvent)
class ContractEventAdmin(admin.ModelAdmin):
    """Admin interface for the ContractEvent model (read-only audit log)."""

    list_display = ["id", "contract", "event_type", "timestamp", "notes_preview"]
    list_filter = ["event_type", "timestamp"]
    search_fields = ["contract__title", "notes"]
    readonly_fields = ["contract", "event_type", "timestamp", "notes"]
    ordering = ["-timestamp"]

    def has_add_permission(self, request: object) -> bool:
        """Prevent creating events manually from admin."""
        return False

    def has_change_permission(self, request: object, obj: object = None) -> bool:
        """Events are immutable — no edit permission."""
        return False

    @admin.display(description="Notes")
    def notes_preview(self, obj: ContractEvent) -> str:
        """Return a truncated preview of the event notes."""
        return (obj.notes[:80] + "…") if len(obj.notes) > 80 else obj.notes
