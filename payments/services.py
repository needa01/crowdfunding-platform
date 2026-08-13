# payments/services.py

from django.utils import timezone

from crowdfunding.enums import (
    DonationStatus,
    TransactionStatus,
    WalletTransactionType,
)

from donations.models import DonationReceipt
from wallets.models import WalletTransaction


def verify_donation_payment(
    payment_transaction,
    reference_number,
    verified_by,
):
    """
    Verify a donation payment.

    This method should be called only after all request validations
    have already been completed in the view.
    """

    donation = payment_transaction.donation
    campaign = donation.campaign
    wallet = campaign.wallet

    # ----------------------------------------
    # Update Payment Transaction
    # ----------------------------------------

    payment_transaction.gateway_reference_id = reference_number
    payment_transaction.status = TransactionStatus.SUCCESS
    payment_transaction.processed_at = timezone.now()

    payment_transaction.gateway_response = {
        "payment_mode": "MANUAL_DEMO",
        "reference_number": reference_number,
    }

    payment_transaction.save(
        update_fields=[
            "gateway_reference_id",
            "status",
            "processed_at",
            "gateway_response",
            "updated_at",
        ]
    )

    # ----------------------------------------
    # Update Donation
    # ----------------------------------------

    donation.status = DonationStatus.SUCCESS
    donation.donated_at = timezone.now()

    donation.save(
        update_fields=[
            "status",
            "donated_at",
            "updated_at",
        ]
    )

    # ----------------------------------------
    # Update Campaign Wallet
    # ----------------------------------------

    balance_before = wallet.balance
    balance_after = balance_before + donation.amount

    wallet.balance = balance_after

    wallet.save(
        update_fields=[
            "balance",
            "updated_at",
        ]
    )

    # ----------------------------------------
    # Wallet Transaction
    # ----------------------------------------

    WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=WalletTransactionType.CREDIT,
        amount=donation.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        currency=wallet.currency,
        donation=donation,
        description=f"Donation {donation.unique_donation_number}",
        created_by=verified_by,
    )

    # ----------------------------------------
    # Update Campaign Raised Amount
    # ----------------------------------------

    # ----------------------------------------
    # Update Campaign Summary
    # ----------------------------------------

    campaign.raised_amount += donation.amount

    # Count donor only once per campaign
    is_existing_donor = (
        donation.__class__.objects.filter(
            campaign=campaign,
            donor=donation.donor,
            status=DonationStatus.SUCCESS,
        )
        .exclude(pk=donation.pk)
        .exists()
    )

    if not is_existing_donor:
        campaign.total_donors += 1

    campaign.save(
        update_fields=[
            "raised_amount",
            "total_donors",
            "updated_at",
        ]
    )

    # ----------------------------------------
    # Generate Receipt
    # ----------------------------------------

    receipt, _ = DonationReceipt.objects.get_or_create(
        donation=donation,
        defaults={
            "generated_by": verified_by,
        },
    )

    return {
        "donation_uuid": str(donation.uuid),
        "donation_number": donation.unique_donation_number,
        "receipt_number": receipt.receipt_num,
        "payment_status": payment_transaction.status.value,
        "donation_status": donation.status.value,
    }

