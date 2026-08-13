from django.urls import path

from admin_panel.serializers import CreateAdminSerializer
from admin_panel.views import admin_dashboard, admin_login, create_admin, delete_admin, get_admins, get_csr_for_verification, get_donor_for_verification, get_fundraiser_for_verification, get_campaign_for_verification, get_ngo_for_verification, get_users

urlpatterns = [
    path("login", admin_login, name="admin_login"),
    path("dashboard", admin_dashboard, name="admin_dashboard"),
    path("get-users", get_users, name="get_users"),
    path("get-admins", get_admins, name="get_admins"),
    path("donor/<uuid:user_id>", get_donor_for_verification, name="admin-get-donor"),
    path("fundraiser/<uuid:user_id>", get_fundraiser_for_verification, name="admin-get-fundraiser"),
    path("ngo/<uuid:user_id>", get_ngo_for_verification, name="admin-get-ngo"),
    path("csr/<uuid:user_id>", get_csr_for_verification, name="admin-get-csr"),
    path("campaign/<slug:campaign_slug>", get_campaign_for_verification, name="admin-get-campaign"),
    path("create", create_admin, name="create_admin"),
    path("delete/<uuid:admin_uuid>", delete_admin, name="delete_admin"),
]