from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from crowdfunding.enums import DonationType


def generate_donation_receipt(receipt):
    donation = receipt.donation

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    width, height = A4

    pdf.setTitle(
        f"Donation Receipt {receipt.receipt_num}"
    )

    # --------------------------------------------------
    # ASSETS
    # --------------------------------------------------

    logo_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "logo.webp"
    )

    stamp_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "stamp.png"
    )

    signature_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "sign.avif"
    )

    # --------------------------------------------------
    # LOGO
    # --------------------------------------------------

    if logo_path.exists():
        pdf.drawImage(
            ImageReader(str(logo_path)),
            50,
            height - 100,
            width=100,
            height=60,
            preserveAspectRatio=True,
            mask="auto",
        )

    # --------------------------------------------------
    # HEADER
    # --------------------------------------------------

    pdf.setFont(
        "Helvetica-Bold",
        20
    )

    pdf.drawString(
        180,
        height - 60,
        "DONATION RECEIPT"
    )

    # Receipt number

    pdf.setFont(
        "Helvetica",
        10
    )

    pdf.drawRightString(
        width - 50,
        height - 90,
        f"Receipt No: {receipt.receipt_num}"
    )

    # --------------------------------------------------
    # DIVIDER
    # --------------------------------------------------

    pdf.line(
        50,
        height - 115,
        width - 50,
        height - 115
    )

    # --------------------------------------------------
    # DONATION DETAILS
    # --------------------------------------------------

    y = height - 155

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        50,
        y,
        "Donation Details"
    )

    y -= 35

    # --------------------------------------------------
    # COMMON DETAILS
    # --------------------------------------------------

    details = [
        (
            "Donation Number",
            donation.unique_donation_number
        ),
        (
            "Amount",
            f"{donation.amount} {donation.currency.value}"
        ),
    ]

    # --------------------------------------------------
    # CAMPAIGN / PLATFORM
    # --------------------------------------------------

    if donation.donation_type == DonationType.CAMPAIGN:

        details.append(
            (
                "Campaign",
                donation.campaign.campaign_name
            )
        )

    elif donation.donation_type == DonationType.PLATFORM:

        details.append(
            (
                "Donation Type",
                "Platform Donation"
            )
        )

        details.append(
            (
                "Platform",
                "Our Platform"
            )
        )

    # --------------------------------------------------
    # DONOR + DATE
    # --------------------------------------------------

    details.extend(
        [
            (
                "Donor",
                "Anonymous"
                if donation.is_anonymous
                else donation.donor.fullname
            ),
            (
                "Date",
                donation.donated_at.strftime("%d-%m-%Y")
                if donation.donated_at
                else donation.created_at.strftime("%d-%m-%Y")
            ),
        ]
    )

    # --------------------------------------------------
    # DRAW DETAILS
    # --------------------------------------------------

    for label, value in details:

        pdf.setFont(
            "Helvetica-Bold",
            10
        )

        pdf.drawString(
            60,
            y,
            f"{label}:"
        )

        pdf.setFont(
            "Helvetica",
            10
        )

        pdf.drawString(
            180,
            y,
            str(value)
        )

        y -= 28

    # --------------------------------------------------
    # STAMP
    # --------------------------------------------------

    if stamp_path.exists():

        pdf.drawImage(
            ImageReader(str(stamp_path)),
            60,
            120,
            width=110,
            height=110,
            preserveAspectRatio=True,
            mask="auto",
        )

    # --------------------------------------------------
    # SIGNATURE
    # --------------------------------------------------

    if signature_path.exists():

        pdf.drawImage(
            ImageReader(str(signature_path)),
            width - 200,
            145,
            width=120,
            height=60,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawString(
        width - 200,
        125,
        "Authorized Signature"
    )

    # --------------------------------------------------
    # FOOTER
    # --------------------------------------------------

    pdf.line(
        50,
        80,
        width - 50,
        80
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.drawCentredString(
        width / 2,
        55,
        "Thank you for your contribution."
    )

    # --------------------------------------------------
    # SAVE PDF
    # --------------------------------------------------

    pdf.showPage()
    pdf.save()

    pdf_bytes = buffer.getvalue()

    buffer.close()

    filename = (
        f"{receipt.receipt_num}.pdf"
    )

    receipt.receipt_file.save(
        filename,
        ContentFile(pdf_bytes),
        save=False
    )

    receipt.generated_at = timezone.now()

    receipt.save(
        update_fields=[
            "receipt_file",
            "generated_at",
        ]
    )

    return receipt





from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


def generate_csr_donation_receipt(receipt):
    """
    Generate a dedicated CSR contribution receipt.

    This uses CSRProfile information and has a different
    design from the normal donor receipt.
    """

    donation = receipt.donation
    csr_user = donation.donor

    # =========================================================
    # 1. GET CSR PROFILE
    # =========================================================

    try:
        csr_profile = csr_user.csr_profile
    except Exception:
        csr_profile = None

    # =========================================================
    # 2. PDF SETUP
    # =========================================================

    buffer = BytesIO()

    pdf = canvas.Canvas(
        buffer,
        pagesize=A4
    )

    width, height = A4

    pdf.setTitle(
        f"CSR Contribution Receipt {receipt.receipt_num}"
    )

    # =========================================================
    # 3. ASSETS
    # =========================================================

    logo_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "logo.webp"
    )

    stamp_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "stamp.png"
    )

    signature_path = (
        Path(settings.BASE_DIR)
        / "static"
        / "receipts"
        / "sign.avif"
    )

    # =========================================================
    # 4. PAGE BORDER
    # =========================================================

    pdf.setStrokeColor(colors.HexColor("#D1D5DB"))
    pdf.setLineWidth(1)

    pdf.rect(
        30,
        30,
        width - 60,
        height - 60
    )

    # =========================================================
    # 5. LOGO
    # =========================================================

    if logo_path.exists():

        pdf.drawImage(
            ImageReader(str(logo_path)),
            55,
            height - 105,
            width=95,
            height=55,
            preserveAspectRatio=True,
            mask="auto",
        )

    # =========================================================
    # 6. HEADER
    # =========================================================

    pdf.setFillColor(colors.HexColor("#1F2937"))

    pdf.setFont(
        "Helvetica-Bold",
        19
    )

    pdf.drawCentredString(
        width / 2,
        height - 70,
        "CSR CONTRIBUTION RECEIPT"
    )

    pdf.setFont(
        "Helvetica",
        9
    )

    pdf.setFillColor(colors.HexColor("#6B7280"))

    pdf.drawCentredString(
        width / 2,
        height - 88,
        "Corporate Social Responsibility Contribution"
    )

    # =========================================================
    # 7. RECEIPT NUMBER
    # =========================================================

    pdf.setFillColor(colors.HexColor("#111827"))

    pdf.setFont(
        "Helvetica-Bold",
        10
    )

    pdf.drawRightString(
        width - 55,
        height - 115,
        f"Receipt No: {receipt.receipt_num}"
    )

    # =========================================================
    # 8. HEADER DIVIDER
    # =========================================================

    pdf.setStrokeColor(colors.HexColor("#9CA3AF"))

    pdf.line(
        55,
        height - 130,
        width - 55,
        height - 130
    )

    # =========================================================
    # 9. CSR ORGANIZATION SECTION
    # =========================================================

    y = height - 165

    pdf.setFillColor(colors.HexColor("#111827"))

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        55,
        y,
        "CSR Organization Details"
    )

    y -= 25

    # ---------------------------------------------------------
    # CSR NAME
    # ---------------------------------------------------------

    csr_name = (
        csr_profile.csr_name
        if csr_profile and csr_profile.csr_name
        else csr_user.fullname
    )

    # ---------------------------------------------------------
    # CSR REGISTRATION NUMBER
    # ---------------------------------------------------------

    csr_reg_num = (
        csr_profile.csr_reg_num
        if csr_profile and csr_profile.csr_reg_num
        else "-"
    )

    # ---------------------------------------------------------
    # CONTACT PERSON
    # ---------------------------------------------------------

    contact_person = (
        csr_profile.contact_person_name
        if csr_profile and csr_profile.contact_person_name
        else "-"
    )

    # ---------------------------------------------------------
    # DESIGNATION
    # ---------------------------------------------------------

    designation = (
        csr_profile.contact_person_designation
        if csr_profile and csr_profile.contact_person_designation
        else "-"
    )

    # ---------------------------------------------------------
    # ADDRESS
    # ---------------------------------------------------------

    address_parts = []

    if csr_profile:

        if csr_profile.address:
            address_parts.append(
                csr_profile.address
            )

        if csr_profile.city:
            address_parts.append(
                csr_profile.city
            )

        if csr_profile.state:
            address_parts.append(
                csr_profile.state
            )

        if csr_profile.country:
            address_parts.append(
                csr_profile.country
            )

        if csr_profile.pincode:
            address_parts.append(
                csr_profile.pincode
            )

    csr_address = ", ".join(address_parts) if address_parts else "-"

    # ---------------------------------------------------------
    # WEBSITE
    # ---------------------------------------------------------

    website = (
        csr_profile.website
        if csr_profile and csr_profile.website
        else "-"
    )

    csr_details = [
        ("CSR Name", csr_name),
        ("CSR Registration No.", csr_reg_num),
        ("Contact Person", contact_person),
        ("Designation", designation),
        ("Address", csr_address),
        ("Website", website),
    ]

    # =========================================================
    # 10. DRAW CSR DETAILS
    # =========================================================

    for label, value in csr_details:

        pdf.setFillColor(
            colors.HexColor("#374151")
        )

        pdf.setFont(
            "Helvetica-Bold",
            9
        )

        pdf.drawString(
            65,
            y,
            f"{label}:"
        )

        pdf.setFillColor(
            colors.HexColor("#111827")
        )

        pdf.setFont(
            "Helvetica",
            9
        )

        # Address can be long, so wrap it.
        if label == "Address" and len(str(value)) > 75:

            address_text = str(value)

            first_line = address_text[:75]

            remaining = address_text[75:]

            pdf.drawString(
                190,
                y,
                first_line
            )

            y -= 15

            while remaining:

                line = remaining[:85]

                remaining = remaining[85:]

                pdf.drawString(
                    190,
                    y,
                    line
                )

                y -= 15

            y -= 8

        else:

            pdf.drawString(
                190,
                y,
                str(value)
            )

            y -= 22

    # =========================================================
    # 11. CONTRIBUTION SECTION
    # =========================================================

    y -= 10

    pdf.setFillColor(
        colors.HexColor("#111827")
    )

    pdf.setFont(
        "Helvetica-Bold",
        13
    )

    pdf.drawString(
        55,
        y,
        "Contribution Details"
    )

    y -= 28

    # =========================================================
    # 12. COMMON CONTRIBUTION DETAILS
    # =========================================================

    contribution_details = [
        (
            "Donation Number",
            donation.unique_donation_number
        ),
        (
            "Contribution Amount",
            f"{donation.amount} {donation.currency.value}"
        ),
    ]

    # =========================================================
    # 13. CAMPAIGN / PLATFORM
    # =========================================================

    if donation.donation_type == DonationType.CAMPAIGN:

        campaign_name = "-"

        beneficiary = "-"

        if donation.campaign:

            campaign_name = (
                donation.campaign.campaign_name
                or "-"
            )

            # Try beneficiary if the Campaign model has it.
            beneficiary_value = getattr(
                donation.campaign,
                "beneficiary",
                None
            )

            if beneficiary_value:

                beneficiary = getattr(
                    beneficiary_value,
                    "value",
                    beneficiary_value
                )

        contribution_details.extend(
            [
                (
                    "Contribution Type",
                    "Campaign Contribution"
                ),
                (
                    "Campaign",
                    campaign_name
                ),
                (
                    "Beneficiary",
                    beneficiary
                ),
            ]
        )

    elif donation.donation_type == DonationType.PLATFORM:

        contribution_details.extend(
            [
                (
                    "Contribution Type",
                    "Platform Contribution"
                ),
                (
                    "Platform",
                    "Our Platform"
                ),
            ]
        )

    # =========================================================
    # 14. DATE
    # =========================================================

    contribution_date = (
        donation.donated_at
        if donation.donated_at
        else donation.created_at
    )

    contribution_details.append(
        (
            "Contribution Date",
            contribution_date.strftime("%d-%m-%Y")
        )
    )

    # =========================================================
    # 15. DRAW CONTRIBUTION DETAILS
    # =========================================================

    for label, value in contribution_details:

        pdf.setFillColor(
            colors.HexColor("#374151")
        )

        pdf.setFont(
            "Helvetica-Bold",
            9
        )

        pdf.drawString(
            65,
            y,
            f"{label}:"
        )

        pdf.setFillColor(
            colors.HexColor("#111827")
        )

        pdf.setFont(
            "Helvetica",
            9
        )

        # Wrap long campaign names
        value_text = str(value)

        if len(value_text) > 70:

            first_line = value_text[:70]

            remaining = value_text[70:]

            pdf.drawString(
                190,
                y,
                first_line
            )

            y -= 15

            while remaining:

                line = remaining[:80]

                remaining = remaining[80:]

                pdf.drawString(
                    190,
                    y,
                    line
                )

                y -= 15

            y -= 7

        else:

            pdf.drawString(
                190,
                y,
                value_text
            )

            y -= 22

    # =========================================================
    # 16. FORMAL DECLARATION BOX
    # =========================================================

    y -= 10

    pdf.setStrokeColor(
        colors.HexColor("#D1D5DB")
    )

    pdf.setFillColor(
        colors.HexColor("#F9FAFB")
    )

    pdf.roundRect(
        55,
        y - 65,
        width - 110,
        65,
        5,
        stroke=1,
        fill=1
    )

    pdf.setFillColor(
        colors.HexColor("#374151")
    )

    pdf.setFont(
        "Helvetica-Bold",
        9
    )

    pdf.drawString(
        70,
        y - 20,
        "Contribution Acknowledgement"
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )

    pdf.setFillColor(
        colors.HexColor("#4B5563")
    )

    acknowledgement = (
        "This receipt acknowledges the contribution made by the "
        "above-mentioned CSR organization through our platform."
    )

    pdf.drawString(
        70,
        y - 38,
        acknowledgement
    )

    pdf.drawString(
        70,
        y - 51,
        "This document is issued electronically and is valid without a physical signature."
    )

    # =========================================================
    # 17. STAMP
    # =========================================================

    if stamp_path.exists():

        pdf.drawImage(
            ImageReader(str(stamp_path)),
            65,
            100,
            width=95,
            height=95,
            preserveAspectRatio=True,
            mask="auto",
        )

    # =========================================================
    # 18. SIGNATURE
    # =========================================================

    if signature_path.exists():

        pdf.drawImage(
            ImageReader(str(signature_path)),
            width - 190,
            125,
            width=110,
            height=55,
            preserveAspectRatio=True,
            mask="auto",
        )

    pdf.setFillColor(
        colors.HexColor("#374151")
    )

    pdf.setFont(
        "Helvetica",
        8.5
    )

    pdf.drawString(
        width - 190,
        110,
        "Authorized Signature"
    )

    # =========================================================
    # 19. FOOTER
    # =========================================================

    pdf.setStrokeColor(
        colors.HexColor("#D1D5DB")
    )

    pdf.line(
        55,
        75,
        width - 55,
        75
    )

    pdf.setFillColor(
        colors.HexColor("#6B7280")
    )

    pdf.setFont(
        "Helvetica",
        8
    )

    pdf.drawCentredString(
        width / 2,
        57,
        "Thank you for your CSR contribution."
    )

    pdf.drawCentredString(
        width / 2,
        44,
        f"Receipt No: {receipt.receipt_num}"
    )

    # =========================================================
    # 20. SAVE PDF
    # =========================================================

    pdf.showPage()
    pdf.save()

    pdf_bytes = buffer.getvalue()

    buffer.close()

    filename = (
        f"{receipt.receipt_num}.pdf"
    )

    receipt.receipt_file.save(
        filename,
        ContentFile(pdf_bytes),
        save=False
    )

    receipt.generated_at = timezone.now()

    receipt.save(
        update_fields=[
            "receipt_file",
            "generated_at",
        ]
    )

    return receipt






