from rest_framework import serializers


class CreateDonationSerializer(serializers.Serializer):

    campaign_slug = serializers.SlugField()

    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    is_anonymous = serializers.BooleanField(
        default=False
    )

    message = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=300
    )