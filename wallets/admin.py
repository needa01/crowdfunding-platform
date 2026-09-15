from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import Wallet, WalletTransaction


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):

    list_display = (
        "uuid",
        "display_wallet_type",
        "campaign",
        "balance",
        "currency",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "wallet_type",
        "currency",
        "created_at",
    )

    search_fields = (
        "uuid",
        "campaign__campaign_name",
        "campaign__campaign_slug",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )
    
    @admin.display(description="Wallet Type")
    def display_wallet_type(self,obj):
        value = obj.wallet_type
    
        if value is None:
            return "-"
    
        if hasattr(value, "value"):
            return value.value
    
        return str(value)


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):

    list_display = (
        "uuid",
        "wallet",
        "transaction_type",
        "amount",
        "balance_before",
        "balance_after",
        "currency",
        "donation",
        "withdrawal",
        "created_by",
        "created_at",
    )

    list_filter = (
        "transaction_type",
        "currency",
        "created_at",
    )

    search_fields = (
        "uuid",
        "wallet__uuid",
        "donation__unique_donation_number",
        "donation__uuid",
        "withdrawal__uuid",
        "created_by__email",
    )

    readonly_fields = (
        "uuid",
        "created_at",
    )

    ordering = (
        "-created_at",
    )

    autocomplete_fields = (
        "wallet",
        "donation",
        "withdrawal",
        "created_by",
    )
    
    