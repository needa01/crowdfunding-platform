from django.contrib import admin

from .models import NGOProfile, CSRProfile


@admin.register(NGOProfile)
class NGOProfileAdmin(admin.ModelAdmin):
    list_display = (
        "ngo_name",
        "display_ngo_type",
        "reg_num",
        "user",
        "contact_person_name",
        "contact_person_designation",
        "city",
        "state",
        "country",
        "created_at",
    )

    search_fields = (
        "ngo_name",
        "reg_num",
        "user__fullname",
        "user__email",
        "user__mobile",
        "contact_person_name",
        "city",
        "state",
        "country",
    )

    list_filter = (
        "ngo_type",
        "country",
        "state",
        "city",
        "created_at",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "user",
    )

    ordering = ("-created_at",)

    fieldsets = (
        (
            "NGO Information",
            {
                "fields": (
                    "uuid",
                    "user",
                    "ngo_name",
                    "ngo_type",
                    "reg_num",
                )
            },
        ),
        (
            "Contact Person",
            {
                "fields": (
                    "contact_person_name",
                    "contact_person_designation",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "city",
                    "state",
                    "country",
                    "pincode",
                )
            },
        ),
        (
            "Website",
            {
                "fields": (
                    "website",
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
    
    @admin.display(description="NGO Type")
    def display_ngo_type(self, obj):
        value = obj.ngo_type
        
        if value is None:
            return "-"
        
        if hasattr(value, "value"):
            return value.value
    
        return str(value)


@admin.register(CSRProfile)
class CSRProfileAdmin(admin.ModelAdmin):
    list_display = (
        "csr_name",
        "csr_reg_num",
        "user",
        "contact_person_name",
        "contact_person_designation",
        "city",
        "state",
        "country",
        "created_at",
    )

    search_fields = (
        "csr_name",
        "csr_reg_num",
        "user__fullname",
        "user__email",
        "user__mobile",
        "contact_person_name",
        "city",
        "state",
        "country",
    )

    list_filter = (
        "country",
        "state",
        "city",
        "created_at",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "user",
    )

    ordering = ("-created_at",)

    fieldsets = (
        (
            "CSR Information",
            {
                "fields": (
                    "uuid",
                    "user",
                    "csr_name",
                    "csr_reg_num",
                )
            },
        ),
        (
            "Contact Person",
            {
                "fields": (
                    "contact_person_name",
                    "contact_person_designation",
                )
            },
        ),
        (
            "Address",
            {
                "fields": (
                    "address",
                    "city",
                    "state",
                    "country",
                    "pincode",
                )
            },
        ),
        (
            "Website",
            {
                "fields": (
                    "website",
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