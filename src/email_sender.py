import os
import re
import json
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EMAIL_SETTINGS_FILE = os.path.join(DATA_DIR, "email_settings.json")

def html_to_plain_text(html: str) -> str:
    """Converts HTML proposal into clean, readable plain text for anti-spam multipart delivery."""
    text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
    text = re.sub(r'</p>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>', '• ', text, flags=re.IGNORECASE)
    text = re.sub(r'</li>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&bull;', '•')
    lines = [line.strip() for line in text.splitlines()]
    return '\n'.join(lines).strip()

def load_email_settings() -> Dict[str, Any]:
    defaults = {
        "smtp_server": "mail.smtp2go.com",
        "smtp_port": 587,
        "smtp_user": "407flips.com",
        "smtp_password": "",
        "sender_name": "John Roberts | 407 Flips",
        "sender_email": "john@407flips.com",
        "reply_to": "john@407flips.com",
        "company_name": "407 Flips co.",
        "company_phone": "(407) 815-5043",
        "business_address": "Orlando & Central Florida"
    }
    if os.path.exists(EMAIL_SETTINGS_FILE):
        try:
            with open(EMAIL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def save_email_settings(settings: Dict[str, Any]):
    with open(EMAIL_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def send_email(recipient_email: str, subject: str, html_body: str, 
               agent_id: str = "", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Sends email via SMTP2GO with full RFC 5322 compliance:
    - Proper Message-ID and Date headers (prevents spam rejection)
    - Full dual-part MIME (rich HTML + authentic plain text fallback)
    - Formatted quoted display name
    - Port fallback (587 -> 2525)
    """
    settings = load_email_settings()
    host = settings.get("smtp_server", "mail.smtp2go.com")
    port = int(settings.get("smtp_port", 587))
    user = settings.get("smtp_user", "")
    pwd = settings.get("smtp_password", "")
    sender_name = settings.get("sender_name", "John Roberts | 407 Flips")
    sender_email = settings.get("sender_email", "john@407flips.com")
    reply_to = settings.get("reply_to", "john@407flips.com")

    if not pwd:
        return {"status": "error", "message": "SMTP password not configured. Check Email Settings."}

    if not recipient_email or "@" not in recipient_email:
        return {"status": "error", "message": "Invalid recipient email address."}

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = recipient_email
    msg["Reply-To"] = reply_to
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain="407flips.com")
    msg["MIME-Version"] = "1.0"

    # Authentic plain text version for anti-spam filters
    plain_text = html_to_plain_text(html_body)
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    # Connect with port fallback (preferred 587, fallback 2525)
    ports_to_try = [port]
    if port != 587: ports_to_try.append(587)
    if 2525 not in ports_to_try: ports_to_try.append(2525)

    last_error = None
    sent_successfully = False

    for attempt_port in ports_to_try:
        try:
            server = smtplib.SMTP(host, attempt_port, timeout=12)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user, pwd)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
            server.quit()
            sent_successfully = True
            break
        except Exception as e:
            last_error = e
            continue

    if not sent_successfully:
        return {"status": "error", "message": f"SMTP Error sending email: {str(last_error)}"}

    try:
        from src.storage import data_manager
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "channel": "EMAIL",
            "direction": "OUTBOUND",
            "agent_id": agent_id,
            "recipient_email": recipient_email,
            "subject": subject,
            "message": subject,
            "status": "SENT",
            "metadata": metadata or {}
        }
        data_manager.log_outreach(log_entry)

        if agent_id:
            data_manager.update_agent_state(agent_id, {
                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_contact_channel": "EMAIL",
                "pipeline_stage": "Contacted"
            })
    except Exception as e:
        print(f"[WARN] Failed to log email outreach: {e}")

    return {
        "status": "success",
        "message": f"Email successfully dispatched to {recipient_email} via SMTP2GO!",
        "recipient": recipient_email
    }

def test_smtp_connection() -> Dict[str, Any]:
    settings = load_email_settings()
    host = settings.get("smtp_server", "mail.smtp2go.com")
    port = int(settings.get("smtp_port", 2525))
    user = settings.get("smtp_user", "")
    pwd = settings.get("smtp_password", "")

    if not pwd:
        return {"status": "error", "message": "SMTP password not set in settings."}

    try:
        server = smtplib.SMTP(host, port, timeout=10)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(user, pwd)
        server.quit()
        return {"status": "success", "message": f"Successfully authenticated with SMTP2GO ({host}:{port}) as {user}!"}
    except Exception as e:
        return {"status": "error", "message": f"Could not authenticate with {host}:{port}: {str(e)}"}
