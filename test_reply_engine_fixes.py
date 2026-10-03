"""
Test Suite for Agent Deal Hunter Reply Engine Fixes
Verifies all 8 core capabilities & bug fixes:
1. Price interpolation formatting
2. Deflection detection -> auto-pivot to ARV
3. Number-change re-route
4. Soft-no -> 30-day check-in task
5. Global opt-out suppression
6. Enhancer bypass on Brooke first-touch
7. Underwriting contradiction flag
8. Opener template rules (full street address, no off-MLS private intel, zero hyphens)
"""

import os
import sys
import re
import json

# Ensure project root in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.storage import (
    data_manager,
    add_global_opt_out,
    is_globally_opted_out,
    remove_global_opt_out,
    extract_reroute_phone_number,
    load_global_opt_outs
)
from src.sms_gateway import send_sms
from src.lauren_engine import lauren_engine, check_underwriting_contradictions
from src.bot_engine import bot_engine, polish_reply_with_gemini, load_golden_replies

def run_tests():
    passed = 0
    total = 0

    def assert_test(name, condition, details=""):
        nonlocal passed, total
        total += 1
        if condition:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            print(f"  [FAIL] {name}: {details}")

    print("\n================== 1. PRICE INTERPOLATION TEST ==================")
    # Check all golden dataset entries for Lauren Math Drop, High ARV Anchor, and Standing LOI
    goldens = load_golden_replies()
    lauren_goldens = [g for g in goldens if g.get("node") in ["LAUREN_MATH_DROP", "LAUREN_HIGH_ARV_ANCHOR", "LAUREN_STANDING_LOI"]]
    
    assert_test("Lauren goldens exist in training data", len(lauren_goldens) >= 3, f"Found {len(lauren_goldens)}")
    
    for g in lauren_goldens:
        text = g.get("final_approved_text", "")
        # Checks if there are thousands separators WITHOUT leading digits (e.g. " ,000" or " ,600")
        has_broken_digits = bool(re.search(r'(?<!\d),\d{3}', text))
        has_full_dollar = bool(re.search(r'\$\d{2,3},\d{3}', text))
        assert_test(f"Full price digits in {g.get('node')}", not has_broken_digits and has_full_dollar, f"Rendered text: {text}")

    # Test Math Drop Generation in lauren_engine
    mock_fixer = {
        "id": "test_fixer_1",
        "address": "123 Ocean Dr",
        "agent_name": "Sarah Jenkins",
        "agent_phone": "(321) 555-1122",
        "redfin_estimate": 300000.0,
        "sqft": 1400.0,
        "current_node": "ASKED_AGENT_ARV"
    }
    eval_res = lauren_engine.evaluate_inbound(mock_fixer, "Maybe around 260k if completely redone.")
    reply_text = eval_res.get("reply_text", "")
    assert_test("Math Drop includes full $260,000", "$260,000" in reply_text, f"Got: {reply_text}")
    assert_test("Math Drop does NOT drop leading digits", not bool(re.search(r'(?<!\d),\d{3}', reply_text)), f"Got: {reply_text}")
    assert_test("Math Drop has cash offer figure", "puts John right around $" in reply_text, f"Got: {reply_text}")

    print("\n================== 2. DEFLECTION DETECTION -> AUTO-PIVOT TO ARV ==================")
    # Test deflection pattern 1: "The inspection summary attached to the MLS listing covers everything they know."
    fixer_defl1 = {
        "id": "test_defl_1",
        "address": "456 Palm Breeze Rd",
        "agent_name": "Glenda Pruitt",
        "current_node": "OPENING_HOOK",
        "status": "NEW"
    }
    defl_res1 = lauren_engine.evaluate_inbound(fixer_defl1, "The inspection summary attached to the MLS listing covers everything they know.")
    assert_test("Deflection 1 auto-pivots to ASKED_AGENT_ARV", defl_res1.get("node") == "ASKED_AGENT_ARV", f"Node: {defl_res1.get('node')}")
    assert_test("Deflection 1 asks for resale ARV", "what do you realistically think it lists and sells for" in defl_res1.get("reply_text", ""), f"Reply: {defl_res1.get('reply_text')}")

    # Test deflection pattern 2: "That's all in the listing."
    fixer_defl2 = {
        "id": "test_defl_2",
        "address": "789 Pine Ct",
        "agent_name": "Bob Smith",
        "current_node": "ASKED_REPAIR_SCOPE",
        "status": "VETTING_REPAIRS"
    }
    defl_res2 = lauren_engine.evaluate_inbound(fixer_defl2, "That is all in the listing remarks.")
    assert_test("Deflection 2 auto-pivots to ASKED_AGENT_ARV", defl_res2.get("node") == "ASKED_AGENT_ARV", f"Node: {defl_res2.get('node')}")

    # Verify Golden dataset has Deflection under Repair Scope Extraction
    defl_golden = next((g for g in goldens if "Deflection" in str(g.get("tags", [])) or "inspection summary" in g.get("agent_inbound", "")), None)
    assert_test("Golden entry exists for Deflection", defl_golden is not None, f"Found: {defl_golden}")

    print("\n================== 3. NUMBER-CHANGE RE-ROUTE TEST ==================")
    inbound_new_num1 = "We use a different number for texting (813) 555-4321."
    extracted1 = extract_reroute_phone_number(inbound_new_num1)
    assert_test("Extracted Redfin texting number", extracted1 == "(813) 555-4321", f"Got: {extracted1}")

    inbound_new_num2 = "Please text my cell at 407-555-9876."
    extracted2 = extract_reroute_phone_number(inbound_new_num2)
    assert_test("Extracted cell re-route number", extracted2 == "(407) 555-9876", f"Got: {extracted2}")

    # Test fixer phone update on re-route
    fixer_reroute = {
        "id": "fixer_reroute_test",
        "address": "100 Coastal Hwy",
        "agent_phone": "(321) 555-0000",
        "current_node": "OPENING_HOOK"
    }
    lauren_engine.evaluate_inbound(fixer_reroute, "We use a different number for texting 813-777-8899.")
    assert_test("Fixer phone updated to new number", fixer_reroute.get("agent_phone") == "(813) 777-8899", f"Got: {fixer_reroute.get('agent_phone')}")
    assert_test("Original phone preserved in fixer record", fixer_reroute.get("rerouted_from_phone") == "(321) 555-0000", f"Got: {fixer_reroute.get('rerouted_from_phone')}")

    print("\n================== 4. SOFT-NO -> 30-DAY CHECK-IN TEST ==================")
    fixer_soft_no = {
        "id": "fixer_soft_no_test",
        "address": "200 Sunrise Blvd",
        "agent_name": "Mark Davis",
        "current_node": "OPENING_HOOK",
        "status": "NEW"
    }
    soft_res = lauren_engine.evaluate_inbound(fixer_soft_no, "Nothing right now, but I will keep you in mind if something pops up.")
    assert_test("Soft-no moves to 30_DAY_FOLLOWUP node", soft_res.get("node") == "30_DAY_FOLLOWUP", f"Node: {soft_res.get('node')}")
    assert_test("Soft-no auto-logs followup task", fixer_soft_no.get("followup_task") is not None, f"Task: {fixer_soft_no.get('followup_task')}")
    assert_test("Task has 30 day scheduled date", fixer_soft_no.get("followup_task", {}).get("type") == "30_DAY_CHECKIN", f"Task: {fixer_soft_no.get('followup_task')}")

    print("\n================== 5. GLOBAL OPT-OUT SUPPRESSION TEST ==================")
    test_opt_phone = "(407) 555-9988"
    remove_global_opt_out(test_opt_phone)
    assert_test("Initially not opted out", not is_globally_opted_out(test_opt_phone))

    # Opt-out on Lauren desk
    add_global_opt_out(test_opt_phone, source_desk="LAUREN", reason="Agent texted STOP")
    assert_test("Global opt-out recorded", is_globally_opted_out(test_opt_phone))

    # Attempt to send SMS
    send_res = send_sms(phone=test_opt_phone, message="Hey are you there?")
    assert_test("Outgoing SMS suppressed", send_res.get("status") == "suppressed", f"Result: {send_res}")
    assert_test("Suppression reason returned", "suppressed" in send_res.get("message", "").lower(), f"Msg: {send_res.get('message')}")

    # Clean up test opt-out
    remove_global_opt_out(test_opt_phone)
    assert_test("Opt-out removed cleanly", not is_globally_opted_out(test_opt_phone))

    print("\n================== 6. ENHANCER BYPASS ON BROOKE FIRST-TOUCH ==================")
    template_first_touch = "Hey Sarah, Brooke here. We buy 2 to 3 fixer projects a month in Melbourne. Got anything beat up?"
    mock_agent = {"full_name": "Sarah Realtor", "first_name": "Sarah"}
    
    for opener_node in ["OPENING_HOOK", "ENTRY_HOOK", "ENTRY_HOOK_AWAITING_REPLY", "FIRST_TOUCH", "BROOKE_COLD_ICEBREAKER", "icebreaker"]:
        result = polish_reply_with_gemini(opener_node, template_first_touch, mock_agent, "[Cold Outreach]")
        assert_test(f"Enhancer bypasses {opener_node}", result == template_first_touch, f"Got: {result}")

    print("\n================== 7. UNDERWRITING CONTRADICTION FLAG TEST ==================")
    fixer_contra = {
        "id": "fixer_contra_test",
        "address": "333 Magnolia St",
        "agent_name": "Linda Green",
        "repair_notes": "Roof is only 5 years old, HVAC was replaced in 2019, but needs full cosmetic gut.",
        "current_node": "ASKED_AGENT_ARV",
        "messages": [
            {"direction": "INBOUND", "text": "Roof is 5 years old and HVAC 2019 works great."}
        ]
    }
    has_contra, details = check_underwriting_contradictions(fixer_contra, "Comps are at $250k.")
    assert_test("Contradiction detected for 5-yr roof & 2019 HVAC", has_contra, f"Details: {details}")
    assert_test("Contradiction details mention Roof", any("Roof" in d for d in details), f"Details: {details}")
    assert_test("Contradiction details mention HVAC", any("HVAC" in d for d in details), f"Details: {details}")

    math_eval = lauren_engine.evaluate_inbound(fixer_contra, "Comps are sitting at $250k.")
    assert_test("Contradiction flagged in evaluate_inbound result", math_eval.get("contradiction_flag") is True, f"Eval: {math_eval}")

    print("\n================== 8. OPENER TEMPLATE RULES TEST ==================")
    fixer_prop = {
        "id": "prop_test_1",
        "address": "7158 Summit Dr",
        "city": "Winter Haven",
        "remarks": "Handyman special, cash only, needs roof."
    }
    hook = lauren_engine.generate_opening_hook(fixer_prop)
    assert_test("Opener includes full street address (7158 Summit Dr)", "7158 Summit Dr" in hook, f"Hook: {hook}")
    assert_test("Opener strictly has zero hyphens", "-" not in hook and "–" not in hook and "—" not in hook, f"Hook: {hook}")
    assert_test("Opener does NOT mention off-MLS private intel", "utilities off" not in hook.lower() and "lien" not in hook.lower(), f"Hook: {hook}")

    print(f"\n================== ALL TESTS COMPLETE: {passed}/{total} PASSED ==================\n")
    if passed == total:
        print("ALL TESTS PASSED SUCCESSFULLY!")
        return 0
    else:
        print(f"WARNING: {total - passed} test(s) failed.")
        return 1

if __name__ == "__main__":
    sys.exit(run_tests())
