from django.db import models
from django_enum.fields import EnumField
import uuid
from crowdfunding.enums import Currency, WalletTransactionType, WalletType


class Wallet(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    wallet_type = EnumField(
        WalletType,
        default=WalletType.CAMPAIGN
    )

    campaign = models.OneToOneField(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="wallet",
        blank=True,
        null=True,
    )

    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    currency = EnumField(
        Currency
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "wallets"
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.wallet_type == WalletType.CAMPAIGN and not self.campaign:
            raise ValidationError(
                {"campaign": "Campaign wallet must be linked to a campaign."}
            )

        if self.wallet_type == WalletType.PLATFORM and self.campaign:
            raise ValidationError(
                {"campaign": "Platform wallet cannot be linked to a campaign."}
            )

    def __str__(self):
        if self.wallet_type == WalletType.CAMPAIGN:
            return f"{self.campaign.title} Wallet"

        return "Platform Wallet"
    
    
class WalletTransaction(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    wallet = models.ForeignKey(
        "Wallet",
        on_delete=models.CASCADE,
        related_name="transactions",
    )

    transaction_type = EnumField(
        WalletTransactionType,
    )

    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    balance_before = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    balance_after = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    currency = EnumField(
        Currency,
        default=Currency.INR,
    )

    donation = models.ForeignKey(
        "donations.Donation",
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
        blank=True,
        null=True,
    )

    withdrawal = models.ForeignKey(
        "payments.Withdrawal",
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
        blank=True,
        null=True,
    )

    campaign_service = models.ForeignKey(
        "campaigns.CampaignPromotionService",
        on_delete=models.SET_NULL,
        related_name="wallet_transactions",
        blank=True,
        null=True,
    )

    description = models.TextField(
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        related_name="created_wallet_transactions",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "wallet_transactions"
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        references = [
            self.donation,
            self.withdrawal,
            self.campaign_service,
        ]

        if sum(ref is not None for ref in references) != 1:
            raise ValidationError(
                "A wallet transaction must reference exactly one of "
                "donation, withdrawal, or campaign_service."
            )

    def __str__(self):
        return (
            f"{self.wallet.uuid} | "
            f"{self.transaction_type} | "
            f"{self.amount}"
        )



