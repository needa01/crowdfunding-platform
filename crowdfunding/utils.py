import re
import uuid

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from rest_framework import status

from accounts.models import ProfileStatus, Status, UserType


def change_user_password(user, old_password, new_password):
    """
    Change user password after validating old password.
    """

    if not user.check_password(old_password):
        return (
            False,
            "Old password is incorrect",
            status.HTTP_400_BAD_REQUEST
        )

    if user.check_password(new_password):
        return (
            False,
            "New password cannot be same as current password",
            status.HTTP_400_BAD_REQUEST
        )

    try:
        validate_password(new_password, user=user)
    except ValidationError as e:
        return (
            False,
            e.messages,
            status.HTTP_400_BAD_REQUEST
        )

    user.password = make_password(new_password)
    user.save(update_fields=["password"])

    return (
        True,
        "Password changed successfully",
        status.HTTP_200_OK
    )

def get_login_message(user):

    if(user.status == Status.SUSPENDED):
        return (status.HTTP_403_FORBIDDEN, False, "Account suspended. Please Contact Support.")

    return (status.HTTP_200_OK, True,"Login Successful")

def generate_donation_number():
    return f"DON-{uuid.uuid4().hex[:12].upper()}"

def generate_receipt_number():
    return f"RCPT-{uuid.uuid4().hex[:12].upper()}"

def generate_withdrawal_reference():
    return f"WDL-{uuid.uuid4().hex[:12].upper()}"

@property
def display_name(self):
    if self.user_type == UserType.NGO and hasattr(self, "ngo_profile"):
        return self.ngo_profile.ngo_name

    if self.user_type == UserType.CSR and hasattr(self, "csr_profile"):
        return self.csr_profile.csr_name

    return self.fullname


