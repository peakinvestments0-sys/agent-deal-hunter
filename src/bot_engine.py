"""
Lead Vetting & Underdog Model Bot Engine
Directly implements:
1. Lead Vetting Flow Chart (Lead Vetting Flow Chart@2x.png)
2. Underdog Model Macro Funnel (Underdog Model@2x.png)
3. Gemini AI Voice Enhancer & Golden Replies Training Engine
"""

import os
import re
import json
import time
import random
import requests
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
BOT_SETTINGS_FILE = os.path.join(DATA_DIR, "bot_settings.json")
TRAINING_DATA_FILE = os.path.join(DATA_DIR, "training_golden_replies.json")

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

DEFAULT_BOT_SETTINGS = {
    "enabled": True,
    "mode": "copilot",  # "copilot" (human approves before sending) or "autopilot" (auto dispatches via SMS)
    "bot_name": "Emma",
    "partner_name": "John",
    "office_phone": "(407) 815-5043",
    "call_window_hours": 3,
    "zestimate_gold_threshold": 0.80, # Asking <= 80% of Zestimate is GOLD
    "auto_send_delay_seconds": 30,
    "campaign_followup_1_days": 3,
    "campaign_followup_2_days": 7,
    "campaign_coldcall_days": 14,
    "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
    "gemini_model": "gemini-3.8-flash",
    "use_gemini_enhancer": True,
    "auto_cadence_followup_enabled": True,
    "cadence_send_time": "09:00",
    "cadence_throttle_seconds": 6
}

# --- Standard Script Constants from Lead Vetting Flow Chart ---
SCRIPTS = {
    # Entry Hook
    "ENTRY_HOOK": "Amazing, what can you share with me about this one?",
    
    # On-Market Branch
    "ON_MARKET_CHECK_OFFERS": "Awesome, I see its currently listed on market. Do you have any offers on the table?",
    "ON_MARKET_TURNKEY_DOM": "Amazing. This one looks beautiful. I see you guys have had it on the market for {dom} days. What are the sellers looking to do?",
    "ON_MARKET_TURNKEY_CREATIVE": "Great. Makes a ton of sense. Normally we buy the fixer uppers like everyone else. For a turnkey property like this one we can pay close to retail but it has to be on creative terms. Would they be open to that conversation?",
    "ON_MARKET_NEEDS_WORK_NEGOTIABLE": "Perfect. For properties like this one, we can come in with a cash offer but its typically going to be less than what the list price is. Are the sellers negotiable?",
    "ON_MARKET_NEEDS_WORK_PHOTOS": "Amazing. Well I have all the photos online, is there anything else I should know before we start to evaluate the property?",
    
    # Off-Market Branch
    "OFF_MARKET_CONDITION": "What can you tell me about the condition? What kind of shape are the roof, AC, and interior in?",
    "OFF_MARKET_PHOTOS": "Perfect, do you have any photos, a walkthrough link, or lockbox code by chance?",
    "OFF_MARKET_PRICE": "Thank you for that. What are they looking to get?",
    
    # Off-Market Updated & Asking > Zestimate
    "OFF_MARKET_UPDATED_CREATIVE": "Amazing. Well the house sounds incredible. We typically like to buy the homes that need some work. For this one, it sounds like its pretty much ready to go. The only way I can pay their retail price on this one would have to be on creative terms. Are they open to that discussion?",
    
    # Off-Market Fixer & Asking <= 80% Zestimate (THE GOLD)
    "OFF_MARKET_GOLD_TIMELINE": "Great, thank you for sharing this with me. How soon are the sellers looking to make a decision?",
    "OFF_MARKET_GOLD_SET_APPT": "Great. I will go ahead and set you up with my partner John who does all of our deal evaluations and see if we can get you a competitive offer. Would later today or tomorrow morning work better for a quick 5-minute call?",
    
    # Handoff & Appointment Closes
    "MATT_APPOINTMENT_REQUEST": "Great. I will go ahead and set you up with my partner John who does all of our deal evaluations and see if we can get you a competitive offer. Would later today or tomorrow morning work better for a quick 5-minute call?",
    "MATT_APPOINTMENT_CLARIFY": "Awesome. Would later today or tomorrow morning work better for a quick 5-minute call with John?",
    "MATT_APPOINTMENT_CONFIRMED": "Sounds great! I have scheduled John to call you at {time} from our office line (407) 815-5043. We look forward to connecting and seeing if we can make a deal work together.",
    
    # Tier 2 Nurture Pivot
    "TIER_2_NURTURE_ASK": "Perfect, I completely understand. We buy all types of properties in all kinds of situations. Do you know of anyone that may have a fixer upper coming soon?",
    "TIER_2_NURTURE_SAVED": "No problem at all! Keep our info handy and please let us know whenever you come across any off-market or fixer properties. Happy to have you represent us!",

    # Identity & Persona Inquiries
    "IDENTITY_EXPLAINED": "Hey {first_name}, this is {bot_name} with {partner_name}'s acquisition team at Peak Investments! He asked me to reach out regarding {address}. Are you still working with the sellers on this one?",
    
    # Underdog Model Follow-up Sequence Templates
    "FOLLOWUP_1": "Hey {first_name}, just following up on {address}. Did you guys end up taking an offer or is it still available? Still actively buying in {city}.",
    "FOLLOWUP_2": "Hi {first_name}, circling back one more time regarding {address}. If anything falls through or you have another off-market fixer coming up in {county}, let me know! Happy to pay full commission."
}


def load_bot_settings() -> Dict[str, Any]:
    if os.path.exists(BOT_SETTINGS_FILE):
        try:
            with open(BOT_SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg = dict(DEFAULT_BOT_SETTINGS)
                cfg.update(saved)
                return cfg
        except Exception:
            pass
    return dict(DEFAULT_BOT_SETTINGS)


def save_bot_settings(settings: Dict[str, Any]):
    cfg = dict(DEFAULT_BOT_SETTINGS)
    cfg.update(settings)
    with open(BOT_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


# --- Golden Replies Training Data Helpers ---

def load_golden_replies() -> List[Dict[str, Any]]:
    if os.path.exists(TRAINING_DATA_FILE):
        try:
            with open(TRAINING_DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
    return []


def save_golden_reply(entry: Dict[str, Any]):
    """Appends or updates a golden training example when user approves/edits a reply."""
    replies = load_golden_replies()
    entry_id = entry.get("id") or f"golden_{int(time.time())}_{random.randint(100, 999)}"
    entry["id"] = entry_id
    if not entry.get("timestamp"):
        entry["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")

    # Replace existing or insert at the beginning
    replies = [r for r in replies if r.get("id") != entry_id]
    replies.insert(0, entry)
    replies = replies[:100]  # Cap at 100 recent high-quality training pairs

    try:
        with open(TRAINING_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(replies, f, indent=2)
    except Exception as e:
        print(f"Error saving golden reply: {e}")


def delete_golden_reply(entry_id: str) -> bool:
    """Removes a golden training example by ID."""
    replies = load_golden_replies()
    initial_len = len(replies)
    replies = [r for r in replies if r.get("id") != entry_id]
    if len(replies) != initial_len:
        try:
            with open(TRAINING_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(replies, f, indent=2)
            return True
        except Exception:
            return False
    return False


# --- Standard Flowchart Scenarios for Studio Critiques ---
STANDARD_TRAINING_SCENARIOS = [
    {
        "node": "ENTRY_HOOK_AWAITING_REPLY",
        "title": "1. Inbound Property Pitch",
        "category": "Initial Contact",
        "description": "When an agent texts a property address or initial pitch.",
        "sample_inbound": "Hey Johnathan, I have a property at 123 Main St in Melbourne.",
        "default_suggestion": "Amazing, what can you share with me about this one?",
        "default_script": "Amazing, what can you share with me about this one?"
    },
    {
        "node": "OFF_MARKET_CONDITION",
        "title": "2. Vetting Condition (Roof, AC, Interior)",
        "category": "Condition Vetting",
        "description": "When an off-market deal is pitched, asking for specific mechanical & cosmetic repair scope.",
        "sample_inbound": "Hey Johnathan, I have an off-market 3/2 fixer at 789 Ocean Breeze Ave in Melbourne, seller asking $180k cash.",
        "default_suggestion": "What can you tell me about the condition? What kind of shape are the roof, AC, and interior in?",
        "default_script": "What can you tell me about the condition? What kind of shape are the roof, AC, and interior in?"
    },
    {
        "node": "OFF_MARKET_PHOTOS",
        "title": "3. Requesting Photos & Access",
        "category": "Property Access",
        "description": "After condition is described, asking for photo link, walkthrough video, or lockbox code.",
        "sample_inbound": "Roof is about 12 years old, AC is working fine. Needs full kitchen and bathroom update, cosmetic rehab throughout.",
        "default_suggestion": "Perfect, do you have any photos, a walkthrough link, or lockbox code by chance?",
        "default_script": "Perfect, do you have any photos, a walkthrough link, or lockbox code by chance?"
    },
    {
        "node": "OFF_MARKET_PRICE",
        "title": "4. Inquiring Asking Price",
        "category": "Pricing & Valuation",
        "description": "When photos are shared but asking price was not disclosed yet.",
        "sample_inbound": "Here is the drive link with 25 photos: drive.google.com/test123",
        "default_suggestion": "Thank you for that. What are the sellers looking to get for it?",
        "default_script": "Thank you for that. What are the sellers looking to get for it?"
    },
    {
        "node": "OFF_MARKET_GOLD_TIMELINE",
        "title": "5. Asking Decision Timeline (Gold Deal)",
        "category": "Seller Motivation",
        "description": "When asking price is <= 80% Zestimate (THE GOLD), asking closing & decision timeframe.",
        "sample_inbound": "Photos are attached, asking $180k cash.",
        "default_suggestion": "Great, thank you for sharing this with me. How soon are the sellers looking to make a decision?",
        "default_script": "Great, thank you for sharing this with me. How soon are the sellers looking to make a decision?"
    },
    {
        "node": "OFF_MARKET_UPDATED_CREATIVE",
        "title": "6. Retail Price -> Creative Terms Pivot",
        "category": "Creative Financing",
        "description": "When property is turnkey or seller asking full retail price, pivoting to creative financing (seller finance / sub-to).",
        "sample_inbound": "It is in pristine move-in condition, sellers want $410,000 cash firm.",
        "default_suggestion": "Amazing. Well the house sounds incredible. For this one, the only way I can pay their retail price would have to be on creative terms. Are they open to that discussion?",
        "default_script": "Amazing. Well the house sounds incredible. For this one, the only way I can pay their retail price would have to be on creative terms. Are they open to that discussion?"
    },
    {
        "node": "MATT_APPOINTMENT_REQUEST",
        "title": "7. Underwriting Partner Handoff",
        "category": "Appointment Booking",
        "description": "Introducing underwriting partner John for a 5-minute evaluation call.",
        "sample_inbound": "Seller wants to close within the next 2-3 weeks, needs cash fast.",
        "default_suggestion": "Great. I will go ahead and set you up with my partner John who does all of our deal evaluations and see if we can get you a competitive offer. Would later today or tomorrow morning work better for a quick 5-minute call?",
        "default_script": "Great. I will go ahead and set you up with my partner John who does all of our deal evaluations and see if we can get you a competitive offer. Would later today or tomorrow morning work better for a quick 5-minute call?"
    },
    {
        "node": "APPOINTMENT_CONFIRMED",
        "title": "8. Confirming Call Appointment",
        "category": "Appointment Booking",
        "description": "When agent gives their availability time for the call.",
        "sample_inbound": "Tomorrow at 2pm works great for us.",
        "default_suggestion": "Sounds great! I have scheduled John to call you tomorrow at 2pm. We look forward to connecting and seeing if we can make a deal work together.",
        "default_script": "Sounds great! I have scheduled John to call you tomorrow at 2pm. We look forward to connecting and seeing if we can make a deal work together."
    },
    {
        "node": "TIER_2_NURTURE_ASK",
        "title": "9. Tier 2 Pocket Lead Pivot",
        "category": "Nurture Lead",
        "description": "When seller declines creative terms or cash discount, pivoting to ask for upcoming pocket deals.",
        "sample_inbound": "No, they will not do creative financing. Cash only.",
        "default_suggestion": "Perfect, I completely understand. We buy all types of properties in all kinds of situations. Do you know of anyone that may have a fixer upper coming soon?",
        "default_script": "Perfect, I completely understand. We buy all types of properties in all kinds of situations. Do you know of anyone that may have a fixer upper coming soon?"
    },
    {
        "agent_desk": "BROOKE",
        "node": "IDENTITY_EXPLAINED",
        "title": "10. Identity Verification ('Who is this?')",
        "category": "Identity & Tone",
        "description": "When an agent asks who is texting or what company you are with, introducing the assistant and partner.",
        "sample_inbound": "Who is this? What company are you with?",
        "default_suggestion": "Hey Candace, Brooke here! Reaching out regarding 123 Main St for John. Are you still working with the sellers on this one?",
        "default_script": "Hey Candace, Brooke here! Reaching out regarding 123 Main St for John. Are you still working with the sellers on this one?"
    },
    # --- Lauren's Redfin Trojan Horse Scenarios ---
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_OPENING_HOOK",
        "title": "1. Smart Opening Hook (Flattery & Condition)",
        "category": "Trojan Horse Step 1",
        "description": "Reaching out on a Redfin fixer with natural flattery, acknowledging listed remarks, and asking about unlisted condition with zero hyphens.",
        "sample_inbound": "[New Redfin Fixer Scraped: 456 Palm Breeze Rd, Melbourne, FL. Remarks: Handyman special, cash only, needs complete kitchen, bath, and roof.]",
        "default_suggestion": "Hey Sarah, Lauren here. Saw your listing on Palm Breeze Rd. Saw your notes about the roof and interior updates needed. Other than what is already noted in the listing, does the home need anything else major to get it to full market value?",
        "default_script": "Hey Sarah, Lauren here. Saw your listing on Palm Breeze Rd. Saw your notes about the roof and interior updates needed. Other than what is already noted in the listing, does the home need anything else major to get it to full market value?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_ASK_REPAIR_SCOPE",
        "title": "2. Repair Scope Extraction (Major Mechanicals)",
        "category": "Trojan Horse Step 2",
        "description": "When agent confirms negotiability, asking about the major mechanicals (roof, AC, plumbing, electrical).",
        "sample_inbound": "Yes the sellers are very negotiable, they just want it sold this month.",
        "default_suggestion": "Awesome, thanks for getting back to me Sarah. In your opinion, what shape are the major mechanicals in (roof, AC, plumbing, electrical), and what kind of rehab do you think it needs?",
        "default_script": "Awesome, thanks for getting back to me Sarah. In your opinion, what shape are the major mechanicals in (roof, AC, plumbing, electrical), and what kind of rehab do you think it needs?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_ASK_REPAIR_COST",
        "title": "3. Dollar Rehab Extraction (Get Agent's Number)",
        "category": "Trojan Horse Step 3",
        "description": "After agent lists repairs, asking for their exact dollar estimate so they anchor their own rehab cost.",
        "sample_inbound": "Needs a full roof, AC is ancient, and the whole inside is 1980s original.",
        "default_suggestion": "Got it, that helps a ton. When you walk through it, what dollar amount do you think a buyer needs to sink into it to get it to top of market condition?",
        "default_script": "Got it, that helps a ton. When you walk through it, what dollar amount do you think a buyer needs to sink into it to get it to top of market condition?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_ASK_AGENT_ARV",
        "title": "4. Back-End ARV Extraction",
        "category": "Trojan Horse Step 4",
        "description": "Asking what the listing agent realistically thinks it will list and sell for once fully renovated.",
        "sample_inbound": "A flipper is probably looking at 50k to 60k in work.",
        "default_suggestion": "Makes total sense. If our crew comes in and does all that work to make it pristine, what do you think you could realistically list and sell it for on the back end?",
        "default_script": "Makes total sense. If our crew comes in and does all that work to make it pristine, what do you think you could realistically list and sell it for on the back end?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_MATH_DROP",
        "title": "5. The Math Drop (Low ARV Arbitrage)",
        "category": "Trojan Horse Step 5A",
        "description": "When agent ARV is low, accept their comp immediately, say nothing about higher comps, and run math from their low number.",
        "sample_inbound": "If it is completely remodeled like new, maybe 260k max in this pocket.",
        "default_suggestion": "Sarah, running your numbers through our flip calculator: based on your $260,000 resale number, minus ~55k in repairs, 9 percent in holding and commission fees, and our crew's standard 15 percent margin puts John right around $128,000 cash with zero inspection contingencies. That is why we are coming in way under that one. Would it make sense to send over an offer and have John do a follow up for any questions?",
        "default_script": "Sarah, running your numbers through our flip calculator: based on your $260,000 resale number, minus ~55k in repairs, 9 percent in holding and commission fees, and our crew's standard 15 percent margin puts John right around $128,000 cash with zero inspection contingencies. That is why we are coming in way under that one. Would it make sense to send over an offer and have John do a follow up for any questions?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_HIGH_ARV_ANCHOR",
        "title": "6. High ARV Anchor (Conservative Comps)",
        "category": "Trojan Horse Step 5B",
        "description": "When agent ARV is high or close to right, anchor them down showing low conservative comps.",
        "sample_inbound": "Comps are easily at $380,000 all day long.",
        "default_suggestion": "Sarah, we looked closely at those comps, but recent conservative neighborhood sales are sitting lower around $256,500. Running that through our flip calculator, minus ~55k in repairs, 9 percent in holding and commission fees, and our crew's standard 15 percent margin puts John right around $125,000 cash with zero inspection contingencies. That is why we are coming in way under that one. Would it make sense to send over an offer and have John do a follow up for any questions?",
        "default_script": "Sarah, we looked closely at those comps, but recent conservative neighborhood sales are sitting lower around $256,500. Running that through our flip calculator, minus ~55k in repairs, 9 percent in holding and commission fees, and our crew's standard 15 percent margin puts John right around $125,000 cash with zero inspection contingencies. That is why we are coming in way under that one. Would it make sense to send over an offer and have John do a follow up for any questions?"
    },
    {
        "agent_desk": "LAUREN",
        "node": "LAUREN_STANDING_LOI",
        "title": "7. Pushback & 30 Day Standing Written LOI",
        "category": "Standing Paper Trail",
        "description": "When the agent rejects the offer or claims it is too low, leaving a 30 day standing written LOI with Page 12 commission protection.",
        "sample_inbound": "No way, seller turned down 170k last week. That is way too low.",
        "default_suggestion": "Totally understand we have a gap right now, Sarah! I just shot our formal written terms to your email as well as a standing cash offer at $128,000 just in case the seller's circumstances or timeline change down the road, or if anything falls through with another buyer. Our offer stands for 30 days. If anything shifts, John and I are ready to close clean in 14 days!",
        "default_script": "Totally understand we have a gap right now, Sarah! I just shot our formal written terms to your email as well as a standing cash offer at $128,000 just in case the seller's circumstances or timeline change down the road, or if anything falls through with another buyer. Our offer stands for 30 days. If anything shifts, John and I are ready to close clean in 14 days!"
    }
]


def test_gemini_connection(api_key: str, model: str = "gemini-3.5-flash-lite") -> Dict[str, Any]:
    """Tests connectivity to Google Gemini API using REST endpoint."""
    if not api_key:
        return {"status": "error", "message": "No Gemini API key provided."}
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": "Respond with 'GEMINI_OK' if you can read this."}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 20,
                "temperature": 0.1
            }
        }
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=20)
        if res.status_code == 200:
            data = res.json()
            cand = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return {"status": "success", "message": f"Successfully connected to Google Gemini ({model})!", "response": cand.strip()}
        else:
            return {"status": "error", "message": f"Gemini API returned HTTP {res.status_code}: {res.text}"}
    except Exception as e:
        return {"status": "error", "message": f"Gemini connection failed: {str(e)}"}


def polish_reply_with_gemini(node: str, template_reply: str, agent: Dict[str, Any], inbound_message: str) -> str:
    """
    Enhances the deterministic flowchart script using Gemini with few-shot golden examples.
    Strictly preserves the node objective while matching authentic Florida investor voice.
    Falls back gracefully to template_reply if API key is absent or request fails.
    """
    settings = load_bot_settings()
    api_key = (settings.get("gemini_api_key") or os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key or not settings.get("use_gemini_enhancer", True):
        return template_reply

    # HARD FIREWALL: Cold first-touch openers must ALWAYS send deterministically from approved templates.
    # Never allow Gemini to rewrite cold outbound texts (prevents 'Happy Friday!' or syrupy gratitude fluff).
    COLD_OPENER_NODES = {
        "OPENING_HOOK",
        "ENTRY_HOOK",
        "ENTRY_HOOK_AWAITING_REPLY",
        "FIRST_TOUCH",
        "LAUREN_OPENING_HOOK",
        "BROOKE_COLD_ICEBREAKER"
    }
    if node in COLD_OPENER_NODES:
        return sanitize_sms_no_hyphens(template_reply)

    model = settings.get("gemini_model", "gemini-3.5-flash-lite")
    partner_name = settings.get("partner_name", "Jessica")
    agent_name = agent.get("first_name") or agent.get("full_name") or "there"

    is_lauren = node.startswith("LAUREN_")
    bot_name = "Lauren" if is_lauren else settings.get("bot_name", "Brooke")
    office_phone = settings.get("office_phone", "(407) 815-5043")

    # Grab 6 most relevant golden examples for few-shot prompt for this specific assistant
    all_goldens = load_golden_replies()
    if is_lauren:
        goldens = [g for g in all_goldens if g.get("agent_desk") == "LAUREN"][:6]
    else:
        goldens = [g for g in all_goldens if g.get("agent_desk") == "BROOKE" or not g.get("agent_desk")][:6]

    few_shots = ""
    for g in goldens:
        inb = g.get("agent_inbound")
        out = g.get("final_approved_text")
        if inb and out:
            few_shots += f"\nAgent: {inb}\n{bot_name}: {out}\n"

    if is_lauren:
        system_prompt = (
            f"You are Lauren, an acquisition specialist working with {partner_name}.\n"
            f"You are texting via cellular SMS with a Florida listing agent regarding an on-market fixer property.\n"
            f"You use the Trojan Horse Socratic approach: subtle natural intro, inquiring on unlisted condition, extracting repair dollars, and presenting math.\n"
            f"FLOWCHART OBJECTIVE FOR THIS NODE ({node}):\n"
            f"\"{template_reply}\"\n\n"
            f"CRITICAL RULES:\n"
            f"1. STRICT ZERO HYPHENS RULE: NEVER EVER use hyphens or dashes between words anywhere in your response. (For example write 'top of market', 'as is', '14 day close', '9 percent', '15 percent', 'full market value', '2026 HGTV full retail'). Do not use dashes or hyphens.\n"
            f"2. BANNED FILLER & GRATITUDE (STRICT): NEVER say 'Happy Friday', 'Hope your week is going great', 'Hope this text finds you well', 'Hope you are well', 'Awesome thanks for thinking of us', or 'Thank you for reaching out'. Do NOT start texts with syrupy customer service gratitude.\n"
            f"3. Keep it natural, human, casual, and grounded (1 to 2 sentences max). Real buyers text casually on phone.\n"
            f"4. FLATTERY & TONE: Never use fake or gushing flattery like 'love that pocket of Orlando'. Keep comments subtle, authentic, and grounded in property reality.\n"
            f"5. IDENTITY: Introduce yourself as 'Lauren here' or 'its Lauren'. DO NOT say 'with 407 Flips' or 'from 407 Flips' in initial texts. Company info is mentioned later when relevant.\n"
            f"6. RETAIL TARGET VARIETY: Vary phrasing for condition targets such as 'full market value', '2026 HGTV full retail', 'full retail value', 'top of the neighborhood', 'top of market', or 'fully renovated retail'.\n"
            f"7. Output ONLY the raw SMS text. No quotation marks, no greetings like 'Dear', no markdown."
        )
    else:
        system_prompt = (
            f"You are {bot_name}, an active acquisitions coordinator working with {partner_name}.\n"
            f"You are texting via cellular SMS with a Florida real estate listing agent.\n"
            f"Underwriting evaluation partner: {partner_name}.\n"
            f"Main office phone for calls: {office_phone}.\n"
            f"FLOWCHART OBJECTIVE FOR THIS NODE ({node}):\n"
            f"\"{template_reply}\"\n\n"
            f"CRITICAL RULES:\n"
            f"1. STRICT ZERO HYPHENS RULE: NEVER EVER use hyphens or dashes between words anywhere in your response. (Write 'off market', 'as is', 'pre MLS', '10 day close').\n"
            f"2. BANNED FILLER & GRATITUDE (STRICT): NEVER say 'Happy Friday', 'Hope your week is going great', 'Hope this text finds you well', 'Hope you are well', 'Awesome thanks for thinking of us', or 'Thank you for reaching out'. Do NOT start texts with syrupy customer service gratitude.\n"
            f"3. Keep it short, natural, direct, and human (1 to 2 sentences max, under 160 characters when possible). Text like a busy acquisitions investor typing on an iPhone with thumbs.\n"
            f"4. IDENTITY: Introduce yourself as '{bot_name} here' or 'its {bot_name}'. DO NOT say 'with 407 Flips' in initial outreach.\n"
            f"5. Strictly achieve the current step's objective: inquire on condition, ask for photo link or access, ask timeline, or schedule quick call with {partner_name}.\n"
            f"6. Output ONLY the raw SMS text. No quotation marks, no greetings like 'Dear', no markdown."
        )

    user_prompt = (
        f"FEW-SHOT EXAMPLES OF APPROVED TEXTING STYLE:\n{few_shots}\n\n"
        f"CURRENT CONVERSATION:\n"
        f"Agent Name: {agent_name}\n"
        f"Agent Inbound SMS: \"{inbound_message}\"\n"
        f"Core Script Intent: \"{template_reply}\"\n\n"
        f"Your SMS text reply:"
    )

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"{system_prompt}\n\n{user_prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "maxOutputTokens": 90,
                "temperature": 0.3
            }
        }
        res = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=25)
        if res.status_code == 200:
            data = res.json()
            cand = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
            cand = cand.strip('"\n\r ')
            if cand.lower().startswith("johnathan:"):
                cand = cand[10:].strip()
            if len(cand) >= 12:
                return cand
    except Exception:
        pass

    return template_reply


# --- Helper Parsing Utilities ---

OPT_OUT_KEYWORDS = [
    "stop", "unsubscribe", "remove", "wrong number", "take me off", 
    "do not text", "don't text", "lose my number", "cease", "f*** off"
]

TURNKEY_KEYWORDS = [
    "turnkey", "move in ready", "move-in ready", "remodeled", "renovated", 
    "updated", "great condition", "pristine", "brand new", "mint condition", 
    "fully updated", "no work needed", "no repairs", "gorgeous"
]

NEEDS_WORK_KEYWORDS = [
    "needs work", "fixer", "fix and flip", "tlc", "needs tlc", "rehab", 
    "gut", "rough", "handyman", "as is", "as-is", "roof is old", 
    "needs roof", "needs kitchen", "water damage", "fire damage", 
    "structural", "teardown", "dated", "cosmetic", "fixer upper"
]

DETAILED_CONDITION_KEYWORDS = [
    "roof", "a/c", "ac", "hvac", "plumbing", "electrical", "foundation", 
    "kitchen", "bath", "bathroom", "flooring", "paint", "gut", 
    "water damage", "fire damage", "permit", "years old", "scope", "drywall"
]

PHOTO_KEYWORDS = [
    "http", "drive.google", "dropbox", "box.com", "photo", "photos", 
    "pictures", "pics", "link", "lockbox", "combo", "code", "supra", "sent photos"
]

CREATIVE_YES_KEYWORDS = [
    "yes", "yeah", "yep", "sure", "open to it", "maybe", "depends", 
    "what are the terms", "what terms", "explain", "open to creative", 
    "tell me more", "how does that work", "possibly", "seller finance", "sub to"
]

CREATIVE_NO_KEYWORDS = [
    "no", "nope", "not open", "cash only", "they want cash", "wont do", "won't do",
    "standard sale", "conventional", "will not consider", "not interested", "no terms"
]


def is_opt_out(text: str) -> bool:
    clean = text.lower().strip()
    return any(k in clean for k in OPT_OUT_KEYWORDS)


def extract_price(text: str) -> Optional[float]:
    """Extracts dollar price from phrases like '$250k', '250,000', 'asking 320k', '$400000', '$180k cash'."""
    clean = text.lower().replace(",", "")
    
    # Matches $250k or 250k
    k_match = re.search(r'\$?(\d+(?:\.\d+)?)\s*k\b', clean)
    if k_match:
        return float(k_match.group(1)) * 1000.0

    # Matches $250000 or 250000 (minimum 5 digits)
    num_match = re.search(r'\$?(\d{5,8})\b', clean)
    if num_match:
        return float(num_match.group(1))

    # Matches $xxx,xxx
    full_match = re.search(r'\$(\d+)', text.replace(",", ""))
    if full_match:
        val = float(full_match.group(1))
        if val >= 10000:
            return val

    return None


def extract_address_candidate(text: str) -> Optional[str]:
    """Finds street address pattern like '123 Main St' or '789 Ocean Breeze Ave' while avoiding fractions like '3/2'."""
    pattern = r'(?<!\/)(?<!\d\/)\b(\d{1,5}\s+(?:[A-Za-z0-9\.]+\s+){1,4}(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Ct|Court|Pl|Place|Trl|Trail|Pkwy|Parkway|Loop|Cir|Circle))\b'
    m = re.search(pattern, text, re.IGNORECASE)
    if m:
        return m.group(1).strip().title()
    return None


def extract_time_candidate(text: str) -> Optional[str]:
    """Extracts appointment availability like 'tomorrow at 2pm', 'after 3', 'morning', etc."""
    time_patterns = [
        r'\b(?:at|around|after)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b',
        r'\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b',
        r'\b\d{1,2}\s*o\'?clock\b',
        r'\btomorrow\b(?:\s+(?:morning|afternoon|evening|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?',
        r'\btoday\b(?:\s+(?:morning|afternoon|evening|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?',
        r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b(?:\s+(?:morning|afternoon|evening|at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?))?',
        r'\b(?:anytime|morning|afternoon|evening|noon)\b'
    ]
    for pat in time_patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m and len(m.group(0).strip()) > 1:
            return m.group(0).strip().title()
    return None


# --- Bot State Machine Engine ---

class BotEngine:
    def __init__(self):
        self.settings = load_bot_settings()

    def get_initial_vetting_state(self, agent: Dict[str, Any]) -> Dict[str, Any]:
        """Initial state structure for an agent entering the vetting flow."""
        primary_l = (agent.get("listings") or [{}])[0]
        return {
            "active": True,
            "current_node": "AWAITING_ADDRESS",
            "flow_type": "UNKNOWN", # ON_MARKET_TURNKEY, ON_MARKET_NEEDS_WORK, OFF_MARKET_CREATIVE, OFF_MARKET_GOLD
            "address": primary_l.get("address", agent.get("primary_address", "")),
            "city": primary_l.get("city", agent.get("primary_city", "")),
            "dom": primary_l.get("days_on_market", agent.get("primary_dom", 0)),
            "listing_price": primary_l.get("listing_price", agent.get("primary_price", 0.0)),
            "zestimate": primary_l.get("estimated_value", primary_l.get("listing_price", 0.0)),
            "asking_price": 0.0,
            "price_to_zestimate_ratio": None,
            "is_gold": False,
            "condition": "UNKNOWN", # TURNKEY, NEEDS_WORK
            "condition_notes": "",
            "photos_shared": False,
            "creative_open": None,
            "decision_timeline": "",
            "appointment_time": None,
            "appointment_deadline": None,
            "notes": [],
            "suggested_reply": "",
            "suggested_reply_node": "",
            "suggested_reply_reason": "",
            "last_interaction": time.strftime("%Y-%m-%d %H:%M:%S")
        }

    def evaluate_inbound_sms(self, agent: Dict[str, Any], message: str) -> Dict[str, Any]:
        """
        Processes an incoming SMS message from an agent through the flowchart decision tree.
        Guarantees thorough multi-step vetting:
        Address -> Detailed Condition (roof, AC, interior) -> Photos/Access -> Price & Gold Ratio -> Timeline -> Partner Appointment.
        """
        settings = load_bot_settings()
        partner_name = settings.get("partner_name", "Jessica")
        clean_msg = message.lower().strip()
        state = agent.get("bot_vetting") or self.get_initial_vetting_state(agent)
        state_updates = dict(state)
        state_updates["notes"] = list(state.get("notes", []))
        state_updates["notes"].append(f"Agent: {message}")
        state_updates["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")

        # 1. OPT-OUT & COMPLIANCE GUARD
        if is_opt_out(clean_msg):
            state_updates["active"] = False
            state_updates["current_node"] = "CASH_AGENT_DEAD"
            return {
                "action": "OPT_OUT",
                "reply_text": "",
                "node": "CASH_AGENT_DEAD",
                "tier_update": "🛑 Cash Agent Dead",
                "stage_update": "Opt-Out / Dead",
                "state_updates": state_updates
            }

        # 1b. IDENTITY & PERSONA INQUIRY ("Who is this?" / "Who am I talking to?")
        IDENTITY_KEYWORDS = [
            "who is this", "who's this", "whos this", "who is texting", 
            "who am i talking to", "who am i speaking with", "who are you", 
            "what company", "who is reaching out", "whose number is this",
            "who is it"
        ]
        if any(k in clean_msg for k in IDENTITY_KEYWORDS):
            agent_first = agent.get("first_name") or (agent.get("full_name", "").split()[0] if agent.get("full_name") else "there")
            bot_name = settings.get("bot_name", "Emma")
            primary_addr = state_updates.get("address") or (agent.get("listings") or [{}])[0].get("address") or "your listing"
            state_updates["current_node"] = "IDENTITY_EXPLAINED"
            base_reply = f"Hey {agent_first}, {bot_name} here! Reaching out regarding {primary_addr} for {partner_name}. Are you still working with the sellers on this one?"
            reason = f"Agent asked for identity verification. {bot_name} introduced herself and {partner_name} and refocused on {primary_addr}."
            
            reply = polish_reply_with_gemini("IDENTITY_EXPLAINED", base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = "IDENTITY_EXPLAINED"
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": "IDENTITY_EXPLAINED",
                "tier_update": "🔥 Tier 1: In Conversation",
                "stage_update": "Warm / In Discussion",
                "state_updates": state_updates
            }

        curr_node = state.get("current_node", "AWAITING_ADDRESS")

        # Check for extracted address and price in the incoming message
        extracted_addr = extract_address_candidate(message)
        price_found = extract_price(message)
        if price_found:
            state_updates["asking_price"] = price_found

        is_off_market_text = (
            "off-market" in clean_msg or "off market" in clean_msg or 
            "pocket" in clean_msg or "fixer" in clean_msg
        )

        # 2. PROPERTY RESET DETECTION:
        # If an address candidate is mentioned AND it's a new pitch or previous state reached appointment,
        # reset state to evaluate this new deal from step 1!
        if extracted_addr and (
            curr_node in ["AWAITING_ADDRESS", "START", "APPOINTMENT_CONFIRMED", "APPOINTMENT_CLARIFY", "CASH_AGENT_DEAD"] or
            state_updates.get("address", "").lower() != extracted_addr.lower() or
            is_off_market_text
        ):
            # Check if address matches an MLS listing in agent's inventory
            matched_listing = None
            for l in agent.get("listings", []):
                if extracted_addr.lower() in l.get("address", "").lower():
                    matched_listing = l
                    break

            state_updates["address"] = extracted_addr
            if matched_listing:
                state_updates["flow_type"] = "ON_MARKET"
                state_updates["dom"] = matched_listing.get("days_on_market", 0)
                state_updates["listing_price"] = matched_listing.get("listing_price", 0.0)
                state_updates["zestimate"] = matched_listing.get("estimated_value", matched_listing.get("listing_price", 0.0))
            else:
                state_updates["flow_type"] = "OFF_MARKET"
                # If Zestimate unknown, default to a realistic Brevard baseline ($275,000) or 1.35x asking
                if state_updates.get("zestimate", 0) == 0:
                    state_updates["zestimate"] = (price_found * 1.35) if price_found else 275000.0

            # If Off-market deal was pitched with address:
            if state_updates["flow_type"] == "OFF_MARKET" or is_off_market_text:
                state_updates["flow_type"] = "OFF_MARKET"
                # Check if agent provided detailed condition notes right off the bat
                has_detailed_condition = any(k in clean_msg for k in DETAILED_CONDITION_KEYWORDS)
                has_photos = any(k in clean_msg for k in PHOTO_KEYWORDS)

                if not has_detailed_condition:
                    # Step 1 of Off-market: Must vet condition (roof, AC, interior rehab scope)!
                    state_updates["current_node"] = "OFF_MARKET_CONDITION"
                    base_reply = f"Hey, thanks for thinking of us on {extracted_addr}! What can you tell me about the condition? What kind of shape are the roof, A/C, and interior in?"
                    reason = f"Off-market deal received ({extracted_addr}). Vetting condition details (roof, A/C, and interior rehab)."
                elif not has_photos:
                    # Step 2: Condition is known, ask for photos/lockbox
                    state_updates["condition_notes"] = message
                    state_updates["current_node"] = "OFF_MARKET_PHOTOS"
                    base_reply = SCRIPTS["OFF_MARKET_PHOTOS"]
                    reason = "Condition noted. Inquiring about photo link or lockbox code."
                else:
                    # Condition and photos both provided, advance to price & timeline
                    state_updates["photos_shared"] = True
                    state_updates["condition_notes"] = message
                    state_updates["current_node"] = "OFF_MARKET_GOLD_TIMELINE"
                    base_reply = SCRIPTS["OFF_MARKET_GOLD_TIMELINE"]
                    reason = "Condition and photos already provided. Inquiring about decision timeline."

                reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
                state_updates["suggested_reply"] = reply
                state_updates["suggested_reply_node"] = state_updates["current_node"]
                state_updates["suggested_reply_reason"] = reason

                return {
                    "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                    "reply_text": reply,
                    "node": state_updates["current_node"],
                    "tier_update": "🔥 Tier 1: In Conversation",
                    "stage_update": "Warm / In Discussion",
                    "state_updates": state_updates
                }
            else:
                # On-market listing entry
                state_updates["current_node"] = "ENTRY_HOOK_AWAITING_REPLY"
                base_reply = SCRIPTS["ENTRY_HOOK"]
                reason = "On-market listing identified. Asking what they can share about this property."
                reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)

                state_updates["suggested_reply"] = reply
                state_updates["suggested_reply_node"] = state_updates["current_node"]
                state_updates["suggested_reply_reason"] = reason

                return {
                    "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                    "reply_text": reply,
                    "node": state_updates["current_node"],
                    "tier_update": "🔥 Tier 1: In Conversation",
                    "stage_update": "Warm / In Discussion",
                    "state_updates": state_updates
                }

        # --- STEP-BY-STEP PROGRESSION ---

        # 3. OFF-MARKET FLOW: CONDITION VETTING
        if curr_node in ["OFF_MARKET_CONDITION", "ENTRY_HOOK_AWAITING_REPLY", "IDENTITY_EXPLAINED"]:
            # Check if agent notes condition
            has_detailed_condition = any(k in clean_msg for k in DETAILED_CONDITION_KEYWORDS) or any(k in clean_msg for k in NEEDS_WORK_KEYWORDS)
            has_photos = any(k in clean_msg for k in PHOTO_KEYWORDS)

            if state_updates.get("flow_type") == "OFF_MARKET" or is_off_market_text:
                state_updates["flow_type"] = "OFF_MARKET"
                if has_detailed_condition:
                    state_updates["condition_notes"] = message
                    if has_photos:
                        state_updates["photos_shared"] = True
                        # If price is already known, check ratio and advance to timeline
                        if state_updates.get("asking_price", 0) > 0:
                            asking = state_updates["asking_price"]
                            zest = state_updates.get("zestimate") or (asking * 1.30)
                            ratio = asking / zest
                            state_updates["price_to_zestimate_ratio"] = round(ratio, 3)
                            gold_threshold = settings.get("zestimate_gold_threshold", 0.80)

                            if ratio <= gold_threshold or ratio <= 0.85:
                                state_updates["is_gold"] = True
                                state_updates["flow_type"] = "OFF_MARKET_GOLD"
                                state_updates["current_node"] = "OFF_MARKET_GOLD_TIMELINE"
                                base_reply = SCRIPTS["OFF_MARKET_GOLD_TIMELINE"]
                                reason = f"⭐ GOLD PROPERTY DETECTED! Price (${asking:,.0f}) is {ratio*100:.1f}% of Zestimate. Condition & photos known. Inquiring on seller timeline."
                                tier = "⭐ Tier 1: GOLD DEAL"
                            else:
                                state_updates["current_node"] = "OFF_MARKET_CREATIVE"
                                base_reply = SCRIPTS["OFF_MARKET_UPDATED_CREATIVE"]
                                reason = "Price above cash threshold. Pivoting to creative terms."
                                tier = "🔥 Tier 1: Creative Terms"
                        else:
                            state_updates["current_node"] = "OFF_MARKET_PRICE"
                            base_reply = SCRIPTS["OFF_MARKET_PRICE"]
                            reason = "Condition and photos received. Inquiring on asking price."
                            tier = "🔥 Tier 1: In Conversation"
                    else:
                        # Advance to asking for photos
                        state_updates["current_node"] = "OFF_MARKET_PHOTOS"
                        base_reply = SCRIPTS["OFF_MARKET_PHOTOS"]
                        reason = "Condition details recorded. Inquiring on photos, walkthrough link, or lockbox code."
                        tier = "🔥 Tier 1: In Conversation"
                else:
                    # Still need condition
                    state_updates["current_node"] = "OFF_MARKET_CONDITION"
                    base_reply = SCRIPTS["OFF_MARKET_CONDITION"]
                    reason = "Off-market deal identified. Vetting what work it needs to reach 2025 renovated condition."
                    tier = "🔥 Tier 1: In Conversation"

                reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
                state_updates["suggested_reply"] = reply
                state_updates["suggested_reply_node"] = state_updates["current_node"]
                state_updates["suggested_reply_reason"] = reason

                return {
                    "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                    "reply_text": reply,
                    "node": state_updates["current_node"],
                    "tier_update": tier,
                    "stage_update": "Warm / In Discussion",
                    "state_updates": state_updates
                }

        # 4. OFF-MARKET FLOW: PHOTOS & ACCESS VETTING
        if curr_node == "OFF_MARKET_PHOTOS":
            if any(k in clean_msg for k in PHOTO_KEYWORDS) or "lockbox" in clean_msg or "link" in clean_msg or "code" in clean_msg or "pic" in clean_msg:
                state_updates["photos_shared"] = True

            # If asking price is already captured, do not ask again! Evaluate ratio and move to timeline
            asking = state_updates.get("asking_price") or 0.0
            if asking > 0:
                zest = state_updates.get("zestimate") or (asking * 1.30)
                ratio = asking / zest
                state_updates["price_to_zestimate_ratio"] = round(ratio, 3)
                gold_threshold = settings.get("zestimate_gold_threshold", 0.80)

                if ratio <= gold_threshold or ratio <= 0.85:
                    state_updates["is_gold"] = True
                    state_updates["flow_type"] = "OFF_MARKET_GOLD"
                    state_updates["current_node"] = "OFF_MARKET_GOLD_TIMELINE"
                    base_reply = SCRIPTS["OFF_MARKET_GOLD_TIMELINE"]
                    reason = f"⭐ GOLD PROPERTY DETECTED! Price (${asking:,.0f}) is {ratio*100:.1f}% of Zestimate. Photos acknowledged. Inquiring on decision timeline."
                    tier = "⭐ Tier 1: GOLD DEAL"
                else:
                    state_updates["current_node"] = "OFF_MARKET_CREATIVE"
                    base_reply = SCRIPTS["OFF_MARKET_UPDATED_CREATIVE"]
                    reason = "Price is above cash threshold. Pivoting to creative terms."
                    tier = "🔥 Tier 1: Creative Terms"
            else:
                state_updates["current_node"] = "OFF_MARKET_PRICE"
                base_reply = SCRIPTS["OFF_MARKET_PRICE"]
                reason = "Photos acknowledged. Inquiring on seller asking price."
                tier = "🔥 Tier 1: In Conversation"

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": tier,
                "stage_update": "Warm / In Discussion",
                "state_updates": state_updates
            }

        # 5. OFF-MARKET FLOW: ASKING PRICE & RATIO EVALUATION
        if curr_node == "OFF_MARKET_PRICE":
            if price_found:
                state_updates["asking_price"] = price_found

            asking = state_updates.get("asking_price") or 0.0
            zest = state_updates.get("zestimate") or 0.0
            if zest == 0.0 and asking > 0.0:
                zest = asking * 1.30
                state_updates["zestimate"] = zest

            ratio = (asking / zest) if zest > 0 else 1.0
            state_updates["price_to_zestimate_ratio"] = round(ratio, 3)

            is_needs_work = any(k in state_updates.get("condition_notes", "").lower() for k in NEEDS_WORK_KEYWORDS) or any(k in clean_msg for k in NEEDS_WORK_KEYWORDS)
            gold_threshold = settings.get("zestimate_gold_threshold", 0.80)

            # THE GOLD: Asking Price is <= 80% of Zestimate (or fixer <= 85%)
            if ratio <= gold_threshold or (is_needs_work and ratio <= 0.85):
                state_updates["is_gold"] = True
                state_updates["flow_type"] = "OFF_MARKET_GOLD"
                state_updates["current_node"] = "OFF_MARKET_GOLD_TIMELINE"
                base_reply = SCRIPTS["OFF_MARKET_GOLD_TIMELINE"]
                reason = f"⭐ GOLD PROPERTY DETECTED! Price (${asking:,.0f}) is {ratio*100:.1f}% of Zestimate (${zest:,.0f}). Inquiring on seller timeline."
                tier = "⭐ Tier 1: GOLD DEAL"
                stage = "Underwriting / Hot Lead"
            else:
                state_updates["is_gold"] = False
                state_updates["flow_type"] = "OFF_MARKET_CREATIVE"
                state_updates["current_node"] = "OFF_MARKET_CREATIVE"
                base_reply = SCRIPTS["OFF_MARKET_UPDATED_CREATIVE"]
                reason = f"Property updated or price (${asking:,.0f}) is {ratio*100:.1f}% of Zestimate. Pivoting to creative terms."
                tier = "🔥 Tier 1: Creative Terms"
                stage = "Creative Terms Review"

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": tier,
                "stage_update": stage,
                "state_updates": state_updates
            }

        # 6. OFF-MARKET FLOW: TIMELINE & MOTIVATION -> PARTNER HANDOFF
        if curr_node == "OFF_MARKET_GOLD_TIMELINE":
            state_updates["decision_timeline"] = message
            state_updates["current_node"] = "MATT_APPOINTMENT_REQUEST"
            base_reply = SCRIPTS["OFF_MARKET_GOLD_SET_APPT"].format(partner_name=partner_name)
            reason = f"Timeline acknowledged. Flowchart Action: Set 5-minute call with evaluation partner {partner_name}."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "⭐ Tier 1: GOLD DEAL (Appt Partner)",
                "stage_update": "Appointment Pending (Offer Pipeline)",
                "state_updates": state_updates
            }

        # 7. CREATIVE TERMS EVALUATION
        if curr_node in ["OFF_MARKET_CREATIVE", "ON_MARKET_TURNKEY_CREATIVE"]:
            if any(k in clean_msg for k in CREATIVE_NO_KEYWORDS):
                state_updates["creative_open"] = False
                state_updates["current_node"] = "TIER_2_NURTURE_ASK"
                base_reply = SCRIPTS["TIER_2_NURTURE_ASK"]
                reason = "Agent declined creative terms. Asking for upcoming fixer uppers to move to Tier 2."
                tier = "🌱 Tier 2: Pocket Lead Nurture"
                stage = "Tier 2 Nurture"
            elif any(k in clean_msg for k in CREATIVE_YES_KEYWORDS) or "?" in clean_msg:
                state_updates["creative_open"] = True
                state_updates["current_node"] = "MATT_APPOINTMENT_REQUEST"
                base_reply = SCRIPTS["MATT_APPOINTMENT_REQUEST"].format(partner_name=partner_name)
                reason = f"Agent open to creative terms. Booking call with {partner_name}."
                tier = "🔥 Tier 1: Hot Deal (Creative Terms)"
                stage = "Appointment Pending"
            else:
                state_updates["current_node"] = "MATT_APPOINTMENT_REQUEST"
                base_reply = SCRIPTS["MATT_APPOINTMENT_REQUEST"].format(partner_name=partner_name)
                reason = f"Booking call with {partner_name} to discuss creative structures."
                tier = "🔥 Tier 1: Hot Deal (Appt Partner)"
                stage = "Appointment Pending"

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": tier,
                "stage_update": stage,
                "state_updates": state_updates
            }

        # 8. APPOINTMENT SCHEDULING & CONFIRMATION
        if curr_node in ["MATT_APPOINTMENT_REQUEST", "APPOINTMENT_CLARIFY"]:
            appt_time = extract_time_candidate(message)
            if appt_time:
                clean_time = appt_time
                if clean_time.lower().startswith("at "):
                    clean_time = clean_time[3:].strip()
                if clean_time.lower().startswith("tomorrow") or clean_time.lower().startswith("today"):
                    time_phrase = clean_time
                else:
                    time_phrase = f"at {clean_time}"

                state_updates["appointment_time"] = clean_time
                state_updates["current_node"] = "APPOINTMENT_CONFIRMED"
                base_reply = f"Sounds great! I have scheduled {partner_name} to call you {time_phrase}. We look forward to connecting and seeing if we can make a deal work together."
                reason = f"Appointment confirmed for {partner_name} ({time_phrase}). Tagged Tier 1 with Offer Pipeline entry."
                tier = "🔥 Tier 1: Appointment Booked"
                stage = "Appointment Confirmed"
            else:
                state_updates["current_node"] = "APPOINTMENT_CLARIFY"
                base_reply = SCRIPTS["MATT_APPOINTMENT_CLARIFY"].format(partner_name=partner_name)
                reason = f"Clarifying best time for {partner_name} call."
                tier = "🔥 Tier 1: Hot Deal (Appt Partner)"
                stage = "Appointment Pending"

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": tier,
                "stage_update": stage,
                "state_updates": state_updates
            }

        # 9. TIER 2 NURTURE CLOSE
        if curr_node == "TIER_2_NURTURE_ASK":
            state_updates["current_node"] = "TIER_2_NURTURE_SAVED"
            base_reply = SCRIPTS["TIER_2_NURTURE_SAVED"]
            reason = "Tier 2 agent tagged for 30-day pocket listing follow-up cadence."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "🌱 Tier 2: Pocket Lead Nurture",
                "stage_update": "Tier 2 Nurture",
                "state_updates": state_updates
            }

        # --- ON-MARKET FLOW BRANCHES ---
        if curr_node in ["ON_MARKET_CHECK_OFFERS", "ON_MARKET_TURNKEY_CHECK_OFFERS", "ON_MARKET_NEEDS_WORK_CHECK_OFFERS"]:
            is_turnkey = any(k in clean_msg for k in TURNKEY_KEYWORDS) or state_updates.get("condition") == "TURNKEY"
            is_needs_work = any(k in clean_msg for k in NEEDS_WORK_KEYWORDS) or state_updates.get("condition") == "NEEDS_WORK"
            dom = state_updates.get("dom") or 15

            if is_needs_work and not is_turnkey:
                state_updates["condition"] = "NEEDS_WORK"
                state_updates["flow_type"] = "ON_MARKET_NEEDS_WORK"
                state_updates["current_node"] = "ON_MARKET_NEEDS_WORK_NEGOTIABLE"
                base_reply = SCRIPTS["ON_MARKET_NEEDS_WORK_NEGOTIABLE"]
                reason = "Fixer listing on market. Anchoring cash discount expectation below list price."
            else:
                state_updates["condition"] = "TURNKEY"
                state_updates["flow_type"] = "ON_MARKET_TURNKEY"
                state_updates["current_node"] = "ON_MARKET_TURNKEY_DOM"
                base_reply = SCRIPTS["ON_MARKET_TURNKEY_DOM"].format(dom=dom)
                reason = f"Turnkey property on market ({dom} DOM). Asking what sellers are looking to do."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "🔥 Tier 1: In Conversation",
                "stage_update": "Warm / In Discussion",
                "state_updates": state_updates
            }

        if curr_node == "ON_MARKET_TURNKEY_DOM":
            state_updates["current_node"] = "ON_MARKET_TURNKEY_CREATIVE"
            base_reply = SCRIPTS["ON_MARKET_TURNKEY_CREATIVE"]
            reason = "Flowchart Action: Pivot to creative terms (retail price with terms)."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "🔥 Tier 1: Creative Terms",
                "stage_update": "Creative Terms Review",
                "state_updates": state_updates
            }

        if curr_node == "ON_MARKET_NEEDS_WORK_NEGOTIABLE":
            state_updates["current_node"] = "ON_MARKET_NEEDS_WORK_PHOTOS"
            base_reply = SCRIPTS["ON_MARKET_NEEDS_WORK_PHOTOS"]
            reason = "Photos acknowledged. Inquiring on seller notes before underwriting."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "🔥 Tier 1: In Conversation",
                "stage_update": "Warm / In Discussion",
                "state_updates": state_updates
            }

        if curr_node == "ON_MARKET_NEEDS_WORK_PHOTOS":
            state_updates["current_node"] = "MATT_APPOINTMENT_REQUEST"
            call_window = settings.get("call_window_hours", 3)
            base_reply = f"Awesome. I'm having my partner {partner_name} evaluate this right now. She'll give you a call within {call_window} hours to go over numbers. Would later today or tomorrow morning work better?"
            reason = f"Flowchart Action: Set appointment for {partner_name} to call within {call_window} hours."

            reply = polish_reply_with_gemini(state_updates["current_node"], base_reply, agent, message)
            state_updates["suggested_reply"] = reply
            state_updates["suggested_reply_node"] = state_updates["current_node"]
            state_updates["suggested_reply_reason"] = reason

            return {
                "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
                "reply_text": reply,
                "node": state_updates["current_node"],
                "tier_update": "🔥 Tier 1: Hot Deal (Appt Partner)",
                "stage_update": "Appointment Pending (3h Call)",
                "state_updates": state_updates
            }

        # Default Catch-all Handler
        base_reply = f"Thanks for the details! Let's get my partner {partner_name} on the phone for 5 minutes to see how we can make this work for your sellers. When are you free today or tomorrow?"
        reply = polish_reply_with_gemini("CATCH_ALL_APPT", base_reply, agent, message)

        state_updates["suggested_reply"] = reply
        state_updates["suggested_reply_node"] = "CATCH_ALL_APPT"
        state_updates["suggested_reply_reason"] = f"Catch-all handler: Routing to partner {partner_name} call."

        return {
            "action": "AUTO_SEND" if settings.get("mode") == "autopilot" else "SUGGEST",
            "reply_text": reply,
            "node": "CATCH_ALL_APPT",
            "tier_update": "🔥 Tier 1: In Conversation",
            "stage_update": "Warm / In Discussion",
            "state_updates": state_updates
        }

    # --- Underdog Model Campaign Evaluation ---

    def check_campaign_cadence(self, agent: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Determines if an agent is due for Follow-Up #1, Follow-Up #2, or Cold Call Bucket
        based on days since last contact and response status.
        """
        last_contact = agent.get("last_contact_date") or agent.get("last_outreach_date")
        if not last_contact and agent.get("outreach_history"):
            for o in agent["outreach_history"]:
                if o.get("direction") == "OUTBOUND" and o.get("timestamp"):
                    last_contact = o.get("timestamp")
                    break

        if not last_contact:
            return None

        # If agent has replied or is dead, do not send cold follow-ups
        if agent.get("last_reply_date") or "Dead" in agent.get("tier", ""):
            return None

        try:
            dt = datetime.strptime(last_contact[:19], "%Y-%m-%d %H:%M:%S")
            days_silent = (datetime.now() - dt).days
        except Exception:
            return None

        settings = load_bot_settings()
        fu1_days = settings.get("campaign_followup_1_days", 3)
        fu2_days = settings.get("campaign_followup_2_days", 7)
        cc_days = settings.get("campaign_coldcall_days", 14)

        parts = agent.get("full_name", "").split()
        first_name = agent.get("first_name") or (parts[0] if parts else "") or "there"
        addr = agent.get("primary_address", "the listing")
        city = agent.get("primary_city", "Florida")
        county = agent.get("county", "Florida")

        if days_silent >= cc_days:
            return {
                "eligible": True,
                "campaign_step": "COLD_CALL_BUCKET",
                "tier": "📞 Cold Call Bucket",
                "days_since_outreach": days_silent,
                "days_silent": days_silent,
                "suggested_template": "",
                "message": "",
                "requires_call": True
            }
        elif days_silent >= fu2_days and agent.get("pipeline_stage") != "Follow-Up #2 Sent":
            msg = SCRIPTS["FOLLOWUP_2"].format(first_name=first_name, address=addr, county=county)
            return {
                "eligible": True,
                "campaign_step": "FOLLOW_UP_2",
                "tier": "🟡 Follow-Up #2 Due",
                "days_since_outreach": days_silent,
                "days_silent": days_silent,
                "suggested_template": msg,
                "message": msg,
                "requires_call": False
            }
        elif days_silent >= fu1_days and agent.get("pipeline_stage") not in ["Follow-Up #1 Sent", "Follow-Up #2 Sent"]:
            msg = SCRIPTS["FOLLOWUP_1"].format(first_name=first_name, address=addr, city=city)
            return {
                "eligible": True,
                "campaign_step": "FOLLOW_UP_1",
                "tier": "🟡 Follow-Up #1 Due",
                "days_since_outreach": days_silent,
                "days_silent": days_silent,
                "suggested_template": msg,
                "message": msg,
                "requires_call": False
            }

        return None


bot_engine = BotEngine()
