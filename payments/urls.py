from django.urls import path

from . import views

urlpatterns = [
    path(
        "verify",
        views.verify_payment,
        name="verify_payment",
    ),
    path(
        "status/<uuid:transaction_uuid>",
        views.payment_status,
        name="payment_status",
    ),
    path(
        "razorpay-callback/campaign-donation",
        views.donation_razorpay_callback,
        name="donation_razorpay_callback",
    ),
    path(
        "razorpay-callback/campaign_promotion",
        views.campaign_promotion_razorpay_callback,
        name="campaign_promotion_razorpay_callback"
    ),
    
]
