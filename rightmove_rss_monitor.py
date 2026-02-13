"""
Alternative approach using Rightmove RSS feeds
This is more reliable than web scraping and less likely to break
"""

import feedparser
import requests
import json
import openpyxl
from datetime import datetime
import re
import os
from difflib import SequenceMatcher

# Configuration
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
EXCEL_FILE = 'Masterkey.xlsx'

# Rightmove RSS feed URLs for Brighton & Hove
# You can customize these based on your search criteria
RSS_FEEDS = [
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&maxPrice=500000&minBedrooms=3&radius=3.0&sortType=6&index=0",
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&maxPrice=500000&minBedrooms=4&radius=3.0&sortType=6&index=0",
]

def normalize_address(address):
    """Normalize address for comparison"""
    address = ' '.join(address.lower().split())
    address = re.sub(r'\s+(brighton|hove|bn\d+\s*\d+[a-z]*)', '', address, flags=re.IGNORECASE)
    address = re.sub(r'[^\w\s]', '', address)
    return address

def extract_postcode(address):
    """Extract UK postcode from address"""
    postcode_pattern = r'BN\d+\s*\d+[A-Z]{2}'
    match = re.search(postcode_pattern, address, re.IGNORECASE)
    return match.group(0).upper() if match else None

def address_similarity(addr1, addr2):
    """Calculate similarity between two addresses"""
    # Check postcode match first (high confidence)
    pc1 = extract_postcode(addr1)
    pc2 = extract_postcode(addr2)
    
    if pc1 and pc2:
        if pc1 == pc2:
            # Same postcode - check street number/name
            norm1 = normalize_address(addr1)
            norm2 = normalize_address(addr2)
            similarity = SequenceMatcher(None, norm1, norm2).ratio()
            return similarity
    
    # Fall back to full address comparison
    norm1 = normalize_address(addr1)
    norm2 = normalize_address(addr2)
    return SequenceMatcher(None, norm1, norm2).ratio()

def load_hmo_addresses():
    """Load HMO addresses from Excel file"""
    wb = openpyxl.load_workbook(EXCEL_FILE)
    ws = wb['Sheet1']
    
    addresses = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[3]:
            addresses.append({
                'address': row[3],
                'reference': row[0],
                'bedrooms': row[14],
                'households': row[12],
                'ward': row[4],
                'licence_date': row[5]
            })
    
    wb.close()
    return addresses

def fetch_rss_properties():
    """Fetch properties from Rightmove RSS feeds"""
    all_properties = []
    
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            
            for entry in feed.entries:
                # Extract property details from RSS entry
                prop = {
                    'id': entry.get('guid', entry.get('link')),
                    'title': entry.get('title', ''),
                    'address': entry.get('title', ''),  # RSS title often contains address
                    'description': entry.get('description', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                }
                
                # Try to extract price from description
                price_match = re.search(r'£[\d,]+', prop['description'])
                if price_match:
                    prop['price'] = price_match.group(0)
                else:
                    prop['price'] = 'Price on request'
                
                all_properties.append(prop)
                
        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")
    
    return all_properties

def check_property_match(property_address, hmo_addresses, threshold=0.75):
    """Check if property matches any HMO address"""
    best_match = None
    best_similarity = 0
    
    for hmo in hmo_addresses:
        similarity = address_similarity(property_address, hmo['address'])
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = hmo
    
    if best_similarity >= threshold:
        return True, best_match, best_similarity
    
    return False, None, 0

def send_telegram_message(message):
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
        print(f"Error sending Telegram message: {e}")
        return False

def format_alert_message(property_data, hmo_data, similarity):
    """Format the alert message"""
    message = f"""
🏠 <b>POTENTIAL HMO MATCH FOUND!</b>

<b>Rightmove Property:</b>
📍 {property_data.get('title', 'N/A')}
💰 {property_data.get('price', 'N/A')}
🔗 <a href="{property_data.get('link', '#')}">View on Rightmove</a>

<b>Matching HMO License:</b>
📋 Reference: {hmo_data['reference']}
📍 Address: {hmo_data['address']}
🛏️ Bedrooms: {hmo_data['bedrooms']}
👥 Households: {hmo_data['households']}
📍 Ward: {hmo_data['ward']}
📅 License Date: {hmo_data['licence_date']}

🎯 Match Confidence: {similarity*100:.1f}%
⏰ Found: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
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
    """Main monitoring function"""
    print(f"🔍 Starting Rightmove HMO monitoring at {datetime.now()}")
    
    # Load HMO database
    hmo_addresses = load_hmo_addresses()
    print(f"📊 Loaded {len(hmo_addresses)} HMO properties from database")
    
    # Load seen properties
    seen_properties = load_seen_properties()
    print(f"📝 Previously tracked {len(seen_properties)} properties")
    
    # Fetch properties from RSS
    properties = fetch_rss_properties()
    print(f"🏘️ Found {len(properties)} properties on Rightmove")
    
    # Check each property
    new_matches = 0
    for prop in properties:
        prop_id = prop.get('id')
        
        if not prop_id:
            continue
        
        # Skip if already seen
        if prop_id in seen_properties:
            continue
        
        # Check for match
        is_match, hmo_data, similarity = check_property_match(prop['address'], hmo_addresses)
        
        if is_match:
            # Send alert
            message = format_alert_message(prop, hmo_data, similarity)
            if send_telegram_message(message):
                print(f"✅ Alert sent for: {prop['address']} (match: {similarity*100:.1f}%)")
                new_matches += 1
            else:
                print(f"❌ Failed to send alert for: {prop['address']}")
        
        # Mark as seen
        seen_properties.add(prop_id)
    
    # Save seen properties
    save_seen_properties(seen_properties)
    
    print(f"✨ Monitoring complete. Found {new_matches} new matches.")
    print(f"📊 Total tracked properties: {len(seen_properties)}")

if __name__ == "__main__":
    main()
