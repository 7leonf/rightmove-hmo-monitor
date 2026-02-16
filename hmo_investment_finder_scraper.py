"""
HMO Investment Opportunity Finder - Professional Web Scraper
Updated 2026: Uses curl_cffi for TLS impersonation and JSON model extraction.
"""

import json
import openpyxl
from datetime import datetime
import re
import os
from collections import defaultdict
import time
import random
# Using curl_cffi to bypass TLS fingerprinting blocks on GitHub Actions
from curl_cffi import requests

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
EXCEL_FILE = 'Masterkey.xlsx'

# Search URLs for Brighton & Hove
SEARCH_URLS = [
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=3&radius=3.0&sortType=6&index=0",
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=4&radius=3.0&sortType=6&index=0",
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=5&radius=3.0&sortType=6&index=0",
]

def load_landlord_database():
    """Load landlord portfolio data from Excel"""
    try:
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb['Sheet1']
        landlords = defaultdict(lambda: {'name': '', 'properties': [], 'wards': set(), 'property_count': 0, 'agent': ''})
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            # Mapping: Applicant Name (Col 6), Property Address (Col 3), Ward (Col 4), Agent (Col 8)
            name, addr, ward, agent = row[6], row[3], row[4], row[8]
            if name:
                l = landlords[name]
                l['name'], l['agent'] = name, agent or l['agent']
                l['properties'].append(addr)
                l['wards'].add(ward)
                l['property_count'] += 1
        
        for l in landlords.values(): l['wards'] = list(l['wards'])
        return dict(landlords)
    except Exception as e:
        print(f"❌ Excel Load Error: {e}")
        return {}

def scrape_rightmove_page(url):
    """Bypasses blocks by extracting Rightmove's internal window.jsonModel"""
    properties = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.9",
        "Referer": "https://www.rightmove.co.uk/"
    }
    
    try:
        # Impersonate Chrome to bypass TLS fingerprinting
        resp = requests.get(url, headers=headers, impersonate="chrome120", timeout=25)
        if resp.status_code != 200:
            print(f"   ⚠️ Blocked: HTTP {resp.status_code}")
            return properties

        # Extract the JSON variable that powers the Rightmove React app
        json_pattern = r"window\.jsonModel\s*=\s*(\{.*?\})\s*</script>"
        match = re.search(json_pattern, resp.text)
        
        if match:
            data = json.loads(match.group(1))
            listings = data.get('properties', [])
            print(f"   ✅ Extracted {len(listings)} listings from JSON model")
            
            for p in listings:
                properties.append({
                    'id': str(p.get('id')),
                    'title': p.get('displayAddress', 'No Address'),
                    'price': p.get('price', {}).get('displayPrices', [{}])[0].get('displayPrice', 'POA'),
                    'description': p.get('summary', ''),
                    'link': f"https://www.rightmove.co.uk{p.get('propertyUrl')}",
                    'bedrooms': p.get('bedrooms', 0)
                })
        else:
            print("   ⚠️ No JSON data found. Rightmove may be blocking the request.")
    except Exception as e:
        print(f"   ❌ Scraping Error: {e}")
    return properties

def assess_hmo_potential(prop):
    """Calculates HMO suitability score"""
    desc, title, beds = prop['description'].lower(), prop['title'].lower(), prop['bedrooms']
    score = 0
    reasons = []
    
    if beds >= 5: score += 35; reasons.append(f"{beds} beds")
    elif beds >= 3: score += 20; reasons.append(f"{beds} beds")
    
    keywords = {'student': 15, 'sharers': 15, 'hmo': 30, 'investment': 10, 'ensuite': 10}
    for kw, pts in keywords.items():
        if kw in desc or kw in title:
            score += pts
            reasons.append(f"Found '{kw}'")
    return score, reasons

def find_matching_landlords(prop, landlords):
    """Matches properties to existing landlord portfolios"""
    matches = []
    for name, info in landlords.items():
        m_score = 0
        reasons = []
        if any(w.lower() in prop['title'].lower() for w in info['wards'] if w):
            m_score += 40; reasons.append("Existing portfolio area")
        if info['property_count'] >= 3:
            m_score += 20; reasons.append(f"Active ({info['property_count']} units)")
            
        if m_score >= 30:
            matches.append({'landlord': name, 'score': m_score, 'reasons': reasons, 'portfolio_size': info['property_count'], 'agent': info['agent']})
    
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:5]

def send_telegram_alert(msg):
    """Sends alert to Telegram"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': msg, 'parse_mode': 'HTML'}
    try:
        return requests.post(url, data=payload, timeout=10).status_code == 200
    except: return False

def main():
    print(f"🔍 Starting Finder: {datetime.now()}")
    landlords = load_landlord_database()
    
    try:
        with open('seen_properties.json', 'r') as f: seen = set(json.load(f))
    except: seen = set()
    
    all_props = []
    for url in SEARCH_URLS:
        print(f"📡 Scraping: {url[:60]}...")
        all_props.extend(scrape_rightmove_page(url))
        # Random delay to avoid bot detection
        time.sleep(random.uniform(7, 14))
    
    new_count = 0
    for prop in all_props:
        if prop['id'] in seen: continue
        
        h_score, h_reasons = assess_hmo_potential(prop)
        if h_score >= 25:
            matches = find_matching_landlords(prop, landlords)
            if matches:
                alert = f"🏠 <b>HMO OPPORTUNITY</b>\n\n📍 {prop['title']}\n💰 {prop['price']}\n🛏️ {prop['bedrooms']} Beds\n🔗 <a href='{prop['link']}'>View</a>\n\n<b>Top Match:</b> {matches[0]['landlord']}"
                if send_telegram_alert(alert): new_count += 1
        seen.add(prop['id'])
    
    with open('seen_properties.json', 'w') as f: json.dump(list(seen), f)
    print(f"✨ Complete. New found: {new_count}")

if __name__ == "__main__":
    main()
