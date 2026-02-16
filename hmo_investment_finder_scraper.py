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
                
                price_elem
