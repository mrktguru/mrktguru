# Activity Logging System - Deployment Guide

## Overview

Added comprehensive activity logging system to track ALL account actions:
- Verification, login, sync
- Join/leave groups
- Read posts, reactions
- Send messages, DMs, invites
- Profile updates
- And more...

## Files Created

1. **models/activity_log.py** - AccountActivityLog model
2. **utils/activity_logger.py** - ActivityLogger helper class
3. **templates/accounts/activity_logs.html** - Logs viewing page
4. **routes/accounts.py** - Added activity_logs route

## Database Migration

The `AccountActivityLog` table will be created automatically by SQLAlchemy when you first use it, OR you can create it manually:

### SQLite:
```sql
CREATE TABLE account_activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    action_category VARCHAR(30) DEFAULT 'general',
    target VARCHAR(500),
    status VARCHAR(20) DEFAULT 'success',
    description TEXT,
    details TEXT,
    error_message TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    proxy_used VARCHAR(100),
    timestamp DATETIME NOT NULL,
    duration_ms INTEGER,
    FOREIGN KEY (account_id) REFERENCES accounts(id)
);

CREATE INDEX ix_account_activity_logs_account_id ON account_activity_logs(account_id);
CREATE INDEX ix_account_activity_logs_action_type ON account_activity_logs(action_type);
CREATE INDEX ix_account_activity_logs_timestamp ON account_activity_logs(timestamp);
```

### PostgreSQL:
```sql
CREATE TABLE account_activity_logs (
    id SERIAL PRIMARY KEY,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    action_type VARCHAR(50) NOT NULL,
    action_category VARCHAR(30) DEFAULT 'general',
    target VARCHAR(500),
    status VARCHAR(20) DEFAULT 'success',
    description TEXT,
    details TEXT,
    error_message TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    proxy_used VARCHAR(100),
    timestamp TIMESTAMP NOT NULL,
    duration_ms INTEGER
);

CREATE INDEX ix_account_activity_logs_account_id ON account_activity_logs(account_id);
CREATE INDEX ix_account_activity_logs_action_type ON account_activity_logs(action_type);
CREATE INDEX ix_account_activity_logs_timestamp ON account_activity_logs(timestamp);
```

## How to Use

### In Code:

```python
from utils.activity_logger import ActivityLogger

# Create logger for account
logger = ActivityLogger(account_id=123)

# Log verification
logger.log_verification(status='success', proxy='1.2.3.4:1080')

# Log joining group
logger.log_join_group('channelname', status='success')

# Log reading posts
logger.log_read_posts('channelname', posts_count=10)

# Log with timing
logger.start_timer()
# ... do something ...
logger.log('some_action', status='success')  # duration auto-calculated
```

### Quick Logging:

```python
from utils.activity_logger import log_account_activity

log_account_activity(
    account_id=123,
    action_type='verification',
    status='success',
    description='Account verified',
    proxy='1.2.3.4:1080'
)
```

## UI Access

1. Go to account detail page
2. Click "View Activity Logs" button
3. Filter by:
   - Action Type
   - Category
   - Status
   - Limit

## Action Types

- `verification` - Account verification
- `login` - Login/connection
- `join_group` - Joined channel/group
- `leave_group` - Left channel/group
- `read_posts` - Read posts from channel
- `react` - Reacted to post
- `send_message` - Sent message
- `send_dm` - Sent DM
- `invite_user` - Invited user to channel
- `update_profile` - Updated profile
- `sync_profile` - Synced from Telegram

## Categories

- `system` - System actions (verification, login)
- `warmup` - Warmup activities
- `campaign` - Campaign actions (DM, invites)
- `manual` - Manual user actions
- `profile` - Profile updates

## Next Steps

To integrate logging into existing code:

1. Import ActivityLogger
2. Add logging calls after each action
3. Include proxy info, errors, timing

Example for verification route:
```python
from utils.activity_logger import ActivityLogger

logger = ActivityLogger(account_id)
logger.start_timer()

try:
    # ... verification code ...
    logger.log_verification(
        status='success',
        proxy=f"{proxy.host}:{proxy.port}" if proxy else None
    )
except Exception as e:
    logger.log_verification(
        status='failed',
        error=str(e)
    )
```

## Testing

1. Deploy changes
2. Verify account
3. Go to "View Activity Logs"
4. Should see verification log entry
