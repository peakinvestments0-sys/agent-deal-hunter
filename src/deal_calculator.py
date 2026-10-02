from typing import Dict, Any

def calculate_buy_box(listing_price: float, estimated_value: float, sqft: int = 1500, year_built: int = 1980, condition: str = "average") -> Dict[str, Any]:
    """
    Computes investor acquisition metrics based on the transcript's 50-60% rule:
    - Conservative ARV / AVM
    - Estimated Rehab Budget based on sqft, age, and condition
    - 15% investor margin
    - Target Cash Offer Range (50% - 62% of ARV)
    - Max Allowable Offer (MAO)
    """
    arv = estimated_value if estimated_value > 0 else (listing_price if listing_price > 0 else 300000.0)
    
    # Rehab multiplier estimate
    current_year = 2026
    age = max(0, current_year - (year_built if year_built > 1900 else 1980))
    
    if condition.lower() in ["gut", "heavy", "poor", "original"]:
        rehab_per_sqft = 45.0 + (0.15 * age)
    elif condition.lower() in ["light", "cosmetic", "good"]:
        rehab_per_sqft = 20.0 + (0.05 * age)
    else:  # Average / Unknown
        rehab_per_sqft = 32.0 + (0.10 * age)
        
    sqft_clean = sqft if sqft and sqft > 400 else 1500
    est_rehab = round(sqft_clean * rehab_per_sqft, -2)
    
    # 15% target investor margin
    margin_15 = round(arv * 0.15, -2)
    
    # Target cash range (50% to 62% rule)
    target_low = round(arv * 0.50, -2)
    target_high = round(arv * 0.62, -2)
    
    # Formula-based MAO: ARV * 0.70 - Rehab
    formula_mao = round(max(0, (arv * 0.70) - est_rehab), -2)
    
    return {
        "arv": arv,
        "est_rehab": est_rehab,
        "rehab_per_sqft": round(rehab_per_sqft, 2),
        "target_low": target_low,
        "target_high": target_high,
        "formula_mao": formula_mao,
        "margin_15": margin_15
    }

def generate_setup_call_hud(agent_name: str, property_address: str, asking_price: float, 
                            buy_box: Dict[str, Any], condition_notes: str = "", 
                            occupancy: str = "Vacant", timeline: str = "ASAP") -> Dict[str, Any]:
    """
    Builds the dynamic 5-step Setup Call Negotiation HUD script
    tailored to the specific property, numbers, and agent relationship.
    """
    first_name = agent_name.split()[0] if agent_name else "there"
    arv_formatted = f"${buy_box['arv']:,.0f}"
    ask_formatted = f"${asking_price:,.0f}" if asking_price > 0 else "their asking price"
    low_formatted = f"${buy_box['target_low']:,.0f}"
    high_formatted = f"${buy_box['target_high']:,.0f}"
    rehab_formatted = f"${buy_box['est_rehab']:,.0f}"
    margin_formatted = f"${buy_box['margin_15']:,.0f}"

    steps = [
        {
            "step_num": 1,
            "title": "Acknowledge & Rapport",
            "objective": "Confirm receipt without arguing price",
            "script": f"Hey {first_name}, thanks for sending over {property_address}. I see your seller is hoping for around {ask_formatted}."
        },
        {
            "step_num": 2,
            "title": "Anchor the ARV (Make Them Say It)",
            "objective": "Get the agent's professional opinion on top market value",
            "script": f"Given the condition ({condition_notes or 'original state'}), what do you think it realistically fetches on the MLS once fully remodeled?"
        },
        {
            "step_num": 3,
            "title": "The Transparent Math Bridge",
            "objective": "Frame your offer around math, not an insult",
            "script": f"Got it. Here is how our fund runs our numbers: We buy 100% as-is for cash, but we have to budget roughly {rehab_formatted} for the renovation plus a 15% investor margin (~{margin_formatted}) for our capital partners. That's why we couldn't be at {ask_formatted}."
        },
        {
            "step_num": 4,
            "title": "The Wiggle-Room Probe",
            "objective": "Test for flexibility before drafting contracts",
            "script": f"Since the property is {occupancy.lower()} and they want a clean {timeline.lower()} exit, is there some flexibility on that number if we deliver a guaranteed 10 to 14-day cash close with zero inspection headaches?"
        },
        {
            "step_num": 5,
            "title": "Commission Protection Hook",
            "objective": "Motivate the agent to advocate for your offer",
            "script": f"And remember {first_name}, we're more than happy to have you represent us on the buy side so you can retain both sides of the commission on this transaction."
        }
    ]

    return {
        "agent_name": agent_name,
        "property_address": property_address,
        "target_range": f"{low_formatted} – {high_formatted}",
        "steps": steps
    }
