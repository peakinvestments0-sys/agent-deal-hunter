"""
Lana Engine - On-Market Infill Land Specialist & Residual Underwriting Agent
Third Desk of Agent Hunter (Lauren: On-Market Fixers, Brooke: Pocket Listings, Lana: Infill Land)

Core Capabilities:
1. Infill Land Targeting Filters (4,000 sqft - 0.5 acre, active, residential, DOM >= 60; flexible list price)
2. Residual Land Value Underwriting Calculator:
   max_payable = finished_newbuild_value - (build_cost_psf * planned_sqft) - builder_profit - fees
   Primary Offer Rule: offer = max_payable - $10,000 negotiation buffer
   Negotiation: step up in $2k-$3k increments if agent counters
   Spread Gate: offer must be at least $40,000 below list price (or proportional for sub-$80k lots)
   Fallback Rule: 60% of list price when comp data is thin
3. Direct Cash Offer Opener (no 20-questions survey, default 21-day close)
4. Dual LOI Delivery (1-click via SMS text or formal Email)
5. Clean Follow-Up & Negotiation:
   - Friday Follow-Up: "Would your client reconsider my offer of $X?"
   - Multi-Lot Agent Consolidation: packaged bundle offer
   - Land Math Drop: full structural & margin breakdown
   - Builder Credentials & verified cash POF
6. Zero Em/En Dashes SMS rule (preserves standard plain hyphens like '21-day')
7. Human-Review Safeguard: drafts every LOI, never auto-sends without review
"""

import os
import re
import json
import time
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


def strip_hyphens_for_sms(text: str) -> str:
    """
    Strips em-dashes (—) and en-dashes (–), but preserves standard plain hyphens (-).
    Prevents carrier UCS-2 SMS encoding fragmentation while allowing hyphenated words like '21-day'.
    """
    if not text:
        return ""
    # Strip unicode em/en dashes
    text = re.sub(r'\s*[–—]\s*', ' ', text)
    # Normalize double spaces
    text = re.sub(r' +', ' ', text)
    return text.strip()


# Backwards compatibility alias
sanitize_sms_no_hyphens = strip_hyphens_for_sms


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
            
    # Check regional fallback
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
    - Days on Market: 60+ DOM floor
    - Active listing status
    - Excludes floodway/conservation/unbuildable remarks
    Note: The rigid flat $80k floor has been removed so secondary infill markets
    like Brevard (Palm Bay, $45k-$65k) and Jacksonville ($40k-$70k) can qualify.
    """
    reasons = []
    
    # 1. Nominal sanity price check (exclude obvious $1 dummy/auction listings)
    list_price = float(lot.get("list_price") or lot.get("price") or 0.0)
    if list_price < 10000:
        reasons.append(f"List price ${list_price:,.0f} below nominal $10,000 sanity floor")

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


def step_up_counter_offer(current_offer: float, max_payable: float, step: float = 2500.0) -> float:
    """
    Negotiates up in $2k-$3k steps if the agent counters or engages,
    capped at the residual max_payable limit.
    """
    new_offer = min(max_payable, current_offer + step)
    return round(new_offer, -2)


def calculate_residual_land_value(
    list_price: Optional[float] = None,
    county: str = "ORANGE",
    neighborhood_code: Optional[str] = None,
    market_area: Optional[str] = None,
    planned_sqft: float = 2000.0,
    finished_newbuild_value: Optional[float] = None,
    builder_profit_pct: float = 0.18,
    fees_pct: float = 0.04,
    lot: Optional[Dict[str, Any]] = None,
    force_fallback: bool = False
) -> Dict[str, Any]:
    """
    Computes Residual Land Value & LOI Send Feasibility for Lana Desk:
    
    Formula:
      max_payable = finished_newbuild_value
                    - (build_cost_psf * planned_sqft)
                    - builder_profit
                    - fees
    
    Primary Offer Rule:
      offer = max_payable - $10,000 negotiation buffer
      The desk may negotiate up in $2k-$3k steps if the agent engages.
    
    Gate:
      Offer must be at least $40,000 below list price (or >= 25% discount on lower-priced lots).
    
    Fallback:
      When comp data is thin, offer = 60% of list price.
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
    is_thin_comps = False
    if not finished_newbuild_value or finished_newbuild_value <= 0:
        comp_bm = get_area_comp_benchmarks(county, neighborhood_code, market_area)
        finished_newbuild_value = float(comp_bm.get("median_finished_value", 440000.0))
        comp_source = comp_bm.get("source_level", "COUNTY_BASELINE")
        if comp_bm.get("comps_count", 0) < 3 or comp_source in ["COUNTY_BASELINE", "DEFAULT"]:
            is_thin_comps = True
    else:
        comp_source = "USER_SPECIFIED"

    # For imported lots where micro-comps are thin, dynamically scale finished new-build
    # Infill land generally represents 22% - 28% of finished new-build value.
    if is_thin_comps and list_price > 0:
        estimated_newbuild = max(finished_newbuild_value, round(list_price * 3.5, -3))
        finished_newbuild_value = estimated_newbuild

    # 3. Builder margin & transaction fees
    builder_profit = finished_newbuild_value * builder_profit_pct
    fees = max(7500.0, finished_newbuild_value * fees_pct)

    # 4. Maximum allowable land purchase price
    max_payable = max(0.0, finished_newbuild_value - total_build_cost - builder_profit - fees)

    # 5. Offer Calculation: Primary vs. Thin-Comp Fallback
    if force_fallback or is_thin_comps:
        offer_price = round(list_price * 0.60, -2)
        pricing_rule = "FALLBACK_60_PCT"
        if max_payable < offer_price:
            max_payable = round(list_price * 0.70, -2)
    else:
        # Primary: (residual max payable) - $10,000 negotiation buffer
        calculated_offer = max(10000.0, max_payable - 10000.0)
        offer_price = round(calculated_offer, -2)
        pricing_rule = "PRIMARY_RESIDUAL_BUFFER"

    discount_pct = round((1.0 - (offer_price / list_price)) * 100.0, 1) if list_price > 0 else 40.0

    # 6. Spread Gate Check
    spread_dollars = list_price - offer_price
    # If list price is high (>= $100k), enforce $40k gate. If lower ($40k-$80k), scale floor to 25% discount.
    required_min_spread = min(40000.0, list_price * 0.35) if list_price < 100000 else 40000.0
    passes_spread_gate = (spread_dollars >= required_min_spread)

    # 7. Send Rule Evaluation
    passes_send_rule = (offer_price <= max_payable and passes_spread_gate)
    can_send_loi = passes_send_rule
    variance = max_payable - offer_price
    spread_deficit = round(max(0.0, offer_price - max_payable), 2)

    math_explanation = (
        f"Finished New-Build (${finished_newbuild_value:,.0f}) "
        f"- Build Structure Cost (${total_build_cost:,.0f} @ ${build_cost_psf:.0f}/sqft for {planned_sqft:,.0f} sqft) "
        f"- {builder_profit_pct*100:.0f}% Builder Margin (${builder_profit:,.0f}) "
        f"- Holding/Closing Fees (${fees:,.0f}) = Max Allowable Land Value: ${max_payable:,.0f}. "
        f"Offer: ${offer_price:,.0f} ({'PASSES' if can_send_loi else 'EXCEEDS CEILING OR SPREAD GATE'})."
    )

    return {
        "list_price": round(list_price, 2),
        "target_offer": round(offer_price, 2),
        "offer_price": round(offer_price, 2),
        "discount_pct": discount_pct,
        "pricing_rule": pricing_rule,
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
        "spread_dollars": round(spread_dollars, 2),
        "passes_spread_gate": passes_spread_gate,
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
            "redfin_url": (lot_data.get("redfin_url") or lot_data.get("url") or "").strip(),
            "photo_url": (lot_data.get("photo_url") or lot_data.get("image_url") or "").strip(),
            "neighborhood_code": nbrhd,
            "market_area": mkt_ar,
            "close_days": int(lot_data.get("close_days") or 21),
            "qualifies_infill": qualifies,
            "filter_notes": filter_reasons,
            "underwriting": underwriting,
            "current_node": "DRAFT_PENDING_REVIEW",
            "status": "QUALIFIED_DRAFT" if qualifies else "FLAGGED_REVIEW",
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "messages": [],
            "last_outbound_date": None,
            "loi_sent": False
        }

    def generate_opener_sms(self, lot: Dict[str, Any], close_days: int = 21) -> str:
        """
        Direct Lana Cash Offer Opener (Canonical):
        'Hi [Name], my name is Lana. I'm interested in your listing on [Street]. 
         I reviewed the numbers — I'll be at $[Offer] cash with a [N]-day close. 
         If this is something your client is interested in, let me know and I can get a contract sent over.'
        """
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        
        # Extract street portion (e.g., 'Michigan Ave' from '4122 Michigan Ave')
        street_match = re.search(r'^\d+\s+(.*)$', addr.split(',')[0].strip())
        street = street_match.group(1) if street_match else addr.split(',')[0].strip()

        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))
        effective_close = int(lot.get("close_days") or close_days)

        template = (
            "Hi {agent_name}, my name is Lana. I'm interested in your listing on {street}. "
            "I reviewed the numbers — I'll be at ${offer:,.0f} cash with a {close_days}-day close. "
            "If this is something your client is interested in, let me know and I can get a contract sent over."
        )
        rendered = template.format(agent_name=agent_name, street=street, offer=offer, close_days=effective_close)
        return strip_hyphens_for_sms(rendered)

    def generate_doorbell_sms(self, lot: Dict[str, Any], close_days: int = 21) -> str:
        """Alias for generate_opener_sms."""
        return self.generate_opener_sms(lot, close_days=close_days)

    def generate_friday_followup_sms(self, lot: Dict[str, Any]) -> str:
        """
        Friday Follow-Up:
        'Hi [Name], is [Street] still available? Would your client reconsider my offer of $[Offer]?'
        """
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the lot")
        street_match = re.search(r'^\d+\s+(.*)$', addr.split(',')[0].strip())
        street = street_match.group(1) if street_match else addr.split(',')[0].strip()

        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))

        template = "Hi {agent_name}, is {street} still available? Would your client reconsider my offer of ${offer:,.0f}?"
        rendered = template.format(agent_name=agent_name, street=street, offer=offer)
        return strip_hyphens_for_sms(rendered)

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

    def generate_loi_sms(self, lot: Dict[str, Any], close_days: int = 21) -> str:
        """
        Generates condensed LOI terms text for 1-click delivery via SMS/text.
        """
        agent_name = (lot.get("agent_name") or "there").split()[0].title()
        addr = lot.get("address", "the parcel")
        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))
        effective_close = int(lot.get("close_days") or close_days)

        template = (
            "LOI Terms for {address}: Purchase Price: ${offer:,.0f} Cash. Earnest Money: $2,500. "
            "Feasibility Period: 14 days. Closing: {close_days} days. Full listing commission protected. "
            "Proof of funds verified. Let me know if you would like me to text or email the contract. Lana"
        )
        rendered = template.format(agent_name=agent_name, address=addr, offer=offer, close_days=effective_close)
        return strip_hyphens_for_sms(rendered)

    def generate_loi_email_html(self, lot: Dict[str, Any], close_days: int = 21) -> str:
        """Generates formal written LOI terms for Email delivery."""
        agent_name = (lot.get("agent_name") or "Listing Agent").title()
        addr = lot.get("address", "Subject Vacant Parcel")
        uw = lot.get("underwriting") or {}
        offer = float(uw.get("offer_price") or uw.get("target_offer") or round(lot.get("list_price", 100000) * 0.60, -2))
        list_price = float(lot.get("list_price", offer * 1.5))
        effective_close = int(lot.get("close_days") or close_days)

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; color: #1e293b; line-height: 1.6;">
            <div style="background: #0f172a; padding: 20px; border-radius: 8px 8px 0 0; color: white;">
                <h2 style="margin: 0; color: #38bdf8; font-size: 20px;">LETTER OF INTENT TO PURCHASE VACANT LAND</h2>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #94a3b8;">Commercial & Residential Builder Acquisitions</p>
            </div>
            <div style="border: 1px solid #e2e8f0; border-top: none; padding: 24px; border-radius: 0 0 8px 8px; background: #ffffff;">
                <p>Dear {agent_name},</p>
                <p>Please present this Letter of Intent (LOI) to the seller of <strong>{addr}</strong>. Our builder client is ready to execute a contract immediately upon mutual agreement on the core terms below:</p>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px; font-weight: bold; width: 40%; color: #475569;">Property Address:</td>
                        <td style="padding: 10px; color: #0f172a;">{addr}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Current List Price:</td>
                        <td style="padding: 10px; color: #0f172a;">${list_price:,.0f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Cash Purchase Price:</td>
                        <td style="padding: 10px; font-weight: bold; color: #16a34a; font-size: 16px;">${offer:,.0f}</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Financing Terms:</td>
                        <td style="padding: 10px; color: #0f172a;">All Cash (Zero Financing Contingency)</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Earnest Money Deposit:</td>
                        <td style="padding: 10px; color: #0f172a;">$2,500 deposited within 3 days of execution</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Feasibility / Study Period:</td>
                        <td style="padding: 10px; color: #0f172a;">14 days for builder site survey and utility checks</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Closing Date:</td>
                        <td style="padding: 10px; color: #0f172a;">{effective_close} days from effective date</td>
                    </tr>
                    <tr style="border-bottom: 1px solid #e2e8f0; background: #f8fafc;">
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Broker Commission:</td>
                        <td style="padding: 10px; color: #0f172a;">Full commission as published in MLS protected and paid at closing</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold; color: #475569;">Offer Expiration:</td>
                        <td style="padding: 10px; color: #dc2626;">5 business days from transmission</td>
                    </tr>
                </table>

                <p style="font-size: 13px; color: #64748b; margin-top: 24px;">Proof of funds is available upon request. To proceed, please reply to this email or text confirmation to have the contract delivered.</p>
                
                <div style="margin-top: 24px; padding-top: 16px; border-top: 1px solid #e2e8f0;">
                    <p style="margin: 0; font-weight: bold; color: #0f172a;">Lana</p>
                    <p style="margin: 2px 0 0 0; font-size: 13px; color: #64748b;">Infill Land Acquisitions Coordinator | Peak Investments</p>
                </div>
            </div>
        </div>
        """
        return html.strip()

    def consolidate_agent_listings(self, agent_name: str, lots: List[Dict[str, Any]], close_days: int = 21) -> Dict[str, Any]:
        """
        Consolidation Rule: one agent with multiple qualifying lots gets ONE combined package text.
        """
        first_name = agent_name.split()[0].title() if agent_name else "there"
        total_offer = 0.0
        street_list = []
        for l in lots:
            uw = l.get("underwriting") or {}
            off = float(uw.get("offer_price") or uw.get("target_offer") or round(l.get("list_price", 100000) * 0.60, -2))
            total_offer += off
            addr = l.get("address", "the lot")
            street_match = re.search(r'^\d+\s+(.*)$', addr.split(',')[0].strip())
            street = street_match.group(1) if street_match else addr.split(',')[0].strip()
            street_list.append(street)
        
        lot_count = len(lots)
        streets_str = " and ".join(street_list[:2]) if len(street_list) <= 2 else f"{street_list[0]} and {len(street_list)-1} other parcels"
        
        sms_text = (
            f"Hi {first_name}, my name is Lana. I'm interested in your listings on {streets_str}. "
            f"I reviewed the numbers — I'll be at ${total_offer:,.0f} cash with a {close_days}-day close for the package. "
            f"If this is something your clients are open to, let me know and I can get contracts sent over."
        )
        sms_clean = strip_hyphens_for_sms(sms_text)
        return {
            "agent_name": agent_name,
            "lot_count": lot_count,
            "total_offer": total_offer,
            "sms_text": sms_clean,
            "consolidated_message": sms_clean
        }

    def generate_consolidated_agent_sms(self, agent_name: str, lots: List[Dict[str, Any]], close_days: int = 21) -> str:
        """Helper returning just the consolidated SMS string."""
        res = self.consolidate_agent_listings(agent_name, lots, close_days)
        return res["sms_text"]

    def evaluate_inbound(self, arg1: Any, arg2: Any = None) -> Dict[str, Any]:
        """
        Evaluates an inbound agent text message and generates the appropriate Lana reply.
        Accepts both (lot, inbound_text) and (inbound_text, lot).
        Streamlined flow: handles LOI delivery choice, counter-offer steps, math drop, builder creds.
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
        street_match = re.search(r'^\d+\s+(.*)$', addr.split(',')[0].strip())
        street = street_match.group(1) if street_match else addr.split(',')[0].strip()
        
        uw = lot.get("underwriting") or calculate_residual_land_value(lot.get("list_price", 100000), lot.get("county", "ORANGE"))
        target_offer = float(uw.get("offer_price") or uw.get("target_offer") or 60000.0)
        max_payable = float(uw.get("max_payable") or (target_offer + 10000.0))
        finished_val = float(uw.get("finished_newbuild_value", 450000.0))
        build_cost_psf = float(uw.get("build_cost_psf", 165.0))
        planned_sqft = float(uw.get("planned_sqft", 2000.0))
        total_build = float(uw.get("total_build_cost", planned_sqft * build_cost_psf))
        builder_margin_pct = float(uw.get("builder_profit_pct", 18.0))
        close_days = int(lot.get("close_days") or 21)

        # 1. Agent asks for LOI / contract / agrees ("send it", "email it", "text it", "let's see it", "send over the contract")
        if (
            re.search(r'\b(send\s+(?:over\s+)?(?:me\s+)?(?:the\s+|an\s+)?(?:loi|contract|offer|email)|email\s+it|text\s+it|what\'?s\s+your\s+offer|send\s+it\s+over|let\s+me\s+see\s+it|yes|send\s+contract)\b', clean)
            or re.search(r'\b(send|email|text)\b.*\b(contract|loi)\b', clean)
        ):
            reply = "Awesome, would you prefer the formal written LOI sent over via text here, or directly to your email?"
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_SEND_LOI",
                "status": "LOI_REQUESTED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "DISPATCH_WRITTEN_LOI"
            }

        # 2. Agent Counters / Negotiates ("can you do $X", "counter", "need more", "bump", "higher")
        if re.search(r'\b(counter|can you do|come up|raise|bump|better|closer|meet in the middle|seller wants more|too low can you)\b', clean):
            stepped_offer = step_up_counter_offer(target_offer, max_payable, 2500.0)
            if stepped_offer > target_offer:
                reply = (
                    f"I reviewed this with my client. We have a little room to bridge the gap and can come up to "
                    f"${stepped_offer:,.0f} cash with the same {close_days}-day close. Would that get this across the finish line for your seller?"
                )
            else:
                reply = (
                    f"My client's maximum ceiling on this parcel based on build costs is ${max_payable:,.0f} cash. "
                    f"We can step up to ${max_payable:,.0f} with a {close_days}-day close if we can wrap this up this week."
                )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_COUNTER_OFFER",
                "status": "COUNTER_OFFER_PITCHED",
                "stepped_offer": stepped_offer,
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "STEP_UP_OFFER"
            }

        # 3. Price is Firm Objection
        if re.search(r'\b(firm|not negotiable|won\'?t take less|no lowballs|asking price only|full price|no discounts)\b', clean):
            reply = (
                f"I respect where your seller wants to be. My client is an active infill builder, so our numbers are tied "
                f"directly to current build costs and back end resale comps. We are ready to move quickly with zero financing "
                f"contingencies at ${target_offer:,.0f} cash with a {close_days}-day close. This offer is valid for 5 business days."
            )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_FIRM_PRICE",
                "status": "OBJECTION_FIRM_PRICE",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "HOLD_FIRM"
            }

        # 4. "Why so low" / Build-Cost Math Drop
        if re.search(r'\b(why so low|how did you get|breakdown|too low|insulting|explain the price|ridiculous|makes no sense)\b', clean):
            reply = (
                f"Running your numbers through our infill builder calculator: finished new construction in this pocket sells around "
                f"${finished_val:,.0f}. At current structure costs of ${build_cost_psf:.0f} per sqft for a {planned_sqft:,.0f} sqft build "
                f"(${total_build:,.0f}), plus our client's standard {builder_margin_pct:.0f} percent builder margin and holding fees, that puts our "
                f"maximum land basis right at ${max_payable:,.0f} cash. We opened at ${target_offer:,.0f} with a {close_days}-day cash close. Would it make sense to send over our contract or full LOI?"
            )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_MATH_DROP",
                "status": "MATH_DROP_DELIVERED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "MATH_DROP"
            }

        # 5. Wholesaler Vetting -> Builder Credentials
        if re.search(r'\b(who is your client|are they real|proof of funds|pof|who is the builder|real buyer|scam|wholesaler|actual builder)\b', clean):
            reply = (
                f"Yes, absolutely. My client is a local residential builder actively pouring foundations and completing spec "
                f"single family homes in the area. We have verified cash proof of funds and close on vacant lots with zero lender "
                f"red tape. Happy to send our written contract or LOI to you by text or email."
            )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_BUILDER_CREDS",
                "status": "BUILDER_CREDS_SHARED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "BUILDER_CREDIBILITY"
            }

        # 6. Identity -> Local Builder Partner
        if re.search(r'\b(who is this|what company|who are you|who am i speaking with|company are you with|what\'?s your name)\b', clean):
            reply = (
                f"Hi {agent_name}, this is Lana with Peak Investments. We partner with local residential home builders "
                f"acquiring buildable infill lots for spec new construction."
            )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_IDENTITY",
                "status": "IDENTITY_CONFIRMED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "IDENTITY"
            }

        # 7. Other Buyer Interest
        if re.search(r'\b(other offers?|multiple offers?|lot of interest|have an offer|about to go under contract)\b', clean):
            reply = (
                f"Understood, that makes complete sense. If your current buyer stalls on financing or feasibility, "
                f"we are ready to step in at ${target_offer:,.0f} cash with a {close_days}-day close. This offer is valid for 5 business days."
            )
            clean_reply = strip_hyphens_for_sms(reply)
            return {
                "node": "LANA_OTHER_INTEREST",
                "status": "BACKUP_POSITIONED",
                "reply_text": clean_reply,
                "suggested_reply": clean_reply,
                "action": "BACKUP_CASH"
            }

        # Default fallback: reiterate clean offer terms
        fallback_reply = (
            f"Thanks for following up {agent_name}. We reviewed the numbers on {street} and are at ${target_offer:,.0f} cash "
            f"with a {close_days}-day close. Let me know if you would like me to get a contract or LOI sent over."
        )
        clean_fallback = strip_hyphens_for_sms(fallback_reply)
        return {
            "node": "LANA_GENERAL_REPLY",
            "status": "GENERAL_FOLLOWUP",
            "reply_text": clean_fallback,
            "suggested_reply": clean_fallback,
            "action": "GENERAL"
        }


lana_engine = LanaEngine()
