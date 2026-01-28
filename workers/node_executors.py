"""
DEPRECATED: Use modules.nodes package instead.
This file allows backward compatibility.
"""
from modules.nodes import execute_node
from modules.nodes.registry import NODE_EXECUTORS
from modules.nodes.profile import BioExecutor, UsernameExecutor, PhotoExecutor, SyncProfileExecutor, Set2FAExecutor
from modules.nodes.channels import SubscribeExecutor, VisitExecutor, SmartSubscribeExecutor
from modules.nodes.actions import ImportContactsExecutor, SendMessageExecutor
from modules.nodes.activities import IdleExecutor, PassiveActivityExecutor, SearchFilterExecutor

# Mapping old function names to new class executors via a wrapper (if strictly needed)
# But mostly likely only execute_node is used.
# If specific functions were imported, they are not strictly equivalent (Class vs Func).
# Assuming refactor is sufficient with execute_node.

__all__ = ['execute_node', 'NODE_EXECUTORS']
