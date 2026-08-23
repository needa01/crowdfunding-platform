from django.db import models

# Create your models here.
import datetime
import secrets
from ssl import Purpose

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
    ServiceType,
    UserType,
    UserType,
    Currency,
)
from organizations.models import NGOProfile
from django.core.exceptions import ValidationError


class Campaign(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaigns",
        null=False,
        blank=False,
    )

    campaign_type = EnumField(CampaignType, default=CampaignType.CROWDFUNDING)

    ngo = models.ForeignKey(
        NGOProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaigns",
    )

    campaign_name = models.CharField(max_length=255)

    campaign_slug = models.SlugField(unique=True, max_length=300)

    campaign_desc = models.TextField()

    cover_photo = models.ImageField(
        upload_to="campaigns/covers/", null=True, blank=True
    )

    goal_amount = models.DecimalField(max_digits=15, decimal_places=2)

    raised_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    total_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    amount_withdrawn = models.DecimalField(max_digits=15, decimal_places=2, default=0)

    beneficiary_type = EnumField(BeneficiaryType)

    beneficiary_group_type = EnumField(BeneficiaryGroupType)

    cause = EnumField(CampaignCause)

    beneficiary_name = models.CharField(max_length=255, null=True, blank=True)

    beneficiary_relation = EnumField(BeneficiaryRelation, null=True, blank=True)

    beneficiary_mobile = models.CharField(max_length=15, null=True, blank=True)

    beneficiary_member_count = models.PositiveIntegerField(null=True, blank=True)

    beneficiary_location = models.CharField(max_length=255, null=True, blank=True)

    beneficiary_age = models.PositiveIntegerField(null=True, blank=True)

    hospital_name = models.CharField(max_length=255, null=True, blank=True)

    hospital_location = models.CharField(max_length=255, null=True, blank=True)

    ailment = models.TextField(null=True, blank=True)

    campaign_status = EnumField(CampaignStatus, default=CampaignStatus.DRAFT)

    is_featured = models.BooleanField(default=False)

    total_donors = models.PositiveIntegerField(default=0)

    total_views = models.PositiveIntegerField(default=0)

    start_date = models.DateField(null=True, blank=True)

    end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = "campaign"

    def __str__(self):
        return self.campaign_name

    def clean(self):
        # CSR users cannot create campaigns
        if self.created_by.user_type == UserType.CSR:
            raise ValidationError({"created_by": "CSR users cannot create campaigns."})

        # If user type is ngo then ngo field must be set
        if self.created_by.user_type == UserType.NGO and not self.ngo:
            raise ValidationError({"ngo": "NGO users must be associated with an NGO."})

        # Individual campaign should not have NGO
        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER and self.ngo:
            raise ValidationError(
                {"ngo": "Individual campaigns cannot be associated with an NGO."}
            )

        if self.campaign_type == CampaignType.CSR:
            if not self.ngo:
                raise ValidationError(
                    {"ngo": "CSR campaigns must be associated with an NGO."}
                )
            if self.created_by.user_type != UserType.NGO:
                raise ValidationError(
                    {"created_by": "CSR campaigns can only be created by NGO users."}
                )

        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:
            if self.beneficiary_type == BeneficiaryType.NGO:
                raise ValidationError(
                    {
                        "beneficiary_type": "Individual fundraisers cannot choose NGO as the beneficiary."
                    }
                )

        if self.beneficiary_group_type == BeneficiaryGroupType.INDIVIDUAL:
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

            if not self.beneficiary_relation:
                raise ValidationError(
                    {
                        "beneficiary_relation": (
                            "Relation is required when beneficiary type is Relative."
                        )
                    }
                )

        else:
            # Relation is only applicable for Relative
            self.beneficiary_relation = None

    def save(self, *args, **kwargs):

        if self.beneficiary_group_type == BeneficiaryGroupType.INDIVIDUAL:
            self.beneficiary_member_count = 1

        # Generate slug only when creating the campaign
        if not self.campaign_slug:
            base_slug = slugify(self.campaign_name)

            while True:
                timestamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
                random_suffix = secrets.token_hex(3)  # 6 random hex characters

                slug = f"{base_slug}-{timestamp}-{random_suffix}"

                if not Campaign.objects.filter(campaign_slug=slug).exists():
                    self.campaign_slug = slug
                    break

        if self.created_by.user_type == UserType.INDIVIDUAL_FUNDRAISER:

            self.campaign_type = CampaignType.CROWDFUNDING

            if self.beneficiary_type == BeneficiaryType.ME:

                self.beneficiary_group_type = BeneficiaryGroupType.INDIVIDUAL

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

                self.beneficiary_member_count = 1

        if self.created_by.user_type == UserType.NGO:

            self.beneficiary_relation = None

        if self.cause != CampaignCause.MEDICAL:

            self.hospital_name = None
            self.hospital_location = None
            self.ailment = None
        print(self.cause)
        print(self.hospital_name)
        print(self.hospital_location)
        print(self.ailment)
        # Run model validations
        self.full_clean()

        super().save(*args, **kwargs)


class PromotionServicePricing(models.Model):

    service_type = EnumField(ServiceType, unique=True)

    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table="campaign_promotion_services_pricing"

class CampaignPromotionService(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    campaign = models.ForeignKey(
        Campaign, on_delete=models.CASCADE, related_name="services"
    )

    service_type = models.ForeignKey(
        PromotionServicePricing,
        on_delete=models.PROTECT,
        related_name="campaign_promotions"
    )

    amount = models.DecimalField(max_digits=10, decimal_places=2)

    currency = EnumField(Currency, default=Currency.INR)

    promotion_status = EnumField(PromotionStatus, default=PromotionStatus.PENDING)

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table="campaign_promotion_services"

    def clean(self):

        if self.campaign:

            # Only verified crowdfunding campaigns
            if self.campaign.campaign_type == CampaignType.CSR:
                raise ValidationError(
                    {
                        "campaign": (
                            "Promotional services are available only "
                            "for crowdfunding campaigns."
                        )
                    }
                )

            if self.campaign.campaign_status != CampaignStatus.VERIFIED:
                raise ValidationError(
                    {
                        "campaign": (
                            "Promotional services are available only "
                            "for verified campaigns."
                        )
                    }
                )

        # Amount must be positive
        if self.amount <= 0:
            raise ValidationError(
                {"amount": "Promotion amount must be greater than zero."}
            )

        # Date validation
        if self.start_date and self.end_date:
            if self.end_date <= self.start_date:
                raise ValidationError(
                    {"end_date": ("End date must be greater than start date.")}
                )

        overlapping = (
            CampaignPromotionService.objects.filter(
                campaign=self.campaign,
                service_type=self.service_type,
                promotion_status__in=[
                    PromotionStatus.PAID,
                    PromotionStatus.SCHEDULED,
                    PromotionStatus.ACTIVE,
                ],
            )
            .exclude(uuid=self.uuid)
            .filter(
                start_date__lt=self.end_date,
                end_date__gt=self.start_date,
            )
        )

        if overlapping.exists():
            raise ValidationError(
                {
                    "start_date": (
                        "This campaign already has an overlapping "
                        "promotion for this service."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
