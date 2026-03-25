"""
Initial migration for referrals app.
"""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ReferralCode",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("code", models.CharField(db_index=True, default="", max_length=20)),
                ("is_active", models.BooleanField(default=True)),
                ("max_uses", models.IntegerField(default=100)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referral_code",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Referral Code",
                "verbose_name_plural": "Referral Codes",
                "db_table": "referral_codes",
            },
        ),
        migrations.CreateModel(
            name="RewardTier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("min_referrals", models.IntegerField()),
                ("points", models.IntegerField(default=0)),
                ("premium_days", models.IntegerField(default=0)),
                ("badge", models.CharField(blank=True, max_length=100)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Reward Tier",
                "verbose_name_plural": "Reward Tiers",
                "db_table": "reward_tiers",
                "ordering": ["min_referrals"],
            },
        ),
        migrations.CreateModel(
            name="Referral",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("registered", "Registered"), ("subscribed", "Subscribed"), ("expired", "Expired")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("rewards_claimed", models.BooleanField(default=False)),
                ("subscribed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "referral_code",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals",
                        to="referrals.referralcode",
                    ),
                ),
                (
                    "referrer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals_made",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "referee",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="referrals_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Referral",
                "verbose_name_plural": "Referrals",
                "db_table": "referrals",
                "ordering": ["-created_at"],
                "unique_together": {("referrer", "email")},
            },
        ),
        migrations.CreateModel(
            name="RewardHistory",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "reward_type",
                    models.CharField(
                        choices=[("points", "Points"), ("premium_days", "Premium Days"), ("badge", "Badge")],
                        max_length=20,
                    ),
                ),
                ("reward_value", models.IntegerField()),
                ("description", models.TextField()),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "referral",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rewards",
                        to="referrals.referral",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reward_history",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Reward History",
                "verbose_name_plural": "Reward History",
                "db_table": "reward_history",
                "ordering": ["-created_at"],
            },
        ),
    ]
