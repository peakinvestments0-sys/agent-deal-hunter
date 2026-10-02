import os
import re
import json
import glob
import time
import random
import threading
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
from src.ingestion import parse_propwire_csv, raw_phone_digits, clean_phone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "agent_pipeline_state.json")
CUSTOM_AGENTS_FILE = os.path.join(DATA_DIR, "custom_agents.json")
OUTREACH_FILE = os.path.join(DATA_DIR, "outreach_history.json")

def load_json(filepath: str, default: Any) -> Any:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath: str, data: Any):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

class AgentDataManager:
    def __init__(self):
        self.cached_agents: Dict[str, Dict[str, Any]] = {}
        self.pipeline_state: Dict[str, Dict[str, Any]] = {}
        self.refresh()

    def refresh(self):
        """Scan data folder for all CSV exports and merge with custom agents and state."""
        self.pipeline_state = load_json(STATE_FILE, {})
        csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
        root_csvs = glob.glob(os.path.join(BASE_DIR, "*.csv"))
        all_csvs = list(set(csv_files + root_csvs))

        merged: Dict[str, Dict[str, Any]] = {}
        for path in all_csvs:
            parsed = parse_propwire_csv(path)
            for agent in parsed:
                aid = agent["agent_id"]
                if aid not in merged:
                    merged[aid] = agent
                else:
                    existing_addrs = {l["address"].lower() for l in merged[aid]["listings"]}
                    for l in agent["listings"]:
                        if l["address"].lower() not in existing_addrs:
                            merged[aid]["listings"].append(l)
                    merged[aid]["listing_count"] = len(merged[aid]["listings"])
                    merged[aid]["total_volume"] = sum(x["listing_price"] for x in merged[aid]["listings"])
                    merged[aid]["avg_price"] = merged[aid]["total_volume"] / merged[aid]["listing_count"]

        # Merge custom sandbox/test agents
        custom_agents = load_json(CUSTOM_AGENTS_FILE, {})
        for aid, agent in custom_agents.items():
            merged[aid] = agent

        # Apply saved pipeline state & dynamic indicators
        now = datetime.now()
        from src.bot_engine import bot_engine
        for aid, agent in merged.items():
            if aid in self.pipeline_state:
                saved = self.pipeline_state[aid]
                agent["pipeline_stage"] = saved.get("pipeline_stage", agent.get("pipeline_stage", "New Ingest"))
                agent["tier"] = saved.get("tier", agent.get("tier", "Single Listing Agent"))
                agent["notes"] = saved.get("notes", "")
                agent["custom_phone"] = saved.get("custom_phone", "")
                agent["custom_email"] = saved.get("custom_email", "")
                agent["pocket_deals"] = saved.get("pocket_deals", [])
                agent["last_contact_date"] = saved.get("last_contact_date", None)
                agent["last_contact_channel"] = saved.get("last_contact_channel", None)
                agent["unread_replies"] = saved.get("unread_replies", 0)
                agent["last_reply_text"] = saved.get("last_reply_text", "")
                agent["last_reply_date"] = saved.get("last_reply_date", None)
                agent["bot_vetting"] = saved.get("bot_vetting", None)
                agent["last_bot_suggestion"] = saved.get("last_bot_suggestion", "")
                agent["last_bot_node"] = saved.get("last_bot_node", "")
                agent["last_bot_reason"] = saved.get("last_bot_reason", "")
                agent["is_gold_deal"] = saved.get("is_gold_deal", False)

                # Field overrides from edits
                for k in ["full_name", "first_name", "last_name", "phone", "email", "brokerage", "primary_address", "primary_city", "primary_price"]:
                    if k in saved and saved[k] is not None and saved[k] != "":
                        agent[k] = saved[k]
                if "phone" in saved and saved["phone"]:
                    agent["phone_raw"] = raw_phone_digits(saved["phone"])
            else:
                agent["pipeline_stage"] = agent.get("pipeline_stage", "New Ingest")
                agent["notes"] = agent.get("notes", "")
                agent["pocket_deals"] = agent.get("pocket_deals", [])
                agent["unread_replies"] = 0
                agent["bot_vetting"] = None
                agent["last_bot_suggestion"] = ""
                agent["last_bot_node"] = ""
                agent["last_bot_reason"] = ""
                agent["is_gold_deal"] = False

            # Cadence & Follow-up Campaign Evaluation (Underdog Model)
            agent["campaign_status"] = bot_engine.check_campaign_cadence(agent)
            agent["cadence_due"] = False
            agent["days_since_contact"] = None
            if agent.get("last_contact_date"):
                try:
                    dt = datetime.strptime(agent["last_contact_date"][:19], "%Y-%m-%d %H:%M:%S")
                    diff = (now - dt).days
                    agent["days_since_contact"] = diff
                    if diff >= 21:
                        agent["cadence_due"] = True
                except Exception:
                    pass

            # Stale Listing / High DOM Motivation Signal (60+ Days on Market)
            max_dom = max((l.get("days_on_market", 0) for l in agent["listings"]), default=0)
            agent["max_dom"] = max_dom
            agent["is_stale_dom"] = max_dom >= 60

        self.cached_agents = merged

    def get_all_agents(self, county: str = None, stage: str = None, tier: str = None, search: str = None) -> List[Dict[str, Any]]:
        agents = list(self.cached_agents.values())

        if county and county.upper() != "ALL":
            agents = [a for a in agents if a.get("county", "").upper() == county.upper()]

        if stage and stage.upper() != "ALL":
            st_upper = stage.upper()
            if stage == "cadence_due":
                agents = [a for a in agents if a.get("cadence_due")]
            elif stage == "stale_dom":
                agents = [a for a in agents if a.get("is_stale_dom")]
            elif stage == "inbox":
                agents = [a for a in agents if a.get("unread_replies", 0) > 0]
            elif stage == "chatted":
                agents = [
                    a for a in agents if (
                        a.get("unread_replies", 0) > 0 or
                        bool(a.get("last_contact_date")) or
                        bool(a.get("last_reply_text")) or
                        a.get("pipeline_stage") in ("Contacted", "Warm / In Discussion", "Pocket Deal Review", "Appointment Pending", "Appointment Confirmed", "Contract Sent")
                    )
                ]
            elif st_upper == "FOLLOWUP_1":
                agents = [a for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "FOLLOW_UP_1"]
            elif st_upper == "FOLLOWUP_2":
                agents = [a for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "FOLLOW_UP_2"]
            elif st_upper == "COLDCALL":
                agents = [a for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "COLD_CALL_BUCKET"]
            elif st_upper == "GOLD":
                agents = [a for a in agents if a.get("is_gold_deal") or "GOLD" in a.get("tier", "")]
            elif st_upper == "APPOINTMENT":
                agents = [a for a in agents if "Appointment" in a.get("pipeline_stage", "") or "Appt" in a.get("tier", "")]
            else:
                agents = [a for a in agents if a.get("pipeline_stage", "").lower() == stage.lower()]

        if tier and tier.upper() != "ALL":
            t_upper = tier.upper()
            if t_upper == "TIER_1":
                agents = [a for a in agents if "Tier 1" in a.get("tier", "")]
            elif t_upper == "TIER_2":
                agents = [a for a in agents if "Tier 2" in a.get("tier", "")]
            elif t_upper == "TIER_3":
                agents = [a for a in agents if "Tier 3" in a.get("tier", "")]
            elif t_upper == "GOLD":
                agents = [a for a in agents if a.get("is_gold_deal") or "GOLD" in a.get("tier", "")]
            elif t_upper == "DEAD":
                agents = [a for a in agents if "Dead" in a.get("tier", "")]
            else:
                agents = [a for a in agents if tier.lower() in a.get("tier", "").lower()]

        if search:
            q = search.lower().strip()
            def matches(a):
                if q in a["full_name"].lower(): return True
                if q in a.get("phone", "").lower(): return True
                if q in a.get("email", "").lower(): return True
                if q in a.get("brokerage", "").lower(): return True
                for l in a["listings"]:
                    if q in l.get("address", "").lower() or q in l.get("city", "").lower() or q in l.get("apn", "").lower():
                        return True
                return False
            agents = [a for a in agents if matches(a)]

        return agents

    def get_agent(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self.cached_agents.get(agent_id)

    get_agent_by_id = get_agent

    def find_agent_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        p_digits = raw_phone_digits(phone)
        if not p_digits:
            return None
        for a in self.cached_agents.values():
            if raw_phone_digits(a.get("phone", "")) == p_digits or raw_phone_digits(a.get("custom_phone", "")) == p_digits:
                return a
        return None

    def update_agent_state(self, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if agent_id not in self.pipeline_state:
            self.pipeline_state[agent_id] = {}

        self.pipeline_state[agent_id].update(updates)
        save_json(STATE_FILE, self.pipeline_state)

        if agent_id in self.cached_agents:
            self.cached_agents[agent_id].update(updates)
            return self.cached_agents[agent_id]
        return None

    def edit_agent(self, agent_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if "phone" in updates and updates["phone"]:
            updates["phone"] = clean_phone(updates["phone"])
            updates["phone_raw"] = raw_phone_digits(updates["phone"])
        if "full_name" in updates and updates["full_name"]:
            parts = str(updates["full_name"]).strip().split(" ", 1)
            updates["first_name"] = parts[0]
            updates["last_name"] = parts[1] if len(parts) > 1 else ""

        # Check if custom agent and update in custom_agents.json
        custom_agents = load_json(CUSTOM_AGENTS_FILE, {})
        if agent_id in custom_agents:
            custom_agents[agent_id].update(updates)
            save_json(CUSTOM_AGENTS_FILE, custom_agents)

        # Update pipeline state & cache
        self.update_agent_state(agent_id, updates)
        if agent_id in self.cached_agents:
            self.cached_agents[agent_id].update(updates)
            return self.cached_agents[agent_id]
        return None

    def create_custom_agent(self, data: Dict[str, Any]) -> Dict[str, Any]:
        custom_agents = load_json(CUSTOM_AGENTS_FILE, {})
        phone_clean = clean_phone(data.get("phone", ""))
        phone_digits = raw_phone_digits(phone_clean)
        aid = data.get("agent_id") or f"custom_{phone_digits or int(time.time())}"

        full_name = data.get("full_name", "").strip() or "Test Agent"
        parts = full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""

        listing_price = float(data.get("listing_price", 275000.0) or 275000.0)
        city = data.get("city", "Melbourne").strip()
        county = data.get("county", "BREVARD").strip().upper()
        address = data.get("address", "123 Sandbox Way").strip()

        listings = [
            {
                "address": address,
                "city": city,
                "county": county,
                "zip": data.get("zip", "32901"),
                "listing_price": listing_price,
                "estimated_value": float(data.get("estimated_value", listing_price * 1.1) or listing_price * 1.1),
                "beds": int(data.get("beds", 3) or 3),
                "baths": float(data.get("baths", 2.0) or 2.0),
                "sqft": int(data.get("sqft", 1600) or 1600),
                "year_built": int(data.get("year_built", 1995) or 1995),
                "days_on_market": int(data.get("days_on_market", 14) or 14),
                "apn": data.get("apn", "TEST-001-APN"),
                "owner_name": "Test Property Owner",
                "legal_description": "LOT 1 TEST SUBDIVISION"
            }
        ]

        new_agent = {
            "agent_id": aid,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone_clean,
            "phone_raw": phone_digits,
            "email": data.get("email", "").strip().lower(),
            "brokerage": data.get("brokerage", "Florida Test Realty").strip(),
            "county": county,
            "listings": listings,
            "pipeline_stage": data.get("pipeline_stage", "New Ingest"),
            "notes": data.get("notes", "Sandbox test agent"),
            "pocket_deals": [],
            "listing_count": 1,
            "total_volume": listing_price,
            "avg_price": listing_price,
            "tier": "🧪 Test Agent",
            "primary_address": address,
            "primary_city": city,
            "primary_price": listing_price,
            "primary_dom": int(data.get("days_on_market", 14) or 14),
            "is_custom": True
        }

        custom_agents[aid] = new_agent
        save_json(CUSTOM_AGENTS_FILE, custom_agents)
        self.cached_agents[aid] = new_agent
        self.refresh()
        return self.cached_agents.get(aid, new_agent)

    def delete_agent(self, agent_id: str) -> bool:
        custom_agents = load_json(CUSTOM_AGENTS_FILE, {})
        deleted = False
        if agent_id in custom_agents:
            del custom_agents[agent_id]
            save_json(CUSTOM_AGENTS_FILE, custom_agents)
            deleted = True
        if agent_id in self.pipeline_state:
            del self.pipeline_state[agent_id]
            save_json(STATE_FILE, self.pipeline_state)
            deleted = True
        if agent_id in self.cached_agents:
            del self.cached_agents[agent_id]
            deleted = True
        return deleted

    def record_inbound_sms(self, phone: str, message: str, raw_payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Processes inbound SMS webhook from Android SMS Gateway:
        - Matches phone to agent
        - Evaluates message through Lead Vetting Flowchart bot engine
        - Auto-tags Tiers (Tier 1, Tier 2, Tier 3, Cash Agent Dead, Gold Deal)
        - Logs to outreach history as INBOUND
        - Flags unread message badge & generates flowchart suggested reply
        - If in Autopilot mode, automatically dispatches response
        """
        agent = self.find_agent_by_phone(phone)
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Check if phone matches Lauren's on-market fixers
        fixer_match = None
        if not agent:
            clean_digits = raw_phone_digits(phone)[-10:]
            if clean_digits:
                try:
                    from src.lauren_engine import load_fixers
                    for f in load_fixers():
                        f_digits = raw_phone_digits(f.get("agent_phone") or "")[-10:]
                        if f_digits and f_digits == clean_digits:
                            fixer_match = f
                            break
                except Exception:
                    pass

        log_entry = {
            "timestamp": timestamp,
            "direction": "INBOUND",
            "channel": "SMS",
            "sender_phone": phone,
            "message": message,
            "status": "RECEIVED",
            "agent_id": agent["agent_id"] if agent else (fixer_match["id"] if fixer_match else None),
            "agent_name": agent["full_name"] if agent else (fixer_match.get("agent_name", "Fixer Agent") if fixer_match else "Unknown Agent"),
            "is_fixer": bool(fixer_match),
            "fixer_address": fixer_match.get("address", "") if fixer_match else "",
            "raw": raw_payload or {}
        }
        self.log_outreach(log_entry)

        bot_result = None
        if agent:
            from src.bot_engine import bot_engine, load_bot_settings
            aid = agent["agent_id"]
            current_unreads = self.pipeline_state.get(aid, {}).get("unread_replies", 0) + 1

            bot_result = bot_engine.evaluate_inbound_sms(agent, message)

            updates = {
                "pipeline_stage": bot_result.get("stage_update", "Warm / In Discussion"),
                "tier": bot_result.get("tier_update", agent.get("tier")),
                "last_reply_text": message,
                "last_reply_date": timestamp,
                "unread_replies": current_unreads,
                "bot_vetting": bot_result.get("state_updates"),
                "last_bot_suggestion": bot_result.get("reply_text", ""),
                "last_bot_node": bot_result.get("node", ""),
                "last_bot_reason": bot_result.get("state_updates", {}).get("suggested_reply_reason", "")
            }

            if bot_result.get("state_updates", {}).get("is_gold"):
                updates["is_gold_deal"] = True

            self.update_agent_state(aid, updates)

            # Check Autopilot mode
            cfg = load_bot_settings()
            is_test = bool(agent.get("is_test") or agent.get("is_custom") or "test" in str(agent.get("tier", "")).lower())
            test_autopilot = agent.get("test_autopilot", False)
            should_auto_send = (cfg.get("mode") == "autopilot") or (is_test and test_autopilot)

            if (
                cfg.get("enabled", True) 
                and should_auto_send 
                and bot_result.get("reply_text")
            ):
                base_delay = int(cfg.get("auto_send_delay_seconds", 30))
                # Natural human jitter (e.g. 25-38 seconds)
                delay_seconds = max(15, base_delay + random.randint(-4, 7))
                reply_text = bot_result["reply_text"]
                reply_node = bot_result.get("node")

                # Mark agent as pending delayed autopilot dispatch so UI displays live typing
                self.update_agent_state(aid, {
                    "pending_autopilot": True,
                    "pending_autopilot_text": reply_text,
                    "pending_autopilot_node": reply_node,
                    "pending_autopilot_send_time": time.time() + delay_seconds,
                    "pending_autopilot_eta_seconds": delay_seconds
                })

                # Background worker thread so API responds immediately without blocking
                def _delayed_autopilot_worker(target_aid: str, target_phone: str, text: str, delay: int, node: str):
                    time.sleep(delay)
                    try:
                        curr_st = self.pipeline_state.get(target_aid, {})
                        # Ensure not cancelled or manually overridden during the delay
                        if curr_st.get("pending_autopilot") and curr_st.get("pending_autopilot_text") == text:
                            from src.sms_gateway import send_sms
                            send_sms(
                                phone=target_phone,
                                message=text,
                                agent_id=target_aid,
                                metadata={"auto_bot": True, "node": node, "delay_seconds": delay}
                            )
                            self.update_agent_state(target_aid, {
                                "pending_autopilot": False,
                                "pending_autopilot_text": None,
                                "pending_autopilot_send_time": None,
                                "last_bot_suggestion": "",
                                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S")
                            })
                    except Exception as e:
                        print(f"Error in autopilot delayed dispatch: {e}")

                threading.Thread(
                    target=_delayed_autopilot_worker,
                    args=(aid, phone, reply_text, delay_seconds, reply_node),
                    daemon=True
                ).start()

        return {
            "log": log_entry,
            "bot_result": bot_result
        }

    def approve_bot_suggestion(self, agent_id: str, custom_message: Optional[str] = None) -> Dict[str, Any]:
        """Approves and dispatches the suggested flowchart response for an agent, logging golden reply."""
        agent = self.get_agent(agent_id)
        if not agent:
            return {"status": "error", "message": "Agent not found"}

        message_to_send = (custom_message or agent.get("last_bot_suggestion", "")).strip()
        if not message_to_send:
            return {"status": "error", "message": "No pending suggestion to send"}

        # Log golden training reply if human approved/edited
        try:
            from src.bot_engine import save_golden_reply
            last_suggested = (agent.get("last_bot_suggestion") or "").strip()
            was_edited = bool(custom_message and custom_message.strip() != last_suggested)
            save_golden_reply({
                "agent_name": agent.get("full_name"),
                "agent_phone": agent.get("phone"),
                "node": agent.get("last_bot_node", ""),
                "agent_inbound": agent.get("last_reply_text", ""),
                "suggested_template": last_suggested,
                "final_approved_text": message_to_send,
                "was_edited": was_edited,
                "channel": "SMS"
            })
        except Exception as e:
            print(f"Error logging golden reply: {e}")

        # Cancel any pending autopilot delayed send
        self.update_agent_state(agent_id, {
            "pending_autopilot": False,
            "pending_autopilot_text": None,
            "pending_autopilot_send_time": None
        })

        phone = agent.get("custom_phone") or agent.get("phone")
        from src.sms_gateway import send_sms
        res = send_sms(phone=phone, message=message_to_send, agent_id=agent_id, metadata={"approved_copilot": True})

        if res.get("status") == "success":
            self.update_agent_state(agent_id, {
                "last_bot_suggestion": "",
                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                "unread_replies": 0
            })

        return res

    def set_agent_tier(self, agent_id: str, tier: str) -> Optional[Dict[str, Any]]:
        return self.update_agent_state(agent_id, {"tier": tier})

    def reset_agent_history(self, agent_id: str):
        """Clears all outreach history and state for a test agent to test fresh."""
        hist = load_json(OUTREACH_FILE, [])
        agent = self.get_agent(agent_id)
        p_raw = raw_phone_digits(agent.get("phone", "")) if agent else ""
        cleaned = []
        for h in hist:
            if h.get("agent_id") == agent_id:
                continue
            if p_raw and (raw_phone_digits(h.get("sender_phone", "")) == p_raw or raw_phone_digits(h.get("recipient_phone", "")) == p_raw):
                continue
            cleaned.append(h)
        save_json(OUTREACH_FILE, cleaned)

        if agent_id in self.pipeline_state:
            del self.pipeline_state[agent_id]
            save_json(STATE_FILE, self.pipeline_state)

        self.refresh()

    def get_due_campaigns(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns lists of agents due for Underdog Model follow-up campaigns."""
        fu1 = []
        fu2 = []
        cold = []
        for a in self.cached_agents.values():
            st = a.get("campaign_status")
            if st:
                step = st.get("campaign_step")
                if step == "FOLLOW_UP_1":
                    fu1.append(a)
                elif step == "FOLLOW_UP_2":
                    fu2.append(a)
                elif step == "COLD_CALL_BUCKET":
                    cold.append(a)
        return {
            "follow_up_1": fu1,
            "follow_up_2": fu2,
            "cold_call_bucket": cold
        }

    def send_campaign_followup(self, agent_id: str) -> Dict[str, Any]:
        agent = self.get_agent(agent_id)
        if not agent or not agent.get("campaign_status"):
            return {"status": "error", "message": "Agent not due for campaign follow-up"}

        c_status = agent["campaign_status"]
        msg = c_status.get("message")
        phone = agent.get("custom_phone") or agent.get("phone")
        if not msg or not phone:
            return {"status": "error", "message": "No message or phone available"}

        from src.sms_gateway import send_sms
        res = send_sms(phone=phone, message=msg, agent_id=agent_id, metadata={"campaign_step": c_status.get("campaign_step")})
        if res.get("status") == "success":
            step = c_status.get("campaign_step")
            new_stage = "Follow-Up #1 Sent" if step == "FOLLOW_UP_1" else "Follow-Up #2 Sent"
            self.update_agent_state(agent_id, {
                "pipeline_stage": new_stage,
                "last_contact_date": time.strftime("%Y-%m-%d %H:%M:%S")
            })
        return res

    def get_bot_pipeline_summary(self) -> Dict[str, Any]:
        agents = list(self.cached_agents.values())
        return {
            "total_agents": len(agents),
            "tier_1_hot": sum(1 for a in agents if "Tier 1" in a.get("tier", "")),
            "tier_2_pocket": sum(1 for a in agents if "Tier 2" in a.get("tier", "")),
            "tier_3_cold": sum(1 for a in agents if "Tier 3" in a.get("tier", "")),
            "gold_deals": sum(1 for a in agents if a.get("is_gold_deal") or "GOLD" in a.get("tier", "")),
            "appointments_set": sum(1 for a in agents if "Appointment" in a.get("pipeline_stage", "") or "Appt" in a.get("tier", "")),
            "follow_up_1_due": sum(1 for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "FOLLOW_UP_1"),
            "follow_up_2_due": sum(1 for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "FOLLOW_UP_2"),
            "cold_call_bucket": sum(1 for a in agents if (a.get("campaign_status") or {}).get("campaign_step") == "COLD_CALL_BUCKET"),
            "cash_agent_dead": sum(1 for a in agents if "Dead" in a.get("tier", ""))
        }

    def mark_inbox_read(self, agent_id: str):
        if agent_id in self.pipeline_state:
            self.update_agent_state(agent_id, {"unread_replies": 0})

    def add_pocket_deal(self, agent_id: str, deal: Dict[str, Any]):
        if agent_id not in self.pipeline_state:
            self.pipeline_state[agent_id] = {}
        
        deals = self.pipeline_state[agent_id].get("pocket_deals", [])
        deals.append(deal)
        self.pipeline_state[agent_id]["pocket_deals"] = deals
        self.pipeline_state[agent_id]["pipeline_stage"] = "Pocket Deal Review"
        save_json(STATE_FILE, self.pipeline_state)

        if agent_id in self.cached_agents:
            self.cached_agents[agent_id]["pocket_deals"] = deals
            self.cached_agents[agent_id]["pipeline_stage"] = "Pocket Deal Review"

    def get_counties(self) -> List[str]:
        counties = set()
        for a in self.cached_agents.values():
            if a.get("county"):
                counties.add(a["county"].upper())
        return sorted(list(counties))

    def ensure_outreach_ids(self) -> List[Dict[str, Any]]:
        logs = load_json(OUTREACH_FILE, [])
        changed = False
        for idx, m in enumerate(logs):
            if not m.get("id"):
                raw_id = m.get("raw", {}).get("id") or m.get("raw", {}).get("payload", {}).get("messageId")
                m["id"] = raw_id if raw_id else f"msg_{int(time.time())}_{idx}_{uuid.uuid4().hex[:6]}"
                changed = True
        if changed:
            save_json(OUTREACH_FILE, logs)
        return logs

    def log_outreach(self, log_entry: Dict[str, Any]):
        if "id" not in log_entry or not log_entry["id"]:
            log_entry["id"] = f"msg_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}"
        logs = self.ensure_outreach_ids()
        logs.insert(0, log_entry)
        save_json(OUTREACH_FILE, logs[:1000])

    def get_outreach_history(self, agent_id: str = None, direction: str = None) -> List[Dict[str, Any]]:
        logs = self.ensure_outreach_ids()
        if agent_id:
            logs = [l for l in logs if l.get("agent_id") == agent_id]
        if direction:
            logs = [l for l in logs if l.get("direction") == direction]
        return logs

    def delete_outreach_message(self, message_id: str = None, timestamp: str = None, sender_phone: str = None, message_text: str = None) -> bool:
        logs = self.ensure_outreach_ids()
        original_len = len(logs)
        remaining = []
        deleted_agent_id = None

        for m in logs:
            match = False
            if message_id and m.get("id") == message_id:
                match = True
            elif timestamp and sender_phone and m.get("timestamp") == timestamp and (m.get("sender_phone") == sender_phone or raw_phone_digits(m.get("sender_phone", "")) == raw_phone_digits(sender_phone)):
                if not message_text or m.get("message") == message_text:
                    match = True

            if match:
                deleted_agent_id = m.get("agent_id")
                continue
            remaining.append(m)

        if len(remaining) < original_len:
            save_json(OUTREACH_FILE, remaining)
            if deleted_agent_id and deleted_agent_id in self.pipeline_state:
                agent_inbounds = [x for x in remaining if x.get("agent_id") == deleted_agent_id and x.get("direction") == "INBOUND"]
                if not agent_inbounds:
                    self.update_agent_state(deleted_agent_id, {
                        "unread_replies": 0,
                        "last_reply_text": "",
                        "last_reply_date": None,
                        "last_bot_suggestion": "",
                        "last_bot_node": "",
                        "last_bot_reason": ""
                    })
                else:
                    curr_unreads = self.pipeline_state[deleted_agent_id].get("unread_replies", 0)
                    if curr_unreads > 0:
                        self.update_agent_state(deleted_agent_id, {"unread_replies": max(0, curr_unreads - 1)})
            self.refresh()
            return True
        return False

    def clear_spam_inbound(self) -> int:
        """
        Smart spam clear:
        Deletes actual spam (shortcodes, bank OTPs, verification codes, marketing promos)
        NEVER deletes texts from registered MLS agents or Lauren's on-market fixers!
        """
        logs = self.ensure_outreach_ids()
        fixer_phones = set()
        try:
            from src.lauren_engine import load_fixers
            for f in load_fixers():
                ph = raw_phone_digits(f.get("agent_phone") or "")[-10:]
                if ph:
                    fixer_phones.add(ph)
        except Exception:
            pass

        agent_phones = {raw_phone_digits(a.get("phone") or "")[-10:] for a in self.cached_agents.values() if a.get("phone")}

        spam_keywords = [
            "verification code", "security code", "your code is", "passcode",
            "one-time code", "otp", "do not share", "auth code", "reply stop to",
            "text stop to", "opt out", "promo code", "special offer", "discount code"
        ]

        cleaned = []
        deleted_count = 0
        for m in logs:
            if m.get("direction") == "INBOUND":
                aid = m.get("agent_id")
                is_fixer = m.get("is_fixer")
                phone_digits = raw_phone_digits(m.get("sender_phone") or "")[-10:]
                msg_lower = (m.get("message") or "").lower()

                # Rule 1: Identified MLS agent -> KEEP
                if aid and m.get("agent_name") not in ("Unknown Agent", None) and not is_fixer:
                    cleaned.append(m)
                    continue

                # Rule 2: Matched to Lauren Fixer -> KEEP
                if is_fixer or (phone_digits and phone_digits in fixer_phones):
                    cleaned.append(m)
                    continue

                # Rule 3: Known agent phone -> KEEP
                if phone_digits and phone_digits in agent_phones:
                    cleaned.append(m)
                    continue

                # Rule 4: Shortcode (less than 10 digits) -> SPAM
                raw_digits_len = len(raw_phone_digits(m.get("sender_phone") or ""))
                if raw_digits_len > 0 and raw_digits_len < 10:
                    deleted_count += 1
                    continue

                # Rule 5: Matches automated spam keywords -> SPAM
                if any(kw in msg_lower for kw in spam_keywords):
                    deleted_count += 1
                    continue

            cleaned.append(m)

        if deleted_count > 0:
            save_json(OUTREACH_FILE, cleaned)
            self.refresh()
        return deleted_count

data_manager = AgentDataManager()
