from rest_framework import serializers

from accounts.models import CustomUser
from crowdfunding.enums import Status, UserType

class UsersKPISerializer(serializers.Serializer):
    total_users = serializers.IntegerField()
    individual_fundraisers = serializers.IntegerField()
    ngos = serializers.IntegerField()
    csrs = serializers.IntegerField()


class CampaignKPISerializer(serializers.Serializer):
    active = serializers.IntegerField()
    completed = serializers.IntegerField()
    pending_approval = serializers.IntegerField()
    rejected = serializers.IntegerField()

class DonationsKPISerializer(serializers.Serializer):
    total_donations = serializers.DecimalField(max_digits=10, decimal_places=2)
    donation_count = serializers.IntegerField()
    platform_donations = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_refund = serializers.DecimalField(max_digits=10, decimal_places=2)

class PaymentsKPISerializer(serializers.Serializer):
    pending_withdrawal_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_withdrawn = serializers.DecimalField(max_digits=10, decimal_places=2)
    failed_payments = serializers.IntegerField()
    total_campaign_service_amount = serializers.DecimalField(max_digits=10, decimal_places=2)

class PendingActionsSerializer(serializers.Serializer):
    individual_fundraisers = serializers.IntegerField()
    ngos = serializers.IntegerField()
    csrs = serializers.IntegerField()
    donors = serializers.IntegerField()
    campaigns = serializers.IntegerField()

class KPISerializer(serializers.Serializer):
    users = UsersKPISerializer()
    campaigns = CampaignKPISerializer()
    donations = DonationsKPISerializer()
    payments = PaymentsKPISerializer()
        
class DashboardSerializer(serializers.Serializer):
    kpis = KPISerializer()
    pending_actions = PendingActionsSerializer()


class CreateAdminSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    class Meta:
        model = CustomUser
        fields = [
            "fullname",
            "email",
            "mobile",
            "password",
        ]

    def validate_email(self, value):

        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Email already exists."
            )

        return value

    def validate_mobile(self, value):

        if CustomUser.objects.filter(mobile=value).exists():
            raise serializers.ValidationError(
                "Mobile already exists."
            )

        return value

    def create(self, validated_data):

        password = validated_data.pop("password")

        user = CustomUser.objects.create(
            **validated_data,
            username=validated_data["email"],
            user_type=UserType.ADMIN,
            status=Status.ACTIVE,
            is_active=True,
        )

        user.set_password(password)
        user.save()

        return user




