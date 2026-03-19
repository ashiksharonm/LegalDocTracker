"""
URL configuration for LegalDocTracker project.
"""
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

admin.site.site_header = "LegalDocTracker Admin"
admin.site.site_title = "LegalDocTracker"
admin.site.index_title = "Contract Lifecycle Management"

urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),
    # JWT Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    # Contracts API
    path("api/", include("contracts.urls")),
]
