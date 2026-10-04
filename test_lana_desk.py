"""
Comprehensive Verification Test Suite for Lana Desk (On-Market Infill Land Specialist)
Tests all updated core capabilities:
1. Infill targeting filters (Acreage, DOM, Zoning, Remarks; removal of rigid $80k floor)
2. Residual land value formula:
   max_payable = finished_value - (build_cost_psf * planned_sqft) - profit - fees
   Primary: offer = max_payable - $10,000 buffer
   Fallback: offer = 60% list price when comp data is thin
   Negotiation: step up in $2k-$3k increments if countered
3. Universal Florida DOR SDF parser (67 counties) & Multi-State build costs (Orlando, Tampa, Jax, Dallas, Houston, Atlanta)
4. Streamlined Lana Engine:
   - Direct Cash Offer Opener (default 21-day close, no 20-questions survey, no 'Reply STOP')
   - Dual LOI Delivery (SMS and Email)
   - Counter offer negotiation ($2k-$3k step-ups)
   - Firm price (firm expiration date, no 'our offer stands')
   - Land Math Drop
   - Builder credentials
5. Friday follow-up sequence ("Would your client reconsider my offer of $X?")
6. Multi-lot agent consolidation package
7. Hyphen sanitization (strips em/en dashes, keeps plain hyphens like '21-day')
8. Golden training scenarios & deterministic polisher bypass
"""

import os
import sys
import json
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.lana_engine import (
    passes_infill_filters,
    calculate_residual_land_value,
    get_build_cost_psf,
    strip_hyphens_for_sms,
    step_up_counter_offer,
    lana_engine
)
from src.sdf_parser import (
    FL_DOR_COUNTY_MAP,
    FLORIDA_COUNTIES,
    COUNTY_TO_DOR_CODE,
    get_county_code_from_filename,
    load_land_comps
)
from src.bot_engine import (
    STANDARD_TRAINING_SCENARIOS,
    COLD_OPENER_NODES,
    polish_reply_with_gemini
)

passed = 0
total = 0

def assert_test(name: str, condition: bool, details: str = ""):
    global passed, total
    total += 1
    if condition:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}: {details}")

def run_lana_tests():
    global passed, total
    passed = 0
    total = 0

    print("\n================== 1. INFILL TARGETING FILTERS TEST ==================")
    # Valid infill lot
    valid_lot = {
        "address": "123 Infill Way",
        "lot_acres": 0.22,
        "lot_sqft": 9583,
        "list_price": 115000,
        "days_on_market": 72,
        "zoning": "R-2 Residential Single Family",
        "remarks": "Great infill lot between two beautiful modern homes. Utilities at road."
    }
    passes, reason = passes_infill_filters(valid_lot)
    assert_test("Standard infill lot passes filters", passes, str(reason))

    # Large lot (>0.50 AC)
    large_lot = dict(valid_lot, lot_acres=1.5, lot_sqft=65340)
    passes, reason = passes_infill_filters(large_lot)
    assert_test("Acreage > 0.50 fails infill filter", not passes and any("ceiling" in r or "exceeds" in r for r in reason), str(reason))

    # Tiny lot (<4,000 sqft / 0.08 AC)
    tiny_lot = dict(valid_lot, lot_acres=0.05, lot_sqft=2178)
    passes, reason = passes_infill_filters(tiny_lot)
    assert_test("Acreage < 4,000 sqft fails infill filter", not passes and any("minimum" in r or "below" in r for r in reason), str(reason))

    # Secondary market lot at $45,000 (Brevard / Jacksonville rule: no rigid $80k rejection)
    brevard_lot = dict(valid_lot, list_price=45000)
    passes_brevard, reason_b = passes_infill_filters(brevard_lot)
    assert_test("Secondary market lot at $45,000 passes infill filter", passes_brevard, str(reason_b))

    # Nominal sanity floor (<$10,000)
    scam_lot = dict(valid_lot, list_price=5000)
    passes_scam, reason_s = passes_infill_filters(scam_lot)
    assert_test("Nominal price < $10,000 fails sanity floor", not passes_scam and any("sanity" in r.lower() or "floor" in r.lower() for r in reason_s), str(reason_s))

    # Low DOM (<60 DOM floor)
    fresh_lot = dict(valid_lot, days_on_market=15)
    passes, reason = passes_infill_filters(fresh_lot)
    assert_test("DOM < 60 days fails floor filter", not passes and any("dom" in r.lower() or "threshold" in r.lower() for r in reason), str(reason))

    # Commercial zoning
    comm_lot = dict(valid_lot, zoning="C-3 Heavy Commercial")
    passes, reason = passes_infill_filters(comm_lot)
    assert_test("Commercial zoning fails residential filter", not passes and any("zoning" in r.lower() for r in reason), str(reason))

    # Conservation / Unbuildable remarks
    wetland_lot = dict(valid_lot, remarks="Wetland conservation easement. Unbuildable parcel.")
    passes, reason = passes_infill_filters(wetland_lot)
    assert_test("Conservation / unbuildable remarks fails filter", not passes and any("conservation" in r.lower() or "unbuildable" in r.lower() for r in reason), str(reason))

    # Floodway remarks
    floodway_lot = dict(valid_lot, remarks="Property sits directly in designated floodway AE.")
    passes, reason = passes_infill_filters(floodway_lot)
    assert_test("Floodway remarks fails filter", not passes and any("floodway" in r.lower() for r in reason), str(reason))

    print("\n================== 2. RESIDUAL LAND UNDERWRITING MATH TEST ==================")
    # Formula: max_payable = finished_value - (build_cost_psf * planned_sqft) - profit - fees
    # Finished: $450k, 2000 sqft @ $165/sqft ($330,000), 18% profit ($81,000), 4% fees ($18,000)
    # Total deductions = $429,000 -> Max Payable = $21,000
    lot_math_test = {
        "list_price": 100000,
        "county": "ORANGE"
    }
    uw = calculate_residual_land_value(
        lot=lot_math_test,
        planned_sqft=2000,
        finished_newbuild_value=450000,
        builder_profit_pct=0.18,
        fees_pct=0.04
    )
    assert_test("Build cost calculated correctly ($330,000)", uw["total_build_cost"] == 330000, str(uw["total_build_cost"]))
    assert_test("Builder margin calculated correctly ($81,000)", uw["builder_margin_dollars"] == 81000, str(uw["builder_margin_dollars"]))
    assert_test("Fees calculated correctly ($18,000)", uw["fees_dollars"] == 18000, str(uw["fees_dollars"]))
    assert_test("Residual max payable matches formula ($21,000)", uw["max_payable"] == 21000, str(uw["max_payable"]))
    
    # Primary rule: offer = max_payable - $10,000 buffer = $11,000
    assert_test("Primary offer = max_payable - $10,000 buffer ($11,000)", uw["offer_price"] == 11000, str(uw["offer_price"]))
    assert_test("Viable lot passes send rule", uw["passes_send_rule"] is True, str(uw["passes_send_rule"]))

    # Negotiation step up test ($2k-$3k steps up to max_payable)
    stepped = step_up_counter_offer(uw["offer_price"], uw["max_payable"], step=2500.0)
    assert_test("Step-up counter offer increases by $2,500 ($13,500)", stepped == 13500, str(stepped))
    stepped_capped = step_up_counter_offer(20000, uw["max_payable"], step=2500.0)
    assert_test("Step-up counter offer caps at max_payable ($21,000)", stepped_capped == 21000, str(stepped_capped))

    # Thin comp fallback test (offer = 60% of list price)
    uw_fallback = calculate_residual_land_value(
        lot=lot_math_test,
        planned_sqft=2000,
        finished_newbuild_value=450000,
        force_fallback=True
    )
    assert_test("Fallback offer = 60% of list price ($60,000)", uw_fallback["offer_price"] == 60000, str(uw_fallback["offer_price"]))

    print("\n================== 3. MULTI-STATE COMP & BUILD COSTS TEST ==================")
    from src.sdf_parser import COUNTY_TO_DOR_CODE
    unique_counties = len(set(FLORIDA_COUNTIES.values()))
    assert_test("DOR County dictionary covers all 67 Florida counties", unique_counties == 67, f"Counties: {unique_counties}")
    assert_test("Orange County correctly mapped to code 58", COUNTY_TO_DOR_CODE.get("ORANGE") == "58", str(COUNTY_TO_DOR_CODE.get("ORANGE")))

    # Verify Multi-State Build Costs Table
    c_orl, _ = get_build_cost_psf("ORANGE")
    assert_test("Orlando build cost loaded ($165/sqft)", c_orl == 165, str(c_orl))
    c_dal, _ = get_build_cost_psf("DALLAS")
    assert_test("Dallas build cost loaded ($155/sqft)", c_dal == 155, str(c_dal))
    c_hou, _ = get_build_cost_psf("HARRIS")
    assert_test("Houston build cost loaded ($145/sqft)", c_hou == 145, str(c_hou))
    c_atl, _ = get_build_cost_psf("FULTON")
    assert_test("Atlanta build cost loaded ($160/sqft)", c_atl == 160, str(c_atl))

    # Verify filename code extraction
    co_code = get_county_code_from_filename("SDF58F202601.csv")
    assert_test("Extracts county code 58 from SDF58F202601.csv", co_code == "58", str(co_code))

    # Check parsed land comps data
    comps_data = load_land_comps()
    assert_test("Parsed land comps file exists and has counties", len(comps_data) > 0, f"Found {len(comps_data)} counties")
    if "ORANGE" in comps_data:
        orange_comps = comps_data["ORANGE"]
        assert_test("Orange County has vacant land sales", orange_comps.get("total_vacant_sales", 0) > 1000, str(orange_comps.get("total_vacant_sales")))
        assert_test("Orange County has SFH comps", orange_comps.get("total_sfh_sales", 0) > 10000, str(orange_comps.get("total_sfh_sales")))

    print("\n================== 4. STREAMLINED LANA ENGINE & COPY ==================")
    test_lot_context = {
        "id": "lot_test_101",
        "address": "4122 Michigan Ave",
        "agent_name": "Carlos Martinez",
        "list_price": 120000,
        "county": "ORANGE",
        "close_days": 21,
        "underwriting": {
            "offer_price": 72000,
            "max_payable": 85000,
            "finished_newbuild_value": 460000,
            "build_cost_psf": 165,
            "planned_sqft": 2000
        }
    }

    # 1. Direct Cash Offer Opener
    opener = lana_engine.generate_opener_sms(test_lot_context)
    assert_test("Opener addresses listing agent Carlos", "Carlos" in opener, opener)
    assert_test("Opener references Michigan Ave", "Michigan Ave" in opener, opener)
    assert_test("Opener presents cash offer ($72,000)", "$72,000" in opener, opener)
    assert_test("Opener confirms 21-day close", "21-day" in opener or "21 day" in opener, opener)
    assert_test("Opener offers contract sent over", "contract" in opener.lower(), opener)
    assert_test("Opener has NO 'Reply STOP' compliance text", "Reply STOP" not in opener, opener)
    assert_test("Opener strips em-dashes for SMS", "—" not in opener, opener)

    # 2. Dual LOI Delivery (SMS)
    loi_sms = lana_engine.generate_loi_sms(test_lot_context)
    assert_test("LOI SMS text contains purchase price", "$72,000" in loi_sms, loi_sms)
    assert_test("LOI SMS text contains 21-day close", "21" in loi_sms, loi_sms)
    assert_test("LOI SMS text contains feasibility terms", "Feasibility" in loi_sms, loi_sms)

    # 3. Agent Asks for Written LOI -> Channel Choice
    send_loi_reply = lana_engine.evaluate_inbound("Send over the contract so I can review with seller.", test_lot_context)
    assert_test("LOI request routes to LANA_SEND_LOI", send_loi_reply["node"] == "LANA_SEND_LOI", send_loi_reply["node"])
    assert_test("LOI reply offers text or email choice", "text" in send_loi_reply["suggested_reply"] and "email" in send_loi_reply["suggested_reply"], send_loi_reply["suggested_reply"])

    # 4. Counter-Offer Negotiation -> Steps Up in $2k-$3k
    counter_reply = lana_engine.evaluate_inbound("Can your buyer come up a bit? Seller wants more.", test_lot_context)
    assert_test("Counter request routes to LANA_COUNTER_OFFER", counter_reply["node"] == "LANA_COUNTER_OFFER", counter_reply["node"])
    assert_test("Counter reply steps up to $74,500", "$74,500" in counter_reply["suggested_reply"], counter_reply["suggested_reply"])

    # 5. Firm Price Pushback -> 5-Day Expiration (No Standing Offer Language)
    firm_reply = lana_engine.evaluate_inbound("Seller is firm on price at $120k. No discounts.", test_lot_context)
    assert_test("Firm price routed to LANA_FIRM_PRICE", firm_reply["node"] == "LANA_FIRM_PRICE", firm_reply["node"])
    assert_test("Firm price response carries 5 business days validity", "5 business days" in firm_reply["suggested_reply"], firm_reply["suggested_reply"])
    assert_test("Firm price response has NO 'offer stands' phrasing", "offer stands" not in firm_reply["suggested_reply"], firm_reply["suggested_reply"])

    # 6. Why So Low -> Land Math Drop
    math_reply = lana_engine.evaluate_inbound("Why is your offer so low? That makes no sense.", test_lot_context)
    assert_test("Why so low routed to LANA_MATH_DROP", math_reply["node"] == "LANA_MATH_DROP", math_reply["node"])
    assert_test("Math Drop explains permit & structure build costs", "build" in math_reply["suggested_reply"].lower() or "sqft" in math_reply["suggested_reply"].lower(), math_reply["suggested_reply"])
    assert_test("Math Drop preserves full figures", bool(re.search(r'\$\d{2,3},\d{3}', math_reply["suggested_reply"])), math_reply["suggested_reply"])

    # 7. Wholesaler Vetting -> Builder Credentials
    builder_reply = lana_engine.evaluate_inbound("Are you an actual builder or just another wholesaler?", test_lot_context)
    assert_test("Wholesaler vetting routed to LANA_BUILDER_CREDS", builder_reply["node"] == "LANA_BUILDER_CREDS", builder_reply["node"])
    assert_test("Builder reply confirms verified proof of funds", "funds" in builder_reply["suggested_reply"].lower(), builder_reply["suggested_reply"])

    # 8. Identity -> Local Builder Partner
    id_reply = lana_engine.evaluate_inbound("Who is this and what company are you with?", test_lot_context)
    assert_test("Identity routed to LANA_IDENTITY", id_reply["node"] == "LANA_IDENTITY", id_reply["node"])
    assert_test("Identity confirms Lana name", "Lana" in id_reply["suggested_reply"], id_reply["suggested_reply"])

    print("\n================== 5. FRIDAY SEQUENCE & AGENT CONSOLIDATION ==================")
    # Friday Sequence
    friday_seq = lana_engine.generate_friday_sequence([test_lot_context])
    assert_test("Friday sequence returns active items", len(friday_seq) == 1, str(len(friday_seq)))
    if friday_seq:
        friday_sms = friday_seq[0]["friday_sms"]
        assert_test("Friday text addresses agent Carlos", "Carlos" in friday_sms, friday_sms)
        assert_test("Friday text asks if Michigan Ave still available", "Michigan Ave" in friday_sms, friday_sms)
        assert_test("Friday text asks to reconsider offer of $72,000", "reconsider" in friday_sms.lower() and "$72,000" in friday_sms, friday_sms)
        assert_test("Friday text has NO 'Reply STOP' compliance text", "Reply STOP" not in friday_sms, friday_sms)

    # Multi-Lot Agent Consolidation
    second_lot = {
        "id": "lot_test_102",
        "address": "4128 Michigan Ave",
        "agent_name": "Carlos Martinez",
        "list_price": 110000,
        "county": "ORANGE",
        "close_days": 21,
        "underwriting": {
            "offer_price": 66000,
            "max_payable": 80000
        }
    }
    consolidation = lana_engine.consolidate_agent_listings("Carlos Martinez", [test_lot_context, second_lot])
    assert_test("Consolidation bundles 2 lots", consolidation["lot_count"] == 2, str(consolidation["lot_count"]))
    assert_test("Consolidation calculates combined offer ($138,000)", consolidation["total_offer"] == 138000, str(consolidation["total_offer"]))
    assert_test("Consolidation confirms 21-day close", "21-day" in consolidation["sms_text"] or "21 day" in consolidation["sms_text"], consolidation["sms_text"])

    print("\n================== 6. HYPHEN & EM-DASH SANITIZATION TEST ==================")
    raw_sample = "Reviewed numbers — I'll be at $72,000 cash with a 21-day close."
    sanitized = strip_hyphens_for_sms(raw_sample)
    assert_test("Em-dash (—) stripped from text", "—" not in sanitized, sanitized)
    assert_test("Plain hyphen preserved in '21-day'", "21-day" in sanitized, sanitized)

    print("\n================== 7. GOLDEN TRAINING & BYPASS TEST ==================")
    lana_scenarios = [s for s in STANDARD_TRAINING_SCENARIOS if s.get("agent_desk") == "LANA"]
    assert_test("8 LANA training scenarios defined in STANDARD_TRAINING_SCENARIOS", len(lana_scenarios) == 8, f"Found {len(lana_scenarios)}")
    assert_test("LANA_OPENING_HOOK in COLD_OPENER_NODES", "LANA_OPENING_HOOK" in COLD_OPENER_NODES, str(COLD_OPENER_NODES))

    for sc in lana_scenarios:
        assert_test(f"Scenario '{sc.get('node')}' has NO 'Reply STOP'", "Reply STOP" not in sc.get("default_suggestion", ""), sc.get("node"))
        assert_test(f"Scenario '{sc.get('node')}' has NO 'offer stands'", "offer stands" not in sc.get("default_suggestion", "").lower(), sc.get("node"))

    # Test deterministic bypass of Gemini polisher
    sample_hook = "Hi Carlos, my name is Lana. I'm interested in your listing on Michigan Ave. I reviewed the numbers I'll be at $72,000 cash with a 21-day close. If this is something your client is interested in, let me know and I can get a contract sent over."
    polished = polish_reply_with_gemini(
        node="LANA_OPENING_HOOK",
        template_reply=sample_hook,
        agent={"agent_desk": "LANA"},
        inbound_message=""
    )
    assert_test("polish_reply_with_gemini bypasses LANA_OPENING_HOOK deterministically", polished == sample_hook, polished)

    print(f"\n================== ALL TESTS COMPLETE: {passed}/{total} PASSED ==================")
    if passed == total:
        print("\nALL LANA DESK TESTS PASSED SUCCESSFULLY! 100% VERIFIED.\n")
        return True
    else:
        print(f"\nFAILURES DETECTED: {total - passed} tests failed.\n")
        return False

if __name__ == "__main__":
    success = run_lana_tests()
    sys.exit(0 if success else 1)
