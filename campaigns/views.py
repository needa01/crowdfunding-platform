from django.shortcuts import get_object_or_404, render
from django.db.models import F, Prefetch
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    permission_classes,
    authentication_classes,
)
from decimal import ROUND_UP
from accounts.models import BankAccount
from campaigns.models import RAZORPAY_FEE_PERCENTAGE, GST_PERCENTAGE
from decimal import Decimal, InvalidOperation
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from campaigns.models import (
    Campaign,
    CampaignPromotionService,
)
from campaigns.serializers import (
    CampaignDetailSerializer,
    CampaignListSerializer,
    CampaignPromotionServiceTypesSerializer,
    MyCampaignDetailSerializer,
    MyCampaignListSerializer,
)
from crowdfunding.enums import (
    BeneficiaryType,
    CampaignCause,
    CampaignPromotionServiceType,
    CampaignStatus,
    CampaignType,
    DonationStatus,
    UserType,
    VerificationStatus,
    VerificationType,
    TransactionType,
    PaymentGateway,
    TransactionStatus,
    Currency,
    PromotionStatus,
    WalletTransactionType,
    WalletType,
    WithdrawalStatus,
)
from django.utils import timezone
from django.core.exceptions import ValidationError
from crowdfunding.permissions import IsCampaignCreator
from donations.models import Donation
from organizations.models import NGOProfile
from payments.models import (
    PaymentTransaction,
    PromotionServicePaymentTransaction,
    Withdrawal,
)
from verification.models import EntityVerificationRequest
import razorpay
from django.conf import settings

from wallets.models import Wallet

from decimal import Decimal

from django.db.models import Sum, Count, Q
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from campaigns.models import Campaign
from donations.models import Donation
from wallets.models import Wallet, WalletTransaction

razorpay_client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET,
    )
)


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
@transaction.atomic
def create_campaign(request):

    user = request.user
    print("user", request.user)

    # =========================================================
    # 1. ONLY INDIVIDUAL FUNDRAISER AND NGO CAN CREATE
    # =========================================================
    print(user.user_type)
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

    # =========================================================
    # 2. PROFILE VERIFICATION
    # =========================================================

    verification = (
        EntityVerificationRequest.objects.filter(user=user)
        .order_by("-created_at")
        .first()
    )

    if verification is None:
        return Response(
            {
                "success": False,
                "message": (
                    "Please complete profile verification before "
                    "creating a campaign."
                ),
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
                "message": (
                    "Your verification request was rejected. "
                    "Please resubmit your documents."
                ),
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

    # =========================================================
    # 3. CAMPAIGN TYPE
    # =========================================================
    print("here",user.user_type)
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
                    "message": (
                        "NGOs can only create Crowdfunding " "or CSR campaigns."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        ngo = get_object_or_404(
            NGOProfile,
            user=user,
        )

    # =========================================================
    # 4. VALIDATE CAUSE
    # =========================================================

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
                "message": (
                    "Selected cause is not allowed for " "Crowdfunding campaigns."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if campaign_type == CampaignType.CSR and cause not in csr_causes:
        return Response(
            {
                "success": False,
                "message": ("Selected cause is not allowed for " "CSR campaigns."),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 5. BENEFICIARY TYPE
    # =========================================================

    beneficiary_type = request.data.get("beneficiary_type")

    if not beneficiary_type:
        return Response(
            {
                "success": False,
                "message": "beneficiary_type is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 6. BENEFICIARY BANK ACCOUNT INPUT
    # =========================================================
    #
    # Bank account is created specifically for this campaign.
    #
    # user = None
    # campaign = newly created campaign
    #
    # =========================================================

    account_holder_name = request.data.get("account_holder_name")
    account_number = request.data.get("account_number")
    ifsc_code = request.data.get("ifsc_code")
    bank_name = request.data.get("bank_name")
    branch_name = request.data.get("branch_name")
    cancelled_cheque = request.FILES.get("cancelled_cheque")

    bank_required_fields = {
        "account_holder_name": account_holder_name,
        "account_number": account_number,
        "ifsc_code": ifsc_code,
        "bank_name": bank_name,
        "branch_name": branch_name,
        "cancelled_cheque": cancelled_cheque,
    }

    missing_bank_fields = [
        field for field, value in bank_required_fields.items() if value in (None, "")
    ]

    if missing_bank_fields:
        return Response(
            {
                "success": False,
                "message": "Bank account details are required.",
                "missing_fields": missing_bank_fields,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 7. BUILD CAMPAIGN DATA
    # =========================================================

    campaign_data = {
        "created_by": user,
        "ngo": ngo,
        "campaign_type": campaign_type,
        "campaign_name": request.data.get("campaign_name"),
        "campaign_desc": request.data.get("campaign_desc"),
        "cover_photo": request.FILES.get("cover_photo"),
        "goal_amount": request.data.get("goal_amount"),
        "cause": cause,
        "beneficiary_type": beneficiary_type,
        "start_date": request.data.get("start_date"),
        "end_date": request.data.get("end_date"),
    }

    # =========================================================
    # 8. BENEFICIARY DETAILS
    # =========================================================

    if beneficiary_type != BeneficiaryType.ME.value:

        campaign_data["beneficiary_group_type"] = request.data.get(
            "beneficiary_group_type"
        )

        campaign_data["beneficiary_name"] = request.data.get(
            "beneficiary_name"
        )

        campaign_data["beneficiary_mobile"] = request.data.get(
            "beneficiary_mobile"
        )

        campaign_data["beneficiary_location"] = request.data.get(
            "beneficiary_location"
        )

        # ---------------------------------------------------------
        # BENEFICIARY MEMBER COUNT
        # ---------------------------------------------------------

        member_count = request.data.get("beneficiary_member_count")

        if member_count not in (None, ""):
            try:
                campaign_data["beneficiary_member_count"] = int(member_count)
            except (TypeError, ValueError):
                return Response(
                    {
                        "success": False,
                        "message": (
                            "beneficiary_member_count must be a valid integer."
                        ),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            campaign_data["beneficiary_member_count"] = None

        # ---------------------------------------------------------
        # BENEFICIARY RELATION
        # ---------------------------------------------------------

        if user.user_type == UserType.INDIVIDUAL_FUNDRAISER:
            campaign_data["beneficiary_relation"] = request.data.get(
                "beneficiary_relation"
            )


    # =========================================================
    # BENEFICIARY AGE
    # =========================================================
    # Age must be handled for ALL beneficiary types,
    # including "ME".

    age = request.data.get("beneficiary_age")

    if age not in (None, ""):
        try:
            campaign_data["beneficiary_age"] = int(age)
        except (TypeError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "beneficiary_age must be a valid integer.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        campaign_data["beneficiary_age"] = None



    # =========================================================
    # 9. MEDICAL FIELDS
    # =========================================================

    if cause == CampaignCause.MEDICAL:

        campaign_data["hospital_name"] = request.data.get("hospital_name")

        campaign_data["hospital_location"] = request.data.get("hospital_location")

        campaign_data["ailment"] = request.data.get("ailment")

    # =========================================================
    # 10. CREATE CAMPAIGN
    # =========================================================

    try:

        print("campaign_data:", campaign_data)

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

    # =========================================================
    # 11. CREATE CAMPAIGN BENEFICIARY BANK ACCOUNT
    # =========================================================

    try:

        bank_account = BankAccount.objects.create(
            user=None,
            campaign=campaign,
            account_holder_name=account_holder_name,
            account_number=account_number,
            ifsc_code=ifsc_code,
            bank_name=bank_name,
            branch_name=branch_name,
            cancelled_cheque=cancelled_cheque,
        )

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
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 12. SUCCESS RESPONSE
    # =========================================================

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
                "bank_account": {
                    "uuid": str(bank_account.uuid),
                    "account_holder_name": (bank_account.account_holder_name),
                    "account_number": (bank_account.account_number),
                    "ifsc_code": bank_account.ifsc_code,
                    "bank_name": bank_account.bank_name,
                },
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsCampaignCreator])
@transaction.atomic
def create_campaign_promotion_payment(request):

    campaign_slug = request.data.get("campaign_slug")
    services_data = request.data.get("services")

    # =========================================================
    # 1. VALIDATE BASIC INPUT
    # =========================================================

    if not campaign_slug:
        return Response(
            {
                "success": False,
                "message": "campaign_slug is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not services_data:
        return Response(
            {
                "success": False,
                "message": "services is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not isinstance(services_data, list):
        return Response(
            {
                "success": False,
                "message": "services must be an array.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if len(services_data) == 0:
        return Response(
            {
                "success": False,
                "message": "At least one promotion service is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 2. GET CAMPAIGN
    # =========================================================

    try:
        campaign = Campaign.objects.get(campaign_slug=campaign_slug)
    except Campaign.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # =========================================================
    # 3. CHECK CAMPAIGN OWNER
    # =========================================================

    if campaign.created_by != request.user:
        return Response(
            {
                "success": False,
                "message": "You are not allowed to promote this campaign.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # 4. CHECK CAMPAIGN TYPE
    # =========================================================

    if campaign.campaign_type == CampaignType.CSR:
        return Response(
            {
                "success": False,
                "message": (
                    "Promotional services are available only "
                    "for crowdfunding campaigns."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 5. CHECK CAMPAIGN VERIFICATION
    # =========================================================

    verification = EntityVerificationRequest.objects.filter(
        campaign=campaign,
        verification_type=VerificationType.CAMPAIGN,
    ).first()

    if not verification or verification.status != VerificationStatus.APPROVED:
        return Response(
            {
                "success": False,
                "message": "Only verified campaigns can be promoted.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 6. VALIDATE SERVICES
    # =========================================================

    validated_services = []

    service_total = Decimal("0.00")

    # Get all allowed hard-coded promotion types
    allowed_service_types = {
        service_type.value for service_type in CampaignPromotionServiceType
    }

    for item in services_data:

        service_type = item.get("service_type")
        amount = item.get("amount")
        user_notes = item.get("user_notes", "")

        # -----------------------------------------------------
        # SERVICE TYPE REQUIRED
        # -----------------------------------------------------

        if not service_type:
            return Response(
                {
                    "success": False,
                    "message": ("service_type is required for every service."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # VALIDATE SERVICE TYPE
        # -----------------------------------------------------

        if service_type not in allowed_service_types:
            return Response(
                {
                    "success": False,
                    "message": (f"Invalid promotion service type: " f"{service_type}."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # AMOUNT REQUIRED
        # -----------------------------------------------------

        if amount is None:
            return Response(
                {
                    "success": False,
                    "message": (f"Amount is required for service " f"{service_type}."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # VALIDATE AMOUNT
        # -----------------------------------------------------

        try:
            amount = Decimal(str(amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):

            return Response(
                {
                    "success": False,
                    "message": (f"Invalid amount for service " f"{service_type}."),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if amount <= 0:
            return Response(
                {
                    "success": False,
                    "message": (
                        f"Amount for {service_type} " "must be greater than zero."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # -----------------------------------------------------
        # CONVERT STRING TO ENUM
        # -----------------------------------------------------

        promotion_service_type = CampaignPromotionServiceType(service_type)

        # -----------------------------------------------------
        # STORE SERVICE
        # -----------------------------------------------------

        validated_services.append(
            {
                "service_type": promotion_service_type,
                "amount": amount,
                "user_notes": user_notes,
            }
        )

        service_total += amount

    # =========================================================
    # 7. CALCULATE CUSTOMER PAYABLE AMOUNT
    #
    # Promotion budget = amount the service should receive
    #
    # Customer pays:
    #
    #     Promotion Budget
    #     + Razorpay Fee
    #     + GST on Razorpay Fee
    #
    # Fee = 2%
    # GST = 18%
    #
    # Since the fee is calculated on the final customer payment:
    #
    # total = budget / (1 - 0.02 - (0.02 * 0.18))
    #
    # denominator = 0.9764
    #
    # Example:
    #
    # ₹3000 / 0.9764 = ₹3072.511...
    #
    # Rounded according to the payment amount:
    # ₹3072.52
    # =========================================================

    fee_percentage = RAZORPAY_FEE_PERCENTAGE / Decimal("100")

    gst_percentage = GST_PERCENTAGE / Decimal("100")

    denominator = Decimal("1") - fee_percentage - (fee_percentage * gst_percentage)

    final_total = (service_total / denominator).quantize(
        Decimal("0.01"),
        rounding=ROUND_UP,
    )

    # =========================================================
    # 8. CALCULATE FEE AND GST FOR DISPLAY/STORAGE
    # =========================================================

    total_fee = (final_total * fee_percentage).quantize(
        Decimal("0.01"),
        rounding=ROUND_UP,
    )

    total_tax = (total_fee * gst_percentage).quantize(
        Decimal("0.01"),
        rounding=ROUND_UP,
    )

    # =========================================================
    # 9. CREATE PAYMENT TRANSACTION
    # =========================================================

    payment_transaction = PaymentTransaction.objects.create(
        transaction_type=TransactionType.CAMPAIGN_PROMOTION,
        amount=final_total,
        status=TransactionStatus.PENDING,
        gateway=PaymentGateway.RAZORPAY,
        currency=Currency.INR,
    )

    # =========================================================
    # 10. CREATE RAZORPAY ORDER
    # =========================================================

    try:

        razorpay_order = razorpay_client.order.create(
            {
                "amount": int(final_total * Decimal("100")),
                "currency": "INR",
                "receipt": str(payment_transaction.uuid),
            }
        )

    except Exception as exc:

        print(
            "RAZORPAY ORDER CREATION ERROR:",
            exc,
        )

        raise

    # =========================================================
    # 11. SAVE RAZORPAY ORDER ID
    # =========================================================

    payment_transaction.gateway_order_id = razorpay_order["id"]

    payment_transaction.save(
        update_fields=[
            "gateway_order_id",
        ]
    )

    # =========================================================
    # 12. CREATE PROMOTION SERVICE RECORDS
    #
    # Each service stores its original promotion budget.
    #
    # Fee and tax are distributed proportionally between
    # selected services.
    # =========================================================

    created_services = []

    for item in validated_services:

        service_amount = item["amount"]

        # Proportion of total promotion budget
        proportion = service_amount / service_total

        service_fee = (total_fee * proportion).quantize(
            Decimal("0.01"),
            rounding=ROUND_UP,
        )

        service_tax = (total_tax * proportion).quantize(
            Decimal("0.01"),
            rounding=ROUND_UP,
        )

        promotion_service = CampaignPromotionService.objects.create(
            campaign=campaign,
            service_type=item["service_type"],
            amount=service_amount,
            fee=service_fee,
            tax=service_tax,
            currency=Currency.INR,
            promotion_status=PromotionStatus.PENDING,
            user_notes=item["user_notes"],
        )

        created_services.append(promotion_service)

    # =========================================================
    # 13. LINK SERVICES TO PAYMENT TRANSACTION
    # =========================================================

    for service in created_services:

        PromotionServicePaymentTransaction.objects.create(
            payment_transaction=payment_transaction,
            promotion_service=service,
        )

    # =========================================================
    # 14. RESPONSE
    # =========================================================

    return Response(
        {
            "success": True,
            "message": "Promotion payment order created.",
            "data": {
                "transaction_uuid": str(payment_transaction.uuid),
                "razorpay_order_id": (razorpay_order["id"]),
                # Actual promotion budget
                "promotion_budget": service_total,
                # Fee charged to customer
                "razorpay_fee": total_fee,
                # GST on fee
                "gst": total_tax,
                # Actual amount customer pays
                "amount": final_total,
                "amount_in_paise": int(final_total * Decimal("100")),
                "currency": "INR",
                "razorpay_key_id": (settings.RAZORPAY_KEY_ID),
                "services": [
                    {
                        "promotion_service_uuid": str(service.uuid),
                        "service_type": (service.service_type.value),
                        "amount": service.amount,
                        "fee": service.fee,
                        "tax": service.tax,
                    }
                    for service in created_services
                ],
            },
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
@transaction.atomic
def update_campaign(request, campaign_slug):

    print("entered")

    campaign = get_object_or_404(
        Campaign,
        campaign_slug=campaign_slug,
        created_by=request.user,
        campaign_status=CampaignStatus.DRAFT,
    )

    print("exit")

    # =========================================================
    # 1. CAMPAIGN FIELDS
    # =========================================================

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
            setattr(
                campaign,
                field,
                request.data.get(field),
            )

    # =========================================================
    # 2. MEDICAL FIELDS
    # =========================================================

    if campaign.cause == CampaignCause.MEDICAL:

        campaign.hospital_name = request.data.get(
            "hospital_name"
        )

        campaign.hospital_location = request.data.get(
            "hospital_location"
        )

        campaign.ailment = request.data.get(
            "ailment"
        )

    else:

        campaign.hospital_name = None
        campaign.hospital_location = None
        campaign.ailment = None

    # =========================================================
    # 3. INTEGER FIELDS
    # =========================================================

    for field in [
        "beneficiary_age",
        "beneficiary_member_count",
    ]:

        if field in request.data:

            value = request.data.get(field)

            if value in ["", None]:

                setattr(
                    campaign,
                    field,
                    None,
                )

            else:

                try:
                    setattr(
                        campaign,
                        field,
                        int(value),
                    )

                except (TypeError, ValueError):

                    return Response(
                        {
                            "success": False,
                            "message": (
                                f"{field} must be a valid integer."
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

    # =========================================================
    # 4. COVER PHOTO
    # =========================================================

    if "cover_photo" in request.FILES:

        campaign.cover_photo = request.FILES[
            "cover_photo"
        ]

    # =========================================================
    # 5. UPDATE CAMPAIGN
    # =========================================================

    try:

        campaign.save()

    except ValidationError as e:

        return Response(
            {
                "success": False,
                "errors": (
                    e.message_dict
                    if hasattr(e, "message_dict")
                    else e.messages
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 6. CAMPAIGN BENEFICIARY BANK ACCOUNT
    # =========================================================

    bank_account = BankAccount.objects.filter(
        campaign=campaign
    ).first()

    if not bank_account:

        return Response(
            {
                "success": False,
                "message": (
                    "Beneficiary bank account was not found."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 7. UPDATE BANK ACCOUNT FIELDS
    # =========================================================

    bank_fields = [
        "account_holder_name",
        "account_number",
        "ifsc_code",
        "bank_name",
        "branch_name",
    ]

    for field in bank_fields:

        if field in request.data:

            value = request.data.get(field)

            if value not in [None, ""]:

                setattr(
                    bank_account,
                    field,
                    value,
                )

    # =========================================================
    # 8. CANCELLED CHEQUE
    # =========================================================

    if "cancelled_cheque" in request.FILES:

        bank_account.cancelled_cheque = request.FILES[
            "cancelled_cheque"
        ]

    # =========================================================
    # 9. SAVE BANK ACCOUNT
    # =========================================================

    try:

        bank_account.save()

    except ValidationError as e:

        return Response(
            {
                "success": False,
                "errors": (
                    e.message_dict
                    if hasattr(e, "message_dict")
                    else e.messages
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # =========================================================
    # 10. SUCCESS RESPONSE
    # =========================================================

    return Response(
        {
            "success": True,
            "message": "Campaign updated successfully.",
            "data": {
                "campaign_slug": str(
                    campaign.campaign_slug
                ),
                "bank_account": {
                    "uuid": str(
                        bank_account.uuid
                    ),
                    "account_holder_name": (
                        bank_account.account_holder_name
                    ),
                    "account_number": (
                        bank_account.account_number
                    ),
                    "ifsc_code": (
                        bank_account.ifsc_code
                    ),
                    "bank_name": (
                        bank_account.bank_name
                    ),
                    "branch_name": (
                        bank_account.branch_name
                    ),
                    "cancelled_cheque": (
                        bank_account.cancelled_cheque.url
                        if bank_account.cancelled_cheque
                        else None
                    ),
                },
            },
        },
        status=status.HTTP_200_OK,
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

        campaign = (
            Campaign.objects.select_related(
                "created_by",
                "ngo",
            )
            .prefetch_related(
                Prefetch(
                    "services",
                    queryset=CampaignPromotionService.objects.all().order_by(
                        "-created_at"
                    ),
                )
            )
            .get(
                campaign_slug=campaign_slug,
                created_by=request.user,
            )
        )

    except Campaign.DoesNotExist:

        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
            },
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
                    "donated_at": (
                        donation.donated_at.strftime("%d %b %Y, %I:%M %p")
                        if donation.donated_at
                        else None
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


@api_view(["GET"])
@permission_classes([AllowAny])
def get_promotion_services(request):

    services = [
        {
            "service_type": service_type.value,
        }
        for service_type in CampaignPromotionServiceType
    ]

    serializer = CampaignPromotionServiceTypesSerializer(services, many=True)

    return Response(
        {
            "success": True,
            "message": "Promotion services retrieved successfully.",
            "data": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_my_verified_campaigns(request):

    # 1. First get only my ACTIVE campaigns
    campaigns = Campaign.objects.filter(
        created_by=request.user,
        campaign_status=CampaignStatus.ACTIVE,
    ).order_by("-created_at")

    data = []

    # 2. Now check each campaign in EntityVerificationRequest
    for campaign in campaigns:

        verification = EntityVerificationRequest.objects.filter(
            campaign=campaign,
            verification_type=VerificationType.CAMPAIGN,
            status=VerificationStatus.APPROVED,
        ).first()

        # No verified request → don't show campaign
        if not verification:
            continue

        # 3. Get campaign wallet
        wallet = Wallet.objects.filter(
            campaign=campaign,
            wallet_type=WalletType.CAMPAIGN,
        ).first()

        data.append(
            {
                "campaign_name": campaign.campaign_name,
                "campaign_slug": campaign.campaign_slug,
                "cover_photo": (
                    request.build_absolute_uri(campaign.cover_photo.url)
                    if campaign.cover_photo
                    else None
                ),
                "wallet_balance": str(wallet.balance if wallet else Decimal("0.00")),
                "campaign_status": campaign.campaign_status.value,
                "is_verified": True,
            }
        )

    return Response(
        {
            "success": True,
            "data": data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def campaign_funds_detail(request, campaign_slug):

    # =========================================================
    # 1. GET CAMPAIGN
    # =========================================================

    campaign = get_object_or_404(Campaign, campaign_slug=campaign_slug)

    # =========================================================
    # 2. SECURITY CHECK
    # =========================================================

    if campaign.created_by != request.user:

        return Response(
            {
                "success": False,
                "message": ("You are not authorized to view " "these campaign funds."),
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # =========================================================
    # 3. CAMPAIGN VALUES
    # =========================================================

    goal_amount = campaign.goal_amount or Decimal("0.00")

    raised_amount = campaign.raised_amount or Decimal("0.00")

    remaining_amount = max(goal_amount - raised_amount, Decimal("0.00"))

    if goal_amount > 0:

        progress_percentage = (raised_amount / goal_amount) * Decimal("100")

        progress_percentage = min(progress_percentage, Decimal("100"))

    else:

        progress_percentage = Decimal("0.00")

    # =========================================================
    # 4. SUCCESSFUL PAYMENT TRANSACTIONS
    # =========================================================

    successful_payments = PaymentTransaction.objects.filter(
        donation__campaign=campaign, status=TransactionStatus.SUCCESS
    )

    # =========================================================
    # 5. GROSS AMOUNT RAISED
    # =========================================================

    gross_raised = successful_payments.aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")

    # =========================================================
    # 6. RAZORPAY FEES
    # =========================================================

    razorpay_fees = Decimal("0.00")
    razorpay_gst = Decimal("0.00")

    for payment in successful_payments:

        gateway_response = payment.gateway_response or {}

        fee_paise = gateway_response.get("fee", 0)
        tax_paise = gateway_response.get("tax", 0)

        total_fee_paise = Decimal(str(fee_paise)) + Decimal(str(tax_paise))

        razorpay_gst += Decimal(str(tax_paise)) / Decimal("100")

        razorpay_fees += total_fee_paise / Decimal("100")

    # =========================================================
    # 7. NET CAMPAIGN FUNDS
    # =========================================================

    net_campaign_funds = gross_raised - razorpay_fees

    # =========================================================
    # 10. GET CAMPAIGN WALLET
    # =========================================================

    wallet, _ = Wallet.objects.get_or_create(campaign=campaign)

    wallet_balance = wallet.balance or Decimal("0.00")

    # =========================================================
    # 11. WITHDRAWALS
    # =========================================================

    withdrawals = Withdrawal.objects.filter(campaign=campaign).order_by("-created_at")

    # ---------------------------------------------------------
    # Completed withdrawals
    # ---------------------------------------------------------

    completed_withdrawals = withdrawals.filter(status=WithdrawalStatus.PAID)

    # ---------------------------------------------------------
    # Pending / processing withdrawals
    # ---------------------------------------------------------

    pending_withdrawals = withdrawals.filter(
        status__in=[
            WithdrawalStatus.PENDING,
            WithdrawalStatus.APPROVED,
        ]
    )

    # ---------------------------------------------------------
    # Total withdrawn
    # ---------------------------------------------------------

    total_withdrawn = completed_withdrawals.aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")

    # ---------------------------------------------------------
    # Pending withdrawal amount
    # ---------------------------------------------------------

    pending_withdrawal_amount = pending_withdrawals.aggregate(total=Sum("amount"))[
        "total"
    ] or Decimal("0.00")

    # =========================================================
    # 12. AVAILABLE BALANCE
    # =========================================================

    # Wallet balance is the authoritative available balance.

    available_balance = wallet_balance

    # =========================================================
    # 13. TOTAL DONORS
    # =========================================================

    total_donors = (
        Donation.objects.filter(campaign=campaign, status=DonationStatus.SUCCESS)
        .values("donor")
        .distinct()
        .count()
    )

    # =========================================================
    # 14. WALLET TRANSACTIONS
    # =========================================================

    transactions = WalletTransaction.objects.filter(wallet=wallet).order_by(
        "-created_at"
    )

    wallet_transaction_data = []

    for transaction in transactions:

        wallet_transaction_data.append(
            {
                "uuid": str(transaction.uuid),
                "transaction_type": (
                    transaction.transaction_type.value
                    if transaction.transaction_type
                    else None
                ),
                "description": getattr(transaction, "description", ""),
                "credit": (
                    transaction.amount
                    if transaction.transaction_type == WalletTransactionType.CREDIT
                    else None
                ),
                "debit": str(
                    transaction.amount
                    if transaction.transaction_type == WalletTransactionType.DEBIT
                    else None
                ),
                "balance_after": str(
                    transaction.balance_after
                    if transaction.balance_after is not None
                    else Decimal("0.00")
                ),
                "created_at": transaction.created_at,
            }
        )

    # =========================================================
    # 15. WITHDRAWAL HISTORY
    # =========================================================

    withdrawal_data = []

    for withdrawal in withdrawals:

        withdrawal_data.append(
            {
                "uuid": str(withdrawal.uuid),
                "withdrawal_number": getattr(withdrawal, "withdrawal_number", None),
                "amount": str(
                    withdrawal.amount
                    if withdrawal.amount is not None
                    else Decimal("0.00")
                ),
                "status": withdrawal.status.value if withdrawal.status else None,
                "created_at": withdrawal.created_at,
                "processed_at": getattr(withdrawal, "processed_at", None),
                "failure_reason": getattr(withdrawal, "failure_reason", None),
            }
        )

    # =========================================================
    # 16. FINAL RESPONSE
    # =========================================================

    responseData = {
        "success": True,
        # =================================================
        # CAMPAIGN
        # =================================================
        "campaign": {
            "campaign_slug": (campaign.campaign_slug),
            "campaign_name": (campaign.campaign_name),
            "campaign_status": (campaign.campaign_status.value),
            "goal_amount": str(goal_amount),
            "raised_amount": str(raised_amount),
            "remaining_amount": str(remaining_amount),
            "progress_percentage": round(float(progress_percentage), 2),
            "total_donors": (total_donors),
        },
        # =================================================
        # FUNDS
        # =================================================
        "funds": {
            "gross_raised": str(gross_raised),
            "razorpay_fees": str(razorpay_fees - razorpay_gst),
            "razorpay_gst": str(razorpay_gst),
            "total_gateway_deduction": str(razorpay_fees),
            "net_campaign_funds": str(net_campaign_funds),
            "total_withdrawn": str(total_withdrawn),
            "pending_withdrawal_amount": str(pending_withdrawal_amount),
            "available_balance": str(available_balance),
        },
        # =================================================
        # WALLET TRANSACTIONS
        # =================================================
        "wallet_transactions": (wallet_transaction_data),
        # =================================================
        # WITHDRAWALS
        # =================================================
        "withdrawals": (withdrawal_data),
    }

    print("final response", responseData)
    return Response(responseData, status=status.HTTP_200_OK)
