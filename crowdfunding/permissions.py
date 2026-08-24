from rest_framework.permissions import BasePermission

from crowdfunding.enums import (
    ProfileStatus,
    Status,
    UserType,
    VerificationStatus,
    VerificationType,
)
from verification.models import EntityVerificationRequest


class IsActiveAccount(BasePermission):

    def has_permission(self, request, view):

        user = request.user
        return user.is_authenticated and user.status == Status.ACTIVE


class CanCompleteProfile(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        return (
            user.is_authenticated
            and user.status == Status.ACTIVE
            and (
                user.user_type == UserType.DONOR
                or user.profile_status
                in [
                    ProfileStatus.BASIC_INFO,
                    ProfileStatus.PROFILE_COMPLETED,
                    ProfileStatus.VERIFICATION_PENDING,
                    ProfileStatus.VERIFIED,
                ]
            )
        )


class CanManageDocuments(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        return (
            user.is_authenticated
            and user.status == Status.ACTIVE
            and user.profile_status
            in [ProfileStatus.PROFILE_COMPLETED, ProfileStatus.VERIFICATION_REJECTED]
        )


class CanEditProfile(BasePermission):
    message = (
        "Your profile cannot be edited at this stage. "
        "Profiles can only be edited when the profile is completed or verification has been rejected."
    )

    def has_permission(self, request, view):

        user = request.user

        return (
            user.is_authenticated
            and user.status == Status.ACTIVE
            and user.profile_status
            in [ProfileStatus.PROFILE_COMPLETED, ProfileStatus.VERIFICATION_REJECTED]
        )


class CanDonate(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        if not user.is_authenticated:
            return False

        if user.status != Status.ACTIVE:
            return False

        if user.user_type == UserType.DONOR:
            return True

        return user.profile_status in [
            ProfileStatus.BASIC_INFO,
            ProfileStatus.PROFILE_COMPLETED,
            ProfileStatus.VERIFIED,
            ProfileStatus.VERIFICATION_PENDING,
            ProfileStatus.VERIFICATION_REJECTED,
        ]


class IsProfileApproved(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        if not user.is_authenticated:
            return False

        if user.status != Status.ACTIVE:
            return False

        if user.user_type == UserType.DONOR:
            return True

        return user.profile_status == ProfileStatus.VERIFIED


class IsSuperAdmin(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        return user.is_authenticated and user.user_type == UserType.SUPER_ADMIN


class IsPlatformAdmin(BasePermission):

    def has_permission(self, request, view):

        user = request.user

        return user.is_authenticated and user.user_type in [
            UserType.ADMIN,
            UserType.SUPER_ADMIN,
        ]


class IsDonor(BasePermission):

    def has_permission(self, request, view):
        print("Is DOnor")
        print("user", request.user.user_type)
        return (
            request.user.is_authenticated and request.user.user_type == UserType.DONOR
        )


class IsIndividualFundraiser(BasePermission):

    def has_permission(self, request, view):

        return (
            request.user.is_authenticated
            and request.user.user_type == UserType.INDIVIDUAL_FUNDRAISER
        )


class IsNGO(BasePermission):

    def has_permission(self, request, view):

        return request.user.is_authenticated and request.user.user_type == UserType.NGO


class IsCSR(BasePermission):

    def has_permission(self, request, view):

        return request.user.is_authenticated and request.user.user_type == UserType.CSR


class IsCampaignCreator(BasePermission):
    print("p enter")
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view):
        user = request.user
        print("p enter2")

        if not user.is_authenticated:
            self.message = "Authentication credentials were not provided."
            return False
        print("p enter3")

        if user.user_type == UserType.NGO:
            verification_type = VerificationType.NGO
            print("p enter4")
        

        elif user.user_type == UserType.INDIVIDUAL_FUNDRAISER:
            verification_type = VerificationType.INDIVIDUAL_FUNDRAISER
            print("p enter5")
            

        else:
            self.message = "You do not have permission to perform this action."
            return False

        is_verified = EntityVerificationRequest.objects.filter(
            user=user,
            verification_type=verification_type,
            status=VerificationStatus.APPROVED,
        ).exists()
        print("p enter6")

        if not is_verified:
            self.message = "Please verify your profile first."
            return False
        
        print("p enter7")

        return True
