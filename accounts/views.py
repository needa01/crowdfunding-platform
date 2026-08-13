import random

from django.shortcuts import render
import requests
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db import IntegrityError, transaction
from accounts.models import (
    OTP,
    BankAccount,
    CustomUser,
    DonorProfile,
    IndividualProfile,
    ProfileStatus,
    Status,
    UserType,
)
from crowdfunding.enums import DocOwner, DocumentPurpose, NGOType, VerificationStatus, VerificationType
from crowdfunding.permissions import (
    CanCompleteProfile,
    CanEditProfile,
    CanManageDocuments,
    IsActiveAccount,
    IsDonor,
    IsIndividualFundraiser,
    IsNGO,
)
from crowdfunding.utils import change_user_password, get_login_message
from crowdfunding import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from rest_framework import status
from django.utils import timezone
from organizations.models import CSRProfile, NGOProfile
from verification.models import Document, DocumentType, EntityVerificationRequest



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_user_info(request):

    user = request.user

    verification_request = (
        user.verification_requests
        .order_by("-created_at")
        .first()
    )

    verification_status = (
        verification_request.status.value
        if verification_request
        else None
    )

    return Response(
        {
            "success": True,
            "user_name": user.fullname,
            "user_email": user.email,
            "user_type": user.user_type.value,
            "status": user.status.value,
            "profile_status": user.profile_status.value,
            "verification_status": verification_status,
        },
        status=status.HTTP_200_OK,
    )



@api_view(["POST"])
@permission_classes([AllowAny])
def send_otp(request):

    mobile = request.data.get("mobile")

    if not mobile:
        return Response(
            {"success": False, "error": "Mobile is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if mobile is already verified
    user = CustomUser.objects.filter(
        mobile=mobile, is_mobile_verified=True, is_deleted=False
    ).first()

    if user:
        return Response(
            {"success": False, "error": "Mobile number is already verified"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Existing active OTP?
    if OTP.objects.filter(
        mobile=mobile, is_verified=False, expires_at__gt=timezone.now()
    ).exists():
        return Response(
            {
                "success": False,
                "error": "OTP already sent. Please wait before requesting another.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    otp = str(random.randint(100000, 999999))
    message = f"Your OTP is {otp}. Do not share it with anyone."
    url = "https://www.fast2sms.com/dev/bulkV2"

    params = {
        "authorization": settings.FAST2SMS_API_KEY,
        "route": "q",
        "message": message,
        "numbers": mobile,
    }
    print("OTP", otp)
    OTP.objects.create(
        mobile=mobile, otp=otp, request_id="aaswh5656", is_verified=False
    )
    return Response(
        {
            "success": True,
            "message": "OTP sent successfully.",
            "request_id": "request_id",
        },
        status=status.HTTP_200_OK,
    )
    # try:
    #     response = requests.get(url, params=params, timeout=10)
    #     print(response.json())
    #     # Parse JSON safely
    #     try:
    #         data = response.json()
    #     except ValueError:
    #         return Response(
    #             {
    #                 "success": False,
    #                 "error": "Invalid response received from SMS provider.",
    #             },
    #             status=status.HTTP_502_BAD_GATEWAY,
    #         )

    #     # Success (HTTP 200 + return=true)
    #     if response.status_code == 200 and data.get("return") is True:

    #         OTP.objects.create(
    #             mobile=mobile,
    #             otp= otp,
    #             request_id= data.get("request_id"),
    #             is_verified= False
    #         )

    #         return Response(
    #             {
    #                 "success": True,
    #                 "message": "OTP sent successfully.",
    #                 "request_id": data.get("request_id"),
    #             },
    #             status=status.HTTP_200_OK,
    #         )

    #     # Invalid Mobile Number (Fast2SMS 411)
    #     if (
    #         response.status_code == 400
    #         and data.get("status_code") == 411
    #     ):
    #         return Response(
    #             {
    #                 "success": False,
    #                 "error": "Invalid mobile number.",
    #             },
    #             status=status.HTTP_400_BAD_REQUEST,
    #         )

    #     # Other Fast2SMS errors
    #     return Response(
    #         {
    #             "success": False,
    #             "error": data.get("message", "Failed to send OTP."),
    #             "provider_status_code": data.get("status_code"),
    #         },
    #         status=response.status_code,
    #     )

    # except requests.Timeout:
    #     return Response(
    #         {
    #             "success": False,
    #             "error": "SMS service timed out. Please try again.",
    #         },
    #         status=status.HTTP_504_GATEWAY_TIMEOUT,
    #     )

    # except requests.ConnectionError:
    #     return Response(
    #         {
    #             "success": False,
    #             "error": "Unable to connect to SMS service.",
    #         },
    #         status=status.HTTP_503_SERVICE_UNAVAILABLE,
    #     )

    # except requests.RequestException:
    #     return Response(
    #         {
    #             "success": False,
    #             "error": "Failed to send OTP due to an external service error.",
    #         },
    #         status=status.HTTP_502_BAD_GATEWAY,
    #     )

    # except Exception:
    #     return Response(
    #         {
    #             "success": False,
    #             "error": "Something went wrong while sending OTP.",
    #         },
    #         status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #     )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):

    mobile = request.data.get("mobile")
    otp = request.data.get("otp")
    # Check if mobile is already verified
    user = CustomUser.objects.filter(
        mobile=mobile, is_mobile_verified=True, is_deleted=False
    ).first()

    if user:
        return Response(
            {"success": False, "error": "Mobile number is already verified"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    otp_obj = OTP.objects.filter(mobile=mobile, otp=otp).order_by("-created_at").first()

    if not otp_obj:
        return Response(
            {"success": False, "error": "Invalid OTP", "is_verified": False},
            status=status.HTTP_400_BAD_REQUEST,
        )
    # Check if OTP is verified
    if otp_obj.is_verified:
        return Response(
            {"success": False, "error": "OTP already verified", "is_verified": True},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check if OTP is expired
    if otp_obj.expires_at < timezone.now():
        return Response(
            {"success": False, "error": "OTP expired", "is_verified": False},
            status=status.HTTP_400_BAD_REQUEST,
        )

    otp_obj.is_verified = True
    otp_obj.save()

    return Response(
        {"success": True, "is_verified": True, "message": "OTP verified"},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_as_donor(request):
    fullname = request.data.get("fullname")
    email = request.data.get("email")
    password = request.data.get("password")
    mobile = request.data.get("mobile")
    confirm_password = request.data.get("confirm_password")

    try:

        with transaction.atomic():
            if not all([fullname, mobile, email, password, confirm_password]):
                return Response(
                    {"success": False, "error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check email uniqueness
            if CustomUser.objects.filter(email=email).exists():
                return Response(
                    {"success": False, "error": "Email already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check mobile uniqueness
            if CustomUser.objects.filter(mobile=mobile).exists():
                return Response(
                    {"success": False, "error": "Mobile already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if password != confirm_password:
                return Response(
                    {"success": False, "error": "Passwords do match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                validate_password(password)
            except ValidationError as e:
                return Response(
                    {"success": False, "error": e.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_otp = (
                OTP.objects.filter(mobile=mobile, is_verified=True)
                .order_by("-created_at")
                .first()
            )

            if not verified_otp:
                return Response(
                    {"success": False, "error": "Mobile number is not verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create donor
            user = CustomUser.objects.create(
                username=email,  # required by AbstractUser
                fullname=fullname,
                email=email,
                mobile=mobile,
                password=make_password(password),
                user_type=UserType.DONOR,
                is_mobile_verified=True,
                status=Status.ACTIVE,
                profile_status=ProfileStatus.PROFILE_COMPLETED,
            )
            donorprofile = DonorProfile.objects.create(user=user)
            refresh = RefreshToken.for_user(user)

            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return Response(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_type": user.user_type.value,
                },
                status=status.HTTP_201_CREATED,
            )

    except IntegrityError as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except Exception:

        return Response(
            {"success": False, "error": "str(e)"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_as_indi_fundraiser(request):
    fullname = request.data.get("fullname")
    email = request.data.get("email")
    password = request.data.get("password")
    confirm_password = request.data.get("confirm_password")
    mobile = request.data.get("mobile")

    try:
        with transaction.atomic():
            # Mandatory field validation
            if not all([fullname, email, password, confirm_password, mobile]):
                return Response(
                    {"success": False, "error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check email uniqueness
            if CustomUser.objects.filter(email=email).exists():
                return Response(
                    {"success": False, "error": "Email already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check mobile uniqueness
            if CustomUser.objects.filter(mobile=mobile).exists():
                return Response(
                    {"success": False, "error": "Mobile already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Matching Password and confirm password validation
            if password != confirm_password:
                return Response(
                    {"success": False, "error": "Passwords do not match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Password validation
            try:
                validate_password(password)
            except ValidationError as e:
                return Response(
                    {"success": False, "error": e.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_otp = (
                OTP.objects.filter(mobile=mobile, is_verified=True)
                .order_by("-created_at")
                .first()
            )

            if not verified_otp:
                return Response(
                    {"success": False, "error": "Mobile number is not verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create individual fundraiser user
            user = CustomUser.objects.create(
                username=email,  # required by AbstractUser
                fullname=fullname,
                email=email,
                mobile=mobile,
                password=make_password(password),
                user_type=UserType.INDIVIDUAL_FUNDRAISER,
                is_mobile_verified=True,
            )

            refresh = RefreshToken.for_user(user)

            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return Response(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_type": user.user_type.value,
                },
                status=status.HTTP_201_CREATED,
            )
    except IntegrityError:
        return Response(
            {"success": False, "error": "Email or mobile already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_as_ngo(request):
    fullname = request.data.get("fullname")
    email = request.data.get("email")
    password = request.data.get("password")
    confirm_password = request.data.get("confirm_password")
    mobile = request.data.get("mobile")

    try:
        with transaction.atomic():

            # Mandatory field validation
            if not all([fullname, email, password, confirm_password, mobile]):
                return Response(
                    {"success": False, "error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check email uniqueness
            if CustomUser.objects.filter(email=email).exists():
                return Response(
                    {"success": False, "error": "Email already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check mobile uniqueness
            if CustomUser.objects.filter(mobile=mobile).exists():
                return Response(
                    {"success": False, "error": "Mobile already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Matching Password and confirm password validation
            if password != confirm_password:
                return Response(
                    {"success": False, "error": "Passwords do not match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Password validation
            try:
                validate_password(password)
            except ValidationError as e:
                return Response(
                    {"success": False, "error": e.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_otp = (
                OTP.objects.filter(mobile=mobile, is_verified=True)
                .order_by("-created_at")
                .first()
            )

            if not verified_otp:
                return Response(
                    {"success": False, "error": "Mobile number is not verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create individual fundraiser user
            user = CustomUser.objects.create(
                username=email,  # required by AbstractUser
                fullname=fullname,
                email=email,
                mobile=mobile,
                password=make_password(password),
                user_type=UserType.NGO,
                is_mobile_verified=True,
            )

            refresh = RefreshToken.for_user(user)

            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return Response(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_type": user.user_type.value,
                },
                status=status.HTTP_201_CREATED,
            )

    except IntegrityError:
        return Response(
            {"success": False, "error": "Email or mobile already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def signup_as_csr(request):
    fullname = request.data.get("fullname")
    email = request.data.get("email")
    password = request.data.get("password")
    confirm_password = request.data.get("confirm_password")
    mobile = request.data.get("mobile")

    try:
        with transaction.atomic():
            # Mandatory field validation
            if not all([fullname, email, password, confirm_password, mobile]):
                return Response(
                    {"success": False, "error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check email uniqueness
            if CustomUser.objects.filter(email=email).exists():
                return Response(
                    {"success": False, "error": "Email already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check mobile uniqueness
            if CustomUser.objects.filter(mobile=mobile).exists():
                return Response(
                    {"success": False, "error": "Mobile already registered"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Matching Password and confirm password validation
            if password != confirm_password:
                return Response(
                    {"success": False, "error": "Passwords do not match"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Password validation
            try:
                validate_password(password)
            except ValidationError as e:
                return Response(
                    {"success": False, "error": e.messages},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            verified_otp = (
                OTP.objects.filter(mobile=mobile, is_verified=True)
                .order_by("-created_at")
                .first()
            )

            if not verified_otp:
                return Response(
                    {"success": False, "error": "Mobile number is not verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create individual fundraiser user
            user = CustomUser.objects.create(
                username=email,  # required by AbstractUser
                fullname=fullname,
                email=email,
                mobile=mobile,
                password=make_password(password),
                user_type=UserType.CSR,
                is_mobile_verified=True,
            )

            refresh = RefreshToken.for_user(user)

            access_token = str(refresh.access_token)
            refresh_token = str(refresh)

            return Response(
                {
                    "success": True,
                    "message": "User registered successfully",
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "user_type": user.user_type.value,
                },
                status=status.HTTP_201_CREATED,
            )

    except IntegrityError:
        return Response(
            {"success": False, "error": "Email or mobile already registered"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, CanCompleteProfile, IsActiveAccount])
def register_individual_profile(request):
    # Implementation for individual fundraiser signup
    user = request.user

    occupation = request.data.get("occupation")
    address = request.data.get("address")
    city = request.data.get("city")
    state = request.data.get("state")
    country = request.data.get("country")
    pincode = request.data.get("pincode")

    try:
        with transaction.atomic():
            # Mandatory field validation
            if not all([occupation, address, city, state, country, pincode]):
                return Response(
                    {"success": False, "error": "All fields are required"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Check if the user exists
            try:
                print("check")
                user_obj = CustomUser.objects.get(uuid=user.uuid)
                print("check2")
            except CustomUser.DoesNotExist:
                return Response(
                    {"success": False, "error": "User not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Check if the user is a INDIVIDUAL_FUNDRAISER
            if user.user_type != UserType.INDIVIDUAL_FUNDRAISER:
                return Response(
                    {
                        "success": False,
                        "error": "Only individual fundraisers can register an individual profile",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            if IndividualProfile.objects.filter(user=user).exists():
                return Response(
                    {"success": False, "error": "Profile already exists"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create Individual profile
            individual_profile = IndividualProfile.objects.create(
                user=user,
                occupation=occupation,
                address=address,
                city=city,
                state=state,
                country=country,
                pincode=pincode,
            )
            print("check4")
            # Update profile status
            user.profile_status = ProfileStatus.PROFILE_COMPLETED
            print("Check5")
            user.save()

            return Response(
                {
                    "success": True,
                    "message": "Fundraiser profile registered successfully",
                },
                status=status.HTTP_201_CREATED,
            )
    except Exception as e:

        import traceback

        traceback.print_exc()

        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, CanCompleteProfile, IsActiveAccount])
def register_ngo_profile(request):
    # Implementation for NGO signup
    user = request.user
    ngo_name = request.data.get("ngo_name")
    ngo_type = request.data.get("ngo_type")
    ngo_reg_num = request.data.get("ngo_reg_num")
    address = request.data.get("address")
    city = request.data.get("city")
    state = request.data.get("state")
    country = request.data.get("country")
    pincode = request.data.get("pincode")
    contact_person_name = request.data.get("contact_person_name")
    contact_person_designation = request.data.get("contact_person_designation")
    website = request.data.get("website")
    print(request.data)
    # Mandatory field validation
    if not all(
        [
            ngo_name,
            ngo_type,
            ngo_reg_num,
            address,
            city,
            state,
            country,
            pincode,
            contact_person_name,
            contact_person_designation,
        ]
    ):
        return Response(
            {"success": False, "error": "All fields are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    print("check1")
    # Check if the user exists
    try:
        user = CustomUser.objects.get(uuid=user.uuid)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    print("check2")
    # Check if the user is a NGO
    if user.user_type != UserType.NGO:
        return Response(
            {"success": False, "error": "Only NGO users can register an NGO profile"},
            status=status.HTTP_403_FORBIDDEN,
        )
    print("check3")
    # Check NGO registration number uniqueness
    if NGOProfile.objects.filter(reg_num=ngo_reg_num).exists():
        return Response(
            {"success": False, "error": "Registration number already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    print("check4")
    ngo_type = request.data.get("ngo_type", "").strip().lower()

    ngo_type_map = {
        "trust": NGOType.TRUST,
        "society": NGOType.SOCIETY,
        "section_8": NGOType.SECTION_8,
        "section 8": NGOType.SECTION_8,
    }

    ngo_type = ngo_type_map.get(ngo_type)

    if ngo_type is None:
        return Response(
            {
                "success": False,
                "error": "Invalid NGO type.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        with transaction.atomic():
            print("check5")
            # Create NGO profile
            ngo_profile = NGOProfile.objects.create(
                user=user,
                ngo_name=ngo_name,
                ngo_type=ngo_type,
                reg_num=ngo_reg_num,
                address=address,
                city=city,
                state=state,
                country=country,
                pincode=pincode,
                contact_person_name=contact_person_name,
                contact_person_designation=contact_person_designation,
                website=website,
            )
            print("check6")
            user.profile_status = ProfileStatus.PROFILE_COMPLETED
            print("check7")
            user.save()
            return Response(
                {"success": True, "message": "NGO registered successfully"},
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated, CanCompleteProfile, IsActiveAccount])
def register_csr_profile(request):
    # Implementation for CSR signup
    user = request.user
    csr_name = request.data.get("csr_name")
    csr_reg_num = request.data.get("csr_reg_num")
    address = request.data.get("address")
    city = request.data.get("city")
    state = request.data.get("state")
    country = request.data.get("country")
    pincode = request.data.get("pincode")
    contact_person_name = request.data.get("contact_person_name")
    contact_person_designation = request.data.get("contact_person_designation")
    website = request.data.get("website")

    # Mandatory field validation
    if not all(
        [
            csr_name,
            csr_reg_num,
            address,
            city,
            state,
            country,
            pincode,
            contact_person_name,
            contact_person_designation,
        ]
    ):
        return Response(
            {"success": False, "error": "All fields are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    print("check2")

    # Check if the user exists
    try:
        user = CustomUser.objects.get(uuid=user.uuid)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "error": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    print("check3")
    # Check if the user is a CSR
    if user.user_type != UserType.CSR:
        return Response(
            {"success": False, "error": "Only CSR users can register a CSR profile"},
            status=status.HTTP_403_FORBIDDEN,
        )
    print("check4")
    # Check CSR registration number uniqueness
    if CSRProfile.objects.filter(csr_reg_num=csr_reg_num).exists():
        return Response(
            {"success": False, "error": "Registration number already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            print("cjeck5")
            # Create CSR profile
            csr_profile = CSRProfile.objects.create(
                user=user,
                csr_name=csr_name,
                csr_reg_num=csr_reg_num,
                address=address,
                city=city,
                state=state,
                country=country,
                pincode=pincode,
                contact_person_name=contact_person_name,
                contact_person_designation=contact_person_designation,
                website=website,
            )
            print("check6")
            user.profile_status = ProfileStatus.PROFILE_COMPLETED
            user.save()
            return Response(
                {"success": True, "message": "CSR registered successfully"},
                status=status.HTTP_201_CREATED,
            )

    except Exception as e:

        import traceback

        traceback.print_exc()
        print("error in api", str(e))
        return Response(
            {"success": False, "error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response(
            {"success": False, "error": "Email and password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Find user by email
    try:
        user = CustomUser.objects.get(email=email)
    except CustomUser.DoesNotExist:
        return Response(
            {"success": False, "error": "Invalid email"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if user.user_type in [UserType.ADMIN, UserType.SUPER_ADMIN]:
        return Response(
            {"success": False, "error": "Please use the Admin Portal."},
            status=status.HTTP_403_FORBIDDEN,
        )

    if not user.check_password(password):
        return Response(
            {"success": False, "error": "Invalid password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if user.status != Status.ACTIVE:
        return Response(
            {
                "success": False,
                "error": "Your account is inactive. Please contact support.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    status_code, success, message = get_login_message(user)

    if not success:
        return Response({"success": False, "error": message}, status=status_code)

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "success": True,
            "message": message,
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        },
        status=status_code,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsActiveAccount])
def change_password(request):

    old_password = request.data.get("old_password")
    new_password = request.data.get("new_password")

    success, message, status_code = change_user_password(
        request.user, old_password, new_password
    )

    if not success:
        return Response({"success": False, "error": message}, status=status_code)

    return Response({"success": True, "message": message}, status=status_code)


@api_view(["GET"])
@permission_classes([IsActiveAccount, IsDonor])
def get_donor_profile(request):

    try:
        user = request.user
        profile = DonorProfile.objects.get(user_id=user)
        
        verification = (
            EntityVerificationRequest.objects.filter(
                user=user,
                verification_type=VerificationType.DONOR,
            )
            .order_by("-created_at")
            .first()
        )

        return Response(
            {
                "success": True,
                "data": {
                    "fullname": user.fullname,
                    "email": user.email,
                    "mobile": user.mobile,
                    "profile_picture": (
                        request.build_absolute_uri(user.profile_picture.url)
                        if user.profile_picture
                        else None
                    ),
                    "verification_remarks": (
                        verification.remarks if verification else ""
                    ),
                    "verification_status": (
                        verification.status.value if verification else None
                    ),
                    "occupation": profile.occupation or "",
                    "address": profile.address or "",
                    "city": profile.city or "",
                    "state": profile.state or "",
                    "country": profile.country or "",
                    "pincode": profile.pincode or "",
                    "profile_status": user.profile_status.value,
                },
            },
            status=status.HTTP_200_OK,
        )

    except DonorProfile.DoesNotExist as u:
        return Response(
            {
                "success": False,
                "error": str(u),
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
@permission_classes([CanEditProfile, IsDonor])
def update_donor_profile(request):
    try:
        user = request.user
        data = request.data

        try:
            profile = DonorProfile.objects.get(user=user)
        except DonorProfile.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Donor profile not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        profile_fields = [
            "occupation",
            "address",
            "city",
            "state",
            "country",
            "pincode",
        ]

        # If updating profile details, require all fields
        if any(field in data for field in profile_fields):

            missing_fields = [field for field in profile_fields if not data.get(field)]

            if missing_fields:
                return Response(
                    {
                        "success": False,
                        "error": f"Missing fields: {', '.join(missing_fields)}",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            profile.occupation = data["occupation"].strip()
            profile.address = data["address"].strip()
            profile.city = data["city"].strip()
            profile.state = data["state"].strip()
            profile.country = data["country"].strip()
            profile.pincode = data["pincode"].strip()

            profile.save()

        # Update fullname independently
        if "fullname" in data:

            fullname = data["fullname"].strip()

            if not fullname:
                return Response(
                    {
                        "success": False,
                        "error": "Full name cannot be empty.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.fullname = fullname

        # Update profile picture independently
        profile_picture = request.FILES.get("profile_picture")

        if profile_picture:
            # Delete old image if it exists
            if user.profile_picture:
                user.profile_picture.delete(save=False)

            user.profile_picture = profile_picture

        user.save()

        return Response(
            {
                "success": True,
                "message": "Donor profile updated successfully.",
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
@permission_classes([IsActiveAccount, IsIndividualFundraiser])
def get_individual_profile(request):
    try:
        user = request.user

        profile = IndividualProfile.objects.get(user=user)
        verification = (
            EntityVerificationRequest.objects.filter(
                user=user,
                verification_type=VerificationType.INDIVIDUAL_FUNDRAISER,
            )
            .order_by("-created_at")
            .first()
        )
        return Response(
            {
                "success": True,
                "data": {
                    "fullname": user.fullname,
                    "email": user.email,
                    "mobile": user.mobile,
                    "profile_picture": (
                        request.build_absolute_uri(user.profile_picture.url)
                        if user.profile_picture
                        else None
                    ),
                    "verification_remarks": (
                        verification.remarks if verification else ""
                    ),
                    "verification_status": (
                        verification.status.value if verification else None
                    ),
                    "occupation": profile.occupation or "",
                    "address": profile.address or "",
                    "city": profile.city or "",
                    "state": profile.state or "",
                    "country": profile.country or "",
                    "pincode": profile.pincode or "",
                    "profile_status": user.profile_status.value,
                },
            },
            status=status.HTTP_200_OK,
        )

    except IndividualProfile.DoesNotExist:
        return Response(
            {
                "success": False,
                "error": "Individual fundraiser profile not found.",
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
@permission_classes([CanCompleteProfile, IsIndividualFundraiser])
def update_individual_profile(request):
    try:
        user = request.user
        data = request.data

        try:
            profile = IndividualProfile.objects.get(user=user)
        except IndividualProfile.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "error": "Individual fundraiser profile not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        profile_fields = [
            "occupation",
            "address",
            "city",
            "state",
            "country",
            "pincode",
        ]

        # If updating profile details, require all fields
        if any(field in data for field in profile_fields):

            missing_fields = [field for field in profile_fields if not data.get(field)]

            if missing_fields:
                return Response(
                    {
                        "success": False,
                        "error": "Occupation, address, city, state, country and pincode are required.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            profile.occupation = data["occupation"].strip()
            profile.address = data["address"].strip()
            profile.city = data["city"].strip()
            profile.state = data["state"].strip()
            profile.country = data["country"].strip()
            profile.pincode = data["pincode"].strip()

            profile.save()

        # Update fullname independently
        fullname = data.get("fullname")

        if fullname is not None:

            fullname = fullname.strip()

            if not fullname:
                return Response(
                    {
                        "success": False,
                        "error": "Full name cannot be empty.",
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.fullname = fullname

        # Update profile picture independently
        if "profile_picture" in data:
            user.profile_picture = data["profile_picture"]

        user.save()

        return Response(
            {
                "success": True,
                "message": "Individual fundraiser profile updated successfully.",
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
@permission_classes([IsActiveAccount])
def get_bank_account(request):

    try:

        bank_account = BankAccount.objects.get(user=request.user)

        return Response(
            {
                "success": True,
                "has_bank_account": True,
                "data": {
                    "account_holder_name": bank_account.account_holder_name,
                    "bank_name": bank_account.bank_name,
                    "account_number": bank_account.account_number,
                    "ifsc_code": bank_account.ifsc_code,
                    "branch_name": bank_account.branch_name or "",
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank_account.cancelled_cheque.url)
                        if bank_account.cancelled_cheque
                        else None
                    ),
                    "verification_status": bank_account.verification_status.value,
                    "remarks": bank_account.remarks or "",
                    "verified_at": (
                        bank_account.verified_at.isoformat()
                        if bank_account.verified_at
                        else None
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

    except BankAccount.DoesNotExist:

        return Response(
            {
                "success": True,
                "has_bank_account": False,
                "data": None,
                "message": "No bank account added yet.",
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


@api_view(["PUT"])
@permission_classes([CanEditProfile])
@transaction.atomic
def update_bank_account(request):
    try:
        user = request.user

        account_holder_name = request.data.get("account_holder_name", "").strip()
        bank_name = request.data.get("bank_name", "").strip()
        account_number = request.data.get("account_number", "").strip()
        ifsc_code = request.data.get("ifsc_code", "").strip().upper()
        branch_name = request.data.get("branch_name", "").strip()
        cancelled_cheque = request.FILES.get("cancelled_cheque")

        # Create if not exists, otherwise update
        bank_account, created = BankAccount.objects.get_or_create(
            user=user,
            defaults={
                "account_holder_name": account_holder_name,
                "bank_name": bank_name,
                "account_number": account_number,
                "ifsc_code": ifsc_code,
                "branch_name": branch_name,
            },
        )

        # Update existing record
        if not created:
            if account_holder_name:
                bank_account.account_holder_name = account_holder_name

            if bank_name:
                bank_account.bank_name = bank_name

            if account_number:
                bank_account.account_number = account_number

            if ifsc_code:
                bank_account.ifsc_code = ifsc_code

            if branch_name:
                bank_account.branch_name = branch_name

        # Upload new cancelled cheque
        if cancelled_cheque:
            bank_account.cancelled_cheque = cancelled_cheque

        # Any modification requires reverification
        bank_account.verification_status = VerificationStatus.PENDING
        bank_account.verified_by = None
        bank_account.verified_at = None
        bank_account.remarks = None

        bank_account.save()

        return Response(
            {
                "success": True,
                "message": (
                    "Bank account created successfully."
                    if created
                    else "Bank account updated successfully."
                ),
                "data": {
                    "account_holder_name": bank_account.account_holder_name,
                    "bank_name": bank_account.bank_name,
                    "account_number": bank_account.account_number,
                    "ifsc_code": bank_account.ifsc_code,
                    "branch_name": bank_account.branch_name,
                    "verification_status": bank_account.verification_status.value,
                    "cancelled_cheque": (
                        request.build_absolute_uri(bank_account.cancelled_cheque.url)
                        if bank_account.cancelled_cheque
                        else None
                    ),
                },
            },
            status=status.HTTP_200_OK,
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
