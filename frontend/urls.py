from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login", views.login_page, name="login"),
    path("change-password", views.change_password, name="change-password"),
    path("campaigns", views.campaigns, name="campaigns"),
    # signup urls
    path("signup/donor", views.donor_signup, name="donor_signup"),
    path("signup/fundraiser", views.fundraiser_signup, name="fundraiser_signup"),
    path("signup/ngo", views.ngo_signup, name="ngo_signup"),
    path("signup/csr", views.csr_signup, name="csr_signup"),
    # register urls
    path("register/fundraiser", views.register_fundraiser, name="fundraiser_register"),
    path("register/ngo", views.register_ngo, name="ngo_register"),
    path("register/csr", views.register_csr, name="csr_register"),
    # profile urls
    path("profile/donor", views.donor_profile, name="donor_profile"),
    path("profile/fundraiser", views.fundraiser_profile, name="fundraiser_profile"),
    path("profile/ngo", views.ngo_profile, name="ngo_profile"),
    path("profile/csr", views.csr_profile, name="csr_profile"),
    # my-campaign url
    path("profile/my-campaigns", views.my_campaigns, name="my_campaigns"),
    # detailed campaign page
    path(
        "campaign/<slug:campaign_slug>", views.campaign_detail, name="detail_campaign"
    ),
    path("profile/my-campaign", views.my_campaign_detail, name="my_detail_campaign"),
    path("campaign/promote/<slug:campaign_slug>", views.campaign_promotion_view, name="campaign_promotion_view"),
    # create campaign page for individual fundraiser and ngo
    path(
        "fundraiser/create-campaign/",
        views.create_fundraiser_crowdfunding_campaign_view,
        name="create_fundraiser_campaign",
    ),
    path(
        "ngo/create-campaign/crowdfunding",
        views.create_ngo_crowdfunding_campaign_view,
        name="create_ngo_crowdfunding_campaign",
    ),
    path(
        "ngo/create-campaign/csr",
        views.create_ngo_csr_campaign_view,
        name="create_ngo_csr_campaign",
    ),
    # donation urls
    path(
        "campaign/<slug:campaign_slug>/donate",
        views.create_campaign_donation,
        name="create_campaign_donation",
    ),
    path(
        "platform/donate",
        views.create_platform_donation,
        name="create_platform_donation",
    ),
    path(
        "my-donations",
        views.my_donations,
        name="my_donations",
    ),
    path(
        "donations/<uuid:donation_uuid>",
        views.get_donation_details,
        name="get_donation_details",
    ),
    # payment urls
    path(
        "donation/success",
        views.donation_success_page,
        name="donation_success",
    ),
    path(
            "payment/success",
            views.payment_success_page,
            name="payment_success",
        ),
        
    
    # admin urls
    path("admin/login", views.admin_login_view, name="admin_login"),
    path("admin/dashboard", views.admin_dashboard_view, name="admin_dashboard"),
    path("admin/donor-management", views.admin_donors_view, name="admin_donors"),
    path("admin/ngo-management", views.admin_ngos_view, name="admin_ngos"),
    path("admin/csr-management", views.admin_csrs_view, name="admin_csrs"),
    path(
        "admin/fundraiser-management",
        views.admin_fundraiser_view,
        name="admin_indi_fundraisers",
    ),
    path(
        "admin/campaign-management", views.admin_campaigns_view, name="admin_campaigns"
    ),
    path("admin/admin-management", views.admin_admins_view, name="admin_admins"),
    path("admin/create-admin", views.admin_create_view, name="admin_create"),
    path(
        "admin/donor-verification/<uuid:user_uuid>",
        views.admin_donor_verification_view,
        name="admin_donor_verification",
    ),
    path(
        "admin/fundraiser-verification/<uuid:user_uuid>",
        views.admin_fundraiser_verification_view,
        name="admin_fundraiser_verification",
    ),
    path(
        "admin/ngo-verification/<uuid:user_uuid>",
        views.admin_ngo_verification_view,
        name="admin_ngo_verification",
    ),
    path(
        "admin/csr-verification/<uuid:user_uuid>",
        views.admin_csr_verification_view,
        name="admin_csr_verification",
    ),
    path(
        "admin/campaign-verification/<slug:campaign_slug>",
        views.admin_campaign_verification_view,
        name="admin_campaign_verification",
    ),
]
