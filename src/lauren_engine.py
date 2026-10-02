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
    "full market value",
    "2026 HGTV full retail",
    "full retail value",
    "top of the neighborhood",
    "top of market",
    "top of the market",
    "max retail value",
    "fully renovated retail"
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

        return {
            "id": property_data.get("id") or f"fixer_{int(time.time())}_{property_data.get('address', 'prop').replace(' ', '_')[:20]}",
            "address": property_data.get("address", ""),
            "city": property_data.get("city", "Melbourne"),
            "county": property_data.get("county", "BREVARD"),
            "zip": property_data.get("zip", ""),
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

    def generate_opening_hook(self, fixer: Dict[str, Any]) -> str:
        """
        Creates natural, varied opening SMS applying the Don't Look Stupid rule.
        Uses natural, subtle investor tone without fake gushing flattery.
        Introduces as 'Lauren here' or 'its Lauren' (never mentions 407 Flips upfront).
        Rotates retail target phrases and condition inquiries with zero hyphens.
        """
        agent_first = fixer.get("agent_name", "there").split()[0]
        addr = fixer.get("address", "your listing")
        remarks = fixer.get("remarks", "").lower()

        # Identify mentioned items to avoid asking about them
        has_cash_only = "cash" in remarks or "hard money" in remarks
        has_as_is = "as is" in remarks or "as-is" in remarks
        has_repairs_needed = any(w in remarks for w in ["needs", "handyman", "tlc", "fixer", "roof", "updating", "work"])

        retail_target = random.choice(RETAIL_CONDITION_TARGETS)

        intro_options = [
            f"Hey {agent_first}, Lauren here.",
            f"Hi {agent_first}, its Lauren.",
            f"Hey {agent_first}, its Lauren.",
            f"Hi {agent_first}, Lauren here."
        ]
        intro = random.choice(intro_options)

        hook_options = [
            f"Saw your listing over on {addr}.",
            f"Reaching out regarding your listing on {addr}.",
            f"Checked out {addr}.",
            f"Had a quick question on {addr}.",
            f"Taking a look at {addr}."
        ]
        hook = random.choice(hook_options)

        if has_cash_only or has_as_is or has_repairs_needed:
            condition_questions = [
                f"Saw your notes about the property and condition. Outside of what is already noted in the listing, does the home need anything else major to get it to {retail_target}?",
                f"Noticed your remarks regarding the condition. Besides what you already have listed online, is there anything else big the house needs to hit {retail_target}?",
                f"Took a look at the condition notes. Beyond what is already posted, does it need any other heavy work to reach {retail_target}?",
                f"Saw the notes on needed repairs. Other than what is already disclosed, is there anything else major the home needs to get to {retail_target}?",
                f"Saw the details on condition. Besides what is already mentioned in your listing, is there any other major work needed to bring it to {retail_target}?"
            ]
        else:
            condition_questions = [
                f"Other than what you have listed, does the house need anything major to get it to {retail_target}?",
                f"Outside of what is noted online, is there anything else the property needs to bring it to {retail_target}?",
                f"Beyond what is in your listing remarks, are there any major updates or mechanicals needed to hit {retail_target}?",
                f"Looking at this for our next project. Besides what you have listed, does it need any other heavy work to reach {retail_target}?",
                f"Other than what is noted in the listing, are there any big ticket repairs needed to get it to {retail_target}?"
            ]

        question = random.choice(condition_questions)
        full_text = f"{intro} {hook} {question}"
        return sanitize_sms_no_hyphens(full_text)

    def evaluate_inbound(self, fixer: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Processes an agent reply through Lauren's Trojan Horse engine.
        Applies Asymmetric ARV Arbitrage and Nate Barger MAO math.
        """
        clean_msg = message.lower().strip()
        curr_node = fixer.get("current_node", "OPENING_HOOK")
        agent_first = fixer.get("agent_name", "there").split()[0]
        addr = fixer.get("address", "the property")
        redfin_est = fixer.get("redfin_estimate") or 250000.0
        sqft = fixer.get("sqft") or 1200.0

        # Hard Opt Out
        if any(w in clean_msg for w in ["stop", "unsubscribe", "remove", "wrong number", "don't text", "dont text", "f*** off", "fuck off", "lose my number", "do not contact", "harassment"]):
            fixer["status"] = "DEAD"
            fixer["current_node"] = "DEAD"
            return {
                "action": "OPT_OUT",
                "reply_text": "",
                "node": "DEAD",
                "reason": "Agent requested opt-out."
            }

        # 1. Identity Inquiry ("Who is this?")
        if any(w in clean_msg for w in ["who is this", "who's this", "whos this", "who are you", "what company", "who is texting"]):
            reply = (
                f"Hey {agent_first}, its Lauren! John and I are local buyers actively looking for our next project in "
                f"{fixer.get('city', 'the area')}. Reached out regarding {addr}. Are you still working with the sellers on this one?"
            )
            fixer["current_node"] = "IDENTITY_ANSWERED"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "IDENTITY_ANSWERED",
                "reason": "Lauren introduced herself and partner John, refocusing on the property."
            }

        has_pushback = any(w in clean_msg for w in ["no way", "turned down", "too low", "seller won't", "seller wont", "under 180", "anything under", "insulting", "firm on", "waste of time", "pass on", "cannot accept", "cant accept", "gap"])
        has_comp_word = bool(re.search(r'\b(comps?|arv|resale|worth|sell for|list for)\b', clean_msg))
        has_repair_detail = any(w in clean_msg for w in ["roof", "a/c", "ac", "plumbing", "electrical", "dated", "rehab", "repairs", "work", "handyman", "kitchen", "bath", "flooring", "paint", "needs"])

        # 2. Pushback & Price Resistance -> Trojan Horse Step 5: Send Standing Written LOI Rule
        if has_pushback or (curr_node == "MATH_PRESENTED" and not has_comp_word and not has_repair_detail):
            offer_val = fixer.get("underwriting", {}).get("offer_price") or 128000.0
            reply = (
                f"Totally understand we have a gap right now, {agent_first}! I just shot our formal written terms to your email as well "
                f"as a standing cash offer at ${offer_val:,.0f} just in case the seller's circumstances or timeline change down the road, "
                f"or if anything falls through with another buyer. Our offer stands for 30 days. If anything shifts, John and I are ready to close clean in 14 days!"
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

        # 3. Repair Scope (Agent details condition without comp numbers) -> Trojan Horse Step 2
        if has_repair_detail and not has_comp_word:
            fixer["repair_notes"] = message
            repair_cand = self._extract_dollar_amount(message)
            if repair_cand and repair_cand < (redfin_est * 0.50):
                fixer["agent_repair_estimate"] = repair_cand

            retail_target = random.choice(RETAIL_CONDITION_TARGETS)
            reply = (
                f"Got it, that helps a ton. When you walk through it, what dollar amount do you think a buyer needs to sink into it "
                f"to reach {retail_target} condition?"
            )
            fixer["current_node"] = "ASKED_REPAIR_COST"
            fixer["status"] = "VETTING_REPAIRS"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "ASKED_REPAIR_COST",
                "reason": "Trojan Horse Step 2: Repair scope noted, asking for repair dollar estimate."
            }

        # 4. Agent gives repair cost dollar figure without comp words -> Trojan Horse Step 3
        if curr_node == "ASKED_REPAIR_COST" and not has_comp_word:
            repair_cand = self._extract_dollar_amount(message)
            if repair_cand and repair_cand < (redfin_est * 0.50):
                fixer["agent_repair_estimate"] = repair_cand

            reply = (
                f"Makes total sense. If our crew comes in and does all that work to make it pristine, "
                f"what do you think you could realistically list and sell it for on the back end?"
            )
            fixer["current_node"] = "ASKED_AGENT_ARV"
            fixer["status"] = "VETTING_REPAIRS"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "ASKED_AGENT_ARV",
                "reason": "Trojan Horse Step 3: Repair dollar noted, asking for resale ARV."
            }

        # 5. Back-End ARV / Comps -> Trojan Horse Step 4: Execute Asymmetric ARV Arbitrage & Math Drop
        if has_comp_word or curr_node == "ASKED_AGENT_ARV":
            arv_cand = self._extract_dollar_amount(message)
            agent_arv = arv_cand or redfin_est
            fixer["agent_arv_estimate"] = agent_arv

            # ASYMMETRIC ARV ARBITRAGE RULE:
            # 1. Agent comes in LOW: Accept their comp immediately! Say nothing about higher comps.
            # 2. Agent comes in HIGH or close to right: Anchor them down showing low comps as possible.
            if agent_arv < redfin_est:
                effective_arv = agent_arv
                intro_phrase = f"{agent_first}, running your numbers through our flip calculator: based on your ${agent_arv:,.0f} resale number"
            else:
                effective_arv = min(agent_arv * 0.85, redfin_est * 0.95)
                intro_phrase = f"{agent_first}, we looked closely at those comps, but recent conservative neighborhood sales are sitting lower around ${effective_arv:,.0f}. Running that through our flip calculator"

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
                offer_phrase = "leaves zero profit margin at all"
            else:
                offer_phrase = f"puts John right around ${offer:,.0f} cash with zero inspection contingencies"

            reply = (
                f"{intro_phrase}, minus ~${agent_rehab:,.0f} in repairs, 9 percent in holding and commission fees, and our crew's standard 15 percent margin "
                f"{offer_phrase}. That is why we are coming in way under that one. "
                f"Would it make sense to send over an offer and have John do a follow up for any questions?"
            )
            fixer["current_node"] = "MATH_PRESENTED"
            fixer["status"] = "MATH_PRESENTED"
            return {
                "action": "SUGGEST",
                "reply_text": sanitize_sms_no_hyphens(reply),
                "node": "MATH_PRESENTED",
                "reason": "Trojan Horse Step 4: Socratic math drop using agent's own figures."
            }

        # 6. Default Step 1 Hook Follow-up
        reply = (
            f"Awesome, thanks for getting back to me {agent_first}. In your opinion, what shape are the major mechanicals in "
            f"(roof, AC, plumbing, electrical), and what kind of rehab do you think it needs?"
        )
        fixer["current_node"] = "ASKED_REPAIR_SCOPE"
        fixer["status"] = "VETTING_REPAIRS"
        return {
            "action": "SUGGEST",
            "reply_text": sanitize_sms_no_hyphens(reply),
            "node": "ASKED_REPAIR_SCOPE",
            "reason": "Trojan Horse Step 1: Inquiring on repair scope directly from the agent."
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
