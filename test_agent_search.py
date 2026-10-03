import urllib.request
import urllib.parse
import re
import html as html_lib
import sys

sys.stdout.reconfigure(encoding='utf-8')

def lookup_agent_phone(agent_name: str, brokerage: str = "", city: str = "Florida") -> dict:
    if not agent_name or agent_name.lower() in ["listing agent", "agent", "realtor"]:
        return {"phone": None, "source": "None"}

    queries = [
        f'"{agent_name}" "{brokerage}" phone number',
        f'"{agent_name}" {city} FL realtor phone',
        f'{agent_name} {brokerage} {city} realtor.com'
    ]

    found_phones = []

    for query in queries:
        url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote_plus(query)
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                raw_html = resp.read().decode('utf-8', errors='ignore')
                snippets = re.findall(r'<a class="result__snippet"[^>]*>([\s\S]*?)</a>', raw_html)
                titles = re.findall(r'<h2 class="result__title"[^>]*>([\s\S]*?)</h2>', raw_html)
                text = ' '.join(titles + snippets)
                text = re.sub(r'<[^>]+>', ' ', text)
                text = html_lib.unescape(text)

                # Match US phone numbers
                phones = re.findall(r'(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})', text)
                for p in phones:
                    num = f"{p[0]}-{p[1]}-{p[2]}"
                    # Filter out toll-free numbers
                    if not num.startswith(('800-', '888-', '877-', '866-', '855-')):
                        if num not in found_phones:
                            found_phones.append(num)

                if found_phones:
                    break
        except Exception as e:
            pass

    return {
        "agent_name": agent_name,
        "brokerage": brokerage,
        "phones": found_phones,
        "best_phone": found_phones[0] if found_phones else None
    }

# Test with 3 real Florida agents
print("1:", lookup_agent_phone("Steven Smith", "Coldwell Banker", "Lakeland"))
print("2:", lookup_agent_phone("Randall Patrick", "Exp Realty", "Winter Haven"))
print("3:", lookup_agent_phone("Glenda Pruitt", "Coldwell Banker", "Winter Haven"))
print("4:", lookup_agent_phone("Gary Desmond", "Keller Williams", "Lakeland"))
