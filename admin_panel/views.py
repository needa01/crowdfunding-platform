from django.db import DatabaseError, transaction
from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from accounts.models import CustomUser, DonorProfile, IndividualProfile
from admin_panel.serializers import CreateAdminSerializer, DashboardSerializer
from campaigns.models import Campaign, CampaignPromotionService
from crowdfunding.enums import (
    CampaignStatus,
    CampaignCause,
    DocumentPurpose,
    DonationStatus,
    DonationType,
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
    if user.user_type not in [UserType.ADMIN, UserType.SUPER_ADMIN]:
        return Response(
            {
                "success": False,
                "error": "You are not authorized to access the admin portal.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

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
    try:
        user = request.user
        print("everything is okay")
        if user.user_type not in [UserType.ADMIN, UserType.SUPER_ADMIN]:
            return Response(
                {
                    "success": False,
                    "error": "You are not authorized to access the admin dashboard.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        print("everything is okay2")

        total_users = CustomUser.objects.exclude(
            user_type__in=[UserType.ADMIN, UserType.SUPER_ADMIN]
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
            Donation.objects.aggregate(total_amount=Sum("amount"))["total_amount"] or 0
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
        if request.user.user_type != UserType.SUPER_ADMIN:
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
                    "created_at": admin.created_at,
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
            "document_type",
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
                "created_at": user.created_at,
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
                    "verified_at": bank.verified_at,
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
                    "document_type": document.document_type.name,
                    "document_holder_name": document.document_holder_name,
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
                    "reviewed_at": document.reviewed_at,
                    "created_at": document.created_at,
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
                "reviewed_at": (verification.reviewed_at if verification else None),
                "created_at": (verification.created_at if verification else None),
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
            "document_type",
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
                "created_at": user.created_at,
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
                    "verified_at": bank.verified_at,
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
                    "document_type": document.document_type.name,
                    "document_holder_name": document.document_holder_name,
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
                    "reviewed_at": document.reviewed_at,
                    "created_at": document.created_at,
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
                "reviewed_at": (verification.reviewed_at if verification else None),
                "created_at": (verification.created_at if verification else None),
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
            "document_type",
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
                "created_at": user.created_at,
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
                    "created_at": profile.created_at,
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
                    "verified_at": bank.verified_at,
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
                    "document_type": document.document_type.name,
                    "document_holder_name": document.document_holder_name,
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
                    "reviewed_at": document.reviewed_at,
                    "created_at": document.created_at,
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
                "reviewed_at": (verification.reviewed_at if verification else None),
                "created_at": (verification.created_at if verification else None),
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
            "document_type",
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
                "created_at": user.created_at,
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
                    "created_at": profile.created_at,
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
                    "verified_at": bank.verified_at,
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
                    "document_type": document.document_type.name,
                    "document_holder_name": document.document_holder_name,
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
                    "reviewed_at": document.reviewed_at,
                    "created_at": document.created_at,
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
                "reviewed_at": (verification.reviewed_at if verification else None),
                "created_at": (verification.created_at if verification else None),
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

    verification = (
        EntityVerificationRequest.objects.select_related("reviewed_by")
        .filter(campaign=campaign)
        .order_by("-created_at")
        .first()
    )

    documents = (
        Document.objects.select_related(
            "document_type",
            "reviewed_by",
        )
        .filter(
            campaign=campaign,
            purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
        )
        .order_by("created_at")
    )
    profile = getattr(campaign.created_by, "individual_profile", None)
    ngo_profile = getattr(campaign.created_by, "ngo_profile", None)

    response = {
        "success": True,
        "message": "Campaign details fetched successfully.",
        "data": {
            # ---------------- Campaign ----------------
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
                    request.build_absolute_uri(campaign.cover_photo.url)
                    if campaign.cover_photo
                    else None
                ),
                "total_donors": campaign.total_donors,
                "total_views": campaign.total_views,
                "start_date": campaign.start_date,
                "end_date": campaign.end_date,
                "created_at": campaign.created_at,
            },
            # ---------------- Creator ----------------
            "creator": {
                "uuid": str(campaign.created_by.uuid),
                "fullname": campaign.created_by.fullname,
                "email": campaign.created_by.email,
                "mobile": campaign.created_by.mobile,
                "user_type": campaign.created_by.user_type.value,
                "profile_picture": (
                    request.build_absolute_uri(campaign.created_by.profile_picture.url)
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
                        "contact_person_name": ngo_profile.contact_person_name,
                        "contact_person_designation": ngo_profile.contact_person_designation,
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
            "ngo": (
                {
                    "uuid": str(campaign.ngo.uuid),
                    "ngo_name": campaign.ngo.ngo_name,
                    "ngo_type": campaign.ngo.ngo_type.value,
                    "registration_number": campaign.ngo.reg_num,
                    "contact_person_name": campaign.ngo.contact_person_name,
                    "contact_person_designation": campaign.ngo.contact_person_designation,
                    "address": campaign.ngo.address,
                    "city": campaign.ngo.city,
                    "state": campaign.ngo.state,
                    "country": campaign.ngo.country,
                    "pincode": campaign.ngo.pincode,
                    "website": campaign.ngo.website,
                    "created_at": campaign.ngo.created_at,
                }
                if campaign.ngo
                else None
            ),
            "medical_details": (
                (
                    {
                        "hospital_name": campaign.hospital_name,
                        "hospital_location": campaign.hospital_location,
                        "ailment": campaign.ailment,
                    }
                )
                if campaign.cause == CampaignCause.MEDICAL
                else None
            ),
            # ---------------- Beneficiary ----------------
            "beneficiary": {
                "beneficiary_type": campaign.beneficiary_type.value,
                "beneficiary_group_type": campaign.beneficiary_group_type.value,
                "beneficiary_name": campaign.beneficiary_name,
                "beneficiary_relation": (
                    campaign.beneficiary_relation.value
                    if campaign.beneficiary_relation
                    else None
                ),
                "beneficiary_mobile": campaign.beneficiary_mobile,
                "beneficiary_location": campaign.beneficiary_location,
                "beneficiary_member_count": campaign.beneficiary_member_count,
                "beneficiary_age": campaign.beneficiary_age,
            },
            # ---------------- Documents ----------------
            "documents": [
                {
                    "uuid": str(document.uuid),
                    "document_type": document.document_type.name,
                    "document_holder_name": document.document_holder_name,
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
                    "reviewed_at": document.reviewed_at,
                    "created_at": document.created_at,
                }
                for document in documents
            ],
            # ---------------- Verification Request ----------------
            "verification_request": {
                "uuid": str(verification.uuid) if verification else None,
                "verification_type": (
                    verification.verification_type.value if verification else None
                ),
                "status": (verification.status.value if verification else None),
                "ai_score": (verification.ai_result if verification else None),
                "remarks": (verification.remarks if verification else None),
                "reviewed_by": (
                    verification.reviewed_by.fullname
                    if verification and verification.reviewed_by
                    else None
                ),
                "reviewed_at": (verification.reviewed_at if verification else None),
                "created_at": (verification.created_at if verification else None),
            },
            "financials": {
                "goal_amount": campaign.goal_amount,
                "raised_amount": campaign.raised_amount,
                "total_charges": campaign.total_charges,
                "amount_withdrawn": campaign.amount_withdrawn,
            },
        },
    }

    return Response(
        response,
        status=status.HTTP_200_OK,
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
