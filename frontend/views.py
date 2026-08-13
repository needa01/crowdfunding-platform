from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def home(request):
    return render(request, "index.html")

def login_page(request):
    return render(request, 'login.html')

def campaigns(request):
    return render(request, 'campaigns/campaigns.html')

#signup views
def donor_signup(request):
    return render(request, 'signup/donor.html')

def fundraiser_signup(request):
    return render(request, 'signup/fundraiser.html')

def ngo_signup(request):
    return render(request, 'signup/ngo.html')

def csr_signup(request):
    return render(request, 'signup/csr.html')


#profile views
def donor_profile(request):
    return render(request, 'profile/donor.html')

def fundraiser_profile(request):
    return render(request, 'profile/fundraiser.html')

def ngo_profile(request):
    return render(request, 'profile/ngo.html')

def csr_profile(request):
    return render(request, 'profile/csr.html')

#my campaigns views
def my_campaigns(request):
    return render(request, 'campaigns/my_campaigns.html')

#detailed campaign view
def campaign_detail(request, campaign_slug):
    return render(
        request,
        "campaigns/campaign-detail.html",
        {
            "campaign_slug": campaign_slug,
        },
    )

#detailed campaign view
def my_campaign_detail(request):
    return render(request, 'campaigns/my-campaign-detail.html')



#register views
def register_fundraiser(request):
    return render(request, 'register/register_fundraiser.html')

def register_ngo(request):
    return render(request, 'register/register_ngo.html')

def register_csr(request):
    return render(request, 'register/register_csr.html')

#create campaign page
def create_fundraiser_crowdfunding_campaign_view(request):
    return render(request, 'campaigns/crowdfunding/create-campaign.html')


def create_ngo_crowdfunding_campaign_view(request):
    return render(request, 'campaigns/ngo-crowdfunding/create-campaign.html')


def create_ngo_csr_campaign_view(request):
    return render(request, 'campaigns/csr/create-campaign.html')


#donation views
def create_campaign_donation(request, campaign_slug):
    print("Frontend view")
    return render(
        request,
        "donation/donate.html",
        {
            "campaign_slug": campaign_slug,
        },
    )
    
def my_donations(request):
    return render(request, 'donation/my-donations.html')

def get_donation_details(request, donation_uuid):
    return render(
        request,
        "donation/donation-details.html",
        {
            "donation_uuid": donation_uuid,
        },
    )

#admin views
def admin_login_view(request):
    return render(request, 'platform_admin/login.html')



def admin_dashboard_view(request):
    return render(request, 'platform_admin/dashboard.html')



def admin_donors_view(request):
    return render(request, 'platform_admin/management/donors.html')

def admin_ngos_view(request):
    return render(request, 'platform_admin/management/ngos.html')

def admin_csrs_view(request):
    return render(request, 'platform_admin/management/csrs.html')

def admin_fundraiser_view(request):
    return render(request, 'platform_admin/management/indi_fundraisers.html')

def admin_campaigns_view(request):
    return render(request, 'platform_admin/management/campaigns.html')

def admin_admins_view(request):
    return render(request, 'platform_admin/management/admins.html')

def admin_create_view(request):
    return render(request, 'platform_admin/create-admin.html')

# VERIFICATION PAGE

def admin_donor_verification_view(request, user_uuid):
    return render(
        request,
        "platform_admin/verification_page/donor.html",
        {"user_uuid": user_uuid},
    )
    
def admin_fundraiser_verification_view(request, user_uuid):
    return render(
        request,
        "platform_admin/verification_page/fundraiser.html",
        {"user_uuid": user_uuid},
    )
    
def admin_ngo_verification_view(request, user_uuid):
    return render(
        request,
        "platform_admin/verification_page/ngo.html",
        {"user_uuid": user_uuid},
    )
    
def admin_csr_verification_view(request, user_uuid):
    return render(
        request,
        "platform_admin/verification_page/csr.html",
        {"user_uuid": user_uuid},
    )
    
def admin_campaign_verification_view(request, campaign_slug):
    return render(
        request,
        "platform_admin/verification_page/campaign.html",
        {"campaign_slug": campaign_slug},
    )
    
