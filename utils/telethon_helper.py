"""
DEPRECATED: Use modules.telethon instead.
This file is a facade for backward compatibility.
Refactored into modules/telethon/ package.
"""
from modules.telethon.client import ExtendedTelegramClient, get_client as get_telethon_client
from modules.telethon.verification import verify_session
from modules.telethon.operations import (
    send_invite, 
    send_dm, 
    parse_channel_members, 
    get_channel_messages, 
    send_channel_message,
    get_channel_info,
    read_channel_posts,
    join_channel_for_warmup as join_channel_for_warmup_legacy, # Wait, I named it join_channel
    react_to_post,
    send_conversation_message,
    update_telegram_profile,
    update_telegram_photo,
    search_public_channels,
    sync_official_profile,
    set_2fa_password,
    join_channel,
    get_active_sessions,
    terminate_session,
    terminate_all_sessions,
    remove_2fa_password
)


# Alias join_channel to join_channel_for_warmup for compatibility
join_channel_for_warmup = join_channel

# Re-export clean alias
TelegramClient = ExtendedTelegramClient

# Cleanup isn't strictly needed in new model (no global active clients list)
def cleanup_clients():
    pass
