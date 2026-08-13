from django.urls import path

from . import views

urlpatterns = [

    path(
        "verify",
        views.verify_payment,
        name="verify_payment",
    ),

]