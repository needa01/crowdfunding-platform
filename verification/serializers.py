
from rest_framework import serializers

from verification.models import Document


class UploadProfileDocumentSerializer(serializers.ModelSerializer):

    class Meta:
        model = Document
        fields = [
            "document_type",
            "document_number",
            "file_url",
        ]


class CampaignDocumentSerializer(serializers.ModelSerializer):


    class Meta:
        model = Document
        fields = [
            "uuid",
            "document_type",
            "document_number",
            "file_url",
            "verification_status",
            "verification_remarks",
            "created_at",
        ]