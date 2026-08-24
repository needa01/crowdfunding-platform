from django.db import transaction
from django.http import HttpResponse
import razorpay
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.views.decorators.csrf import (
    csrf_exempt,
)
from django.http import HttpResponseRedirect
from django.utils import timezone
from django.shortcuts import redirect
from django.conf import settings
import json
from crowdfunding.permissions import CanDonate
from crowdfunding.enums import (
    DonationStatus,
    TransactionStatus,
    TransactionType,
    DonationType,
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


razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )
)






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

            
            
            # =================================================
            # GET DONATION
            # =================================================


            donation = payment_transaction.donation


            if not donation:
                raise ValueError("Payment transaction is not linked to a donation.")
            



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
            
            donation.donated_at = timezone.now()

            donation.save(
                update_fields=[
                    "status",
                    "updated_at",
                    "donated_at",
                ]
            )

            # =================================================
            # GET CAMPAIGN
            # =================================================
            if donation.donation_type != DonationType.CAMPAIGN:
                raise ValueError(
                    "This payment is not a campaign donation."
                )

            if donation.campaign_id is None:
                raise ValueError(
                    "Campaign donation has no campaign."
                )
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

    return redirect(f"/frontend/donation/success?donation_uuid={donation.uuid}")



@api_view(["POST"])
@permission_classes([AllowAny])
def platform_donation_razorpay_callback(request):

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
        payment_transaction = PaymentTransaction.objects.select_related(
            "donation"
        ).get(
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
    # 4. VERIFY THIS IS A PLATFORM DONATION
    # =========================================================

    donation = payment_transaction.donation

    if not donation:
        return Response(
            {
                "success": False,
                "message": "Payment transaction is not linked to a donation.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if donation.donation_type != DonationType.PLATFORM:
        return Response(
            {
                "success": False,
                "message": "This payment is not a platform donation.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Platform donation should NEVER have a campaign
    if donation.campaign_id is not None:
        return Response(
            {
                "success": False,
                "message": "Invalid platform donation configuration.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 5. CHECK IF ALREADY PROCESSED
    # =========================================================

    if payment_transaction.status == TransactionStatus.SUCCESS:

        return Response(
            {
                "success": True,
                "message": "Platform donation has already been verified.",
                "data": {
                    "payment_id": payment_transaction.gateway_payment_id,
                    "order_id": payment_transaction.gateway_order_id,
                    "transaction_uuid": str(
                        payment_transaction.uuid
                    ),
                    "donation_uuid": str(
                        donation.uuid
                    ),
                    "donation_number":
                        donation.unique_donation_number,
                    "payment_status": "SUCCESS",
                },
            },
            status=status.HTTP_200_OK,
        )

    # =========================================================
    # 6. VERIFY RAZORPAY SIGNATURE
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
            "PLATFORM DONATION RAZORPAY SIGNATURE "
            "VERIFICATION FAILED"
        )

        return Response(
            {
                "success": False,
                "message": "Invalid Razorpay payment signature.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 7. FETCH PAYMENT FROM RAZORPAY
    # =========================================================

    try:

        razorpay_payment = razorpay_client.payment.fetch(
            razorpay_payment_id
        )

    except Exception as exc:

        print(
            "RAZORPAY PLATFORM PAYMENT FETCH ERROR:",
            exc
        )

        return Response(
            {
                "success": False,
                "message": "Unable to fetch payment from Razorpay.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )

    print(
        "RAZORPAY PLATFORM PAYMENT:",
        razorpay_payment
    )

    # =========================================================
    # 8. VERIFY PAYMENT BELONGS TO OUR ORDER
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
    # 9. CHECK RAZORPAY PAYMENT STATUS
    # =========================================================

    razorpay_status = razorpay_payment.get("status")

    print(
        "RAZORPAY PLATFORM PAYMENT STATUS:",
        razorpay_status
    )

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
    # 10. PROCESS PAYMENT ATOMICALLY
    # =========================================================

    try:

        with transaction.atomic():

            # ---------------------------------------------
            # Lock transaction
            # ---------------------------------------------

            payment_transaction = (
                PaymentTransaction.objects
                .select_for_update()
                .get(
                    uuid=payment_transaction.uuid
                )
            )

            # ---------------------------------------------
            # Prevent duplicate processing
            # ---------------------------------------------

            if (
                payment_transaction.status
                == TransactionStatus.SUCCESS
            ):

                donation = payment_transaction.donation

                return Response(
                    {
                        "success": True,
                        "message": "Platform donation already processed.",
                        "data": {
                            "payment_id":
                                payment_transaction.gateway_payment_id,
                            "order_id":
                                payment_transaction.gateway_order_id,
                            "transaction_uuid":
                                str(payment_transaction.uuid),
                            "donation_uuid":
                                str(donation.uuid),
                            "donation_number":
                                donation.unique_donation_number,
                            "payment_status":
                                "SUCCESS",
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            # ---------------------------------------------
            # Get donation again
            # ---------------------------------------------

            donation = payment_transaction.donation

            if not donation:

                raise ValueError(
                    "Payment transaction is not linked to a donation."
                )

            # ---------------------------------------------
            # Verify donation type again
            # ---------------------------------------------

            if (
                donation.donation_type
                != DonationType.PLATFORM
            ):

                raise ValueError(
                    "Payment is not a platform donation."
                )

            if donation.campaign_id is not None:

                raise ValueError(
                    "Platform donation cannot be linked "
                    "to a campaign."
                )

            # =================================================
            # SAVE RAZORPAY PAYMENT DETAILS
            # =================================================

            payment_transaction.gateway_payment_id = (
                razorpay_payment_id
            )

            payment_transaction.gateway_signature = (
                razorpay_signature
            )

            # ---------------------------------------------
            # Payment method
            # ---------------------------------------------

            razorpay_method = razorpay_payment.get(
                "method"
            )

            payment_method_map = {

                "card": PaymentMethod.CARD,

                "upi": PaymentMethod.UPI,

                "netbanking": PaymentMethod.NETBANKING,

                "wallet": PaymentMethod.WALLET,

                "emi": PaymentMethod.EMI,

                "bank_transfer":
                    PaymentMethod.BANK_TRANSFER,
            }

            payment_transaction.payment_method = (
                payment_method_map.get(
                    razorpay_method,
                    PaymentMethod.OTHER
                )
            )

            # ---------------------------------------------
            # Save complete Razorpay response
            # ---------------------------------------------

            payment_transaction.gateway_response = dict(
                razorpay_payment
            )


            # =================================================
            # MARK PAYMENT SUCCESS
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
            # MARK PLATFORM DONATION SUCCESS
            # =================================================

            donation.status = DonationStatus.SUCCESS
            donation.donated_at = timezone.now()

            donation.save(
                update_fields=[
                    "status",
                    "donated_at",
                    "updated_at",
                ]
            )

            # =================================================
            # PLATFORM LEDGER
            # =================================================

            # IMPORTANT:
            #
            # Do NOT update:
            #
            # donation.campaign
            # campaign.raised_amount
            # campaign.wallet
            #
            # because this is a PLATFORM donation.
            #
            # If you have a PlatformWallet / PlatformLedger,
            # create/update it here.

            # Example:
            #
            # platform_wallet = (
            #     PlatformWallet.objects.select_for_update()
            #     .get(...)
            # )
            #
            # platform_wallet.balance += donation.amount
            # platform_wallet.save(...)

            # =================================================
            # PLATFORM RECEIPT
            # =================================================

            # If you have a receipt service:
            #
            # create_donation_receipt(donation)

    except PaymentTransaction.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Payment transaction no longer exists.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as exc:

        print(
            "PLATFORM DONATION PAYMENT PROCESSING ERROR:",
            exc
        )

        return Response(
            {
                "success": False,
                "message": (
                    "Payment was verified but could not "
                    "be processed."
                ),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # =========================================================
    # 11. SUCCESS RESPONSE
    # =========================================================
    return HttpResponseRedirect(
        f"/frontend/donation/success?donation_uuid={donation.uuid}"
    )



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

    return redirect(f"/frontend/payment/success")





