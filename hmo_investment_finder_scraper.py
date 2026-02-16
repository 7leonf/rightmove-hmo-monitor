"""
HMO Investment Opportunity Finder - Web Scraping Version
Since Rightmove disabled RSS feeds, this version scrapes the search pages directly
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
    # 3+ bed properties
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=3&radius=3.0&sortType=6&index=0",
    # 4+ bed properties
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=4&radius=3.0&sortType=6&index=0",
    # 5+ bed properties  
    "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=5&radius=3.0&sortType=6&index=0",
]

def load_landlord_database():
    """Load landlord portfolio data from Excel"""
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
        applicant_name = row[6]  # Applicant Name
        property_address = row[3]  # Property Address
        ward = row[4]  # Ward Name
        bedrooms = row[14]  # Bedrooms
        agent = row[8]  # Agent Name
        
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
    
    # Convert sets to lists
    for landlord in landlords.values():
        landlord['wards'] = list(landlord['wards'])
    
    return dict(landlords)

def scrape_rightmove_page(url):
    """Scrape property listings from Rightmove search page"""
    properties = []
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            print(f"   ⚠️  HTTP {response.status_code} for {url[:80]}")
            return properties
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find property cards
        property_cards = soup.find_all('div', class_='propertyCard')
        
        if not property_cards:
            # Try alternative class names
            property_cards = soup.find_all('div', attrs={'data-test': 'property-card'})
        
        print(f"   Found {len(property_cards)} property cards")
        
        for card in property_cards:
            try:
                # Extract property ID
                prop_id = card.get('id', '')
                if not prop_id:
                    prop_id = card.get('data-property-id', '')
                
                # Extract title/address
                title_elem = card.find('h2', class_='propertyCard-title')
                if not title_elem:
                    title_elem = card.find('address', class_='propertyCard-address')
                title = title_elem.get_text(strip=True) if title_elem else ''
                
                # Extract price
                price_elem = card.find('div', class_='propertyCard-priceValue')
                price = price_elem.get_text(strip=True) if price_elem else 'POA'
                
                # Extract description
                desc_elem = card.find('span', attrs={'data-test': 'property-description'})
                if not desc_elem:
                    desc_elem = card.find('div', class_='propertyCard-description')
                description = desc_elem.get_text(strip=True) if desc_elem else ''
                
                # Extract link
                link_elem = card.find('a', class_='propertyCard-link')
                if not link_elem:
                    link_elem = card.find('a', href=True)
                
                link = ''
                if link_elem and link_elem.get('href'):
                    href = link_elem['href']
                    if href.startswith('/'):
                        link = f"https://www.rightmove.co.uk{href}"
                    else:
                        link = href
                
                # Extract property details (bedrooms, etc.)
                details_elem = card.find('div', class_='propertyCard-details')
                bedrooms = 0
                if details_elem:
                    bed_match = re.search(r'(\d+)\s+bed', details_elem.get_text(), re.IGNORECASE)
                    if bed_match:
                        bedrooms = int(bed_match.group(1))
                
                if prop_id and title:
                    properties.append({
                        'id': prop_id,
                        'title': title,
                        'price': price,
                        'description': description,
                        'link': link,
                        'bedrooms': bedrooms
                    })
            
            except Exception as e:
                print(f"   ⚠️  Error parsing property card: {e}")
                continue
        
    except Exception as e:
        print(f"   ❌ Error scraping page: {e}")
    
    return properties

def extract_postcode(address):
    """Extract UK postcode"""
    postcode_pattern = r'BN\d+\s*\d+[A-Z]{2}'
    match = re.search(postcode_pattern, address, re.IGNORECASE)
    return match.group(0).upper() if match else None

def get_ward_from_postcode(postcode):
    """Determine ward from postcode"""
    if not postcode:
        return []
    
    ward_map = {
        'BN1': ['West Hill & North Laine', 'Regency', 'Queens Park'],
        'BN2': ['Hanover & Elm Grove', 'Kemptown', 'Queens Park', 'Moulsecoomb & Bevendean'],
        'BN3': ['Brunswick & Adelaide', 'Goldsmid', 'Central Hove', 'Wish'],
        'BN41': ['Portslade'],
        'BN42': ['Southwick'],
    }
    
    prefix = postcode[:3]
    return ward_map.get(prefix, [])

def assess_hmo_potential(property_data):
    """Assess HMO potential"""
    description = property_data.get('description', '').lower()
    title = property_data.get('title', '').lower()
    bedrooms = property_data.get('bedrooms', 0)
    
    score = 0
    reasons = []
    
    # Bedroom count
    if bedrooms >= 5:
        score += 30
        reasons.append(f"{bedrooms} bedrooms (excellent for HMO)")
    elif bedrooms >= 3:
        score += 20
        reasons.append(f"{bedrooms} bedrooms (good for HMO)")
    
    # Keywords
    hmo_keywords = {
        'student': 10, 'sharers': 15, 'hmo': 30, 'rental income': 15,
        'investment': 10, 'multi': 10, 'separate': 5, 'ensuite': 10,
    }
    
    for keyword, points in hmo_keywords.items():
        if keyword in description or keyword in title:
            score += points
            reasons.append(f"Mentions '{keyword}'")
    
    # Property type
    if 'terraced' in description or 'terrace' in title:
        score += 5
        reasons.append("Terraced house (good for HMO conversion)")
    
    return score, reasons

def extract_epc_rating(property_data):
    """Extract EPC rating"""
    description = property_data.get('description', '')
    
    epc_pattern = r'EPC\s+(?:rating\s+)?([A-G])'
    match = re.search(epc_pattern, description, re.IGNORECASE)
    
    return match.group(1).upper() if match else None

def is_low_epc(epc_rating):
    """Check if EPC is below C"""
    if not epc_rating:
        return False
    return epc_rating in ['D', 'E', 'F', 'G']

def find_matching_landlords(property_data, landlords):
    """Find interested landlords"""
    matches = []
    
    property_postcode = extract_postcode(property_data.get('title', ''))
    property_wards = get_ward_from_postcode(property_postcode) if property_postcode else []
    
    for landlord_name, landlord_info in landlords.items():
        match_score = 0
        reasons = []
        
        # Same ward
        for ward in property_wards:
            if ward in landlord_info['wards']:
                match_score += 30
                reasons.append(f"Has properties in {ward}")
        
        # Active investor
        if landlord_info['property_count'] >= 3:
            match_score += 20
            reasons.append(f"Active investor ({landlord_info['property_count']} properties)")
        
        # Uses agent
        if landlord_info['agent']:
            match_score += 10
            reasons.append(f"Works with agent: {landlord_info['agent']}")
        
        if match_score >= 20:
            matches.append({
                'landlord': landlord_name,
                'score': match_score,
                'reasons': reasons,
                'portfolio_size': landlord_info['property_count'],
                'agent': landlord_info['agent']
            })
    
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:5]

def send_telegram_alert(message):
    """Send Telegram alert"""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram credentials not configured")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    data = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'HTML',
        'disable_web_page_preview': False
    }
    
    try:
        response = requests.post(url, data=data, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"Error sending Telegram: {e}")
        return False

def format_opportunity_alert(property_data, hmo_score, hmo_reasons, epc_rating, landlord_matches):
    """Format alert message"""
    message = f"""
🏠 <b>INVESTMENT OPPORTUNITY FOUND!</b>

📍 <b>Property:</b>
{property_data['title']}
💰 {property_data['price']}
🔗 <a href="{property_data['link']}">View on Rightmove</a>

"""
    
    if epc_rating:
        if is_low_epc(epc_rating):
            message += f"⚡ <b>EPC Rating: {epc_rating}</b> (Below C - Renovation opportunity!)\n"
        else:
            message += f"⚡ EPC Rating: {epc_rating}\n"
    
    if hmo_score > 0:
        message += f"\n🏘️ <b>HMO Potential Score: {hmo_score}/100</b>\n"
        for reason in hmo_reasons[:3]:
            message += f"  • {reason}\n"
    
    if landlord_matches:
        message += f"\n👥 <b>Potential Buyers ({len(landlord_matches)} matches):</b>\n"
        for match in landlord_matches[:3]:
            message += f"\n<b>{match['landlord']}</b> (Match: {match['score']}%)\n"
            message += f"  Portfolio: {match['portfolio_size']} properties\n"
            if match['agent']:
                message += f"  Agent: {match['agent']}\n"
            for reason in match['reasons'][:2]:
                message += f"  • {reason}\n"
    
    message += f"\n⏰ Found: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message.strip()

def load_seen_properties():
    """Load seen property IDs"""
    try:
        with open('seen_properties.json', 'r') as f:
            return set(json.load(f))
    except FileNotFoundError:
        return set()

def save_seen_properties(seen_ids):
    """Save seen property IDs"""
    with open('seen_properties.json', 'w') as f:
        json.dump(list(seen_ids), f, indent=2)

def main():
    """Main finder function"""
    print(f"🔍 Starting HMO Investment Opportunity Finder at {datetime.now()}")
    print("="*80)
    
    # Load database
    print("\n📊 Loading landlord database...")
    landlords = load_landlord_database()
    print(f"✅ Loaded {len(landlords)} landlords")
    print(f"   Total properties: {sum(l['property_count'] for l in landlords.values())}")
    
    # Load seen properties
    seen_properties = load_seen_properties()
    print(f"\n📝 Previously tracked {len(seen_properties)} properties")
    
    # Scrape properties
    print("\n🏘️  Scraping Rightmove...")
    all_properties = []
    
    for url in SEARCH_URLS:
        print(f"\n📡 Scraping: {url[:80]}...")
        props = scrape_rightmove_page(url)
        all_properties.extend(props)
        time.sleep(2)  # Be polite - wait between requests
    
    print(f"\n✅ Found {len(all_properties)} properties total")
    
    # Analyze properties
    opportunities_found = 0
    
    for prop in all_properties:
        prop_id = prop.get('id')
        
        if not prop_id or prop_id in seen_properties:
            continue
        
        # Assess opportunity
        hmo_score, hmo_reasons = assess_hmo_potential(prop)
        epc_rating = extract_epc_rating(prop)
        
        is_opportunity = False
        
        if is_low_epc(epc_rating):
            is_opportunity = True
            print(f"\n💡 Low EPC: {prop['title'][:50]}... (EPC: {epc_rating})")
        elif hmo_score >= 25:  # Lower threshold
            is_opportunity = True
            print(f"\n💡 HMO potential: {prop['title'][:50]}... (Score: {hmo_score})")
        
        if is_opportunity:
            matches = find_matching_landlords(prop, landlords)
            
            if matches:
                message = format_opportunity_alert(prop, hmo_score, hmo_reasons, epc_rating, matches)
                
                if send_telegram_alert(message):
                    print(f"   ✅ Alert sent! Matched with {len(matches)} landlords")
                    opportunities_found += 1
                else:
                    print(f"   ❌ Failed to send alert")
            else:
                print(f"   ℹ️  No matching landlords")
        
        seen_properties.add(prop_id)
    
    # Save progress
    save_seen_properties(seen_properties)
    
    print("\n" + "="*80)
    print(f"✨ Monitoring complete!")
    print(f"   📊 New opportunities found: {opportunities_found}")
    print(f"   📝 Total properties tracked: {len(seen_properties)}")
    print("="*80)

if __name__ == "__main__":
    main()
