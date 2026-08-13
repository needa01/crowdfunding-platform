from django.urls import path

from organizations.views import get_csr_profile, get_ngo_profile, update_csr_profile, update_ngo_profile



urlpatterns = [
    
    # get profile details url
    path("ngo-profile", get_ngo_profile, name="get-ngo-profile"),
    path("csr-profile", get_csr_profile, name="get-csr-profile"),
    
    # update profile urls
    path("ngo-profile/update", update_ngo_profile, name="update-ngo-profile"),
    path("csr-profile/update", update_csr_profile,name="update-csr-profile",),
]
