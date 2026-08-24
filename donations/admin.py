from django.contrib import admin

from .models import Donation, DonationReceipt


@admin.register(Donation)
class DonationAdmin(admin.ModelAdmin):

    list_display = (
        "unique_donation_number",
        "campaign",
        "donor",
        "amount",
        "display_currency",
        "display_donation_type",
        "display_status",
        "is_anonymous",
        "donated_at",
        "created_at",
    )

    list_filter = (
        "donation_type",
        "currency",
        "status",
        "is_anonymous",
        "created_at",
        "donated_at",
    )

    search_fields = (
        "unique_donation_number",
        "campaign__campaign_name",
        "campaign__campaign_slug",
        "donor__fullname",
        "donor__email",
        "donor__mobile",
        "message",
    )

    autocomplete_fields = (
        "campaign",
        "donor",
    )

    readonly_fields = (
        "uuid",
        "unique_donation_number",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Donation",
            {
                "fields": (
                    "uuid",
                    "unique_donation_number",
                    "donation_type",
                    "campaign",
                    "donor",
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "amount",
                    "currency",
                    "status",
                    "donated_at",
                )
            },
        ),
        (
            "Donor Information",
            {
                "fields": (
                    "is_anonymous",
                    "message",
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

    @admin.display(description="Currency")
    def display_currency(self, obj):
        value = obj.currency

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Donation Type")
    def display_donation_type(self, obj):
        value = obj.donation_type

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Status")
    def display_status(self, obj):
        value = obj.status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)


@admin.register(DonationReceipt)
class DonationReceiptAdmin(admin.ModelAdmin):

    list_display = (
        "receipt_num",
        "donation",
        "display_donation_number",
        "generated_by",
        "generated_at",
        "email_sent_at",
    )

    search_fields = (
        "receipt_num",
        "donation__unique_donation_number",
        "donation__campaign__campaign_name",
        "donation__donor__fullname",
        "donation__donor__email",
        "generated_by__fullname",
        "generated_by__email",
    )

    list_filter = (
        "generated_at",
        "email_sent_at",
    )

    autocomplete_fields = (
        "donation",
        "generated_by",
    )

    readonly_fields = (
        "uuid",
        "receipt_num",
        "generated_at",
        "email_sent_at",
    )

    ordering = (
        "-generated_at",
    )

    fieldsets = (
        (
            "Receipt",
            {
                "fields": (
                    "uuid",
                    "receipt_num",
                    "donation",
                    "receipt_file",
                )
            },
        ),
        (
            "Generation",
            {
                "fields": (
                    "generated_by",
                    "generated_at",
                )
            },
        ),
        (
            "Email",
            {
                "fields": (
                    "email_sent_at",
                )
            },
        ),
    )

    @admin.display(description="Donation Number")
    def display_donation_number(self, obj):
        if obj.donation:
            return obj.donation.unique_donation_number

        return "-"