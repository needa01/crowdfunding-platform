from django.utils import timezone
from rest_framework import serializers

from campaigns.models import Campaign
from crowdfunding.enums import CampaignStatus
from verification.models import Document, EntityVerificationRequest

from .models import CampaignPromotionServiceTypes


class CampaignListSerializer(serializers.ModelSerializer):
    organizer = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    campaign_status = serializers.SerializerMethodField()
    percentage_raised = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "uuid",
            "campaign_slug",
            "campaign_name",
            "campaign_desc",
            "cover_photo",
            "campaign_type",
            "campaign_status",
            "cause",
            "goal_amount",
            "raised_amount",
            "percentage_raised",
            "total_donors",
            "total_views",
            "is_featured",
            "start_date",
            "end_date",
            "days_left",
            "organizer",
        ]

    def get_campaign_status(self, obj):
        if (
            obj.end_date
            and obj.end_date < timezone.localdate()
            and obj.campaign_status == CampaignStatus.ACTIVE
        ):
            return "Expired"

        return obj.campaign_status.value

    def get_cover_photo(self, obj):
        """
        Return absolute URL of campaign cover photo.
        """

        if not obj.cover_photo:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(obj.cover_photo.url)

        return obj.cover_photo.url

    def get_organizer(self, obj):
        """
        Return organizer name.
        NGO campaign -> NGO name
        Individual fundraiser -> User full name
        """

        if obj.ngo:
            # Change this if your NGO model uses another field
            return obj.ngo.ngo_name

        if obj.created_by:
            full_name = obj.created_by.get_full_name()

            if full_name:
                return full_name

            return obj.created_by.email

        return None

    def get_percentage_raised(self, obj):
        """
        Funding percentage.
        """

        if not obj.goal_amount or obj.goal_amount == 0:
            return 0

        percentage = (obj.raised_amount / obj.goal_amount) * 100

        return round(float(percentage), 2)

    def get_days_left(self, obj):
        """
        Remaining campaign days.
        """

        if not obj.end_date:
            return None

        today = timezone.now().date()

        days = (obj.end_date - today).days

        return max(days, 0)


class MyCampaignListSerializer(serializers.ModelSerializer):
    verification_status = serializers.SerializerMethodField()
    verification_remarks = serializers.CharField(read_only=True)
    campaign_status = serializers.SerializerMethodField()

    class Meta:
        model = Campaign
        fields = [
            "campaign_name",
            "campaign_desc",
            "campaign_slug",
            "cover_photo",
            "goal_amount",
            "raised_amount",
            "cause",
            "campaign_status",
            "beneficiary_name",
            "start_date",
            "end_date",
            "created_at",
            "verification_status",
            "verification_remarks",
        ]

    def get_campaign_status(self, obj):
        if (
            obj.end_date
            and obj.end_date < timezone.localdate()
            and obj.campaign_status == CampaignStatus.ACTIVE
        ):
            return "Expired"

        return obj.campaign_status.value

    def get_verification_status(self, obj):
        return obj.verification_status.value if obj.verification_status else None


class CampaignDocumentSerializer(serializers.ModelSerializer):
    document_url = serializers.SerializerMethodField()
    document_type = serializers.CharField(source="document_type.name", read_only=True)

    class Meta:
        model = Document
        fields = [
            "uuid",
            "document_type",
            "document_holder_name",
            "document_number",
            "document_url",
            "verification_status",
            "verification_remarks",
            "created_at",
        ]

    def get_document_url(self, obj):
        request = self.context.get("request")

        if obj.file_url:
            if request:
                return request.build_absolute_uri(obj.file_url.url)
            return obj.file_url.url

        return None


class CampaignVerificationSerializer(serializers.ModelSerializer):
    verified_by = serializers.SerializerMethodField()

    class Meta:
        model = EntityVerificationRequest
        fields = [
            "status",
            "verified_by",
            "reviewed_at",
            "remarks",
            "ai_score",
            "created_at",
        ]

    def get_verified_by(self, obj):
        if obj.reviewed_by:
            return {
                "uuid": str(obj.reviewed_by.uuid),
                "name": obj.reviewed_by.get_full_name()
                or obj.reviewed_by.username
                or obj.reviewed_by.email,
                "email": obj.reviewed_by.email,
            }
        return None


class CampaignCreatorSerializer(serializers.Serializer):
    fullname = serializers.CharField()
    email = serializers.EmailField()
    mobile = serializers.CharField()
    user_type = serializers.SerializerMethodField()
    profile_picture = serializers.SerializerMethodField()

    def get_profile_picture(self, obj):
        if not obj.profile_picture:
            return None

        request = self.context.get("request")

        if request:
            return request.build_absolute_uri(obj.profile_picture.url)

        return obj.profile_picture.url

    def get_user_type(self, obj):
        return obj.user_type.value


class NGODetailSerializer(serializers.Serializer):
    uuid = serializers.UUIDField()
    ngo_name = serializers.CharField()
    registration_number = serializers.CharField()
    email = serializers.EmailField()
    mobile = serializers.CharField()
    address = serializers.CharField()


class CampaignDetailSerializer(serializers.ModelSerializer):

    created_by = CampaignCreatorSerializer(read_only=True)
    ngo = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()
    progress_percentage = serializers.SerializerMethodField()
    amount_remaining = serializers.SerializerMethodField()
    campaign_status = serializers.SerializerMethodField()
    days_left = serializers.SerializerMethodField()
    wallet_balance = serializers.SerializerMethodField()
    documents = CampaignDocumentSerializer(
        many=True,
        read_only=True,
    )

    verification = serializers.SerializerMethodField()

    class Meta:
        model = Campaign

        fields = [
            "uuid",
            "campaign_slug",
            "campaign_name",
            "campaign_desc",
            "campaign_type",
            "campaign_status",
            "cause",
            "cover_photo",
            "goal_amount",
            "raised_amount",
            "wallet_balance",  # <-- Add here
            "progress_percentage",
            "amount_remaining",
            "total_charges",
            "amount_withdrawn",
            "beneficiary_type",
            "beneficiary_group_type",
            "beneficiary_name",
            "beneficiary_relation",
            "beneficiary_mobile",
            "beneficiary_member_count",
            "beneficiary_location",
            "beneficiary_age",
            "hospital_name",
            "hospital_location",
            "ailment",
            "total_donors",
            "total_views",
            "is_featured",
            "start_date",
            "end_date",
            "days_left",
            "created_at",
            "updated_at",
            "created_by",
            "ngo",
            "documents",
            "verification",
        ]

    def get_campaign_status(self, obj):
        if (
            obj.end_date
            and obj.end_date < timezone.localdate()
            and obj.campaign_status == CampaignStatus.ACTIVE
        ):
            return "Expired"

        return obj.campaign_status.value

    def get_verification(self, obj):
        verification = (
            obj.verification_requests.select_related("reviewed_by")
            .order_by("-created_at")
            .first()
        )

        if not verification:
            return None

        return CampaignVerificationSerializer(
            verification,
            context=self.context,
        ).data

    def get_cover_photo(self, obj):
        if obj.cover_photo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.cover_photo.url)
        return None

    def get_progress_percentage(self, obj):
        if obj.goal_amount == 0:
            return 0

        return round(
            (obj.raised_amount / obj.goal_amount) * 100,
            2,
        )

    def get_amount_remaining(self, obj):
        return obj.goal_amount - obj.raised_amount

    def get_days_left(self, obj):
        if obj.end_date:
            days = (obj.end_date - timezone.localdate()).days
            return max(days, 0)
        return None

    def get_ngo(self, obj):

        if not obj.ngo:
            return None

        ngo = obj.ngo
        user = ngo.user

        return {
            "uuid": str(ngo.uuid),
            "ngo_name": ngo.ngo_name,
            "registration_number": ngo.reg_num,
            "email": user.email,
            "mobile": user.mobile,
            "address": ngo.address,
            "city": ngo.city,
            "state": ngo.state,
            "country": ngo.country,
            "pincode": ngo.pincode,
            "website": ngo.website,
            "contact_person_name": ngo.contact_person_name,
            "contact_person_designation": ngo.contact_person_designation,
        }

    def get_wallet_balance(self, obj):
        if hasattr(obj, "wallet") and obj.wallet:
            return obj.wallet.balance

        return 0


class MyCampaignDetailSerializer(serializers.ModelSerializer):

    created_by = CampaignCreatorSerializer(read_only=True)

    ngo = serializers.SerializerMethodField()
    campaign_status = serializers.SerializerMethodField()
    cover_photo = serializers.SerializerMethodField()

    progress_percentage = serializers.SerializerMethodField()

    amount_remaining = serializers.SerializerMethodField()

    days_left = serializers.SerializerMethodField()

    documents = CampaignDocumentSerializer(
        many=True,
        read_only=True,
    )

    verification = serializers.SerializerMethodField()

    class Meta:
        model = Campaign

        fields = [
            "uuid",
            "campaign_slug",
            "campaign_name",
            "campaign_desc",
            "campaign_type",
            "campaign_status",
            "cause",
            "cover_photo",
            "goal_amount",
            "raised_amount",
            "progress_percentage",
            "amount_remaining",
            "total_charges",
            "amount_withdrawn",
            "beneficiary_type",
            "beneficiary_group_type",
            "beneficiary_name",
            "beneficiary_relation",
            "beneficiary_mobile",
            "beneficiary_member_count",
            "beneficiary_location",
            "beneficiary_age",
            "hospital_name",
            "hospital_location",
            "ailment",
            "total_donors",
            "total_views",
            "is_featured",
            "start_date",
            "end_date",
            "days_left",
            "created_at",
            "updated_at",
            "created_by",
            "ngo",
            "documents",
            "verification",
        ]

    def get_campaign_status(self, obj):
        if (
            obj.end_date
            and obj.end_date < timezone.localdate()
            and obj.campaign_status == CampaignStatus.ACTIVE
        ):
            return "Expired"

        return obj.campaign_status.value

    def get_verification(self, obj):
        verification = (
            obj.verification_requests.select_related("reviewed_by")
            .order_by("-created_at")
            .first()
        )

        if not verification:
            return None

        return CampaignVerificationSerializer(
            verification,
            context=self.context,
        ).data

    def get_cover_photo(self, obj):
        if obj.cover_photo:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.cover_photo.url)
        return None

    def get_progress_percentage(self, obj):
        if obj.goal_amount == 0:
            return 0

        return round(
            (obj.raised_amount / obj.goal_amount) * 100,
            2,
        )

    def get_amount_remaining(self, obj):
        return obj.goal_amount - obj.raised_amount

    def get_days_left(self, obj):
        if obj.end_date:
            days = (obj.end_date - timezone.localdate()).days
            return max(days, 0)
        return None

    def get_ngo(self, obj):

        if not obj.ngo:
            return None

        return {
            "uuid": obj.ngo.uuid,
            "ngo_name": obj.ngo.ngo_name,
            "registration_number": obj.ngo.reg_num,
            "email": obj.ngo.user.email,
            "mobile": obj.ngo.user.mobile,
            "address": obj.ngo.address,
        }


class CampaignPromotionServiceTypesSerializer(serializers.ModelSerializer):
    service_type = serializers.CharField(source="service_type.value")

    class Meta:
        model = CampaignPromotionServiceTypes
        fields = [
            "uuid",
            "service_type",
            "minimum_amount",
        ]
