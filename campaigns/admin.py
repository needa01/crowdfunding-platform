from django.contrib import admin

from .models import (
    Campaign,
    CampaignPromotionServiceTypes,
    CampaignPromotionService,
)


@admin.register(Campaign)
class CampaignAdmin(admin.ModelAdmin):
    list_display = (
        "campaign_name",
        "created_by",
        "display_campaign_type",
        "display_campaign_status",
        "goal_amount",
        "raised_amount",
        "total_donors",
        "is_deleted",
        "start_date",
        "end_date",
        "created_at",
    )

    list_filter = (
        "campaign_type",
        "campaign_status",
        "beneficiary_type",
        "cause",
        "is_deleted",
        "start_date",
        "end_date",
    )

    search_fields = (
        "campaign_name",
        "campaign_slug",
        "created_by__fullname",
        "created_by__email",
        "created_by__mobile",
        "beneficiary_name",
        "beneficiary_mobile",
        "hospital_name",
    )

    readonly_fields = (
        "uuid",
        "raised_amount",
        "total_charges",
        "amount_withdrawn",
        "total_donors",
        "total_views",
        "created_at",
        "updated_at",
    )


    autocomplete_fields = (
        "created_by",
        "ngo",
    )

    ordering = ("-created_at",)

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "uuid",
                    "created_by",
                    "campaign_type",
                    "ngo",
                    "campaign_name",
                    "campaign_slug",
                    "campaign_desc",
                    "cover_photo",
                )
            },
        ),
        (
            "Financial Information",
            {
                "fields": (
                    "goal_amount",
                    "raised_amount",
                    "total_charges",
                    "amount_withdrawn",
                )
            },
        ),
        (
            "Beneficiary",
            {
                "fields": (
                    "beneficiary_type",
                    "beneficiary_group_type",
                    "beneficiary_name",
                    "beneficiary_relation",
                    "beneficiary_mobile",
                    "beneficiary_member_count",
                    "beneficiary_location",
                    "beneficiary_age",
                )
            },
        ),
        (
            "Cause / Medical Information",
            {
                "fields": (
                    "cause",
                    "hospital_name",
                    "hospital_location",
                    "ailment",
                )
            },
        ),
        (
            "Campaign Status",
            {
                "fields": (
                    "campaign_status",
                    "is_deleted",
                )
            },
        ),
        (
            "Statistics",
            {
                "fields": (
                    "total_donors",
                    "total_views",
                )
            },
        ),
        (
            "Dates",
            {
                "fields": (
                    "start_date",
                    "end_date",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    
    @admin.display(description="Campaign Status")
    def display_campaign_status(self, obj):
        value = obj.campaign_status
    
        print("CURRENCY:", value)
        print("TYPE:", type(value))
    
        if value is None:
            return "-"
    
        if hasattr(value, "value"):
            return value.value
    
        return str(value)
    
    @admin.display(description="Campaign Type")
    def display_campaign_type(self, obj):
        value = obj.campaign_type
    
        print("CURRENCY:", value)
        print("TYPE:", type(value))
    
        if value is None:
            return "-"
    
        if hasattr(value, "value"):
            return value.value
    
        return str(value)


@admin.register(CampaignPromotionServiceTypes)
class CampaignPromotionServiceTypesAdmin(admin.ModelAdmin):
    list_display = (
        "display_service_name",
        "minimum_amount",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "service_name",
        "is_active",
    )

    search_fields = (
        "service_name",
    )

    readonly_fields = (
        "uuid",
        "created_at",
        "updated_at",
    )

    ordering = (
        "service_name",
    )
    

    @admin.display(description="Service Type")
    def display_service_name(self, obj):
        value = obj.service_name
    
        if value is None:
            return "-"
    
        if hasattr(value, "value"):
            return value.value
    
        return str(value)
    



@admin.register(CampaignPromotionService)
class CampaignPromotionServiceAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "service_type",
        "amount",
        "fee",
        "tax",
        "display_currency",
        "display_promotion_status",
        "created_at",
    )

    list_filter = (
        "service_type",
        "promotion_status",
        "currency",
        "created_at",
    )

    search_fields = (
        "campaign__campaign_name",
        "campaign__campaign_slug",
        "campaign__created_by__fullname",
        "campaign__created_by__email",
    )

    autocomplete_fields = (
        "campaign",
        "service_type",
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
            "Promotion",
            {
                "fields": (
                    "uuid",
                    "campaign",
                    "service_type",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "amount",
                    "fee",
                    "tax",
                    "currency",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "promotion_status",
                    "user_notes",
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
    
    @admin.display(description="Currency")
    def display_currency(self, obj):
        value = obj.currency

        print("CURRENCY:", value)
        print("TYPE:", type(value))

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)

    @admin.display(description="Promotion Status")
    def display_promotion_status(self, obj):
        value = obj.promotion_status

        if value is None:
            return "-"

        if hasattr(value, "value"):
            return value.value

        return str(value)
