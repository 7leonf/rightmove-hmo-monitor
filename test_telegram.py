"""
DIAGNOSTIC VERSION - Shows what's happening
"""

import os
import sys

print("=" * 80)
print("🔍 TELEGRAM BOT DIAGNOSTICS")
print("=" * 80)

# Check 1: Environment variables
print("\n1️⃣ Checking environment variables...")
bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
chat_id = os.environ.get('TELEGRAM_CHAT_ID')

if bot_token:
    print(f"✅ TELEGRAM_BOT_TOKEN is set (length: {len(bot_token)} chars)")
    print(f"   Starts with: {bot_token[:10]}...")
else:
    print("❌ TELEGRAM_BOT_TOKEN is NOT set!")
    print("   → Go to Settings → Secrets → Actions → Add TELEGRAM_BOT_TOKEN")

if chat_id:
    print(f"✅ TELEGRAM_CHAT_ID is set: {chat_id}")
else:
    print("❌ TELEGRAM_CHAT_ID is NOT set!")
    print("   → Go to Settings → Secrets → Actions → Add TELEGRAM_CHAT_ID")

if not bot_token or not chat_id:
    print("\n⚠️  Please add the missing secrets and try again")
    sys.exit(1)

# Check 2: Test Telegram bot
print("\n2️⃣ Testing Telegram bot connection...")
try:
    import requests
    
    # Test bot token validity
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        if data.get('ok'):
            bot_info = data['result']
            print(f"✅ Bot token is VALID!")
            print(f"   Bot name: @{bot_info.get('username')}")
            print(f"   Bot ID: {bot_info.get('id')}")
        else:
            print(f"❌ Bot token is INVALID: {data}")
    else:
        print(f"❌ Failed to connect to Telegram API: {response.status_code}")
        print(f"   Response: {response.text}")
        
except Exception as e:
    print(f"❌ Error testing bot: {e}")

# Check 3: Test sending message
print("\n3️⃣ Testing message sending...")
try:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {
        'chat_id': chat_id,
        'text': '🧪 Test message from your Rightmove HMO Monitor!\n\nIf you received this, everything is working! ✅',
        'parse_mode': 'HTML'
    }
    
    response = requests.post(url, data=data, timeout=10)
    
    if response.status_code == 200:
        result = response.json()
        if result.get('ok'):
            print("✅ Test message SENT successfully!")
            print("   → Check your Telegram app!")
        else:
            print(f"❌ Failed to send: {result}")
            if 'description' in result:
                desc = result['description']
                if 'chat not found' in desc.lower():
                    print("\n💡 FIX: You need to start a conversation with your bot first!")
                    print("   1. Open Telegram")
                    print("   2. Search for your bot")
                    print("   3. Click START or send /start")
                    print("   4. Then run this workflow again")
    else:
        print(f"❌ HTTP Error {response.status_code}: {response.text}")
        
except Exception as e:
    print(f"❌ Error sending message: {e}")

# Check 4: Excel file
print("\n4️⃣ Checking for Masterkey.xlsx...")
import os.path

if os.path.isfile('Masterkey.xlsx'):
    print("✅ Masterkey.xlsx found!")
    
    try:
        import openpyxl
        wb = openpyxl.load_workbook('Masterkey.xlsx')
        ws = wb['Sheet1']
        row_count = ws.max_row
        print(f"   → {row_count - 1} properties loaded")
        wb.close()
    except Exception as e:
        print(f"❌ Error reading Excel: {e}")
else:
    print("❌ Masterkey.xlsx NOT found in repository!")
    print("   → Make sure you uploaded it to the root of your repo")

print("\n" + "=" * 80)
print("🏁 DIAGNOSTICS COMPLETE")
print("=" * 80)
