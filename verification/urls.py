from django.urls import path

from .views import (
    delete_document,
    get_campaign_documents,
    get_document_types,
    get_profile_documents,
    submit_campaign_verification,
    verify_campaign,
    verify_campaign_bank_account,
    verify_document,
    verify_bankaccount,
)

from . import views

urlpatterns = [
    path("campaign/documents", get_campaign_documents, name="get-campaign-docs"),
    path("profile/documents", get_profile_documents, name="get-profile-docs"),
    path(
        "profile/document/upload",
        views.upload_profile_document,
        name="upload-profile-docs",
    ),
    path(
        "campaign/document/upload",
        views.upload_campaign_document,
        name="upload-campaign-docs",
    ),
    path(
        "profile/submit",
        views.submit_profile_verification,
        name="submit-profile-verification",
    ),
    path(
        "campaign/submit",
        submit_campaign_verification,
        name="submit-campaign-verification",
    ),
    path("documents/<uuid:uuid>/verify", verify_document, name="verify-document"),
    path(
        "documents/<uuid:document_uuid>/delete",
        delete_document,
        name="delete_document",
    ),
    path("bankaccount/verify", verify_bankaccount, name="verify_bankaccount"),
    path("campaign/bankaccount/verify", verify_campaign_bank_account, name="verify_campaign_bank_account"),
    path("profile/verify", views.verify_profile, name="verify-profile"),
    path("campaign/verify", verify_campaign, name="verify-campaign"),
    path("document-types", get_document_types, name="get-document-types"),
]
