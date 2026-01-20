#!/usr/bin/env python3
"""
Test script to verify proxy connection with Telethon
"""
import asyncio
from telethon import TelegramClient
import socks

# Test proxy configuration
PROXY_CONFIG = {
    'type': socks.SOCKS5,
    'addr': 'gw.dataimpulse.com',
    'port': 10000,
    'username': 'c93c2077360b4b610d8f__cr.in',
    'password': '29ba314409f67c3a'
}

# Convert to tuple format for Telethon
proxy_tuple = (
    PROXY_CONFIG['type'],
    PROXY_CONFIG['addr'],
    PROXY_CONFIG['port'],
    True,  # rdns
    PROXY_CONFIG['username'],
    PROXY_CONFIG['password']
)

print("=" * 60)
print("TELETHON PROXY CONNECTION TEST")
print("=" * 60)
print(f"Proxy Type: {PROXY_CONFIG['type']} (socks.SOCKS5)")
print(f"Proxy Host: {PROXY_CONFIG['addr']}")
print(f"Proxy Port: {PROXY_CONFIG['port']}")
print(f"Proxy Tuple: {proxy_tuple}")
print("=" * 60)

async def test_connection():
    """Test Telethon connection through proxy"""
    
    # Create client with proxy
    client = TelegramClient(
        'test_proxy_session',
        api_id=2040,  # Desktop API
        api_hash='b18441a1ff607e10a989891a54616e98',
        proxy=proxy_tuple
    )
    
    try:
        print("\n🔌 Attempting to connect through proxy...")
        await client.connect()
        
        if client.is_connected():
            print("✅ Connection successful!")
            print("\n📡 Testing API call (getting dialogs)...")
            
            # Test actual API call
            dialogs = await client.get_dialogs(limit=1)
            print(f"✅ API call successful! Retrieved {len(dialogs)} dialog(s)")
            
        else:
            print("❌ Connection failed - client not connected")
            
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🔌 Disconnecting...")
        await client.disconnect()
        print("✅ Disconnected")

if __name__ == "__main__":
    print("\nStarting test...")
    asyncio.run(test_connection())
    print("\n" + "=" * 60)
    print("TEST COMPLETED")
    print("=" * 60)
