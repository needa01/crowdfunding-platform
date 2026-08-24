from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import FileResponse
from django.shortcuts import render
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.core.paginator import Paginator
from rest_framework.permissions import AllowAny

from campaigns.models import Campaign
from crowdfunding.enums import (
    CampaignStatus,
    Currency,
    DonationStatus,
    DonationType,
    PaymentGateway,
    TransactionStatus,
    TransactionType,
    VerificationStatus,
    VerificationType,
)
from crowdfunding.permissions import CanDonate, IsActiveAccount, IsDonor, IsCampaignCreator
from crowdfunding.utils import generate_receipt_number
from donations.models import Donation, DonationReceipt
from donations.serializers import CreateDonationSerializer
from donations.services import generate_donation_receipt
from payments.models import PaymentTransaction
from payments.services import create_razorpay_order, create_platform_razorpay_order
from verification.models import EntityVerificationRequest
from django.conf import settings


# Create your views here.
@api_view(["POST"])
@permission_classes([CanDonate])
@transaction.atomic
def create_campaign_donation(request):

    # ========================================================
    # REQUEST DATA
    # ========================================================

    campaign_slug = request.data.get("campaign_slug")

    amount = request.data.get("amount")

    message = request.data.get("message", "")

    is_anonymous = request.data.get("is_anonymous", False)

    # ========================================================
    # CAMPAIGN SLUG
    # ========================================================

    if not campaign_slug:

        return Response(
            {
                "success": False,
                "message": "Campaign slug is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not isinstance(campaign_slug, str) or not campaign_slug.strip():
        return Response(
            {
                "success": False,
                "message": "Invalid campaign slug.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # AMOUNT
    # ========================================================

    if amount is None or amount == "":

        return Response(
            {
                "success": False,
                "message": "Donation amount is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:

        amount = Decimal(str(amount))

    except (InvalidOperation, ValueError, TypeError):
        return Response(
            {
                "success": False,
                "message": "Invalid donation amount.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not amount.is_finite():
        return Response(
            {
                "success": False,
                "message": "Invalid donation amount.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount < Decimal("1"):

        return Response(
            {
                "success": False,
                "message": "Minimum donation amount is ₹1.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
        
    
    if amount.as_tuple().exponent < -2:
        return Response(
            {
                "success": False,
                "message": "Donation amount can have at most 2 decimal places.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if message is None:
        message = ""

    if not isinstance(message, str):
        return Response(
            {
                "success": False,
                "message": "Invalid donation message.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    message = message.strip()

    # ========================================================
    # 7. VALIDATE ANONYMOUS FLAG
    # ========================================================

    if isinstance(is_anonymous, str):
        if is_anonymous.lower() == "true":
            is_anonymous = True
        elif is_anonymous.lower() == "false":
            is_anonymous = False
        else:
            return Response(
                {
                    "success": False,
                    "message": "is_anonymous must be true or false.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    elif not isinstance(is_anonymous, bool):
        return Response(
            {
                "success": False,
                "message": "is_anonymous must be true or false.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )


    # ========================================================
    # CAMPAIGN
    # ========================================================

    campaign = Campaign.objects.filter(
        campaign_slug=campaign_slug,
        is_deleted=False,
    ).first()

    if not campaign:

        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ========================================================
    # EXPIRY
    # ========================================================

    if campaign.end_date <= timezone.localdate():

        return Response(
            {
                "success": False,
                "message": "This campaign has expired and is no longer accepting donations.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # OWN CAMPAIGN
    # ========================================================

    if campaign.created_by_id == request.user.uuid:

        return Response(
            {
                "success": False,
                "message": "You cannot donate to your own campaign.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # CAMPAIGN STATUS
    # ========================================================

    if campaign.campaign_status != CampaignStatus.ACTIVE:

        return Response(
            {
                "success": False,
                "message": "This campaign is not accepting donations.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # CAMPAIGN VERIFICATION
    # ========================================================

    verification = EntityVerificationRequest.objects.filter(
        campaign=campaign,
        verification_type=VerificationType.CAMPAIGN,
    ).first()

    if not verification:

        return Response(
            {
                "success": False,
                "message": "Campaign verification not found.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.status != VerificationStatus.APPROVED:

        return Response(
            {
                "success": False,
                "message": "This campaign is not accepting donations.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # WALLET
    # ========================================================

    if not hasattr(campaign, "wallet"):

        return Response(
            {
                "success": False,
                "message": "Campaign wallet is not configured.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ========================================================
    # CREATE DONATION
    # ========================================================

    try:
        donation = Donation.objects.create(
            donation_type=DonationType.CAMPAIGN,
            campaign=campaign,
            donor=request.user,
            amount=amount,
            currency=Currency.INR,
            message=message,
            is_anonymous=is_anonymous,
            status=DonationStatus.PENDING,
        )

    except IntegrityError:
        return Response(
            {
                "success": False,
                "message": "Unable to create donation.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as exc:
        print("DONATION CREATION ERROR:", exc)

        return Response(
            {
                "success": False,
                "message": "An unexpected error occurred while creating the donation.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ========================================================
    # CREATE RAZORPAY ORDER
    # ========================================================

    try:
        razorpay_order = create_razorpay_order(
            donation=donation
        )

        if not razorpay_order:
            raise ValueError("Empty Razorpay order response.")

        razorpay_order_id = razorpay_order.get("id")

        if not razorpay_order_id:
            raise ValueError("Razorpay order ID was not returned.")

    except Exception as exc:

        print("RAZORPAY ORDER ERROR:", exc)

        donation.status = DonationStatus.FAILED
        donation.save(
            update_fields=["status", "updated_at"]
        )

        return Response(
            {
                "success": False,
                "message": "Unable to create Razorpay order. Please try again.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )


    # ========================================================
    # PAYMENT TRANSACTION
    # ========================================================

    try:

        payment_transaction = PaymentTransaction.objects.create(
            transaction_type=TransactionType.DONATION,
            donation=donation,
            gateway=PaymentGateway.RAZORPAY,
            gateway_order_id=razorpay_order_id,
            amount=amount,
            currency=Currency.INR,
            status=TransactionStatus.PENDING,
            gateway_response={
                "razorpay_order": razorpay_order,
            },
        )

    except IntegrityError as exc:

        print("PAYMENT TRANSACTION INTEGRITY ERROR:", exc)

        donation.status = DonationStatus.FAILED
        donation.save(
            update_fields=["status", "updated_at"]
        )

        return Response(
            {
                "success": False,
                "message": "Unable to initialize payment transaction.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as exc:

        print("PAYMENT TRANSACTION ERROR:", exc)

        donation.status = DonationStatus.FAILED
        donation.save(
            update_fields=["status", "updated_at"]
        )

        return Response(
            {
                "success": False,
                "message": "Unable to initialize payment transaction.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    return Response(
        {
            "success": True,
            "message": "Donation initiated successfully.",
            "data": {
                "donation_uuid": str(donation.uuid),
                "transaction_uuid": str(payment_transaction.uuid),
                "donation_number": donation.unique_donation_number,
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "razorpay_order_id": razorpay_order_id,
                "amount": str(donation.amount),
                "amount_in_paise": int(
                    donation.amount * Decimal("100")
                ),
                "currency": donation.currency.value,
                "payment_status": payment_transaction.status.value,
            },
        },
        status=status.HTTP_201_CREATED,
    )



@api_view(["POST"])
@permission_classes([CanDonate])
@transaction.atomic
def create_platform_donation(request):

    # ========================================================
    # REQUEST DATA
    # ========================================================

    amount = request.data.get("amount")
    message = request.data.get("message", "")
    is_anonymous = request.data.get("is_anonymous", False)

    # ========================================================
    # AMOUNT
    # ========================================================

    if amount is None:
        return Response(
            {
                "success": False,
                "message": "Donation amount is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = Decimal(str(amount))
    except Exception:
        return Response(
            {
                "success": False,
                "message": "Invalid donation amount.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount < Decimal("1"):
        return Response(
            {
                "success": False,
                "message": "Minimum platform donation amount is ₹1.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ========================================================
    # CREATE PLATFORM DONATION
    # ========================================================

    donation = Donation.objects.create(
        donation_type=DonationType.PLATFORM,
        campaign=None,
        donor=request.user,
        amount=amount,
        currency=Currency.INR,
        message=message,
        is_anonymous=is_anonymous,
        status=DonationStatus.PENDING,
    )

    # ========================================================
    # CREATE RAZORPAY ORDER
    # ========================================================

    try:
        razorpay_order = create_platform_razorpay_order(
            donation=donation
        )

    except Exception as exc:
        donation.status = DonationStatus.FAILED
        donation.save(update_fields=["status", "updated_at"])

        return Response(
            {
                "success": False,
                "message": "Unable to create Razorpay order.",
            },
            status=status.HTTP_502_BAD_GATEWAY,
        )
    # ========================================================
    # PAYMENT TRANSACTION
    # ========================================================

    payment_transaction = PaymentTransaction.objects.create(
        transaction_type=TransactionType.DONATION,
        donation=donation,
        gateway=PaymentGateway.RAZORPAY,
        gateway_order_id=razorpay_order["id"],
        amount=amount,
        currency=Currency.INR,
        status=TransactionStatus.PENDING,
        gateway_response={
            "razorpay_order": razorpay_order,
        },
    )

    # ========================================================
    # RESPONSE
    # ========================================================

    return Response(
        {
            "success": True,
            "message": "Platform donation initiated successfully.",
            "data": {
                "donation_uuid": str(donation.uuid),
                "transaction_uuid": str(payment_transaction.uuid),
                "donation_number": donation.unique_donation_number,

                "razorpay_key_id": settings.RAZORPAY_KEY_ID,

                "razorpay_order_id": razorpay_order["id"],

                "amount": str(donation.amount),

                "amount_in_paise": int(
                    donation.amount * Decimal("100")
                ),

                "currency": donation.currency.value,

                "payment_status":
                    payment_transaction.status.value,
            },
        },
        status=status.HTTP_201_CREATED,
    )



@api_view(["GET"])
@permission_classes([IsActiveAccount, IsDonor])
def get_donation_details(request, donation_uuid):
    try:
        donation = Donation.objects.select_related(
            "campaign",
            "receipt",
            "transaction",
        ).get(
            uuid=donation_uuid,
            donor=request.user,
        )

        return Response(
            {
                "success": True,
                "data": {
                    "uuid": str(donation.uuid),
                    "donation_number": donation.unique_donation_number,
                    "campaign": {
                        "uuid": str(donation.campaign.uuid),
                        "campaign_name": donation.campaign.campaign_name,
                        "campaign_slug": donation.campaign.campaign_slug,
                        "cover_photo": (
                            request.build_absolute_uri(
                                donation.campaign.cover_photo.url
                            )
                            if donation.campaign.cover_photo
                            else None
                        ),
                    },
                    "amount": str(donation.amount),
                    "currency": donation.currency.value,
                    "status": donation.status.value,
                    "is_anonymous": donation.is_anonymous,
                    "message": donation.message,
                    "donated_at": donation.donated_at,
                    "created_at": donation.created_at,
                    "receipt": {
                        "available": hasattr(donation, "receipt"),
                        "receipt_number": (
                            donation.receipt.receipt_num
                            if hasattr(donation, "receipt")
                            else None
                        ),
                        "has_receipt_file": (
                            bool(donation.receipt.receipt_file)
                            if hasattr(donation, "receipt")
                            else False
                        ),
                    },
                    "payment": {
                        "gateway": (
                            donation.transaction.gateway.value
                            if hasattr(donation, "transaction")
                            else None
                        ),
                        "payment_method": (
                            donation.transaction.payment_method.value
                            if (
                                hasattr(donation, "transaction")
                                and donation.transaction.payment_method
                            )
                            else None
                        ),
                        "transaction_status": (
                            donation.transaction.status.value
                            if hasattr(donation, "transaction")
                            else None
                        ),
                        "gateway_payment_id": (
                            donation.transaction.gateway_payment_id
                            if hasattr(donation, "transaction")
                            else None
                        ),
                    },
                },
            }
        )

    except Donation.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Donation not found.",
            },
            status=404,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "message": str(e),
            },
            status=500,
        )


@api_view(["GET"])
@permission_classes([IsActiveAccount, IsDonor])
def get_my_donations(request):

    try:

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        donations = (
            Donation.objects.filter(donor=request.user, status=DonationStatus.SUCCESS)
            .select_related(
                "campaign",
                "receipt",
            )
            .order_by("-created_at")
        )

        paginator = Paginator(donations, page_size)
        page_obj = paginator.get_page(page)

        data = []

        for donation in page_obj:

            campaign = donation.campaign

            data.append(
                {
                    "uuid": str(donation.uuid),
                    "donation_number": donation.unique_donation_number,
                    "campaign": {
                        "uuid": str(campaign.uuid),
                        "campaign_name": campaign.campaign_name,
                        "campaign_slug": campaign.campaign_slug,
                        "cover_photo": (
                            request.build_absolute_uri(campaign.cover_photo.url)
                            if campaign.cover_photo
                            else None
                        ),
                        "goal_amount": str(campaign.goal_amount),
                        "raised_amount": str(campaign.raised_amount),
                    },
                    "amount": str(donation.amount),
                    "currency": donation.currency.value,
                    "status": donation.status.value,
                    "is_anonymous": donation.is_anonymous,
                    "message": donation.message,
                    "donated_at": donation.donated_at,
                    "created_at": donation.created_at,
                    "receipt_available": hasattr(
                        donation,
                        "receipt",
                    ),
                }
            )

        return Response(
            {
                "success": True,
                "count": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page_obj.number,
                "has_next": page_obj.has_next(),
                "has_previous": page_obj.has_previous(),
                "data": data,
            }
        )

    except Exception as e:

        return Response(
            {
                "success": False,
                "message": str(e),
            },
            status=500,
        )


@api_view(["POST"])
@permission_classes([CanDonate])
def generate_receipt(request, donation_uuid):

    # =========================================================
    # 1. GET DONATION
    # =========================================================

    try:
        donation = Donation.objects.select_related("campaign", "donor").get(
            uuid=donation_uuid,
            donor=request.user,
        )

    except Donation.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Donation not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # 2. RECEIPT CAN ONLY BE GENERATED FOR SUCCESSFUL DONATION
    # =========================================================
    
    if donation.donor != request.user:
        return Response(
            {
                "success": False,
                "message": "You are not authorized to generate the receipt for this donation.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if donation.status != DonationStatus.SUCCESS:
        return Response(
            {
                "success": False,
                "message": "Receipt can only be generated for successful donations.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 3. GET OR CREATE RECEIPT
    #
    # Receipt row is created ONLY here.
    # =========================================================

    try:
        with transaction.atomic():

            receipt, created = DonationReceipt.objects.get_or_create(donation=donation)

            # =================================================
            # 4. IF PDF ALREADY EXISTS
            # =================================================

            if receipt.receipt_file:
                return Response(
                    {
                        "success": True,
                        "message": "Receipt already generated.",
                        "data": {
                            "receipt_uuid": str(receipt.uuid),
                            "receipt_number": receipt.receipt_num,
                            "receipt_url": receipt.receipt_file.url,
                        },
                    },
                    status=status.HTTP_200_OK,
                )

            # =================================================
            # 5. GENERATE PDF
            # =================================================

            generate_donation_receipt(receipt)

            # Refresh from database in case the service updated
            # the receipt_file / other fields.
            receipt.refresh_from_db()

            # =================================================
            # 6. VERIFY PDF WAS CREATED
            # =================================================

            if not receipt.receipt_file:
                return Response(
                    {
                        "success": False,
                        "message": "Receipt record was created but PDF generation failed.",
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # =================================================
            # 7. RETURN RECEIPT
            # =================================================

            return Response(
                {
                    "success": True,
                    "message": (
                        "Receipt generated successfully."
                        if created
                        else "Receipt generated successfully."
                    ),
                    "data": {
                        "receipt_uuid": str(receipt.uuid),
                        "receipt_number": receipt.receipt_num,
                        "receipt_url": receipt.receipt_file.url,
                    },
                },
                status=status.HTTP_200_OK,
            )

    except Exception as exc:

        print("RECEIPT GENERATION ERROR:", exc)

        return Response(
            {
                "success": False,
                "message": "Unable to generate receipt.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([CanDonate])
def download_receipt(request, donation_uuid):

    try:
        receipt = DonationReceipt.objects.select_related("donation").get(
            donation__uuid=donation_uuid, donation__donor=request.user
        )

    except DonationReceipt.DoesNotExist:
        return Response(
            {"success": False, "message": "Receipt not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not receipt.receipt_file:
        return Response(
            {"success": False, "message": "Receipt has not been generated yet."},
            status=status.HTTP_404_NOT_FOUND,
        )

    return FileResponse(
        receipt.receipt_file.open("rb"),
        as_attachment=True,
        filename=f"{receipt.receipt_num}.pdf",
        content_type="application/pdf",
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def donation_success(request, donation_uuid):

    try:
        donation = Donation.objects.get(uuid=donation_uuid)

    except Donation.DoesNotExist:
        return Response(
            {"success": False, "message": "Donation not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    receipt = DonationReceipt.objects.filter(donation=donation).first()

    return Response(
        {
            "success": True,
            "data": {
                "donation_uuid": str(donation.uuid),
                "donation_number": donation.unique_donation_number,
                "receipt_number": (receipt.receipt_number if receipt else None),
                "amount": str(donation.amount),
                "status": donation.status.value,
            },
        },
        status=status.HTTP_200_OK,
    )
