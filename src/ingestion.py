import os
import re
import csv
import json
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REDFIN_CACHE_FILE = os.path.join(DATA_DIR, "redfin_agent_cache.json")

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

# --- Redfin Scraping & Auto-Enrichment ---

def load_redfin_cache() -> Dict[str, Any]:
    if os.path.exists(REDFIN_CACHE_FILE):
        try:
            with open(REDFIN_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_redfin_cache(cache: Dict[str, Any]):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(REDFIN_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass

def scrape_redfin_agent_details(url: str, cache: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    if not url or not url.startswith("http"):
        return {"agent_name": "", "agent_phone": "", "brokerage": "", "broker_phone": "", "photo_url": ""}
    
    if cache is not None and url in cache:
        return cache[url]

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return {"agent_name": "", "agent_phone": "", "brokerage": "", "broker_phone": "", "photo_url": ""}
        
        agent_name = ""
        agent_phone = ""
        broker_phone = ""
        broker_name = ""
        
        # Match with optional backslashes for escaped json in reactServerState
        m_name = re.search(r'\\?"listingAgentName\\?"\s*:\s*\\?"([^\\"]+)', r.text)
        if m_name:
            try:
                agent_name = m_name.group(1).encode().decode('unicode_escape')
            except Exception:
                agent_name = m_name.group(1)
            
        m_phone = re.search(r'\\?"listingAgentNumber\\?"\s*:\s*\\?"([^\\"]+)', r.text)
        if m_phone:
            agent_phone = m_phone.group(1)
            
        m_bphone = re.search(r'\\?"listingBrokerNumber\\?"\s*:\s*\\?"([^\\"]+)', r.text)
        if m_bphone:
            broker_phone = m_bphone.group(1)
            
        m_broker = re.search(r'\\?"brokerName\\?"\s*:\s*\\?"([^\\"]+)', r.text)
        if m_broker:
            try:
                broker_name = m_broker.group(1).encode().decode('unicode_escape')
            except Exception:
                broker_name = m_broker.group(1)
            
        # Fallback Method 2: HTML tags
        if not agent_name:
            m_html_name = re.search(r'data-rf-test-id="agentInfoItem-agentDisplay"[^>]*>.*?Listed by <span>([^<]+)</span>', r.text, re.DOTALL)
            if m_html_name:
                agent_name = m_html_name.group(1).strip()

        # Listing Photo from OpenGraph
        m_img = re.search(r'<meta\s+(?:property=["\']og:image["\']\s+content=["\']([^"\']+)["\']|content=["\']([^"\']+)["\']\s+property=["\']og:image["\'])', r.text)
        photo_url = (m_img.group(1) or m_img.group(2) or "").strip() if m_img else ""
        
        res = {
            "agent_name": agent_name.strip(),
            "agent_phone": (agent_phone or broker_phone).strip(),
            "brokerage": broker_name.strip(),
            "broker_phone": broker_phone.strip(),
            "photo_url": photo_url
        }
        if cache is not None:
            cache[url] = res
        return res
    except Exception:
        return {"agent_name": "", "agent_phone": "", "brokerage": "", "broker_phone": "", "photo_url": ""}

def is_redfin_csv(file_path: str) -> bool:
    if not os.path.exists(file_path):
        return False
    try:
        with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
            header = f.readline().lower()
            return "redfin.com" in header or "url (see" in header or ("property type" in header and "price" in header and "city" in header)
    except Exception:
        return False

def parse_redfin_csv(file_path: str, max_workers: int = 15) -> List[Dict[str, Any]]:
    """
    Parses a Redfin Search CSV export, auto-enriches listing agent details via parallel
    page inspection, and groups records by unique listing agent with active listings.
    """
    if not os.path.exists(file_path):
        return []

    cache = load_redfin_cache()
    rows = []
    urls_to_scrape = set()

    with open(file_path, mode="r", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Find Redfin URL column
            url = ""
            for k, v in r.items():
                if k and ("url" in k.lower() or "redfin" in k.lower()):
                    if v and str(v).startswith("http"):
                        url = str(v).strip()
                        break
            r["_parsed_url"] = url
            if url and url not in cache:
                urls_to_scrape.add(url)
            rows.append(r)

    # Scrape missing URLs in parallel with thread pool
    if urls_to_scrape:
        print(f"[REDFIN ENRICHER] Scraping {len(urls_to_scrape)} new Redfin URLs with {max_workers} threads...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {executor.submit(scrape_redfin_agent_details, u): u for u in urls_to_scrape}
            for future in as_completed(future_to_url):
                u = future_to_url[future]
                try:
                    res = future.result()
                    if res:
                        cache[u] = res
                except Exception as e:
                    print(f"[REDFIN ENRICHER ERROR] {u}: {e}")
        save_redfin_cache(cache)

    agents_map: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        url = row.get("_parsed_url", "")
        agent_info = cache.get(url, {}) if url else {}
        
        agent_name = agent_info.get("agent_name") or "Listing Agent"
        phone_raw = agent_info.get("agent_phone") or agent_info.get("broker_phone") or ""
        brokerage = agent_info.get("brokerage") or "Real Estate Brokerage"
        
        first_name = agent_name.split()[0] if agent_name != "Listing Agent" else "there"
        last_name = " ".join(agent_name.split()[1:]) if len(agent_name.split()) > 1 else ""
        
        phone_norm = clean_phone(phone_raw)
        p_digits = raw_phone_digits(phone_raw)

        if p_digits and len(p_digits) >= 7:
            agent_key = f"phone_{p_digits}"
        elif agent_name and agent_name != "Listing Agent":
            agent_key = f"name_{agent_name.lower().replace(' ', '_')}"
        else:
            addr_key = (row.get("ADDRESS") or row.get("Address") or "unknown").lower().replace(" ", "_")
            agent_key = f"prop_{addr_key}"

        price = safe_float(row.get("PRICE") or row.get("Price") or row.get("Listing Price"))
        dom = safe_int(row.get("DAYS ON MARKET") or row.get("Days on Market"))
        beds = safe_float(row.get("BEDS") or row.get("Beds"))
        baths = safe_float(row.get("BATHS") or row.get("Baths"))
        sqft = safe_int(row.get("SQUARE FEET") or row.get("Square Feet") or row.get("Living Square Feet"))
        yr = safe_int(row.get("YEAR BUILT") or row.get("Year Built"))
        
        addr = (row.get("ADDRESS") or row.get("Address") or "").strip().title()
        city = (row.get("CITY") or row.get("City") or "").strip().title()
        state = (row.get("STATE OR PROVINCE") or row.get("State") or "FL").strip().upper()
        zip_code = (row.get("ZIP OR POSTAL CODE") or row.get("Zip") or "").strip()
        county = (row.get("LOCATION") or row.get("County") or "").strip().upper()
        mls_id = (row.get("MLS#") or row.get("Mls#") or "").strip()

        listing = {
            "id": mls_id or f"rf_{abs(hash(addr)) % 10000000}",
            "address": addr,
            "city": city,
            "state": state,
            "zip": zip_code,
            "county": county,
            "property_type": (row.get("PROPERTY TYPE") or row.get("Property Type") or "Single Family").strip(),
            "beds": beds,
            "baths": baths,
            "sqft": sqft,
            "year_built": yr,
            "listing_price": price,
            "days_on_market": dom,
            "listing_status": (row.get("STATUS") or "ACTIVE").strip().upper(),
            "estimated_value": round(price * 1.2, 2) if price else 275000.0,
            "redfin_url": url,
            "owner_name": "Property Owner",
            "owner_mailing": "",
            "tax_amount": 0.0
        }

        if agent_key not in agents_map:
            agents_map[agent_key] = {
                "agent_id": agent_key,
                "full_name": agent_name,
                "first_name": first_name,
                "last_name": last_name,
                "phone": phone_norm,
                "phone_raw": p_digits,
                "email": "",
                "brokerage": brokerage,
                "county": county or "CENTRAL FL",
                "listings": [],
                "pipeline_stage": "New Ingest",
                "notes": f"Imported from Redfin: {url}" if url else "",
                "pocket_deals": []
            }

        agents_map[agent_key]["listings"].append(listing)

    # Calculate summary metrics per agent
    agent_list = []
    for a in agents_map.values():
        total_vol = sum(l["listing_price"] for l in a["listings"])
        count = len(a["listings"])
        avg_p = total_vol / count if count > 0 else 0.0
        
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
        
        primary_l = a["listings"][0]
        a["primary_address"] = primary_l["address"]
        a["primary_city"] = primary_l["city"]
        a["primary_price"] = primary_l["listing_price"]
        a["primary_dom"] = primary_l["days_on_market"]
        
        agent_list.append(a)

    agent_list.sort(key=lambda x: (x["listing_count"], x["total_volume"]), reverse=True)
    return agent_list


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

def parse_real_estate_csv(file_path: str) -> List[Dict[str, Any]]:
    """Master router to automatically detect and parse either Redfin or Propwire CSVs."""
    if is_redfin_csv(file_path):
        return parse_redfin_csv(file_path)
    return parse_propwire_csv(file_path)
