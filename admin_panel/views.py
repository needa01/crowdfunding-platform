from decimal import Decimal

from django.db import DatabaseError, transaction
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from accounts.models import BankAccount, CustomUser, DonorProfile, IndividualProfile
from admin_panel.serializers import CreateAdminSerializer, DashboardSerializer
from campaigns.models import Campaign, CampaignPromotionService
from crowdfunding.enums import (
    CampaignStatus,
    CampaignCause,
    DocumentPurpose,
    DonationStatus,
    DonationType,
    PromotionStatus,
    Status,
    TransactionStatus,
    UserType,
    VerificationStatus,
    VerificationType,
    WithdrawalStatus,
)
from crowdfunding.permissions import IsPlatformAdmin, IsSuperAdmin
from donations.models import Donation
from django.db.models import Sum

from organizations.models import CSRProfile, NGOProfile
from payments.models import PaymentTransaction, PaymentTransaction, Withdrawal
from verification.models import Document, EntityVerificationRequest


# Create your views here.
@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login(request):
    print("admin_login called")
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response(
            {"success": False, "error": "Email and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Invalid email"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    # Only admins allowed
    if (
        user.user_type not in [UserType.ADMIN, UserType.SUPER_ADMIN]
        and not user.is_superuser
    ):
        return Response(
            {
                "success": False,
                "error": "You are not authorized to access the admin portal.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    print("admin_login: User is an admin")
    if not user.check_password(password):
        return Response(
            {"success": False, "error": "Invalid password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if user.status != Status.ACTIVE:
        return Response(
            {
                "success": False,
                "error": "Your account is inactive.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "success": True,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "message": "Login successful",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def admin_dashboard(request):
    print("admin_dashboard called")
    try:
        user = request.user
        print("everything is okay")
        if (
            user.user_type not in [UserType.ADMIN, UserType.SUPER_ADMIN]
            and not user.is_superuser
        ):
            return Response(
                {
                    "success": False,
                    "error": "You are not authorized to access the admin dashboard.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        print("everything is okay2")

        total_users = CustomUser.objects.exclude(
            user_type__in=[UserType.ADMIN, UserType.SUPER_ADMIN], is_superuser=True
        ).count()
        total_individual_fundraisers = CustomUser.objects.filter(
            user_type=UserType.INDIVIDUAL_FUNDRAISER
        ).count()
        total_ngos = CustomUser.objects.filter(user_type=UserType.NGO).count()
        total_csrs = CustomUser.objects.filter(user_type=UserType.CSR).count()
        print("everything is okay3")

        total_active_campaigns = Campaign.objects.filter(
            campaign_status=CampaignStatus.ACTIVE
        ).count()
        total_completed_campaigns = Campaign.objects.filter(
            Q(campaign_status=CampaignStatus.COMPLETED) | Q(end_date__lt=timezone.now())
        ).count()
        total_pending_campaigns = Campaign.objects.filter(
            campaign_status=CampaignStatus.PENDING
        ).count()
        total_rejected_campaigns = Campaign.objects.filter(
            campaign_status=CampaignStatus.REJECTED
        ).count()
        print("everything is okay4")

        total_donations = (
            Donation.objects.filter(status=DonationStatus.SUCCESS).aggregate(
                total_amount=Sum("amount")
            )["total_amount"]
            or 0
        )
        donation_count = Donation.objects.filter(status=DonationStatus.SUCCESS).count()
        platform_donations = (
            Donation.objects.filter(
                donation_type=DonationType.PLATFORM, status=DonationStatus.SUCCESS
            ).aggregate(total_amount=Sum("amount"))["total_amount"]
            or 0
        )
        total_refund = (
            Donation.objects.filter(status=DonationStatus.REFUNDED).aggregate(
                total_amount=Sum("amount")
            )["total_amount"]
            or 0
        )
        print("everything is okay5")

        pending_withdrawal_amount = (
            Withdrawal.objects.filter(
                status__in=[WithdrawalStatus.PENDING, WithdrawalStatus.APPROVED]
            ).aggregate(total=Sum("amount"))["total"]
            or 0
        )
        total_withdrawn = (
            Withdrawal.objects.filter(status=WithdrawalStatus.PAID).aggregate(
                total=Sum("amount")
            )["total"]
            or 0
        )
        failed_payments = (
            PaymentTransaction.objects.filter(status=TransactionStatus.FAILED).count()
            or 0
        )
        total_campaign_service_amount = (
            CampaignPromotionService.objects.aggregate(total_amount=Sum("amount"))[
                "total_amount"
            ]
            or 0
        )
        print("everything is okay5")

        pending_individual_fundraisers = EntityVerificationRequest.objects.filter(
            verification_type=VerificationType.INDIVIDUAL_FUNDRAISER,
            status=VerificationStatus.PENDING,
        ).count()
        pending_ngos = EntityVerificationRequest.objects.filter(
            verification_type=VerificationType.NGO, status=VerificationStatus.PENDING
        ).count()
        pending_csrs = EntityVerificationRequest.objects.filter(
            verification_type=VerificationType.CSR, status=VerificationStatus.PENDING
        ).count()
        pending_donors = EntityVerificationRequest.objects.filter(
            verification_type=VerificationType.DONOR, status=VerificationStatus.PENDING
        ).count()
        pending_campaigns = EntityVerificationRequest.objects.filter(
            verification_type=VerificationType.CAMPAIGN,
            status=VerificationStatus.PENDING,
        ).count()

        print("everything is okay6")

        data = {
            "kpis": {
                "users": {
                    "total_users": total_users,
                    "individual_fundraisers": total_individual_fundraisers,
                    "ngos": total_ngos,
                    "csrs": total_csrs,
                },
                "campaigns": {
                    "active": total_active_campaigns,
                    "completed": total_completed_campaigns,
                    "pending_approval": total_pending_campaigns,
                    "rejected": total_rejected_campaigns,
                },
                "donations": {
                    "total_donations": total_donations,
                    "donation_count": donation_count,
                    "platform_donations": platform_donations,
                    "total_refund": total_refund,
                },
                "payments": {
                    "pending_withdrawal_amount": pending_withdrawal_amount,
                    "total_withdrawn": total_withdrawn,
                    "failed_payments": failed_payments,
                    "total_campaign_service_amount": total_campaign_service_amount,
                },
            },
            "pending_actions": {
                "individual_fundraisers": pending_individual_fundraisers,
                "ngos": pending_ngos,
                "csrs": pending_csrs,
                "donors": pending_donors,
                "campaigns": pending_campaigns,
            },
        }
        print("everything is okay7")

        serializer = DashboardSerializer(data)
        print("everything is okay8")

        return Response(
            {"success": True, "data": serializer.data}, status=status.HTTP_200_OK
        )

    except DatabaseError:
        return Response(
            {
                "success": False,
                "error": "Unable to load dashboard data. Please try again later.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_users(request):
    try:
        role = request.GET.get("role")
        verification_status = request.GET.get("status")

        if role:
            try:
                role = VerificationType[role.upper()]
            except KeyError:
                return Response(
                    {"success": False, "error": "Invalid verification type."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if verification_status:
            try:
                verification_status = VerificationStatus[verification_status.upper()]
            except KeyError:
                return Response(
                    {"success": False, "error": "Invalid verification status."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        queryset = EntityVerificationRequest.objects.select_related(
            "user",
            "campaign",
        ).order_by("-created_at")

        if role:
            queryset = queryset.filter(verification_type=role)

        if verification_status:
            queryset = queryset.filter(status=verification_status)

        results = []

        for verification in queryset:

            if verification.verification_type == VerificationType.CAMPAIGN:
                campaign = verification.campaign

                results.append(
                    {
                        "campaign_slug": campaign.campaign_slug,
                        "campaign_name": campaign.campaign_name,
                        "goal_amount": campaign.goal_amount,
                        "campaign_type": campaign.campaign_type.value,
                        "created_by": {
                            "fullname": campaign.created_by.display_name,
                            "user_type": campaign.created_by.user_type.value,
                        },
                    }
                )

            else:
                user = verification.user

                results.append(
                    {
                        "uuid": user.uuid,
                        "fullname": user.display_name,
                        "email": user.email,
                        "mobile": user.mobile,
                        "profile_picture": (
                            user.profile_picture.url if user.profile_picture else None
                        ),
                        "verification_submitted_at": verification.updated_at,
                    }
                )

        return Response(
            {
                "success": True,
                "count": queryset.count(),
                "role": role.value,
                "status": verification_status.value,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsSuperAdmin])
def get_admins(request):

    try:
        # Only superadmin can access this API
        if request.user.user_type != UserType.SUPER_ADMIN and not request.user.is_superuser:
            return Response(
                {
                    "success": False,
                    "message": "Only superadmin can access admin management.",
                },
                status=403,
            )

        admins = CustomUser.objects.filter(user_type=UserType.ADMIN).order_by(
            "-created_at"
        )

        data = []

        for admin in admins:

            data.append(
                {
                    "uuid": str(admin.uuid),
                    "fullname": admin.fullname,
                    "email": admin.email,
                    "mobile": admin.mobile,
                    "status": admin.status.value if admin.status else None,
                    "created_at": (
                        admin.created_at.strftime("%d %b %Y, %I:%M %p")
                        if admin.created_at
                        else None
                    ),
                }
            )

        return Response(
            {
                "success": True,
                "message": "Admins retrieved successfully.",
                "data": data,
                "count": len(data),
            },
            status=200,
        )

    except Exception as e:

        return Response(
            {
                "success": False,
                "message": "Failed to retrieve admins.",
                "error": str(e),
            },
            status=500,
        )




@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def get_promotion_services_list(request,status):
    try:
        # =========================================================
        # 1. VALIDATE STATUS
        # =========================================================

        status_value = str(status).strip().lower()

        status_map = {
            "pending": PromotionStatus.PENDING,
            "submitted": PromotionStatus.SUBMITTED,
            "active": PromotionStatus.ACTIVE,
            "completed": PromotionStatus.COMPLETED,
            "cancelled": PromotionStatus.CANCELLED,
        }

        if status_value not in status_map:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Invalid status. Allowed values are: "
                        "Pending, Submitted, Active, Completed, Cancelled."
                    ),
                },
                status=400,
            )

        promotion_status = status_map[status_value]

        # =========================================================
        # 2. GET PROMOTION SERVICES
        # =========================================================

        services = (
            CampaignPromotionService.objects
            .filter(promotion_status=promotion_status)
            .select_related("campaign")
            .order_by("-created_at")
        )

        # =========================================================
        # 3. BUILD RESPONSE
        # =========================================================

        service_data = []

        for service in services:
            service_data.append(
                {
                    "uuid": str(service.uuid),
                    "campaign": {
                        "uuid": str(service.campaign.uuid),
                        "slug": service.campaign.campaign_slug,
                        "title": service.campaign.campaign_name,
                    },
                    "service_type": (
                        service.service_type
                        if isinstance(service.service_type, str)
                        else service.service_type.value
                    ),
                    "amount": str(service.amount),
                    "fee": str(service.fee),
                    "tax": str(service.tax),
                    "currency": service.currency.value,
                    "promotion_status": (
                        service.promotion_status.value
                        if hasattr(service.promotion_status, "value")
                        else service.promotion_status
                    ),
                    "user_notes": service.user_notes,
                    "created_at": service.created_at,
                    "updated_at": service.updated_at,
                }
            )

        # =========================================================
        # 4. RESPONSE
        # =========================================================

        return Response(
            {
                "success": True,
                "message": "Promotion services fetched successfully.",
                "status": promotion_status.value,
                "count": len(service_data),
                "services": service_data,
            },
            status=200,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "message": "Failed to fetch promotion services.",
                "error": str(e),
            },
            status=500,
        )






@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_donor_for_verification(request, user_id):

    try:
        user = CustomUser.objects.select_related(
            "bank_account",
            "bank_account__verified_by",
        ).get(
            uuid=user_id,
            user_type=UserType.DONOR,
            is_deleted=False,
        )

    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "message": "Donor not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # ------------------------------------
    # Profile
    # ------------------------------------

    profile = DonorProfile.objects.filter(user=user).first()
    # ------------------------------------
    # Bank Account
    # ------------------------------------

    bank = getattr(user, "bank_account", None)

    # ------------------------------------
    # Verification Request
    # ------------------------------------

    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    # ------------------------------------
    # User Documents
    # ------------------------------------

    documents = (
        Document.objects.select_related(
            "reviewed_by",
        )
        .filter(user=user, purpose=DocumentPurpose.PROFILE_VERIFICATION)
        .order_by("created_at")
    )

    response = {
        "success": True,
        "message": "Donor details fetched successfully.",
        "data": {
            # ---------------- USER ----------------
            "user": {
                "uuid": str(user.uuid),
                "fullname": user.fullname,
                "email": user.email,
                "mobile": user.mobile,
                "profile_picture": (
                    request.build_absolute_uri(user.profile_picture.url)
                    if user.profile_picture
                    else None
                ),
                "user_type": user.user_type.value,
                "status": user.status.value,
                "profile_status": user.profile_status.value,
                "created_at": (
                    user.created_at.strftime("%d %b %Y, %I:%M %p")
                    if user.created_at
                    else None
                ),
            },
            # ---------------- PROFILE ----------------
            "profile": (
                {
                    "occupation": getattr(profile, "occupation", None),
                    "address": getattr(profile, "address", None),
                    "city": getattr(profile, "city", None),
                    "state": getattr(profile, "state", None),
                    "country": getattr(profile, "country", None),
                    "pincode": getattr(profile, "pincode", None),
                }
                if profile
                else None
            ),
            # ---------------- BANK ----------------
            "bank": (
                {
                    "uuid": str(bank.uuid),
                    "account_holder_name": bank.account_holder_name,
                    "bank_name": bank.bank_name,
                    "account_number": bank.account_number,
                    "ifsc_code": bank.ifsc_code,
                    "branch_name": bank.branch_name,
                    "verification_status": bank.verification_status.value,
                    "remarks": bank.remarks,
                    "verified_by": (
                        bank.verified_by.display_name if bank.verified_by else None
                    ),
                    "verified_at": (
                        bank.verified_at.strftime("%d %b %Y, %I:%M %p")
                        if bank.verified_at
                        else None
                    ),
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank.cancelled_cheque.url)
                        if bank.cancelled_cheque
                        else None
                    ),
                }
                if bank
                else None
            ),
            # ---------------- DOCUMENTS ----------------
            "documents": [
                {
                    "uuid": str(document.uuid),
                    "document_type": document.document_type,
                    "document_number": document.document_number,
                    "file": (
                        request.build_absolute_uri(document.file_url.url)
                        if document.file_url
                        else None
                    ),
                    "verification_status": document.verification_status.value,
                    "verification_remarks": document.verification_remarks,
                    "reviewed_by": (
                        document.reviewed_by.fullname if document.reviewed_by else None
                    ),
                    "reviewed_at": (
                        document.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                        if document.reviewed_at
                        else None
                    ),
                    "created_at": (
                        document.created_at.strftime("%d %b %Y, %I:%M %p")
                        if document.created_at
                        else None
                    ),
                }
                for document in documents
            ],
            # ---------------- VERIFICATION REQUEST ----------------
            "verification_request": {
                "uuid": (str(verification.uuid) if verification else None),
                "verification_type": (
                    verification.verification_type.value if verification else None
                ),
                "status": (verification.status.value if verification else None),
                "ai_score": (verification.ai_result if verification else None),
                "remarks": (verification.remarks if verification else None),
                "reviewed_by": (
                    verification.reviewed_by.display_name
                    if verification and verification.reviewed_by
                    else None
                ),
                "reviewed_at": (
                    verification.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.reviewed_at
                    else None
                ),
                "created_at": (
                    verification.created_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.created_at
                    else None
                ),
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_fundraiser_for_verification(request, user_id):

    try:
        user = CustomUser.objects.select_related(
            "bank_account",
            "bank_account__verified_by",
        ).get(
            uuid=user_id,
            user_type=UserType.INDIVIDUAL_FUNDRAISER,
            is_deleted=False,
        )

    except CustomUser.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Individual fundraiser not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ------------------------------------
    # Profile
    # ------------------------------------

    profile = IndividualProfile.objects.filter(user=user).first()

    # ------------------------------------
    # Bank Account
    # ------------------------------------

    bank = getattr(user, "bank_account", None)

    # ------------------------------------
    # Verification Request
    # ------------------------------------

    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    # ------------------------------------
    # Documents
    # ------------------------------------

    documents = (
        Document.objects.select_related(
            "reviewed_by",
        )
        .filter(
            user=user,
            purpose=DocumentPurpose.PROFILE_VERIFICATION,
        )
        .order_by("created_at")
    )

    response = {
        "success": True,
        "message": "Individual fundraiser details fetched successfully.",
        "data": {
            # ---------------- USER ----------------
            "user": {
                "uuid": str(user.uuid),
                "fullname": user.fullname,
                "email": user.email,
                "mobile": user.mobile,
                "profile_picture": (
                    request.build_absolute_uri(user.profile_picture.url)
                    if user.profile_picture
                    else None
                ),
                "user_type": user.user_type.value,
                "status": user.status.value,
                "profile_status": user.profile_status.value,
                "created_at": (
                    user.created_at.strftime("%d %b %Y, %I:%M %p")
                    if user.created_at
                    else None
                ),
            },
            # ---------------- PROFILE ----------------
            "profile": (
                {
                    "occupation": profile.occupation,
                    "address": profile.address,
                    "city": profile.city,
                    "state": profile.state,
                    "country": profile.country,
                    "pincode": profile.pincode,
                }
                if profile
                else None
            ),
            # ---------------- BANK ----------------
            "bank": (
                {
                    "uuid": str(bank.uuid),
                    "account_holder_name": bank.account_holder_name,
                    "bank_name": bank.bank_name,
                    "account_number": bank.account_number,
                    "ifsc_code": bank.ifsc_code,
                    "branch_name": bank.branch_name,
                    "verification_status": bank.verification_status.value,
                    "remarks": bank.remarks,
                    "verified_by": (
                        bank.verified_by.display_name if bank.verified_by else None
                    ),
                    "verified_at": (
                        bank.verified_at.strftime("%d %b %Y, %I:%M %p")
                        if bank.verified_at
                        else None
                    ),
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank.cancelled_cheque.url)
                        if bank.cancelled_cheque
                        else None
                    ),
                }
                if bank
                else None
            ),
            # ---------------- DOCUMENTS ----------------
            "documents": [
                {
                    "uuid": str(document.uuid),
                    "document_type": document.document_type,
                    "document_number": document.document_number,
                    "file": (
                        request.build_absolute_uri(document.file_url.url)
                        if document.file_url
                        else None
                    ),
                    "verification_status": document.verification_status.value,
                    "verification_remarks": document.verification_remarks,
                    "reviewed_by": (
                        document.reviewed_by.fullname if document.reviewed_by else None
                    ),
                    "reviewed_at": (
                        document.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                        if document.reviewed_at
                        else None
                    ),
                    "created_at": (
                        document.created_at.strftime("%d %b %Y, %I:%M %p")
                        if document.created_at
                        else None
                    ),
                }
                for document in documents
            ],
            # ---------------- VERIFICATION REQUEST ----------------
            "verification_request": {
                "uuid": (str(verification.uuid) if verification else None),
                "verification_type": (
                    verification.verification_type.value if verification else None
                ),
                "status": (verification.status.value if verification else None),
                "ai_score": (verification.ai_result if verification else None),
                "remarks": (verification.remarks if verification else None),
                "reviewed_by": (
                    verification.reviewed_by.display_name
                    if verification and verification.reviewed_by
                    else None
                ),
                "reviewed_at": (
                    verification.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.reviewed_at
                    else None
                ),
                "created_at": (
                    verification.created_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.created_at
                    else None
                ),
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_ngo_for_verification(request, user_id):

    try:
        user = CustomUser.objects.select_related(
            "ngo_profile",
            "bank_account",
            "bank_account__verified_by",
        ).get(
            uuid=user_id,
            user_type=UserType.NGO,
            is_deleted=False,
        )

    except CustomUser.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "NGO not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ------------------------------------
    # NGO Profile
    # ------------------------------------

    profile = getattr(user, "ngo_profile", None)

    # ------------------------------------
    # Bank Account
    # ------------------------------------

    bank = getattr(user, "bank_account", None)

    # ------------------------------------
    # Verification Request
    # ------------------------------------

    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    # ------------------------------------
    # Documents
    # ------------------------------------

    documents = (
        Document.objects.select_related(
            "reviewed_by",
        )
        .filter(
            user=user,
            purpose=DocumentPurpose.PROFILE_VERIFICATION,
        )
        .order_by("created_at")
    )

    response = {
        "success": True,
        "message": "NGO details fetched successfully.",
        "data": {
            # ---------------- USER ----------------
            "user": {
                "uuid": str(user.uuid),
                "fullname": user.fullname,
                "email": user.email,
                "mobile": user.mobile,
                "profile_picture": (
                    request.build_absolute_uri(user.profile_picture.url)
                    if user.profile_picture
                    else None
                ),
                "user_type": user.user_type.value,
                "status": user.status.value,
                "profile_status": user.profile_status.value,
                "created_at": (
                    user.created_at.strftime("%d %b %Y, %I:%M %p")
                    if user.created_at
                    else None
                ),
            },
            # ---------------- NGO PROFILE ----------------
            "profile": (
                {
                    "uuid": str(profile.uuid),
                    "ngo_name": profile.ngo_name,
                    "ngo_type": profile.ngo_type.value,
                    "registration_number": profile.reg_num,
                    "contact_person_name": profile.contact_person_name,
                    "contact_person_designation": profile.contact_person_designation,
                    "website": profile.website,
                    "address": profile.address,
                    "city": profile.city,
                    "state": profile.state,
                    "country": profile.country,
                    "pincode": profile.pincode,
                    "created_at": (
                        profile.created_at.strftime("%d %b %Y, %I:%M %p")
                        if profile.created_at
                        else None
                    ),
                }
                if profile
                else None
            ),
            # ---------------- BANK ----------------
            "bank": (
                {
                    "uuid": str(bank.uuid),
                    "account_holder_name": bank.account_holder_name,
                    "bank_name": bank.bank_name,
                    "account_number": bank.account_number,
                    "account_type": bank.account_type.value,
                    "ifsc_code": bank.ifsc_code,
                    "branch_name": bank.branch_name,
                    "verification_status": bank.verification_status.value,
                    "remarks": bank.remarks,
                    "verified_by": (
                        bank.verified_by.display_name if bank.verified_by else None
                    ),
                    "verified_at": (
                        bank.verified_at.strftime("%d %b %Y, %I:%M %p")
                        if bank.verified_at
                        else None
                    ),
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank.cancelled_cheque.url)
                        if bank.cancelled_cheque
                        else None
                    ),
                }
                if bank
                else None
            ),
            # ---------------- DOCUMENTS ----------------
            "documents": [
                {
                    "uuid": str(document.uuid),
                    "document_type": document.document_type,
                    "document_number": document.document_number,
                    "file": (
                        request.build_absolute_uri(document.file_url.url)
                        if document.file_url
                        else None
                    ),
                    "verification_status": document.verification_status.value,
                    "verification_remarks": document.verification_remarks,
                    "reviewed_by": (
                        document.reviewed_by.display_name
                        if document.reviewed_by
                        else None
                    ),
                    "reviewed_at": (
                        document.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                        if document.reviewed_at
                        else None
                    ),
                    "created_at": (
                        document.created_at.strftime("%d %b %Y, %I:%M %p")
                        if document.created_at
                        else None
                    ),
                }
                for document in documents
            ],
            # ---------------- VERIFICATION REQUEST ----------------
            "verification_request": {
                "uuid": str(verification.uuid) if verification else None,
                "verification_type": (
                    verification.verification_type.value if verification else None
                ),
                "status": (verification.status.value if verification else None),
                "ai_score": (verification.ai_result if verification else None),
                "remarks": (verification.remarks if verification else None),
                "reviewed_by": (
                    verification.reviewed_by.display_name
                    if verification and verification.reviewed_by
                    else None
                ),
                "reviewed_at": (
                    verification.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.reviewed_at
                    else None
                ),
                "created_at": (
                    verification.created_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.created_at
                    else None
                ),
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_csr_for_verification(request, user_id):

    try:
        user = CustomUser.objects.select_related(
            "csr_profile",
            "bank_account",
            "bank_account__verified_by",
        ).get(
            uuid=user_id,
            user_type=UserType.CSR,
            is_deleted=False,
        )

    except CustomUser.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "CSR not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ------------------------------------
    # CSR Profile
    # ------------------------------------

    profile = getattr(user, "csr_profile", None)

    # ------------------------------------
    # Bank Account
    # ------------------------------------

    bank = getattr(user, "bank_account", None)

    # ------------------------------------
    # Verification Request
    # ------------------------------------

    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    # ------------------------------------
    # Documents
    # ------------------------------------

    documents = (
        Document.objects.select_related(
            "reviewed_by",
        )
        .filter(
            user=user,
            purpose=DocumentPurpose.PROFILE_VERIFICATION,
        )
        .order_by("created_at")
    )

    response = {
        "success": True,
        "message": "CSR details fetched successfully.",
        "data": {
            # ---------------- USER ----------------
            "user": {
                "uuid": str(user.uuid),
                "fullname": user.fullname,
                "email": user.email,
                "mobile": user.mobile,
                "profile_picture": (
                    request.build_absolute_uri(user.profile_picture.url)
                    if user.profile_picture
                    else None
                ),
                "user_type": user.user_type.value,
                "status": user.status.value,
                "profile_status": user.profile_status.value,
                "created_at": (
                    user.created_at.strftime("%d %b %Y, %I:%M %p")
                    if user.created_at
                    else None
                ),
            },
            # ---------------- CSR PROFILE ----------------
            "profile": (
                {
                    "uuid": str(profile.uuid),
                    "csr_name": profile.csr_name,
                    "csr_registration_number": profile.csr_reg_num,
                    "contact_person_name": profile.contact_person_name,
                    "contact_person_designation": profile.contact_person_designation,
                    "website": profile.website,
                    "address": profile.address,
                    "city": profile.city,
                    "state": profile.state,
                    "country": profile.country,
                    "pincode": profile.pincode,
                    "created_at": (
                        profile.created_at.strftime("%d %b %Y, %I:%M %p")
                        if profile.created_at
                        else None
                    ),
                }
                if profile
                else None
            ),
            # ---------------- BANK ----------------
            "bank": (
                {
                    "uuid": str(bank.uuid),
                    "account_holder_name": bank.account_holder_name,
                    "bank_name": bank.bank_name,
                    "account_number": bank.account_number,
                    "account_type": bank.account_type.value,
                    "ifsc_code": bank.ifsc_code,
                    "branch_name": bank.branch_name,
                    "verification_status": bank.verification_status.value,
                    "remarks": bank.remarks,
                    "verified_by": (
                        bank.verified_by.display_name if bank.verified_by else None
                    ),
                    "verified_at": (
                        bank.verified_at.strftime("%d %b %Y, %I:%M %p")
                        if bank.verified_at
                        else None
                    ),
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank.cancelled_cheque.url)
                        if bank.cancelled_cheque
                        else None
                    ),
                }
                if bank
                else None
            ),
            # ---------------- DOCUMENTS ----------------
            "documents": [
                {
                    "uuid": str(document.uuid),
                    "document_type": document.document_type,
                    "document_number": document.document_number,
                    "file": (
                        request.build_absolute_uri(document.file_url.url)
                        if document.file_url
                        else None
                    ),
                    "verification_status": document.verification_status.value,
                    "verification_remarks": document.verification_remarks,
                    "reviewed_by": (
                        document.reviewed_by.display_name
                        if document.reviewed_by
                        else None
                    ),
                    "reviewed_at": (
                        document.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                        if document.reviewed_at
                        else None
                    ),
                    "created_at": (
                        document.created_at.strftime("%d %b %Y, %I:%M %p")
                        if document.created_at
                        else None
                    ),
                }
                for document in documents
            ],
            # ---------------- VERIFICATION REQUEST ----------------
            "verification_request": {
                "uuid": str(verification.uuid) if verification else None,
                "verification_type": (
                    verification.verification_type.value if verification else None
                ),
                "status": (verification.status.value if verification else None),
                "ai_score": (verification.ai_result if verification else None),
                "remarks": (verification.remarks if verification else None),
                "reviewed_by": (
                    verification.reviewed_by.display_name
                    if verification and verification.reviewed_by
                    else None
                ),
                "reviewed_at": (
                    verification.reviewed_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.reviewed_at
                    else None
                ),
                "created_at": (
                    verification.created_at.strftime("%d %b %Y, %I:%M %p")
                    if verification and verification.created_at
                    else None
                ),
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def get_campaign_for_verification(request, campaign_slug):

    try:
        campaign = Campaign.objects.select_related(
            "created_by",
            "created_by__individual_profile",
            "created_by__ngo_profile",
            "ngo",
        ).get(
            campaign_slug=campaign_slug,
            is_deleted=False,
        )

    except Campaign.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # VERIFICATION REQUEST
    # =========================================================

    verification = (
        EntityVerificationRequest.objects.select_related("reviewed_by")
        .filter(campaign=campaign)
        .order_by("-created_at")
        .first()
    )

    # =========================================================
    # CAMPAIGN DOCUMENTS
    # =========================================================

    documents = (
        Document.objects.select_related("reviewed_by")
        .filter(
            campaign=campaign,
            purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
        )
        .order_by("created_at")
    )

    # =========================================================
    # CAMPAIGN BANK ACCOUNT
    # =========================================================

    bank_account = (
        BankAccount.objects
        .filter(campaign=campaign)
        .first()
    )

    # =========================================================
    # PROFILES
    # =========================================================

    profile = getattr(
        campaign.created_by,
        "individual_profile",
        None,
    )

    ngo_profile = getattr(
        campaign.created_by,
        "ngo_profile",
        None,
    )

    # =========================================================
    # RESPONSE
    # =========================================================

    response = {
        "success": True,
        "message": "Campaign details fetched successfully.",

        "data": {

            # =====================================================
            # CAMPAIGN
            # =====================================================

            "campaign": {
                "campaign_slug": campaign.campaign_slug,
                "campaign_name": campaign.campaign_name,
                "campaign_type": campaign.campaign_type.value,
                "cause": campaign.cause.value,
                "campaign_description": campaign.campaign_desc,
                "goal_amount": campaign.goal_amount,
                "raised_amount": campaign.raised_amount,
                "campaign_status": campaign.campaign_status.value,

                "cover_photo": (
                    request.build_absolute_uri(
                        campaign.cover_photo.url
                    )
                    if campaign.cover_photo
                    else None
                ),

                "total_donors": campaign.total_donors,
                "total_views": campaign.total_views,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,

                "created_at": (
                    campaign.created_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                    if campaign.created_at
                    else None
                ),
            },

            # =====================================================
            # CREATOR
            # =====================================================

            "creator": {
                "uuid": str(campaign.created_by.uuid),
                "fullname": campaign.created_by.fullname,
                "email": campaign.created_by.email,
                "mobile": campaign.created_by.mobile,
                "user_type": campaign.created_by.user_type.value,

                "profile_picture": (
                    request.build_absolute_uri(
                        campaign.created_by.profile_picture.url
                    )
                    if campaign.created_by.profile_picture
                    else None
                ),

                # Individual Profile
                "individual_profile": (
                    {
                        "occupation": profile.occupation,
                        "address": profile.address,
                        "city": profile.city,
                        "state": profile.state,
                        "country": profile.country,
                        "pincode": profile.pincode,
                    }
                    if profile
                    else None
                ),

                # NGO Profile
                "ngo_profile": (
                    {
                        "uuid": str(ngo_profile.uuid),
                        "ngo_name": ngo_profile.ngo_name,
                        "ngo_type": ngo_profile.ngo_type.value,
                        "registration_number": ngo_profile.reg_num,
                        "contact_person_name": (
                            ngo_profile.contact_person_name
                        ),
                        "contact_person_designation": (
                            ngo_profile.contact_person_designation
                        ),
                        "address": ngo_profile.address,
                        "city": ngo_profile.city,
                        "state": ngo_profile.state,
                        "country": ngo_profile.country,
                        "pincode": ngo_profile.pincode,
                        "website": ngo_profile.website,
                    }
                    if ngo_profile
                    else None
                ),
            },

            # =====================================================
            # NGO
            # =====================================================

            "ngo": (
                {
                    "uuid": str(campaign.ngo.uuid),
                    "ngo_name": campaign.ngo.ngo_name,
                    "ngo_type": campaign.ngo.ngo_type.value,
                    "registration_number": campaign.ngo.reg_num,
                    "contact_person_name": (
                        campaign.ngo.contact_person_name
                    ),
                    "contact_person_designation": (
                        campaign.ngo.contact_person_designation
                    ),
                    "address": campaign.ngo.address,
                    "city": campaign.ngo.city,
                    "state": campaign.ngo.state,
                    "country": campaign.ngo.country,
                    "pincode": campaign.ngo.pincode,
                    "website": campaign.ngo.website,

                    "created_at": (
                        campaign.ngo.created_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if campaign.ngo.created_at
                        else None
                    ),
                }
                if campaign.ngo
                else None
            ),

            # =====================================================
            # MEDICAL DETAILS
            # =====================================================

            "medical_details": (
                {
                    "hospital_name": campaign.hospital_name,
                    "hospital_location": campaign.hospital_location,
                    "ailment": campaign.ailment,
                }
                if campaign.cause == CampaignCause.MEDICAL
                else None
            ),

            # =====================================================
            # BENEFICIARY
            # =====================================================

            "beneficiary": {
                "beneficiary_type": (
                    campaign.beneficiary_type.value
                    if campaign.beneficiary_type
                    else None
                ),

                "beneficiary_group_type": (
                    campaign.beneficiary_group_type.value
                    if campaign.beneficiary_group_type
                    else None
                ),

                "beneficiary_name": campaign.beneficiary_name,

                "beneficiary_relation": (
                    campaign.beneficiary_relation.value
                    if campaign.beneficiary_relation
                    else None
                ),

                "beneficiary_mobile": campaign.beneficiary_mobile,
                "beneficiary_location": campaign.beneficiary_location,
                "beneficiary_member_count": (
                    campaign.beneficiary_member_count
                ),
                "beneficiary_age": campaign.beneficiary_age,
            },

            # =====================================================
            # BANK ACCOUNT
            # =====================================================

            "bank_account": (
                {
                    "uuid": str(bank_account.uuid),

                    "account_holder_name": (
                        bank_account.account_holder_name
                    ),

                    "account_number": (
                        bank_account.account_number
                    ),

                    "ifsc_code": bank_account.ifsc_code,

                    "bank_name": bank_account.bank_name,

                    "branch_name": bank_account.branch_name,

                    # If your BankAccount model has these fields,
                    # keep them. Otherwise remove them.
                    "verification_status": (
                        bank_account.verification_status.value
                        if getattr(
                            bank_account,
                            "verification_status",
                            None,
                        )
                        else None
                    ),

                    "verification_remarks": getattr(
                        bank_account,
                        "verification_remarks",
                        None,
                    ),

                    "reviewed_by": (
                        bank_account.reviewed_by.fullname
                        if getattr(
                            bank_account,
                            "reviewed_by",
                            None,
                        )
                        else None
                    ),

                    "reviewed_at": (
                        bank_account.reviewed_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if getattr(
                            bank_account,
                            "reviewed_at",
                            None,
                        )
                        else None
                    ),

                    "created_at": (
                        bank_account.created_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if bank_account.created_at
                        else None
                    ),
                }
                if bank_account
                else None
            ),

            # =====================================================
            # DOCUMENTS
            # =====================================================

            "documents": [
                {
                    "uuid": str(document.uuid),

                    "document_type": document.document_type,

                    

                    "document_number": document.document_number,

                    "file": (
                        request.build_absolute_uri(
                            document.file_url.url
                        )
                        if document.file_url
                        else None
                    ),

                    "verification_status": (
                        document.verification_status.value
                    ),

                    "verification_remarks": (
                        document.verification_remarks
                    ),

                    "reviewed_by": (
                        document.reviewed_by.fullname
                        if document.reviewed_by
                        else None
                    ),

                    "reviewed_at": (
                        document.reviewed_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if document.reviewed_at
                        else None
                    ),

                    "created_at": (
                        document.created_at.strftime(
                            "%d %b %Y, %I:%M %p"
                        )
                        if document.created_at
                        else None
                    ),
                }
                for document in documents
            ],

            # =====================================================
            # VERIFICATION REQUEST
            # =====================================================

            "verification_request": {
                "uuid": (
                    str(verification.uuid)
                    if verification
                    else None
                ),

                "verification_type": (
                    verification.verification_type.value
                    if verification
                    else None
                ),

                "status": (
                    verification.status.value
                    if verification
                    else None
                ),

                "ai_score": (
                    verification.ai_result
                    if verification
                    else None
                ),

                "remarks": (
                    verification.remarks
                    if verification
                    else None
                ),

                "reviewed_by": (
                    verification.reviewed_by.fullname
                    if verification
                    and verification.reviewed_by
                    else None
                ),

                "reviewed_at": (
                    verification.reviewed_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                    if verification
                    and verification.reviewed_at
                    else None
                ),

                "created_at": (
                    verification.created_at.strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                    if verification
                    else None
                ),
            },

            # =====================================================
            # FINANCIALS
            # =====================================================

            "financials": {
                "goal_amount": campaign.goal_amount,
                "raised_amount": campaign.raised_amount,
                "amount_withdrawn": campaign.amount_withdrawn,
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
    )



# =============================================================
# GET PROMOTION SERVICE DETAIL
# =============================================================

@api_view(["GET"])
@permission_classes([IsPlatformAdmin])
def get_promotion_service_detail(request, uuid):

    try:

        # =========================================================
        # 1. GET PROMOTION SERVICE
        # =========================================================

        try:
            promotion_service = (
                CampaignPromotionService.objects
                .select_related(
                    "campaign",
                    "campaign__created_by",
                    "campaign__ngo",
                )
                .get(uuid=uuid)
            )

        except CampaignPromotionService.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Promotion service not found.",
                },
                status=404,
            )

        campaign = promotion_service.campaign

        # =========================================================
        # 2. SERVICE TYPE
        # =========================================================

        service_type = promotion_service.service_type

        if hasattr(service_type, "value"):
            service_type_value = service_type.value
        else:
            service_type_value = str(service_type)

        # service_name if your enum contains it
        service_name = getattr(
            service_type,
            "service_name",
            service_type_value,
        )

        # =========================================================
        # 3. PROMOTION STATUS
        # =========================================================

        promotion_status = promotion_service.promotion_status

        if hasattr(promotion_status, "value"):
            promotion_status_value = promotion_status.value
        else:
            promotion_status_value = str(promotion_status)

        # =========================================================
        # 4. CAMPAIGN TYPE
        # =========================================================

        campaign_type = campaign.campaign_type

        if hasattr(campaign_type, "value"):
            campaign_type_value = campaign_type.value
        else:
            campaign_type_value = str(campaign_type)

        # =========================================================
        # 5. CAMPAIGN STATUS
        # =========================================================

        campaign_status = campaign.campaign_status

        if hasattr(campaign_status, "value"):
            campaign_status_value = campaign_status.value
        else:
            campaign_status_value = str(campaign_status)

        # =========================================================
        # 6. CREATED BY
        # =========================================================

        created_by = campaign.created_by

        creator_data = {
            "uuid": str(created_by.uuid),
            "fullname": created_by.fullname,
            "email": created_by.email,
            "mobile": created_by.mobile,
        }

        # =========================================================
        # 7. NGO DETAILS
        # =========================================================

        ngo_data = None

        if campaign.ngo:

            ngo_data = {
                "uuid": str(campaign.ngo.uuid),
                "name": getattr(
                    campaign.ngo,
                    "ngo_name",
                    None,
                ),
            }

        # =========================================================
        # 8. CAMPAIGN DETAILS
        # =========================================================

        campaign_data = {

            "uuid": str(campaign.uuid),

            "campaign_name": campaign.campaign_name,

            "campaign_slug": campaign.campaign_slug,

            "campaign_description": campaign.campaign_desc,

            "cover_photo": (
                request.build_absolute_uri(
                    campaign.cover_photo.url
                )
                if campaign.cover_photo
                else None
            ),

            "campaign_type": campaign_type_value,

            "campaign_status": campaign_status_value,

            "goal_amount": str(
                campaign.goal_amount
            ),

            "raised_amount": str(
                campaign.raised_amount
            ),



            "amount_withdrawn": str(
                campaign.amount_withdrawn
            ),

            "total_donors": campaign.total_donors,

            "total_views": campaign.total_views,

            "start_date": campaign.start_date,

            "end_date": campaign.end_date,

            "cause": (
                campaign.cause.value
                if hasattr(campaign.cause, "value")
                else str(campaign.cause)
            ),

            "beneficiary_type": (
                campaign.beneficiary_type.value
                if hasattr(
                    campaign.beneficiary_type,
                    "value",
                )
                else str(campaign.beneficiary_type)
            ),

            "beneficiary_group_type": (
                campaign.beneficiary_group_type.value
                if hasattr(
                    campaign.beneficiary_group_type,
                    "value",
                )
                else str(
                    campaign.beneficiary_group_type
                )
            ),

            "beneficiary_name": campaign.beneficiary_name,

            "beneficiary_relation": (
                campaign.beneficiary_relation.value
                if campaign.beneficiary_relation
                and hasattr(
                    campaign.beneficiary_relation,
                    "value",
                )
                else (
                    str(campaign.beneficiary_relation)
                    if campaign.beneficiary_relation
                    else None
                )
            ),

            "beneficiary_mobile": (
                campaign.beneficiary_mobile
            ),

            "beneficiary_member_count": (
                campaign.beneficiary_member_count
            ),

            "beneficiary_location": (
                campaign.beneficiary_location
            ),

            "beneficiary_age": (
                campaign.beneficiary_age
            ),

            "hospital_name": (
                campaign.hospital_name
            ),

            "hospital_location": (
                campaign.hospital_location
            ),

            "ailment": campaign.ailment,

            "created_at": campaign.created_at,

            "updated_at": campaign.updated_at,

            "created_by": creator_data,

            "ngo": ngo_data,
        }

        # =========================================================
        # 9. PROMOTION SERVICE DETAILS
        # =========================================================

        amount = Decimal(
            promotion_service.amount or 0
        )

        fee = Decimal(
            promotion_service.fee or 0
        )

        tax = Decimal(
            promotion_service.tax or 0
        )

        total = amount + fee + tax

        promotion_data = {

            "uuid": str(
                promotion_service.uuid
            ),

            "service_type": service_type_value,

            "service_name": service_name,

            "amount": str(amount),

            "fee": str(fee),

            "tax": str(tax),

            "total": str(total),

            "currency": (
                promotion_service.currency.value
                if hasattr(
                    promotion_service.currency,
                    "value",
                )
                else str(
                    promotion_service.currency
                )
            ),

            "promotion_status": (
                promotion_status_value
            ),

            "user_notes": (
                promotion_service.user_notes
            ),

            "created_at": (
                promotion_service.created_at
            ),

            "updated_at": (
                promotion_service.updated_at
            ),
        }

        # =========================================================
        # 10. RESPONSE
        # =========================================================

        return Response(
            {
                "success": True,

                "message": (
                    "Promotion service details "
                    "fetched successfully."
                ),

                "promotion_service": promotion_data,

                "campaign": campaign_data,
            },
            status=200,
        )

    except Exception as e:

        return Response(
            {
                "success": False,

                "message": (
                    "Failed to fetch promotion "
                    "service details."
                ),

                "error": str(e),
            },
            status=500,
        )


# =============================================================
# UPDATE PROMOTION SERVICE STATUS
# =============================================================

@api_view(["PATCH"])
@permission_classes([IsPlatformAdmin])
@transaction.atomic
def update_promotion_service_status(request, uuid):

    try:

        # =========================================================
        # 1. GET PROMOTION SERVICE
        # =========================================================

        try:

            promotion_service = (
                CampaignPromotionService.objects
                .select_for_update()
                .select_related("campaign")
                .get(uuid=uuid)
            )

        except CampaignPromotionService.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Promotion service not found.",
                },
                status=404,
            )

        # =========================================================
        # 2. GET NEW STATUS
        # =========================================================

        requested_status = request.data.get("status")

        if not requested_status:

            return Response(
                {
                    "success": False,
                    "message": "status is required.",
                },
                status=400,
            )

        requested_status = (
            str(requested_status)
            .strip()
            .lower()
        )

        # =========================================================
        # 3. ALLOWED STATUS VALUES
        # =========================================================
        #
        # Pending is intentionally NOT present.
        #

        allowed_statuses = {

            "submitted": PromotionStatus.SUBMITTED,

            "active": PromotionStatus.ACTIVE,

            "completed": PromotionStatus.COMPLETED,
        }

        if requested_status not in allowed_statuses:

            return Response(
                {
                    "success": False,

                    "message": (
                        "Invalid status. Allowed values are "
                        "Submitted, Active, and Completed. "
                        "Pending cannot be selected."
                    ),
                },
                status=400,
            )

        new_status = allowed_statuses[
            requested_status
        ]

        # =========================================================
        # 4. CURRENT STATUS
        # =========================================================

        current_status = (
            promotion_service.promotion_status
        )

        if hasattr(
            current_status,
            "value",
        ):
            current_status_value = (
                current_status.value
            )
        else:
            current_status_value = str(
                current_status
            )

        current_status_lower = (
            current_status_value.lower()
        )

        # =========================================================
        # 5. PENDING CANNOT BE UPDATED
        # =========================================================

        if (
            current_status_lower
            == PromotionStatus.PENDING.value.lower()
        ):

            return Response(
                {
                    "success": False,

                    "message": (
                        "A Pending promotion service "
                        "cannot be changed by admin."
                    ),
                },
                status=400,
            )

        # =========================================================
        # 6. CANCELLED CANNOT BE UPDATED
        # =========================================================

        if (
            current_status_lower
            == PromotionStatus.CANCELLED.value.lower()
        ):

            return Response(
                {
                    "success": False,

                    "message": (
                        "Cancelled promotion services "
                        "cannot be changed."
                    ),
                },
                status=400,
            )

        # =========================================================
        # 7. SAME STATUS
        # =========================================================

        if current_status_lower == requested_status:

            return Response(
                {
                    "success": False,

                    "message": (
                        f"Promotion service is already "
                        f"{current_status_value}."
                    ),
                },
                status=400,
            )

        # =========================================================
        # 8. COMPLETED CANNOT GO BACK
        # =========================================================

    

        # =========================================================
        # 9. VALID TRANSITIONS
        # =========================================================
        #
        # Submitted -> Active
        # Submitted -> Completed
        # Active    -> Submitted
        # Active    -> Completed
        #

        valid_transitions = {

            "submitted": {
                "active",
                "completed",
            },

            "active": {
                "submitted",
                "completed",
            },
            
            "completed":{
                "active",
                "submitted",
            }
        }

        allowed_next_statuses = valid_transitions.get(
            current_status_lower,
            set(),
        )

        if requested_status not in allowed_next_statuses:

            return Response(
                {
                    "success": False,

                    "message": (
                        f"Cannot change promotion service "
                        f"status from {current_status_value} "
                        f"to {new_status.value}."
                    ),
                },
                status=400,
            )

        # =========================================================
        # 10. UPDATE
        # =========================================================

        promotion_service.promotion_status = (
            new_status
        )

        promotion_service.save(
            update_fields=[
                "promotion_status",
                "updated_at",
            ]
        )

        # =========================================================
        # 11. RESPONSE
        # =========================================================

        return Response(
            {
                "success": True,

                "message": (
                    "Promotion service status "
                    "updated successfully."
                ),

                "promotion_service": {

                    "uuid": str(
                        promotion_service.uuid
                    ),

                    "previous_status": (
                        current_status_value
                    ),

                    "new_status": (
                        new_status.value
                    ),
                },
            },
            status=200,
        )

    except Exception as e:

        return Response(
            {
                "success": False,

                "message": (
                    "Failed to update promotion "
                    "service status."
                ),

                "error": str(e),
            },
            status=500,
        )

@api_view(["POST"])
@permission_classes([IsSuperAdmin])
def create_admin(request):

    serializer = CreateAdminSerializer(data=request.data)

    if serializer.is_valid():

        admin = serializer.save()

        return Response(
            {
                "success": True,
                "message": "Admin created successfully.",
                "data": {
                    "uuid": str(admin.uuid),
                    "fullname": admin.fullname,
                    "email": admin.email,
                    "mobile": admin.mobile,
                    "user_type": admin.user_type.value,
                    "status": admin.status.value,
                },
            },
            status=status.HTTP_201_CREATED,
        )

    return Response(
        {
            "success": False,
            "errors": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST,
    )


@api_view(["DELETE"])
@permission_classes([IsSuperAdmin])
@transaction.atomic
def delete_admin(request, admin_uuid):

    try:
        print("Deleting admin with UUID:", admin_uuid)
        admin = CustomUser.objects.get(
            uuid=admin_uuid,
            user_type=UserType.ADMIN,
        )

        # Prevent deleting yourself
        if admin.uuid == request.user.uuid:
            return Response(
                {
                    "success": False,
                    "message": "You cannot delete your own account.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Soft delete
        admin.status = Status.DELETED
        admin.is_active = False

        # If your model has this field
        if hasattr(admin, "is_deleted"):
            admin.is_deleted = True

        admin.save()

        return Response(
            {
                "success": True,
                "message": "Admin deleted successfully.",
            }
        )

    except CustomUser.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Admin not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as e:

        return Response(
            {
                "success": False,
                "message": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
