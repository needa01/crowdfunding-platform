from django.shortcuts import get_object_or_404, render
from django.db.models import F
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from django.core.paginator import Paginator
from django.db.models import OuterRef, Subquery
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from campaigns.models import Campaign
from campaigns.serializers import (
    CampaignDetailSerializer,
    CampaignListSerializer,
    MyCampaignDetailSerializer,
    MyCampaignListSerializer,
)
from crowdfunding.enums import (
    BeneficiaryGroupType,
    BeneficiaryType,
    CampaignCause,
    CampaignStatus,
    CampaignType,
    DonationStatus,
    KYC_Status,
    UserType,
    VerificationStatus,
    VerificationType,
)
from django.utils import timezone
from django.core.exceptions import ValidationError
from crowdfunding.permissions import IsCampaignCreator
from donations.models import Donation
from organizations.models import NGOProfile
from verification.models import EntityVerificationRequest


@api_view(["GET"])
@authentication_classes([JWTAuthentication])
@permission_classes([AllowAny])
def campaign_list(request):
    """
    Campaign Listing API

    Anonymous Users
        -> Crowdfunding campaigns

    CSR Users
        -> CSR campaigns

    Donor / NGO / Individual Fundraiser /
    Admin / Super Admin
        -> Crowdfunding campaigns

    Conditions:
        - ACTIVE campaign
        - APPROVED verification
        - Goal not reached
    """

    # Default campaign type for guests
    campaign_type = CampaignType.CROWDFUNDING

    if request.user.is_authenticated:
        if request.user.user_type == UserType.CSR:
            campaign_type = CampaignType.CSR

    queryset = (
        Campaign.objects.filter(
            campaign_status=CampaignStatus.ACTIVE,
            campaign_type=campaign_type,
            verification_requests__verification_type=VerificationType.CAMPAIGN,
            verification_requests__status=VerificationStatus.APPROVED,
            end_date__gte=timezone.now().date(),
        )
        .filter(raised_amount__lt=F("goal_amount"))
        .select_related(
            "created_by",
            "ngo",
        )
        .distinct()
        .order_by(
            "-is_featured",
            "-created_at",
        )
    )

    serializer = CampaignListSerializer(
        queryset,
        many=True,
        context={
            "request": request,
        },
    )

    return Response(
        {
            "success": True,
            "campaign_type": (
                campaign_type.value
                if hasattr(campaign_type, "value")
                else str(campaign_type)
            ),
            "count": queryset.count(),
            "campaigns": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
def create_campaign(request):

    user = request.user

    # --------------------------------------------------
    # Only Individual Fundraiser and NGO can create campaigns
    # --------------------------------------------------
    if user.user_type not in (
        UserType.INDIVIDUAL_FUNDRAISER,
        UserType.NGO,
    ):
        return Response(
            {
                "success": False,
                "message": "You are not allowed to create campaigns.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # --------------------------------------------------
    # Profile verification
    # --------------------------------------------------
    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    if verification is None:
        return Response(
            {
                "success": False,
                "message": "Please complete profile verification before creating a campaign.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if verification.status == VerificationStatus.PENDING:
        return Response(
            {
                "success": False,
                "message": "Your verification request is pending.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if verification.status == VerificationStatus.REJECTED:
        return Response(
            {
                "success": False,
                "message": "Your verification request was rejected. Please resubmit your documents.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if verification.status != VerificationStatus.APPROVED:
        return Response(
            {
                "success": False,
                "message": "Your profile is not verified.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # --------------------------------------------------
    # Campaign Type
    # --------------------------------------------------

    if user.user_type == UserType.INDIVIDUAL_FUNDRAISER:

        campaign_type = CampaignType.CROWDFUNDING
        ngo = None

    else:

        campaign_type = request.data.get("campaign_type")

        if not campaign_type:
            return Response(
                {
                    "success": False,
                    "message": "campaign_type is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            campaign_type = CampaignType(campaign_type)
        except ValueError:
            return Response(
                {
                    "success": False,
                    "message": "Invalid campaign type.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if campaign_type not in (
            CampaignType.CROWDFUNDING,
            CampaignType.CSR,
        ):
            return Response(
                {
                    "success": False,
                    "message": "NGOs can only create Crowdfunding or CSR campaigns.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ngo = get_object_or_404(NGOProfile, user=user)

    # --------------------------------------------------
    # Validate Cause
    # --------------------------------------------------

    crowdfunding_causes = {
        CampaignCause.MEDICAL,
        CampaignCause.EDUCATION,
        CampaignCause.MEMORIAL,
        CampaignCause.CHILDREN,
        CampaignCause.WOMEN_EMPOWERMENT,
        CampaignCause.ANIMAL_WELFARE,
        CampaignCause.OTHERS,
    }

    csr_causes = {
        CampaignCause.COMMUNITY_DEVELOPMENT,
        CampaignCause.DISASTER_RELIEF,
        CampaignCause.ENVIRONMENT,
        CampaignCause.EDUCATION,
        CampaignCause.CHILDREN,
        CampaignCause.WOMEN_EMPOWERMENT,
        CampaignCause.ANIMAL_WELFARE,
        CampaignCause.HEALTHCARE,
        CampaignCause.LIVELIHOOD_SKILL_DEVELOPMENT,
        CampaignCause.OTHERS,
    }

    cause = request.data.get("cause")

    if not cause:
        return Response(
            {
                "success": False,
                "message": "Cause is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        cause = CampaignCause(cause)
    except ValueError:
        return Response(
            {
                "success": False,
                "message": "Invalid cause.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if campaign_type == CampaignType.CROWDFUNDING and cause not in crowdfunding_causes:
        return Response(
            {
                "success": False,
                "message": "Selected cause is not allowed for Crowdfunding campaigns.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if campaign_type == CampaignType.CSR and cause not in csr_causes:
        return Response(
            {
                "success": False,
                "message": "Selected cause is not allowed for CSR campaigns.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Build campaign data
    # --------------------------------------------------

    campaign_data = {
        "created_by": user,
        "ngo": ngo,
        "campaign_type": campaign_type,
        "campaign_name": request.data.get("campaign_name"),
        "campaign_desc": request.data.get("campaign_desc"),
        "cover_photo": request.FILES.get("cover_photo"),
        "goal_amount": request.data.get("goal_amount"),
        "cause": cause,
        "beneficiary_type": request.data.get("beneficiary_type"),
        "start_date": request.data.get("start_date"),
        "end_date": request.data.get("end_date"),
    }

    beneficiary_type = request.data.get("beneficiary_type")

    if beneficiary_type != BeneficiaryType.ME.value:

        campaign_data["beneficiary_group_type"] = request.data.get(
            "beneficiary_group_type"
        )

        campaign_data["beneficiary_name"] = request.data.get("beneficiary_name")

        campaign_data["beneficiary_mobile"] = request.data.get("beneficiary_mobile")

        campaign_data["beneficiary_location"] = request.data.get("beneficiary_location")

        member_count = request.data.get("beneficiary_member_count")

        campaign_data["beneficiary_member_count"] = (
            int(member_count) if member_count not in (None, "") else None
        )

        age = request.data.get("beneficiary_age")

        campaign_data["beneficiary_age"] = int(age) if age not in (None, "") else None

        if user.user_type == UserType.INDIVIDUAL_FUNDRAISER:
            campaign_data["beneficiary_relation"] = request.data.get(
                "beneficiary_relation"
            )

    # --------------------------------------------------
    # Medical fields
    # --------------------------------------------------

    if cause == CampaignCause.MEDICAL:

        campaign_data["hospital_name"] = request.data.get("hospital_name")

        campaign_data["hospital_location"] = request.data.get("hospital_location")

        campaign_data["ailment"] = request.data.get("ailment")

    # --------------------------------------------------
    # Create Campaign
    # --------------------------------------------------

    try:
        print(campaign_data)
        campaign = Campaign.objects.create(**campaign_data)

    except ValidationError as e:

        return Response(
            {
                "success": False,
                "errors": (
                    e.message_dict if hasattr(e, "message_dict") else e.messages
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:

        return Response(
            {
                "success": False,
                "message": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --------------------------------------------------
    # Success
    # --------------------------------------------------

    return Response(
        {
            "success": True,
            "message": "Campaign created successfully.",
            "data": {
                "campaign_name": campaign.campaign_name,
                "campaign_slug": campaign.campaign_slug,
                "campaign_type": campaign.campaign_type.value,
                "campaign_status": campaign.campaign_status.value,
                "created_at": campaign.created_at,
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
def update_campaign(request, campaign_slug):
    print("entered")
    campaign = get_object_or_404(
        Campaign,
        campaign_slug=campaign_slug,
        created_by=request.user,
        campaign_status=CampaignStatus.DRAFT,
    )
    print("exit")

    fields = [
        "campaign_name",
        "campaign_desc",
        "goal_amount",
        "cause",
        "beneficiary_type",
        "beneficiary_group_type",
        "beneficiary_name",
        "beneficiary_relation",
        "beneficiary_mobile",
        "beneficiary_age",
        "beneficiary_location",
        "beneficiary_member_count",
        "hospital_name",
        "hospital_location",
        "ailment",
        "start_date",
        "end_date",
    ]

    for field in fields:
        if field in request.data:
            setattr(campaign, field, request.data.get(field))

    if "cause" in request.data:
        campaign.cause = request.data["cause"]

    # Medical fields
    if campaign.cause == CampaignCause.MEDICAL:
        campaign.hospital_name = request.data.get("hospital_name")
        campaign.hospital_location = request.data.get("hospital_location")
        campaign.ailment = request.data.get("ailment")
    else:
        campaign.hospital_name = None
        campaign.hospital_location = None
        campaign.ailment = None

    for field in ["beneficiary_age", "beneficiary_member_count"]:
        if field in request.data:
            value = request.data.get(field)

            if value in ["", None]:
                setattr(campaign, field, None)
            else:
                setattr(campaign, field, int(value))

    # Cover photo
    if "cover_photo" in request.FILES:
        campaign.cover_photo = request.FILES["cover_photo"]

    campaign.save()

    return Response(
        {
            "success": True,
            "message": "Campaign updated successfully.",
            "data": {"campaign_slug": str(campaign.campaign_slug)},
        }
    )


@api_view(["GET"])
@permission_classes([IsCampaignCreator])
def get_my_campaigns(request):

    print("entered")
    verification_qs = EntityVerificationRequest.objects.filter(
        campaign=OuterRef("pk"),
        verification_type=VerificationType.CAMPAIGN,
    ).order_by("-created_at")

    campaigns = (
        Campaign.objects.filter(created_by=request.user)
        .annotate(
            verification_status=Subquery(verification_qs.values("status")[:1]),
            verification_remarks=Subquery(verification_qs.values("remarks")[:1]),
        )
        .order_by("-created_at")
    )
    print("campaigns", campaigns)
    serializer = MyCampaignListSerializer(campaigns, many=True)

    return Response(
        {
            "success": True,
            "count": campaigns.count(),
            "data": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def campaign_detail(request, campaign_slug):

    try:

        campaign = Campaign.objects.select_related(
            "created_by",
            "ngo",
        ).get(
            campaign_slug=campaign_slug,
            campaign_status__in=[
                CampaignStatus.ACTIVE,
                CampaignStatus.PAUSED,
                CampaignStatus.COMPLETED,
                CampaignStatus.CLOSED,
            ],
        )

    except Campaign.DoesNotExist:

        return Response(
            {"success": False, "message": "Campaign not found."},
            status=404,
        )

    Campaign.objects.filter(pk=campaign.pk).update(total_views=F("total_views") + 1)

    campaign.refresh_from_db()

    serializer = CampaignDetailSerializer(
        campaign,
        context={
            "request": request,
        },
    )

    return Response(
        {
            "success": True,
            "data": serializer.data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
def my_campaign_detail(request, campaign_slug):

    try:

        campaign = Campaign.objects.select_related(
            "created_by",
            "ngo",
        ).get(campaign_slug=campaign_slug)

    except Campaign.DoesNotExist:

        return Response(
            {"success": False, "message": "Campaign not found."},
            status=404,
        )

    serializer = MyCampaignDetailSerializer(
        campaign,
        context={
            "request": request,
        },
    )

    return Response(
        {
            "success": True,
            "data": serializer.data,
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def get_campaign_donations(request, campaign_slug):

    try:

        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        campaign = Campaign.objects.get(
            campaign_slug=campaign_slug,
            campaign_status__in=[
                CampaignStatus.ACTIVE,
                CampaignStatus.PAUSED,
                CampaignStatus.COMPLETED,
                CampaignStatus.CLOSED,
            ],
            is_deleted=False,
        )

        donations = (
            Donation.objects.filter(
                campaign=campaign,
                status=DonationStatus.SUCCESS,
            )
            .select_related(
                "donor",
                "donor__ngo_profile",
                "donor__csr_profile",
            )
            .order_by("-donated_at", "-created_at")
        )

        paginator = Paginator(donations, page_size)
        page_obj = paginator.get_page(page)

        data = []

        for donation in page_obj:

            if donation.is_anonymous:

                donor_name = "Anonymous"

            else:

                donor = donation.donor

                if donor.user_type == UserType.NGO:

                    donor_name = (
                        donor.ngo_profile.ngo_name
                        if hasattr(donor, "ngo_profile")
                        else donor.fullname
                    )

                elif donor.user_type == UserType.CSR:

                    donor_name = (
                        donor.csr_profile.csr_name
                        if hasattr(donor, "csr_profile")
                        else donor.fullname
                    )

                else:
                    # Donor / Individual Fundraiser / Others
                    donor_name = donor.fullname

            data.append(
                {
                    "donor_name": donor_name,
                    "amount": str(donation.amount),
                    "currency": donation.currency.value,
                    "message": donation.message or "",
                    "is_anonymous": donation.is_anonymous,
                    "donated_at": donation.donated_at,
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

    except Campaign.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
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
