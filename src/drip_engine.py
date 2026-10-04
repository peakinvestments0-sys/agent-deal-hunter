"""
Auto-Drip Outbound Queue Engine (Load & Go)
Supports both Brooke's Off-Market Whales Desk and Lauren's On-Market Fixer Upper Desk.

Features:
1. True background 'Load & Go' drip execution (safe from browser closing/reloads).
2. Paced human-like delays (random jitter between configurable min/max seconds).
3. Operating hours safety guard (quiet hours: 8:30 AM to 7:30 PM local).
4. GSM-7 Zero-Hyphens & Muse.ai carrier compliance.
5. Live state monitoring with second-by-second countdowns for UI bars.
"""

import os
import time
import json
import random
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.storage import data_manager, load_json, save_json
from src.sms_gateway import send_sms
from src.lauren_engine import lauren_engine, load_fixers, save_fixers, sanitize_sms_no_hyphens, resolve_spin
from src.lana_engine import lana_engine, load_lots, save_lots
from src.bot_engine import load_bot_settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DRIP_LOG_FILE = os.path.join(DATA_DIR, "drip_queue_log.json")

BROOKE_DRIP_TEMPLATES = [
    "{Hey|Hi} {Agent_FirstName}, Brooke here. We buy 2 to 3 fixer projects a month in {City}. Got anything beat up that will not qualify for traditional retail buyers?",
    "{Hey|Hi} {Agent_FirstName}, quick question. What is the roughest property you have seen lately that never made it to MLS? Looking for our next flip in {City}.",
    "{Hi|Hey} {Agent_FirstName}, saw your listing on {Listing_Address}. Do you have any off market fixers coming down the pipeline before they hit the MLS?"
]


class DripQueueManager:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        self.status = "IDLE"  # IDLE, RUNNING, PAUSED, COMPLETED, QUIET_HOURS
        self.active_desk = None  # BROOKE, LAUREN, ALL
        self.total_queued = 0
        self.sent_count = 0
        self.failed_count = 0
        self.current_target: Optional[Dict[str, Any]] = None
        self.next_send_time: Optional[str] = None
        self.seconds_remaining = 0
        self.min_delay = 60
        self.max_delay = 120
        self.last_sent_message: Optional[str] = None
        self.last_error: Optional[str] = None
        self.queue: List[Dict[str, Any]] = []

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "active_desk": self.active_desk,
            "total_queued": self.total_queued,
            "sent_count": self.sent_count,
            "failed_count": self.failed_count,
            "remaining_count": len(self.queue),
            "current_target": self.current_target,
            "next_send_time": self.next_send_time,
            "seconds_remaining": max(0, self.seconds_remaining),
            "min_delay": self.min_delay,
            "max_delay": self.max_delay,
            "last_sent_message": self.last_sent_message,
            "last_error": self.last_error,
            "is_alive": bool(self._thread and self._thread.is_alive())
        }

    def start_drip(
        self,
        desk: str = "BROOKE",
        min_delay: int = 60,
        max_delay: int = 120,
        county: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        if self.status == "RUNNING":
            return {"status": "error", "message": "Drip queue is already running. Pause or stop it first."}

        self.min_delay = max(15, min_delay)
        self.max_delay = max(self.min_delay + 5, max_delay)
        self.active_desk = desk.upper()
        self._stop_event.clear()
        self._pause_event.clear()

        # Build Queue
        new_queue = []

        if self.active_desk in ["BROOKE", "ALL"]:
            agents = data_manager.get_all_agents()
            for a in agents:
                phone = a.get("phone", "").strip()
                stage = a.get("pipeline_stage", "New")
                is_dead = a.get("is_dead") or stage == "DEAD" or "opt" in stage.lower()
                is_contacted = a.get("first_touch_sent") or stage not in ["New", "Uncontacted", "Pending Outreach", ""]
                
                if county and county != "ALL":
                    if a.get("county", "").upper() != county.upper():
                        continue

                if phone and not is_dead and not is_contacted:
                    new_queue.append({
                        "desk": "BROOKE",
                        "id": a.get("agent_id"),
                        "name": a.get("full_name") or a.get("agent_name") or "Agent",
                        "phone": phone,
                        "city": a.get("city") or "Florida",
                        "county": a.get("county") or "Florida",
                        "address": a.get("primary_listing_address") or a.get("address") or "your active listing",
                        "agent_record": a
                    })

        if self.active_desk in ["LAUREN", "ALL"]:
            fixers = load_fixers()
            missing_phones = 0
            already_contacted = 0
            county_skipped = 0

            for f in fixers:
                phone = (f.get("agent_phone") or "").strip()
                status = f.get("status", "NEW")
                msgs = f.get("messages", [])
                is_dead = status == "DEAD"
                is_contacted = status != "NEW" or len(msgs) > 0

                if is_contacted:
                    already_contacted += 1

                if county and county != "ALL":
                    if (f.get("county") or "").upper() != county.upper():
                        county_skipped += 1
                        continue

                if not phone:
                    missing_phones += 1
                    continue

                if not is_dead and not is_contacted:
                    new_queue.append({
                        "desk": "LAUREN",
                        "id": f.get("id"),
                        "name": f.get("agent_name") or "Listing Agent",
                        "phone": phone,
                        "city": f.get("city") or "Florida",
                        "county": f.get("county") or "Florida",
                        "address": f.get("address") or "the property",
                        "fixer_record": f
                    })

        if self.active_desk in ["LANA", "ALL"]:
            lots = load_lots()
            for l in lots:
                phone = (l.get("agent_phone") or "").strip()
                status = l.get("status", "QUALIFIED")
                msgs = l.get("messages", [])
                is_dead = status in ["DEAD", "CLOSED_PASS"]
                is_contacted = l.get("last_outbound_date") is not None or len(msgs) > 0

                if county and county != "ALL":
                    if (l.get("county") or "").upper() != county.upper():
                        continue

                if not phone or is_dead or is_contacted:
                    continue

                new_queue.append({
                    "desk": "LANA",
                    "id": l.get("id"),
                    "name": l.get("agent_name") or "Listing Agent",
                    "phone": phone,
                    "city": l.get("city") or "Florida",
                    "county": l.get("county") or "Florida",
                    "address": l.get("address") or "the lot",
                    "lot_record": l
                })

        if limit and limit > 0:
            new_queue = new_queue[:limit]

        if not new_queue:
            if self.active_desk == "LAUREN":
                fixers = load_fixers()
                if not fixers:
                    msg = "Lauren's Desk is empty. Scrape Redfin fixer listings using the Chrome extension first."
                elif missing_phones > 0 and len(new_queue) == 0:
                    msg = f"Found {len(fixers)} listings on Lauren's Desk, but {missing_phones} are missing agent phone numbers. Click '📱 + Add Phone' on any card to enter their number, or scrape listings with listed contacts."
                elif already_contacted == len(fixers):
                    msg = f"All {len(fixers)} fixer listings on Lauren's Desk have already been contacted."
                elif county_skipped > 0:
                    msg = f"No listings found for county '{county}'. Try switching County filter to 'All Counties'."
                else:
                    msg = f"No uncontacted agents found ready to drip for {self.active_desk} desk."
            else:
                msg = f"No uncontacted agents found ready to drip for {self.active_desk} desk."

            return {
                "status": "warning",
                "message": msg,
                "queued": 0
            }

        self.queue = new_queue
        self.total_queued = len(new_queue)
        self.sent_count = 0
        self.failed_count = 0
        self.status = "RUNNING"

        self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="DripQueueWorker")
        self._thread.start()

        return {
            "status": "success",
            "message": f"Auto-Drip Queue started for {self.total_queued} contacts ({self.active_desk} Desk).",
            "queued": self.total_queued,
            "min_delay": self.min_delay,
            "max_delay": self.max_delay
        }

    def pause_drip(self) -> Dict[str, Any]:
        if self.status == "RUNNING":
            self.status = "PAUSED"
            self._pause_event.set()
            return {"status": "success", "message": "Auto-Drip queue paused."}
        elif self.status == "PAUSED":
            self.status = "RUNNING"
            self._pause_event.clear()
            return {"status": "success", "message": "Auto-Drip queue resumed."}
        return {"status": "warning", "message": f"Drip queue is currently {self.status}."}

    def stop_drip(self) -> Dict[str, Any]:
        self.status = "IDLE"
        self._stop_event.set()
        self._pause_event.clear()
        self.queue = []
        self.seconds_remaining = 0
        self.current_target = None
        return {"status": "success", "message": "Auto-Drip queue stopped and cleared."}

    def _is_quiet_hours(self) -> bool:
        """Returns True if outside business hours (8:30 AM to 7:30 PM local)."""
        now = datetime.now()
        # 8:30 AM = 8.5, 7:30 PM = 19.5
        decimal_hour = now.hour + (now.minute / 60.0)
        return decimal_hour < 8.5 or decimal_hour > 19.5

    def _worker_loop(self):
        print(f"[DripEngine] Started Auto-Drip worker for {len(self.queue)} contacts.")

        while self.queue and not self._stop_event.is_set():
            # Handle Pause
            if self._pause_event.is_set():
                time.sleep(1)
                continue

            # Handle Quiet Hours
            if self._is_quiet_hours():
                prev_status = self.status
                self.status = "QUIET_HOURS"
                time.sleep(30)
                continue
            else:
                if self.status == "QUIET_HOURS":
                    self.status = "RUNNING"

            # Pop next item
            item = self.queue.pop(0)
            self.current_target = item
            desk = item.get("desk")
            target_id = item.get("id")
            phone = item.get("phone")
            name = item.get("name", "there")
            first_name = name.split()[0]
            city = item.get("city", "Florida")
            address = item.get("address", "your listing")

            msg_to_send = ""

            try:
                if desk == "BROOKE":
                    # Generate Brooke Spintax single-segment opener
                    template = random.choice(BROOKE_DRIP_TEMPLATES)
                    raw_msg = template.replace("{Agent_FirstName}", first_name).replace("{City}", city).replace("{Listing_Address}", address)
                    msg_to_send = sanitize_sms_no_hyphens(resolve_spin(raw_msg))

                    res = send_sms(phone=phone, message=msg_to_send, agent_id=target_id, metadata={"drip": True, "desk": "BROOKE"})
                    
                    # Update Agent in Storage
                    agent = data_manager.find_agent_by_id(target_id)
                    if agent:
                        agent["pipeline_stage"] = "Contacted"
                        agent["first_touch_sent"] = True
                        agent["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        data_manager.save_agent(agent)

                    self.sent_count += 1
                    self.last_sent_message = f"[Brooke ➔ {name}] {msg_to_send}"

                elif desk == "LAUREN":
                    # Generate or pull Lauren hook
                    fixers = load_fixers()
                    fixer = next((f for f in fixers if f.get("id") == target_id), None)
                    if fixer:
                        msg_to_send = fixer.get("opening_hook") or lauren_engine.generate_opening_hook(fixer)
                        res = send_sms(phone=phone, message=msg_to_send, agent_id=target_id, metadata={"drip": True, "desk": "LAUREN"})
                        
                        if "messages" not in fixer: fixer["messages"] = []
                        fixer["messages"].append({
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "direction": "OUTBOUND",
                            "sender": "Lauren (Drip)",
                            "text": msg_to_send
                        })
                        fixer["status"] = "OUTREACH_SENT"
                        fixer["last_interaction"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_fixers(fixers)

                    self.sent_count += 1
                    self.last_sent_message = f"[Lauren ➔ {name}] {msg_to_send}"

                elif desk == "LANA":
                    lots = load_lots()
                    lot = next((l for l in lots if l.get("id") == target_id), None)
                    if lot:
                        msg_to_send = lana_engine.generate_opener_sms(lot)
                        res = send_sms(phone=phone, message=msg_to_send, agent_id=target_id, metadata={"drip": True, "desk": "LANA"})
                        
                        if "messages" not in lot: lot["messages"] = []
                        lot["messages"].append({
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                            "direction": "OUTBOUND",
                            "sender": "Lana (Drip)",
                            "text": msg_to_send
                        })
                        lot["status"] = "OUTREACH_SENT"
                        lot["last_outbound_date"] = time.strftime("%Y-%m-%d %H:%M:%S")
                        save_lots(lots)

                    self.sent_count += 1
                    self.last_sent_message = f"[Lana ➔ {name}] {msg_to_send}"

                self._log_drip_entry(item, msg_to_send, "SENT")

            except Exception as e:
                self.failed_count += 1
                self.last_error = f"Error sending to {name} ({phone}): {str(e)}"
                print(f"[DripEngine] {self.last_error}")
                self._log_drip_entry(item, msg_to_send, f"FAILED: {str(e)}")

            # Pacing Delay with Countdown
            if self.queue and not self._stop_event.is_set():
                delay = random.randint(self.min_delay, self.max_delay)
                self.seconds_remaining = delay
                next_epoch = time.time() + delay
                self.next_send_time = time.strftime("%H:%M:%S", time.localtime(next_epoch))

                while self.seconds_remaining > 0 and not self._stop_event.is_set():
                    if self._pause_event.is_set():
                        time.sleep(1)
                        continue
                    time.sleep(1)
                    self.seconds_remaining -= 1

        self.status = "COMPLETED" if self.sent_count > 0 else "IDLE"
        self.current_target = None
        self.seconds_remaining = 0
        print(f"[DripEngine] Drip worker completed. Sent: {self.sent_count}, Failed: {self.failed_count}.")

    def _log_drip_entry(self, target: Dict[str, Any], message: str, status: str):
        try:
            logs = load_json(DRIP_LOG_FILE, [])
            logs.insert(0, {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "desk": target.get("desk"),
                "id": target.get("id"),
                "name": target.get("name"),
                "phone": target.get("phone"),
                "address": target.get("address"),
                "message": message,
                "status": status
            })
            save_json(DRIP_LOG_FILE, logs[:200])
        except Exception:
            pass


drip_engine = DripQueueManager()
