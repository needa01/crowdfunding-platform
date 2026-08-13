from decimal import Decimal

from django.db import transaction
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from django.core.paginator import Paginator

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
from crowdfunding.permissions import CanDonate, IsActiveAccount, IsDonor
from donations.models import Donation
from donations.serializers import CreateDonationSerializer
from payments.models import PaymentTransaction
from verification.models import EntityVerificationRequest


# Create your views here.
@api_view(["POST"])
@permission_classes([CanDonate])
@transaction.atomic
def create_campaign_donation(request):

    campaign_slug = request.data.get("campaign_slug")
    amount = request.data.get("amount")
    message = request.data.get("message", "")
    is_anonymous = request.data.get("is_anonymous", False)

    # ----------------------------
    # Validate Campaign Slug
    # ----------------------------
    if not campaign_slug:
        return Response(
            {"success": False, "message": "Campaign slug is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ----------------------------
    # Validate Amount
    # ----------------------------
    if amount is None:
        return Response(
            {"success": False, "message": "Donation amount is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        amount = Decimal(amount)
    except Exception:
        return Response(
            {"success": False, "message": "Invalid donation amount."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount <= 0:
        return Response(
            {"success": False, "message": "Donation amount must be greater than zero."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if amount < 10:
        return Response(
            {"success": False, "message": "Minimum donation amount is ₹10."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ----------------------------
    # Get Campaign
    # ----------------------------
    campaign = Campaign.objects.filter(
        campaign_slug=campaign_slug,
        is_deleted=False,
    ).first()

    if not campaign:
        return Response(
            {"success": False, "message": "Campaign not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ----------------------------
    # Cannot Donate Own Campaign
    # ----------------------------

    if campaign.created_by_id == request.user.uuid:
        return Response(
            {"success": False, "message": "You cannot donate to your own campaign."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # ----------------------------
    # Campaign Status Check
    # ----------------------------
    if campaign.campaign_status != CampaignStatus.ACTIVE:
        return Response(
            {"success": False, "message": "This campaign is not accepting donations."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ----------------------------
    # Campaign Verification Check
    # ----------------------------

    verification = EntityVerificationRequest.objects.filter(
        campaign=campaign,
        verification_type=VerificationType.CAMPAIGN,
    ).first()

    if not verification:
        return Response(
            {"success": False, "message": "Campaign verification not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if verification.status != VerificationStatus.APPROVED:
        return Response(
            {"success": False, "message": "This campaign is not accepting donations."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ----------------------------
    # Wallet Check
    # ----------------------------
    if not hasattr(campaign, "wallet"):
        return Response(
            {"success": False, "message": "Campaign wallet is not configured."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # ----------------------------
    # Create Donation
    # ----------------------------
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

    # ----------------------------
    # Create Payment Transaction
    # ----------------------------
    payment_transaction = PaymentTransaction.objects.create(
        transaction_type=TransactionType.DONATION,
        donation=donation,
        gateway=PaymentGateway.MANUAL,  # Demo only
        amount=amount,
        currency=Currency.INR,
        status=TransactionStatus.PENDING,
    )

    # ----------------------------
    # Return Demo Payment Details
    # ----------------------------
    return Response(
        {
            "success": True,
            "message": "Donation initiated successfully.",
            "data": {
                "donation_uuid": donation.uuid,
                "transaction_uuid": payment_transaction.uuid,
                "donation_number": donation.unique_donation_number,
                "amount": donation.amount,
                "currency": donation.currency.value,
                "payment_status": payment_transaction.status.value,
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
                        "receipt_url": (
                            request.build_absolute_uri(donation.receipt.receipt_url.url)
                            if hasattr(donation, "receipt")
                            and donation.receipt.receipt_url
                            else None
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
