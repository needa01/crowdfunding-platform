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