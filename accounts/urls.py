from django.urls import path

from .views import change_password, get_bank_account, get_donor_profile, get_individual_profile, get_user_info, login, register_csr_profile, register_individual_profile, register_ngo_profile, send_otp, signup_as_csr,  signup_as_indi_fundraiser, signup_as_donor, signup_as_ngo, update_bank_account, update_donor_profile, update_individual_profile, verify_otp

urlpatterns = [
    #user info api
    path("get-user-info", get_user_info, name="get_user_info"),
    
    #otp urls
    path("send-otp", send_otp, name="send_otp"),
    path("verify-otp", verify_otp, name="verify_otp"),
    
    #signup urls
    path("signup/donor", signup_as_donor, name="signup_as_donor"),
    path("signup/individual_fundraiser", signup_as_indi_fundraiser, name="signup_as_indi_fundraiser"),
    path("signup/ngo", signup_as_ngo, name="signup_as_ngo"),
    path("signup/csr", signup_as_csr, name="signup_as_csr"),
    
    #register urls
    path("register/individual_fundraiser", register_individual_profile, name="register_individual"),
    path("register/ngo", register_ngo_profile, name="register_ngo"),
    path("register/csr", register_csr_profile, name="register_csr"),
    
    #get profile details url
    path("donor-profile",get_donor_profile,name="get-donor-profile"),
    path("fundraiser-profile",get_individual_profile,name="get-individual-profile"),
    
    #update profile urls
    path("donor-profile/update", update_donor_profile,name="update-donor-profile"),
    path("fundraiser-profile/update", update_individual_profile, name="update-donor-profile"),
    
    #bank account urls
    path("bankaccount", get_bank_account, name="get-bank-account"),
    path("bankaccount/update", update_bank_account, name="update-bank-account"),
    
    
    #login and change password urls
    path("login", login, name="login"),
    path("change-password", change_password, name="change_user_password")
]