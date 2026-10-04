"""
Agent Contact Skip-Trace & Web Phone Lookup Service
Searches Realtor.com, DuckDuckGo, Bing, and Google search snippets for Realtor cell/office phone numbers.
"""

import urllib.request
import urllib.parse
import re
import html as html_lib
from typing import Dict, Any, List, Optional
from concurrent.futures import ThreadPoolExecutor

COMMON_TOLL_FREE = ('800-', '888-', '877-', '866-', '855-', '844-', '833-')
FLORIDA_AREA_CODES = {
    '239', '305', '321', '352', '386', '407', '561', '727', '772', '813', '850', '863', '904', '941', '954', '689'
}


def clean_phone_number(raw: str) -> Optional[str]:
    digits = re.sub(r'\D', '', str(raw))
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    if len(digits) == 10:
        area = digits[:3]
        prefix = digits[3:6]
        line = digits[6:]
        formatted = f"{area}-{prefix}-{line}"
        if not formatted.startswith(COMMON_TOLL_FREE):
            return formatted
    return None


def search_web_snippets(query: str) -> List[str]:
    phones = []
    # 1. DuckDuckGo HTML search
    try:
        url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote_plus(query)
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            raw_html = resp.read().decode('utf-8', errors='ignore')
            snippets = re.findall(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>', raw_html)
            titles = re.findall(r'<h2 class="result__title"[^>]*>([\s\S]*?)</h2>', raw_html)
            text = ' '.join(titles + snippets)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = html_lib.unescape(text)

            matches = re.findall(r'(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})', text)
            for m in matches:
                formatted = f"{m[0]}-{m[1]}-{m[2]}"
                if not formatted.startswith(COMMON_TOLL_FREE) and formatted not in phones:
                    phones.append(formatted)
    except Exception:
        pass

    return phones


def lookup_agent_contact(
    agent_name: str,
    brokerage: str = "",
    city: str = "Florida",
    address: str = ""
) -> Dict[str, Any]:
    """
    Looks up contact info for a Florida realtor using name, brokerage, city, and listing address.
    """
    clean_name = (agent_name or "").strip()
    if not clean_name or clean_name.lower() in ["listing agent", "agent", "realtor", "none", "n/a"]:
        return {
            "status": "error",
            "message": "Invalid agent name",
            "agent_name": clean_name,
            "phone": None,
            "candidates": []
        }

    clean_brokerage = (brokerage or "").strip()
    clean_city = (city or "Florida").strip()

    # Priority search queries
    queries = [
        f'"{clean_name}" "{clean_brokerage}" phone number',
        f'"{clean_name}" {clean_city} FL realtor phone',
        f'{clean_name} {clean_brokerage} {clean_city} realtor.com phone',
        f'"{clean_name}" "{clean_brokerage}" contact'
    ]
    if address:
        queries.insert(0, f'"{clean_name}" "{address}" phone')

    all_candidates = []

    for q in queries:
        found = search_web_snippets(q)
        for p in found:
            if p not in all_candidates:
                all_candidates.append(p)
        if all_candidates:
            break

    # Prioritize Florida area codes
    fl_phones = [p for p in all_candidates if p[:3] in FLORIDA_AREA_CODES]
    best_phone = fl_phones[0] if fl_phones else (all_candidates[0] if all_candidates else None)

    return {
        "status": "success" if best_phone else "not_found",
        "agent_name": clean_name,
        "brokerage": clean_brokerage,
        "city": clean_city,
        "phone": best_phone,
        "candidates": all_candidates
    }


def batch_lookup_fixer_phones(fixers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriches a list of fixers with missing phone numbers in parallel."""
    def _enrich_single(fixer):
        if fixer.get("agent_phone") and fixer.get("agent_phone").strip():
            return fixer

        name = fixer.get("agent_name", "")
        brokerage = fixer.get("brokerage", "")
        city = fixer.get("city", "Florida")
        address = fixer.get("address", "")

        res = lookup_agent_contact(name, brokerage, city, address)
        if res.get("phone"):
            fixer["agent_phone"] = res["phone"]
            fixer["phone_lookup_source"] = "WEB_SKIP_TRACE"

        return fixer

    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(_enrich_single, fixers))


def lookup_single_lot_contact(lot: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches a single infill lot listing:
    1. Scrapes Redfin listing page if redfin_url exists (gets photo_url, agent_name, brokerage, phone).
    2. If phone is missing or toll-free, executes web skip-trace via lookup_agent_contact.
    """
    from src.ingestion import scrape_redfin_agent_details
    redfin_url = (lot.get("redfin_url") or "").strip()
    if redfin_url and (not lot.get("photo_url") or not lot.get("agent_phone")):
        scraped = scrape_redfin_agent_details(redfin_url)
        if scraped.get("photo_url") and not lot.get("photo_url"):
            lot["photo_url"] = scraped["photo_url"]
        if scraped.get("agent_name") and (not lot.get("agent_name") or lot.get("agent_name") in ["Listing Agent", ""]):
            lot["agent_name"] = scraped["agent_name"]
        if scraped.get("brokerage") and (not lot.get("brokerage") or lot.get("brokerage") in ["Local Realty", "Brokerage", ""]):
            lot["brokerage"] = scraped["brokerage"]
        if scraped.get("agent_phone") and not lot.get("agent_phone"):
            lot["agent_phone"] = scraped["agent_phone"]
            lot["phone_lookup_source"] = "REDFIN_PAGE"

    phone = (lot.get("agent_phone") or "").strip()
    is_toll_free = any(phone.startswith(tf) for tf in COMMON_TOLL_FREE)
    if not phone or is_toll_free:
        name = lot.get("agent_name", "")
        brokerage = lot.get("brokerage", "")
        city = lot.get("city", "Florida")
        address = lot.get("address", "")
        res = lookup_agent_contact(name, brokerage, city, address)
        if res.get("phone"):
            lot["agent_phone"] = res["phone"]
            lot["phone_lookup_source"] = "WEB_SKIP_TRACE"

    return lot


def batch_lookup_lot_phones(lots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Enriches a list of infill lots with missing agent phones & photos in parallel."""
    with ThreadPoolExecutor(max_workers=6) as executor:
        return list(executor.map(lookup_single_lot_contact, lots))
