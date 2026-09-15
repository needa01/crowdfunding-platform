# upload_paths.py

from datetime import datetime

from crowdfunding.enums import UserType


def get_user_type_folder(user):
    """
    Returns the folder name based on CustomUser.user_type.
    """

    user_type = user.user_type

    # If your EnumField returns an enum
    if hasattr(user_type, "value"):
        user_type = user_type.value

    return str(user_type).lower()


def profile_picture_upload_path(instance, filename):
    user = instance

    user_type = get_user_type_folder(user)

    return (
        f"{user_type}/"
        f"{user.uuid}/"
        f"profile/"
        f"{filename}"
    )


def document_upload_path(instance, filename):
    now = datetime.now()

    # -------------------------
    # USER DOCUMENT
    # -------------------------
    if instance.user:
        user = instance.user

        user_type = get_user_type_folder(user)

        return (
            f"{user_type}/"
            f"{user.uuid}/"
            f"documents/"
            f"{filename}"
        )

    # -------------------------
    # CAMPAIGN DOCUMENT
    # -------------------------
    if instance.campaign:
        campaign = instance.campaign
        user = campaign.created_by

        user_type = get_user_type_folder(user)

        return (
            f"{user_type}/"
            f"{user.uuid}/"
            "campaigns/"
            f"{campaign.uuid}/"
            f"{filename}"
        )

    # Should never happen because of your clean()
    return f"documents/{now.year}/{now.month:02d}/{filename}"


def cancelled_cheque_upload_path(instance, filename):
    user = instance.user

    user_type = get_user_type_folder(user)

    return (
        f"{user_type}/"
        f"{user.uuid}/"
        f"cancelled-cheque/"
        f"{filename}"
    )




def receipt_upload_path(instance, filename):
    donation = instance.donation
    user = donation.donor

    user_type = get_user_type_folder(user)

    return (
        f"{user_type}/"
        f"{user.uuid}/"
        f"receipts/"
        f"{filename}"
    )






def campaign_profile_upload_path(instance, filename):
    user = instance.created_by

    if user.user_type == UserType.NGO:
        user_type = "ngo"

    elif user.user_type == UserType.INDIVIDUAL_FUNDRAISER:
        user_type = "fundraiser"

    else:
        user_type = "other"

    return (
        f"{user_type}/"
        f"{user.uuid}/"
        f"campaigns/"
        f"{instance.uuid}/"
        f"profile/"
        f"{filename}"
    )