from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from crowdfunding.permissions import CanDonate
from crowdfunding.enums import TransactionStatus, TransactionType
from payments.models import PaymentTransaction

from .services import verify_donation_payment


@api_view(["POST"])
@permission_classes([CanDonate])
@transaction.atomic
def verify_payment(request):

    print("Verify Payment API called")

    transaction_uuid = request.data.get("transaction_uuid")
    reference_number = request.data.get("reference_number")

    # ---------------------------------------
    # Validate Request
    # ---------------------------------------

    if not transaction_uuid:
        return Response(
            {"success": False, "message": "Transaction UUID is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not reference_number:
        return Response(
            {"success": False, "message": "Reference number is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------
    # Fetch Transaction
    # ---------------------------------------

    try:
        payment_transaction = (
            PaymentTransaction.objects.select_for_update(of=("self",))
            .select_related(
                "donation",
                "donation__campaign",
                "donation__campaign__wallet",
            )
            .get(uuid=transaction_uuid)
        )

    except PaymentTransaction.DoesNotExist:
        return Response(
            {"success": False, "message": "Payment transaction not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ---------------------------------------
    # Validate Transaction Owner
    # ---------------------------------------

    if (
        payment_transaction.transaction_type == TransactionType.DONATION
        and payment_transaction.donation.donor_id != request.user.uuid
    ):
        return Response(
            {
                "success": False,
                "message": "You are not authorized to verify this payment.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # ---------------------------------------
    # Transaction Status Check
    # ---------------------------------------

    if payment_transaction.status != TransactionStatus.PENDING:
        return Response(
            {
                "success": False,
                "message": (
                    f"Payment is already "
                    f"{payment_transaction.status.value.lower()}."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------
    # Verify Donation Payment
    # ---------------------------------------

    if payment_transaction.transaction_type == TransactionType.DONATION:

        verify_donation_payment(
            payment_transaction=payment_transaction,
            reference_number=reference_number,
            verified_by=request.user,
        )

    # elif payment_transaction.transaction_type == TransactionType.CAMPAIGN_PROMOTION:

    #     verify_campaign_promotion_payment(
    #         payment_transaction,
    #         reference_number,
    #         request.user,
    #     )

    # elif payment_transaction.transaction_type == TransactionType.WITHDRAWAL:

    #     verify_withdrawal_payment(
    #         payment_transaction,
    #         reference_number,
    #         request.user,
    #     )

    else:
        return Response(
            {"success": False, "message": "Unsupported transaction type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------
    # Success Response
    # ---------------------------------------

    donation = payment_transaction.donation

    return Response(
        {
            "success": True,
            "message": "Payment verified successfully.",
            "data": {
                "transaction_uuid": str(payment_transaction.uuid),
                "donation_uuid": str(donation.uuid),
                "donation_number": donation.unique_donation_number,
                "receipt_number": (
                    donation.receipt.receipt_num
                    if hasattr(donation, "receipt")
                    else None
                ),
            },
        },
        status=status.HTTP_200_OK,
    )
