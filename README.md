# Crowdfunding Platform

A role-based crowdfunding and CSR donation platform built using **Django** and **Django REST Framework**.

The platform supports different user roles with specific permissions for creating campaigns, making donations, verifying profiles and campaigns, and managing administrators.

---

## Roles

The platform supports the following roles:

- **Donor**
- **Individual Fundraiser**
- **NGO**
- **CSR**
- **Admin**
- **Super Admin**

---

## Frontend and Backend

### Frontend

The frontend is built using **Django Templates** with basic HTML, CSS, and JavaScript.

### Backend

The backend is built using:

- Python
- Django
- Django REST Framework
- REST APIs
- JWT Authentication
- Role-based permissions

The frontend communicates with the backend through REST APIs.

---

## Application URLs

### Normal User Signup

http://127.0.0.1:8000/frontend/

### Normal User Login

http://127.0.0.1:8000/frontend/login

### Admin / Super Admin Login

http://127.0.0.1:8000/frontend/admin/login

---

# Campaign Types

The platform supports two types of campaigns:

1. **Crowdfunding**
2. **CSR**

---

# Roles and Responsibilities

## 1. Donor

A Donor can:

- Verify their profile.
- Donate only to **verified Crowdfunding campaigns**.
- Download donation receipts.

### Donation Requirements

A Donor must have a verified profile before donating.

A Donor can donate only to a campaign that:

- Is of type **Crowdfunding**
- Has been verified

### Donor Flow

```text
Donor
  ↓
Profile Verification
  ↓
Profile Verified
  ↓
Verified Crowdfunding Campaign
  ↓
Donate
  ↓
Download Receipt
```

## 2. Individual Fundraiser

An **Individual Fundraiser** can:

- Verify their profile.
- Create Crowdfunding campaigns.

### Campaign Creation Requirement

The Individual Fundraiser's profile must be verified before creating a campaign.

An Individual Fundraiser can create:

- **Crowdfunding campaigns**

An Individual Fundraiser cannot create:

- **CSR campaigns**

### Individual Fundraiser Flow

```text
Individual Fundraiser
        ↓
Profile Verification
        ↓
Profile Verified
        ↓
Create Crowdfunding Campaign
        ↓
Campaign Verification
        ↓
Campaign Listed
```
## 3. NGO

An **NGO** can:

- Verify their profile.
- Create Crowdfunding campaigns.
- Create CSR campaigns.

### Campaign Creation Requirement

The NGO's profile must be verified before creating a campaign.

A verified NGO can create:

- **Crowdfunding campaigns**
- **CSR campaigns**

### NGO Flow

```text
NGO
 ↓
Profile Verification
 ↓
Profile Verified
 ↓
Create Campaign
 ↓
+-----------------------+
|                       |
↓                       ↓
Crowdfunding          CSR Campaign
Campaign
```
## 4. CSR

A **CSR** user can:

- Verify their profile.
- Donate to verified CSR campaigns after their profile has been verified.
- Download donation receipts.

### Donation Requirement

A CSR user's profile must be verified before making a donation.

A CSR user can donate only to:

- **Verified CSR campaigns**

A CSR user cannot donate to Crowdfunding campaigns.

### CSR Flow

```text
CSR
 ↓
Profile Verification
 ↓
Profile Verified
 ↓
Verified CSR Campaign
 ↓
Donate
 ↓
Download Receipt
```
## 5. Admin

An **Admin** can perform administrative operations according to the permissions assigned by the platform.

Admins are created only by the **Super Admin**.

## 6. Super Admin

The **Super Admin** has the highest level of administrative access.

A Super Admin can:

- Verify user profiles.
- Verify campaigns.
- Create Admins.
- View Admins.
- Delete Admins.
- Manage Admin accounts through **Admin Management**.

---
## Super Admin Creation

The Super Admin is initially created using Django's built-in `createsuperuser` command.

### Create Super Admin

Run:

```bash
python manage.py createsuperuser
```
Enter the required credentials.

After creating the user, change the user's role in the database to: **SUPER_ADMIN**

The Super Admin can then log in through:

http://127.0.0.1:8000/frontend/admin/login

## Admin Creation

Admin signup is **not available** through the normal user signup page.

Only the **Super Admin** can create Admin accounts.

The Super Admin must:

1. Log in to the platform.
2. Open **Admin Management**.
3. Create a new Admin.
4. Provide the required Admin details.

### Admin Creation Flow

```text
Super Admin Login
        ↓
Admin Management
        ↓
Create Admin
        ↓
Admin Account Created
```

### Super Admin Capabilities

The Super Admin can:

- Create Admin
- View Admins
- Delete Admin
- Verify Profile
- Verify Campaigns

---

## Profile Verification

Profile verification is required before users can perform activities that require a verified profile.

Users must upload all required documents.

A profile can be verified only after all required documents have been successfully verified.

### Profile Verification Flow

```text
User Registration
       ↓
Complete Profile
       ↓
Upload Required Documents
       ↓
Document Verification
       ↓
All Documents Verified
       ↓
Profile Verified
```

If any required document has not been verified, the profile **cannot be marked as verified**.

---

## Campaign Management

Campaigns can be created only by users whose profiles have been verified.

### Individual Fundraiser

A verified **Individual Fundraiser** can create:

- **Crowdfunding campaigns**

#### Individual Fundraiser Flow

```text
Verified Individual Fundraiser
             ↓
Create Crowdfunding Campaign
```
### NGO

A verified **NGO** can create:

- **Crowdfunding campaigns**
- **CSR campaigns**

#### NGO Flow

```text
          Verified NGO
               ↓
     +----------------------+
     |                      |
     ↓                      ↓
Crowdfunding            CSR Campaign
Campaign
```
## Campaign Verification

Creating a campaign does not automatically make it available on the platform.

Every campaign must be verified by an **Admin or Super Admin**.

A campaign can only:

- Be listed after verification.
- Receive donations after verification.

### Campaign Lifecycle

```text
Campaign Created
       ↓
Pending Verification
       ↓
Admin / Super Admin Verification
       ↓
Campaign Verified
       ↓
Campaign Listed
       ↓
Receive Donations
```
## Donation Rules

### Crowdfunding Campaigns

Only **Donors** can donate to verified Crowdfunding campaigns.

The following conditions must be satisfied:

```text
User Role = Donor
       AND
Profile = Verified
       AND
Campaign Type = Crowdfunding
       AND
Campaign = Verified

### Crowdfunding Donation Flow

```text
Donor
 ↓
Verified Profile
 ↓
Verified Crowdfunding Campaign
 ↓
Enter Donation Details
 ↓
Create Donation
 ↓
Payment Verification
 ↓
Successful Donation
 ↓
Donation Receipt
```

### CSR Campaigns

Only **CSR users** can donate to verified CSR campaigns.

The following conditions must be satisfied:

```text
User Role = CSR
       AND
Profile = Verified
       AND
Campaign Type = CSR
       AND
Campaign = Verified
```
### CSR Donation Flow

```text
CSR
 ↓
Verified Profile
 ↓
Verified CSR Campaign
 ↓
Enter Donation Details
 ↓
Create Donation
 ↓
Payment Verification
 ↓
Successful Donation
 ↓
Donation Receipt
```
## Donation Receipts

After a successful donation, the platform generates a donation receipt associated with the donation.

Users can:

- View their successful donations.
- Download the corresponding donation receipts.
