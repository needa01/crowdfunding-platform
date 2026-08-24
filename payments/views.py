from django.db import transaction
from django.http import HttpResponse
import razorpay
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import (
    csrf_exempt,
)
from django.utils import timezone
from django.shortcuts import redirect
from django.conf import settings
import json
from crowdfunding.permissions import CanDonate
from crowdfunding.enums import (
    DonationStatus,
    TransactionStatus,
    TransactionType,
    PaymentMethod,
    PromotionStatus,
)
from payments.models import PaymentTransaction

from .services import (
    fetch_razorpay_order_payments,
    complete_donation_payment,
    fetch_razorpay_payment,
    verify_razorpay_signature,
)

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )
)


@api_view(["POST"])
@permission_classes([CanDonate])
def verify_payment(request):

    transaction_uuid = request.data.get("transaction_uuid")

    razorpay_payment_id = request.data.get("razorpay_payment_id")

    razorpay_order_id = request.data.get("razorpay_order_id")

    razorpay_signature = request.data.get("razorpay_signature")

    # ========================================================
    # VALIDATION
    # ========================================================

    if not transaction_uuid:

        return Response(
            {
                "success": False,
                "message": "Transaction UUID is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not razorpay_payment_id:

        return Response(
            {
                "success": False,
                "message": "Razorpay payment ID is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not razorpay_order_id:

        return Response(
            {
                "success": False,
                "message": "Razorpay order ID is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not razorpay_signature:

        return Response(
            {
                "success": False,
                "message": "Razorpay signature is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # FETCH TRANSACTION
    # ========================================================

    try:

        payment_transaction = (
            PaymentTransaction.objects.select_for_update()
            .select_related(
                "donation",
                "donation__campaign",
                "donation__campaign__wallet",
            )
            .get(uuid=transaction_uuid)
        )

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Payment transaction not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ========================================================
    # OWNER
    # ========================================================

    if payment_transaction.donation.donor_id != request.user.uuid:

        return Response(
            {
                "success": False,
                "message": "You are not authorized " "to verify this payment.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # ========================================================
    # TRANSACTION TYPE
    # ========================================================

    if payment_transaction.transaction_type != TransactionType.DONATION:

        return Response(
            {
                "success": False,
                "message": "Unsupported transaction type.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # IDEMPOTENCY
    # ========================================================

    if payment_transaction.status == TransactionStatus.SUCCESS:

        donation = payment_transaction.donation

        receipt = getattr(
            donation,
            "receipt",
            None,
        )

        return Response(
            {
                "success": True,
                "message": "Payment has already been verified.",
                "data": {
                    "transaction_uuid": str(payment_transaction.uuid),
                    "donation_uuid": str(donation.uuid),
                    "donation_number": donation.unique_donation_number,
                    "receipt_number": (receipt.receipt_num if receipt else None),
                },
            },
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # ONLY PENDING CAN BE VERIFIED
    # ========================================================

    if payment_transaction.status != TransactionStatus.PENDING:

        return Response(
            {
                "success": False,
                "message": "Payment is already "
                f"{payment_transaction.status.value.lower()}.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # NEVER TRUST CLIENT ORDER ID
    # ========================================================

    stored_order_id = payment_transaction.gateway_order_id

    if razorpay_order_id != stored_order_id:

        return Response(
            {
                "success": False,
                "message": "Razorpay order ID does not " "match the transaction.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # VERIFY SIGNATURE
    # ========================================================

    try:

        verify_razorpay_signature(
            order_id=stored_order_id,
            payment_id=razorpay_payment_id,
            signature=razorpay_signature,
        )

    except Exception:

        return Response(
            {
                "success": False,
                "message": "Invalid Razorpay payment signature.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # FETCH PAYMENT FROM RAZORPAY
    # ========================================================

    try:

        razorpay_payment = fetch_razorpay_payment(razorpay_payment_id)
        print("RAZORPAY PAYMENT:", razorpay_payment)
        print("RAZORPAY STATUS:", razorpay_payment.get("status"))

    except Exception as exc:

        print("RAZORPAY FETCH ERROR:", exc)

        return Response(
            {
                "success": False,
                "message": "Unable to fetch payment from Razorpay.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    # ========================================================
    # VERIFY PAYMENT ORDER
    # ========================================================

    if razorpay_payment.get("order_id") != stored_order_id:

        return Response(
            {
                "success": False,
                "message": "Payment does not belong " "to this Razorpay order.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # COMPLETE
    # ========================================================

    try:

        result = complete_donation_payment(
            payment_transaction=payment_transaction,
            razorpay_payment=razorpay_payment,
            verified_by=request.user,
        )

    except ValueError as exc:

        return Response(
            {
                "success": False,
                "message": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    return Response(
        {
            "success": True,
            "message": "Payment verified successfully.",
            "data": result,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([CanDonate])
def payment_status(request, transaction_uuid):

    # ========================================================
    # FETCH TRANSACTION
    # ========================================================

    try:

        payment_transaction = PaymentTransaction.objects.select_related(
            "donation",
            "donation__campaign",
            "donation__campaign__wallet",
        ).get(uuid=transaction_uuid)

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Payment transaction not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ========================================================
    # OWNER
    # ========================================================

    if payment_transaction.donation.donor_id != request.user.uuid:

        return Response(
            {
                "success": False,
                "message": "You are not authorized " "to view this payment.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # ========================================================
    # ALREADY SUCCESS
    # ========================================================

    if payment_transaction.status == TransactionStatus.SUCCESS:

        donation = payment_transaction.donation

        receipt = getattr(
            donation,
            "receipt",
            None,
        )

        return Response(
            {
                "success": True,
                "data": {
                    "status": "success",
                    "transaction_uuid": str(payment_transaction.uuid),
                    "donation_uuid": str(donation.uuid),
                    "donation_number": donation.unique_donation_number,
                    "receipt_number": (receipt.receipt_num if receipt else None),
                },
            },
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # ONLY PENDING
    # ========================================================

    if payment_transaction.status != TransactionStatus.PENDING:

        return Response(
            {
                "success": True,
                "data": {
                    "status": payment_transaction.status.value,
                    "transaction_uuid": str(payment_transaction.uuid),
                },
            },
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # ASK RAZORPAY FOR PAYMENTS
    # ========================================================

    try:

        payments_response = fetch_razorpay_order_payments(
            payment_transaction.gateway_order_id
        )

    except Exception as exc:

        return Response(
            {
                "success": False,
                "message": "Unable to fetch payment status " "from Razorpay.",
                "error": str(exc),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    payments = payments_response.get("items", [])

    # ========================================================
    # FIND CAPTURED PAYMENT
    # ========================================================

    captured_payment = None

    for payment in payments:

        if payment.get("order_id") != payment_transaction.gateway_order_id:
            continue

        payment_status = payment.get("status")

        print("RAZORPAY PAYMENT STATUS:", payment_status)

        if payment_status == "captured":

            captured_payment = payment

            break

        if payment_status == "failed":

            return Response(
                {
                    "success": True,
                    "data": {
                        "status": "failed",
                        "transaction_uuid": str(payment_transaction.uuid),
                    },
                },
                status=status.HTTP_200_OK,
            )

    # ========================================================
    # NO CAPTURED PAYMENT
    # ========================================================

    if not captured_payment:

        return Response(
            {
                "success": True,
                "data": {
                    "status": "pending",
                    "transaction_uuid": str(payment_transaction.uuid),
                    "donation_uuid": str(payment_transaction.donation.uuid),
                },
            },
            status=status.HTTP_200_OK,
        )

    # ========================================================
    # COMPLETE PAYMENT
    # ========================================================

    try:

        result = complete_donation_payment(
            payment_transaction=payment_transaction,
            razorpay_payment=captured_payment,
            verified_by=request.user,
        )

    except ValueError as exc:

        return Response(
            {
                "success": False,
                "message": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # SUCCESS
    # ========================================================

    return Response(
        {
            "success": True,
            "message": "Payment confirmed successfully.",
            "data": result,
        },
        status=status.HTTP_200_OK,
    )


import razorpay

from decimal import Decimal

from django.db import transaction

from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import PaymentTransaction
from .services import razorpay_client

# Import your actual models if they are in different apps.
from donations.models import Donation, DonationReceipt
from wallets.models import Wallet


@api_view(["POST"])
@permission_classes([AllowAny])
def donation_razorpay_callback(request):

    # =========================================================
    # 1. GET RAZORPAY CALLBACK DATA
    # =========================================================

    razorpay_payment_id = request.data.get("razorpay_payment_id")

    razorpay_order_id = request.data.get("razorpay_order_id")

    razorpay_signature = request.data.get("razorpay_signature")

    # =========================================================
    # 2. VALIDATE CALLBACK DATA
    # =========================================================

    missing_fields = []

    if not razorpay_payment_id:
        missing_fields.append("razorpay_payment_id")

    if not razorpay_order_id:
        missing_fields.append("razorpay_order_id")

    if not razorpay_signature:
        missing_fields.append("razorpay_signature")

    if missing_fields:

        return Response(
            {
                "success": False,
                "message": "Required payment fields are missing.",
                "errors": {"missing_fields": missing_fields},
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 3. FIND PAYMENT TRANSACTION
    # =========================================================

    try:
        payment_transaction = PaymentTransaction.objects.get(
            gateway_order_id=razorpay_order_id
        )

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Payment transaction not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # 4. CHECK IF ALREADY PROCESSED
    # =========================================================

    if payment_transaction.status == TransactionStatus.SUCCESS:

        return Response(
            {
                "success": True,
                "message": "Payment has already been verified.",
                "data": {
                    "payment_id": payment_transaction.gateway_payment_id,
                    "order_id": payment_transaction.gateway_order_id,
                    "transaction_uuid": str(payment_transaction.uuid),
                },
            },
            status=status.HTTP_200_OK,
        )

    # =========================================================
    # 5. VERIFY RAZORPAY SIGNATURE
    # =========================================================

    try:

        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

    except razorpay.errors.SignatureVerificationError:

        print("RAZORPAY SIGNATURE VERIFICATION FAILED")

        return Response(
            {
                "success": False,
                "message": "Invalid Razorpay payment signature.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 6. FETCH PAYMENT FROM RAZORPAY
    # =========================================================
    #
    # Signature verification proves that the callback
    # parameters are authentic.
    #
    # We additionally fetch the payment from Razorpay
    # and check its status before updating our database.
    # =========================================================

    try:

        razorpay_payment = razorpay_client.payment.fetch(razorpay_payment_id)

    except Exception as exc:

        print("RAZORPAY PAYMENT FETCH ERROR:", exc)

        return Response(
            {
                "success": False,
                "message": "Unable to fetch payment from Razorpay.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    print("RAZORPAY PAYMENT:", razorpay_payment)

    # =========================================================
    # 7. VERIFY PAYMENT BELONGS TO OUR ORDER
    # =========================================================

    fetched_order_id = razorpay_payment.get("order_id")

    if fetched_order_id != razorpay_order_id:

        return Response(
            {
                "success": False,
                "message": "Payment does not belong to this order.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 8. CHECK RAZORPAY PAYMENT STATUS
    # =========================================================

    razorpay_status = razorpay_payment.get("status")

    print("RAZORPAY PAYMENT STATUS:", razorpay_status)

    if razorpay_status != "captured":

        return Response(
            {
                "success": False,
                "message": "Payment has not been captured.",
                "data": {
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "razorpay_status": razorpay_status,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 9. PROCESS PAYMENT ATOMICALLY
    # =========================================================

    try:

        with transaction.atomic():

            # ---------------------------------------------
            # Lock transaction row
            # ---------------------------------------------

            payment_transaction = PaymentTransaction.objects.select_for_update().get(
                uuid=payment_transaction.uuid
            )

            # ---------------------------------------------
            # Prevent duplicate processing
            # ---------------------------------------------

            if payment_transaction.status == TransactionStatus.SUCCESS:

                return Response(
                    {
                        "success": True,
                        "message": "Payment already processed.",
                        "data": {
                            "payment_id": razorpay_payment_id,
                            "order_id": razorpay_order_id,
                            "transaction_uuid": str(payment_transaction.uuid),
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            # =========================================================
            # SAVE RAZORPAY PAYMENT DETAILS
            # =========================================================

            payment_transaction.gateway_payment_id = razorpay_payment_id
            payment_transaction.gateway_signature = razorpay_signature

            # Payment method: upi / card / netbanking / wallet etc.
            razorpay_method = razorpay_payment.get("method")

            payment_method_map = {
                "card": PaymentMethod.CARD,
                "upi": PaymentMethod.UPI,
                "netbanking": PaymentMethod.NETBANKING,
                "wallet": PaymentMethod.WALLET,
                "emi": PaymentMethod.EMI,
                "bank_transfer": PaymentMethod.BANK_TRANSFER,
            }

            payment_transaction.payment_method = payment_method_map.get(
                razorpay_method, PaymentMethod.OTHER
            )

            # Save complete Razorpay PAYMENT response
            payment_transaction.gateway_response = dict(razorpay_payment)

            # Razorpay returns monetary values in paise
            razorpay_fee = razorpay_payment.get("fee")
            razorpay_tax = razorpay_payment.get("tax")
            
            
            # =================================================
            # GET DONATION
            # =================================================


            donation = payment_transaction.donation


            if not donation:
                raise ValueError("Payment transaction is not linked to a donation.")
            
            
            if razorpay_fee is not None:
                donation.fee = Decimal(razorpay_fee) / Decimal("100")

            if razorpay_tax is not None:
                donation.tax = Decimal(razorpay_tax) / Decimal("100")



            payment_transaction.status = TransactionStatus.SUCCESS
            payment_transaction.processed_at = timezone.now()

            payment_transaction.save(
                update_fields=[
                    "gateway_payment_id",
                    "gateway_signature",
                    "payment_method",
                    "gateway_response",
                    "status",
                    "processed_at",
                ]
            )


            # =================================================
            # MARK DONATION SUCCESS
            # =================================================

            donation.status = DonationStatus.SUCCESS

            donation.save(
                update_fields=[
                    "status",
                ]
            )

            # =================================================
            # GET CAMPAIGN
            # =================================================

            campaign = donation.campaign

            # =================================================
            # UPDATE CAMPAIGN RAISED AMOUNT
            # =================================================

            campaign.raised_amount = campaign.raised_amount + donation.amount

            campaign.save(
                update_fields=[
                    "raised_amount",
                ]
            )

            # =================================================
            # UPDATE CAMPAIGN WALLET
            # =================================================

            wallet = Wallet.objects.select_for_update().get(campaign=campaign)

            wallet.balance = wallet.balance + donation.amount

            wallet.save(
                update_fields=[
                    "balance",
                ]
            )

            # =================================================
            # RECEIPT
            # =================================================
            #
            # If your existing project generates the receipt
            # here, call that service/function.
            #
            # Example:
            #
            # create_donation_receipt(donation)
            #
            # Do NOT create duplicate receipts if one already
            # exists.
            # =================================================

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Payment transaction no longer exists.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Wallet.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Campaign wallet not found.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as exc:

        print("PAYMENT PROCESSING ERROR:", exc)

        return Response(
            {
                "success": False,
                "message": "Payment was verified but could not be processed.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # =========================================================
    # 10. RETURN REST RESPONSE
    # =========================================================

    # return Response(
    #     {
    #         "success": True,
    #         "message": "Payment verified and donation processed successfully.",
    #         "data": {
    #             "payment_id": razorpay_payment_id,
    #             "order_id": razorpay_order_id,
    #             "transaction_uuid": str(payment_transaction.uuid),
    #             "donation_uuid": str(donation.uuid),
    #             "donation_number": donation.unique_donation_number,
    #             "payment_status": "SUCCESS",
    #         },
    #     },
    #     status=status.HTTP_200_OK,
    # )

    return redirect(f"/frontend/payment/success?donation_uuid={donation.uuid}")



@api_view(["POST"])
@permission_classes([AllowAny])
def campaign_promotion_razorpay_callback(request):

    print("========================================")
    print("CAMPAIGN PROMOTION RAZORPAY CALLBACK")
    print("========================================")
    print("REQUEST DATA:")
    print(request.data)

    # =========================================================
    # 1. GET RAZORPAY DATA
    # =========================================================

    razorpay_payment_id = request.data.get("razorpay_payment_id")
    razorpay_order_id = request.data.get("razorpay_order_id")
    razorpay_signature = request.data.get("razorpay_signature")

    # =========================================================
    # 2. VALIDATE
    # =========================================================

    missing_fields = []

    if not razorpay_payment_id:
        missing_fields.append("razorpay_payment_id")

    if not razorpay_order_id:
        missing_fields.append("razorpay_order_id")

    if not razorpay_signature:
        missing_fields.append("razorpay_signature")

    if missing_fields:
        return Response(
            {
                "success": False,
                "message": "Required payment fields are missing.",
                "errors": {
                    "missing_fields": missing_fields
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 3. FIND PAYMENT TRANSACTION
    # =========================================================

    try:
        payment_transaction = PaymentTransaction.objects.get(
            gateway_order_id=razorpay_order_id,
            transaction_type=TransactionType.CAMPAIGN_PROMOTION,
        )

    except PaymentTransaction.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": (
                    "Campaign promotion payment transaction not found."
                ),
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # 4. CHECK ALREADY PROCESSED
    # =========================================================

    if payment_transaction.status == TransactionStatus.SUCCESS:

        promotions = (
            payment_transaction
            .campaign_promotion_services
            .all()
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Promotion payment has already been verified."
                ),
                "data": {
                    "payment_id": (
                        payment_transaction.gateway_payment_id
                    ),
                    "order_id": (
                        payment_transaction.gateway_order_id
                    ),
                    "transaction_uuid": str(
                        payment_transaction.uuid
                    ),
                    "promotion_uuids": [
                        str(promotion.uuid)
                        for promotion in promotions
                    ],
                },
            },
            status=status.HTTP_200_OK,
        )

    # =========================================================
    # 5. VERIFY SIGNATURE
    # =========================================================

    try:
        razorpay_client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

    except razorpay.errors.SignatureVerificationError:

        print(
            "RAZORPAY SIGNATURE VERIFICATION FAILED"
        )

        return Response(
            {
                "success": False,
                "message": (
                    "Invalid Razorpay payment signature."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 6. FETCH PAYMENT
    # =========================================================

    try:
        razorpay_payment = (
            razorpay_client.payment.fetch(
                razorpay_payment_id
            )
        )

    except Exception as exc:

        print(
            "RAZORPAY PAYMENT FETCH ERROR:",
            exc,
        )

        return Response(
            {
                "success": False,
                "message": (
                    "Unable to fetch payment from Razorpay."
                ),
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    print(
        "RAZORPAY PAYMENT:",
        razorpay_payment,
    )

    # =========================================================
    # 7. VERIFY ORDER ID
    # =========================================================

    if (
        razorpay_payment.get("order_id")
        != razorpay_order_id
    ):
        return Response(
            {
                "success": False,
                "message": (
                    "Payment does not belong to this order."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 8. CHECK CAPTURED
    # =========================================================

    razorpay_status = razorpay_payment.get("status")

    if razorpay_status != "captured":

        return Response(
            {
                "success": False,
                "message": (
                    "Payment has not been captured."
                ),
                "data": {
                    "payment_id": razorpay_payment_id,
                    "order_id": razorpay_order_id,
                    "razorpay_status": razorpay_status,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 9. PROCESS TRANSACTION
    # =========================================================

    try:

        with transaction.atomic():

            # -------------------------------------------------
            # LOCK PAYMENT TRANSACTION
            # -------------------------------------------------

            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .get(
                    uuid=payment_transaction.uuid
                )
            )

            # -------------------------------------------------
            # DUPLICATE CHECK
            # -------------------------------------------------

            if (
                payment_transaction.status
                == TransactionStatus.SUCCESS
            ):

                promotions = (
                    payment_transaction
                    .campaign_promotion_services
                    .all()
                )

                return Response(
                    {
                        "success": True,
                        "message": (
                            "Promotion payment "
                            "already processed."
                        ),
                        "data": {
                            "promotion_uuids": [
                                str(promotion.uuid)
                                for promotion in promotions
                            ]
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            # =================================================
            # GET ALL PROMOTIONS
            # =================================================

            promotions = (
                payment_transaction
                .campaign_promotion_services
                .all()
            )

            # QuerySet must use exists()
            if not promotions.exists():

                raise ValueError(
                    "Payment transaction is not linked "
                    "to any campaign promotion."
                )

            # =================================================
            # SAVE RAZORPAY DETAILS
            # =================================================

            payment_transaction.gateway_payment_id = (
                razorpay_payment_id
            )

            payment_transaction.gateway_signature = (
                razorpay_signature
            )

            # =================================================
            # PAYMENT METHOD
            # =================================================

            razorpay_method = (
                razorpay_payment.get("method")
            )

            payment_method_map = {
                "card": PaymentMethod.CARD,
                "upi": PaymentMethod.UPI,
                "netbanking": PaymentMethod.NETBANKING,
                "wallet": PaymentMethod.WALLET,
                "emi": PaymentMethod.EMI,
                "bank_transfer": PaymentMethod.BANK_TRANSFER,
            }

            payment_transaction.payment_method = (
                payment_method_map.get(
                    razorpay_method,
                    PaymentMethod.OTHER,
                )
            )

            # =================================================
            # SAVE COMPLETE RAZORPAY RESPONSE
            # =================================================

            payment_transaction.gateway_response = (
                dict(razorpay_payment)
            )

            # =================================================
            # RAZORPAY FEE / TAX
            # =================================================

            razorpay_fee = (
                razorpay_payment.get("fee")
            )

            razorpay_tax = (
                razorpay_payment.get("tax")
            )

            # =================================================
            # MARK TRANSACTION SUCCESS
            # =================================================

            payment_transaction.status = (
                TransactionStatus.SUCCESS
            )

            payment_transaction.processed_at = (
                timezone.now()
            )

            payment_transaction.save(
                update_fields=[
                    "gateway_payment_id",
                    "gateway_signature",
                    "payment_method",
                    "gateway_response",
                    "status",
                    "processed_at",
                ]
            )

            # =================================================
            # MARK ALL PROMOTIONS ACTIVE
            # =================================================

            promotions.update(
                promotion_status=PromotionStatus.ACTIVE
            )

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": (
                    "Payment transaction "
                    "no longer exists."
                ),
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as exc:

        print(
            "CAMPAIGN PROMOTION PAYMENT "
            "PROCESSING ERROR:",
            exc,
        )

        return Response(
            {
                "success": False,
                "message": (
                    "Payment was verified but "
                    "promotion could not be processed."
                ),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # =========================================================
    # 10. SUCCESS RESPONSE
    # =========================================================

    return Response(
        {
            "success": True,
            "message": (
                "Campaign promotion payment "
                "processed successfully."
            ),
            "data": {
                "payment_id": razorpay_payment_id,
                "order_id": razorpay_order_id,
                "transaction_uuid": str(
                    payment_transaction.uuid
                ),
                "promotion_uuids": [
                    str(promotion.uuid)
                    for promotion in promotions
                ],
                "payment_status": "SUCCESS",
            },
        },
        status=status.HTTP_200_OK,
    )





