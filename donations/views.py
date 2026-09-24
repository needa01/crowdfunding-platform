from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.timezone import localtime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.core.paginator import Paginator, EmptyPage
from rest_framework.permissions import AllowAny, IsAuthenticated

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
from crowdfunding.permissions import (
    CanDonate,
    IsActiveAccount,
    IsCSR,
    IsDonor,
    IsCampaignCreator,
)
from crowdfunding.utils import generate_receipt_number
from donations.models import Donation, DonationReceipt
from donations.serializers import CreateDonationSerializer
from donations.services import generate_csr_donation_receipt, generate_donation_receipt
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
        razorpay_order = create_razorpay_order(donation=donation)

        if not razorpay_order:
            raise ValueError("Empty Razorpay order response.")

        razorpay_order_id = razorpay_order.get("id")

        if not razorpay_order_id:
            raise ValueError("Razorpay order ID was not returned.")

    except Exception as exc:

        print("RAZORPAY ORDER ERROR:", exc)

        donation.status = DonationStatus.FAILED
        donation.save(update_fields=["status", "updated_at"])

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
        donation.save(update_fields=["status", "updated_at"])

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
        donation.save(update_fields=["status", "updated_at"])

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
                "amount_in_paise": int(donation.amount * Decimal("100")),
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
        razorpay_order = create_platform_razorpay_order(donation=donation)

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
                "amount_in_paise": int(donation.amount * Decimal("100")),
                "currency": donation.currency.value,
                "payment_status": payment_transaction.status.value,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsActiveAccount])
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

        data = {
            "uuid": str(donation.uuid),
            "donation_number": donation.unique_donation_number,
            "amount": str(donation.amount),
            "currency": donation.currency.value,
            "status": donation.status.value,
            "is_anonymous": donation.is_anonymous,
            "message": donation.message or "",
            "donated_at": (
                localtime(donation.donated_at).strftime("%d %b %Y, %I:%M %p")
                if donation.donated_at
                else None
            ),
            "created_at": (
                localtime(donation.created_at).strftime("%d %b %Y, %I:%M %p")
                if donation.created_at
                else None
            ),
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
        }

        # ==========================================================
        # CAMPAIGN DONATION
        # ==========================================================

        if donation.donation_type == DonationType.CAMPAIGN:

            data["campaign"] = {
                "uuid": str(donation.campaign.uuid),
                "campaign_name": donation.campaign.campaign_name,
                "campaign_slug": donation.campaign.campaign_slug,
                "cover_photo": (
                    request.build_absolute_uri(donation.campaign.cover_photo.url)
                    if donation.campaign.cover_photo
                    else None
                ),
            }

        # ==========================================================
        # PLATFORM DONATION
        # ==========================================================

        elif donation.donation_type == DonationType.PLATFORM:

            data["platform"] = {
                "name": "Our Platform",
                "cover_photo": request.build_absolute_uri("/static/receipts/logo.webp"),
            }

        return Response(
            {
                "success": True,
                "data": data,
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
@permission_classes([IsActiveAccount])
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

            # -----------------------------------------------------
            # Common donation data
            # -----------------------------------------------------

            donation_data = {
                "uuid": str(donation.uuid),
                "donation_number": (donation.unique_donation_number),
                "donation_type": (donation.donation_type.value),
                "amount": str(donation.amount),
                "currency": (donation.currency.value),
                "status": (donation.status.value),
                "is_anonymous": (donation.is_anonymous),
                "message": (donation.message),
                "donated_at": (donation.donated_at),
                "created_at": (donation.created_at),
                "receipt_available": (
                    hasattr(
                        donation,
                        "receipt",
                    )
                ),
            }

            # =====================================================
            # 5. CAMPAIGN DONATION
            # =====================================================

            if donation.donation_type == DonationType.CAMPAIGN:

                campaign = donation.campaign

                # A campaign donation must have a campaign
                if not campaign:
                    return Response(
                        {
                            "success": False,
                            "message": (
                                "Campaign donation is not "
                                "associated with a campaign."
                            ),
                            "donation_uuid": str(donation.uuid),
                        },
                        status=500,
                    )

                donation_data["campaign"] = {
                    "campaign_name": (campaign.campaign_name),
                    "cover_photo": (
                        request.build_absolute_uri(campaign.cover_photo.url)
                        if campaign.cover_photo
                        else None
                    ),
                }

            # =====================================================
            # 6. PLATFORM DONATION
            # =====================================================

            elif donation.donation_type == DonationType.PLATFORM:

                donation_data["platform"] = {
                    "name": "Platform Donation",
                    "cover_photo": (
                        request.build_absolute_uri("/static/receipts/logo.webp")
                    ),
                }

            # =====================================================
            # 7. ADD DONATION TO RESPONSE
            # =====================================================

            data.append(donation_data)

        # =========================================================
        # 8. SUCCESS RESPONSE
        # =========================================================

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
@permission_classes([IsAuthenticated])
def generate_receipt(request, donation_uuid):

    # =========================================================
    # 1. GET DONATION
    # =========================================================

    try:
        donation = (
            Donation.objects
            .select_related("campaign", "donor")
            .get(
                uuid=donation_uuid,
                donor=request.user,
            )
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
    # 2. VERIFY DONATION OWNER
    # =========================================================

    if donation.donor != request.user:
        return Response(
            {
                "success": False,
                "message": (
                    "You are not authorized to generate the receipt "
                    "for this donation."
                ),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # 3. RECEIPT ONLY FOR SUCCESSFUL DONATION
    # =========================================================

    if donation.status != DonationStatus.SUCCESS:
        return Response(
            {
                "success": False,
                "message": (
                    "Receipt can only be generated for successful donations."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 4. DETERMINE USER TYPE
    # =========================================================

    user_type = getattr(request.user, "user_type", None)

    # Handles EnumField / normal string field
    user_type_value = getattr(user_type, "value", user_type)

    is_csr = str(user_type_value).upper() == "CSR"

    # =========================================================
    # 5. GET OR CREATE RECEIPT
    # =========================================================

    try:

        with transaction.atomic():

            receipt, created = DonationReceipt.objects.get_or_create(
                donation=donation
            )

            # =====================================================
            # 6. IF RECEIPT PDF ALREADY EXISTS
            # =====================================================

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

            # =====================================================
            # 7. GENERATE RECEIPT
            # =====================================================

            if is_csr:

                # ---------------------------------------------
                # CSR RECEIPT DESIGN
                # ---------------------------------------------
                generate_csr_donation_receipt(receipt)

            else:

                # ---------------------------------------------
                # NORMAL DONOR RECEIPT DESIGN
                # ---------------------------------------------
                generate_donation_receipt(receipt)

            # =====================================================
            # 8. REFRESH RECEIPT
            # =====================================================

            receipt.refresh_from_db()

            # =====================================================
            # 9. VERIFY PDF WAS CREATED
            # =====================================================

            if not receipt.receipt_file:

                return Response(
                    {
                        "success": False,
                        "message": (
                            "Receipt record was created but "
                            "PDF generation failed."
                        ),
                    },
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

            # =====================================================
            # 10. RETURN RECEIPT
            # =====================================================

            return Response(
                {
                    "success": True,
                    "message": "Receipt generated successfully.",
                    "data": {
                        "receipt_uuid": str(receipt.uuid),
                        "receipt_number": receipt.receipt_num,
                        "receipt_url": receipt.receipt_file.url,
                        "receipt_type": "CSR" if is_csr else "DONOR",
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







@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCSR])
def my_contributions(request):

    try:

        user = request.user

        # =========================================================
        # 1. CHECK CSR USER
        # =========================================================

        user_type = getattr(
            user,
            "user_type",
            None
        )

        user_type_value = getattr(
            user_type,
            "value",
            user_type
        )

        if str(user_type_value).lower() != "csr":

            return Response(
                {
                    "success": False,
                    "message": "Only CSR users can access My Contributions."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # =========================================================
        # 2. QUERY PARAMETERS
        # =========================================================

        search = request.query_params.get(
            "search",
            ""
        ).strip()

        campaign_status_filter = request.query_params.get(
            "campaign_status",
            ""
        ).strip()

        payment_status_filter = request.query_params.get(
            "payment_status",
            ""
        ).strip()

        date_filter = request.query_params.get(
            "date",
            ""
        ).strip()

        try:

            page = int(
                request.query_params.get(
                    "page",
                    1
                )
            )

            page_size = int(
                request.query_params.get(
                    "page_size",
                    10
                )
            )

        except ValueError:

            return Response(
                {
                    "success": False,
                    "message": "page and page_size must be valid integers."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if page < 1:

            return Response(
                {
                    "success": False,
                    "message": "page must be greater than 0."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if page_size < 1 or page_size > 50:

            return Response(
                {
                    "success": False,
                    "message": "page_size must be between 1 and 50."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # =========================================================
        # 3. GET CSR DONATIONS
        # =========================================================

        donations = (
            user.donations
            .select_related(
                "campaign",
                "receipt",
                "transaction"
            )
            .order_by("-created_at")
        )

        # =========================================================
        # 4. SEARCH
        # =========================================================

        if search:

            donations = donations.filter(
                Q(
                    campaign__campaign_name__icontains=search
                )
                |
                Q(
                    campaign__campaign_slug__icontains=search
                )
                |
                Q(
                    unique_donation_number__icontains=search
                )
                |
                Q(
                    transaction__gateway_payment_id__icontains=search
                )
                |
                Q(
                    message__icontains=search
                )
            ).distinct()

        # =========================================================
        # 5. CAMPAIGN STATUS FILTER
        #
        # Only CAMPAIGN donations have campaign status.
        # =========================================================

        if campaign_status_filter:

            donations = donations.filter(
                donation_type="CAMPAIGN",
                campaign__campaign_status__iexact=campaign_status_filter
            )

        # =========================================================
        # 6. PAYMENT STATUS FILTER
        # =========================================================

        if payment_status_filter:

            payment_status_lower = (
                payment_status_filter.lower()
            )

            if payment_status_lower == "paid":

                donations = donations.filter(
                    transaction__status__in=[
                        "SUCCESS"
                    ]
                )

            elif payment_status_lower == "pending":

                donations = donations.filter(
                    transaction__status__in=[
                        "PENDING"
                    ]
                )

            elif payment_status_lower == "failed":

                donations = donations.filter(
                    transaction__status__in=[
                        "FAILED",
                    ]
                )

            elif payment_status_lower == "refunded":

                donations = donations.filter(
                    Q(
                        transaction__status__in=[
                            "REFUNDED",
                        ]
                    )
                    |
                    Q(
                        transaction__refund_id__isnull=False
                    )
                )

            else:

                return Response(
                    {
                        "success": False,
                        "message": (
                            "Invalid payment_status. "
                            "Allowed values are Paid, Pending, "
                            "Failed and Refunded."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        # =========================================================
        # 7. DATE FILTER
        # =========================================================

        if date_filter:

            donations = donations.filter(
                donated_at__date=date_filter
            )

        # =========================================================
        # 8. SUMMARY
        #
        # All CSR donations are considered.
        #
        # CAMPAIGN:
        #   - total_contributions
        #   - campaigns_supported
        #   - active_contributions
        #   - completed_contributions
        #
        # PLATFORM:
        #   - total_contributions only
        # =========================================================

        all_donations = (
            user.donations
            .select_related(
                "campaign",
                "transaction"
            )
        )

        successful_statuses = {
            "SUCCESS",
            "SUCCESSFUL",
            "COMPLETED",
            "CAPTURED",
            "PAID"
        }

        total_contributions = Decimal("0.00")

        active_contributions = Decimal("0.00")

        completed_contributions = Decimal("0.00")

        supported_campaign_ids = set()

        for donation in all_donations:

            # =====================================================
            # DONATION TYPE
            # =====================================================

            donation_type_value = getattr(
                donation.donation_type,
                "value",
                donation.donation_type
            )

            donation_type_value = str(
                donation_type_value
            ).upper()

            # =====================================================
            # DONATION STATUS
            # =====================================================

            donation_status = getattr(
                donation.status,
                "value",
                donation.status
            )

            donation_status = str(
                donation_status
            ).upper()

            # =====================================================
            # TRANSACTION
            # =====================================================

            transaction = getattr(
                donation,
                "transaction",
                None
            )

            transaction_status = ""

            if transaction:

                transaction_status = getattr(
                    transaction.status,
                    "value",
                    transaction.status
                )

                transaction_status = str(
                    transaction_status
                ).upper()

            # =====================================================
            # CHECK PAYMENT SUCCESS
            # =====================================================

            is_paid = (
                transaction_status in successful_statuses
                or donation_status in successful_statuses
            )

            # =====================================================
            # REFUND CHECK
            # =====================================================

            if transaction:

                if (
                    transaction.refund_id
                    or transaction.refunded_at
                    or transaction_status in {
                        "REFUNDED",
                        "PARTIALLY_REFUNDED"
                    }
                ):

                    is_paid = False

            if not is_paid:
                continue

            # =====================================================
            # AMOUNT
            # =====================================================

            amount = (
                donation.amount
                or Decimal("0.00")
            )

            # =====================================================
            # ALL SUCCESSFUL DONATIONS
            #
            # Both CAMPAIGN and PLATFORM donations contribute
            # to total_contributions.
            # =====================================================

            total_contributions += amount

            # =====================================================
            # CAMPAIGN DONATION ONLY
            # =====================================================

            if donation_type_value != "CAMPAIGN":
                continue

            campaign = donation.campaign

            if not campaign:
                continue

            # =====================================================
            # UNIQUE CAMPAIGNS SUPPORTED
            # =====================================================

            supported_campaign_ids.add(
                campaign.pk
            )

            # =====================================================
            # CAMPAIGN STATUS
            # =====================================================

            campaign_status = getattr(
                campaign.campaign_status,
                "value",
                campaign.campaign_status
            )

            campaign_status = str(
                campaign_status
            ).upper()

            if campaign_status == "ACTIVE":

                active_contributions += amount

            elif campaign_status == "COMPLETED":

                completed_contributions += amount

        # =========================================================
        # 9. PAGINATION
        # =========================================================

        paginator = Paginator(
            donations,
            page_size
        )

        try:

            page_obj = paginator.page(
                page
            )

        except EmptyPage:

            return Response(
                {
                    "success": False,
                    "message": "Page number out of range."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # =========================================================
        # 10. BUILD CONTRIBUTIONS
        # =========================================================

        contributions = []

        for donation in page_obj.object_list:

            # =====================================================
            # DONATION TYPE
            # =====================================================

            donation_type_value = getattr(
                donation.donation_type,
                "value",
                donation.donation_type
            )

            donation_type_value = str(
                donation_type_value
            ).upper()

            # =====================================================
            # CAMPAIGN
            # =====================================================

            campaign = donation.campaign

            # =====================================================
            # TRANSACTION
            # =====================================================

            transaction = getattr(
                donation,
                "transaction",
                None
            )

            # =====================================================
            # RECEIPT
            # =====================================================

            receipt = getattr(
                donation,
                "receipt",
                None
            )

            # =====================================================
            # DONATION STATUS
            # =====================================================

            donation_status = getattr(
                donation.status,
                "value",
                donation.status
            )

            donation_status = str(
                donation_status
            )

            # =====================================================
            # CAMPAIGN STATUS
            # =====================================================

            campaign_status = None

            if campaign:

                campaign_status = getattr(
                    campaign.campaign_status,
                    "value",
                    campaign.campaign_status
                )

                campaign_status = str(
                    campaign_status
                )

            # =====================================================
            # CAMPAIGN NAME
            # =====================================================

            campaign_name = None

            if campaign:

                campaign_name = getattr(
                    campaign,
                    "campaign_name",
                    None
                )

            # =====================================================
            # CAMPAIGN BENEFICIARY
            # =====================================================

            beneficiary = None

            if campaign:

                beneficiary_value = getattr(
                    campaign,
                    "beneficiary",
                    None
                )

                if beneficiary_value is None:

                    beneficiary_value = getattr(
                        campaign,
                        "beneficiary_type",
                        None
                    )

                if beneficiary_value is not None:

                    beneficiary = getattr(
                        beneficiary_value,
                        "value",
                        beneficiary_value
                    )

                    beneficiary = str(
                        beneficiary
                    )

            # =====================================================
            # PAYMENT STATUS
            # =====================================================

            if transaction:

                transaction_status = getattr(
                    transaction.status,
                    "value",
                    transaction.status
                )

                transaction_status = str(
                    transaction_status
                ).upper()

                if (
                    transaction.refund_id
                    or transaction.refunded_at
                    or transaction_status in {
                        "REFUNDED",
                        "PARTIALLY_REFUNDED"
                    }
                ):

                    display_payment_status = "Refunded"

                elif transaction_status in {
                    "SUCCESS",
                    "SUCCESSFUL",
                    "COMPLETED",
                    "CAPTURED",
                    "PAID"
                }:

                    display_payment_status = "Paid"

                elif transaction_status in {
                    "FAILED",
                    "FAILURE",
                    "CANCELLED",
                    "CANCELED",
                    "REJECTED"
                }:

                    display_payment_status = "Failed"

                else:

                    display_payment_status = "Pending"

            else:

                donation_status_upper = (
                    donation_status.upper()
                )

                if donation_status_upper in {
                    "SUCCESS",
                    "SUCCESSFUL",
                    "COMPLETED",
                    "PAID"
                }:

                    display_payment_status = "Paid"

                elif donation_status_upper in {
                    "FAILED",
                    "FAILURE",
                    "CANCELLED",
                    "CANCELED",
                    "REJECTED"
                }:

                    display_payment_status = "Failed"

                else:

                    display_payment_status = "Pending"

            # =====================================================
            # RECEIPT
            # =====================================================

            receipt_data = None

            if receipt:

                receipt_file_url = None

                if receipt.receipt_file:

                    try:

                        receipt_file_url = (
                            request.build_absolute_uri(
                                receipt.receipt_file.url
                            )
                        )

                    except Exception:

                        receipt_file_url = None

                receipt_data = {
                    "uuid": str(
                        receipt.uuid
                    ),
                    "receipt_number": (
                        receipt.receipt_num
                    ),
                    "generated_at": (
                        localtime(
                            receipt.generated_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if receipt.generated_at
                        else None
                    ),
                    "file_url": receipt_file_url,
                    "available": bool(
                        receipt.receipt_file
                    )
                }

            # =====================================================
            # PAYMENT DETAILS
            # =====================================================

            payment_data = None

            if transaction:

                gateway = getattr(
                    transaction.gateway,
                    "value",
                    transaction.gateway
                )

                payment_method = getattr(
                    transaction.payment_method,
                    "value",
                    transaction.payment_method
                )

                transaction_currency = getattr(
                    transaction.currency,
                    "value",
                    transaction.currency
                )

                transaction_status_display = getattr(
                    transaction.status,
                    "value",
                    transaction.status
                )

                payment_data = {
                    "transaction_id": str(
                        transaction.uuid
                    ),

                    "gateway": (
                        str(gateway)
                        if gateway is not None
                        else None
                    ),

                    "payment_id": (
                        transaction.gateway_payment_id
                    ),

                    "payment_method": (
                        str(payment_method)
                        if payment_method is not None
                        else None
                    ),

                    "amount": str(
                        transaction.amount
                    ),

                    "currency": (
                        str(transaction_currency)
                        if transaction_currency is not None
                        else None
                    ),

                    "status": (
                        str(transaction_status_display)
                        if transaction_status_display is not None
                        else None
                    ),

                    "processed_at": (
                        localtime(
                            transaction.processed_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if transaction.processed_at
                        else None
                    ),

                    "refund_id": (
                        transaction.refund_id
                    ),

                    "refund_amount": (
                        str(
                            transaction.refund_amount
                        )
                        if transaction.refund_amount is not None
                        else None
                    ),

                    "refunded_at": (
                        localtime(
                            transaction.refunded_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if transaction.refunded_at
                        else None
                    )
                }

            # =====================================================
            # BASE CONTRIBUTION DATA
            # =====================================================

            contribution_data = {
                "donation": {
                    "uuid": str(
                        donation.uuid
                    ),

                    "donation_number": (
                        donation.unique_donation_number
                    ),

                    "donation_type": (
                        donation_type_value
                    ),

                    "amount": str(
                        donation.amount
                    ),

                    "currency": str(
                        getattr(
                            donation.currency,
                            "value",
                            donation.currency
                        )
                    ),

                    "status": donation_status,

                    "is_anonymous": (
                        donation.is_anonymous
                    ),

                    "message": (
                        donation.message
                    ),

                    "donated_at": (
                        localtime(
                            donation.donated_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if donation.donated_at
                        else None
                    ),

                    "created_at": (
                        localtime(
                            donation.created_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                    ),

                    "updated_at": (
                        localtime(
                            donation.updated_at
                        ).strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                    )
                },

                "payment_status": (
                    display_payment_status
                ),

                "payment": payment_data,

                "receipt": receipt_data
            }

            # =====================================================
            # CAMPAIGN DONATION
            #
            # Only CAMPAIGN donations receive "campaign".
            # =====================================================

            if donation_type_value == "CAMPAIGN":

                contribution_data["campaign"] = (
                    {
                        "uuid": (
                            str(
                                campaign.uuid
                            )
                            if getattr(
                                campaign,
                                "uuid",
                                None
                            )
                            else None
                        ),

                        "name": (
                            campaign_name
                        ),

                        "slug": getattr(
                            campaign,
                            "campaign_slug",
                            None
                        ),

                        "beneficiary": (
                            beneficiary
                        ),

                        "status": (
                            campaign_status
                        )
                    }
                    if campaign
                    else None
                )

            # =====================================================
            # PLATFORM DONATION
            #
            # Only PLATFORM donations receive "platform".
            # =====================================================

            elif donation_type_value == "PLATFORM":

                contribution_data["platform"] = {
                    "name": "Platform",

                    "description": (
                        donation.message
                        or "Contribution made to support the platform."
                    )
                }

            # =====================================================
            # ADD CONTRIBUTION
            # =====================================================

            contributions.append(
                contribution_data
            )

        # =========================================================
        # 11. RESPONSE
        # =========================================================

        return Response(
            {
                "success": True,

                "summary": {
                    "total_contributions": str(
                        total_contributions
                    ),

                    "campaigns_supported": len(
                        supported_campaign_ids
                    ),

                    "active_contributions": str(
                        active_contributions
                    ),

                    "completed_contributions": str(
                        completed_contributions
                    )
                },

                "pagination": {
                    "current_page": page_obj.number,

                    "page_size": page_size,

                    "total_pages": paginator.num_pages,

                    "total_records": paginator.count,

                    "has_next": (
                        page_obj.has_next()
                    ),

                    "has_previous": (
                        page_obj.has_previous()
                    ),

                    "next_page": (
                        page_obj.next_page_number()
                        if page_obj.has_next()
                        else None
                    ),

                    "previous_page": (
                        page_obj.previous_page_number()
                        if page_obj.has_previous()
                        else None
                    )
                },

                "contributions": contributions
            },

            status=status.HTTP_200_OK
        )

    except Exception as e:

        return Response(
            {
                "success": False,
                "message": "Unable to fetch CSR contributions.",
                "error": str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_my_contribution_detail(request, donation_uuid):

    # =========================================================
    # 1. VERIFY USER IS CSR
    # =========================================================

    user_type = getattr(request.user, "user_type", None)
    user_type_value = getattr(user_type, "value", user_type)

    if str(user_type_value).upper() != "CSR":
        return Response(
            {
                "success": False,
                "message": "Only CSR users can access this contribution.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # 2. GET CSR DONATION
    # =========================================================

    try:
        donation = (
            Donation.objects
            .select_related(
                "campaign",
                "donor",
                "donor__csr_profile",
                "receipt",
                "transaction",
            )
            .get(
                uuid=donation_uuid,
                donor=request.user,
            )
        )

    except Donation.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Contribution not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # 3. GET CSR PROFILE
    # =========================================================

    csr_profile = getattr(
        request.user,
        "csr_profile",
        None
    )

    # =========================================================
    # 4. DONATION TYPE
    # =========================================================

    donation_type = getattr(
        donation.donation_type,
        "value",
        donation.donation_type,
    )

    donation_type = str(donation_type)

    # =========================================================
    # 5. DONATION STATUS
    # =========================================================

    donation_status = getattr(
        donation.status,
        "value",
        donation.status,
    )

    donation_status = str(donation_status)

    # =========================================================
    # 6. CAMPAIGN DETAILS
    # =========================================================

    campaign_data = None

    if donation.donation_type == DonationType.CAMPAIGN:

        campaign = donation.campaign

        if campaign:

            campaign_status = getattr(
                campaign.campaign_status,
                "value",
                campaign.campaign_status,
            )

            beneficiary = getattr(
                campaign,
                "beneficiary",
                None
            )

            beneficiary_value = getattr(
                beneficiary,
                "value",
                beneficiary,
            )

            campaign_data = {
                "uuid": str(campaign.uuid),
                "name": campaign.campaign_name,
                "slug": campaign.campaign_slug,
                "beneficiary": (
                    str(beneficiary_value)
                    if beneficiary_value
                    else None
                ),
                "status": (
                    str(campaign_status)
                    if campaign_status
                    else None
                ),
            }

    # =========================================================
    # 7. PLATFORM DETAILS
    # =========================================================

    platform_data = None

    if donation.donation_type == DonationType.PLATFORM:

        platform_data = {
            "name": "Platform",
            "description": (
                "Contribution made to support the platform."
            ),
        }

    # =========================================================
    # 8. PAYMENT DETAILS
    # =========================================================

    payment_data = None

    transaction = getattr(
        donation,
        "transaction",
        None
    )

    if transaction:

        gateway = getattr(
            transaction.gateway,
            "value",
            transaction.gateway,
        )

        payment_method = getattr(
            transaction.payment_method,
            "value",
            transaction.payment_method,
        )

        transaction_status = getattr(
            transaction.status,
            "value",
            transaction.status,
        )

        payment_data = {
            "transaction_id": str(transaction.uuid),
            "gateway": (
                str(gateway)
                if gateway
                else None
            ),
            "payment_id": transaction.gateway_payment_id,
            "payment_method": (
                str(payment_method)
                if payment_method
                else None
            ),
            "amount": str(transaction.amount),
            "currency": (
                getattr(
                    transaction.currency,
                    "value",
                    transaction.currency,
                )
                if transaction.currency
                else None
            ),
            "status": (
                str(transaction_status)
                if transaction_status
                else None
            ),
            "processed_at": (
                transaction.processed_at.strftime(
                    "%d %b %Y, %I:%M %p"
                )
                if transaction.processed_at
                else None
            ),
            "refund_id": transaction.refund_id,
            "refund_amount": (
                str(transaction.refund_amount)
                if transaction.refund_amount is not None
                else None
            ),
            "refunded_at": (
                transaction.refunded_at.strftime(
                    "%d %b %Y, %I:%M %p"
                )
                if transaction.refunded_at
                else None
            ),
        }

    # =========================================================
    # 9. RECEIPT DETAILS
    # =========================================================

    receipt_data = None

    receipt = getattr(
        donation,
        "receipt",
        None
    )

    if receipt:

        receipt_data = {
            "uuid": str(receipt.uuid),
            "receipt_number": receipt.receipt_num,
            "generated": bool(receipt.receipt_file),
            "generated_at": (
                receipt.generated_at.strftime(
                    "%d %b %Y, %I:%M %p"
                )
                if receipt.generated_at
                else None
            ),
            "receipt_url": (
                receipt.receipt_file.url
                if receipt.receipt_file
                else None
            ),
        }

    # =========================================================
    # 10. RECEIPT ACTION
    # =========================================================

    if receipt and receipt.receipt_file:

        receipt_action = "DOWNLOAD"

    elif donation.status == DonationStatus.SUCCESS:

        receipt_action = "GENERATE"

    else:

        receipt_action = "NOT_AVAILABLE"

    # =========================================================
    # 11. CSR PROFILE DETAILS
    # =========================================================

    csr_data = {
        "user_uuid": str(request.user.uuid),
        "fullname": request.user.fullname,
        "email": request.user.email,
        "mobile": request.user.mobile,
    }

    if csr_profile:

        csr_data.update(
            {
                "csr_name": csr_profile.csr_name,
                "csr_registration_number": csr_profile.csr_reg_num,
                "contact_person_name": (
                    csr_profile.contact_person_name
                ),
                "contact_person_designation": (
                    csr_profile.contact_person_designation
                ),
                "address": csr_profile.address,
                "city": csr_profile.city,
                "state": csr_profile.state,
                "country": csr_profile.country,
                "pincode": csr_profile.pincode,
                "website": csr_profile.website,
            }
        )

    # =========================================================
    # 12. DONATION DATE
    # =========================================================

    donation_date = (
        donation.donated_at
        if donation.donated_at
        else donation.created_at
    )

    # =========================================================
    # 13. RESPONSE
    # =========================================================

    return Response(
        {
            "success": True,
            "message": "Contribution details retrieved successfully.",

            "data": {

                # -------------------------------------------------
                # CONTRIBUTION
                # -------------------------------------------------

                "contribution": {

                    "uuid": str(donation.uuid),

                    "donation_number": (
                        donation.unique_donation_number
                    ),

                    "donation_type": donation_type,

                    "amount": str(donation.amount),

                    "currency": (
                        getattr(
                            donation.currency,
                            "value",
                            donation.currency,
                        )
                    ),

                    "status": donation_status,

                    "is_anonymous": donation.is_anonymous,

                    "message": donation.message,

                    "donated_at": (
                        donation_date.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if donation_date
                        else None
                    ),

                    "created_at": (
                        donation.created_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if donation.created_at
                        else None
                    ),
                },

                # -------------------------------------------------
                # CSR
                # -------------------------------------------------

                "csr": csr_data,

                # -------------------------------------------------
                # CAMPAIGN
                # -------------------------------------------------

                "campaign": campaign_data,

                # -------------------------------------------------
                # PLATFORM
                # -------------------------------------------------

                "platform": platform_data,

                # -------------------------------------------------
                # PAYMENT
                # -------------------------------------------------

                "payment": payment_data,

                # -------------------------------------------------
                # RECEIPT
                # -------------------------------------------------

                "receipt": receipt_data,

                # -------------------------------------------------
                # FRONTEND ACTION
                # -------------------------------------------------

                "receipt_action": receipt_action,
            },
        },
        status=status.HTTP_200_OK,
    )





