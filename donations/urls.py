from django.urls import path

from . import views

urlpatterns = [

    path(
        "create-donation",
        views.create_campaign_donation,
        name="create_campaign_donation",
    ),

    path(
        "my-donations",
        views.get_my_donations,
        name="my_donations",
    ),

    path(
        "<uuid:donation_uuid>",
        views.get_donation_details,
        name="get_donation_details",
    ),
    
    path(
        "<uuid:donation_uuid>/generate-receipt/",
        views.generate_receipt,
        name="generate_receipt"
    ),
    
    path(
        "<uuid:donation_uuid>/download-receipt/",
        views.download_receipt,
        name="download_receipt"
    ),

    # path(
    #     "<uuid:donation_uuid>/receipt",
    #     views.download_receipt,
    #     name="download_receipt",
    # ),

]