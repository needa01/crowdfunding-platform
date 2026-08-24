from django.urls import path

from . import views

urlpatterns = [
    
    path(
        "razorpay-callback/campaign-donation",
        views.donation_razorpay_callback,
        name="donation_razorpay_callback",
    ),
    path(
        "razorpay-callback/platform-donation",
        views.platform_donation_razorpay_callback,
        name="platform_donation_razorpay_callback",
    ),
    path(
        "razorpay-callback/campaign_promotion",
        views.campaign_promotion_razorpay_callback,
        name="campaign_promotion_razorpay_callback"
    ),
    
]
