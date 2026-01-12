#!/usr/bin/env python3
"""
Test script to verify that Telethon is actually using the proxy
This will show the real IP address being used by Telethon
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import db
from app import app
from models.account import Account
from utils.telethon_helper import get_telethon_client
import aiohttp


async def check_ip_with_proxy(account_id):
    """Check what IP Telethon is actually using"""
    
    with app.app_context():
        account = Account.query.get(account_id)
        if not account:
            print(f"❌ Account {account_id} not found")
            return
        
        print(f"\n{'='*60}")
        print(f"Testing account: {account.phone}")
        print(f"{'='*60}\n")
        
        # Show configured proxy
        if account.proxy:
            print(f"📋 Configured Proxy:")
            print(f"   Type: {account.proxy.type}")
            print(f"   Host: {account.proxy.host}")
            print(f"   Port: {account.proxy.port}")
            print(f"   Username: {account.proxy.username or 'None'}")
            print(f"   Stored IP: {account.proxy.current_ip or 'Unknown'}")
        else:
            print(f"⚠️  NO PROXY CONFIGURED!")
        
        print(f"\n{'='*60}")
        print(f"Testing connection...")
        print(f"{'='*60}\n")
        
        # Test 1: Check IP without Telethon (direct connection)
        print("1️⃣  Checking server's direct IP (without proxy):")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.ipify.org?format=json', timeout=10) as resp:
                    data = await resp.json()
                    server_ip = data.get('ip')
                    print(f"   Server IP: {server_ip}")
        except Exception as e:
            print(f"   Error: {e}")
            server_ip = "Unknown"
        
        # Test 2: Check IP through configured proxy
        if account.proxy:
            print(f"\n2️⃣  Checking IP through configured proxy:")
            try:
                import socks
                import aiohttp_socks
                
                proxy_type = socks.SOCKS5 if account.proxy.type == "socks5" else socks.HTTP
                
                # Build proxy URL
                if account.proxy.username and account.proxy.password:
                    proxy_url = f"{account.proxy.type}://{account.proxy.username}:{account.proxy.password}@{account.proxy.host}:{account.proxy.port}"
                else:
                    proxy_url = f"{account.proxy.type}://{account.proxy.host}:{account.proxy.port}"
                
                connector = aiohttp_socks.ProxyConnector.from_url(proxy_url)
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get('https://api.ipify.org?format=json', timeout=15) as resp:
                        data = await resp.json()
                        proxy_ip = data.get('ip')
                        print(f"   Proxy IP: {proxy_ip}")
                        
                        if proxy_ip == server_ip:
                            print(f"   ⚠️  WARNING: Proxy IP matches server IP! Proxy may not be working!")
                        else:
                            print(f"   ✅ Proxy is working (different from server IP)")
            except Exception as e:
                print(f"   ❌ Error testing proxy: {e}")
                print(f"   This suggests the proxy configuration may be invalid!")
                proxy_ip = "Error"
        
        # Test 3: Check IP used by Telethon
        print(f"\n3️⃣  Checking IP used by Telethon client:")
        client = None
        try:
            client = get_telethon_client(account_id)
            await client.connect()
            
            # Get Telegram's view of our connection
            me = await client.get_me()
            print(f"   ✅ Connected to Telegram as: {me.first_name} (@{me.username or 'no username'})")
            print(f"   Telegram ID: {me.id}")
            
            # Try to get datacenter info
            try:
                dc = await client.get_dc()
                print(f"   Connected to DC: {dc}")
            except:
                pass
            
            print(f"\n   ⚠️  Note: Telegram doesn't directly expose the IP we're using,")
            print(f"   but if connection succeeded with proxy config, it should be using it.")
            
        except Exception as e:
            print(f"   ❌ Error connecting with Telethon: {e}")
            print(f"   This could indicate proxy issues or session problems!")
        finally:
            if client and client.is_connected():
                await client.disconnect()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"SUMMARY:")
        print(f"{'='*60}")
        
        if account.proxy:
            print(f"✓ Proxy configured: {account.proxy.host}:{account.proxy.port}")
            if 'proxy_ip' in locals() and proxy_ip != "Error":
                print(f"✓ Proxy IP: {proxy_ip}")
                if proxy_ip != server_ip:
                    print(f"✅ PROXY IS WORKING - Different from server IP")
                else:
                    print(f"❌ PROXY NOT WORKING - Same as server IP!")
            else:
                print(f"❌ Could not verify proxy IP - check proxy settings!")
        else:
            print(f"❌ NO PROXY CONFIGURED - All connections use server IP!")
        
        print(f"\n{'='*60}\n")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 test_proxy.py <account_id>")
        print("\nExample: python3 test_proxy.py 1")
        sys.exit(1)
    
    account_id = int(sys.argv[1])
    
    try:
        asyncio.run(check_ip_with_proxy(account_id))
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
