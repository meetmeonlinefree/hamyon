#!/usr/bin/env python3
"""
Firebase Push Notification System for Hamyon App
Supports: News, App Updates, Daily RUB Rate
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple

# ==================== CONFIGURATION ====================
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
FCM_URL = f"https://fcm.googleapis.com/v1/projects/{FIREBASE_PROJECT_ID}/messages:send"
TOPIC = "hamyon_app"

# ==================== FILE CHANGE DETECTION ====================

def get_changed_files() -> List[str]:
    """
    Get list of changed JSON files in the last commit
    Uses git diff to detect changes
    """
    try:
        # Get changed files between HEAD and HEAD~1
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        
        changed_files = result.stdout.strip().split('\n')
        # Filter only JSON files
        json_files = [f for f in changed_files if f.endswith('.json')]
        
        # Check if news.json or app_update.json changed
        relevant_files = []
        for file in json_files:
            if 'news.json' in file or 'app_update.json' in file:
                relevant_files.append(file)
        
        if relevant_files:
            print(f"📝 Changed files detected: {', '.join(relevant_files)}")
        else:
            print("ℹ️ No relevant JSON files changed")
            
        return relevant_files
    
    except subprocess.CalledProcessError as e:
        print(f"❌ Error getting changed files: {e}")
        return []
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return []

def load_json(file_path: str) -> Optional[Dict]:
    """
    Load JSON file and return parsed data
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"✅ Loaded JSON: {file_path}")
            return data
    except FileNotFoundError:
        print(f"⚠️ File not found: {file_path}")
        return None
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in {file_path}: {e}")
        return None

# ==================== RUB RATE PARSER ====================

def get_best_rub_rate() -> Optional[Dict]:
    """
    Fetch and parse RUB exchange rates from NBT Tajikistan
    Returns best buy rate info or None on error
    """
    try:
        # Get current date in DD.MM.YYYY format
        current_date = datetime.now().strftime("%d.%m.%Y")
        
        # Build URL
        url = f"https://nbt.tj/ru/kurs/kurs_kommer_bank.php?date={current_date}&currency=RUB"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        print(f"🌐 Fetching RUB rates from: {url}")
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Parse HTML
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table')
        
        if not table:
            print("❌ Table not found in HTML")
            return None
        
        rows = table.find_all('tr')
        if len(rows) < 2:
            print("❌ No data rows found in table")
            return None
        
        best_buy = 0.0
        best_bank = ""
        best_sell = 0.0
        best_date = current_date
        
        # Skip header row (index 0)
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) < 14:  # Need at least 14 columns
                continue
                
            try:
                # Parse values
                bank_name = cols[0].get_text(strip=True)
                buy_str = cols[11].get_text(strip=True).replace(',', '.')
                sell_str = cols[12].get_text(strip=True).replace(',', '.')
                date_str = cols[13].get_text(strip=True)
                
                # Convert to float
                buy = float(buy_str) if buy_str else 0.0
                sell = float(sell_str) if sell_str else 0.0
                
                # Check if this is the best buy rate
                if buy > best_buy:
                    best_buy = buy
                    best_bank = bank_name
                    best_sell = sell
                    best_date = date_str if date_str else current_date
                    
            except (ValueError, IndexError) as e:
                print(f"⚠️ Error parsing row: {e}")
                continue
        
        if best_buy == 0:
            print("❌ No valid rates found")
            return None
        
        result = {
            "bank": best_bank,
            "buy": best_buy,
            "sell": best_sell,
            "date": best_date
        }
        
        print(f"✅ Best RUB rate found: {best_bank} (Buy: {best_buy} TJS)")
        return result
        
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error parsing rates: {e}")
        return None

def create_daily_rate_notification(rate_data: Dict) -> Dict:
    """
    Create notification payload for daily RUB rate
    """
    title = f"💱 {rate_data['bank']}"
    
    body = (
        f"Лучший курс денежных переводов RUB\n"
        f"🏦 Банк: {rate_data['bank']}\n"
        f"📈 Покупка: {rate_data['buy']:.2f} TJS\n"
        f"📉 Продажа: {rate_data['sell']:.2f} TJS\n"
        f"🕒 Дата: {rate_data['date']}\n"
        f"💰 Выгодный курс найден!\n"
        f"Переводы RUB → TJS"
    )
    
    return {
        "title": title,
        "body": body,
        "type": "daily_rate",
        "url": "https://nbt.tj/ru/kurs/kurs_kommer_bank.php"
    }

# ==================== FIREBASE SENDER ====================

def send_push(title: str, body: str, notification_type: str, url: str = "") -> bool:
    """
    Send push notification via Firebase Cloud Messaging HTTP v1 API
    Returns True on success, False on failure
    """
    if not FIREBASE_PROJECT_ID:
        print("❌ FIREBASE_PROJECT_ID not set")
        return False
    
    if not ACCESS_TOKEN:
        print("❌ ACCESS_TOKEN not set")
        return False
    
    # Prepare notification payload
    notification = {
        "message": {
            "topic": TOPIC,
            "notification": {
                "title": title,
                "body": body
            },
            "data": {
                "type": notification_type,
                "url": url if url else ""
            },
            "android": {
                "priority": "HIGH"
            }
        }
    }
    
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        print(f"📤 Sending push notification...")
        print(f"   Topic: {TOPIC}")
        print(f"   Type: {notification_type}")
        print(f"   Title: {title[:50]}...")
        
        response = requests.post(
            FCM_URL,
            json=notification,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            print("✅ Push notification sent successfully!")
            return True
        else:
            print(f"❌ Firebase API error: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Network error sending notification: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

# ==================== MAIN LOGIC ====================

def process_news(json_data: Dict):
    """
    Process and send news notifications
    """
    if not json_data:
        return
    
    for item in json_data.get("news", []):
        if item.get("send_push", False):
            title = item.get("title", "Новость")
            body = item.get("body", "")
            url = item.get("url", "")
            
            send_push(
                title=title,
                body=body,
                notification_type="news",
                url=url
            )
        else:
            print(f"ℹ️ Skipping news: {item.get('title', 'Unnamed')} (send_push=False)")

def process_app_update(json_data: Dict):
    """
    Process and send app update notifications
    """
    if not json_data:
        return
    
    if json_data.get("send_push", False):
        title = json_data.get("title", "Обновление приложения")
        body = json_data.get("message", "")
        url = json_data.get("download_url", "")
        
        send_push(
            title=title,
            body=body,
            notification_type="app_update",
            url=url
        )
    else:
        print(f"ℹ️ Skipping app update (send_push=False)")

def main():
    """
    Main entry point
    """
    print("=" * 60)
    print("🚀 Hamyon Firebase Push System")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Check if running in daily_rate mode
    notification_mode = os.getenv("NOTIFICATION_MODE", "changes")
    
    if notification_mode == "daily_rate":
        print("\n📊 DAILY RATE MODE")
        print("-" * 40)
        
        # Get RUB rates
        rate_data = get_best_rub_rate()
        if not rate_data:
            print("❌ Failed to get RUB rates. Exiting.")
            sys.exit(1)
        
        # Create notification
        notification = create_daily_rate_notification(rate_data)
        
        # Send push
        success = send_push(
            title=notification["title"],
            body=notification["body"],
            notification_type=notification["type"],
            url=notification["url"]
        )
        
        sys.exit(0 if success else 1)
    
    else:
        print("\n📝 FILE CHANGE MODE")
        print("-" * 40)
        
        # Get changed files
        changed_files = get_changed_files()
        
        if not changed_files:
            print("ℹ️ No relevant changes detected. Exiting.")
            sys.exit(0)
        
        # Process each changed file
        for file_path in changed_files:
            print(f"\n📄 Processing: {file_path}")
            json_data = load_json(file_path)
            
            if not json_data:
                continue
            
            if "app_update.json" in file_path:
                process_app_update(json_data)
            elif "news.json" in file_path:
                process_news(json_data)
            else:
                print(f"⚠️ Unknown file type: {file_path}")
        
        print("\n✅ All notifications processed")
        sys.exit(0)

if __name__ == "__main__":
    main()
