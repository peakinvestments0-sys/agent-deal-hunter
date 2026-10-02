import os
import time
import json
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.storage import data_manager, load_json, save_json
from src.bot_engine import load_bot_settings

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCHEDULER_HISTORY_FILE = os.path.join(DATA_DIR, "scheduler_history.json")


def log_scheduler_run(run_summary: Dict[str, Any]):
    logs = load_json(SCHEDULER_HISTORY_FILE, [])
    logs.insert(0, run_summary)
    save_json(SCHEDULER_HISTORY_FILE, logs[:100])


def dispatch_all_due_followups(manual_trigger: bool = False) -> Dict[str, Any]:
    """
    Executes the Underdog Model cadence follow-up sequence.
    Dispatches cellular SMS to all agents currently due for Follow-Up #1 (Day 3)
    and Follow-Up #2 (Day 7) via Android SMS Gateway, with carrier-safe throttling.
    """
    due = data_manager.get_due_campaigns()
    fu1 = due.get("follow_up_1", [])
    fu2 = due.get("follow_up_2", [])
    total_due = len(fu1) + len(fu2)

    settings = load_bot_settings()
    throttle_base = int(settings.get("cadence_throttle_seconds", 6))

    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    summary = {
        "timestamp": now_str,
        "date": time.strftime("%Y-%m-%d"),
        "trigger": "MANUAL" if manual_trigger else "AUTOMATED_9AM",
        "total_due": total_due,
        "follow_up_1_total": len(fu1),
        "follow_up_1_sent": 0,
        "follow_up_2_total": len(fu2),
        "follow_up_2_sent": 0,
        "dispatched_agents": [],
        "errors": []
    }

    # Process Follow-Up #1 (Day 3)
    for a in fu1:
        aid = a.get("agent_id")
        try:
            res = data_manager.send_campaign_followup(aid)
            if res.get("status") == "success":
                summary["follow_up_1_sent"] += 1
                summary["dispatched_agents"].append({
                    "agent_id": aid,
                    "agent_name": a.get("full_name"),
                    "phone": a.get("phone"),
                    "step": "FOLLOW_UP_1",
                    "status": "SENT"
                })
            else:
                summary["errors"].append({
                    "agent_id": aid,
                    "agent_name": a.get("full_name"),
                    "step": "FOLLOW_UP_1",
                    "error": res.get("message")
                })
        except Exception as e:
            summary["errors"].append({
                "agent_id": aid,
                "agent_name": a.get("full_name"),
                "step": "FOLLOW_UP_1",
                "error": str(e)
            })
        time.sleep(random.uniform(throttle_base - 1, throttle_base + 3))

    # Process Follow-Up #2 (Day 7)
    for a in fu2:
        aid = a.get("agent_id")
        try:
            res = data_manager.send_campaign_followup(aid)
            if res.get("status") == "success":
                summary["follow_up_2_sent"] += 1
                summary["dispatched_agents"].append({
                    "agent_id": aid,
                    "agent_name": a.get("full_name"),
                    "phone": a.get("phone"),
                    "step": "FOLLOW_UP_2",
                    "status": "SENT"
                })
            else:
                summary["errors"].append({
                    "agent_id": aid,
                    "agent_name": a.get("full_name"),
                    "step": "FOLLOW_UP_2",
                    "error": res.get("message")
                })
        except Exception as e:
            summary["errors"].append({
                "agent_id": aid,
                "agent_name": a.get("full_name"),
                "step": "FOLLOW_UP_2",
                "error": str(e)
            })
        time.sleep(random.uniform(throttle_base - 1, throttle_base + 3))

    log_scheduler_run(summary)
    return summary


class CadenceScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_run_date: Optional[str] = None
        self._last_auto_run_date: Optional[str] = None
        self._last_run_result: Optional[Dict[str, Any]] = None
        self._is_running_now = False

        # Load last run from disk if available
        hist = load_json(SCHEDULER_HISTORY_FILE, [])
        if hist and isinstance(hist, list) and len(hist) > 0:
            self._last_run_date = hist[0].get("date")
            self._last_run_result = hist[0]
            for item in hist:
                if item.get("trigger") == "SCHEDULED_DAILY" and not self._last_auto_run_date:
                    self._last_auto_run_date = item.get("date")

    def start(self):
        """Starts the background scheduler loop in a daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scheduler_loop, daemon=True, name="CadenceSchedulerWorker")
        self._thread.start()
        print("[Scheduler] Cadence Follow Up Scheduler daemon started (Target: 9:00 AM daily)")

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _scheduler_loop(self):
        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                today_str = now.strftime("%Y-%m-%d")

                settings = load_bot_settings()
                is_enabled = settings.get("auto_cadence_followup_enabled", True)

                target_hour = 9
                target_minute = 0
                time_str = settings.get("cadence_send_time", "09:00")
                try:
                    parts = time_str.split(":")
                    target_hour = int(parts[0])
                    target_minute = int(parts[1]) if len(parts) > 1 else 0
                except Exception:
                    pass

                # Check if it is currently at or after the target time today and has not run yet today
                is_time = (now.hour == target_hour and now.minute >= target_minute) or (now.hour > target_hour)
                not_yet_run_today = (self._last_auto_run_date != today_str)

                if is_enabled and is_time and not_yet_run_today:
                    print(f"[Scheduler] Triggering scheduled {time_str} Underdog Cadence Follow Ups for {today_str}...")
                    self._last_auto_run_date = today_str
                    self._last_run_date = today_str
                    self._is_running_now = True
                    try:
                        res = dispatch_all_due_followups(manual_trigger=False)
                        self._last_run_result = res
                        print(f"[Scheduler] Automated 9:00 AM Follow Ups complete: FU1={res.get('follow_up_1_sent')}, FU2={res.get('follow_up_2_sent')}")
                    finally:
                        self._is_running_now = False

            except Exception as e:
                print(f"[Scheduler] Error in scheduler loop: {e}")

            # Sleep 30 seconds between checks
            self._stop_event.wait(30)

    def get_status(self) -> Dict[str, Any]:
        settings = load_bot_settings()
        is_enabled = settings.get("auto_cadence_followup_enabled", True)
        time_str = settings.get("cadence_send_time", "09:00")

        now = datetime.now()
        target_hour = 9
        target_minute = 0
        try:
            parts = time_str.split(":")
            target_hour = int(parts[0])
            target_minute = int(parts[1]) if len(parts) > 1 else 0
        except Exception:
            pass

        # Calculate next scheduled run
        today_target = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        if now < today_target and self._last_auto_run_date != now.strftime("%Y-%m-%d"):
            next_run_display = f"Today at {time_str} AM"
        else:
            tomorrow = now + timedelta(days=1)
            next_run_display = f"Tomorrow at {time_str} AM ({tomorrow.strftime('%b %d')})"

        due = data_manager.get_due_campaigns()

        return {
            "enabled": is_enabled,
            "is_alive": bool(self._thread and self._thread.is_alive()),
            "is_running_now": self._is_running_now,
            "scheduled_time": time_str,
            "next_run_display": next_run_display,
            "last_run_date": self._last_run_date,
            "last_auto_run_date": self._last_auto_run_date,
            "last_run_result": self._last_run_result,
            "due_counts": {
                "follow_up_1": len(due.get("follow_up_1", [])),
                "follow_up_2": len(due.get("follow_up_2", [])),
                "cold_call_bucket": len(due.get("cold_call_bucket", []))
            }
        }

    def trigger_run_now(self) -> Dict[str, Any]:
        """Manually dispatches all due cadence follow-ups on demand."""
        if self._is_running_now:
            return {"status": "in_progress", "message": "A cadence dispatch cycle is already currently running."}

        def _worker():
            self._is_running_now = True
            try:
                res = dispatch_all_due_followups(manual_trigger=True)
                self._last_run_result = res
                self._last_run_date = time.strftime("%Y-%m-%d")
            finally:
                self._is_running_now = False

        threading.Thread(target=_worker, daemon=True).start()
        return {"status": "started", "message": "Cadence follow-up dispatch started in the background."}


cadence_scheduler = CadenceScheduler()
