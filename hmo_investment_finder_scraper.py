"""
HMO Investment Opportunity Finder - Web Scraping Version
Updated 2026: Direct scraping with modern selectors and bot protection bypass.
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

def scrape_rightmove_page(url):
    """Scrape property listings from Rightmove search page using 2026 selectors"""
    properties = []
    
    # Enhanced headers to bypass modern bot detection
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-GB,en;q=0.9',
        'Referer': 'https://www.rightmove.co.uk/property-for-sale/find.html',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"   ⚠️  HTTP {response.status_code} for {url[:80]}")
            return properties
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Updated selectors for 2026 layout
        property_cards = soup.find_all('div', class_='l-searchResult')
        if not property_cards:
            property_cards = soup.find_all('div', attrs={'data-test': re.compile(r'propertyCard-\d+')})
        
        print(f"   Found {len(property_cards)} property cards")
        
        for card in property_cards:
            try:
                # Extract property ID and link
                link_elem = card.find('a', class_='propertyCard-link') or card.find('a', href=True)
                if not link_elem: continue
                
                href = link_elem['href']
                prop_id = re.search(r'property-(\d+)', href).group(1) if 'property-' in href else card.get('id', '')
                link = f"https://www.rightmove.co.uk{href}" if href.startswith('/') else href
                
                # Extract title/address
                title = card.find('address', class_='propertyCard-address').get_text(strip=True) if card.find('address') else ""
                
                # Extract price (using data-test for stability)
                price_elem = card.find('div', class_='propertyCard-priceValue') or card.find('span', attrs={'data-test': 'property-price'})
                price = price_elem.get_text(strip=True) if price_elem else 'POA'
                
                # Extract description
                desc_elem = card.find('span', attrs={'data-test': 'property-description'}) or card.find('div', class_='propertyCard-description')
                description = desc_elem.get_text(strip=True) if desc_elem else ''
                
                # Extract bedrooms
                details = card.get_text()
                bed_match = re.search(r'(\d+)\s+bed', details, re.IGNORECASE)
                bedrooms = int(bed_match.group(1)) if bed_match else 0
                
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
                continue
    except Exception as e:
        print(f"   ❌ Error scraping page: {e}")
    
    return properties

# ... (rest of your original helper functions load_landlord_database, assess_hmo_potential, etc.)
