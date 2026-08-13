from django.core.exceptions import ValidationError
from django.db import transaction

from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from accounts.models import BankAccount, CustomUser
from campaigns.models import Campaign

from django.db.models import Q

from wallets.models import Wallet
from .models import Document, DocumentType, EntityVerificationRequest
from .serializers import CampaignDocumentSerializer, UploadProfileDocumentSerializer
from crowdfunding.permissions import (
    CanEditProfile,
    CanManageDocuments,
    IsActiveAccount,
    IsCampaignCreator,
    IsPlatformAdmin,
)
from crowdfunding.enums import (
    CampaignStatus,
    Currency,
    DocumentPurpose,
    ProfileStatus,
    UserType,
    VerificationStatus,
    DocOwner,
    VerificationType,
    WalletType,
)


@api_view(["GET"])
@permission_classes([IsActiveAccount, CanManageDocuments])
def get_campaign_documents(request, campaign_uuid):

    documents = Document.objects.filter(campaign__uuid=campaign_uuid).select_related(
        "document_type"
    )

    data = []

    for doc in documents:
        data.append(
            {
                "uuid": str(doc.uuid),
                "document_type": doc.document_type.name,
                "document_holder_name": doc.document_holder_name,
                "document_number": doc.document_number,
                "file_url": (
                    request.build_absolute_uri(doc.file_url.url)
                    if doc.file_url
                    else None
                ),
                "verification_status": doc.verification_status.value,
            }
        )

    return Response({"success": True, "count": len(data), "documents": data})


@api_view(["GET"])
@permission_classes([IsActiveAccount])
def get_profile_documents(request):
    try:
        documents = Document.objects.filter(
            user=request.user, purpose=DocumentPurpose.PROFILE_VERIFICATION
        ).select_related("document_type")

        data = []

        for doc in documents:
            data.append(
                {
                    "uuid": str(doc.uuid),
                    "document_type": doc.document_type.name,
                    "document_holder_name": doc.document_holder_name,
                    "document_number": doc.document_number,
                    "file_url": (
                        request.build_absolute_uri(doc.file_url.url)
                        if doc.file_url
                        else None
                    ),
                    "verification_status": doc.verification_status.value,
                    "verification_remarks": doc.verification_remarks,
                    "uploaded_at": doc.created_at,
                }
            )

        return Response(
            {
                "success": True,
                "count": len(data),
                "documents": data,
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
@permission_classes([IsAuthenticated])
def get_document_types(request):

    applies_to = request.GET.get("purpose")

    queryset = DocumentType.objects.all()

    if applies_to:
        queryset = queryset.filter(applies_to=applies_to)

    return Response(
        {
            "success": True,
            "data": [
                {
                    "uuid":doc.uuid,
                    "name": doc.name,
                    "is_required": doc.is_required
                }
                for doc in queryset
            ],
        }
    )


@api_view(["POST"])
@permission_classes([CanEditProfile, IsActiveAccount])
@transaction.atomic
def upload_profile_document(request):
    try:
        serializer = UploadProfileDocumentSerializer(data=request.data)
        print("hello1")
        if not serializer.is_valid():
            return Response(
                {
                    "success": False,
                    "errors": serializer.errors,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        print("hello2")

        document_type_name = serializer.validated_data["document_type"]
        owner_mapping = {
            UserType.DONOR: DocOwner.DONOR,
            UserType.NGO: DocOwner.NGO,
            UserType.CSR: DocOwner.CSR,
            UserType.INDIVIDUAL_FUNDRAISER: DocOwner.INDIVIDUAL_FUNDRAISER,
        }
        print("hello3")

        try:

            document_type = DocumentType.objects.get(
                name=document_type_name,
                applies_to=owner_mapping[request.user.user_type],
            )
            print("hello4")

        except (KeyError, DocumentType.DoesNotExist):
            return Response(
                {
                    "success": False,
                    "error": "Invalid document type.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        print("here5")
        document = Document.objects.filter(
            user=request.user,
            document_type=document_type,
            purpose=DocumentPurpose.PROFILE_VERIFICATION,
        ).first()

        print("here6")

        if document:
            print("here7")

            # Update existing document

            document.document_holder_name = serializer.validated_data[
                "document_holder_name"
            ]

            document.file_url = serializer.validated_data["file_url"]
            print("here8")

            # Update number only if provided
            if serializer.validated_data.get("document_number"):
                document.document_number = serializer.validated_data["document_number"]

            document.verification_status = VerificationStatus.PENDING

            document.verification_remarks = None
            document.reviewed_by = None
            document.reviewed_at = None
            print("here9")

            document.save()

            message = "Document updated successfully."
            response_status = status.HTTP_200_OK

        else:

            # Create new document
            print("here10")

            Document.objects.create(
                purpose=DocumentPurpose.PROFILE_VERIFICATION,
                user=request.user,
                document_type=document_type,
                document_holder_name=(
                    serializer.validated_data["document_holder_name"]
                ),
                document_number=(serializer.validated_data.get("document_number")),
                file_url=(serializer.validated_data["file_url"]),
                verification_status=(VerificationStatus.PENDING),
            )
            print("here11")

            message = "Document uploaded successfully."
            response_status = status.HTTP_201_CREATED

        print("here12")

        return Response(
            {
                "success": True,
                "message": message,
            },
            status=response_status,
        )

    except ValidationError as e:

        return Response(
            {
                "success": False,
                "errors": e.message_dict,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:

        transaction.set_rollback(True)

        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
@parser_classes([MultiPartParser, FormParser])
@transaction.atomic
def upload_campaign_document(request):

    campaign_slug = request.data.get("campaign_slug")
    document_type_id = request.data.get("document_type_id")
    holder_name = request.data.get("document_holder_name")
    document_number = request.data.get("document_number")
    uploaded_file = request.FILES.get("file_url")

    if not campaign_slug:
        return Response(
            {"success": False, "message": "campaign_slug is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not uploaded_file:
        return Response(
            {"success": False, "message": "Document file is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        campaign = Campaign.objects.get(
            campaign_slug=campaign_slug,
            created_by=request.user,
        )

    except Campaign.DoesNotExist:
        return Response(
            {"success": False, "message": "Campaign not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    try:
        document_type = DocumentType.objects.get(uuid=document_type_id)

    except DocumentType.DoesNotExist:
        return Response(
            {"success": False, "message": "Invalid document type."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    document, created = Document.objects.update_or_create(
        campaign=campaign,
        document_type=document_type,
        purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
        defaults={
            "document_holder_name": holder_name,
            "document_number": document_number,
            "file_url": uploaded_file,
            "verification_status": VerificationStatus.PENDING,
            "verification_remarks": None,
            "reviewed_by": None,
            "reviewed_at": None,
            "ai_score": None,
        },
    )

    return Response(
        {
            "success": True,
            "message": "Document uploaded successfully.",
            "document": CampaignDocumentSerializer(document).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsActiveAccount])
@transaction.atomic
def submit_profile_verification(request):

    user = request.user

    try:

        # Already under verification
        if user.profile_status == ProfileStatus.VERIFICATION_PENDING:

            return Response(
                {
                    "success": False,
                    "error": "Profile already submitted for verification.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Already verified
        if user.profile_status == ProfileStatus.VERIFIED:

            return Response(
                {"success": False, "error": "Profile is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        DOC_OWNER_MAPPING = {
            UserType.DONOR: DocOwner.DONOR,
            UserType.INDIVIDUAL_FUNDRAISER: DocOwner.INDIVIDUAL_FUNDRAISER,
            UserType.NGO: DocOwner.NGO,
            UserType.CSR: DocOwner.CSR,
        }

        doc_owner = DOC_OWNER_MAPPING.get(user.user_type)

        if not doc_owner:
            return Response(
                {
                    "success": False,
                    "error": "Invalid user type.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        required_documents = list(
            DocumentType.objects.filter(
                applies_to=doc_owner,
                is_required=True,
            ).values_list(
                "name",
                flat=True,
            )
        )
        
        VERIFICATION_TYPE_MAPPING = {
            UserType.DONOR: VerificationType.DONOR,
            UserType.INDIVIDUAL_FUNDRAISER: VerificationType.INDIVIDUAL_FUNDRAISER,
            UserType.NGO: VerificationType.NGO,
            UserType.CSR: VerificationType.CSR,
        }


        verification_type = VERIFICATION_TYPE_MAPPING.get(user.user_type)

        if not required_documents or not verification_type:
            return Response(
                {"success": False, "error": "Invalid user type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        missing_documents = []

        for document_name in required_documents:
            exists = Document.objects.filter(
                user=user,
                purpose=DocumentPurpose.PROFILE_VERIFICATION,
                document_type__name=document_name,
            ).exclude(
                file_url=""
            ).exists()

            if not exists:
                missing_documents.append(document_name)

        if missing_documents:
            return Response(
                {
                    "success": False,
                    "error": "Please upload all required documents before submitting.",
                    "missing_documents": missing_documents,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        EntityVerificationRequest.objects.update_or_create(
            user=user,
            verification_type=verification_type,
            defaults={
                "status": VerificationStatus.PENDING,
            },
        )

        user.profile_status = ProfileStatus.VERIFICATION_PENDING
        user.save(update_fields=["profile_status"])

        return Response(
            {
                "success": True,
                "message": "Profile submitted for verification.",
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        transaction.set_rollback(True)

        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsCampaignCreator])
@transaction.atomic
def submit_campaign_verification(request):
    """
    Submit campaign for verification.
    """
    campaign_slug = request.data.get("campaign_slug")
    try:
        campaign = Campaign.objects.select_for_update().get(
            campaign_slug=campaign_slug,
            created_by=request.user,
        )
    except Campaign.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Campaign not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # --------------------------------------------------
    # Campaign must be in Draft
    # --------------------------------------------------

    if campaign.campaign_status != CampaignStatus.DRAFT:
        return Response(
            {
                "success": False,
                "message": "Only draft campaigns can be submitted.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # At least one supporting document is required
    # --------------------------------------------------

    if not Document.objects.filter(
        campaign=campaign,
        purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
    ).exists():
        return Response(
            {
                "success": False,
                "message": "Please upload at least one supporting document.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Prevent duplicate pending verification requests
    # --------------------------------------------------

    if EntityVerificationRequest.objects.filter(
        campaign=campaign,
        verification_type=VerificationType.CAMPAIGN,
        status=VerificationStatus.PENDING,
    ).exists():
        return Response(
            {
                "success": False,
                "message": "Campaign is already pending verification.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Create verification request
    # --------------------------------------------------

    EntityVerificationRequest.objects.create(
        verification_type=VerificationType.CAMPAIGN,
        campaign=campaign,
        status=VerificationStatus.PENDING,
    )

    # --------------------------------------------------
    # Reset document verification status
    # --------------------------------------------------

    Document.objects.filter(
        campaign=campaign,
        purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
    ).update(
        verification_status=VerificationStatus.PENDING,
        verification_remarks=None,
        reviewed_by=None,
        reviewed_at=None,
        ai_score=None,
    )

    # --------------------------------------------------
    # Update campaign status
    # --------------------------------------------------

    campaign.campaign_status = CampaignStatus.PENDING
    campaign.save(update_fields=["campaign_status"])

    return Response(
        {
            "success": True,
            "message": "Campaign submitted for verification successfully.",
        },
        status=status.HTTP_200_OK,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
@transaction.atomic
def verify_document(request, uuid):
    """
    Verify a single document (PAN, Aadhaar, etc.)
    """
    print("usertype", request.user.user_type)
    if request.user.user_type not in (
        UserType.ADMIN,
        UserType.SUPER_ADMIN,
    ):
        return Response(
            {
                "success": False,
                "message": "You are not authorized to verify documents.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    document = get_object_or_404(Document, uuid=uuid)

    verification_status = request.data.get("verification_status")
    verification_remarks = request.data.get("verification_remarks", "").strip()
    print("verification_status", verification_status)
    if verification_status not in (
        VerificationStatus.APPROVED.value,
        VerificationStatus.REJECTED.value,
    ):
        return Response(
            {
                "success": False,
                "message": "Invalid verification status.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if (
        verification_status == VerificationStatus.REJECTED.value
        and not verification_remarks
    ):
        return Response(
            {
                "success": False,
                "message": "Remarks are required when rejecting a document.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    document.verification_status = verification_status
    document.verification_remarks = verification_remarks
    document.reviewed_by = request.user
    document.reviewed_at = timezone.now()

    document.save(
        update_fields=[
            "verification_status",
            "verification_remarks",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )

    return Response(
        {
            "success": True,
            "message": f"{document.document_type.name} {document.verification_status.value} successfully.",
            "data": {
                "uuid": str(document.uuid),
                "document_type": document.document_type.name,
                "verification_status": document.verification_status.value,
                "verification_remarks": document.verification_remarks,
                "reviewed_by": (
                    document.reviewed_by.fullname if document.reviewed_by else None
                ),
                "reviewed_at": document.reviewed_at,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsPlatformAdmin])
@transaction.atomic
def verify_bankaccount(request):
    """
    Approve / Reject donor bank account.
    """
    user_id = request.data.get("user_id")
    verification_status = request.data.get("verification_status")
    verification_remarks = request.data.get("remarks", "").strip()

    if verification_status not in [
        VerificationStatus.APPROVED.value,
        VerificationStatus.REJECTED.value,
    ]:
        return Response(
            {
                "success": False,
                "message": "verification_status must be Approved or Rejected.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        bank = BankAccount.objects.select_related("user").get(user__uuid=user_id)

    except BankAccount.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Bank account not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    if not bank.cancelled_cheque:
        return Response(
            {
                "success": False,
                "message": "Cancelled cheque not uploaded.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    bank.verification_status = VerificationStatus(verification_status)
    bank.verified_by = request.user
    bank.verified_at = timezone.now()
    bank.remarks = verification_remarks
    bank.save()

    return Response(
        {
            "success": True,
            "message": f"Bank account {verification_status.lower()} successfully.",
            "data": {
                "verification_status": bank.verification_status.value,
                "remarks": bank.remarks,
                "verified_by": bank.verified_by.display_name,
                "verified_at": bank.verified_at,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def verify_profile(request):
    """
    Verify User Profile.

    Rules:

    1. Every required document must exist.
    2. Bank account must exist.
    3. If ANY document OR bank account is Pending
       -> Profile cannot be approved/rejected.

    4. Approve Profile
       -> All documents Approved
       -> Bank Approved

    5. Reject Profile
       -> Nothing Pending
       -> At least one document OR bank account Rejected
    """

    user_id = request.data.get("user_id")
    action = request.data.get("action")
    remarks = request.data.get("remarks", "").strip()

    if not user_id:
        return Response(
            {"success": False, "message": "user_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action not in ["approve", "reject"]:
        return Response(
            {"success": False, "message": "Action must be approve or reject."},
            status=status.HTTP_400_BAD_REQUEST,
        )
        # --------------------------------------------------
    # Fetch User
    # --------------------------------------------------

    try:
        user = CustomUser.objects.get(uuid=user_id)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # --------------------------------------------------
    # Determine Verification Type
    # --------------------------------------------------

    verification_type_map = {
        UserType.DONOR: VerificationType.DONOR,
        UserType.INDIVIDUAL_FUNDRAISER: VerificationType.INDIVIDUAL_FUNDRAISER,
        UserType.NGO: VerificationType.NGO,
        UserType.CSR: VerificationType.CSR,
    }

    verification_type = verification_type_map.get(user.user_type)

    if not verification_type:
        return Response(
            {
                "success": False,
                "message": "User type is not eligible for profile verification.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Fetch Pending Verification Request
    # --------------------------------------------------

    try:
        verification_request = EntityVerificationRequest.objects.get(
            user=user, verification_type=verification_type
        )
    except EntityVerificationRequest.DoesNotExist:
        return Response(
            {"success": False, "message": "No pending verification request found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Determine Document Owner
    # --------------------------------------------------

    owner_map = {
        UserType.DONOR: DocOwner.DONOR,
        UserType.INDIVIDUAL_FUNDRAISER: DocOwner.INDIVIDUAL_FUNDRAISER,
        UserType.NGO: DocOwner.NGO,
        UserType.CSR: DocOwner.CSR,
    }

    doc_owner = owner_map.get(user.user_type)

    if not doc_owner:
        return Response(
            {
                "success": False,
                "message": "No document configuration found for this user type.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Fetch Required Document Types
    # --------------------------------------------------

    required_document_types = DocumentType.objects.filter(applies_to=doc_owner, is_required=True)

    if not required_document_types.exists():
        return Response(
            {
                "success": False,
                "message": "Required document types are not configured.",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # --------------------------------------------------
    # Fetch Uploaded Documents
    # --------------------------------------------------

    documents = Document.objects.filter(
        user=user,
        purpose=DocumentPurpose.PROFILE_VERIFICATION,
        document_type__in=required_document_types,
    )

    required_ids = set(required_document_types.values_list("uuid", flat=True))

    uploaded_ids = set(documents.values_list("document_type_id", flat=True))

    missing_ids = required_ids - uploaded_ids

    if missing_ids:

        missing_documents = list(
            required_document_types.filter(uuid__in=missing_ids).values_list(
                "name", flat=True
            )
        )

        return Response(
            {
                "success": False,
                "message": "All required documents must be uploaded.",
                "missing_documents": missing_documents,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Fetch Bank Account
    # --------------------------------------------------

    try:
        bank_account = BankAccount.objects.get(user=user)
    except BankAccount.DoesNotExist:
        return Response(
            {"success": False, "message": "Bank account not found."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Collect Verification Statuses
    # --------------------------------------------------

    document_statuses = list(documents.values_list("verification_status", flat=True))

    bank_status = bank_account.verification_status

    # --------------------------------------------------
    # Check Pending Verification
    # --------------------------------------------------

    has_pending_document = any(
        status == VerificationStatus.PENDING for status in document_statuses
    )

    has_pending_bank = bank_status == VerificationStatus.PENDING

    if has_pending_document or has_pending_bank:
        return Response(
            {
                "success": False,
                "message": (
                    "Please complete verification of all documents "
                    "and the bank account before verifying the profile."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # --------------------------------------------------
    # Check Approved / Rejected Status
    # --------------------------------------------------

    all_documents_approved = all(
        status == VerificationStatus.APPROVED for status in document_statuses
    )

    bank_approved = bank_status == VerificationStatus.APPROVED

    has_rejected_document = any(
        status == VerificationStatus.REJECTED for status in document_statuses
    )

    bank_rejected = bank_status == VerificationStatus.REJECTED

    all_verified = all_documents_approved and bank_approved

    has_any_rejection = has_rejected_document or bank_rejected

    # --------------------------------------------------
    # Approve Profile
    # --------------------------------------------------

    if action == "approve":

        if not all_verified:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Profile can only be approved when all submitted "
                        "documents and the bank account are approved."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification_request.status = VerificationStatus.APPROVED
        verification_request.reviewed_by = request.user
        verification_request.reviewed_at = timezone.now()
        verification_request.remarks = remarks

        user.profile_status = ProfileStatus.VERIFIED

        message = "Profile approved successfully."

    # --------------------------------------------------
    # Reject Profile
    # --------------------------------------------------

    else:

        verification_request.status = VerificationStatus.REJECTED
        verification_request.reviewed_by = request.user
        verification_request.reviewed_at = timezone.now()
        verification_request.remarks = remarks

        user.profile_status = ProfileStatus.VERIFICATION_REJECTED

        message = "Profile rejected successfully."

        # --------------------------------------------------
    # Save Verification Request
    # --------------------------------------------------

    verification_request.save(
        update_fields=[
            "status",
            "reviewed_by",
            "reviewed_at",
            "remarks",
            "updated_at",
        ]
    )

    # --------------------------------------------------
    # Save User
    # --------------------------------------------------

    user.save(
        update_fields=[
            "profile_status",
            "updated_at",
        ]
    )

    # --------------------------------------------------
    # Response
    # --------------------------------------------------

    return Response(
        {
            "success": True,
            "message": message,
            "data": {
                "user_id": str(user.uuid),
                "verification_request_id": str(verification_request.uuid),
                "profile_status": user.profile_status.value,
                "verification_status": verification_request.status.value,
                "reviewed_by": request.user.fullname,
                "reviewed_at": verification_request.reviewed_at,
                "remarks": verification_request.remarks,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsPlatformAdmin])
def verify_campaign(request):
    """
    Verify Campaign

    Rules

    1. Campaign verification request must exist.
    2. At least one campaign document must exist.
    3. No document can remain Pending.
    4. Approve:
        - Every document Approved.
    5. Reject:
        - No Pending documents.
        - At least one Rejected document.
    """

    campaign_slug = request.data.get("campaign_slug")
    action = request.data.get("action")
    remarks = request.data.get("remarks", "").strip()

    if not campaign_slug:
        return Response(
            {
                "success": False,
                "message": "campaign_slug is required.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if action not in ["approve", "reject"]:
        return Response(
            {
                "success": False,
                "message": "Action must be approve or reject.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # Campaign
    # ---------------------------------------------------------

    try:
        campaign = Campaign.objects.get(
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

    # ---------------------------------------------------------
    # Verification Request
    # ---------------------------------------------------------

    try:
        verification_request = EntityVerificationRequest.objects.get(
            campaign=campaign,
            verification_type=VerificationType.CAMPAIGN,
        )
    except EntityVerificationRequest.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Campaign verification request not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # ---------------------------------------------------------
    # Campaign Documents
    # ---------------------------------------------------------

    documents = Document.objects.filter(
        campaign=campaign,
        purpose=DocumentPurpose.CAMPAIGN_VERIFICATION,
    )

    if not documents.exists():
        return Response(
            {
                "success": False,
                "message": "No campaign documents uploaded.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    document_statuses = list(
        documents.values_list(
            "verification_status",
            flat=True,
        )
    )

    # ---------------------------------------------------------
    # Pending Documents
    # ---------------------------------------------------------

    has_pending = any(
        status == VerificationStatus.PENDING
        for status in document_statuses
    )

    if has_pending:
        return Response(
            {
                "success": False,
                "message": (
                    "Please verify every campaign document "
                    "before approving or rejecting the campaign."
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---------------------------------------------------------
    # Approved / Rejected
    # ---------------------------------------------------------

    all_approved = all(
        status == VerificationStatus.APPROVED
        for status in document_statuses
    )

    has_rejected = any(
        status == VerificationStatus.REJECTED
        for status in document_statuses
    )

    # ---------------------------------------------------------
    # Approve Campaign
    # ---------------------------------------------------------

    if action == "approve":

        if not all_approved:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Campaign can only be approved when "
                        "every campaign document is approved."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        verification_request.status = VerificationStatus.APPROVED
        verification_request.reviewed_by = request.user
        verification_request.reviewed_at = timezone.now()
        verification_request.remarks = remarks

        campaign.campaign_status = CampaignStatus.ACTIVE

        message = "Campaign approved successfully."

    # ---------------------------------------------------------
    # Reject Campaign
    # ---------------------------------------------------------

    else:



        verification_request.status = VerificationStatus.REJECTED
        verification_request.reviewed_by = request.user
        verification_request.reviewed_at = timezone.now()
        verification_request.remarks = remarks

        campaign.campaign_status = CampaignStatus.REJECTED

        message = "Campaign rejected successfully."

    # ---------------------------------------------------------
    # Save
    # ---------------------------------------------------------

    verification_request.save(
        update_fields=[
            "status",
            "remarks",
            "reviewed_by",
            "reviewed_at",
            "updated_at",
        ]
    )

    campaign.save(
        update_fields=[
            "campaign_status",
            "updated_at",
        ]
    )
    
    # ---------------------------------------------------------
# Create Campaign Wallet
# ---------------------------------------------------------

    if action == "approve":

        Wallet.objects.get_or_create(
            campaign=campaign,
            defaults={
                "wallet_type": WalletType.CAMPAIGN,
                "currency": Currency.INR,
            },
        )

    # ---------------------------------------------------------
    # Response
    # ---------------------------------------------------------

    return Response(
        {
            "success": True,
            "message": message,
            "data": {
                "campaign_slug": campaign.campaign_slug,
                "campaign_name": campaign.campaign_name,
                "campaign_status": campaign.campaign_status.value,
                "verification_status": verification_request.status.value,
                "reviewed_by": request.user.fullname,
                "reviewed_at": verification_request.reviewed_at,
                "remarks": verification_request.remarks,
            },
        },
        status=status.HTTP_200_OK,
    )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_document(request, document_uuid):
    try:
        document = Document.objects.select_related(
            "user",
            "campaign",
        ).get(
            Q(user=request.user) |
            Q(campaign__created_by=request.user),
            uuid=document_uuid,
        )
    except Document.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Document not found or you do not have permission to delete it.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    # Extra ownership validation
    if document.user and document.user != request.user:
        return Response(
            {
                "success": False,
                "message": "You can only delete your own documents.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    if document.campaign and document.campaign.created_by != request.user:
        return Response(
            {
                "success": False,
                "message": "You can only delete documents belonging to your own campaign.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    # Approved documents cannot be deleted
    if document.verification_status == VerificationStatus.APPROVED:
        return Response(
            {
                "success": False,
                "message": "Approved documents cannot be deleted.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Profile documents cannot be deleted after profile submission
    if document.user:
        profile_submitted = EntityVerificationRequest.objects.filter(
            user=document.user,status__in=[
            VerificationStatus.PENDING,
            VerificationStatus.APPROVED
        ],
        ).exists()

        if profile_submitted:
            return Response(
                {
                    "success": False,
                    "message": "Documents cannot be deleted after your profile has been submitted for verification.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Campaign documents cannot be deleted after campaign submission
    if document.campaign:
        campaign_submitted = EntityVerificationRequest.objects.filter(
            campaign=document.campaign,
            verification_type=VerificationType.CAMPAIGN,
            status__in=[
            VerificationStatus.PENDING,
            VerificationStatus.APPROVED
        ],
        ).exists()

        if campaign_submitted:
            return Response(
                {
                    "success": False,
                    "message": "Documents cannot be deleted after the campaign has been submitted for verification.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )


    # Delete uploaded file
    if document.file_url:
        document.file_url.delete(save=False)

    # Delete database record
    document.delete()

    return Response(
        {
            "success": True,
            "message": "Document deleted successfully.",
        },
        status=status.HTTP_200_OK,
    )



