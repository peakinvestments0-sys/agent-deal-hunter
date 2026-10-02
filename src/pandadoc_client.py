import os
import re
import json
import time
import requests
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PANDADOC_SETTINGS_FILE = os.path.join(DATA_DIR, "pandadoc_settings.json")

def load_pandadoc_settings() -> Dict[str, Any]:
    defaults = {
        "mode": "production",
        "sandbox_key": "a0e076d0cc7560b97b382e6941eb97db6b61a048",
        "production_key": "457d46f006c799047dae455687c71ebac95c58ef",
        "buyer_name": "Peak Investments LLC",
        "buyer_signer_name": "Johnathan Roberts",
        "sender_email": "john@407flips.com",
        "default_title_company": "Title Insights",
        "title_company_phone": "(813) 336-4699",
        "title_company_email": "Team@yourtitlesource.com",
        "title_company_address": "13057 W Linebaugh Ave # 101, Tampa, FL 33626",
        "default_inspection_days": 5,
        "default_closing_days": 21,
        "default_deposit": 2500,
        "farbar_template_id": "6dCNMVqv5wBQ6gF5UoUjun"
    }
    if os.path.exists(PANDADOC_SETTINGS_FILE):
        try:
            with open(PANDADOC_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def save_pandadoc_settings(settings: Dict[str, Any]):
    with open(PANDADOC_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def test_pandadoc_connection(mode_override: str = None, key_override: str = None) -> Dict[str, Any]:
    """Tests authentication against PandaDoc API using the active or provided mode and API key."""
    settings = load_pandadoc_settings()
    mode = (mode_override or settings.get("mode", "sandbox")).lower()
    
    if key_override:
        api_key = key_override.strip()
    else:
        api_key = (settings.get("production_key") if mode == "production" else settings.get("sandbox_key")) or ""
        api_key = api_key.strip()
        
    if not api_key:
        return {"status": "error", "message": f"No {mode.upper()} API key configured."}
        
    try:
        res = requests.get(
            "https://api.pandadoc.com/public/v1/templates",
            headers={"Authorization": f"API-Key {api_key}"},
            timeout=10
        )
        if res.status_code in [200, 201]:
            return {
                "status": "success",
                "message": f"Successfully authenticated with PandaDoc {mode.upper()} API!",
                "mode": mode
            }
        elif res.status_code == 401:
            return {
                "status": "error",
                "message": f"Authentication failed: {mode.upper()} API key is invalid (HTTP 401 Unauthorized)."
            }
        else:
            return {
                "status": "error",
                "message": f"PandaDoc {mode.upper()} API returned HTTP {res.status_code}: {res.text}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Connection failed to PandaDoc: {str(e)}"}

def generate_loi_html(data: Dict[str, Any], for_pandadoc: bool = True) -> str:
    """Generates an institutional 1-Page Letter of Intent (LOI) to present to the listing agent."""
    price_val = float(data.get("purchase_price", 0))
    escrow_val = float(data.get("escrow_deposit", 2500))
    price_fmt = f"${price_val:,.2f}"
    escrow_fmt = f"${escrow_val:,.2f}"
    
    agent_sig = '<span style="color:#6366f1;">[Signature:Agent:Signature]</span>' if for_pandadoc else '_______________________'
    buyer_sig = '<span style="color:#6366f1;">[Signature:Buyer:Signature]</span>' if for_pandadoc else 'Johnathan Roberts'
    agent_date = '<span style="color:#6366f1;">[Date:Agent:Date]</span>' if for_pandadoc else time.strftime("%m/%d/%Y")
    buyer_date = '<span style="color:#6366f1;">[Date:Buyer:Date]</span>' if for_pandadoc else time.strftime("%m/%d/%Y")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 36px 48px; color: #1e293b; font-size: 10pt; line-height: 1.5; }}
  .header {{ border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 18px; }}
  .title {{ font-size: 16pt; font-weight: 800; color: #0f172a; text-transform: uppercase; letter-spacing: 0.5px; }}
  .subtitle {{ font-size: 9pt; color: #64748b; font-weight: 600; text-transform: uppercase; }}
  .meta-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; }}
  .meta-item {{ font-size: 9pt; }}
  .meta-label {{ font-weight: 700; color: #475569; }}
  .terms-list {{ margin: 0; padding: 0 0 0 18px; }}
  .terms-list li {{ margin-bottom: 10px; }}
  .highlight {{ font-weight: 700; color: #0f172a; }}
  .sig-section {{ margin-top: 32px; border-top: 1px solid #cbd5e1; padding-top: 18px; }}
  .sig-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 30px; margin-top: 12px; }}
  .sig-box {{ border: 1px solid #cbd5e1; border-radius: 6px; padding: 14px; background: #fafafa; }}
  .sig-line {{ border-bottom: 1px solid #475569; min-height: 28px; margin-bottom: 6px; display: flex; align-items: flex-end; }}
</style>
</head>
<body>
  <div class="header">
    <div class="title">Letter of Intent to Purchase Real Property</div>
    <div class="subtitle">Confidential Investor Acquisition Proposal &bull; Peak Investments LLC</div>
  </div>

  <div class="meta-grid">
    <div class="meta-item"><span class="meta-label">Date:</span> {time.strftime('%B %d, %Y')}</div>
    <div class="meta-item"><span class="meta-label">Listing Agent:</span> {data.get('agent_name', 'Listing Agent')}</div>
    <div class="meta-item"><span class="meta-label">Property Address:</span> <span class="highlight">{data.get('property_address', 'Address')}</span></div>
    <div class="meta-item"><span class="meta-label">Brokerage:</span> {data.get('brokerage_name', 'Listing Brokerage')}</div>
    <div class="meta-item"><span class="meta-label">County & Parcel ID:</span> {data.get('county', 'FL')} &bull; {data.get('apn', 'Parcel ID')}</div>
    <div class="meta-item"><span class="meta-label">Buyer Entity:</span> {data.get('buyer_name', 'Peak Investments LLC')}</div>
  </div>

  <ol class="terms-list">
    <li><span class="highlight">PURCHASE PRICE:</span> {price_fmt} All-Cash. No financing or appraisal contingencies.</li>
    <li><span class="highlight">INITIAL ESCROW DEPOSIT:</span> {escrow_fmt} deposited with Escrow Agent within two (2) business days of mutual execution.</li>
    <li><span class="highlight">INSPECTION PERIOD:</span> {data.get('inspection_days', 7)} calendar days from effective date. Buyer retains right to inspect condition.</li>
    <li><span class="highlight">CLOSING DATE:</span> On or before {data.get('closing_days', 14)} calendar days following the expiration of the inspection period.</li>
    <li><span class="highlight">AS-IS PURCHASE:</span> Property to be conveyed in completely "AS-IS" condition. Zero repairs or cleanouts required by Seller.</li>
    <li><span class="highlight">TITLE &amp; CLOSING AGENT:</span> Buyer shall designate Closing Agent ({data.get('title_company', 'Title Insights')}) and pay for Owner's Policy and closing fees.</li>
    <li><span class="highlight">ASSIGNABILITY:</span> This agreement and underlying contract are assignable by Buyer and Buyer's designated entity.</li>
    <li><span class="highlight">COMMISSION &amp; REPRESENTATION:</span> Buyer recognizes {data.get('agent_name', 'Listing Agent')} / {data.get('brokerage_name', 'Listing Brokerage')} as the participating listing licensee. Listing commission remains fully intact per listing agreement.</li>
    <li><span class="highlight">CONTRACT EXECUTION:</span> Upon mutual acceptance of these terms, the parties agree to execute a standard Florida Realtors / Florida Bar (FAR/BAR) "AS IS" Residential Purchase Contract.</li>
  </ol>

  <div class="sig-section">
    <div style="font-size: 8.5pt; color: #64748b; margin-bottom: 12px;">Submitted by Buyer and acknowledged by Listing Licensee for presentation to Seller:</div>
    <div class="sig-grid">
      <div class="sig-box">
        <div style="font-size: 8.5pt; font-weight: 700; color: #475569; margin-bottom: 4px;">BUYER: Peak Investments LLC</div>
        <div class="sig-line">{buyer_sig}</div>
        <div style="font-size: 8pt; color: #64748b;">By: {data.get('buyer_signer_name', 'Johnathan Roberts')} &bull; Date: {buyer_date}</div>
      </div>
      <div class="sig-box">
        <div style="font-size: 8.5pt; font-weight: 700; color: #475569; margin-bottom: 4px;">LISTING AGENT / SELLER ACKNOWLEDGMENT:</div>
        <div class="sig-line">{agent_sig}</div>
        <div style="font-size: 8pt; color: #64748b;">Licensee / Principal &bull; Date: {agent_date}</div>
      </div>
    </div>
  </div>
</body>
</html>"""

def generate_farbar_html(data: Dict[str, Any], for_pandadoc: bool = True) -> str:
    """Generates Florida FAR/BAR 'AS IS' Purchase Contract."""
    price_val = float(data.get("purchase_price", 0))
    escrow_val = float(data.get("escrow_deposit", 2500))
    price_fmt = f"${price_val:,.2f}"
    escrow_fmt = f"${escrow_val:,.2f}"
    balance_val = max(0, price_val - escrow_val)
    balance_fmt = f"${balance_val:,.2f}"

    buyer_sig = '<span style="color:#6366f1;">[Signature:Buyer:Signature]</span>' if for_pandadoc else 'Johnathan Roberts'
    seller_sig = '<span style="color:#6366f1;">[Signature:Seller:Signature]</span>' if for_pandadoc else '_______________________'
    buyer_date = '<span style="color:#6366f1;">[Date:Buyer:Date]</span>' if for_pandadoc else time.strftime("%m/%d/%Y")
    seller_date = '<span style="color:#6366f1;">[Date:Seller:Date]</span>' if for_pandadoc else '_______________________'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Times New Roman', Times, serif; margin: 30px 45px; color: #000; font-size: 9.5pt; line-height: 1.4; }}
  .title-block {{ text-align: center; border-bottom: 1.5px solid #000; padding-bottom: 6px; margin-bottom: 14px; }}
  .title {{ font-size: 13pt; font-weight: bold; text-transform: uppercase; }}
  .subtitle {{ font-size: 8.5pt; font-style: italic; }}
  .section {{ margin-bottom: 12px; }}
  .section-title {{ font-weight: bold; text-decoration: underline; margin-bottom: 3px; display: inline-block; }}
  .fill-in {{ font-weight: bold; font-family: Arial, sans-serif; text-decoration: underline; }}
  .sig-table {{ width: 100%; margin-top: 24px; border-collapse: collapse; }}
  .sig-table td {{ vertical-align: top; padding: 10px; width: 50%; }}
  .sig-line {{ border-bottom: 1px solid #000; height: 26px; margin-bottom: 4px; display: flex; align-items: flex-end; }}
  .broker-box {{ border: 1px solid #000; padding: 8px 12px; margin-top: 14px; font-size: 8.5pt; background: #fafafa; }}
</style>
</head>
<body>
  <div class="title-block">
    <div class="title">"AS IS" Residential Contract For Sale And Purchase</div>
    <div class="subtitle">Florida Realtors &reg; / Florida Bar Standard Form &bull; Pre-Filled Cash Acquisition</div>
  </div>

  <div class="section">
    <span class="section-title">1. PARTIES:</span> 
    <span class="fill-in">{data.get('seller_name', 'Seller of Record')}</span> ("Seller"), and 
    <span class="fill-in">{data.get('buyer_name', 'Peak Investments LLC')}</span> ("Buyer"), hereby agree that Seller shall sell and Buyer shall buy the following described Real Property ("Property") pursuant to the terms and conditions herein.
  </div>

  <div class="section">
    <span class="section-title">2. PROPERTY DESCRIPTION:</span><br>
    (a) Street Address: <span class="fill-in">{data.get('property_address', 'Address')}</span>, City of <span class="fill-in">{data.get('city', 'St Petersburg')}</span>, FL Zip: <span class="fill-in">{data.get('zip', '')}</span><br>
    (b) County: <span class="fill-in">{data.get('county', 'FL')}</span> &bull; Property Appraiser Parcel ID / APN: <span class="fill-in">{data.get('apn', 'Parcel ID')}</span><br>
    (c) Legal Description: <span class="fill-in">{data.get('legal_description', 'Recorded Plat / Public Records')}</span>
  </div>

  <div class="section">
    <span class="section-title">3. PURCHASE PRICE &amp; CLOSING FUNDS:</span><br>
    Purchase Price: <span class="fill-in">{price_fmt}</span> (U.S. Dollars)<br>
    (a) Initial Escrow Deposit to be held in escrow by <span class="fill-in">{data.get('title_company', 'Title Insights')}</span>: <span class="fill-in">{escrow_fmt}</span> within 3 days of Effective Date.<br>
    (b) Balance to close by wire transfer upon closing: <span class="fill-in">{balance_fmt}</span>.
  </div>

  <div class="section">
    <span class="section-title">7. ASSIGNABILITY:</span> [X] (a) <span class="fill-in">Buyer may assign and thereby be released from any further liability under this Contract.</span>
  </div>

  <div class="section">
    <span class="section-title">8. FINANCING:</span> (a) [X] <span class="fill-in">CASH TRANSACTION:</span> This Contract is NOT contingent upon Buyer obtaining financing.
  </div>

  <div class="section">
    <span class="section-title">9. TITLE INSURANCE &amp; CLOSING AGENT:</span><br>
    (c) Title Evidence and Insurance: [X] <span class="fill-in">Buyer shall designate Closing Agent (<span class="fill-in">{data.get('title_company', 'Title Insights')}</span>) and pay for Owner's Policy and closing fees</span>, and Seller shall pay for title search fees.
  </div>

  <div class="section">
    <span class="section-title">12. PROPERTY INSPECTION &amp; RIGHT TO CANCEL:</span><br>
    Buyer shall have <span class="fill-in">{data.get('inspection_days', 7)}</span> calendar days ("Inspection Period") from the Effective Date to have inspections performed. If Buyer determines, in Buyer's sole discretion, that the condition of the Property is not acceptable to Buyer, Buyer may cancel this Contract by delivering written notice to Seller prior to the expiration of the Inspection Period and obtain a full refund of deposit.
  </div>

  <div class="section">
    <span class="section-title">18. CLOSING DATE &amp; PROCEDURE:</span><br>
    This transaction shall close on or before <span class="fill-in">{data.get('closing_days', 14)}</span> calendar days from Effective Date or at mutually agreed date. Closing to take place through Buyer's designated closing agent: <span class="fill-in">{data.get('title_company', 'Title Insights')}</span>.
  </div>

  <div class="broker-box">
    <strong>COOPERATING &amp; LISTING BROKERAGE PARTICIPATION (PAGE 12):</strong><br>
    Listing Agent: <span class="fill-in">{data.get('agent_name', 'Listing Agent')}</span> &bull; Listing Brokerage: <span class="fill-in">{data.get('brokerage_name', 'Listing Brokerage')}</span><br>
    Listing Broker and Cooperating Broker are recognized as the sole brokers in this transaction. Commission splits and compensation paid pursuant to listing agreement.
  </div>

  <table class="sig-table">
    <tr>
      <td>
        <strong>BUYER:</strong> {data.get('buyer_name', 'Peak Investments LLC')}<br><br>
        <div class="sig-line">{buyer_sig}</div>
        By: {data.get('buyer_signer_name', 'Johnathan Roberts')}<br>
        Date: {buyer_date}
      </td>
      <td>
        <strong>SELLER:</strong> {data.get('seller_name', 'Property Owner of Record')}<br><br>
        <div class="sig-line">{seller_sig}</div>
        Seller Signature<br>
        Date: {seller_date}
      </td>
    </tr>
  </table>
</body>
</html>"""

def _render_pdf_sync(html_content: str) -> bytes:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        pdf_bytes = page.pdf(
            format="Letter",
            print_background=True,
            margin={"top": "0.3in", "bottom": "0.3in", "left": "0.4in", "right": "0.4in"}
        )
        browser.close()
        return pdf_bytes

async def generate_contract_pdf_bytes(html_content: str) -> bytes:
    """Renders HTML into PDF bytes using Playwright Chromium in a thread safe manner for Windows."""
    import asyncio
    return await asyncio.to_thread(_render_pdf_sync, html_content)

async def dispatch_pandadoc_contract(payload: Dict[str, Any], contract_type: str = "farbar") -> Dict[str, Any]:
    """
    Renders document PDF and sends via PandaDoc API directly to the Listing Agent.
    """
    settings = load_pandadoc_settings()
    agent_id = str(payload.get("agent_id", "")).lower()
    is_test_agent = "test" in agent_id or "custom" in agent_id or "sandbox" in str(payload.get("recipient_email", "")).lower()
    
    if is_test_agent:
        mode = (payload.get("mode") or settings.get("mode", "sandbox")).lower()
    else:
        # Live agents are ALWAYS locked to Production
        mode = "production"

    api_key = settings.get("production_key") if mode == "production" else settings.get("sandbox_key")

    if not api_key:
        return {"status": "error", "message": f"No PandaDoc API key configured for {mode} mode."}

    recipient_email = payload.get("recipient_email", "").strip()
    if not recipient_email or "@" not in recipient_email:
        return {"status": "error", "message": "Valid recipient agent email is required."}

    headers = {"Authorization": f"API-Key {api_key}"}
    agent_name = payload.get("agent_name", "Listing Agent")
    parts = agent_name.split()
    first_n = parts[0] if parts else "Listing"
    last_n = parts[-1] if len(parts) > 1 else "Agent"
    buyer_signer = settings.get("buyer_signer_name", "Johnathan Roberts")
    b_parts = buyer_signer.split()
    b_first = b_parts[0] if b_parts else "Johnathan"
    b_last = b_parts[-1] if len(b_parts) > 1 else "Roberts"
    buyer_email = settings.get("sender_email", "john@407flips.com")

    # Plus-addressing safety if testing with identical emails
    if recipient_email.lower() == buyer_email.lower():
        u, d = recipient_email.split("@", 1)
        recipient_email = f"{u}+agent@{d}"

    doc_title = f"{'FAR/BAR AS-IS Contract' if contract_type == 'farbar' else 'Letter of Intent'} - {payload.get('property_address')}"

    farbar_template_id = str(settings.get("farbar_template_id") or "").strip()
    use_template = (contract_type == "farbar" and bool(farbar_template_id))

    recipients_list = [
        {
            "email": recipient_email,
            "first_name": first_n,
            "last_name": last_n,
            "role": "Agent" if contract_type == "loi" else "Seller",
            "signing_order": 1
        },
        {
            "email": buyer_email,
            "first_name": b_first,
            "last_name": b_last,
            "role": "Buyer",
            "signing_order": 2
        }
    ]

    try:
        if use_template:
            create_payload = {
                "name": doc_title,
                "template_uuid": farbar_template_id,
                "recipients": recipients_list
            }
            res = requests.post(
                "https://api.pandadoc.com/public/v1/documents",
                headers={**headers, "Content-Type": "application/json"},
                json=create_payload,
                timeout=25
            )
        else:
            # Fallback to generating PDF and multipart upload
            if contract_type == "loi":
                html = generate_loi_html(payload, for_pandadoc=True)
                pdf_bytes = await generate_contract_pdf_bytes(html)
            else:
                from src.farbar_filler import fill_official_farbar_pdf
                pdf_bytes = fill_official_farbar_pdf(payload)

            pandadoc_meta = {
                "name": doc_title,
                "recipients": recipients_list,
                "parse_form_fields": False
            }
            files = {
                "file": (f"{contract_type.upper()}_Agreement.pdf", pdf_bytes, "application/pdf")
            }
            res = requests.post(
                "https://api.pandadoc.com/public/v1/documents",
                headers=headers,
                data={"data": json.dumps(pandadoc_meta)},
                files=files,
                timeout=25
            )

        if res.status_code not in [200, 201]:
            return {"status": "error", "message": f"PandaDoc creation failed (HTTP {res.status_code}): {res.text}"}

        doc_id = res.json().get("id")

        # Poll for draft status
        time.sleep(1.5)
        for _ in range(6):
            check = requests.get(f"https://api.pandadoc.com/public/v1/documents/{doc_id}", headers=headers, timeout=10)
            if check.ok and check.json().get("status") == "document.draft":
                break
            time.sleep(1)

        # Dispatch e-sign invite
        send_payload = {
            "message": f"Hello {first_n},\n\nPlease review and present this {contract_type.upper()} offer for {payload.get('property_address')} on behalf of Peak Investments LLC.\n\nAll cash, zero contingencies, 14-day close.",
            "subject": f"{contract_type.upper()} Offer: {payload.get('property_address')} | Peak Investments LLC",
            "silent": False
        }
        requests.post(f"https://api.pandadoc.com/public/v1/documents/{doc_id}/send", headers=headers, json=send_payload, timeout=15)

        # Generate live signing session link
        session_url = ""
        sess_res = requests.post(
            f"https://api.pandadoc.com/public/v1/documents/{doc_id}/session",
            headers=headers,
            json={"recipient": recipient_email, "lifetime": 86400},
            timeout=10
        )
        if sess_res.ok:
            session_id = sess_res.json().get("id")
            if session_id:
                session_url = f"https://app.pandadoc.com/s/{session_id}"

        from src.storage import data_manager
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "channel": "PANDADOC",
            "agent_id": payload.get("agent_id", ""),
            "recipient_email": recipient_email,
            "subject": doc_title,
            "message": f"Dispatched {contract_type.upper()} for {payload.get('property_address')} at ${float(payload.get('purchase_price', 0)):,.2f}",
            "status": "SENT",
            "document_id": doc_id,
            "session_url": session_url
        }
        data_manager.log_outreach(log_entry)

        if payload.get("agent_id"):
            data_manager.update_agent_state(payload.get("agent_id"), {
                "pipeline_stage": "Contract Sent",
                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_contact_channel": "PANDADOC"
            })

        return {
            "status": "success",
            "message": f"{contract_type.upper()} dispatched successfully to {first_n} via PandaDoc!",
            "document_id": doc_id,
            "session_url": session_url,
            "mode": mode
        }
    except Exception as e:
        return {"status": "error", "message": f"PandaDoc API error: {str(e)}"}
