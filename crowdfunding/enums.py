from django.db import models
from enum import Enum

class KYC_Status(Enum):
    NOT_SUBMITTED = "Not Submitted"
    PENDING = "Pending"
    APPROVED = "Approved"
    REJECTED = "Rejected"
        
class UserType(Enum):
    INDIVIDUAL_FUNDRAISER = "Individual Fundraiser"
    NGO = "NGO"
    CSR = "CSR"
    ADMIN = "Admin"
    SUPER_ADMIN = "Super Admin"
    DONOR = "Donor"

class Status(Enum):
    ACTIVE = "Active"
    SUSPENDED = "Suspended"
    DELETED = "Deleted"
    
class ProfileStatus(Enum):
    BASIC_INFO = "Basic Info"
    PROFILE_COMPLETED = "Profile Completed"
    VERIFICATION_PENDING = "Verification Pending"
    VERIFIED = "Verified"
    VERIFICATION_REJECTED = "Verification Rejected" 

class BeneficiaryType(Enum):
    ME = "Me"
    RELATIVE = "Relative"
    FRIEND = "Friend"
    OTHERS = "Others"
    NGO = "NGO"
    INDIVIDUAL = "Individual"
    INSTITUTION = "Institution"
    COMMUNITY = "Community"
    


class BeneficiaryGroupType(Enum):
    INDIVIDUAL = "Individual"
    GROUP = "Group"


class CampaignCause(Enum):
    MEDICAL = "Medical"
    EDUCATION = "Education"
    MEMORIAL = "Memorial"
    DISASTER_RELIEF = "Disaster Relief"
    CHILDREN = "Children"
    ANIMAL_WELFARE = "Animal Welfare"
    ENVIRONMENT = "Environment"
    WOMEN_EMPOWERMENT = "Women Empowerment"
    COMMUNITY_DEVELOPMENT = "Community Development"
    LIVELIHOOD_SKILL_DEVELOPMENT = "Livelihood Skill Development"
    HEALTHCARE = "Healthcare"
    OTHERS = "Others"


class BeneficiaryRelation(Enum):
    MOTHER = "Mother"
    FATHER = "Father"
    BROTHER = "Brother"
    SISTER = "Sister"
    SPOUSE = "Spouse"
    CHILD = "Child"
    OTHERS = "Others"


class CampaignStatus(Enum):
    DRAFT = "Draft"
    PENDING = "Pending"
    ACTIVE = "Active"
    PAUSED = "Paused"
    COMPLETED = "Completed" # Campaign has reached its end date or target amount
    REJECTED = "Rejected"
    CLOSED = "Closed" # Campaign has been closed by the campaign owner or admin



class CampaignType(Enum):
    CROWDFUNDING = "Crowdfunding"
    CSR = "CSR"

class DocumentPurpose(Enum):
        PROFILE_VERIFICATION = "Profile Verification"
        CAMPAIGN_VERIFICATION = "Campaign Verification"



class DocumentPurpose(Enum):
    PROFILE_VERIFICATION = "Profile Verification"
    CAMPAIGN_VERIFICATION = "Campaign Verification"
    BANK_VERIFICATION ="Bank Verification"

class VerificationEntity(Enum):
    INDIVIDUAL_FUNDRAISER = "Individual Fundraiser"
    NGO = "NGO"
    CSR = "CSR"
    CAMPAIGN = "Campaign"
    
class VerificationStatus(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    UNDER_REVIEW = "Under Review"
    REJECTED = "Rejected"
    
class AccountType(Enum):
        SAVINGS = "Savings"
        CURRENT = "Current"

class ServiceType(Enum):
        FEATURED = "Featured"
        GOOGLE_ADS = "Google Ads"
        SOCIAL_MEDIA = "Social Media"

class PromotionStatus(Enum):
    PENDING = "Pending"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"



class NGOType(Enum):
    TRUST = "Trust"
    SOCIETY = "Society"
    SECTION_8 = "Section 8"

class DocOwner(Enum):
    DONOR = "Donor"
    INDIVIDUAL_FUNDRAISER = "Individual Fundraiser"
    NGO = "NGO"
    CSR = "CSR"
    CAMPAIGN = "Campaign"
    CSR_CAMPAIGN = "CSR Campaign"
    
class DonationStatus(Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"
    REFUNDED = "Refunded"
    
class Currency(Enum):
    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"

class PaymentGateway(Enum):
    MANUAL = "Manual" # For testing and demo purposes
    RAZORPAY = "Razorpay"
    STRIPE = "Stripe"
    PAYPAL = "Paypal"
    PAYU = "PayU"
    CASHFREE = "Cashfree"


class PaymentMethod(Enum):
    CARD = "Card"
    UPI = "UPI"
    NETBANKING = "Netbanking"
    WALLET = "Wallet"
    EMI = "EMI"
    BANK_TRANSFER = "Bank Transfer"
    OTHER = "Other"


class TransactionStatus(Enum):
    PENDING = "Pending"
    SUCCESS = "Success"
    FAILED = "Failed"
    REFUNDED = "Refunded"
    
class TransactionType(Enum):
    DONATION = "Donation"
    REFUND = "Refund"
    WITHDRAWAL = "Withdrawal"
    DEPOSIT = "Deposit"
    CAMPAIGN_PROMOTION = "Campaign Promotion"
    
class WithdrawalStatus(Enum):
    PENDING = "Pending"
    APPROVED = "Approved"
    PAID = "Paid"
    REJECTED = "Rejected"
    FAILED = "Failed"
    
class VerificationType(Enum):
    DONOR = "Donor"
    INDIVIDUAL_FUNDRAISER = "Individual Fundraiser"
    NGO = "NGO"
    CSR = "CSR"
    CAMPAIGN = "Campaign"

    
class WalletType(Enum):
    CAMPAIGN = "Campaign"
    PLATFORM = "Platform"
    
class WalletTransactionType(Enum):
    CREDIT = "Credit"
    DEBIT = "Debit"
    
class DonationType(Enum):
    CAMPAIGN = "Campaign"
    PLATFORM = "Platform"