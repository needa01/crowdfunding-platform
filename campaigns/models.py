from django.db import models

# Create your models here.
import datetime
import secrets
from ssl import Purpose
from decimal import Decimal
from django.db import models

import uuid

from django.utils import timezone
from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django_enum import EnumField
from crowdfunding.enums import (
    BeneficiaryGroupType,
    BeneficiaryRelation,
    BeneficiaryType,
    CampaignCause,
    CampaignStatus,
    CampaignType,
    KYC_Status,
    PromotionStatus,
    UserType,
    UserType,
    Currency,
    VerificationType,
    VerificationStatus,
)
from organizations.models import NGOProfile
from django.core.exceptions import ValidationError


# Razorpay platform/payment gateway fee percentage
RAZORPAY_FEE_PERCENTAGE = Decimal("2.00")

# GST percentage applicable to the Razorpay fee
GST_PERCENTAGE = Decimal("18.00")


class Campaign(models.Model):

    uuid = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaigns",
        null=False,
        blank=False,
    )

    campaign_type = EnumField(
        CampaignType,
        default=CampaignType.CROWDFUNDING,
    )

    ngo = models.ForeignKey(
        NGOProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )

    campaign_name = models.CharField(
        max_length=255,
    )

    campaign_slug = models.SlugField(
        unique=True,
        max_length=300,
    )

    campaign_desc = models.TextField()

    cover_photo = models.ImageField(
        upload_to="campaigns/covers/",
        null=True,
        blank=True,
    )

    goal_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
    )

    raised_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    total_charges = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    amount_withdrawn = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0,
    )

    beneficiary_type = EnumField(
        BeneficiaryType,
    )

    beneficiary_group_type = EnumField(
        BeneficiaryGroupType,
    )

    cause = EnumField(
        CampaignCause,
    )

    beneficiary_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    beneficiary_relation = EnumField(
        BeneficiaryRelation,
        null=True,
        blank=True,
    )

    beneficiary_mobile = models.CharField(
        max_length=15,
        null=True,
        blank=True,
    )

    beneficiary_member_count = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    beneficiary_location = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    beneficiary_age = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    hospital_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    hospital_location = models.CharField(
        max_length=255,
        null=True,
        blank=True,
    )

    ailment = models.TextField(
        null=True,
        blank=True,
    )

    campaign_status = EnumField(
        CampaignStatus,
        default=CampaignStatus.DRAFT,
    )

    total_donors = models.PositiveIntegerField(
        default=0,
    )

    total_views = models.PositiveIntegerField(
        default=0,
    )

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    end_date = models.DateField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    is_deleted = models.BooleanField(
        default=False,
    )

    class Meta:
        db_table = "campaign"
        verbose_name = "Campaign"
        verbose_name_plural = "Campaigns"

    def __str__(self):
        return self.campaign_name

    # =========================================================
    # CAMPAIGN VERIFICATION
    # =========================================================

    def is_verified(self):

        verification = self.verification_requests.filter(
            verification_type=VerificationType.CAMPAIGN
        ).first()

        return (
            verification is not None
            and verification.status == VerificationStatus.APPROVED
        )

    # =========================================================
    # MODEL VALIDATION
    # =========================================================

    def clean(self):

        # =====================================================
        # BASIC USER VALIDATION
        # =====================================================

        if self.created_by.user_type == UserType.DONOR:
            raise ValidationError(
                {"created_by": ("Donors cannot create campaigns.")}
            )
        
        # CSR users cannot create campaigns
        if self.created_by.user_type == UserType.CSR:
            raise ValidationError(
                {"created_by": ("CSR users cannot create campaigns.")}
            )

        # NGO users must have an NGO
        if self.created_by.user_type == UserType.NGO and not self.ngo:
            raise ValidationError(
                {"ngo": ("NGO users must be associated with an NGO.")}
            )

        # Individual fundraisers cannot have an NGO
        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER and self.ngo:
            raise ValidationError(
                {"ngo": ("Individual campaigns cannot be associated with an NGO.")}
            )

        # =====================================================
        # CSR CAMPAIGN VALIDATION
        # =====================================================

        if self.campaign_type == CampaignType.CSR:

            if not self.ngo:
                raise ValidationError(
                    {"ngo": ("CSR campaigns must be associated with an NGO.")}
                )

            if self.created_by.user_type != UserType.NGO:
                raise ValidationError(
                    {"created_by": ("CSR campaigns can only be created by NGO users.")}
                )

        # =====================================================
        # INDIVIDUAL FUNDRAISER VALIDATION
        # =====================================================

        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:

            # Individual fundraiser can only create
            # crowdfunding campaigns
            if self.campaign_type != CampaignType.CROWDFUNDING:
                raise ValidationError(
                    {
                        "campaign_type": (
                            "Individual fundraisers can create only crowdfunding campaigns."
                        )
                    }
                )

            # Individual fundraiser cannot select NGO
            if self.beneficiary_type == BeneficiaryType.NGO:
                raise ValidationError(
                    {
                        "beneficiary_type": (
                            "Individual fundraisers cannot choose NGO as the beneficiary."
                        )
                    }
                )

        # =====================================================
        # BENEFICIARY GROUP TYPE
        # =====================================================

        if self.beneficiary_group_type == BeneficiaryGroupType.INDIVIDUAL:

            # Individual beneficiary always has one member
            self.beneficiary_member_count = 1

        elif self.beneficiary_group_type == BeneficiaryGroupType.GROUP:

            if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:

                if not self.beneficiary_member_count:
                    raise ValidationError(
                        {
                            "beneficiary_member_count": "Member count is required for group beneficiaries."
                        }
                    )

                if self.beneficiary_member_count < 2:
                    raise ValidationError(
                        {
                            "beneficiary_member_count": "Group beneficiaries must have at least 2 members."
                        }
                    )

        today = timezone.localdate()
        minimum_start_date = today + datetime.timedelta(days=1)

        if self._state.adding:
            if not self.start_date:
                self.start_date = minimum_start_date

            elif self.start_date < minimum_start_date:
                raise ValidationError(
                    {"start_date": "Start date must be at least tomorrow."}
                )

        # --------------------------------------------
        # End Date Validation
        # --------------------------------------------
        if self.end_date:

            if self.end_date < self.start_date + datetime.timedelta(days=7):
                raise ValidationError(
                    {
                        "end_date": "Campaign must run for at least 7 days from the start date."
                    }
                )
        if self.cause == CampaignCause.MEDICAL:

            if not self.hospital_name:
                raise ValidationError({"hospital_name": "Hospital name is required."})

            if not self.hospital_location:
                raise ValidationError(
                    {"hospital_location": "Hospital location is required."}
                )

            if not self.ailment:
                raise ValidationError({"ailment": "Ailment is required."})

        else:
            self.hospital_name = None
            self.hospital_location = None
            self.ailment = None

        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:

            if self.campaign_type != CampaignType.CROWDFUNDING:
                raise ValidationError(
                    {
                        "campaign_type": "Individual fundraisers can only create crowdfunding campaigns."
                    }
                )

            if self.beneficiary_type == BeneficiaryType.ME:

                self.beneficiary_group_type = BeneficiaryGroupType.INDIVIDUAL

                self.beneficiary_relation = None

                self.beneficiary_name = self.created_by.fullname

                self.beneficiary_mobile = self.created_by.mobile

                profile = getattr(self.created_by, "individual_profile", None)

                if profile:
                    self.beneficiary_location = profile.address

                self.beneficiary_member_count = 1

        if self.created_by.user_type == UserType.NGO:

            # NGO cannot select "Me"
            if self.beneficiary_type == BeneficiaryType.ME:
                raise ValidationError({"beneficiary_type": "NGOs cannot select Me."})

            if (
                self.campaign_type == CampaignType.CSR
                and self.beneficiary_type
                not in [
                    BeneficiaryType.NGO,
                    BeneficiaryType.OTHERS,
                    BeneficiaryType.COMMUNITY,
                    BeneficiaryType.INSTITUTION,
                ]
            ):
                raise ValidationError(
                    {
                        "beneficiary_type": "NGOs can only choose NGO, Others, Community, or Institution for CSR campaigns."
                    }
                )

            # -------------------------------------------------
            # NGO + CROWDFUNDING
            # -------------------------------------------------

            if (
                self.campaign_type == CampaignType.CROWDFUNDING
                and self.beneficiary_type
                not in [
                    BeneficiaryType.NGO,
                    BeneficiaryType.OTHERS,
                    BeneficiaryType.INDIVIDUAL,
                ]
            ):
                raise ValidationError(
                    {
                        "beneficiary_type": "NGOs can only choose NGO, Others, or Individual for Crowdfunding campaigns."
                    }
                )

            self.beneficiary_relation = None

        if self.created_by.user_type == UserType.NGO:
            self.beneficiary_relation = None

        # --------------------------------------------
        # Beneficiary Relation Validation
        # --------------------------------------------

        if self.beneficiary_type == BeneficiaryType.RELATIVE:

            # -------------------------------------------------
            # Relative MUST have a relation
            # -------------------------------------------------

            if not self.beneficiary_relation:
                raise ValidationError(
                    {
                        "beneficiary_relation": (
                            "Relation is required when beneficiary type is Relative."
                        )
                    }
                )

        else:

            # -------------------------------------------------
            # All other beneficiary types MUST NOT have a
            # beneficiary relation.
            #
            # IMPORTANT:
            # Do NOT silently set it to None.
            # Raise an error if the user supplied one.
            # -------------------------------------------------

            if self.beneficiary_relation is not None:
                raise ValidationError(
                    {
                        "beneficiary_relation": (
                            "Beneficiary relation is only allowed when beneficiary type is Relative."
                        )
                    }
                )

        # =====================================================
        # START DATE
        # =====================================================

        today = timezone.localdate()

        minimum_start_date = today + datetime.timedelta(days=1)

        if self._state.adding:

            if not self.start_date:
                self.start_date = minimum_start_date

            elif self.start_date < minimum_start_date:
                raise ValidationError(
                    {"start_date": ("Start date must be at least tomorrow.")}
                )

        # =====================================================
        # END DATE
        # =====================================================

        if self.end_date:

            if self.end_date < (self.start_date + datetime.timedelta(days=7)):
                raise ValidationError(
                    {
                        "end_date": (
                            "Campaign must run for at least "
                            "7 days from the start date."
                        )
                    }
                )

        # =====================================================
        # MEDICAL CAUSE
        # =====================================================

        if self.cause == CampaignCause.MEDICAL:

            if not self.hospital_name:
                raise ValidationError({"hospital_name": ("Hospital name is required.")})

            if not self.hospital_location:
                raise ValidationError(
                    {"hospital_location": ("Hospital location is required.")}
                )

            if not self.ailment:
                raise ValidationError({"ailment": ("Ailment is required.")})

        else:

            # Medical fields must be NULL for non-medical
            # campaigns.
            self.hospital_name = None
            self.hospital_location = None
            self.ailment = None

    # =========================================================
    # SAVE
    # =========================================================

    def save(self, *args, **kwargs):

        # =====================================================
        # INDIVIDUAL BENEFICIARY
        # =====================================================

        if self.beneficiary_group_type == BeneficiaryGroupType.INDIVIDUAL:
            self.beneficiary_member_count = 1

        # =====================================================
        # GROUP BENEFICIARY
        # =====================================================

        elif self.beneficiary_group_type == BeneficiaryGroupType.GROUP:

            # Age must ALWAYS be NULL for group beneficiaries.
            #
            # This is enforced here as well as in clean()
            # so that stale age data cannot remain when
            # changing an existing campaign from Individual
            # to Group.
            self.beneficiary_age = None

        # =====================================================
        # GENERATE CAMPAIGN SLUG
        # =====================================================

        if not self.campaign_slug:

            base_slug = slugify(self.campaign_name)

            while True:

                timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")

                # 6 random hexadecimal characters
                random_suffix = secrets.token_hex(3)

                slug = f"{base_slug}-" f"{timestamp}-" f"{random_suffix}"

                if not Campaign.objects.filter(campaign_slug=slug).exists():

                    self.campaign_slug = slug
                    break

        # =====================================================
        # INDIVIDUAL FUNDRAISER
        # =====================================================

        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:

            # Individual fundraisers can only create
            # crowdfunding campaigns.
            self.campaign_type = CampaignType.CROWDFUNDING

            if self.beneficiary_type == BeneficiaryType.ME:

                self.beneficiary_group_type = BeneficiaryGroupType.INDIVIDUAL

                self.beneficiary_member_count = 1

                self.beneficiary_relation = None

                self.beneficiary_name = self.created_by.fullname

                self.beneficiary_mobile = self.created_by.mobile

                profile = getattr(
                    self.created_by,
                    "individual_profile",
                    None,
                )

                if profile:
                    self.beneficiary_location = profile.address

        # =====================================================
        # NGO
        # =====================================================

        if self.created_by.user_type == UserType.NGO:

            # NGO campaigns do not have beneficiary relation
            self.beneficiary_relation = None

        # =====================================================
        # NON-MEDICAL CAMPAIGN
        # =====================================================

        if self.cause != CampaignCause.MEDICAL:

            self.hospital_name = None
            self.hospital_location = None
            self.ailment = None

        # =====================================================
        # GROUP AGE
        # =====================================================

        if self.beneficiary_group_type == BeneficiaryGroupType.GROUP:

            # Never store age for group beneficiaries.
            self.beneficiary_age = None

        # =====================================================
        # RELATION
        # =====================================================

        if self.beneficiary_type != BeneficiaryType.RELATIVE:

            # Only Relative can have a relation.
            #
            # OTHERS -> NULL
            # FRIEND  -> NULL
            # ME      -> NULL
            self.beneficiary_relation = None

        # =====================================================
        # MODEL VALIDATION
        # =====================================================

        self.full_clean()

        # =====================================================
        # DATABASE SAVE
        # =====================================================

        super().save(*args, **kwargs)


class CampaignPromotionServiceTypes(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    service_name = models.CharField(max_length=50)

    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campaign_promotion_services_type"
        verbose_name = "Campaign Promotion Services Type"
        verbose_name_plural = "Campaign Promotion Services Types"

    def __str__(self):
        return self.service_name


class CampaignPromotionService(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="services"
    )

    service_type = models.ForeignKey(
        CampaignPromotionServiceTypes,
        on_delete=models.PROTECT,
        related_name="campaign_promotions",
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    fee = models.DecimalField(max_digits=10, decimal_places=2)

    tax = models.DecimalField(max_digits=10, decimal_places=2)

    currency = EnumField(Currency, default=Currency.INR)

    promotion_status = EnumField(PromotionStatus, default=PromotionStatus.PENDING)

    user_notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campaign_promotion_service"
        verbose_name = "Campaign Promotion Service"
        verbose_name_plural = "Campaign Promotion Services"

    def __str__(self):
        return f"{self.campaign.campaign_name} ({self.service_type.service_name})"

    def clean(self):

        if self.campaign:

            # Only verified crowdfunding campaigns
            if self.campaign.campaign_type == CampaignType.CSR:
                raise ValidationError(
                    {
                        "campaign": (
                            "Promotional services are available only for crowdfunding campaigns."
                        )
                    }
                )

            # Campaign must be verified
            if not self.campaign.is_verified():
                raise ValidationError(
                    {
                        "campaign": (
                            "Promotional services are available only for verified campaigns."
                        )
                    }
                )

        # Amount must be positive
        if self.amount <= 0:
            raise ValidationError(
                {"amount": "Promotion amount must be greater than zero."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
