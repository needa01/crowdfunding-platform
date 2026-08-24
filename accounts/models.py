from datetime import timedelta
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.core.validators import MinLengthValidator, RegexValidator
from django.core.exceptions import ValidationError
from django_enum.fields import EnumField
from crowdfunding.enums import (
    AccountType,
    KYC_Status,
    ProfileStatus,
    Status,
    UserType,
    VerificationStatus,
)


class CustomUser(AbstractUser):

    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)

    fullname = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)

    mobile = models.CharField(
        max_length=10,
        unique=True,
        validators=[
            RegexValidator(r"^\d+$", "Only digits are allowed."),
            MinLengthValidator(10),
        ],
    )

    is_mobile_verified = models.BooleanField(default=False)

    # profile_picture = models.URLField(null=True, blank=True)
    profile_picture = models.FileField(
        upload_to="documents/profile/%Y/%m/", null=True, blank=True
    )

    user_type = EnumField(UserType, default=UserType.DONOR)

    last_login_at = models.DateTimeField(null=True, blank=True)

    status = EnumField(Status, default=Status.ACTIVE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    profile_status = EnumField(ProfileStatus, default=ProfileStatus.BASIC_INFO)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "User"
        verbose_name = "User"
        verbose_name_plural = "User"

    def __str__(self):
        return self.fullname

    @property
    def display_name(self):
        if self.user_type == UserType.NGO and hasattr(self, "ngo_profile"):
            return self.ngo_profile.ngo_name

        if self.user_type == UserType.CSR and hasattr(self, "csr_profile"):
            return self.csr_profile.csr_name

        return self.fullname


class DonorProfile(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    occupation = models.CharField(max_length=100, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    country = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)

    class Meta:
        db_table = "donor_profile"
        verbose_name = "Donor Profile"
        verbose_name_plural = "Donor Profiles"
    
    def __str__(self):
        return f"{self.user.fullname ({self.user.user_type})}"


class IndividualProfile(models.Model):
    uuid = models.UUIDField(default=uuid.uuid4, primary_key=True, editable=False)
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name="individual_profile")
    occupation = models.CharField(max_length=100, null=True, blank=True)

    address = models.TextField()
    city = models.CharField(max_length=255)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pincode = models.CharField(max_length=10)

    class Meta:
        db_table = "individual_fundraiser_profile"
        verbose_name = "Indivdual Fundraiser Profile"
        verbose_name_plural = "Individual Fundraiser Profiles"
    
    def __str__(self):
           return f"{self.user.fullname ({self.user.user_type})}" 


class OTP(models.Model):
    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    mobile = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(r"^\d+$", "Only digits are allowed."),
            MinLengthValidator(10),
        ],
    )

    otp = models.CharField(max_length=6)

    request_id = models.CharField(max_length=255, null=True, blank=True)

    is_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "otp"
        verbose_name = "OTP"
        verbose_name_plural = "OTP"

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)


class BankAccount(models.Model):

    uuid = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        CustomUser, on_delete=models.CASCADE, related_name="bank_account"
    )

    account_holder_name = models.CharField(max_length=255)

    bank_name = models.CharField(max_length=255)

    account_number_validator = RegexValidator(
        regex=r"^\d{9,18}$",
        message="Account number must contain only digits and be between 9 and 18 digits long.",
    )

    account_number = models.CharField(
        max_length=18,
        validators=[account_number_validator],
    )
    
    account_type = EnumField(AccountType, default=AccountType.SAVINGS)

    ifsc_validator = RegexValidator(
        regex=r"^[A-Z]{4}0[A-Z0-9]{6}$",
        message="Enter a valid IFSC code (e.g. SBIN0001234).",
    )

    ifsc_code = models.CharField(
        max_length=11,
        validators=[ifsc_validator],
    )

    branch_name = models.CharField(max_length=255, null=True)


    cancelled_cheque = models.FileField(
        upload_to="documents/bank/cancelled-cheques/%Y/%m/",
        null=True,
        blank=True,
    )

    verification_status = EnumField(
        VerificationStatus, default=VerificationStatus.PENDING
    )

    verified_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_bank_accounts",
    )

    verified_at = models.DateTimeField(null=True, blank=True)

    remarks = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "bank_account"
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"

    def __str__(self):
        return f"{self.account_holder_name} - {self.bank_name}"

    def clean(self):
        errors = {}

        if (
            self.verification_status == VerificationStatus.APPROVED
            and not self.cancelled_cheque
        ):
            errors["cancelled_cheque"] = "Cancelled cheque is required."

        if self.user and not self.user.is_active:
            errors["user"] = "User is inactive."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.ifsc_code:
            self.ifsc_code = self.ifsc_code.upper()

        self.full_clean()
        super().save(*args, **kwargs)
