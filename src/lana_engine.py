"""
Lana Engine - On-Market Infill Land Specialist & Residual Underwriting Agent
Third Desk of Agent Hunter (Lauren: On-Market Fixers, Brooke: Pocket Listings, Lana: Infill Land)

Core Capabilities:
1. Infill Land Targeting Filters (4,000 sqft - 0.5 acre, active, residential, DOM >= 60, list >= $80k)
2. Residual Land Value Underwriting Calculator:
   max_payable = finished_newbuild_value - (build_cost_psf * planned_sqft) - builder_profit - fees
   Send Rule: offer = 60% of asking; send LOI only if offer <= max_payable
3. Socratic Land Qualification (one question per SMS: buildable?, utilities?, setbacks?, impact fees?)
4. Short SMS Doorbell LOI + Full Emailed Written LOI
5. Land Golden Objections:
   - "Price is firm" -> Production builder discipline
   - "Why so low" -> The Land Math Drop (full build-cost breakdown)
   - "Is your client real" -> Builder credentials, spec portfolio, verified POF
   - "We have other interest" -> Standby backup cash buyer
6. Friday Follow-Up Sequence & End-of-Month Blitz
7. Multi-Lot Agent Consolidation (one combined text per agent for multiple listings)
8. Zero Hyphens SMS rule
"""

import os
import re
import json
import time
import random
from typing import Dict, Any, Optional, List, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOTS_DATA_FILE = os.path.join(DATA_DIR, "on_market_lots.json")
BUILD_COSTS_FILE = os.path.join(DATA_DIR, "build_costs.json")
TEMPLATES_FILE = os.path.join(DATA_DIR, "lana_templates.json")

try:
    from src.sdf_parser import get_area_comp_benchmarks
except ImportError:
    from sdf_parser import get_area_comp_benchmarks


def sanitize_sms_no_hyphens(text: str) -> str:
    """
    Strict zero hyphens rule for SMS copy.
    Replaces any hyphen between words with a space and removes dashes.
    """
    if not text:
        return ""
    text = re.sub(r'(\w)-(\w)', r'\1 \2', text)
    text = re.sub(r'\s*[-–—]\s*', ' ', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def load_build_costs() -> List[Dict[str, Any]]:
    """Loads per-market structure build costs from data/build_costs.json."""
    if os.path.exists(BUILD_COSTS_FILE):
        try:
            with open(BUILD_COSTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_build_cost_psf(county: str = "ORANGE") -> Tuple[float, str]:
    """
    Looks up $/sqft structure cost for a county/metro.
    Returns (build_cost_psf, source_label).
    """
    costs = load_build_costs()
    target_county = county.upper().strip()
    
    for row in costs:
        if row.get("county", "").upper() == target_county:
            return float(row.get("build_cost_psf", 165)), row.get("source", "Market baseline")
            
    # Check fallback rows
    for row in costs:
        if "SOUTH_ATLANTIC" in row.get("county", "").upper():
            return float(row.get("build_cost_psf", 147)), row.get("source", "South Atlantic baseline")
            
    return 162.0, "National fallback"


def load_lana_templates() -> Dict[str, Any]:
    """Loads Lana desk copy templates from data/lana_templates.json."""
    if os.path.exists(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def load_lots() -> List[Dict[str, Any]]:
    """Loads all infill land listings on Lana's desk."""
    if os.path.exists(LOTS_DATA_FILE):
        try:
            with open(LOTS_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_lots(lots: List[Dict[str, Any]]):
    """Saves all infill land listings to data/on_market_lots.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LOTS_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(lots, f, indent=2)


def passes_infill_filters(lot: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Evaluates whether a listing qualifies for Lana's Infill Land Buy Box:
    - Vacant residential land only
    - Lot size: 4,000 sqft to 0.5 acre (~21,780 sqft)
    - Minimum list price: $80,000
    - Days on Market: 60+ DOM floor
    - Active listing status
    - Excludes floodway/conservation/unbuildable remarks
    """
    reasons = []
    
    # 1. Price Floor ($80,000)
    list_price = float(lot.get("list_price") or lot.get("price") or 0.0)
    if list_price < 80000:
        reasons.append(f"List price ${list_price:,.0f} below $80,000 floor")

    # 2. Days On Market Floor (60+ DOM)
    dom = int(lot.get("days_on_market") or lot.get("dom") or 0)
    if dom < 60:
        reasons.append(f"DOM {dom} is under 60-day stale listing threshold")

    # 3. Lot Size (4,000 sqft - 0.5 acre)
    acres = float(lot.get("lot_acres") or 0.0)
    sqft = float(lot.get("lot_sqft") or 0.0)
    if acres > 0 and sqft == 0:
        sqft = acres * 43560.0
    elif sqft > 0 and acres == 0:
        acres = sqft / 43560.0

    if sqft > 0:
        if sqft < 3500:
            reasons.append(f"Lot size {sqft:,.0f} sqft is below 4,000 sqft infill minimum")
        elif sqft > 24000:  # > ~0.55 acre is acreage, not infill
            reasons.append(f"Lot size {acres:.2f} acres ({sqft:,.0f} sqft) exceeds 0.5 acre infill ceiling")

    # 4. Zoning Verification (Residential / Duplex only)
    zoning = str(lot.get("zoning") or "").lower()
    if zoning:
        if any(bad in zoning for bad in ["commercial", "industrial", "c-", "i-", "business"]) and not any(ok in zoning for ok in ["residential", "res", "r-", "duplex", "mixed"]):
            reasons.append(f"Zoning '{zoning}' is non-residential")

    # 5. Remarks & Unbuildable Exclusions
    remarks = str(lot.get("remarks") or lot.get("description") or "").lower()
    exclusion_keywords = [
        "floodway", "conservation easement", "unbuildable", "non buildable",
        "cannot build", "wetlands throughout", "wetlands entire", "no road access",
        "landlocked", "commercial zoned only"
    ]
    for kw in exclusion_keywords:
        if kw in remarks:
            reasons.append(f"Listing remarks disclose exclusion: '{kw}'")
            break

    qualifies = (len(reasons) == 0)
    return qualifies, reasons


def calculate_residual_land_value(
    list_price: Optional[float] = None,
    county: str = "ORANGE",
    neighborhood_code: Optional[str] = None,
    market_area: Optional[str] = None,
    planned_sqft: float = 2000.0,
    finished_newbuild_value: Optional[float] = None,
    builder_profit_pct: float = 0.18,
    fees_pct: float = 0.04,
    lot: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Computes Residual Land Value & LOI Send Feasibility for Lana Desk:
    
    Formula:
      max_payable = finished_newbuild_value
                    - (build_cost_psf * planned_sqft)
                    - builder_profit
                    - fees
    
    Send Rule:
      offer = 60% of list_price
      Send LOI only if offer <= max_payable
    """
    if lot and isinstance(lot, dict):
        if list_price is None:
            list_price = float(lot.get("list_price") or lot.get("price") or 0.0)
        county = lot.get("county") or county
        neighborhood_code = lot.get("neighborhood_code") or neighborhood_code
        market_area = lot.get("market_area") or market_area

    if list_price is None or list_price <= 0:
        return {"error": "List price must be greater than zero"}

    # 1. Structure build cost
    build_cost_psf, build_cost_source = get_build_cost_psf(county)
    total_build_cost = planned_sqft * build_cost_psf

    # 2. Finished new-build resale comp
    if not finished_newbuild_value or finished_newbuild_value <= 0:
        comp_bm = get_area_comp_benchmarks(county, neighborhood_code, market_area)
        finished_newbuild_value = float(comp_bm.get("median_finished_value", 440000.0))
        comp_source = comp_bm.get("source_level", "COUNTY_BASELINE")
    else:
        comp_source = "USER_SPECIFIED"

    # 3. Builder margin & transaction fees
    builder_profit = finished_newbuild_value * builder_profit_pct
    fees = max(7500.0, finished_newbuild_value * fees_pct)

    # 4. Maximum allowable land purchase price
    max_payable = max(0.0, finished_newbuild_value - total_build_cost - builder_profit - fees)

    # 5. Standard Take-It-Or-Leave-It Offer (60% of asking)
    offer_price = round(list_price * 0.60, -2)
    discount_pct = round((1.0 - (offer_price / list_price)) * 100.0, 1) if list_price > 0 else 40.0

    # 6. Send Rule Evaluation: offer <= max_payable
    passes_send_rule = (offer_price <= max_payable)
    can_send_loi = passes_send_rule
    variance = max_payable - offer_price
    spread_deficit = round(max(0.0, offer_price - max_payable), 2)

    math_explanation = (
        f"Finished New-Build (${finished_newbuild_value:,.0f}) "
        f"- Build Structure Cost (${total_build_cost:,.0f} @ ${build_cost_psf:.0f}/sqft for {planned_sqft:,.0f} sqft) "
        f"- {builder_profit_pct*100:.0f}% Builder Margin (${builder_profit:,.0f}) "
        f"- Holding/Closing Fees (${fees:,.0f}) = Max Allowable Land Value: ${max_payable:,.0f}. "
        f"Target 60% Offer: ${offer_price:,.0f} ({'PASSES' if can_send_loi else 'EXCEEDS CEILING'})."
    )

    return {
        "list_price": round(list_price, 2),
        "target_offer": round(offer_price, 2),
        "offer_price": round(offer_price, 2),
        "discount_pct": discount_pct,
        "finished_newbuild_value": round(finished_newbuild_value, 2),
        "comp_source": comp_source,
        "planned_sqft": round(planned_sqft, 2),
        "build_cost_psf": round(build_cost_psf, 2),
        "build_cost_source": build_cost_source,
        "total_build_cost": round(total_build_cost, 2),
        "builder_profit": round(builder_profit, 2),
        "builder_margin_dollars": round(builder_profit, 2),
        "builder_profit_pct": round(builder_profit_pct * 100.0, 1),
        "fees": round(fees, 2),
        "fees_dollars": round(fees, 2),
        "max_payable": round(max_payable, 2),
        "variance": round(variance, 2),
        "spread_deficit": spread_deficit,
        "can_send_loi": can_send_loi,
        "passes_send_rule": passes_send_rule,
        "math_explanation": math_explanation
    }


class LanaEngine:
    """
    On-Market Infill Land Conversation & Underwriting Engine
    Specialist: Lana (Infill Land Acquisitions Coordinator)
    """

    def __init__(self):
        self.templates = load_lana_templates()

    def get_initial_lot_state(self, lot_data: Dict[str, Any]) -> Dict[str, Any]:
        """Initializes state and runs residual underwriting on a new lot listing."""
        list_price = float(lot_data.get("list_price") or lot_data.get("price") or 100000.0)
        county = (lot_data.get("county") or "ORANGE").upper().strip()
        address = lot_data.get("address", "")
        city = lot_data.get("city", "Orlando")
        nbrhd = lot_data.get("neighborhood_code")
        mkt_ar = lot_data.get("market_area")

        underwriting = calculate_residual_land_value(
            list_price=list_price,
            county=county,
            neighborhood_code=nbrhd,
            market_area=mkt_ar,
            planned_sqft=float(lot_data.get("planned_sqft") or 2000.0)
        )

        qualifies, filter_reasons = passes_infill_filters(lot_data)

        lot_id = lot_data.get("id") or f"lot_{int(time.time())}_{address.replace(' ', '_')[:20]}"

        return {
            "id": lot_id,
            "address": address,
            "city": city,
            "county": county,
            "zip": lot_data.get("zip", ""),
            "parcel_id": lot_data.get("parcel_id", ""),
            "list_price": list_price,
            "days_on_market": int(lot_data.get("days_on_market") or lot_data.get("dom") or 65),
            "lot_acres": float(lot_data.get("lot_acres") or 0.20),
            "lot_sqft": float(lot_data.get("lot_sqft") or 8712.0),
            "zoning": lot_data.get("zoning", "Residential"),
            "agent_name": lot_data.get("agent_name", "Listing Agent"),
            "agent_phone": lot_data.get("agent_phone", ""),
            "agent_email": lot_data.get("agent_email", ""),
            "brokerage": lot_data.get("brokerage", "Local Realty"),
            "remarks": lot_data.get("remarks", ""),
            "neighborhood_code": nbrhd,
            "market_area": mkt_ar,
            "qualifies_infill": qualifies,
            "filter_notes": filter_reasons,
            "underwriting": underwriting,
            "current_node": "OPENER",
            "status": "QUALIFIED" if qualifies else "FLAGGED_REVIEW",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": [],
            "last_outbound_date": None,
            "loi_sent": False
        }

    def generate_doorbell_sms(self, lot: Dict[str, Any]) -> str:
        """Alias for generate_opener_sms."""
        return self.generate_opener_sms(lot)

    def generate_opener_sms(self, lot: Dict[str, Any]) -> str:
        """
        Generates Lana's Builder-Framing Doorbell Opener.
        Carries mandatory 'Reply STOP to opt out' on first touch.
        """
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        area = lot.get("city") or lot.get("county") or "Central Florida"

        template = (
            "Hi {agent_name}, Lana here. My client builds new construction in {area} and asked me to reach out regarding {address}. "
            "Is the lot buildable as is, and are municipal water and sewer at the lot line? Reply STOP to opt out"
        )
        rendered = template.format(agent_name=agent_name, area=area, address=addr)
        return sanitize_sms_no_hyphens(rendered)

    def generate_loi_sms(self, lot: Dict[str, Any], close_days: int = 14) -> str:
        """
        Generates short SMS Doorbell LOI text (~140 chars).
        Earns reply; full written LOI goes to email.
        """
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        area = lot.get("city") or lot.get("county") or "the area"
        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))

        template = "Hi {agent_name}, Lana here. My client builds in {area}. We would offer ${offer:,.0f} cash for {address}, close in {close_days} days. Can I send a full LOI to your email?"
        rendered = template.format(agent_name=agent_name, area=area, address=addr, offer=offer, close_days=close_days)
        return sanitize_sms_no_hyphens(rendered)

    def generate_friday_followup_sms(self, lot: Dict[str, Any]) -> str:
        """Friday Sequence: re-texts contacts from prior week who did not respond or rejected."""
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))

        template = "Hi {agent_name}, Lana here checking in before the weekend. Is {address} still available, or would your seller reconsider our ${offer:,.0f} cash offer with 14 day close?"
        return sanitize_sms_no_hyphens(template.format(agent_name=agent_name, address=addr, offer=offer))

    def generate_friday_sequence(self, lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generates Friday followup sequence drafts for a list of lots."""
        results = []
        for lot in lots:
            sms = self.generate_friday_followup_sms(lot)
            results.append({
                "lot_id": lot.get("id"),
                "lot": lot,
                "agent_name": lot.get("agent_name"),
                "address": lot.get("address"),
                "friday_sms": sms,
                "message": sms
            })
        return results

    def consolidate_agent_listings(self, agent_name: str, lots: List[Dict[str, Any]], close_days: int = 14) -> Dict[str, Any]:
        """
        Consolidation Rule: one agent with multiple qualifying lots gets ONE combined package text.
        """
        first_name = agent_name.split()[0].title() if agent_name else "there"
        total_offer = 0.0
        addresses = []
        for l in lots:
            uw = l.get("underwriting") or {}
            off = float(uw.get("offer_price") or uw.get("target_offer") or round(l.get("list_price", 100000) * 0.60, -2))
            total_offer += off
            addr = l.get("address", "the lot").split(",")[0].strip()
            addresses.append(addr)
        
        lot_count = len(lots)
        addr_str = " and ".join(addresses[:2]) if len(addresses) <= 2 else f"{addresses[0]} and {len(addresses)-1} other lots"
        sms_text = f"Hi {first_name}, Lana here. Saw both of your listings on {addr_str}. My client can package them together for ${total_offer:,.0f} cash with a {close_days} day close. Can I send a written offer over to your email?"
        sms_clean = sanitize_sms_no_hyphens(sms_text)
        return {
            "agent_name": agent_name,
            "lot_count": lot_count,
            "total_offer": total_offer,
            "sms_text": sms_clean,
            "consolidated_message": sms_clean
        }

    def generate_consolidated_agent_sms(self, agent_name: str, lots: List[Dict[str, Any]], close_days: int = 14) -> str:
        """Helper returning just the consolidated SMS string."""
        res = self.consolidate_agent_listings(agent_name, lots, close_days)
        return res["sms_text"]

    def evaluate_inbound(self, arg1: Any, arg2: Any = None) -> Dict[str, Any]:
        """
        Evaluates an inbound agent text message and generates the appropriate Lana reply.
        Accepts both (lot, inbound_text) and (inbound_text, lot).
        Handles qualifiers, LOI dispatch, and golden objection replies.
        """
        if isinstance(arg1, dict):
            lot = arg1
            inbound_text = str(arg2 or "")
        else:
            inbound_text = str(arg1 or "")
            lot = arg2 if isinstance(arg2, dict) else {}

        clean = inbound_text.lower().strip()
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        area = lot.get("city") or lot.get("county") or "Central Florida"
        email = lot.get("agent_email") or "your email"
        
        uw = lot.get("underwriting") or calculate_residual_land_value(lot.get("list_price", 100000), lot.get("county", "ORANGE"))
        target_offer = float(uw.get("offer_price") or uw.get("target_offer") or 60000.0)
        finished_val = float(uw.get("finished_newbuild_value", 450000.0))
        build_cost_psf = float(uw.get("build_cost_psf", 165.0))
        planned_sqft = float(uw.get("planned_sqft", 2000.0))
        total_build = float(uw.get("total_build_cost", planned_sqft * build_cost_psf))
        builder_margin_pct = float(uw.get("builder_profit_pct", 18.0))

        # 1. Price is Firm Objection -> 60-Day Backup
        if re.search(r'\b(firm|not negotiable|won\'?t take less|no lowballs|asking price only|full price|no discounts)\b', clean):
            reply = (
                f"I respect where your seller wants to be. If they do not see retail action in 30 to 60 days, our offer stands "
                f"as a guaranteed cash backup at ${target_offer:,.0f} with zero financing contingencies."
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "LANA_FIRM_PRICE",
                "status": "OBJECTION_FIRM_PRICE",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "HOLD_FIRM"
            }

        # 2. "Why so low" / Build-Cost Math Drop
        if re.search(r'\b(why so low|how did you get|breakdown|too low|insulting|explain the price|ridiculous|makes no sense)\b', clean):
            reply = (
                f"Running your numbers through our infill builder calculator: finished new construction in this pocket sells around "
                f"${finished_val:,.0f}. At current structure costs of ${build_cost_psf:.0f} per sqft for a {planned_sqft:,.0f} sqft build "
                f"(${total_build:,.0f}), plus our client's standard {builder_margin_pct:.0f} percent builder margin and holding fees, that puts our "
                f"maximum land basis right at ${target_offer:,.0f} cash. That is why we are at that number. Would it make sense to send over our full LOI breakdown?"
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "LANA_MATH_DROP",
                "status": "MATH_DROP_DELIVERED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "MATH_DROP"
            }

        # 3. "Is your client real" / Wholesaler Vetting -> Builder Credentials
        if re.search(r'\b(who is your client|are they real|proof of funds|pof|who is the builder|real buyer|scam|wholesaler|actual builder)\b', clean):
            reply = (
                f"Yes, absolutely. My client is a local Florida residential builder actively pouring foundations and completing spec "
                f"single family homes in Central Florida. We have verified cash proof of funds and close on vacant lots with zero lender "
                f"red tape. Happy to send our builder package along with the written LOI to {email}."
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "LANA_BUILDER_CREDS",
                "status": "BUILDER_CREDS_SHARED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "BUILDER_CREDIBILITY"
            }

        # 4. Identity -> Local Builder Partner
        if re.search(r'\b(who is this|what company|who are you|who am i speaking with|company are you with|what\'?s your name)\b', clean):
            reply = (
                f"Hi {agent_name}, this is Lana with Peak Investments. We partner with local residential home builders in Central Florida "
                f"acquiring buildable infill lots for spec new construction."
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "LANA_IDENTITY",
                "status": "IDENTITY_CONFIRMED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "IDENTITY"
            }

        # 5. Other Buyer Interest
        if re.search(r'\b(other offers?|multiple offers?|lot of interest|have an offer|about to go under contract)\b', clean):
            reply = (
                f"Understood, that makes complete sense. A lot of retail buyers struggle to secure construction loans right now. "
                f"If your current buyer stalls on financing or drops out during feasibility, we can step in as a guaranteed cash close at ${target_offer:,.0f}."
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "OBJECTION_OTHER_INTEREST",
                "status": "BACKUP_POSITIONED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "BACKUP_CASH"
            }

        # 6. "Send me the LOI" / Agent agrees to review offer
        if re.search(r'\b(send (?:me )?(?:the )?(?:loi|offer|email)|email it|what\'?s your offer|send it over|let me see it)\b', clean):
            reply = (
                f"Awesome, sending the full written LOI over to {email} right now with proof of funds attached. "
                f"Our offer stands for 7 business days. Please let me know once you and the seller have a chance to review!"
            )
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "OBJECTION_SEND_LOI",
                "status": "LOI_REQUESTED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "DISPATCH_WRITTEN_LOI"
            }

        # 7. Socratic Qualification Progression (One question per SMS)
        curr_node = lot.get("current_node", "OPENER")
        
        # After opener answered -> ask zoning / setbacks
        if curr_node == "OPENER":
            reply = f"Thanks {agent_name}. What is the zoning classification on the parcel, and are single family homes or duplexes permitted by right?"
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "QUALIFY_BUILDABLE",
                "status": "QUALIFYING_ZONING",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "QUALIFY"
            }

        if curr_node == "QUALIFY_BUILDABLE":
            reply = f"Got it. Are city water and sewer stubbed directly at the lot line, or would a builder need a septic system and well?"
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "QUALIFY_UTILITIES",
                "status": "QUALIFYING_UTILITIES",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "QUALIFY"
            }

        if curr_node == "QUALIFY_UTILITIES":
            reply = f"Helpful to know. Are you aware of any setbacks, conservation easements, or HOA architectural guidelines on {addr}?"
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "QUALIFY_SETBACKS_HOA",
                "status": "QUALIFYING_RESTRICTIONS",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "QUALIFY"
            }

        if curr_node == "QUALIFY_SETBACKS_HOA":
            reply = f"Understood. Do you know if county and city impact fees have already been paid, or if any credits carry over from a prior structure?"
            clean_reply = sanitize_sms_no_hyphens(reply)
            return {
                "node": "QUALIFY_IMPACT_FEES",
                "status": "QUALIFYING_FEES",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "QUALIFY"
            }

        # Ready to send LOI
        loi_sms = self.generate_loi_sms(lot)
        return {
            "node": "OFFER_LOI",
            "status": "LOI_OFFER_PITCHED",
            "reply_text": loi_sms,
            "suggested_reply": loi_sms,
            "action": "OFFER_DISPATCHED"
        }


lana_engine = LanaEngine()
