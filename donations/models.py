from django.db import models
from django.utils import timezone
from django_enum.fields import EnumField
import uuid
from crowdfunding.enums import Currency, DonationStatus, DonationType
from crowdfunding.utils import generate_donation_number, generate_receipt_number


class Donation(models.Model):
    
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    
    donation_type = EnumField(
        DonationType, default=DonationType.CAMPAIGN
    )
    
    unique_donation_number = models.CharField(
        max_length=16,
        unique=True,
        default=generate_donation_number,
        editable=False,
        db_index=True,
    )
    
    campaign = models.ForeignKey(
        "campaigns.Campaign",
        on_delete=models.CASCADE,
        related_name="donations"
    )

    donor = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.CASCADE,
        related_name="donations"
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    currency = EnumField(
        Currency,
        default=Currency.INR
    )

    is_anonymous = models.BooleanField(default=False)

    message = models.TextField(
        blank=True,
        null=True
    )

    status = EnumField(
        DonationStatus,
        default=DonationStatus.PENDING
    )

    donated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        db_table = "donation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.donor} - {self.amount} {self.currency}"
    
    
class DonationReceipt(models.Model):
    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    donation = models.OneToOneField(
        "Donation",
        on_delete=models.CASCADE,
        related_name="receipt"
    )

    receipt_num = models.CharField(
        max_length=17,
        unique=True,
        default=generate_receipt_number,
        editable=False,
        db_index=True,
    )

    receipt_file = models.FileField(
        upload_to="documents/receipt/%Y/%m/",
        null=True,
        blank=True,
    )
    

    email_sent_at = models.DateTimeField(
        blank=True,
        null=True
    )

    generated_at = models.DateTimeField(
        null=True,
        blank=True
    )

    generated_by = models.ForeignKey(
        "accounts.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_receipts"
    )

    class Meta:
        db_table = "donation_receipt"
        ordering = ["-generated_at"]

    def __str__(self):
        return self.receipt_num


