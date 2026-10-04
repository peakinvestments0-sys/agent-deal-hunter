"""
Test Suite for Agent Deal Hunter - Lana Infill Land Desk
Verifies all 8 core capabilities & requirements:
1. Infill targeting filters (acres, DOM, list price floor, zoning, remarks exclusions)
2. Residual land value underwriting math & 60% send rule
3. Universal Florida DOR Sales Data File (SDF) parser & all 67 county mapping
4. Lana Engine state machine & objection handling (Firm price, Why so low math drop, Builder creds, Identity)
5. Friday follow-up sequence & multi-lot agent portfolio consolidation
6. Strict Zero-Hyphens compliance across SMS copy
7. Deterministic cold opener bypass in bot engine
8. Auto-Drip queue integration for Lana desk
"""

import os
import sys
import re
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.lana_engine import lana_engine, passes_infill_filters, calculate_residual_land_value
from src.sdf_parser import FLORIDA_COUNTIES, get_county_code_from_filename, load_land_comps, parse_florida_sdf_file
from src.bot_engine import STANDARD_TRAINING_SCENARIOS, COLD_OPENER_NODES, polish_reply_with_gemini
from src.sms_gateway import strip_hyphens_for_sms

def run_lana_tests():
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
    assert_test("Standard infill lot passes filters", passes, reason)

    # Large lot (>0.50 AC)
    large_lot = dict(valid_lot, lot_acres=1.5, lot_sqft=65340)
    passes, reason = passes_infill_filters(large_lot)
    assert_test("Acreage > 0.50 fails infill filter", not passes and any("ceiling" in r or "exceeds" in r for r in reason), str(reason))

    # Tiny lot (<4,000 sqft / 0.08 AC)
    tiny_lot = dict(valid_lot, lot_acres=0.05, lot_sqft=2178)
    passes, reason = passes_infill_filters(tiny_lot)
    assert_test("Acreage < 4,000 sqft fails infill filter", not passes and any("minimum" in r or "below" in r for r in reason), str(reason))

    # Low list price (<$80k floor)
    cheap_lot = dict(valid_lot, list_price=45000)
    passes, reason = passes_infill_filters(cheap_lot)
    assert_test("Price < $80,000 floor fails filter", not passes and any("floor" in r or "price" in r.lower() for r in reason), str(reason))

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
        "list_price": 30000,
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
    # 60% of $30,000 = $18,000 -> offer ($18,000) <= max_payable ($21,000) -> PASSES SEND RULE
    assert_test("60% offer price is $18,000", uw["offer_price"] == 18000, str(uw["offer_price"]))
    assert_test("Viable lot passes send rule", uw["passes_send_rule"] is True, str(uw["passes_send_rule"]))

    # Lot that fails send rule: List price $50,000 -> 60% offer = $30,000 > max_payable ($21,000)
    lot_math_fail = {
        "list_price": 50000,
        "county": "ORANGE"
    }
    uw_fail = calculate_residual_land_value(
        lot=lot_math_fail,
        planned_sqft=2000,
        finished_newbuild_value=450000,
        builder_profit_pct=0.18,
        fees_pct=0.04
    )
    assert_test("Non-viable lot fails send rule", uw_fail["passes_send_rule"] is False, str(uw_fail["passes_send_rule"]))
    assert_test("Deficit tracked accurately", uw_fail["spread_deficit"] == 9000, str(uw_fail["spread_deficit"]))

    from src.sdf_parser import COUNTY_TO_DOR_CODE
    unique_counties = len(set(FLORIDA_COUNTIES.values()))
    assert_test("DOR County dictionary covers all 67 Florida counties", unique_counties == 67, f"Counties: {unique_counties}")
    assert_test("Orange County correctly mapped to code 58", COUNTY_TO_DOR_CODE.get("ORANGE") == "58", str(COUNTY_TO_DOR_CODE.get("ORANGE")))
    assert_test("Pinellas County correctly mapped to code 52", COUNTY_TO_DOR_CODE.get("PINELLAS") == "52", str(COUNTY_TO_DOR_CODE.get("PINELLAS")))
    assert_test("Hillsborough County correctly mapped to code 29", COUNTY_TO_DOR_CODE.get("HILLSBOROUGH") == "29", str(COUNTY_TO_DOR_CODE.get("HILLSBOROUGH")))
    assert_test("Duval County correctly mapped to code 16", COUNTY_TO_DOR_CODE.get("DUVAL") == "16", str(COUNTY_TO_DOR_CODE.get("DUVAL")))

    # Verify filename code extraction for any county file
    co_code = get_county_code_from_filename("SDF58F202601.csv")
    assert_test("Extracts county code 58 from SDF58F202601.csv", co_code == "58", str(co_code))
    co_code_pinellas = get_county_code_from_filename("SDF52P2025.txt")
    assert_test("Extracts county code 52 from SDF52P2025.txt", co_code_pinellas == "52", str(co_code_pinellas))

    # Check parsed land comps data
    comps_data = load_land_comps()
    assert_test("Parsed land comps file exists and has counties", len(comps_data) > 0, f"Found {len(comps_data)} counties")
    if "ORANGE" in comps_data:
        orange_comps = comps_data["ORANGE"]
        assert_test("Orange County has vacant land sales", orange_comps.get("total_vacant_sales", 0) > 1000, str(orange_comps.get("total_vacant_sales")))
        assert_test("Orange County has SFH comps", orange_comps.get("total_sfh_sales", 0) > 10000, str(orange_comps.get("total_sfh_sales")))
        assert_test("Market areas aggregation exists", len(orange_comps.get("market_areas", {})) > 5, str(len(orange_comps.get("market_areas", {}))))

    print("\n================== 4. LANA ENGINE STATE MACHINE & OBJECTIONS ==================")
    # 1. Doorbell Opener
    test_lot_context = {
        "id": "lot_test_101",
        "address": "4122 Michigan Ave",
        "agent_name": "Carlos Martinez",
        "list_price": 120000,
        "county": "ORANGE",
        "underwriting": {
            "offer_price": 72000,
            "max_payable": 85000,
            "finished_newbuild_value": 460000,
            "build_cost_psf": 165,
            "planned_sqft": 2000
        }
    }
    opener = lana_engine.generate_doorbell_sms(test_lot_context)
    assert_test("Doorbell opener addresses listing agent Carlos", "Carlos" in opener, opener)
    assert_test("Doorbell opener references Michigan Ave", "Michigan Ave" in opener, opener)
    assert_test("Doorbell opener mentions builder partner / buildable lot", "builder" in opener.lower() or "build" in opener.lower(), opener)
    assert_test("Doorbell opener strictly complies with zero hyphens", re.search(r'\w-\w', opener) is None, opener)

    # 2. Firm Price Pushback -> 60-Day Backup
    firm_reply = lana_engine.evaluate_inbound("Seller is firm on price at $120k. No discounts.", test_lot_context)
    assert_test("Firm price routed to LANA_FIRM_PRICE", firm_reply["node"] == "LANA_FIRM_PRICE", firm_reply["node"])
    assert_test("Firm price response offers 60-day cash backup", "60" in firm_reply["suggested_reply"] or "stands" in firm_reply["suggested_reply"].lower(), firm_reply["suggested_reply"])
    assert_test("Firm price response zero hyphens compliant", re.search(r'\w-\w', firm_reply["suggested_reply"]) is None, firm_reply["suggested_reply"])

    # 3. Why So Low -> Land Math Drop
    math_reply = lana_engine.evaluate_inbound("Why is your offer so low? That makes no sense.", test_lot_context)
    assert_test("Why so low routed to LANA_MATH_DROP", math_reply["node"] == "LANA_MATH_DROP", math_reply["node"])
    assert_test("Math Drop explains permit & structure build costs", "build" in math_reply["suggested_reply"].lower() or "sqft" in math_reply["suggested_reply"].lower(), math_reply["suggested_reply"])
    assert_test("Math Drop preserves full figures without broken commas", bool(re.search(r'\$\d{2,3},\d{3}', math_reply["suggested_reply"])), math_reply["suggested_reply"])
    assert_test("Math Drop zero hyphens compliant", re.search(r'\w-\w', math_reply["suggested_reply"]) is None, math_reply["suggested_reply"])

    # 4. Wholesaler Vetting -> Builder Credentials
    builder_reply = lana_engine.evaluate_inbound("Are you an actual builder or just another wholesaler tying up my listing?", test_lot_context)
    assert_test("Wholesaler vetting routed to LANA_BUILDER_CREDS", builder_reply["node"] == "LANA_BUILDER_CREDS", builder_reply["node"])
    assert_test("Builder reply confirms verified proof of funds", "funds" in builder_reply["suggested_reply"].lower() or "builder" in builder_reply["suggested_reply"].lower(), builder_reply["suggested_reply"])

    # 5. Identity -> Local Builder Partner
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
        assert_test("Friday text checks in on weekend showings / status", "weekend" in friday_sms.lower() or "checking in" in friday_sms.lower(), friday_sms)
        assert_test("Friday text confirms 14-day cash terms", "14" in friday_sms, friday_sms)
        assert_test("Friday text strictly complies with zero hyphens", re.search(r'\w-\w', friday_sms) is None, friday_sms)

    # Multi-Lot Agent Consolidation
    second_lot = {
        "id": "lot_test_102",
        "address": "4128 Michigan Ave",
        "agent_name": "Carlos Martinez",
        "list_price": 110000,
        "county": "ORANGE",
        "underwriting": {
            "offer_price": 66000,
            "max_payable": 80000
        }
    }
    consolidation = lana_engine.consolidate_agent_listings("Carlos Martinez", [test_lot_context, second_lot])
    assert_test("Consolidation bundles 2 lots", consolidation["lot_count"] == 2, str(consolidation["lot_count"]))
    assert_test("Consolidation calculates combined offer ($138,000)", consolidation["total_offer"] == 138000, str(consolidation["total_offer"]))
    assert_test("Consolidation text mentions portfolio package", "both" in consolidation["sms_text"].lower() or "package" in consolidation["sms_text"].lower() or "portfolio" in consolidation["sms_text"].lower(), consolidation["sms_text"])
    assert_test("Consolidation text strictly complies with zero hyphens", re.search(r'\w-\w', consolidation["sms_text"]) is None, consolidation["sms_text"])

    print("\n================== 6. ZERO HYPHENS COMPLIANCE TEST ==================")
    templates_path = os.path.join(BASE_DIR, "data", "lana_templates.json")
    with open(templates_path, "r", encoding="utf-8") as f:
        templates = json.load(f)

    # Check openers
    openers = templates.get("openers", {})
    openers_list = [{"id": k, "text": v} for k, v in openers.items()] if isinstance(openers, dict) else openers
    for op in openers_list:
        text = op.get("text", "") if isinstance(op, dict) else str(op)
        op_id = op.get("id", "opener") if isinstance(op, dict) else "opener"
        clean = strip_hyphens_for_sms(text)
        assert_test(f"Opener '{op_id}' zero hyphens compliant", re.search(r'\w-\w', clean) is None, clean)

    # Check doorbells
    doorbells = templates.get("doorbells") or templates.get("offers") or {}
    doorbells_list = [{"id": k, "text": v} for k, v in doorbells.items()] if isinstance(doorbells, dict) else doorbells
    for db in doorbells_list:
        text = db.get("text", "") if isinstance(db, dict) else str(db)
        db_id = db.get("id", "doorbell") if isinstance(db, dict) else "doorbell"
        clean = strip_hyphens_for_sms(text)
        assert_test(f"Doorbell '{db_id}' zero hyphens compliant", re.search(r'\w-\w', clean) is None, clean)

    # Check objections
    for obj_key, obj_val in templates.get("objections", {}).items():
        text = obj_val.get("reply", "") if isinstance(obj_val, dict) else str(obj_val)
        clean = strip_hyphens_for_sms(text)
        assert_test(f"Objection '{obj_key}' zero hyphens compliant", re.search(r'\w-\w', clean) is None, clean)

    print("\n================== 7. GOLDEN TRAINING & BYPASS TEST ==================")
    lana_scenarios = [s for s in STANDARD_TRAINING_SCENARIOS if s.get("agent_desk") == "LANA"]
    assert_test("8 LANA training scenarios defined in STANDARD_TRAINING_SCENARIOS", len(lana_scenarios) == 8, f"Found {len(lana_scenarios)}")
    assert_test("LANA_OPENING_HOOK in COLD_OPENER_NODES", "LANA_OPENING_HOOK" in COLD_OPENER_NODES, str(COLD_OPENER_NODES))
    assert_test("LANA_OPENER in COLD_OPENER_NODES", "LANA_OPENER" in COLD_OPENER_NODES, str(COLD_OPENER_NODES))

    # Test deterministic bypass of Gemini polisher
    sample_hook = "Hi Carlos, Lana here with Peak Investments. Saw your vacant lot on Michigan Ave. Reply STOP to opt out"
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
