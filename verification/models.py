from django.db import models
import uuid

from django_enum.fields import EnumField
from accounts.models import CustomUser
from campaigns.models import Campaign
from django.conf import settings
from django.core.exceptions import ValidationError
from crowdfunding.enums import (
    DocOwner,
    DocumentPurpose,
    VerificationStatus,
    VerificationType,
)
from django.core.validators import RegexValidator
from django.db.models import Q


class DocumentType(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    applies_to = EnumField(DocOwner)
    is_required = models.BooleanField(default=False, editable=True)

    class Meta:
        db_table = "document_type"

        constraints = [
            models.UniqueConstraint(
                fields=["name", "applies_to"],
                name="unique_document_type_per_owner",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.applies_to.value})"


class Document(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    purpose = EnumField(DocumentPurpose, null=False)

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )

    campaign = models.ForeignKey(
        Campaign,
        on_delete=models.CASCADE,
        related_name="documents",
        null=True,
        blank=True,
    )

    document_type = models.ForeignKey(
        DocumentType, on_delete=models.PROTECT, related_name="documents"
    )

    document_holder_name = models.CharField(max_length=255)

    document_number = models.CharField(max_length=100, null=True, blank=True)

    file_url = models.FileField(upload_to="documents/docs/%Y/%m/")

    verification_status = EnumField(
        VerificationStatus, default=VerificationStatus.PENDING
    )

    ai_score = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )

    verification_remarks = models.TextField(null=True, blank=True)

    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_documents",
    )

    reviewed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "document_type", "purpose"],
                condition=models.Q(user__isnull=False),
                name="unique_user_document_type",
            ),
            models.UniqueConstraint(
                fields=["campaign", "document_type", "purpose"],
                condition=models.Q(campaign__isnull=False),
                name="unique_campaign_document_type",
            ),
        ]

    def clean(self):

        # Exactly one owner
        if bool(self.user) == bool(self.campaign):
            raise ValidationError(
                "A document must belong to either a user or a campaign."
            )

        # Profile verification
        if self.purpose == DocumentPurpose.PROFILE_VERIFICATION and not self.user:
            raise ValidationError({"user": "Profile verification requires a user."})

        # Campaign verification
        if self.purpose == DocumentPurpose.CAMPAIGN_VERIFICATION and not self.campaign:
            raise ValidationError(
                {"campaign": "Campaign verification requires a campaign."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.document_type} - {self.document_holder_name}"


class EntityVerificationRequest(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    verification_type = EnumField(VerificationType)

    user = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="verification_requests",
        blank=True,
        null=True,
    )

    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="verification_requests",
        blank=True,
        null=True,
    )

    status = EnumField(
        VerificationStatus,
        default=VerificationStatus.PENDING,
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    ai_result = models.JSONField(
        blank=True,
        null=True,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    reviewed_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="reviewed_verifications",
        blank=True,
        null=True,
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "entity_verification_requests"
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                name="unique_verification_per_user",
            ),
            models.UniqueConstraint(
                fields=["campaign"],
                name="unique_verification_per_campaign",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        # Individual / NGO / CSR verification
        if self.verification_type in (
            VerificationType.INDIVIDUAL,
            VerificationType.NGO,
            VerificationType.CSR,
        ):
            if not self.user:
                raise ValidationError(
                    {"user": "User is required for this verification type."}
                )

            if self.campaign:
                raise ValidationError(
                    {"campaign": "Campaign must be empty for this verification type."}
                )

        # Campaign verification
        elif self.verification_type == VerificationType.CAMPAIGN:
            if not self.campaign:
                raise ValidationError(
                    {"campaign": "Campaign is required for campaign verification."}
                )

            if self.user:
                raise ValidationError(
                    {"user": "User must be empty for campaign verification."}
                )

    def __str__(self):
        if self.user:
            return f"{self.verification_type} - {self.user.email}"

        return f"{self.verification_type} - {self.campaign.campaign_name}"
