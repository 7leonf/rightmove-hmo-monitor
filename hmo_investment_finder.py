"""
HMO Investment Opportunity Finder
Finds properties on Rightmove with:
- Low EPC (below C) - renovation opportunities
- HMO potential
Then matches them to landlords who might be interested based on their portfolio
"""

import requests
import json
import openpyxl
from datetime import datetime
import re
import os
import feedparser
from collections import defaultdict

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
EXCEL_FILE = 'Masterkey.xlsx'

# Search criteria for investment opportunities
RSS_FEEDS = [
    # Brighton properties, sorted by newest first, no price filters
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=3&radius=3.0&sortType=6",
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=4&radius=3.0&sortType=6",
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=5&radius=3.0&sortType=6",
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
    
    # Convert sets to lists for JSON serialization
    for landlord in landlords.values():
        landlord['wards'] = list(landlord['wards'])
    
    return dict(landlords)

def extract_postcode(address):
    """Extract UK postcode"""
    postcode_pattern = r'BN\d+\s*\d+[A-Z]{2}'
    match = re.search(postcode_pattern, address, re.IGNORECASE)
    return match.group(0).upper() if match else None

def get_ward_from_postcode(postcode):
    """Try to determine ward from postcode (simplified)"""
    if not postcode:
        return None
    
    # Simple ward mapping for Brighton postcodes
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
    """Assess if property has HMO potential based on description"""
    description = property_data.get('description', '').lower()
    title = property_data.get('title', '').lower()
    
    score = 0
    reasons = []
    
    # Check bedroom count
    bed_match = re.search(r'(\d+)\s+bed', title + ' ' + description)
    if bed_match:
        beds = int(bed_match.group(1))
        if beds >= 5:
            score += 30
            reasons.append(f"{beds} bedrooms (excellent for HMO)")
        elif beds >= 3:
            score += 20
            reasons.append(f"{beds} bedrooms (good for HMO)")
    
    # HMO indicators in description
    hmo_keywords = {
        'student': 10,
        'sharers': 15,
        'hmo': 30,
        'rental income': 15,
        'investment': 10,
        'multi': 10,
        'separate': 5,
        'ensuite': 10,
    }
    
    for keyword, points in hmo_keywords.items():
        if keyword in description:
            score += points
            reasons.append(f"Mentions '{keyword}'")
    
    # Property type indicators
    if 'house' in description:
        score += 5
    if 'terraced' in description or 'terrace' in description:
        score += 5
        reasons.append("Terraced house (good for HMO conversion)")
    
    return score, reasons

def extract_epc_rating(property_data):
    """Try to extract EPC rating from description"""
    description = property_data.get('description', '')
    
    # Look for EPC patterns
    epc_pattern = r'EPC\s+(?:rating\s+)?([A-G])'
    match = re.search(epc_pattern, description, re.IGNORECASE)
    
    if match:
        return match.group(1).upper()
    
    # Check for energy efficiency mentions
    if 'energy efficiency' in description.lower():
        return 'Unknown (mentioned)'
    
    return None

def is_low_epc(epc_rating):
    """Check if EPC is below C (D, E, F, G)"""
    if not epc_rating or epc_rating == 'Unknown (mentioned)':
        return False
    return epc_rating in ['D', 'E', 'F', 'G']

def find_matching_landlords(property_data, landlords):
    """Find landlords who might be interested in this property"""
    matches = []
    
    property_postcode = extract_postcode(property_data.get('title', ''))
    property_wards = get_ward_from_postcode(property_postcode) if property_postcode else []
    
    for landlord_name, landlord_info in landlords.items():
        match_score = 0
        reasons = []
        
        # Check if landlord has properties in same ward
        for ward in property_wards:
            if ward in landlord_info['wards']:
                match_score += 30
                reasons.append(f"Has properties in {ward}")
        
        # Check if landlord has multiple properties (active investor)
        if landlord_info['property_count'] >= 3:
            match_score += 20
            reasons.append(f"Active investor ({landlord_info['property_count']} properties)")
        
        # Check if they use an agent (more professional)
        if landlord_info['agent']:
            match_score += 10
            reasons.append(f"Works with agent: {landlord_info['agent']}")
        
        if match_score >= 20:  # Minimum threshold
            matches.append({
                'landlord': landlord_name,
                'score': match_score,
                'reasons': reasons,
                'portfolio_size': landlord_info['property_count'],
                'agent': landlord_info['agent']
            })
    
    # Sort by match score
    matches.sort(key=lambda x: x['score'], reverse=True)
    return matches[:5]  # Top 5 matches

def fetch_properties():
    """Fetch properties from Rightmove RSS feeds"""
    all_properties = []
    
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                prop = {
                    'id': entry.get('guid', entry.get('link')),
                    'title': entry.get('title', ''),
                    'description': entry.get('description', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                }
                
                # Extract price
                price_match = re.search(r'£[\d,]+', prop['description'])
                prop['price'] = price_match.group(0) if price_match else 'Price on request'
                
                all_properties.append(prop)
                
        except Exception as e:
            print(f"Error fetching RSS feed: {e}")
    
    return all_properties

def send_telegram_alert(message):
    """Send alert via Telegram"""
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
    """Format the investment opportunity alert"""
    
    # Build the message
    message = f"""
🏠 <b>INVESTMENT OPPORTUNITY FOUND!</b>

📍 <b>Property:</b>
{property_data['title']}
💰 {property_data['price']}
🔗 <a href="{property_data['link']}">View on Rightmove</a>

"""
    
    # Add EPC info if available
    if epc_rating:
        if is_low_epc(epc_rating):
            message += f"⚡ <b>EPC Rating: {epc_rating}</b> (Below C - Renovation opportunity!)\n"
        else:
            message += f"⚡ EPC Rating: {epc_rating}\n"
    
    # Add HMO potential
    if hmo_score > 0:
        message += f"\n🏘️ <b>HMO Potential Score: {hmo_score}/100</b>\n"
        for reason in hmo_reasons[:3]:  # Top 3 reasons
            message += f"  • {reason}\n"
    
    # Add matching landlords
    if landlord_matches:
        message += f"\n👥 <b>Potential Buyers ({len(landlord_matches)} matches):</b>\n"
        for match in landlord_matches[:3]:  # Top 3 matches
            message += f"\n<b>{match['landlord']}</b> (Match: {match['score']}%)\n"
            message += f"  Portfolio: {match['portfolio_size']} properties\n"
            if match['agent']:
                message += f"  Agent: {match['agent']}\n"
            for reason in match['reasons'][:2]:
                message += f"  • {reason}\n"
    
    message += f"\n⏰ Found: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    
    return message.strip()

def load_seen_properties():
    """Load previously seen property IDs"""
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
    """Main investment opportunity finder"""
    print(f"🔍 Starting HMO Investment Opportunity Finder at {datetime.now()}")
    print("="*80)
    
    # Load landlord database
    print("\n📊 Loading landlord database...")
    landlords = load_landlord_database()
    print(f"✅ Loaded {len(landlords)} landlords")
    print(f"   Total properties: {sum(l['property_count'] for l in landlords.values())}")
    
    # Load seen properties
    seen_properties = load_seen_properties()
    print(f"\n📝 Previously tracked {len(seen_properties)} properties")
    
    # Fetch new properties
    print("\n🏘️  Fetching properties from Rightmove...")
    properties = fetch_properties()
    print(f"✅ Found {len(properties)} properties")
    
    # Analyze each property
    opportunities_found = 0
    
    for prop in properties:
        prop_id = prop.get('id')
        
        if not prop_id or prop_id in seen_properties:
            continue
        
        # Assess HMO potential
        hmo_score, hmo_reasons = assess_hmo_potential(prop)
        
        # Check EPC
        epc_rating = extract_epc_rating(prop)
        
        # Determine if this is an opportunity
        is_opportunity = False
        
        # Criteria for opportunity:
        # 1. Low EPC (below C) - renovation opportunity
        # 2. OR high HMO potential score
        if is_low_epc(epc_rating):
            is_opportunity = True
            print(f"\n💡 Low EPC opportunity: {prop['title'][:50]}... (EPC: {epc_rating})")
        elif hmo_score >= 25:  # Lowered threshold for more opportunities
            is_opportunity = True
            print(f"\n💡 HMO opportunity: {prop['title'][:50]}... (Score: {hmo_score})")
        
        if is_opportunity:
            # Find matching landlords
            matches = find_matching_landlords(prop, landlords)
            
            if matches:
                # Send alert
                message = format_opportunity_alert(prop, hmo_score, hmo_reasons, epc_rating, matches)
                
                if send_telegram_alert(message):
                    print(f"   ✅ Alert sent! Matched with {len(matches)} landlords")
                    opportunities_found += 1
                else:
                    print(f"   ❌ Failed to send alert")
            else:
                print(f"   ℹ️  No matching landlords found")
        
        # Mark as seen
        seen_properties.add(prop_id)
    
    # Save seen properties
    save_seen_properties(seen_properties)
    
    print("\n" + "="*80)
    print(f"✨ Monitoring complete!")
    print(f"   📊 New opportunities found: {opportunities_found}")
    print(f"   📝 Total properties tracked: {len(seen_properties)}")
    print("="*80)

if __name__ == "__main__":
    main()
