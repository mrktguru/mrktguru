import logging
import asyncio
from telethon.tl.functions.messages import ReadHistoryRequest

logger = logging.getLogger(__name__)

# Import existing verification logic to reuse
from utils.safe_verification import safe_self_check, safe_get_me, check_via_public_channel
from utils.telethon_helper import verify_session as verify_session_helper

# We'll move the spamblock check here as it is a verification task
from tasks.basic import task_check_spamblock

async def task_verify_session_legacy(client, account_id, disable_anchor=False):
    """
    Wrapper for the complex verify_session logic in telethon_helper.
    NOTE: verify_session in telethon_helper instantiates its OWN client.
    This creates a conflict if we want to use the Orchestrator's client.
    
    However, for the full verification flow (especially with handshake), 
    we might need to rely on the helper's robust logic which handles 
    connection and everything. 
    
    BUT, the Orchestrator already provides a connected client (ACTIVE).
    
    If we want to use the Orchestrator's client, we should probably refactor 
    verify_session to accept a client, OR just use 'safe_get_me' for 'active' checks.
    
    For now, let's strictly use this for the 'Verify Session' button which often 
    implies a full state check or initial handshake.
    
    If we are already connected via Orchestrator, we likely don't need the full handshake 
    logic of 'verify_session' unless it's the very first run.
    """
    # For now, we delegate to the existing helper logic but this bypasses the 
    # Orchestrator's client, which is suboptimal (double connection).
    # TODO: Refactor verify_session in telethon_helper to accept an optional 'client'
    
    # As a workaround, we can use the Orchestrator to ensure we are ONLINE, 
    # then if we need the complex logic, we might have to disconnect Orchestrator 
    # temporarily or ensure verify_session cleans up.
    
    # Actually, for 'Light Verify', it's just a GetState or GetMe.
    pass

async def task_perform_alignment_check(client):
    """
    Perform a light alignment check (Light Verify).
    Just verifies the session is alive and gets basic info.
    """
    logger.info("⚡ [Task] Starting Light Verification (Alignment Check)...")
    try:
        me = await client.get_me()
        if not me:
            return {'success': False, 'error': 'get_me returned None'}
        
        return {
            'success': True,
            'verification_type': 'light',
            'user': {
                'id': me.id,
                'first_name': me.first_name,
                'last_name': me.last_name,
                'username': me.username,
                'photo': getattr(me, 'photo', None) is not None
            }
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Re-exporting safe verification tasks for uniform access
task_safe_self_check = safe_self_check
task_safe_get_me = safe_get_me
task_public_channel_verify = check_via_public_channel
