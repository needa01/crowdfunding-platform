from django.db import models
from django_enum.fields import EnumField
import uuid
from crowdfunding.enums import (
    Currency,
    PaymentGateway,
    PaymentMethod,
    TransactionStatus,
    TransactionType,
    WithdrawalStatus,
)
from crowdfunding.utils import generate_withdrawal_reference


class Withdrawal(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    withdrawal_reference = models.CharField(
        max_length=20,
        unique=True,
        default=generate_withdrawal_reference,
        editable=False,
    )

    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="withdrawals",
    )

    requested_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.PROTECT,
        related_name="requested_withdrawals",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = EnumField(Currency)

    status = EnumField(
        WithdrawalStatus,
        default=WithdrawalStatus.PENDING,
    )

    remarks = models.TextField(
        blank=True,
        null=True,
    )

    approved_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.PROTECT,
        related_name="approved_withdrawals",
        blank=True,
        null=True,
    )

    approved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    paid_at = models.DateTimeField(
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
        db_table = "withdrawal"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.campaign.title} - ₹{self.amount}"


class PaymentTransaction(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    transaction_type = EnumField(TransactionType)

    campaign_promotion_services = models.ManyToManyField(
        "campaigns.CampaignPromotionService",
        related_name="payment_transactions",
        blank=True
    )

    donation = models.OneToOneField(
        "donations.Donation",
        on_delete=models.CASCADE,
        related_name="transaction",
        blank=True,
        null=True,
    )

    withdrawal = models.ForeignKey(
        "Withdrawal",
        on_delete=models.CASCADE,
        related_name="transactions",
        blank=True,
        null=True,
    )

    gateway = EnumField(PaymentGateway)

    gateway_order_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    gateway_payment_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    gateway_signature = models.CharField(
        max_length=500,
        blank=True,
        null=True,
    )

    payment_method = EnumField(
        PaymentMethod,
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = EnumField(Currency)

    status = EnumField(
        TransactionStatus,
        default=TransactionStatus.PENDING,
    )

    failure_code = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    failure_reason = models.TextField(
        blank=True,
        null=True,
    )

    gateway_response = models.JSONField(
        blank=True,
        null=True,
    )

    refund_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    refund_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
    )

    refund_reason = models.TextField(
        blank=True,
        null=True,
    )

    processed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    refunded_at = models.DateTimeField(
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
        db_table = "transaction"
        ordering = ["-created_at"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.transaction_type == TransactionType.DONATION:
            if not self.donation or self.withdrawal:
                raise ValidationError(
                    "Donation transaction must reference only a donation."
                )

        elif self.transaction_type == TransactionType.WITHDRAWAL:
            if not self.withdrawal or self.donation:
                raise ValidationError(
                    "Withdrawal transaction must reference only a withdrawal."
                )

    def __str__(self):
        if self.donation:
            return f"{self.donation.unique_donation_number} - {self.status}"

        return f"{self.uuid} - {self.status}"
