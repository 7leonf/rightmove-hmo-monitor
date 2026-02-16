"""
HMO Investment Opportunity Finder - Web Scraping Version
Updated 2026: Fixed syntax and updated selectors for modern Rightmove layout.
"""

import requests
from bs4 import BeautifulSoup
import json
import openpyxl
from datetime import datetime
import re
import os
from collections import defaultdict
import time

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
EXCEL_FILE = 'Masterkey.xlsx'

# Search URLs for Brighton & Hove (no price filter, sorted by newest)
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
        
        landlords = defaultdict(lambda: {
            'name': '',
            'properties': [],
            'wards': set(),
            'total_bedrooms': 0,
            'property_count': 0,
            'agent': ''
        })
        
        for row in ws.iter_rows(min_row=2, values_only=True):
            applicant_name = row[6]
            property_address = row[3]
            ward = row[4]
            bedrooms = row[14]
            agent = row[8]
            
            if applicant_name:
                landlord = landlords[applicant_name]
                landlord['name'] = applicant_name
                landlord['properties'].append(property_address)
                landlord['wards'].add(ward)
                landlord['property_count'] += 1
                if bedrooms:
                    landlord['total_bedrooms'] += bedrooms
                if agent and not landlord['agent']:
                    landlord['agent'] = agent
        
        wb.close()
        for landlord in landlords.values():
            landlord['wards'] = list(landlord['wards'])
        return dict(landlords)
    except Exception as e:
        print(f"❌ Error loading Excel: {e}")
        return {}

def scrape_rightmove_page(url):
    """Scrape property listings using updated 2026 selectors"""
    properties = []
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Referer': 'https://www.rightmove.co.uk/property-for-sale/find.html',
        'Connection': 'keep-alive'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"   ⚠️  HTTP {response.status_code} for URL")
            return properties
        
        soup = BeautifulSoup(response.text, 'html.parser')
        property_cards = soup.find_all('div', class_='l-searchResult')
        
        if not property_cards:
            property_cards = soup.find_all('div', attrs={'data-test': re.compile(r'propertyCard-\d+')})
        
        print(f"   Found {len(property_cards)} property cards")
        
        for card in property_cards:
            try:
                link_elem = card.find('a', class_='propertyCard-link') or card.find('a', href=True)
                if not link_elem: continue
                
                href = link_elem.get('href', '')
                id_match = re.search(r'properties/(\d+)', href)
                prop_id = id_match.group(1) if id_match else card.get('id', '').replace('property-', '')
                
                if not prop_id: continue
                
                title_elem = card.find('address', class_='propertyCard-address')
                title = title_elem.get_text(strip=True) if title_elem else ""
                
                price_elem = card.find('div', class_='propertyCard-priceValue') or card.find('span', attrs={'data-test': 'property-price'})
                price = price_elem.get_text(strip=True) if price_elem else 'POA'
                
                desc_elem = card.find('span', attrs={'data-test': 'property-description'})
                description = desc_elem.get_text(strip=True) if desc_elem else ''
                
                bedrooms = 0
                bed_match = re.search(r'(\d+)\s+bed', card.get_text(), re.IGNORECASE)
                if bed_match:
                    bedrooms = int(bed_match.group(1))
                
                properties.append({
                    'id': prop_id,
                    'title': title,
                    'price': price,
                    'description': description,
                    'link': f"https://www.rightmove.co.uk/properties/{prop_id}",
                    'bedrooms': bedrooms
                })
            except Exception:
                continue
    except Exception as e:
        print(f"   ❌ Error: {e}")
    return properties

def extract_postcode(address):
    postcode_pattern = r'BN\d+\s*\d+[A-Z]{2}'
    match = re.search(postcode_pattern, address, re.IGNORECASE)
    return match.group(0).upper() if match else None

def get_ward_from_postcode(postcode):
    if not postcode: return []
    ward_map = {
        'BN1': ['West Hill & North Laine', 'Regency', 'Queens Park'],
        'BN2': ['Hanover & Elm Grove', 'Kemptown', 'Queens Park', 'Moulsecoomb & Bevendean'],
        'BN3': ['Brunswick & Adelaide', 'Goldsmid', 'Central Hove', 'Wish'],
        'BN41': ['Portslade'],
        'BN42': ['Southwick'],
    }
    return ward_map.get(postcode[:3], [])

def assess_hmo_potential(property_data):
    description = property_data.get('description', '').lower()
    title = property_data.get('title', '').lower()
    bedrooms = property_data.get('bedrooms', 0)
    score = 0
    reasons = []
    
    if bedrooms >= 5:
        score += 30
        reasons.append(f"{bedrooms} bedrooms")
    elif bedrooms >= 3:
        score += 20
        reasons.append(f"{bedrooms} bedrooms")
    
    hmo_keywords = {'student': 10, 'sharers': 15, 'hmo': 30, 'investment': 10}
    for kw, pts in hmo_keywords.items():
        if kw in description or kw in title:
            score += pts
            reasons.append(f"Mentions '{kw}'")
    return score, reasons

def extract_epc_rating(property_data):
    epc_pattern = r'EPC\s+(?:rating\s+)?([A-G])'
    match = re.search(epc_pattern, property_data.get('description', ''), re.IGNORECASE)
    return match.group(1).upper() if match else None

def is_low_epc(epc_rating):
    return epc_rating in ['D', 'E', 'F', 'G']

def find_matching_landlords(property_data, landlords):
    matches = []
    postcode = extract_postcode(property_data.get('title', ''))
    wards = get_ward_from_postcode(postcode)
    
    for name, info in landlords.items():
        score = 0
        reasons = []
        for ward in wards:
            if ward in info['wards']:
                score += 30
                reasons.append(f"Owns in {ward}")
        if info['property_count'] >= 3:
            score += 20
        if score >= 20:
            matches.append({
                'landlord': name, 
                'score': score, 
                'reasons': reasons, 
                'portfolio_size': info['property_count'], 
                'agent': info['agent']
            })
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:5]

def send_telegram_alert(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'HTML'}
    try:
        return requests.post(url, data=data, timeout=10).status_code == 200
    except:
        return False

def format_opportunity_alert(prop, hmo_score, hmo_reasons, epc, matches):
    msg = f"🏠 <b>INVESTMENT FOUND!</b>\n\n📍 {prop['title']}\n💰 {prop['price']}\n🔗 <a href='{prop['link']}'>View</a>\n"
    if epc: msg += f"⚡ EPC: {epc}\n"
    if hmo_score > 0:
        msg += f"\n🏘️ <b>HMO Score: {hmo_score}</b>\n"
        for r in hmo_reasons[:2]: msg += f" • {r}\n"
    if matches:
        msg += f"\n👥 <b>Potential Buyers:</b>\n"
        for m in matches[:2]: msg += f"<b>{m['landlord']}</b> (Match: {m['score']}%)\n"
    return msg

def load_seen_properties():
    try:
        with open('seen_properties.json', 'r') as f: return set(json.load(f))
    except: return set()

def save_seen_properties(seen_ids):
    with open('seen_properties.json', 'w') as f: json.dump(list(seen_ids), f)

def main():
    print(f"🔍 Starting Finder at {datetime.now()}")
    landlords = load_landlord_database()
    seen = load_seen_properties()
    all_props = []
    
    for url in SEARCH_URLS:
        print(f"📡 Scraping: {url[:60]}...")
        all_props.extend(scrape_rightmove_page(url))
        time.sleep(2)
    
    new_found = 0
    for prop in all_props:
        p_id = prop.get('id')
        if not p_id or p_id in seen: continue
        
        score, reasons = assess_hmo_potential(prop)
        epc = extract_epc_rating(prop)
        
        if is_low_epc(epc) or score >= 25:
            matches = find_matching_landlords(prop, landlords)
            if matches:
                if send_telegram_alert(format_opportunity_alert(prop, score, reasons, epc, matches)):
                    new_found += 1
        seen.add(p_id)
    
    save_seen_properties(seen)
    print(f"✨ Complete! New opportunities found: {new_found}")

if __name__ == "__main__":
    main()
