from django.contrib import admin

from .models import PaymentTransaction, Withdrawal


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):

    list_display = (
        "withdrawal_reference",
        "campaign",
        "requested_by",
        "amount",
        "display_currency",
        "display_status",
        "approved_by",
        "approved_at",
        "paid_at",
        "created_at",
    )

    list_filter = (
        "status",
        "currency",
        "created_at",
        "approved_at",
        "paid_at",
    )

    search_fields = (
        "withdrawal_reference",
        "campaign__campaign_name",
        "campaign__campaign_slug",
        "requested_by__fullname",
        "requested_by__email",
        "requested_by__mobile",
        "approved_by__fullname",
        "approved_by__email",
        "remarks",
    )

    autocomplete_fields = (
        "campaign",
        "requested_by",
        "approved_by",
    )

    readonly_fields = (
        "uuid",
        "withdrawal_reference",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Withdrawal",
            {
                "fields": (
                    "uuid",
                    "withdrawal_reference",
                    "campaign",
                    "requested_by",
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
                )
            },
        ),
        (
            "Approval",
            {
                "fields": (
                    "approved_by",
                    "approved_at",
                    "remarks",
                )
            },
        ),
        (
            "Payout",
            {
                "fields": (
                    "paid_at",
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

    @admin.display(description="Status")
    def display_status(self, obj):
        value = obj.status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):

    list_display = (
        "uuid",
        "display_transaction_type",
        "display_gateway",
        "display_payment_method",
        "amount",
        "display_currency",
        "display_status",
        "gateway_order_id",
        "gateway_payment_id",
        "processed_at",
        "created_at",
    )

    list_filter = (
        "transaction_type",
        "gateway",
        "payment_method",
        "currency",
        "status",
        "created_at",
        "processed_at",
        "refunded_at",
    )

    search_fields = (
        "uuid",
        "gateway_order_id",
        "gateway_payment_id",
        "gateway_signature",
        "refund_id",
        "donation__unique_donation_number",
        "donation__campaign__campaign_name",
        "donation__donor__fullname",
        "donation__donor__email",
        "withdrawal__uuid",
    )

    autocomplete_fields = (
        "donation",
        "withdrawal",
    )

    filter_horizontal = (
        "campaign_promotion_services",
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
            "Transaction",
            {
                "fields": (
                    "uuid",
                    "transaction_type",
                    "donation",
                    "withdrawal",
                    "campaign_promotion_services",
                )
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "gateway",
                    "gateway_order_id",
                    "gateway_payment_id",
                    "gateway_signature",
                    "payment_method",
                    "amount",
                    "currency",
                    "status",
                )
            },
        ),
        (
            "Failure Information",
            {
                "fields": (
                    "failure_code",
                    "failure_reason",
                )
            },
        ),
        (
            "Gateway Response",
            {
                "fields": (
                    "gateway_response",
                )
            },
        ),
        (
            "Refund",
            {
                "fields": (
                    "refund_id",
                    "refund_amount",
                    "refund_reason",
                    "refunded_at",
                )
            },
        ),
        (
            "Processing",
            {
                "fields": (
                    "processed_at",
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

    @admin.display(description="Transaction Type")
    def display_transaction_type(self, obj):
        value = obj.transaction_type

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Gateway")
    def display_gateway(self, obj):
        value = obj.gateway

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Payment Method")
    def display_payment_method(self, obj):
        value = obj.payment_method

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Currency")
    def display_currency(self, obj):
        value = obj.currency

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