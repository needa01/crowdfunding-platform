from django.contrib import admin

# Register your models here.
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import DonorProfile, IndividualProfile,CustomUser



@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    # =========================================================
    # LIST PAGE
    # =========================================================

    list_display = (
        "mobile",
        "fullname",
        "email",
        "display_user_type",
        "display_status",
        "is_mobile_verified",
        "is_staff",
        "is_active",
        "created_at",
    )

    list_filter = (
        "user_type",
        "status",
        "profile_status",
        "is_mobile_verified",
        "is_staff",
        "is_active",
        "is_superuser",
        "is_deleted",
    )

    search_fields = (
        "mobile",
        "fullname",
        "email",
        "uuid",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
        "last_login_at",
        "deleted_at",
    )

    # =========================================================
    # EDIT USER PAGE
    # =========================================================

    fieldsets = (
        (
            "Account Information",
            {
                "fields": (
                    "uuid",
                    "mobile",
                    "email",
                    "password",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "fullname",
                    "profile_picture",
                )
            },
        ),
        (
            "User Classification",
            {
                "fields": (
                    "user_type",
                    "status",
                    "profile_status",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "is_mobile_verified",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Account Dates",
            {
                "fields": (
                    "last_login",
                    "last_login_at",
                    "created_at",
                    "updated_at",
                    "is_deleted",
                    "deleted_at",
                )
            },
        ),
    )

    # =========================================================
    # ADD USER PAGE
    # =========================================================

    add_fieldsets = (
        (
            "Account Information",
            {
                "classes": ("wide",),
                "fields": (
                    "mobile",
                    "email",
                    "password1",
                    "password2",
                ),
            },
        ),
        (
            "Personal Information",
            {
                "classes": ("wide",),
                "fields": (
                    "fullname",
                    "user_type",
                ),
            },
        ),
    )
    
    @admin.display(description="User Type")
    def display_user_type(self, obj):
        value = obj.user_type

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Status")
    def display_status(self,obj):
        value = obj.status
    
        if value is None:
            return "-"
    
        if hasattr(value, "value"):
            return value.value
    
        return str(value)




@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "user",
        "occupation",
        "city",
        "state",
        "country",
        "pincode",
    )

    search_fields = (
        "user__fullname",
        "user__email",
        "user__mobile",
        "occupation",
        "city",
        "state",
        "country",
        "pincode",
    )

    list_filter = (
        "country",
        "state",
        "city",
    )

    readonly_fields = ("uuid",)


@admin.register(IndividualProfile)
class IndividualProfileAdmin(admin.ModelAdmin):
    list_display = (
        "uuid",
        "user",
        "occupation",
        "city",
        "state",
        "country",
        "pincode",
    )

    search_fields = (
        "user__fullname",
        "user__email",
        "user__mobile",
        "occupation",
        "city",
        "state",
        "country",
        "pincode",
    )

    list_filter = (
        "country",
        "state",
        "city",
    )

    readonly_fields = ("uuid",)


from django.contrib import admin

from .models import BankAccount


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):

    list_display = (
        "account_holder_name",
        "bank_name",
        "display_account_number",
        "display_account_type",
        "ifsc_code",
        "display_verification_status",
        "verified_by",
        "verified_at",
        "created_at",
    )

    list_filter = (
        "account_type",
        "verification_status",
        "bank_name",
        "created_at",
        "verified_at",
    )

    search_fields = (
        "account_holder_name",
        "bank_name",
        "account_number",
        "ifsc_code",
        "branch_name",
        "user__fullname",
        "user__email",
        "user__mobile",
        "remarks",
    )

    autocomplete_fields = (
        "user",
        "verified_by",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    ordering = (
        "-created_at",
    )

    fieldsets = (
        (
            "Account Holder",
            {
                "fields": (
                    "uuid",
                    "user",
                    "account_holder_name",
                )
            },
        ),
        (
            "Bank Details",
            {
                "fields": (
                    "bank_name",
                    "account_number",
                    "account_type",
                    "ifsc_code",
                    "branch_name",
                    "cancelled_cheque",
                )
            },
        ),
        (
            "Verification",
            {
                "fields": (
                    "verification_status",
                    "verified_by",
                    "verified_at",
                    "remarks",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="Account Number")
    def display_account_number(self, obj):
        if not obj.account_number:
            return "-"

        account_number = str(obj.account_number)

        if len(account_number) <= 4:
            return "****"

        return f"{'*' * (len(account_number) - 4)}{account_number[-4:]}"

    @admin.display(description="Account Type")
    def display_account_type(self, obj):
        value = obj.account_type

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Verification Status")
    def display_verification_status(self, obj):
        value = obj.verification_status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)