import os
import re
import csv
import json
from typing import Dict, List, Any

def clean_phone(phone_val: Any) -> str:
    """Normalize phone to 10-digit standard or formatted (xxx) xxx-xxxx."""
    if not phone_val:
        return ""
    digits = re.sub(r'\D', '', str(phone_val))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return str(phone_val).strip()

def raw_phone_digits(phone_val: Any) -> str:
    if not phone_val:
        return ""
    digits = re.sub(r'\D', '', str(phone_val))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits

def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or val == "" or str(val).lower() == "nan":
            return default
        return float(str(val).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return default

def safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None or val == "" or str(val).lower() == "nan":
            return default
        return int(float(str(val).replace(",", "").strip()))
    except (ValueError, TypeError):
        return default

def parse_propwire_csv(file_path: str) -> List[Dict[str, Any]]:
    """
    Parses a Propwire CSV export and groups records by unique listing agent.
    Returns a list of structured agent profiles with nested active listings.
    """
    if not os.path.exists(file_path):
        return []

    agents_map: Dict[str, Dict[str, Any]] = {}

    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            agent_name = (row.get("Listing Agent Full Name") or "").strip()
            first_name = (row.get("Listing Agent First Name") or "").strip()
            last_name = (row.get("Listing Agent Last Name") or "").strip()
            phone_raw = (row.get("Listing Agent Phone") or "").strip()
            email = (row.get("Listing Agent Email") or "").strip().lower()
            brokerage = (row.get("Listing Brokerage Name") or "").strip()
            
            # If agent full name is missing, reconstruct
            if not agent_name and (first_name or last_name):
                agent_name = f"{first_name} {last_name}".strip()
            if not agent_name:
                agent_name = "Unknown Agent"

            # Derive brokerage from email domain if missing
            if not brokerage and "@" in email:
                domain = email.split("@")[1].split(".")[0].lower()
                if "exprealty" in domain:
                    brokerage = "eXp Realty"
                elif "kw" in domain or "keller" in domain:
                    brokerage = "Keller Williams"
                elif "remax" in domain:
                    brokerage = "RE/MAX"
                elif "compass" in domain:
                    brokerage = "Compass"
                elif "coldwell" in domain:
                    brokerage = "Coldwell Banker"
                elif "premier" in domain:
                    brokerage = "Premier Sotheby's"
                else:
                    brokerage = domain.capitalize()

            # Unique key: phone digits, or email, or agent name
            phone_norm = clean_phone(phone_raw)
            p_digits = raw_phone_digits(phone_raw)
            
            if p_digits and len(p_digits) >= 7:
                agent_key = f"phone_{p_digits}"
            elif email and "@" in email:
                agent_key = f"email_{email}"
            else:
                agent_key = f"name_{agent_name.lower().replace(' ', '_')}"

            # Listing Details
            price = safe_float(row.get("Listing Price"))
            est_val = safe_float(row.get("Estimated Value")) or safe_float(row.get("Market Value")) or price
            equity = safe_float(row.get("Estimated Equity"))
            equity_pct = safe_float(row.get("Estimated Equity Percent"))
            dom = safe_int(row.get("Days on Market"))
            
            # Owner name extraction
            o1_first = (row.get("Owner 1 First Name") or "").strip()
            o1_last = (row.get("Owner 1 Last Name") or "").strip()
            owner_name = f"{o1_first} {o1_last}".strip() if (o1_first or o1_last) else "Property Owner"

            listing = {
                "id": (row.get("Id") or "").strip(),
                "address": (row.get("Address") or "").strip().title(),
                "city": (row.get("City") or "").strip().title(),
                "state": (row.get("State") or "FL").strip().upper(),
                "zip": (row.get("Zip") or "").strip(),
                "county": (row.get("County") or "").strip().upper(),
                "apn": (row.get("APN") or "").strip(),
                "legal_description": (row.get("Legal Description") or "").strip(),
                "subdivision": (row.get("Subdivision") or "").strip().title(),
                "property_type": (row.get("Property Type") or row.get("Property Use") or "Single Family").strip(),
                "beds": safe_float(row.get("Bedrooms")),
                "baths": safe_float(row.get("Bathrooms")),
                "sqft": safe_int(row.get("Living Square Feet")),
                "year_built": safe_int(row.get("Year Built")),
                "listing_price": price,
                "days_on_market": dom,
                "listing_status": (row.get("Listing Status") or "ACTIVE").strip().upper(),
                "estimated_value": est_val,
                "estimated_equity": equity,
                "estimated_equity_percent": equity_pct,
                "owner_name": owner_name,
                "owner_mailing": (row.get("Owner Mailing Address") or "").strip(),
                "tax_amount": safe_float(row.get("Tax Amount"))
            }

            if agent_key not in agents_map:
                agents_map[agent_key] = {
                    "agent_id": agent_key,
                    "full_name": agent_name,
                    "first_name": first_name or agent_name.split()[0],
                    "last_name": last_name or (" ".join(agent_name.split()[1:]) if len(agent_name.split()) > 1 else ""),
                    "phone": phone_norm,
                    "phone_raw": p_digits,
                    "email": email,
                    "brokerage": brokerage or "Independent Brokerage",
                    "county": listing["county"],
                    "listings": [],
                    "pipeline_stage": "New Ingest",
                    "notes": "",
                    "pocket_deals": []
                }

            agents_map[agent_key]["listings"].append(listing)

    # Calculate summary metrics per agent
    agent_list = []
    for a in agents_map.values():
        total_vol = sum(l["listing_price"] for l in a["listings"])
        count = len(a["listings"])
        avg_p = total_vol / count if count > 0 else 0.0
        
        # Tier classification
        if count >= 3 or total_vol >= 1_000_000:
            tier = "Whale (High Volume)"
        elif count >= 2:
            tier = "Active Producer (2 Listings)"
        else:
            tier = "Single Listing Agent"

        a["listing_count"] = count
        a["total_volume"] = round(total_vol, 2)
        a["avg_price"] = round(avg_p, 2)
        a["tier"] = tier
        
        # Primary listing reference
        primary_l = a["listings"][0]
        a["primary_address"] = primary_l["address"]
        a["primary_city"] = primary_l["city"]
        a["primary_price"] = primary_l["listing_price"]
        a["primary_dom"] = primary_l["days_on_market"]
        
        agent_list.append(a)

    # Sort: highest listing count first, then volume
    agent_list.sort(key=lambda x: (x["listing_count"], x["total_volume"]), reverse=True)
    return agent_list
