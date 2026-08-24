import razorpay

from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from crowdfunding.enums import (
    DonationStatus,
    PaymentMethod,
    TransactionStatus,
    WalletTransactionType,
)

from donations.models import (
    Donation,
    DonationReceipt,
)

from payments.models import PaymentTransaction
from wallets.models import WalletTransaction


# ============================================================
# RAZORPAY CLIENT
# ============================================================

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )
)


# ============================================================
# CREATE RAZORPAY ORDER
# ============================================================


def create_razorpay_order(*, donation):

    amount_in_paise = int(donation.amount * Decimal("100"))

    order_data = {
        "amount": amount_in_paise,
        "currency": donation.currency.value,
        "receipt": donation.unique_donation_number,
        "notes": {
            "donation_uuid": str(donation.uuid),
            "donation_number": donation.unique_donation_number,
            "campaign_uuid": str(donation.campaign.uuid),
        },
    }

    razorpay_order = razorpay_client.order.create(data=order_data)

    return razorpay_order

def create_platform_razorpay_order(donation):

    client = razorpay.Client(
        auth=(
            settings.RAZORPAY_KEY_ID,
            settings.RAZORPAY_KEY_SECRET,
        )
    )

    amount_in_paise = int(
        donation.amount * Decimal("100")
    )

    order_data = {
        "amount": amount_in_paise,
        "currency": donation.currency.value,
        "receipt": donation.unique_donation_number,
        "notes": {
            "donation_uuid": str(donation.uuid),
            "donation_number": donation.unique_donation_number,
            "donation_type": donation.donation_type.value,
            "donor_uuid": str(donation.donor.uuid),
        },
    }

    return client.order.create(data=order_data)
# ============================================================
# VERIFY CHECKOUT SIGNATURE
# ============================================================


def verify_razorpay_signature(
    *,
    order_id,
    payment_id,
    signature,
):

    razorpay_client.utility.verify_payment_signature(
        {
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        }
    )

    return True


# ============================================================
# FETCH PAYMENT
# ============================================================


def fetch_razorpay_payment(payment_id):

    return razorpay_client.payment.fetch(payment_id)


# ============================================================
# FETCH ORDER
# ============================================================


def fetch_razorpay_order(
    order_id,
):

    return razorpay_client.order.fetch(order_id)


# ============================================================
# FETCH PAYMENTS FOR ORDER
# ============================================================


def fetch_razorpay_order_payments(
    order_id,
):

    return razorpay_client.order.payments(order_id)


# ============================================================
# COMPLETE DONATION PAYMENT
# ============================================================


@transaction.atomic
def complete_donation_payment(
    *,
    payment_transaction,
    razorpay_payment,
    verified_by,
):

    # --------------------------------------------------------
    # Lock transaction
    # --------------------------------------------------------

    payment_transaction = (
        PaymentTransaction.objects.select_for_update()
        .select_related(
            "donation",
            "donation__campaign",
            "donation__campaign__wallet",
        )
        .get(uuid=payment_transaction.uuid)
    )

    donation = payment_transaction.donation

    campaign = donation.campaign

    wallet = campaign.wallet

    # --------------------------------------------------------
    # IDEMPOTENCY
    # --------------------------------------------------------

    if payment_transaction.status == TransactionStatus.SUCCESS:

        receipt = getattr(
            donation,
            "receipt",
            None,
        )

        return {
            "donation_uuid": str(donation.uuid),
            "donation_number": donation.unique_donation_number,
            "receipt_number": (receipt.receipt_num if receipt else None),
            "payment_status": payment_transaction.status.value,
            "donation_status": donation.status.value,
        }


    # --------------------------------------------------------
    # Validate payment ID
    # --------------------------------------------------------

    razorpay_payment_id = razorpay_payment.get("id")

    if razorpay_payment.get("order_id") != payment_transaction.gateway_order_id:
        raise ValueError("Razorpay payment does not belong to this order.")

    if not razorpay_payment_id:

        raise ValueError("Razorpay payment ID is missing.")

    # --------------------------------------------------------
    # Validate amount
    # --------------------------------------------------------

    razorpay_amount = Decimal(str(razorpay_payment["amount"])) / Decimal("100")

    if razorpay_amount != donation.amount:

        raise ValueError("Razorpay payment amount does not " "match donation amount.")

    # --------------------------------------------------------
    # Validate currency
    # --------------------------------------------------------

    if razorpay_payment["currency"] != donation.currency.value:

        raise ValueError(
            "Razorpay payment currency does not " "match donation currency."
        )

    # --------------------------------------------------------
    # Validate status
    # --------------------------------------------------------

    if razorpay_payment["status"] != "captured":
        raise ValueError("Razorpay payment has not been captured.")

    # --------------------------------------------------------
    # Prevent payment reuse
    # --------------------------------------------------------

    existing_payment = (
        PaymentTransaction.objects.filter(
            gateway_payment_id=razorpay_payment_id,
            status=TransactionStatus.SUCCESS,
        )
        .exclude(uuid=payment_transaction.uuid)
        .first()
    )

    if existing_payment:

        raise ValueError("This Razorpay payment has already " "been processed.")

    # --------------------------------------------------------
    # Payment method
    # --------------------------------------------------------

    payment_method_map = {
        "card": PaymentMethod.CARD,
        "upi": PaymentMethod.UPI,
        "netbanking": PaymentMethod.NETBANKING,
        "wallet": PaymentMethod.WALLET,
    }

    payment_method = payment_method_map.get(razorpay_payment.get("method"))

    # --------------------------------------------------------
    # Payment transaction
    # --------------------------------------------------------

    payment_transaction.gateway_payment_id = razorpay_payment_id


    payment_transaction.payment_method = payment_method

    payment_transaction.status = TransactionStatus.SUCCESS

    payment_transaction.processed_at = timezone.now()

    payment_transaction.gateway_response = razorpay_payment

    payment_transaction.save(
        update_fields=[
            "gateway_payment_id",
            "payment_method",
            "status",
            "processed_at",
            "gateway_response",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # Donation
    # --------------------------------------------------------

    donation.status = DonationStatus.SUCCESS

    donation.donated_at = timezone.now()

    donation.save(
        update_fields=[
            "status",
            "donated_at",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # Wallet
    # --------------------------------------------------------

    balance_before = wallet.balance

    balance_after = balance_before + donation.amount

    wallet.balance = balance_after

    wallet.save(
        update_fields=[
            "balance",
            "updated_at",
        ]
    )

    # --------------------------------------------------------
    # Wallet transaction
    # --------------------------------------------------------

    WalletTransaction.objects.create(
        wallet=wallet,
        transaction_type=(WalletTransactionType.CREDIT),
        amount=donation.amount,
        balance_before=balance_before,
        balance_after=balance_after,
        currency=wallet.currency,
        donation=donation,
        description=(f"Donation " f"{donation.unique_donation_number}"),
        created_by=verified_by,
    )

    # --------------------------------------------------------
    # Campaign
    # --------------------------------------------------------

    campaign.raised_amount += donation.amount

    is_existing_donor = (
        Donation.objects.filter(
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

    # --------------------------------------------------------
    # Receipt
    # --------------------------------------------------------

    receipt, _ = DonationReceipt.objects.get_or_create(
        donation=donation,
        
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {
        "donation_uuid": str(donation.uuid),
        "donation_number": donation.unique_donation_number,
        "receipt_number": receipt.receipt_num,
        "payment_status": payment_transaction.status.value,
        "donation_status": donation.status.value,
    }
