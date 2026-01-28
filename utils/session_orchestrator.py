"""
DEPRECATED: Use modules.telethon.session (or modules.telethon) instead.
This file is a facade for backward compatibility.
"""
from modules.telethon.session import SessionOrchestrator, SessionDeathError
from modules.telethon import SessionOrchestrator as SessionOrchestratorAlias

# Ensure export
__all__ = ['SessionOrchestrator', 'SessionDeathError']
