import os
import re
import json
import time
import shutil
from typing import Dict, List, Any, Optional
from pydantic import BaseModel

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from contextlib import asynccontextmanager

from src.storage import data_manager
from src.deal_calculator import calculate_buy_box, generate_setup_call_hud
from src.sms_gateway import load_sms_settings, save_sms_settings, send_sms, test_sms_connection
from src.email_sender import load_email_settings, save_email_settings, send_email, test_smtp_connection
from src.pandadoc_client import (
    load_pandadoc_settings, save_pandadoc_settings, 
    generate_loi_html, generate_farbar_html, generate_contract_pdf_bytes, 
    dispatch_pandadoc_contract, test_pandadoc_connection
)
from src.bot_engine import (
    load_bot_settings, save_bot_settings, bot_engine,
    test_gemini_connection, load_golden_replies, save_golden_reply,
    delete_golden_reply, STANDARD_TRAINING_SCENARIOS, polish_reply_with_gemini
)
from src.scheduler import cadence_scheduler
from src.drip_engine import drip_engine
from src.lauren_engine import (
    load_fixers, save_fixers, calculate_trojan_horse_mao,
    lauren_engine
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    start_cloudflare_tunnel_proxy()
    cadence_scheduler.start()
    yield
    cadence_scheduler.stop()

app = FastAPI(title="Agent Deal Hunter", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "data")

# --- Request Models ---
class UpdateStatusRequest(BaseModel):
    pipeline_stage: Optional[str] = None
    notes: Optional[str] = None
    custom_phone: Optional[str] = None
    custom_email: Optional[str] = None

class EditAgentRequest(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    brokerage: Optional[str] = None
    pipeline_stage: Optional[str] = None
    notes: Optional[str] = None
    primary_address: Optional[str] = None
    primary_city: Optional[str] = None
    primary_price: Optional[float] = None

class CreateAgentRequest(BaseModel):
    full_name: str
    phone: str
    email: str
    brokerage: str = "Florida Test Realty"
    county: str = "BREVARD"
    address: str = "123 Sandbox Way"
    city: str = "Melbourne"
    listing_price: float = 275000.0
    beds: int = 3
    baths: float = 2.0
    sqft: int = 1600
    year_built: int = 1995
    days_on_market: int = 14
    notes: str = "Sandbox test agent"

class TestSmsRequest(BaseModel):
    phone: str
    message: Optional[str] = "Test SMS from Agent Deal Hunter Android Gateway"

class SimulateInboundRequest(BaseModel):
    phone: str
    message: str

class TestEmailRequest(BaseModel):
    recipient_email: str
    subject: Optional[str] = "SMTP2GO Relay Test - Agent Deal Hunter"
    message: Optional[str] = "This is a live test email verifying your SMTP2GO configuration with Agent Deal Hunter."

class TestPandadocRequest(BaseModel):
    mode: Optional[str] = None
    key: Optional[str] = None

class PocketDealRequest(BaseModel):
    address: str
    city: str
    condition_notes: str = ""
    occupancy: str = "Vacant"
    asking_price: float = 0.0
    timeline: str = "ASAP"
    target_offer: float = 0.0
    notes: str = ""

class CalculateDealRequest(BaseModel):
    agent_name: str
    property_address: str
    listing_price: float = 0.0
    estimated_value: float = 0.0
    sqft: int = 1500
    year_built: int = 1980
    condition: str = "average"
    occupancy: str = "Vacant"
    timeline: str = "ASAP"

class SendSmsRequest(BaseModel):
    agent_id: str
    phone: str
    message: str
    metadata: Optional[Dict[str, Any]] = None

class SendEmailRequest(BaseModel):
    agent_id: str
    recipient_email: str
    subject: str
    html_content: str
    metadata: Optional[Dict[str, Any]] = None

class IngestFixerRequest(BaseModel):
    address: str
    city: Optional[str] = "Melbourne"
    county: Optional[str] = "BREVARD"
    zip: Optional[str] = ""
    list_price: Optional[float] = 0.0
    redfin_estimate: Optional[float] = 0.0
    zestimate: Optional[float] = 0.0
    dom: Optional[int] = 1
    sqft: Optional[float] = 1200.0
    beds: Optional[str] = ""
    baths: Optional[str] = ""
    year_built: Optional[str] = ""
    photo_url: Optional[str] = ""
    redfin_url: Optional[str] = ""
    remarks: Optional[str] = ""
    agent_name: Optional[str] = "Listing Agent"
    agent_phone: Optional[str] = ""
    agent_email: Optional[str] = ""
    brokerage: Optional[str] = ""

class IngestBulkFixersRequest(BaseModel):
    listings: List[Dict[str, Any]]

class CalculateFixerMaoRequest(BaseModel):
    arv: float
    sqft: float
    rehab_per_sqft: Optional[float] = 40.0
    high_ticket_total: Optional[float] = 0.0
    closing_cost_pct: Optional[float] = 0.02
    carrying_cost_pct: Optional[float] = 0.02
    commission_pct: Optional[float] = 0.05
    flipper_profit_pct: Optional[float] = 0.15
    wholesale_fee: Optional[float] = 0.0

class FixerInboundRequest(BaseModel):
    message: str

class SendFixerSmsRequest(BaseModel):
    message: Optional[str] = None

class UpdateFixerPhoneRequest(BaseModel):
    phone: str

class ApproveBotRequest(BaseModel):
    agent_id: str
    custom_message: Optional[str] = None
    approved_text: Optional[str] = None

class TestGeminiRequest(BaseModel):
    api_key: str
    model: Optional[str] = "gemini-3.5-flash-lite"

class TestGenerateRequest(BaseModel):
    node: str
    inbound_message: str
    template_reply: str

class SetTierRequest(BaseModel):
    agent_id: str
    tier: str

class SendFollowupRequest(BaseModel):
    agent_id: str

class ContractPayload(BaseModel):
    agent_id: str = ""
    contract_type: str = "farbar"  # "farbar" or "loi"
    mode: Optional[str] = None
    property_address: str
    city: str = ""
    zip: str = ""
    county: str = "FL"
    apn: str = ""
    legal_description: str = ""
    seller_name: str = "Property Owner of Record"
    buyer_name: str = "Peak Investments LLC"
    buyer_signer_name: str = "Johnathan Roberts"
    recipient_email: str
    agent_name: str = ""
    brokerage_name: str = ""
    purchase_price: float = 0.0
    escrow_deposit: float = 2500.0
    inspection_days: int = 7
    closing_days: int = 14
    title_company: str = "Title Insights"

class StartDripRequest(BaseModel):
    desk: Optional[str] = "BROOKE"  # "BROOKE", "LAUREN", "ALL"
    min_delay: Optional[int] = 60
    max_delay: Optional[int] = 120
    county: Optional[str] = None
    limit: Optional[int] = None

# --- API Endpoints ---

@app.get("/api/stats")
def get_stats():
    agents = data_manager.get_all_agents()
    total_listings = sum(a["listing_count"] for a in agents)
    total_volume = sum(a["total_volume"] for a in agents)
    whales = sum(1 for a in agents if "Whale" in a.get("tier", ""))
    awaiting_reply = sum(1 for a in agents if a.get("pipeline_stage") == "Contacted")
    in_discussion = sum(1 for a in agents if a.get("pipeline_stage") in ["Warm / In Discussion", "Pocket Deal Review"])
    contracts_out = sum(1 for a in agents if a.get("pipeline_stage") == "Contract Sent")
    cadence_due_count = sum(1 for a in agents if a.get("cadence_due"))
    stale_dom_count = sum(1 for a in agents if a.get("is_stale_dom"))
    unread_replies_count = sum(a.get("unread_replies", 0) for a in agents)
    counties = data_manager.get_counties()

    bot_summary = data_manager.get_bot_pipeline_summary()

    resp = {
        "total_agents": len(agents),
        "total_listings": total_listings,
        "total_volume": round(total_volume, 2),
        "whales": whales,
        "awaiting_reply": awaiting_reply,
        "in_discussion": in_discussion,
        "contracts_out": contracts_out,
        "cadence_due_count": cadence_due_count,
        "stale_dom_count": stale_dom_count,
        "unread_replies_count": unread_replies_count,
        "counties_count": len(counties)
    }
    resp.update(bot_summary)
    return resp

@app.post("/api/sms/inbound")
@app.post("/api/webhooks/android-sms-gateway")
async def handle_inbound_sms_webhook(request: Request):
    """
    Webhook endpoint for Android SMS Gateway to forward incoming SMS messages.
    Supports both nested event format (capcom6/android-sms-gateway) and flat JSON.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}

    phone = (
        body.get("phoneNumber") or body.get("phone") or body.get("sender") or
        payload.get("phoneNumber") or payload.get("phone") or payload.get("sender") or ""
    )

    message = (
        body.get("message") or body.get("text") or body.get("body") or
        payload.get("message") or payload.get("text") or payload.get("body") or ""
    )

    event_type = body.get("event", "")
    # If it's a delivery or send status event, ignore gracefully
    if event_type and event_type not in ("sms:received", "mms:downloaded", ""):
        return {"status": "ignored", "reason": f"Event {event_type} ignored"}

    if not phone or not message:
        return {"status": "ignored", "reason": "No phone or text detected in webhook"}

    # 1. Log to global inbox
    entry = data_manager.record_inbound_sms(phone=phone, message=message, raw_payload=body)

    # 2. Check if sender matches one of Lauren's Redfin fixers
    clean_in_phone = re.sub(r"\D", "", phone)[-10:]
    if clean_in_phone:
        try:
            fixers = load_fixers()
            matched_fixer = None
            for f in fixers:
                f_phone = re.sub(r"\D", "", f.get("agent_phone") or "")[-10:]
                if f_phone and f_phone == clean_in_phone:
                    matched_fixer = f
                    break

            if matched_fixer:
                matched_fixer.setdefault("messages", []).append({
                    "direction": "INBOUND",
                    "sender": matched_fixer.get("agent_name", "Agent"),
                    "text": message,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                })
                matched_fixer["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
                eval_res = lauren_engine.evaluate_inbound(matched_fixer, message)
                if eval_res and eval_res.get("reply_text"):
                    matched_fixer["suggested_reply"] = eval_res.get("reply_text")
                save_fixers(fixers)
        except Exception as e:
            print(f"[Lauren Inbound Router Error] {e}")

    return {"status": "success", "entry": entry}

@app.get("/api/inbox")
def get_inbox_messages():
    inbound = data_manager.get_outreach_history(direction="INBOUND")
    unread = sum(a.get("unread_replies", 0) for a in data_manager.get_all_agents())
    fixers = load_fixers()
    enriched = []
    for m in inbound:
        item = dict(m)
        aid = m.get("agent_id")
        if aid:
            ag = data_manager.get_agent(aid)
            if ag:
                item["last_bot_suggestion"] = ag.get("last_bot_suggestion") or ""
                item["last_bot_node"] = ag.get("last_bot_node") or ""
                item["is_gold_deal"] = ag.get("is_gold_deal") or False
                item["tier"] = ag.get("tier") or ""

        # Check if matched to Lauren fixer
        sender_clean = re.sub(r"\D", "", m.get("sender_phone") or "")[-10:]
        if sender_clean:
            for f in fixers:
                f_ph = re.sub(r"\D", "", f.get("agent_phone") or "")[-10:]
                if f_ph and f_ph == sender_clean:
                    item["is_fixer"] = True
                    item["fixer_address"] = f.get("address", "")
                    item["last_bot_suggestion"] = f.get("suggested_reply", "")
                    item["last_bot_node"] = f.get("current_node", "")
                    break

        enriched.append(item)
    return {
        "messages": enriched,
        "unread_count": unread
    }

@app.post("/api/inbox/read/{agent_id}")
def mark_inbox_read_endpoint(agent_id: str):
    data_manager.mark_inbox_read(agent_id)
    return {"status": "success"}

class DeleteInboxPayload(BaseModel):
    id: Optional[str] = None
    timestamp: Optional[str] = None
    sender_phone: Optional[str] = None
    message: Optional[str] = None

@app.post("/api/inbox/delete")
def delete_inbox_message_endpoint(payload: DeleteInboxPayload):
    deleted = data_manager.delete_outreach_message(
        message_id=payload.id,
        timestamp=payload.timestamp,
        sender_phone=payload.sender_phone,
        message_text=payload.message
    )
    if deleted:
        return {"status": "success", "message": "Message deleted successfully"}
    return {"status": "error", "message": "Message not found"}

@app.post("/api/inbox/clear-spam")
def clear_inbox_spam_endpoint():
    count = data_manager.clear_spam_inbound()
    return {"status": "success", "deleted_count": count, "message": f"Successfully deleted {count} spam/unmatched message{'s' if count != 1 else ''}"}

@app.post("/api/agent/{agent_id}/reset-history")
def reset_agent_history_endpoint(agent_id: str):
    data_manager.reset_agent_history(agent_id)
    return {"status": "success", "message": "History and state reset successfully"}

@app.post("/api/agent/{agent_id}/toggle-autopilot")
def toggle_agent_autopilot_endpoint(agent_id: str):
    agent = data_manager.get_agent(agent_id)
    if not agent:
        return {"status": "error", "message": "Agent not found"}
    new_val = not agent.get("test_autopilot", False)
    data_manager.update_agent_state(agent_id, {"test_autopilot": new_val})
    return {"status": "success", "test_autopilot": new_val}

@app.get("/api/counties")
def get_counties():
    return data_manager.get_counties()

@app.get("/api/agents")
def get_agents(county: Optional[str] = "ALL", stage: Optional[str] = "ALL", 
               tier: Optional[str] = "ALL", search: Optional[str] = None):
    return data_manager.get_all_agents(county=county, stage=stage, tier=tier, search=search)

@app.get("/api/agent/{agent_id}")
def get_agent(agent_id: str):
    agent = data_manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    outreach = data_manager.get_outreach_history(agent_id)
    return {
        "agent": agent,
        "outreach": outreach
    }

@app.post("/api/agent/{agent_id}/status")
def update_agent_status(agent_id: str, req: UpdateStatusRequest):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    updated = data_manager.update_agent_state(agent_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "success", "agent": updated}

@app.post("/api/agent/{agent_id}/edit")
def edit_agent_endpoint(agent_id: str, req: EditAgentRequest):
    updates = {k: v for k, v in req.dict().items() if v is not None}
    updated = data_manager.edit_agent(agent_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "success", "agent": updated}

@app.post("/api/agent/create")
def create_agent_endpoint(req: CreateAgentRequest):
    new_agent = data_manager.create_custom_agent(req.dict())
    return {"status": "success", "agent": new_agent}

@app.delete("/api/agent/{agent_id}")
def delete_agent_endpoint(agent_id: str):
    success = data_manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "success", "message": f"Agent {agent_id} deleted."}

@app.post("/api/agent/{agent_id}/pocket-deal")
def add_pocket_deal(agent_id: str, req: PocketDealRequest):
    deal_entry = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "address": req.address,
        "city": req.city,
        "condition_notes": req.condition_notes,
        "occupancy": req.occupancy,
        "asking_price": req.asking_price,
        "timeline": req.timeline,
        "target_offer": req.target_offer,
        "notes": req.notes,
        "status": "Under Review"
    }
    data_manager.add_pocket_deal(agent_id, deal_entry)
    return {"status": "success", "deal": deal_entry}

@app.post("/api/deal/calculate")
def calculate_deal(req: CalculateDealRequest):
    buy_box = calculate_buy_box(
        listing_price=req.listing_price,
        estimated_value=req.estimated_value,
        sqft=req.sqft,
        year_built=req.year_built,
        condition=req.condition
    )
    hud = generate_setup_call_hud(
        agent_name=req.agent_name,
        property_address=req.property_address,
        asking_price=req.listing_price,
        buy_box=buy_box,
        condition_notes=req.condition,
        occupancy=req.occupancy,
        timeline=req.timeline
    )
    return {
        "buy_box": buy_box,
        "hud": hud
    }

# --- SMS Gateway Endpoints ---
@app.get("/api/sms/settings")
def get_sms_cfg():
    return load_sms_settings()

@app.post("/api/sms/settings")
def set_sms_cfg(settings: Dict[str, Any]):
    save_sms_settings(settings)
    return {"status": "success", "settings": settings}

@app.post("/api/sms/test")
def test_sms_cfg():
    return test_sms_connection()

@app.post("/api/sms/test-send")
def test_send_sms_endpoint(req: TestSmsRequest):
    return send_sms(phone=req.phone, message=req.message or "Test SMS from Agent Deal Hunter Android Gateway", agent_id="test_outbound")

@app.post("/api/sms/simulate-inbound")
def simulate_inbound_sms(req: SimulateInboundRequest):
    result = data_manager.record_inbound_sms(phone=req.phone, message=req.message, raw_payload={"simulated": True})
    agent = data_manager.find_agent_by_phone(req.phone)
    return {
        "status": "success",
        "message": f"Inbound SMS simulated from {req.phone}!",
        "matched": bool(agent),
        "agent": agent,
        "log": result.get("log"),
        "bot_result": result.get("bot_result")
    }

@app.post("/api/sms/send")
def send_sms_endpoint(req: SendSmsRequest):
    return send_sms(phone=req.phone, message=req.message, agent_id=req.agent_id, metadata=req.metadata)

# --- Bot & Underdog Model Endpoints ---
@app.get("/api/bot/settings")
def get_bot_cfg():
    return load_bot_settings()

@app.post("/api/bot/settings")
def set_bot_cfg(settings: Dict[str, Any]):
    save_bot_settings(settings)
    return {"status": "success", "settings": load_bot_settings()}

@app.get("/api/bot/summary")
def get_bot_summary_endpoint():
    return data_manager.get_bot_pipeline_summary()

@app.post("/api/bot/approve")
def approve_bot_suggestion_endpoint(req: ApproveBotRequest):
    approved_text = req.approved_text or req.custom_message
    return data_manager.approve_bot_suggestion(req.agent_id, approved_text)

@app.post("/api/bot/test-gemini")
def test_gemini_endpoint(req: TestGeminiRequest):
    return test_gemini_connection(req.api_key, req.model or "gemini-3.5-flash-lite")

@app.get("/api/bot/training")
def get_training_replies_endpoint():
    goldens = load_golden_replies()
    return {
        "count": len(goldens),
        "examples": goldens
    }

@app.post("/api/bot/training/add")
def add_training_reply_endpoint(entry: Dict[str, Any]):
    save_golden_reply(entry)
    return {"status": "success", "count": len(load_golden_replies())}

@app.get("/api/bot/training/scenarios")
def get_training_scenarios_endpoint():
    return {
        "scenarios": STANDARD_TRAINING_SCENARIOS
    }

@app.delete("/api/bot/training/{example_id}")
def delete_training_reply_endpoint(example_id: str):
    success = delete_golden_reply(example_id)
    return {"status": "success" if success else "error", "count": len(load_golden_replies())}

@app.post("/api/bot/training/test-generation")
def test_generation_endpoint(req: TestGenerateRequest):
    mock_agent = {"full_name": "Test Realtor", "first_name": "Realtor"}
    enhanced = polish_reply_with_gemini(req.node, req.template_reply, mock_agent, req.inbound_message)
    return {
        "status": "success",
        "node": req.node,
        "input": req.inbound_message,
        "base_script": req.template_reply,
        "generated_reply": enhanced
    }

@app.post("/api/bot/set-tier")
def set_agent_tier_endpoint(req: SetTierRequest):
    updated = data_manager.set_agent_tier(req.agent_id, req.tier)
    if not updated:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"status": "success", "agent": updated}

@app.get("/api/campaigns/due")
def get_due_campaigns_endpoint():
    return data_manager.get_due_campaigns()

@app.post("/api/campaigns/send-followup")
def send_campaign_followup_endpoint(req: SendFollowupRequest):
    return data_manager.send_campaign_followup(req.agent_id)

# --- Automated Cadence Scheduler Endpoints ---
@app.get("/api/scheduler/status")
def get_scheduler_status_endpoint():
    return cadence_scheduler.get_status()

@app.post("/api/scheduler/run-now")
def run_scheduler_now_endpoint():
    return cadence_scheduler.trigger_run_now()

@app.post("/api/scheduler/toggle")
def toggle_scheduler_endpoint(req: Dict[str, Any]):
    enabled = req.get("enabled", True)
    settings = load_bot_settings()
    settings["auto_cadence_followup_enabled"] = enabled
    save_bot_settings(settings)
    return {"status": "success", "enabled": enabled}

# --- Auto-Drip Outbound Queue Endpoints (Load & Go) ---
@app.post("/api/drip/start")
def start_drip_endpoint(req: StartDripRequest):
    return drip_engine.start_drip(
        desk=req.desk or "BROOKE",
        min_delay=req.min_delay or 60,
        max_delay=req.max_delay or 120,
        county=req.county,
        limit=req.limit
    )

@app.post("/api/drip/pause")
def pause_drip_endpoint():
    return drip_engine.pause_drip()

@app.post("/api/drip/stop")
def stop_drip_endpoint():
    return drip_engine.stop_drip()

@app.get("/api/drip/status")
def get_drip_status_endpoint():
    return drip_engine.get_status()

@app.get("/api/drip/log")
def get_drip_log_endpoint():
    from src.storage import load_json
    log_file = os.path.join(DATA_DIR, "drip_queue_log.json")
    return load_json(log_file, [])

# --- SMTP2GO Email Endpoints ---
@app.get("/api/email/settings")
def get_email_cfg():
    return load_email_settings()

@app.post("/api/email/settings")
def set_email_cfg(settings: Dict[str, Any]):
    save_email_settings(settings)
    return {"status": "success", "settings": settings}

@app.post("/api/email/test")
def test_email_cfg():
    return test_smtp_connection()

@app.post("/api/email/test-send")
def test_send_email_endpoint(req: TestEmailRequest):
    html = f"""
    <div style="font-family: Arial, sans-serif; padding: 20px; color: #1e293b; max-width: 600px; border: 1px solid #e2e8f0; border-radius: 12px;">
        <h2 style="color: #4f46e5; margin-top: 0;">✓ SMTP2GO Relay Working</h2>
        <p>This is a live test message dispatched from <strong>Agent Deal Hunter</strong>.</p>
        <div style="background: #f8fafc; padding: 14px; border-radius: 8px; border-left: 4px solid #4f46e5; margin: 16px 0;">
            <p style="margin: 0; font-size: 14px; color: #334155;"><strong>Message:</strong> {req.message}</p>
        </div>
        <p style="font-size: 11px; color: #64748b; margin-bottom: 0;">Dispatched via SMTP2GO at {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    """
    return send_email(
        recipient_email=req.recipient_email,
        subject=req.subject or "SMTP2GO Relay Test - Agent Deal Hunter",
        html_body=html,
        agent_id="test_email"
    )

@app.post("/api/email/send")
def send_email_endpoint(req: SendEmailRequest):
    return send_email(
        recipient_email=req.recipient_email,
        subject=req.subject,
        html_body=req.html_content,
        agent_id=req.agent_id,
        metadata=req.metadata
    )

# --- PandaDoc Endpoints ---
@app.get("/api/pandadoc/settings")
def get_pandadoc_cfg():
    return load_pandadoc_settings()

@app.post("/api/pandadoc/settings")
def set_pandadoc_cfg(settings: Dict[str, Any]):
    save_pandadoc_settings(settings)
    return {"status": "success", "settings": settings}

@app.post("/api/pandadoc/test")
def test_pandadoc_cfg(req: Optional[TestPandadocRequest] = None):
    mode = req.mode if req else None
    key = req.key if req else None
    return test_pandadoc_connection(mode_override=mode, key_override=key)

@app.post("/api/contract/pdf")
async def download_contract_pdf(payload: ContractPayload):
    try:
        if payload.contract_type == "loi":
            html = generate_loi_html(payload.dict(), for_pandadoc=False)
            filename = f"LOI_{re.sub(r'[^a-zA-Z0-9_-]', '_', payload.property_address)}.pdf"
            pdf_bytes = await generate_contract_pdf_bytes(html)
        else:
            from src.farbar_filler import fill_official_farbar_pdf
            filename = f"FARBAR_ASIS_{re.sub(r'[^a-zA-Z0-9_-]', '_', payload.property_address)}.pdf"
            pdf_bytes = fill_official_farbar_pdf(payload.dict())

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        import traceback
        print(f"[ERROR] /api/contract/pdf failed: {repr(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF rendering failed: {repr(e)}")

@app.post("/api/contract/pandadoc/send")
async def send_pandadoc_contract_endpoint(payload: ContractPayload):
    if payload.contract_type == "loi":
        return {
            "status": "error",
            "message": "LOIs do not require PandaDoc. Please dispatch your LOI directly to the agent via Cellular SMS or Email."
        }
    return await dispatch_pandadoc_contract(payload.dict(), contract_type=payload.contract_type)

@app.get("/api/outreach/history")
def get_outreach_log():
    return data_manager.get_outreach_history()

@app.post("/api/upload-csv")
async def upload_csv_file(file: UploadFile = File(...)):
    if not file.filename.endswith(".csv"):
        return {"status": "error", "message": "Only CSV files are supported"}
    dest_path = os.path.join(DATA_DIR, file.filename)
    with open(dest_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    data_manager.refresh()
    total_agents = len(data_manager.get_all_agents())
    return {
        "status": "success", 
        "message": f"Successfully loaded and enriched {file.filename}! Pipeline now has {total_agents} active agents ready for outreach.",
        "total_agents": total_agents
    }

# --- Lauren's On-Market Fixer Desk Endpoints ---

@app.get("/api/fixers")
def get_fixers_endpoint():
    return load_fixers()

@app.post("/api/fixers/ingest")
def ingest_fixer_endpoint(req: IngestFixerRequest):
    fixers = load_fixers()
    fixer_state = lauren_engine.get_initial_fixer_state(req.dict())
    opening_hook = lauren_engine.generate_opening_hook(fixer_state)
    fixer_state["opening_hook"] = opening_hook
    fixer_state["suggested_reply"] = opening_hook
    
    # Prepend or update existing
    fixers = [f for f in fixers if f.get("address", "").lower() != req.address.lower()]
    fixers.insert(0, fixer_state)
    save_fixers(fixers)
    return {"status": "success", "fixer": fixer_state, "count": len(fixers)}

@app.post("/api/fixers/ingest-bulk")
def ingest_bulk_fixers_endpoint(req: IngestBulkFixersRequest):
    fixers = load_fixers()
    existing_addrs = {f.get("address", "").lower() for f in fixers}
    added_count = 0

    for item in req.listings:
        addr = (item.get("address") or "").strip()
        if not addr:
            continue
        fixer_state = lauren_engine.get_initial_fixer_state(item)
        opening_hook = lauren_engine.generate_opening_hook(fixer_state)
        fixer_state["opening_hook"] = opening_hook
        fixer_state["suggested_reply"] = opening_hook

        if addr.lower() in existing_addrs:
            fixers = [f if f.get("address", "").lower() != addr.lower() else fixer_state for f in fixers]
        else:
            fixers.insert(0, fixer_state)
            existing_addrs.add(addr.lower())
            added_count += 1

    save_fixers(fixers)
    data_manager.refresh()
    return {
        "status": "success",
        "message": f"Successfully ingested {len(req.listings)} fixer listings into Lauren's Desk!",
        "total_fixers": len(fixers),
        "newly_added": added_count
    }

@app.post("/api/fixers/calculate-mao")
def calculate_fixer_mao_endpoint(req: CalculateFixerMaoRequest):
    return calculate_trojan_horse_mao(
        arv=req.arv,
        sqft=req.sqft,
        rehab_per_sqft=req.rehab_per_sqft or 40.0,
        high_ticket_total=req.high_ticket_total or 0.0,
        closing_cost_pct=req.closing_cost_pct or 0.02,
        carrying_cost_pct=req.carrying_cost_pct or 0.02,
        commission_pct=req.commission_pct or 0.05,
        flipper_profit_pct=req.flipper_profit_pct or 0.15,
        wholesale_fee=req.wholesale_fee or 0.0
    )

@app.post("/api/fixers/{fixer_id}/send-sms")
def send_fixer_sms_endpoint(fixer_id: str, req: SendFixerSmsRequest):
    fixers = load_fixers()
    fixer = next((f for f in fixers if f.get("id") == fixer_id), None)
    if not fixer:
        raise HTTPException(status_code=404, detail="Fixer listing not found")
    phone = fixer.get("agent_phone")
    if not phone:
        return {"status": "error", "message": "No phone number available for listing agent"}
    
    msg = req.message or fixer.get("suggested_reply") or fixer.get("opening_hook")
    res = send_sms(phone=phone, message=msg, agent_id=fixer_id)
    
    if "messages" not in fixer: fixer["messages"] = []
    fixer["messages"].append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "OUTBOUND",
        "sender": "Lauren",
        "text": msg
    })
    fixer["status"] = "OUTREACH_SENT"
    fixer["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_fixers(fixers)
    return {"status": "success", "res": res, "fixer": fixer}

@app.post("/api/fixers/{fixer_id}/spin-hook")
def spin_fixer_hook_endpoint(fixer_id: str):
    fixers = load_fixers()
    fixer = next((f for f in fixers if f.get("id") == fixer_id), None)
    if not fixer:
        raise HTTPException(status_code=404, detail="Fixer listing not found")
    new_hook = lauren_engine.generate_opening_hook(fixer)
    fixer["opening_hook"] = new_hook
    outbound_count = len([m for m in fixer.get("messages", []) if m.get("direction") == "OUTBOUND"])
    if outbound_count == 0 or fixer.get("current_node") == "OPENING_HOOK":
        fixer["suggested_reply"] = new_hook
    save_fixers(fixers)
    return {"status": "success", "opening_hook": new_hook, "suggested_reply": fixer.get("suggested_reply")}

@app.post("/api/fixers/{fixer_id}/inbound")
def evaluate_fixer_inbound_endpoint(fixer_id: str, req: FixerInboundRequest):
    fixers = load_fixers()
    fixer = next((f for f in fixers if f.get("id") == fixer_id), None)
    if not fixer:
        raise HTTPException(status_code=404, detail="Fixer listing not found")
    
    if "messages" not in fixer: fixer["messages"] = []
    fixer["messages"].append({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "direction": "INBOUND",
        "sender": fixer.get("agent_name", "Agent"),
        "text": req.message
    })
    
    eval_res = lauren_engine.evaluate_inbound(fixer, req.message)
    fixer["suggested_reply"] = eval_res.get("reply_text")
    fixer["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_fixers(fixers)
    return {"status": "success", "eval": eval_res, "fixer": fixer}

@app.post("/api/fixers/{fixer_id}/send-standing-loi")
def send_fixer_standing_loi_endpoint(fixer_id: str):
    fixers = load_fixers()
    fixer = next((f for f in fixers if f.get("id") == fixer_id), None)
    if not fixer:
        raise HTTPException(status_code=404, detail="Fixer listing not found")
    
    agent_email = fixer.get("agent_email")
    agent_name = fixer.get("agent_name", "Agent")
    addr = fixer.get("address", "Property")
    offer_val = fixer.get("underwriting", {}).get("offer_price") or 105000.0
    
    email_res = {"status": "skipped", "message": "No email on file"}
    if agent_email:
        subject = f"Official Cash Offer & Standing LOI: {addr} (Johnathan Roberts / 407 Flips)"
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 0 auto; color: #1e293b; line-height: 1.6;">
            <div style="background-color: #0f172a; padding: 20px; border-radius: 12px 12px 0 0; color: #ffffff;">
                <h2 style="margin: 0; font-size: 20px; color: #f59e0b;">407 FLIPS &bull; STANDING CASH OFFER &amp; LOI</h2>
                <p style="margin: 4px 0 0 0; font-size: 13px; color: #94a3b8;">Property: {addr}</p>
            </div>
            <div style="padding: 24px; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 12px 12px; background: #ffffff;">
                <p>Hi {agent_name},</p>
                <p>Thank you for connecting with Lauren on our acquisitions team. While we understand there is currently a pricing gap on <strong>{addr}</strong>, we would like to present this <strong>Official Standing Cash Offer</strong> for your records and your seller's consideration.</p>
                
                <div style="background: #f8fafc; border-left: 4px solid #10b981; padding: 16px; margin: 20px 0; border-radius: 4px;">
                    <p style="margin: 0; font-size: 13px; color: #64748b;">PURCHASE PRICE (NET CASH TO SELLER):</p>
                    <p style="margin: 4px 0; font-size: 26px; font-weight: bold; color: #0f172a;">${offer_val:,.0f} USD</p>
                    <p style="margin: 4px 0 0 0; font-size: 12px; color: #10b981; font-weight: bold;">&bull; Zero Inspection Contingencies &bull; 14-Day Fast Close &bull; All Cash Funds Verified</p>
                </div>
                
                <h4 style="color: #0f172a; margin-top: 20px;">Key Terms &amp; Commission Protection:</h4>
                <ul style="padding-left: 20px; font-size: 13px; color: #334155;">
                    <li><strong>Buyer Entity:</strong> Peak Investments LLC and/or Assigns (Johnathan Roberts)</li>
                    <li><strong>Earnest Money Deposit (EMD):</strong> $2,500 deposited with Florida Title/Escrow within 3 days.</li>
                    <li><strong>Listing Brokerage Commission:</strong> <strong>Full listing commission preserved and protected (Page 12 FAR/BAR compliant).</strong></li>
                    <li><strong>Closing Date:</strong> On or before 14 days from mutual contract execution.</li>
                    <li><strong>Standing Term:</strong> This offer remains open and valid for <strong>30 days</strong>. If the seller's timeline or circumstances change, or if a retail buyer's contract falls through, we are ready to execute immediately.</li>
                </ul>
                <p style="font-size: 13px; color: #64748b; margin-top: 24px;">Sincerely,<br><strong>Lauren &amp; Johnathan Roberts</strong><br>407 Flips / Peak Investments LLC<br>Direct: (407) 815-5043 | Email: john@407flips.com</p>
            </div>
        </div>
        """
        email_res = send_email(recipient_email=agent_email, subject=subject, html_body=html, agent_id=fixer_id)

    phone = fixer.get("agent_phone")
    sms_res = {"status": "skipped", "message": "No phone"}
    if phone:
        agent_first = agent_name.split()[0]
        sms_text = (
            f"Hey {agent_first}, Lauren with 407 Flips! I just emailed over our official written standing cash offer (${offer_val:,.0f}) "
            f"for {addr} with full commission protected. If the seller's timeline changes or another deal falls through, our offer stands!"
        )
        sms_res = send_sms(phone=phone, message=sms_text, agent_id=fixer_id)
        if "messages" not in fixer: fixer["messages"] = []
        fixer["messages"].append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "direction": "OUTBOUND",
            "sender": "Lauren",
            "text": sms_text
        })

    fixer["standing_loi_sent"] = True
    fixer["status"] = "STANDING_LOI_SENT"
    fixer["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_fixers(fixers)
    return {"status": "success", "email_res": email_res, "sms_res": sms_res, "fixer": fixer}

@app.post("/api/fixers/{fixer_id}/reset-flow")
def reset_fixer_flow_endpoint(fixer_id: str):
    fixers = load_fixers()
    fixer = next((f for f in fixers if f.get("id") == fixer_id), None)
    if not fixer:
        raise HTTPException(status_code=404, detail="Fixer listing not found")
    fixer["current_node"] = "OPENING_HOOK"
    fixer["agent_repair_estimate"] = None
    fixer["agent_arv_estimate"] = None
    fixer["standing_loi_sent"] = False
    fixer["status"] = "NEW"
    fixer["suggested_reply"] = fixer.get("opening_hook")
    fixer["messages"] = []
    save_fixers(fixers)
    return {"status": "success", "fixer": fixer}

@app.delete("/api/fixers/{fixer_id}")
def delete_fixer_endpoint(fixer_id: str):
    fixers = load_fixers()
    initial_len = len(fixers)
    fixers = [f for f in fixers if f.get("id") != fixer_id]
    if len(fixers) == initial_len:
        raise HTTPException(status_code=404, detail="Fixer not found")
    save_fixers(fixers)
    return {"status": "success", "message": f"Fixer {fixer_id} removed"}

# Mount static frontend
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

def start_cloudflare_tunnel_proxy():
    """
    Runs a lightweight HTTP forwarder on port 8765 to receive traffic from Cloudflared
    (which routes realtor.407rescreen.com -> 127.0.0.1:8765) and proxy it to port 8001.
    """
    import http.server
    import urllib.request
    import threading

    class TunnelProxyHandler(http.server.BaseHTTPRequestHandler):
        def forward(self, method):
            length = int(self.headers.get('Content-Length', 0))
            data = self.rfile.read(length) if length > 0 else None
            headers = {k: v for k, v in self.headers.items() if k.lower() not in ('host', 'content-length')}
            headers['Host'] = '127.0.0.1:8001'
            try:
                req = urllib.request.Request('http://127.0.0.1:8001' + self.path, data=data, headers=headers, method=method)
                with urllib.request.urlopen(req, timeout=15) as resp:
                    self.send_response(resp.status)
                    for k, v in resp.headers.items():
                        if k.lower() not in ('transfer-encoding', 'content-length'):
                            self.send_header(k, v)
                    content = resp.read()
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
            except urllib.error.HTTPError as e:
                self.send_response(e.code)
                self.end_headers()
                self.wfile.write(e.read())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())

        def do_POST(self): self.forward("POST")
        def do_GET(self): self.forward("GET")
        def do_DELETE(self): self.forward("DELETE")
        def log_message(self, format, *args): pass

    try:
        proxy_server = http.server.ThreadingHTTPServer(('127.0.0.1', 8765), TunnelProxyHandler)
        t = threading.Thread(target=proxy_server.serve_forever, daemon=True)
        t.start()
        print("[*] Cloudflare Tunnel forwarder active on http://127.0.0.1:8765 (realtor.407rescreen.com -> :8001)")
    except Exception as e:
        print(f"[!] Could not bind tunnel proxy on 8765: {e}")

if __name__ == "__main__":
    import uvicorn
    import threading
    import webbrowser
    import subprocess

    def launch_chrome():
        time.sleep(1.2)
        url = "http://127.0.0.1:8001"
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]
        for cp in chrome_paths:
            if os.path.exists(cp):
                try:
                    subprocess.Popen([cp, url])
                    return
                except Exception:
                    pass
        webbrowser.open(url)

    if not os.environ.get("AGENT_DEAL_HUNTER_BROWSER_OPENED"):
        os.environ["AGENT_DEAL_HUNTER_BROWSER_OPENED"] = "1"
        threading.Thread(target=launch_chrome, daemon=True).start()

    print("\nStarting AGENT DEAL HUNTER on http://0.0.0.0:8001 ...")
    uvicorn.run("server:app", host="0.0.0.0", port=8001, reload=True)
