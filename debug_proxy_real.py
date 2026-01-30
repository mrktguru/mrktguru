import os
import sys
import socks
import socket
import requests
from app import app
from models.proxy import Proxy
from models.account import Account

def test_proxy_auth(account_id):
    with app.app_context():
        # Get account and proxy
        account = Account.query.get(account_id)
        if not account or not account.proxy:
            print("❌ No account or proxy found")
            return

        proxy = account.proxy
        print(f"\n🔍 DEBUG INFO:")
        print(f"Host: {proxy.host}")
        print(f"Port: {proxy.port}")
        print(f"Username in DB: '{proxy.username}'")  # Critical check
        print(f"Password in DB: '{proxy.password}'")
        
        # Check if .ru is in username
        if "__cr.ru" in proxy.username:
            print("✅ username contains '__cr.ru'")
        else:
            print("⚠️ WARNING: username DOES NOT contain '__cr.ru'")
            
        # Construct URL
        proxy_url = f"{proxy.type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}"
        print(f"URL: {proxy.type}://{proxy.username}:***@{proxy.host}:{proxy.port}")
        
        print("\n🌐 Testing Connection via Requests...")
        try:
            proxies = {'http': proxy_url, 'https': proxy_url}
            resp = requests.get("https://api.ipify.org?format=json", proxies=proxies, timeout=15)
            data = resp.json()
            print(f"✅ Response IP: {data['ip']}")
        except Exception as e:
            print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 debug_proxy_real.py <account_id>")
        sys.exit(1)
    test_proxy_auth(int(sys.argv[1]))
