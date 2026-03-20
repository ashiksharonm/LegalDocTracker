"""AppConfig for the contracts application."""
from django.apps import AppConfig


class ContractsConfig(AppConfig):
    """App configuration for contracts."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "contracts"
    verbose_name = "Contract Lifecycle Management"

    def ready(self) -> None:
        """Import signals on app ready."""
        pass  # noqa: WPS604
