import os
import re
import json
import time
import requests
from requests.auth import HTTPBasicAuth
from typing import Dict, Any

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SMS_SETTINGS_FILE = os.path.join(DATA_DIR, "sms_settings.json")

def strip_hyphens_for_sms(text: str) -> str:
    """Zero hyphens rule for cellular SMS."""
    if not text:
        return ""
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)
    text = re.sub(r'\s*[-–—]\s*', ' ', text)
    return re.sub(r' +', ' ', text).strip()

def load_sms_settings() -> Dict[str, Any]:
    defaults = {
        "mode": "cloud",
        "base_url": "https://api.sms-gate.app/3rdparty/v1",
        "username": "",
        "password": "",
        "device_id": "",
        "sim_number": 1,
        "default_template": "Hey {Agent_FirstName}, Brooke here. Saw your listing over on {Listing_Address}. Do you happen to have any off market fixers or pocket listings coming up in {City} before they hit MLS? Happy to have you represent us."
    }
    if os.path.exists(SMS_SETTINGS_FILE):
        try:
            with open(SMS_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                defaults.update(data)
        except Exception:
            pass
    return defaults

def save_sms_settings(settings: Dict[str, Any]):
    with open(SMS_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)

def clean_phone_e164(phone: str) -> str:
    digits = "".join(filter(str.isdigit, str(phone)))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif str(phone).startswith("+"):
        return str(phone).strip()
    return f"+1{digits}" if digits else ""

def send_sms(phone: str, message: str, agent_id: str = "", metadata: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Dispatches SMS through Android SMS Gateway (local Wi Fi IP or cloud relay).
    Guarantees strict zero hyphens rule for cellular SMS.
    """
    settings = load_sms_settings()
    mode = settings.get("mode", "local")
    base_url = settings.get("base_url", "http://192.168.1.100:8080").rstrip("/")
    username = settings.get("username", "admin")
    password = settings.get("password", "")
    sim_number = int(settings.get("sim_number", 1))

    from src.storage import is_globally_opted_out
    if is_globally_opted_out(phone):
        return {
            "status": "suppressed",
            "message": "Recipient phone is globally suppressed across Brooke & Lauren desks due to STOP / opt-out."
        }

    phone_e164 = clean_phone_e164(phone)
    if not phone_e164:
        return {"status": "error", "message": "Invalid recipient phone number."}

    clean_message = strip_hyphens_for_sms(message)

    target_url = "https://api.sms-gate.app/3rdparty/v1/messages" if mode == "cloud" else f"{base_url}/3rdparty/v1/messages"

    payload = {
        "textMessage": {
            "text": clean_message
        },
        "phoneNumbers": [phone_e164],
        "simNumber": sim_number,
        "priority": 100
    }

    headers = {"Content-Type": "application/json"}
    auth = HTTPBasicAuth(username, password) if username or password else None

    try:
        resp = requests.post(target_url, json=payload, headers=headers, auth=auth, timeout=12)
        resp_data = resp.json() if resp.status_code in [200, 201, 202] else {"text": resp.text}

        from src.storage import data_manager
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "channel": "SMS",
            "direction": "OUTBOUND",
            "agent_id": agent_id,
            "recipient_phone": phone_e164,
            "message": message,
            "status": "SENT" if resp.status_code in [200, 201, 202] else "FAILED",
            "status_code": resp.status_code,
            "response": resp_data,
            "metadata": metadata or {}
        }
        data_manager.log_outreach(log_entry)

        if agent_id:
            data_manager.update_agent_state(agent_id, {
                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_contact_channel": "SMS",
                "pipeline_stage": "Contacted"
            })

        if resp.status_code not in [200, 201, 202]:
            return {
                "status": "error",
                "message": f"SMS Gateway returned HTTP {resp.status_code}: {resp.text}",
                "url": target_url
            }

        return {
            "status": "success",
            "message": "SMS dispatched successfully through your Android Gateway!",
            "phone": phone_e164,
            "gateway_response": resp_data
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Could not connect to Android SMS Gateway at {target_url}. Check phone connection or Wi-Fi IP: {str(e)}"
        }

def test_sms_connection() -> Dict[str, Any]:
    settings = load_sms_settings()
    mode = settings.get("mode", "local")
    base_url = settings.get("base_url", "http://192.168.1.100:8080").rstrip("/")
    username = settings.get("username", "admin")
    password = settings.get("password", "")
    target_url = "https://api.sms-gate.app/3rdparty/v1/health" if mode == "cloud" else f"{base_url}/"
    headers = {"Content-Type": "application/json"}
    auth = HTTPBasicAuth(username, password) if username or password else None

    try:
        resp = requests.get(target_url, headers=headers, auth=auth, timeout=6)
        if resp.status_code in [200, 201, 204]:
            return {"status": "success", "message": f"Successfully connected to Android Gateway! (HTTP {resp.status_code})"}
        elif resp.status_code == 401:
            return {"status": "error", "message": "Gateway reached, but Username/Password is incorrect (HTTP 401 Unauthorized)."}
        return {"status": "error", "message": f"Gateway returned HTTP {resp.status_code}"}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed to {target_url}: {str(e)}"}
