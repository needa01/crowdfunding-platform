
from rest_framework import serializers

from verification.models import Document


class UploadProfileDocumentSerializer(serializers.ModelSerializer):
    document_type = serializers.CharField()

    class Meta:
        model = Document
        fields = [
            "document_type",
            "document_holder_name",
            "document_number",
            "file_url",
        ]


class CampaignDocumentSerializer(serializers.ModelSerializer):

    document_type = serializers.CharField(source="document_type.name", read_only=True)

    class Meta:
        model = Document
        fields = [
            "uuid",
            "document_type",
            "document_holder_name",
            "document_number",
            "file_url",
            "verification_status",
            "verification_remarks",
            "created_at",
        ]