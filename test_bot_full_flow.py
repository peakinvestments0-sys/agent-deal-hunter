import sys
import os
import io

# Force UTF-8 on Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath("."))

from src.bot_engine import bot_engine, load_bot_settings, save_bot_settings
from src.storage import data_manager

def test_full_pipeline():
    print("==================================================")
    print("RUNNING END-TO-END LEAD VETTING & UNDERDOG BOT TEST")
    print("==================================================")

    # 1. Verify Bot Settings
    cfg = load_bot_settings()
    print(f"[1] Bot Settings loaded: mode={cfg.get('mode')}, partner={cfg.get('partner_name')}, gold={cfg.get('zestimate_gold_threshold')*100}%")
    assert cfg.get("partner_name") == "Matt", "Partner should be Matt"

    # 2. Create clean test agent
    test_agent = {
        "agent_id": "test_bot_agent_001",
        "full_name": "Sarah Listing Agent",
        "first_name": "Sarah",
        "last_name": "Listing Agent",
        "phone": "(321) 555-0199",
        "phone_raw": "3215550199",
        "email": "sarah@listingagent.com",
        "brokerage": "Florida Sun Realty",
        "county": "BREVARD",
        "pipeline_stage": "Contacted",
        "tier": "Tier 3: Inactive",
        "is_custom": True,
        "is_test": True,
        "listings": [{
            "address": "456 Magnolia Court",
            "city": "Palm Bay",
            "listing_price": 290000,
            "estimated_value": 310000
        }]
    }
    data_manager.cached_agents[test_agent["agent_id"]] = test_agent

    # 3. Flowchart Step 1: Agent texts an address
    print("\n[2] Flowchart Step 1: Agent texts address")
    msg1 = "Hey, check out 789 Ocean Breeze Ave in Melbourne"
    res1 = bot_engine.evaluate_inbound_sms(test_agent, msg1)
    print(f"   Node: {res1.get('node')}")
    print(f"   Reply Suggestion: {res1.get('reply_text')}")
    assert res1.get("node") == "ENTRY_HOOK_AWAITING_REPLY"
    assert "what can you share" in res1.get("reply_text", "").lower()

    test_agent["bot_vetting"] = res1.get("state_updates")

    # 4. Flowchart Step 2: Agent describes off-market fixer condition
    print("\n[3] Flowchart Step 2: Agent describes off-market fixer condition")
    msg2 = "It's an off-market fixer, needs a full roof and kitchen."
    res2 = bot_engine.evaluate_inbound_sms(test_agent, msg2)
    print(f"   Node: {res2.get('node')}")
    print(f"   Reply Suggestion: {res2.get('reply_text')}")
    assert res2.get("node") == "OFF_MARKET_PHOTOS"
    assert "photos" in res2.get("reply_text", "").lower()

    test_agent["bot_vetting"] = res2.get("state_updates")

    # 5. Flowchart Step 3: Agent replies about photos
    print("\n[4] Flowchart Step 3: Agent replies about photos")
    msg3 = "I don't have photos yet, just talked to the owner today."
    res3 = bot_engine.evaluate_inbound_sms(test_agent, msg3)
    print(f"   Node: {res3.get('node')}")
    print(f"   Reply Suggestion: {res3.get('reply_text')}")
    assert res3.get("node") == "OFF_MARKET_PRICE"
    assert "looking to get" in res3.get("reply_text", "").lower()

    test_agent["bot_vetting"] = res3.get("state_updates")
    # Preset estimated value / zestimate for testing
    test_agent["bot_vetting"]["zestimate"] = 300000.0

    # 6. Flowchart Step 4: Agent gives price $180k (Zestimate $300k = 60% -> GOLD DEAL!)
    print("\n[5] Flowchart Step 4: Agent gives asking price $180k (<=80% of Zestimate)")
    msg4 = "Seller wants $180,000 cash for quick close."
    res4 = bot_engine.evaluate_inbound_sms(test_agent, msg4)
    print(f"   Node: {res4.get('node')}")
    print(f"   Tier: {res4.get('tier_update')}")
    print(f"   Is Gold: {res4.get('state_updates', {}).get('is_gold')}")
    print(f"   Deal Ratio: {res4.get('state_updates', {}).get('price_to_zestimate_ratio')}")
    print(f"   Reply Suggestion: {res4.get('reply_text')}")
    assert res4.get("state_updates", {}).get("is_gold") == True, "Should be flagged as GOLD deal"
    assert res4.get("node") == "OFF_MARKET_GOLD_TIMELINE"
    assert "decision" in res4.get("reply_text", "").lower()

    test_agent["bot_vetting"] = res4.get("state_updates")

    # 7. Flowchart Step 5: Agent gives seller timeline
    print("\n[6] Flowchart Step 5: Agent gives seller timeline")
    msg5 = "Seller wants to close within the next 2-3 weeks, needs cash fast."
    res5 = bot_engine.evaluate_inbound_sms(test_agent, msg5)
    print(f"   Node: {res5.get('node')}")
    print(f"   Reply Suggestion: {res5.get('reply_text')}")
    assert "matt" in res5.get("reply_text", "").lower(), "Should propose underwriting call with Matt"
    assert res5.get("node") == "MATT_APPOINTMENT_REQUEST"

    test_agent["bot_vetting"] = res5.get("state_updates")

    # 8. Flowchart Step 6: Agent books appointment time with Matt
    print("\n[7] Flowchart Step 6: Agent confirms appointment time")
    msg6 = "Tomorrow at 2pm works great for us to speak with Matt."
    res6 = bot_engine.evaluate_inbound_sms(test_agent, msg6)
    print(f"   Node: {res6.get('node')}")
    print(f"   Appt Time: {res6.get('state_updates', {}).get('appointment_time')}")
    print(f"   Stage Update: {res6.get('stage_update')}")
    print(f"   Reply Suggestion: {res6.get('reply_text')}")
    assert "2pm" in res6.get("state_updates", {}).get("appointment_time", "").lower() or "tomorrow" in res6.get("state_updates", {}).get("appointment_time", "").lower()
    assert res6.get("stage_update") == "Appointment Confirmed"

    # 9. Test Scenario B: Turnkey / High Price -> Creative Terms Pivot
    print("\n[8] Scenario B: Turnkey over-asking listing -> Creative Terms")
    turnkey_agent = {
        "agent_id": "test_turnkey_002",
        "full_name": "Bob Turnkey",
        "first_name": "Bob",
        "phone": "(321) 555-0200",
        "pipeline_stage": "Contacted",
        "tier": "Tier 3: Inactive",
        "bot_vetting": {
            "current_node": "ON_MARKET_TURNKEY_CREATIVE"
        }
    }
    # If agent says yes to creative terms:
    msg_yes = "Yes, seller would be open to creative financing or seller finance."
    res_tk_yes = bot_engine.evaluate_inbound_sms(turnkey_agent, msg_yes)
    print(f"   Creative Yes Node: {res_tk_yes.get('node')}")
    print(f"   Creative Yes Reply: {res_tk_yes.get('reply_text')}")
    assert res_tk_yes.get("node") == "MATT_APPOINTMENT_REQUEST"

    # If agent says no to creative terms -> routes to Tier 2 pocket nurture:
    msg_no = "No, cash offers only. They won't do creative terms."
    res_tk_no = bot_engine.evaluate_inbound_sms(turnkey_agent, msg_no)
    print(f"   Creative No Node: {res_tk_no.get('node')}")
    print(f"   Tier Update: {res_tk_no.get('tier_update')}")
    print(f"   Creative No Reply: {res_tk_no.get('reply_text')}")
    assert "Tier 2" in res_tk_no.get("tier_update", "")
    assert res_tk_no.get("node") == "TIER_2_NURTURE_ASK"

    # 10. Test Scenario C: Opt-Out / Stop
    print("\n[9] Scenario C: Opt-out detection")
    stop_msg = "Please unsubscribe and remove me from your list, STOP."
    res_stop = bot_engine.evaluate_inbound_sms(test_agent, stop_msg)
    print(f"   Node: {res_stop.get('node')}")
    print(f"   Tier Update: {res_stop.get('tier_update')}")
    print(f"   Action: {res_stop.get('action')}")
    assert "Dead" in res_stop.get("tier_update", "")
    assert res_stop.get("action") == "OPT_OUT"

    # 11. Test Underdog Cadence Check
    print("\n[10] Underdog Macro Model Cadence Check")
    cadence_agent = {
        "agent_id": "test_cadence_003",
        "tier": "Tier 3: Inactive",
        "pipeline_stage": "Contacted",
        "outreach_history": [
            {"direction": "OUTBOUND", "timestamp": "2026-09-24 10:00:00", "message": "Hey are you still active?"}
        ]
    }
    cadence_res = bot_engine.check_campaign_cadence(cadence_agent)
    print(f"   Eligible: {cadence_res.get('eligible')}")
    print(f"   Campaign Step: {cadence_res.get('campaign_step')}")
    print(f"   Days Since: {cadence_res.get('days_since_outreach')}")
    assert cadence_res.get("eligible") == True
    assert cadence_res.get("campaign_step") == "FOLLOW_UP_1"

    print("\n==================================================")
    print("ALL BOT ENGINE TESTS PASSED PERFECTLY!")
    print("==================================================")

if __name__ == "__main__":
    test_full_pipeline()
