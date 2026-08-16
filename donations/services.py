from io import BytesIO

from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pathlib import Path

from django.conf import settings

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

    pdf.setFont("Helvetica-Bold", 20)

    pdf.drawString(
        180,
        height - 60,
        "DONATION RECEIPT"
    )

    # Receipt number

    pdf.setFont("Helvetica", 10)

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

    pdf.setFont(
        "Helvetica",
        11
    )

    details = [
        (
            "Donation Number",
            donation.unique_donation_number
        ),
        (
            "Amount",
            f"{donation.currency} {donation.amount}"
        ),
        (
            "Campaign",
            donation.campaign.campaign_name
        ),
        (
            "Donor",
            donation.donor.fullname
        ),
        (
            "Date",
            donation.created_at.strftime("%d-%m-%Y")
        ),
    ]

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