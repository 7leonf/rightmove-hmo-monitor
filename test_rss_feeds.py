"""
RSS Feed Diagnostic - Check what Rightmove is returning
"""

import feedparser
import requests

# Test RSS feeds
RSS_FEEDS = [
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=3&radius=3.0&sortType=6",
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=4&radius=3.0&sortType=6",
    "https://www.rightmove.co.uk/rss/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=5&radius=3.0&sortType=6",
]

print("="*80)
print("🔍 RIGHTMOVE RSS FEED DIAGNOSTIC")
print("="*80)

for i, feed_url in enumerate(RSS_FEEDS, 1):
    print(f"\n📡 Testing Feed {i}:")
    print(f"URL: {feed_url[:80]}...")
    
    try:
        # Try with requests first to see HTTP response
        response = requests.get(feed_url, timeout=10)
        print(f"   HTTP Status: {response.status_code}")
        print(f"   Content Length: {len(response.text)} bytes")
        
        # Parse with feedparser
        feed = feedparser.parse(feed_url)
        
        print(f"   Feed Status: {feed.get('status', 'Unknown')}")
        print(f"   Feed Version: {feed.get('version', 'Unknown')}")
        print(f"   Entries Found: {len(feed.entries)}")
        
        if feed.entries:
            print(f"\n   ✅ Sample Entry:")
            entry = feed.entries[0]
            print(f"      Title: {entry.get('title', 'N/A')[:80]}")
            print(f"      Link: {entry.get('link', 'N/A')[:80]}")
            print(f"      Published: {entry.get('published', 'N/A')}")
            
            # Show first 200 chars of description
            desc = entry.get('description', 'N/A')
            print(f"      Description: {desc[:200]}...")
        else:
            print(f"   ❌ No entries found in feed")
            
            # Show first 500 chars of raw response
            print(f"\n   Raw Response (first 500 chars):")
            print(f"   {response.text[:500]}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

print("\n" + "="*80)
print("🔍 ALTERNATIVE: Direct Rightmove Search")
print("="*80)

# Try alternative approach - search page
search_url = "https://www.rightmove.co.uk/property-for-sale/find.html?locationIdentifier=REGION%5E1169&minBedrooms=3&radius=3.0&sortType=6"
print(f"\nTrying to access search page directly:")
print(f"URL: {search_url}")

try:
    response = requests.get(search_url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }, timeout=10)
    print(f"Status: {response.status_code}")
    print(f"Response size: {len(response.text)} bytes")
    
    if response.status_code == 200:
        # Check if page contains property listings
        if 'property' in response.text.lower():
            print("✅ Page contains property listings")
        else:
            print("❌ Page doesn't seem to contain properties")
            
        # Check for RSS link in page
        if 'rss' in response.text.lower():
            print("✅ Page mentions RSS")
        else:
            print("❌ No RSS mention found")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "="*80)
print("💡 RECOMMENDATIONS")
print("="*80)

print("""
If feeds are empty:
1. RSS feeds might be disabled by Rightmove
2. Need to use web scraping instead
3. Or use Rightmove API (if available)

If feeds return data but no properties match:
1. Criteria might be too strict
2. Check EPC data availability
3. Adjust HMO scoring

Next steps:
- Check if RSS feeds work in browser
- Consider alternative data sources
- May need to implement web scraping
""")
