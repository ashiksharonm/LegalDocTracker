"""URL routing for the contracts application."""
from django.urls import path

from .views import (
    ContractListCreateView,
    ContractDetailView,
    ContractStatusUpdateView,
    ContractExpiringSoonView,
    ContractClauseView,
)

app_name = "contracts"

urlpatterns = [
    # Contract CRUD
    path("contracts/", ContractListCreateView.as_view(), name="contract-list-create"),
    path("contracts/expiring-soon/", ContractExpiringSoonView.as_view(), name="contract-expiring-soon"),
    path("contracts/<int:contract_id>/", ContractDetailView.as_view(), name="contract-detail"),
    path("contracts/<int:contract_id>/status/", ContractStatusUpdateView.as_view(), name="contract-status-update"),
    # MongoDB clause endpoints
    path("contracts/<int:contract_id>/clauses/", ContractClauseView.as_view(), name="contract-clauses"),
]
