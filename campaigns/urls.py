from django.urls import path

from campaigns.views import (
    campaign_detail,
    campaign_list,
    create_campaign,
    get_campaign_donations,
    get_my_campaigns,
    my_campaign_detail,
    update_campaign,
    get_promotion_services,
    create_campaign_promotion_payment,
)

urlpatterns = [
    path("get-campaigns", campaign_list, name="campaign_list"),
    path("my-campaigns", get_my_campaigns, name="my-campaign_list"),
    path(
        "get-campaign-services", get_promotion_services, name="get_promotion_services"
    ),
    path("create-campaign", create_campaign, name="create-campaign"),
    path(
        "create-campaign-promotion",
        create_campaign_promotion_payment,
        name="create_campaign_promotion_payment",
    ),
    path(
        "update-campaigns/<slug:campaign_slug>",
        update_campaign,
        name="update-campaign",
    ),
    path(
        "campaign/<slug:campaign_slug>",
        campaign_detail,
        name="campaign-detail",
    ),
    path(
        "my-campaign/<slug:campaign_slug>",
        my_campaign_detail,
        name="my-campaign-detail",
    ),
    path(
        "<slug:campaign_slug>/donations",
        get_campaign_donations,
        name="campaign-donations",
    ),
]
