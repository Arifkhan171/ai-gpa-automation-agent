"""
AcadTrack — QR Code Service
University of Loralai, Pakistan

Three functions:
  1. generate_verification_token  — deterministic short hash for a transcript
  2. generate_qr_image            — PNG bytes of the QR code
  3. embed_qr_in_pdf              — merge QR footer overlay onto every PDF page
"""

from __future__ import annotations

import hashlib
import io


# ─────────────────────────────────────────────────────────────────────────────
# 1. Token generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_verification_token(
    roll_no: str,
    semester_range: str,
    issued_at: str,
    secret_key: str,
) -> str:
    """
    Return a 20-character uppercase hex token derived from the four inputs.

    The token is deterministic: the same inputs always produce the same token.
    It is stored in the DB and embedded in the QR code URL.

    Example return value: "A3F9C2D1E8B7A4F2C9E1"
    """
    data = f"{roll_no}:{semester_range}:{issued_at}:{secret_key}"
    full_hash = hashlib.sha256(data.encode()).hexdigest()
    return full_hash[:20].upper()


# ─────────────────────────────────────────────────────────────────────────────
# 2. QR image generation
# ─────────────────────────────────────────────────────────────────────────────

def generate_qr_image(verification_url: str) -> bytes:
    """
    Generate a QR code PNG for the given URL and return raw bytes.

    Error correction level M (≈15 % recovery capacity) is a good balance
    between data density and fault tolerance for printed documents.
    """
    import qrcode  # installed via requirements_backend.txt

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(verification_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
# 3. Embed QR overlay into PDF
# ─────────────────────────────────────────────────────────────────────────────

def embed_qr_in_pdf(
    pdf_bytes: bytes,
    verification_token: str,
    verification_base_url: str,
) -> bytes:
    """
    Stamp a QR code + verification text into the bottom-right corner of
    every page of the supplied PDF and return the merged PDF bytes.

    Layout (bottom-right, all distances from page edge):
      • QR image  : 40 mm × 40 mm,  15 mm from right, 15 mm from bottom
      • Text lines : 7 pt, below the QR block
          "Verify: <url>"
          "Token: <token>"
          "University of Loralai — CoE Office"

    Implementation uses ReportLab for the overlay canvas and pypdf to merge.
    """
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.units import mm
    from reportlab.lib.pagesizes import A4
    from pypdf import PdfWriter, PdfReader

    url = f"{verification_base_url}/verify/{verification_token}"
    qr_png = generate_qr_image(url)

    # ── Build a single-page overlay PDF with the QR stamp ────────────────────
    overlay_buf = io.BytesIO()

    # Use A4 as the canvas size — pypdf scales the overlay to match each page
    page_w, page_h = A4

    c = rl_canvas.Canvas(overlay_buf, pagesize=(page_w, page_h))

    # Dimensions and position
    qr_size    = 40 * mm          # 40 mm square
    margin_r   = 15 * mm          # 15 mm from right edge
    margin_b   = 15 * mm          # 15 mm from bottom edge
    text_h     = 3 * 8            # approx height for 3 lines of 7 pt text

    qr_x = page_w - margin_r - qr_size    # left edge of QR image
    qr_y = margin_b + text_h + 2          # bottom edge of QR image

    # Draw the QR PNG from bytes using an ImageReader
    from reportlab.lib.utils import ImageReader
    qr_reader = ImageReader(io.BytesIO(qr_png))
    c.drawImage(qr_reader, qr_x, qr_y, width=qr_size, height=qr_size,
                mask="auto")

    # Draw verification text lines below the QR code
    c.setFont("Helvetica", 7)
    text_y = margin_b + text_h - 2

    line_gap = 9  # points between lines
    c.drawRightString(page_w - margin_r, text_y,
                      f"Verify: {url}")
    c.drawRightString(page_w - margin_r, text_y - line_gap,
                      f"Token: {verification_token}")
    c.drawRightString(page_w - margin_r, text_y - 2 * line_gap,
                      "University of Loralai \u2014 CoE Office")

    c.save()
    overlay_buf.seek(0)

    # ── Merge overlay onto every page of the original PDF ────────────────────
    original_reader = PdfReader(io.BytesIO(pdf_bytes))

    # BUG 8 FIX: Guard against double-embedding — check /AcadTrackQR marker
    info = original_reader.metadata or {}
    if info.get("/AcadTrackQR"):
        # QR already embedded; return original PDF unchanged
        return pdf_bytes

    overlay_reader  = PdfReader(overlay_buf)
    overlay_page    = overlay_reader.pages[0]

    writer = PdfWriter()
    for page in original_reader.pages:
        page.merge_page(overlay_page)
        writer.add_page(page)

    # Stamp a custom metadata key so a second call knows QR is already there
    writer.add_metadata({"/AcadTrackQR": verification_token})

    out_buf = io.BytesIO()
    writer.write(out_buf)
    return out_buf.getvalue()
