"""
Initial migration for the contracts app.

Creates: Contract, Party, ContractEvent tables.
"""
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    """Initial schema for the contracts application."""

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Party",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("email", models.EmailField(max_length=254, unique=True)),
                ("role", models.CharField(
                    choices=[
                        ("INITIATOR", "Initiator"),
                        ("COUNTERPARTY", "Counterparty"),
                        ("WITNESS", "Witness"),
                    ],
                    default="COUNTERPARTY",
                    max_length=15,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Party",
                "verbose_name_plural": "Parties",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="Contract",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(help_text="Descriptive title of the contract.", max_length=512)),
                ("parties", models.JSONField(default=list, help_text="JSON list of party identifiers involved in the contract.")),
                ("status", models.CharField(
                    choices=[
                        ("DRAFT", "Draft"),
                        ("REVIEW", "Under Review"),
                        ("SIGNED", "Signed"),
                        ("EXPIRED", "Expired"),
                    ],
                    db_index=True,
                    default="DRAFT",
                    max_length=10,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField(
                    blank=True,
                    db_index=True,
                    help_text="Optional expiry date/time in UTC.",
                    null=True,
                )),
                ("owner", models.ForeignKey(
                    help_text="User who created / owns this contract.",
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="contracts",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "verbose_name": "Contract",
                "verbose_name_plural": "Contracts",
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["status", "expires_at"], name="contracts_c_status_4eabb2_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ContractEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(
                    choices=[
                        ("CREATED", "Created"),
                        ("STATUS_CHANGED", "Status Changed"),
                        ("CLAUSE_ADDED", "Clause Added"),
                        ("REVIEWED", "Reviewed"),
                        ("SIGNED", "Signed"),
                        ("EXPIRED", "Expired"),
                        ("CUSTOM", "Custom"),
                    ],
                    db_index=True,
                    default="CUSTOM",
                    max_length=20,
                )),
                ("timestamp", models.DateTimeField(db_index=True, default=django.utils.timezone.now)),
                ("notes", models.TextField(blank=True, default="")),
                ("contract", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="events",
                    to="contracts.contract",
                )),
            ],
            options={
                "verbose_name": "Contract Event",
                "verbose_name_plural": "Contract Events",
                "ordering": ["-timestamp"],
            },
        ),
    ]
