from django.contrib import admin

from .models import (
    DocumentType,
    Document,
    EntityVerificationRequest,
)


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):

    list_display = (
        "name",
        "display_applies_to",
        "is_required",
        "uuid",
    )

    list_filter = (
        "applies_to",
        "is_required",
    )

    search_fields = (
        "name",
    )

    readonly_fields = (
        "uuid",
    )

    ordering = (
        "name",
    )

    fieldsets = (
        (
            "Document Type",
            {
                "fields": (
                    "uuid",
                    "name",
                    "applies_to",
                    "is_required",
                )
            },
        ),
    )

    @admin.display(description="Applies To")
    def display_applies_to(self, obj):
        value = obj.applies_to

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):

    list_display = (
        "document_type",
        "document_holder_name",
        "document_number",
        "display_purpose",
        "display_verification_status",
        "ai_score",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )

    list_filter = (
        "purpose",
        "verification_status",
        "document_type",
        "created_at",
        "reviewed_at",
    )

    search_fields = (
        "document_holder_name",
        "document_number",
        "user__fullname",
        "user__email",
        "user__mobile",
        "campaign__campaign_name",
        "campaign__campaign_slug",
        "verification_remarks",
    )

    autocomplete_fields = (
        "user",
        "campaign",
        "document_type",
        "reviewed_by",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Document",
            {
                "fields": (
                    "uuid",
                    "purpose",
                    "document_type",
                    "document_holder_name",
                    "document_number",
                    "file_url",
                )
            },
        ),
        (
            "Owner",
            {
                "fields": (
                    "user",
                    "campaign",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "verification_status",
                    "ai_score",
                    "verification_remarks",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Purpose")
    def display_purpose(self, obj):
        value = obj.purpose

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Verification Status")
    def display_verification_status(self, obj):
        value = obj.verification_status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)


@admin.register(EntityVerificationRequest)
class EntityVerificationRequestAdmin(admin.ModelAdmin):

    list_display = (
        "display_verification_type",
        "display_owner",
        "display_status",
        "ai_score",
        "reviewed_by",
        "reviewed_at",
        "created_at",
    )

    list_filter = (
        "verification_type",
        "status",
        "created_at",
        "reviewed_at",
    )

    search_fields = (
        "user__fullname",
        "user__email",
        "user__mobile",
        "campaign__campaign_name",
        "campaign__campaign_slug",
        "remarks",
    )

    autocomplete_fields = (
        "user",
        "campaign",
        "reviewed_by",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Verification Request",
            {
                "fields": (
                    "uuid",
                    "verification_type",
                    "status",
                )
            },
        ),
        (
            "Entity",
            {
                "fields": (
                    "user",
                    "campaign",
                )
            },
        ),
        (
            "AI Verification",
            {
                "fields": (
                    "ai_score",
                    "ai_result",
                )
            },
        ),
        (
            "Manual Review",
            {
                "fields": (
                    "remarks",
                    "reviewed_by",
                    "reviewed_at",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Verification Type")
    def display_verification_type(self, obj):
        value = obj.verification_type

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Owner")
    def display_owner(self, obj):
        if obj.user:
            return obj.user.email

        if obj.campaign:
            return obj.campaign.campaign_name

        return "-"

    @admin.display(description="Status")
    def display_status(self, obj):
        value = obj.status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)