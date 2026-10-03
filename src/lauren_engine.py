"""
Lauren Engine - On-Market Redfin Fixer-Upper & Trojan Horse Specialist
Acquisitions Underwriter for 407 Flips

Core Capabilities:
1. "Don't Look Stupid" Listing Awareness (analyzes public remarks before texting)
2. Socratic Trojan Horse Interrogation (asks for repair scope, cost, and back-end ARV)
3. Asymmetric ARV Arbitrage:
   - If Agent ARV < Redfin Estimate: Lock it in immediately! (Maximizes discount/profit)
   - If Agent ARV > Redfin Estimate: Anchor them down with real comps.
4. Exact MAO Formula (Nate Barger / DealsWithNate Framework):
   ARV - Rehab (Sqft + High Ticket) - 9% Fees (Carry, Closing, Commission) - 15-18% Margin - Wholesale Fee = Offer
5. "Standing LOI / In Case Circumstances Change" Paper Trail:
   Unless agent is a hard 'NO WAY', sends formal written terms via email/SMS.
6. 30-Day Recurring Check-in Cadence.
7. Smooth Handoff to Johnathan to close.
"""

import os
import re
import json
import time
import random
import requests
from typing import Dict, Any, Optional, List, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
FIXERS_DATA_FILE = os.path.join(DATA_DIR, "on_market_fixers.json")
BOT_SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")

# Retail condition target terms to mix up SMS phrasing (zero hyphens)
RETAIL_CONDITION_TARGETS = [
    "market ready",
    "top of the market",
    "fully renovated",
    "top dollar",
    "the finish line",
    "turnkey"
]

def sanitize_sms_no_hyphens(text: str) -> str:
    """
    Strict zero hyphens rule for SMS.
    Replaces any hyphen between words with a space and removes dashes.
    """
    if not text:
        return ""
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)
    text = re.sub(r'\s*[-–—]\s*', ' ', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()

def resolve_spin(text: str) -> str:
    """
    Resolves nested or unnested {option1|option2|option3} spin syntax.
    """
    pattern = re.compile(r'\{([^{}]+)\}')
    while True:
        match = pattern.search(text)
        if not match:
            break
        options = match.group(1).split('|')
        text = text[:match.start()] + random.choice(options) + text[match.end():]
    return sanitize_sms_no_hyphens(text)

# --- Standard Rehab Cost Baselines ($/sqft) ---
REHAB_TIERS = {
    "TURNKEY": 0,
    "LIPSTICK": 25,
    "LG_COSMETIC": 30,
    "MG_COSMETIC": 35,
    "HG_COSMETIC": 45,
    "MEDIUM_REHAB": 50,
    "MEDIUM_HIGH": 55,
    "FULL_GUT": 60,
    "FULL_GUT_HIGH": 65,
    "MILLION_DOLLAR": 75,
}

# High Ticket Item Defaults ($)
DEFAULT_HIGH_TICKET = {
    "roof_under_1000sqft": 7500,
    "roof_standard": 12500,
    "hvac_full": 6000,
    "hvac_repair_reduct": 3000,
    "water_heater": 3000,
    "whole_house_replumb": 15000,
    "electrical_rewiring": 10000,
}


def load_fixers() -> List[Dict[str, Any]]:
    if os.path.exists(FIXERS_DATA_FILE):
        try:
            with open(FIXERS_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_fixers(fixers: List[Dict[str, Any]]):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FIXERS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(fixers, f, indent=2)


def calculate_trojan_horse_mao(
    arv: float,
    sqft: float,
    rehab_per_sqft: float = 40.0,
    high_ticket_total: float = 0.0,
    closing_cost_pct: float = 0.02,
    carrying_cost_pct: float = 0.02,
    commission_pct: float = 0.05,
    flipper_profit_pct: float = 0.15,
    wholesale_fee: float = 0.0,
) -> Dict[str, Any]:
    """
    Computes Max Allowable Offer (MAO) according to the user's Nate Barger underwriting calculator.
    Formula:
      Total Rehab = (sqft * rehab_per_sqft) + high_ticket_total
      Total Fees = arv * (closing_cost_pct + carrying_cost_pct + commission_pct) [Typically 9%]
      Flippers Profit = arv * flipper_profit_pct [Typically 15% - 18%]
      Dispo/Purchase Target = ARV - Total Rehab - Total Fees - Flippers Profit
      Offer Price = Dispo Target - wholesale_fee
    """
    if arv <= 0:
        return {"error": "ARV must be greater than zero"}

    sqft_rehab = sqft * rehab_per_sqft
    total_rehab = sqft_rehab + high_ticket_total
    
    total_fees_pct = closing_cost_pct + carrying_cost_pct + commission_pct
    total_fees = arv * total_fees_pct
    
    flippers_profit = arv * flipper_profit_pct
    dispo_target = arv - total_rehab - total_fees - flippers_profit
    offer_price = max(0.0, dispo_target - wholesale_fee)

    return {
        "arv": round(arv, 2),
        "sqft": round(sqft, 2),
        "rehab_per_sqft": round(rehab_per_sqft, 2),
        "sqft_rehab_cost": round(sqft_rehab, 2),
        "high_ticket_total": round(high_ticket_total, 2),
        "total_rehab": round(total_rehab, 2),
        "rehab_pct_of_arv": round((total_rehab / arv) * 100, 1) if arv > 0 else 0,
        "closing_cost": round(arv * closing_cost_pct, 2),
        "carrying_cost": round(arv * carrying_cost_pct, 2),
        "agent_commission": round(arv * commission_pct, 2),
        "total_fees": round(total_fees, 2),
        "total_fees_pct": round(total_fees_pct * 100, 1),
        "flippers_profit": round(flippers_profit, 2),
        "flippers_profit_pct": round(flipper_profit_pct * 100, 1),
        "dispo_target": round(dispo_target, 2),
        "wholesale_fee": round(wholesale_fee, 2),
        "offer_price": round(offer_price, 2),
        "discount_from_arv_pct": round((1 - (offer_price / arv)) * 100, 1) if arv > 0 else 0,
        "math_explanation": (
            f"ARV (${arv:,.0f}) - Repairs (${total_rehab:,.0f}) - Fees (${total_fees:,.0f}) "
            f"- 15% Profit (${flippers_profit:,.0f}) = Target Offer: ${offer_price:,.0f}"
        )
    }


def infer_florida_county(city: str, address: str = "", zip_code: str = "") -> str:
    c = (city or "").upper().strip()
    if any(k in c for k in ["ST PETERSBURG", "ST. PETERSBURG", "ST PETE", "CLEARWATER", "LARGO", "PINELLAS PARK", "DUNEDIN", "TARPON SPRINGS", "SAFETY HARBOR", "SEMINOLE", "GULFPORT", "PALM HARBOR", "OLDSMAR", "MADEIRA BEACH", "TREASURE ISLAND", "ST PETE BEACH", "BELLEAIR", "KENNETH CITY", "INDIAN ROCKS", "SOUTH PASADENA"]):
        return "PINELLAS"
    if any(k in c for k in ["TAMPA", "BRANDON", "RIVERVIEW", "PLANT CITY", "VALRICO", "RUSKIN", "APOLLO BEACH", "LUTZ", "TEMPLE TERRACE", "SEFFNER", "GIBSONTON", "WIMAUMA"]):
        return "HILLSBOROUGH"
    if any(k in c for k in ["NEW PORT RICHEY", "PORT RICHEY", "WESLEY CHAPEL", "ZEPHYRHILLS", "LAND O LAKES", "HUDSON", "HOLIDAY", "DADE CITY", "TRINITY", "ODESSA"]):
        return "PASCO"
    if any(k in c for k in ["ORLANDO", "WINTER PARK", "APOPKA", "OCOEE", "WINTER GARDEN", "WINDERMERE", "MAITLAND", "BELLE ISLE", "PINE HILLS"]):
        return "ORANGE"
    if any(k in c for k in ["SANFORD", "LAKE MARY", "ALTAMONTE", "OVIEDO", "CASSELBERRY", "LONGWOOD", "WINTER SPRINGS"]):
        return "SEMINOLE"
    if any(k in c for k in ["MELBOURNE", "PALM BAY", "TITUSVILLE", "COCOA", "ROCKLEDGE", "MERRITT ISLAND", "SATELLITE BEACH", "CAPE CANAVERAL", "WEST MELBOURNE", "INDIALANTIC", "MIMS", "MALABAR", "GRANT"]):
        return "BREVARD"
    if any(k in c for k in ["SARASOTA", "VENICE", "NORTH PORT", "ENGLEWOOD", "OSPREY", "NOKOMIS"]):
        return "SARASOTA"
    if any(k in c for k in ["BRADENTON", "LAKEWOOD RANCH", "PALMETTO", "ELLENTON", "PARRISH", "ANNA MARIA"]):
        return "MANATEE"
    if any(k in c for k in ["LAKELAND", "WINTER HAVEN", "DAVENPORT", "HAINES CITY", "BARTOW", "LAKE WALES"]):
        return "POLK"
    if any(k in c for k in ["KISSIMMEE", "ST CLOUD", "ST. CLOUD", "CELEBRATION", "POINCIANA"]):
        return "OSCEOLA"
    if any(k in c for k in ["DAYTONA", "DELTONA", "DELAND", "PORT ORANGE", "ORMOND BEACH", "NEW SMYRNA"]):
        return "VOLUSIA"
    if any(k in c for k in ["FORT MYERS", "CAPE CORAL", "LEHIGH ACRES", "BONITA SPRINGS", "ESTERO"]):
        return "LEE"
    if any(k in c for k in ["WEST PALM BEACH", "BOCA RATON", "BOYNTON BEACH", "DELRAY BEACH", "JUPITER", "WELLINGTON", "LAKE WORTH"]):
        return "PALM BEACH"
    if any(k in c for k in ["FORT LAUDERDALE", "PEMBROKE PINES", "HOLLYWOOD", "CORAL SPRINGS", "MIRAMAR", "POMPANO BEACH", "DAVIE", "PLANTATION"]):
        return "BROWARD"
    if any(k in c for k in ["MIAMI", "HIALEAH", "HOMESTEAD", "CORAL GABLES", "DORAL", "KENDALL", "AVENTURA"]):
        return "MIAMI-DADE"
    if any(k in c for k in ["JACKSONVILLE", "ATLANTIC BEACH", "NEPTUNE BEACH"]):
        return "DUVAL"
    if any(k in c for k in ["OCALA", "BELLEVIEW"]):
        return "MARION"
    if any(k in c for k in ["CLERMONT", "LEESBURG", "EUSTIS", "MOUNT DORA", "TAVARES"]):
        return "LAKE"
    return "FLORIDA"


class LaurenEngine:
    """
    On-Market Trojan Horse Conversation & Underwriting Agent
    Specialist: Lauren (Acquisitions Underwriter at 407 Flips)
    """

    def __init__(self):
        pass

    def get_initial_fixer_state(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        list_price = float(property_data.get("list_price") or 0.0)
        redfin_est = float(property_data.get("redfin_estimate") or property_data.get("zestimate") or (list_price * 1.25 if list_price else 275000.0))
        sqft = float(property_data.get("sqft") or 1200)

        # Baseline calculation at $40/sqft + $10k buffer
        baseline_calc = calculate_trojan_horse_mao(
            arv=redfin_est,
            sqft=sqft,
            rehab_per_sqft=40.0,
            high_ticket_total=10000.0,
            flipper_profit_pct=0.15,
            wholesale_fee=0.0
        )

        city = property_data.get("city", "Florida")
        address = property_data.get("address", "")
        zip_code = property_data.get("zip", "")
        raw_county = property_data.get("county")
        county = raw_county if (raw_county and raw_county not in ["BREVARD", "FLORIDA"] or "BREVARD" in city.upper()) else infer_florida_county(city, address, zip_code)
        if not county or county == "FLORIDA":
            county = infer_florida_county(city, address, zip_code)

        return {
            "id": property_data.get("id") or f"fixer_{int(time.time())}_{property_data.get('address', 'prop').replace(' ', '_')[:20]}",
            "address": address,
            "city": city,
            "county": county,
            "zip": zip_code,
            "list_price": list_price,
            "redfin_estimate": redfin_est,
            "dom": int(property_data.get("dom") or 1),
            "sqft": sqft,
            "beds": property_data.get("beds", ""),
            "baths": property_data.get("baths", ""),
            "year_built": property_data.get("year_built", ""),
            "photo_url": property_data.get("photo_url", ""),
            "redfin_url": property_data.get("redfin_url", ""),
            "remarks": property_data.get("remarks", ""),
            # Listing Agent
            "agent_name": property_data.get("agent_name", "Listing Agent"),
            "agent_phone": property_data.get("agent_phone", ""),
            "agent_email": property_data.get("agent_email", ""),
            "brokerage": property_data.get("brokerage", ""),
            # Underwriting State
            "underwriting": baseline_calc,
            "agent_repair_estimate": None,
            "agent_arv_estimate": None,
            "effective_arv": redfin_est,
            "current_node": "OPENING_HOOK",
            "status": "NEW",  # NEW, VETTING_REPAIRS, ARV_ANCHORED, MATH_PRESENTED, LOI_SENT, APPT_SET, 30_DAY_FOLLOWUP, DEAD
            "messages": [],
            "standing_loi_sent": False,
            "last_interaction": time.strftime("%Y-%m-%d %H:%M:%S")
        }

from datetime import datetime, timedelta

def check_underwriting_contradictions(fixer: Dict[str, Any], current_msg: str = "") -> Tuple[bool, List[str]]:
    """
    Checks if agent-provided intel indicates mechanicals/systems are in good or updated condition
    while the underwriting still includes high-ticket repair line items.
    """
    all_text = (fixer.get("repair_notes", "") + " " + current_msg + " " + " ".join(
        m.get("text", "") for m in fixer.get("messages", []) if m.get("direction") == "INBOUND"
    )).lower()

    contradictions = []

    # 1. Roof
    roof_good = bool(re.search(r'\b(roof|shingle|tile)\b.*?\b(new|good|great|fine|replaced|updated|done|(\d{1,2})\s*years?|201[89]|202[0-9])\b', all_text) or
                     re.search(r'\b(new|good|great|fine|replaced|updated|done|(\d{1,2})\s*years?|201[89]|202[0-9])\b.*?\b(roof|shingle|tile)\b', all_text))
    if roof_good:
        contradictions.append("Agent reported Roof in good/recent condition. Check if roof replacement is still in high-ticket repairs.")

    # 2. HVAC / AC
    hvac_good = bool(re.search(r'\b(hvac|ac|a\/c|air conditioner|compressor)\b.*?\b(new|good|great|fine|working|replaced|updated|serviced|(\d{1,2})\s*years?|201[789]|202[0-9])\b', all_text) or
                     re.search(r'\b(new|good|great|fine|working|replaced|updated|serviced|(\d{1,2})\s*years?|201[789]|202[0-9])\b.*?\b(hvac|ac|a\/c|air conditioner|compressor)\b', all_text))
    if hvac_good:
        contradictions.append("Agent reported HVAC/AC is working or recently replaced. Verify HVAC repair allocation.")

    # 3. Plumbing
    plumbing_good = bool(re.search(r'\b(plumbing|pipes|repiped|repipe|pvc|copper)\b.*?\b(new|good|great|fine|updated|repiped|replaced)\b', all_text))
    if plumbing_good:
        contradictions.append("Agent reported Plumbing repiped or updated. Verify whole house replumb line item.")

    # 4. Electrical
    electrical_good = bool(re.search(r'\b(electrical|panel|breaker|wiring|rewired)\b.*?\b(new|good|great|fine|updated|200\s*amp|replaced)\b', all_text))
    if electrical_good:
        contradictions.append("Agent reported Electrical panel or wiring updated. Verify rewiring line item.")

    return len(contradictions) > 0, contradictions


class LaurenEngine:
    """
    On-Market Trojan Horse Conversation & Underwriting Agent
    Specialist: Lauren (Acquisitions Underwriter at 407 Flips)
    """

    def __init__(self):
        pass

    def get_initial_fixer_state(self, property_data: Dict[str, Any]) -> Dict[str, Any]:
        list_price = float(property_data.get("list_price") or 0.0)
        redfin_est = float(property_data.get("redfin_estimate") or property_data.get("zestimate") or (list_price * 1.25 if list_price else 275000.0))
        sqft = float(property_data.get("sqft") or 1200)

        # Baseline calculation at $40/sqft + $10k buffer
        baseline_calc = calculate_trojan_horse_mao(
            arv=redfin_est,
            sqft=sqft,
            rehab_per_sqft=40.0,
            high_ticket_total=10000.0,
            flipper_profit_pct=0.15,
            wholesale_fee=0.0
        )

        city = property_data.get("city", "Florida")
        address = property_data.get("address", "")
        zip_code = property_data.get("zip", "")
        raw_county = property_data.get("county")
        county = raw_county if (raw_county and raw_county not in ["BREVARD", "FLORIDA"] or "BREVARD" in city.upper()) else infer_florida_county(city, address, zip_code)
        if not county or county == "FLORIDA":
            county = infer_florida_county(city, address, zip_code)

        return {
            "id": property_data.get("id") or f"fixer_{int(time.time())}_{property_data.get('address', 'prop').replace(' ', '_')[:20]}",
            "address": address,
            "city": city,
            "county": county,
            "zip": zip_code,
            "list_price": list_price,
            "redfin_estimate": redfin_est,
            "dom": int(property_data.get("dom") or 1),
            "sqft": sqft,
            "beds": property_data.get("beds", ""),
            "baths": property_data.get("baths", ""),
            "year_built": property_data.get("year_built", ""),
            "photo_url": property_data.get("photo_url", ""),
            "redfin_url": property_data.get("redfin_url", ""),
            "remarks": property_data.get("remarks", ""),
            # Listing Agent
            "agent_name": property_data.get("agent_name", "Listing Agent"),
            "agent_phone": property_data.get("agent_phone", ""),
            "agent_email": property_data.get("agent_email", ""),
            "brokerage": property_data.get("brokerage", ""),
            # Underwriting State
            "underwriting": baseline_calc,
            "agent_repair_estimate": None,
            "agent_arv_estimate": None,
            "effective_arv": redfin_est,
            "current_node": "OPENING_HOOK",
            "status": "NEW",  # NEW, VETTING_REPAIRS, ARV_ANCHORED, MATH_PRESENTED, LOI_SENT, APPT_SET, 30_DAY_FOLLOWUP, DEAD
            "messages": [],
            "standing_loi_sent": False,
            "underwriting_contradiction_flag": False,
            "contradiction_details": [],
            "followup_task": None,
            "last_interaction": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def generate_opening_hook(self, fixer: Dict[str, Any]) -> str:
        """
        Creates natural, concise opening SMS applying the Don't Look Stupid rule & Muse Critique.
        - Opener template rule: Always includes FULL street address (never street name alone).
        - Never leads with off-MLS private intel (utilities off, liens, etc.) that the agent cannot verify.
        - Introduces as 'Lauren here' or 'its Lauren'.
        - Crisp, professional investor tone without fake gushing or syrupy gratitude.
        - Strict zero hyphens rule.
        """
        agent_first = fixer.get("agent_name", "there").split()[0]
        addr = fixer.get("address") or "the property"
        # Ensure full street address (e.g. 7158 Summit Dr)
        if addr and addr != "the property" and not re.match(r'^\d+', addr.strip()):
            # If street number missing, fallback to whatever address is present
            addr = fixer.get("address", "the property")

        remarks = fixer.get("remarks", "").lower()

        # Identify mentioned items from public MLS remarks to avoid asking about them
        has_cash_only = "cash" in remarks or "hard money" in remarks
        has_as_is = "as is" in remarks or "as-is" in remarks
        has_repairs_needed = any(w in remarks for w in ["needs", "handyman", "tlc", "fixer", "roof", "updating", "work"])

        retail_target = random.choice(RETAIL_CONDITION_TARGETS)

        intro = random.choice([
            f"Hey {agent_first}, Lauren here.",
            f"Hi {agent_first}, its Lauren.",
            f"Hey {agent_first}, its Lauren.",
            f"Hi {agent_first}, Lauren here."
        ])

        if has_cash_only or has_as_is or has_repairs_needed:
            # Listing remarks already mention condition/repairs - acknowledge once and ask for anything else major
            angles = [
                f"{intro} Looking to write a cash offer on {addr}. Outside of what is already listed, is there anything else I should know before I pencil it out?",
                f"{intro} Want to make a clean cash offer on {addr}. Beyond what is noted in the listing, anything major I should know before I pencil it out?",
                f"{intro} Had a quick question on {addr}. Beyond what is noted in the listing, does it need any other heavy work to reach {retail_target}?",
                f"{intro} Checked out {addr}. Outside of what you have in the listing remarks, are there any other big ticket repairs needed to hit {retail_target}?",
                f"{intro} Reaching out regarding {addr}. Other than what is disclosed online, is there anything else major needed before I pencil out an offer?"
            ]
        else:
            # Clean / Standard listing remarks
            angles = [
                f"{intro} Looking to put together a cash offer on {addr}. Other than what is listed online, anything I should know before I pencil it out?",
                f"{intro} Want to write an offer on {addr}. Besides what you have in the listing remarks, anything I should know before I pencil it out?",
                f"{intro} Had a quick question on {addr}. Other than what is noted in the listing, are there any big ticket repairs needed to get it to {retail_target}?",
                f"{intro} Reaching out about {addr}. Outside of what is listed online, does the house need any major work before I pencil out an offer?",
                f"{intro} Quick question on {addr}. Besides what you have listed, does it need any heavy mechanical or structural updates to reach {retail_target}?"
            ]

        full_text = random.choice(angles)
        return sanitize_sms_no_hyphens(full_text)

    def evaluate_inbound(self, fixer: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Processes an agent reply through Lauren's Trojan Horse engine.
        Applies Muse Critique, Asymmetric ARV Arbitrage, Nate Barger MAO math,
        Deflection Auto-Pivot, Soft-No 30-Day Check-in, Number-Change Re-route,
        and Underwriting Contradiction Checks.
        """
        from src.storage import add_global_opt_out, extract_reroute_phone_number

        clean_msg = message.lower().strip()
        curr_node = fixer.get("current_node", "OPENING_HOOK")
        agent_first = fixer.get("agent_name", "there").split()[0]
        addr = fixer.get("address", "the property")
        redfin_est = fixer.get("redfin_estimate") or 250000.0
        sqft = fixer.get("sqft") or 1200.0

        # 0. Number-Change Re-route Detection
        new_reroute_phone = extract_reroute_phone_number(message)
        if new_reroute_phone:
            old_phone = fixer.get("agent_phone", "")
            if old_phone and re.sub(r'\D', '', old_phone)[-10:] != re.sub(r'\D', '', new_reroute_phone)[-10:]:
                fixer["agent_phone"] = new_reroute_phone
                fixer["rerouted_from_phone"] = old_phone
                fixer["reroute_note"] = f"Agent requested texting at {new_reroute_phone}."

        # 1. Hard Opt Out Guard -> Global Suppression
        if any(w in clean_msg for w in ["stop", "unsubscribe", "remove", "wrong number", "don't text", "dont text", "f*** off", "fuck off", "lose my number", "do not contact", "harassment"]):
            if fixer.get("agent_phone"):
                add_global_opt_out(fixer.get("agent_phone"), source_desk="LAUREN", reason="Agent requested opt-out.")
            fixer["status"] = "DEAD"
            fixer["current_node"] = "DEAD"
            return {
                "action": "OPT_OUT",
                "reply_text": "",
                "node": "DEAD",
                "reason": "Agent requested opt-out. Suppressed globally across Brooke & Lauren desks."
            }

        # 2. Identity Inquiry ("Who is this?")
        if any(w in clean_msg for w in ["who is this", "who's this", "whos this", "who are you", "what company", "who is texting"]):
            reply = (
                f"Hey {agent_first}, its Lauren. John and I are local buyers looking for our next renovation project in "
                f"{fixer.get('city', 'the area')}. Reached out regarding {addr}. Are you still working with the sellers on this one?"
            )
            fixer["current_node"] = "IDENTITY_ANSWERED"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "IDENTITY_ANSWERED",
                "reason": "Lauren introduced herself and partner John, refocusing on the property."
            }

        # 3. Agent / Representation / Licensing Inquiry ("Are you an agent?", "Are you licensed?", "Do you have an agent?")
        if any(w in clean_msg for w in ["are you an agent", "are you a realtor", "are you licensed", "are you the buyer", "do you have an agent", "who is your agent", "are you represented", "is this an agent", "what brokerage"]):
            reply = (
                "No, we are direct cash buyers. We are unrepresented, so you can write up the offer for us if the numbers work. Are the sellers flexible on price for a quick close?"
            )
            fixer["current_node"] = "UNREPRESENTED_CONFIRMED"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "UNREPRESENTED_CONFIRMED",
                "reason": "Agent asked about representation status. Clarified direct unrepresented cash buyer with double commission incentive."
            }

        # 4. Soft-No Detection -> Auto-log 30-Day Follow-Up Task
        SOFT_NO_PATTERNS = [
            "keep you in mind", "keep you guys in mind", "keep your info", "keep in mind",
            "nothing right now", "not right now", "nothing at this time", "nothing at the moment",
            "not at this time", "not at the moment", "maybe in the future", "maybe later",
            "will keep an eye out", "ill let you know if something comes up", "will let you know",
            "will reach out if anything pops up", "don't have anything right now", "dont have anything right now"
        ]
        if any(p in clean_msg for p in SOFT_NO_PATTERNS):
            followup_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
            fixer["followup_task"] = {
                "type": "30_DAY_CHECKIN",
                "scheduled_date": followup_date,
                "status": "PENDING",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "note": "Agent replied with soft no. Auto-logged 30-day follow-up task."
            }
            fixer["current_node"] = "30_DAY_FOLLOWUP"
            fixer["status"] = "30_DAY_FOLLOWUP"
            reply = (
                "Appreciate it! We will keep an eye out and check back in a few weeks. If anything changes with this one or another project pops up, feel free to reach out anytime."
            )
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "30_DAY_FOLLOWUP",
                "reason": "Agent gave a soft no. Auto-logged 30-day follow-up task instead of closing thread."
            }

        # 5. Deflection Detection -> Auto-Pivot to ARV Extraction Rule
        DEFLECTION_PATTERNS = [
            "inspection summary covers",
            "inspection report covers",
            "everything they know",
            "all in the listing",
            "that's all in the listing",
            "thats all in the listing",
            "everything is in the listing",
            "everything in the listing",
            "i don't have more info",
            "dont have more info",
            "dont have any more info",
            "don't know anything else",
            "dont know anything else",
            "see the mls",
            "check the mls",
            "all info is on the listing",
            "read the remarks",
            "refer to listing",
            "see inspection report",
            "attached inspection",
            "dont know much about it",
            "seller doesn't know anything else",
            "seller doesnt know anything else"
        ]
        has_deflection = any(d in clean_msg for d in DEFLECTION_PATTERNS)

        if has_deflection and curr_node in ["OPENING_HOOK", "NEW", "ASKED_REPAIR_SCOPE", "ASKED_REPAIR_COST"]:
            fixer["repair_notes"] = fixer.get("repair_notes", "") + " | " + message
            reply = (
                "Makes sense. Once it is all brought back to top dollar condition, what do you realistically think it lists and sells for on the back end?"
            )
            fixer["current_node"] = "ASKED_AGENT_ARV"
            fixer["status"] = "VETTING_REPAIRS"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "ASKED_AGENT_ARV",
                "reason": "Deflection detected ('all in listing/inspection'). Flowchart Rule: Skipped condition questions and auto-pivoted to ARV extraction."
            }

        has_pushback = any(w in clean_msg for w in ["no way", "turned down", "too low", "seller won't", "seller wont", "under 180", "anything under", "insulting", "firm on", "waste of time", "pass on", "cannot accept", "cant accept", "gap"])
        has_comp_word = bool(re.search(r'\b(comps?|arv|resale|worth|sell for|list for)\b', clean_msg))
        has_repair_detail = any(w in clean_msg for w in ["roof", "a/c", "ac", "plumbing", "electrical", "dated", "rehab", "repairs", "work", "handyman", "kitchen", "bath", "flooring", "paint", "needs"])

        # 6. Pushback & Price Resistance -> Trojan Horse Step 5: Send Standing Written LOI Rule
        if has_pushback or (curr_node == "MATH_PRESENTED" and not has_comp_word and not has_repair_detail):
            offer_val = fixer.get("underwriting", {}).get("offer_price") or 128000.0
            reply = (
                f"Totally understand we have a gap right now. I just emailed our formal written terms "
                f"as a standing cash offer at ${offer_val:,.0f} in case the seller timeline or circumstances change, "
                f"or if a retail buyer falls through. Our offer stands for 30 days. If anything shifts, John and I are ready to close clean in 14 days."
            )
            fixer["standing_loi_sent"] = True
            fixer["status"] = "STANDING_LOI_SENT"
            fixer["current_node"] = "STANDING_LOI_SENT"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "STANDING_LOI_SENT",
                "reason": "Agent objected or pushed back on price. Dispatched Standing Written LOI rule."
            }

        # 7. Agent already at ASKED_REPAIR_COST -> Advance to Trojan Horse Step 4 (Back-End Resale ARV)
        if curr_node == "ASKED_REPAIR_COST" and not has_comp_word:
            repair_cand = self._extract_dollar_amount(message)
            if repair_cand and repair_cand < (redfin_est * 0.50):
                fixer["agent_repair_estimate"] = repair_cand
            else:
                fixer["repair_notes"] = fixer.get("repair_notes", "") + " | " + message

            reply = (
                "Makes sense, sounds mostly cosmetic. What do you think it will realistically sell for once it is finished?"
            )
            fixer["current_node"] = "ASKED_AGENT_ARV"
            fixer["status"] = "VETTING_REPAIRS"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "ASKED_AGENT_ARV",
                "reason": "Trojan Horse Step 3: Repair details noted, advancing to back end resale ARV."
            }

        # 8. Repair Scope Initial Detail (Agent details condition from Opening Hook) -> Trojan Horse Step 2
        if has_repair_detail and not has_comp_word and curr_node in ["OPENING_HOOK", "NEW"]:
            fixer["repair_notes"] = message
            repair_cand = self._extract_dollar_amount(message)
            if repair_cand and repair_cand < (redfin_est * 0.50):
                fixer["agent_repair_estimate"] = repair_cand

            retail_target = random.choice(RETAIL_CONDITION_TARGETS)
            reply = (
                f"Got it, that helps a lot. What ballpark dollar amount do you think is needed in materials and labor to get it {retail_target}?"
            )
            fixer["current_node"] = "ASKED_REPAIR_COST"
            fixer["status"] = "VETTING_REPAIRS"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "ASKED_REPAIR_COST",
                "reason": "Trojan Horse Step 2: Repair scope noted, asking for repair dollar estimate."
            }

        # 9. Back-End ARV / Comps -> Trojan Horse Step 4: Execute Asymmetric ARV Arbitrage & Math Drop
        if has_comp_word or curr_node == "ASKED_AGENT_ARV":
            arv_cand = self._extract_dollar_amount(message)
            agent_arv = arv_cand or redfin_est
            fixer["agent_arv_estimate"] = agent_arv

            # Underwriting Contradiction Check: Compare agent intel against repair inputs
            has_contradiction, contradiction_details = check_underwriting_contradictions(fixer, message)
            fixer["underwriting_contradiction_flag"] = has_contradiction
            fixer["contradiction_details"] = contradiction_details

            # ASYMMETRIC ARV ARBITRAGE RULE:
            # 1. Agent comes in LOW: Accept their comp immediately! Say nothing about higher comps.
            # 2. Agent comes in HIGH or close to right: Anchor them down showing low comps as possible.
            if agent_arv < redfin_est:
                effective_arv = agent_arv
                intro_phrase = f"Running your numbers through our calculator: based on your ${agent_arv:,.0f} resale number"
            else:
                effective_arv = min(agent_arv * 0.85, redfin_est * 0.95)
                intro_phrase = f"We looked closely at those comps, but recent conservative sales in the pocket are sitting lower around ${effective_arv:,.0f}. Running that through our calculator"

            fixer["effective_arv"] = effective_arv

            # Calculate rehab
            est_repair = fixer.get("agent_repair_estimate")
            if not est_repair or est_repair > (effective_arv * 0.50):
                agent_rehab = (sqft * 40.0) + 10000.0
            else:
                agent_rehab = est_repair

            # Run Nate Barger Formula
            calc = calculate_trojan_horse_mao(
                arv=effective_arv,
                sqft=sqft,
                rehab_per_sqft=35.0,
                high_ticket_total=agent_rehab - (sqft * 35.0) if agent_rehab > (sqft * 35.0) else 10000.0,
                closing_cost_pct=0.02,
                carrying_cost_pct=0.02,
                commission_pct=0.05,
                flipper_profit_pct=0.15,
                wholesale_fee=0.0
            )
            fixer["underwriting"] = calc
            offer = calc["offer_price"]

            if offer <= 0:
                offer_phrase = "leaves zero margin at all"
            else:
                offer_phrase = f"puts John right around ${offer:,.0f} cash with zero inspection contingencies"

            reply = (
                f"{intro_phrase}, minus ~${agent_rehab:,.0f} in repairs, 9 percent in holding and commission fees, and our standard 15 percent margin "
                f"{offer_phrase}. That is why we are coming in under that one. "
                f"Would it make sense to send over an offer and have John connect with you?"
            )
            fixer["current_node"] = "MATH_PRESENTED"
            fixer["status"] = "MATH_PRESENTED"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "MATH_PRESENTED",
                "contradiction_flag": has_contradiction,
                "contradiction_details": contradiction_details,
                "reason": "Trojan Horse Step 4: Socratic math drop using agent's own figures." + (" [⚠️ Contradiction flagged: review repairs before sending]" if has_contradiction else "")
            }

        # 10. Default Step 1 Hook Follow-up
        reply = (
            f"Got it {agent_first}. In your opinion, what shape are the major mechanicals in "
            f"(roof, AC, plumbing, electrical), and what kind of work do you think it needs to get it retail ready?"
        )
        fixer["current_node"] = "ASKED_REPAIR_SCOPE"
        fixer["status"] = "VETTING_REPAIRS"
        return {
            "action": "SUGGEST",
            "reply_text": sanitize_sms_no_hyphens(reply),
            "node": "ASKED_REPAIR_SCOPE",
            "reason": "Trojan Horse Step 1: Inquiring on repair scope directly from the agent without syrupy gratitude."
        }

    def _extract_dollar_amount(self, text: str) -> Optional[float]:
        clean = text.lower().replace(",", "")
        k_m = re.search(r'\$?(\d+(?:\.\d+)?)\s*k\b', clean)
        if k_m:
            return float(k_m.group(1)) * 1000.0
        n_m = re.search(r'\$?(\d{4,8})\b', clean)
        if n_m:
            val = float(n_m.group(1))
            if val >= 5000:
                return val
        return None


lauren_engine = LaurenEngine()
