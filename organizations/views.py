from django.shortcuts import render

# Create your views here.
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from verification.models import EntityVerificationRequest

from .models import NGOProfile
from crowdfunding.enums import UserType, VerificationType
from crowdfunding.permissions import CanEditProfile, IsActiveAccount, IsCSR, IsNGO
from organizations.models import CSRProfile



@api_view(["GET"])
@permission_classes([IsActiveAccount, IsNGO])
def get_ngo_profile(request):
    try:
        user = request.user

        profile = NGOProfile.objects.get(user=user)
        
        verification = (
            EntityVerificationRequest.objects.filter(
                user=user,
                verification_type=VerificationType.NGO,
            )
            .order_by("-created_at")
            .first()
        )

        return Response(
            {
                "success": True,
                "data": {
                    "uuid": str(profile.uuid),
                    "ngo_name": profile.ngo_name,
                    "ngo_type": profile.ngo_type.value,
                    "registration_number": profile.reg_num,

                    "contact_person_name": profile.contact_person_name,
                    "contact_person_designation": profile.contact_person_designation,
                    "email": user.email,
                    "mobile": user.mobile,

                    "address": profile.address or "",
                    "city": profile.city or "",
                    "state": profile.state or "",
                    "country": profile.country or "",
                    "pincode": profile.pincode or "",

                    "website": profile.website or "",
                    "profile_picture": (
                        request.build_absolute_uri(user.profile_picture.url)
                        if user.profile_picture
                        else None
                    ),

                    "profile_status": user.profile_status.value,
                    "verification_remarks": (
                        verification.remarks if verification else ""
                    ),
                    "verification_status": (
                        verification.status.value if verification else None
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

    except NGOProfile.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "NGO profile not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
 

@api_view(["PUT"])
@permission_classes([ IsNGO, CanEditProfile])
def update_ngo_profile(request):

    user = request.user

    # Check NGO user
    if user.user_type != UserType.NGO:
        return Response(
            {
                "success": False,
                "message": "Only NGO users can update profile"
            },
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        ngo_profile = NGOProfile.objects.get(user=user)

    except NGOProfile.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "NGO profile does not exist"
            },
            status=status.HTTP_404_NOT_FOUND
        )


    data = request.data


    # ==========================
    # Basic NGO fields update
    # ==========================

    if "ngo_name" in data:
        ngo_profile.ngo_name = data["ngo_name"]


    if "ngo_type" in data:
        ngo_profile.ngo_type = data["ngo_type"]


    if "contact_person_name" in data:
        ngo_profile.contact_person_name = data["contact_person_name"]


    if "contact_person_designation" in data:
        ngo_profile.contact_person_designation = data["contact_person_designation"]


    if "website" in data:
        ngo_profile.website = data["website"]


    # ==========================
    # Registration Number Update
    # ==========================

    if "reg_num" in data:

        if NGOProfile.objects.filter(
            reg_num=data["reg_num"]
        ).exclude(
            uuid=ngo_profile.uuid
        ).exists():

            return Response(
                {
                    "success": False,
                    "message": "Registration number already exists"
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        ngo_profile.reg_num = data["reg_num"]



    # ==========================
    # Address Update Validation
    # ==========================

    address_fields = [
        "address",
        "city",
        "state",
        "country",
        "pincode"
    ]


    address_update = any(
        field in data
        for field in address_fields
    )


    if address_update:

        missing_fields = [
            field
            for field in address_fields
            if not data.get(field)
        ]


        if missing_fields:

            return Response(
                {
                    "success": False,
                    "message": "All address fields are required when updating address",
                    "missing_fields": missing_fields
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        ngo_profile.address = data["address"]
        ngo_profile.city = data["city"]
        ngo_profile.state = data["state"]
        ngo_profile.country = data["country"]
        ngo_profile.pincode = data["pincode"]


    # ==========================
# Profile Picture Update
# ==========================

    if "profile_picture" in request.FILES:

        # Delete old profile picture (optional)
        if user.profile_picture:
            user.profile_picture.delete(save=False)

        user.profile_picture = request.FILES["profile_picture"]
        user.save(update_fields=["profile_picture"])
    ngo_profile.save()


    return Response(
        {
            "success": True,
            "message": "NGO profile updated successfully",
            "profile": {
                "uuid": str(ngo_profile.uuid),
                "ngo_name": ngo_profile.ngo_name,
                "ngo_type": ngo_profile.ngo_type.value,
                "reg_num": ngo_profile.reg_num,
                "contact_person_name": ngo_profile.contact_person_name,
                "contact_person_designation": ngo_profile.contact_person_designation,
                "address": ngo_profile.address,
                "city": ngo_profile.city,
                "state": ngo_profile.state,
                "country": ngo_profile.country,
                "pincode": ngo_profile.pincode,
                "website": ngo_profile.website,
            }
        },
        status=status.HTTP_200_OK
    )       

@api_view(["GET"])
@permission_classes([IsActiveAccount, IsCSR])
def get_csr_profile(request):
    try:
        user = request.user

        profile = CSRProfile.objects.get(user=user)
        
        verification = (
            EntityVerificationRequest.objects.filter(
                user=user,
                verification_type=VerificationType.CSR,
            )
            .order_by("-created_at")
            .first()
        )

        return Response(
            {
                "success": True,
                "data": {
                    "uuid": str(profile.uuid),
                    "csr_name": profile.csr_name,
                    "csr_registration_number": profile.csr_reg_num,

                    "contact_person_name": profile.contact_person_name,
                    "contact_person_designation": profile.contact_person_designation,

                    "email": user.email,
                    "mobile": user.mobile,

                    "address": profile.address or "",
                    "city": profile.city or "",
                    "state": profile.state or "",
                    "country": profile.country or "",
                    "pincode": profile.pincode or "",

                    "website": profile.website or "",
                    "profile_picture": (
                        request.build_absolute_uri(user.profile_picture.url)
                        if user.profile_picture
                        else None
                    ),

                    "profile_status": user.profile_status.value,
                    "verification_remarks": (
                        verification.remarks if verification else ""
                    ),
                    "verification_status": (
                        verification.status.value if verification else None
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

    except CSRProfile.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "CSR profile not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    except Exception as e:
        return Response(
            {
                "success": False,
                "error": str(e),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
        

@api_view(["PUT"])
@permission_classes([CanEditProfile, IsCSR])
def update_csr_profile(request):

    user = request.user

    try:
        csr_profile = CSRProfile.objects.get(
            user=user
        )

    except CSRProfile.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "CSR profile not found"
            },
            status=status.HTTP_404_NOT_FOUND
        )


    data = request.data


    # ==========================
    # Basic CSR Details
    # ==========================

    if "csr_name" in data:
        csr_profile.csr_name = data["csr_name"]


    if "contact_person_name" in data:
        csr_profile.contact_person_name = data["contact_person_name"]


    if "contact_person_designation" in data:
        csr_profile.contact_person_designation = data[
            "contact_person_designation"
        ]


    if "website" in data:
        csr_profile.website = data["website"]



    # ==========================
    # Registration Number
    # ==========================

    if "csr_reg_num" in data:

        if CSRProfile.objects.filter(
            csr_reg_num=data["csr_reg_num"]
        ).exclude(
            uuid=csr_profile.uuid
        ).exists():

            return Response(
                {
                    "success": False,
                    "message": "CSR registration number already exists"
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        csr_profile.csr_reg_num = data["csr_reg_num"]



    # ==========================
    # Address Update
    # ==========================

    address_fields = [
        "address",
        "city",
        "state",
        "country",
        "pincode"
    ]


    address_update = any(
        field in data
        for field in address_fields
    )


    if address_update:

        missing_fields = [
            field
            for field in address_fields
            if not data.get(field)
        ]


        if missing_fields:

            return Response(
                {
                    "success": False,
                    "message": "All address fields are required when updating address",
                    "missing_fields": missing_fields
                },
                status=status.HTTP_400_BAD_REQUEST
            )


        csr_profile.address = data["address"]
        csr_profile.city = data["city"]
        csr_profile.state = data["state"]
        csr_profile.country = data["country"]
        csr_profile.pincode = data["pincode"]


    if "profile_picture" in request.FILES:
    
            # Delete old profile picture (optional)
            if user.profile_picture:
                user.profile_picture.delete(save=False)
    
            user.profile_picture = request.FILES["profile_picture"]
            user.save(update_fields=["profile_picture"])

    csr_profile.save()


    return Response(
        {
            "success": True,
            "message": "CSR profile updated successfully",
            "data": {
                "uuid": str(csr_profile.uuid),
                "csr_name": csr_profile.csr_name,
                "csr_reg_num": csr_profile.csr_reg_num,
                "contact_person_name": csr_profile.contact_person_name,
                "contact_person_designation": csr_profile.contact_person_designation,
                "address": csr_profile.address,
                "city": csr_profile.city,
                "state": csr_profile.state,
                "country": csr_profile.country,
                "pincode": csr_profile.pincode,
                "website": csr_profile.website,
            }
        },
        status=status.HTTP_200_OK
    )
    

