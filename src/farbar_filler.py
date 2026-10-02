import os
import io
import time
from typing import Dict, Any
import pypdf
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MASTER_TEMPLATE_PATH = os.path.join(DATA_DIR, "FARBAR_ASIS_Master_Template.pdf")

def fill_official_farbar_pdf(data: Dict[str, Any]) -> bytes:
    """
    Fills and overlays deal terms onto the official Florida Realtors / Florida Bar
    'AS IS' Residential Contract For Sale And Purchase (14 Pages).
    """
    if not os.path.exists(MASTER_TEMPLATE_PATH):
        raise FileNotFoundError(f"Master FAR/BAR template not found at {MASTER_TEMPLATE_PATH}")

    master_reader = pypdf.PdfReader(MASTER_TEMPLATE_PATH)
    writer = pypdf.PdfWriter()

    # Financial calculations
    price_val = float(data.get("purchase_price", 0))
    escrow_val = float(data.get("escrow_deposit", 2500))
    balance_val = max(0, price_val - escrow_val)
    price_fmt = f"{price_val:,.2f}"
    escrow_fmt = f"{escrow_val:,.2f}"
    balance_fmt = f"{balance_val:,.2f}"

    buyer = str(data.get("buyer_name") or "Peak Investments LLC")
    seller = str(data.get("seller_name") or "Property Owner of Record")
    address = str(data.get("property_address") or "")
    city = str(data.get("city") or "")
    zip_code = str(data.get("zip") or "")
    full_addr = f"{address}, {city}, FL {zip_code}".strip(", ")
    county = str(data.get("county") or "FL")
    apn = str(data.get("apn") or "Public Records")
    legal = str(data.get("legal_description") or "Recorded Plat / Public Records")
    title_co = str(data.get("title_company") or "Title Insights")
    closing_days = int(data.get("closing_days") or 14)
    inspect_days = str(data.get("inspection_days") or 7)
    agent_name = str(data.get("agent_name") or "")
    brokerage_name = str(data.get("brokerage_name") or "")
    buyer_signer = str(data.get("buyer_signer_name") or "Johnathan Roberts")

    # Closing date calculation (today + closing_days)
    closing_date_str = time.strftime("%m/%d/%Y", time.localtime(time.time() + closing_days * 86400))
    acceptance_date_str = time.strftime("%m/%d/%Y", time.localtime(time.time() + 3 * 86400))
    today_str = time.strftime("%m/%d/%Y")

    for p_idx in range(len(master_reader.pages)):
        orig_page = master_reader.pages[p_idx]
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=letter)
        can.setFont("Helvetica-Bold", 9)

        if p_idx == 0:  # Page 1
            # Seller & Buyer
            can.drawString(145, 692, seller[:40])
            can.drawString(135, 681, buyer[:45])
            # Property description
            can.drawString(195, 623, full_addr[:50])
            can.drawString(130, 612, county[:15])
            can.drawString(380, 612, apn[:30])
            can.drawString(190, 600, legal[:55])
            # Purchase price & deposits
            can.drawRightString(540, 381, price_fmt)
            can.drawRightString(540, 364, escrow_fmt)
            # Deposit timing (Line 30): Option (ii) to be made within 3 days
            can.setFont("Helvetica-Bold", 10)
            can.drawString(294, 341, "X")
            can.setFont("Helvetica-Bold", 9)
            can.drawString(410, 341, "3")
            # Escrow Agent / Title Company (Line 33)
            can.drawString(200, 329, title_co[:45])
            # Balance to close by wire (Line 41)
            can.drawRightString(540, 211, balance_fmt)
            # Time for acceptance (Line 44-45)
            can.drawString(95, 177, acceptance_date_str)

        elif p_idx == 1:  # Page 2
            # Closing date line 53
            can.drawString(255, 728, closing_date_str)
            # Assignability line 83 - Checkbox (a): may assign & be released
            can.setFont("Helvetica-Bold", 11)
            can.drawString(185, 383, "X")
            # Financing line 88 - Checkbox (a): Cash transaction
            can.drawString(62, 325, "X")

        elif p_idx == 3:  # Page 4
            # Title Paragraph 9(c)(ii) Buyer designates closing agent
            can.setFont("Helvetica-Bold", 11)
            can.drawString(62, 595, "X")
            can.setFont("Helvetica-Bold", 9)
            can.drawString(160, 574, title_co[:45])

        elif p_idx == 4:  # Page 5
            # Paragraph 12 Inspection Period days
            can.drawString(215, 555, inspect_days)

        elif p_idx == 12:  # Page 13: Paragraph 20 ADDITIONAL TERMS
            can.setFont("Helvetica-Bold", 8)
            terms = data.get("additional_terms")
            if terms:
                # User provided custom terms
                lines = terms.split("\n")
                y_pos = 728
                for l in lines[:5]:
                    can.drawString(180 if y_pos == 728 else 54, y_pos, l[:85])
                    y_pos -= 11
            else:
                # Default standard investor clauses protecting commission & access
                can.drawString(180, 728, "1. Listing licensee commission remains fully intact per existing listing agreement.")
                can.drawString(54, 717, "2. Seller to provide Buyer & Buyer's partners/inspectors reasonable access with 24h notice.")
                can.drawString(54, 706, "3. Property sold strictly in AS-IS condition with zero seller repairs, credits, or cleanout.")

        elif p_idx == 13:  # Page 14 (Last Page)
            # Buyer Signature / Signer info
            can.drawString(110, 412, f"{buyer_signer} (Peak Investments LLC)")
            can.drawString(280, 412, today_str)
            can.drawString(110, 377, seller[:35])
            can.drawString(72, 328, "Peak Investments LLC")
            can.drawString(72, 316, "john@407flips.com")
            # Listing Brokerage Commission Box (Lines 655-658)
            can.drawString(340, 198, agent_name[:40])
            can.drawString(340, 169, brokerage_name[:40])

        can.save()
        packet.seek(0)
        overlay_reader = pypdf.PdfReader(packet)
        orig_page.merge_page(overlay_reader.pages[0])
        writer.add_page(orig_page)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
