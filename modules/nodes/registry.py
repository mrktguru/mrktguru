from modules.nodes.profile import (
    BioExecutor, UsernameExecutor, PhotoExecutor, 
    SyncProfileExecutor, Set2FAExecutor
)
from modules.nodes.channels import (
    SubscribeExecutor, VisitExecutor, SmartSubscribeExecutor
)
from modules.nodes.actions import (
    ImportContactsExecutor, SendMessageExecutor
)
from modules.nodes.activities import (
    IdleExecutor, PassiveActivityExecutor, SearchFilterExecutor
)

NODE_EXECUTORS = {
    'bio': BioExecutor,
    'username': UsernameExecutor,
    'photo': PhotoExecutor,
    'sync_profile': SyncProfileExecutor,
    'set_2fa': Set2FAExecutor,
    'subscribe': SubscribeExecutor,
    'visit': VisitExecutor,
    'smart_subscribe': SmartSubscribeExecutor,
    'import_contacts': ImportContactsExecutor,
    'send_message': SendMessageExecutor,
    'idle': IdleExecutor,
    'passive_activity': PassiveActivityExecutor,
    'search_filter': SearchFilterExecutor
}
