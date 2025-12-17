# TELEGRAM INVITE & DM SYSTEM - Technical Specification

## Table of Contents
1. [System Overview](#system-overview)
2. [Technology Stack](#technology-stack)
3. [Database Schema](#database-schema)
4. [Architecture](#architecture)
5. [Modules](#modules)
6. [API Endpoints](#api-endpoints)
7. [Background Workers](#background-workers)
8. [File Structure](#file-structure)
9. [Installation & Setup](#installation--setup)
10. [Development Roadmap](#development-roadmap)

---

## System Overview

### Purpose
Automated system for Telegram channel/group growth through invite campaigns and direct messaging campaigns with built-in anti-ban mechanisms.

### Key Features
- **Invite Campaigns**: Automated user inviting to channels/groups
- **DM Campaigns**: Mass direct messaging to users
- **Account Management**: Multi-account support with proxy integration
- **Anti-ban System**: Device emulation, human-like behavior, warm-up periods
- **Channel Management**: Post creation, pinning, message handling
- **Analytics & Reports**: Detailed statistics and performance metrics
- **Automation**: Scheduling, auto-actions, recurring tasks
- **Advanced Parser**: Multi-source user collection with smart filtering
- **Blacklist/Whitelist**: User filtering and risk management

### Current Authentication
- Simple login/password system (default: admin/admin123)
- Future: User registration with multi-tenant support

---

## Technology Stack

### Backend
- **Framework**: Flask (Python 3.9+)
- **Database**: PostgreSQL 14+
- **ORM**: SQLAlchemy
- **Task Queue**: Celery + Redis
- **Telegram Library**: Telethon
- **Proxy Support**: SOCKS5/HTTP (mobile proxies with rotation)

### Frontend
- **Framework**: Bootstrap 5 or Tailwind CSS
- **JavaScript**: Vanilla JS / jQuery (keep it simple)
- **Real-time Updates**: Flask-SocketIO or Server-Sent Events

### Infrastructure
- **File Storage**: Local filesystem (session files, media)
- **Caching**: Redis
- **Background Workers**: Celery workers
- **Session Storage**: Encrypted .session files

---

## Database Schema

### Core Tables

#### `users` (authentication)
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);
```

#### `accounts` (Telegram accounts)
```sql
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    phone VARCHAR(20) UNIQUE NOT NULL,
    session_file_path VARCHAR(500) NOT NULL,
    proxy_id INTEGER REFERENCES proxies(id),
    status VARCHAR(20) DEFAULT 'active', -- active/warming_up/cooldown/banned
    health_score INTEGER DEFAULT 100,
    created_at TIMESTAMP DEFAULT NOW(),
    last_activity TIMESTAMP,
    warm_up_days_completed INTEGER DEFAULT 0,
    messages_sent_today INTEGER DEFAULT 0,
    invites_sent_today INTEGER DEFAULT 0
);
```

#### `device_profiles` (device emulation)
```sql
CREATE TABLE device_profiles (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id) UNIQUE,
    device_model VARCHAR(100) NOT NULL,
    system_version VARCHAR(50) NOT NULL,
    app_version VARCHAR(50) NOT NULL,
    lang_code VARCHAR(10) DEFAULT 'ru',
    system_lang_code VARCHAR(10) DEFAULT 'ru-RU',
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `proxies`
```sql
CREATE TABLE proxies (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL, -- socks5/http/mobile
    host VARCHAR(255) NOT NULL,
    port INTEGER NOT NULL,
    username VARCHAR(255),
    password VARCHAR(255),
    rotation_url TEXT,
    rotation_interval INTEGER DEFAULT 1200, -- seconds
    current_ip VARCHAR(50),
    last_rotation TIMESTAMP,
    is_mobile BOOLEAN DEFAULT FALSE,
    status VARCHAR(20) DEFAULT 'active', -- active/inactive/error
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `account_subscriptions` (channel subscriptions for warm-up)
```sql
CREATE TABLE account_subscriptions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    channel_username VARCHAR(255) NOT NULL,
    subscribed_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    subscription_source VARCHAR(20) DEFAULT 'manual', -- manual/auto/template
    notes TEXT
);
```

#### `channels` (target channels/groups)
```sql
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    type VARCHAR(20) NOT NULL, -- channel/group/supergroup
    username VARCHAR(255) UNIQUE,
    chat_id BIGINT UNIQUE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    is_admin BOOLEAN DEFAULT FALSE,
    admin_rights JSONB, -- {can_post, can_pin, can_delete, can_ban, etc.}
    status VARCHAR(20) DEFAULT 'active',
    owner_account_id INTEGER REFERENCES accounts(id),
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `channel_posts`
```sql
CREATE TABLE channel_posts (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id),
    message_id BIGINT NOT NULL,
    content_type VARCHAR(20) NOT NULL, -- text/photo/video/document/poll
    text_content TEXT,
    media_file_path VARCHAR(500),
    is_pinned BOOLEAN DEFAULT FALSE,
    posted_at TIMESTAMP DEFAULT NOW(),
    posted_by_account_id INTEGER REFERENCES accounts(id),
    views_count INTEGER DEFAULT 0,
    reactions_count INTEGER DEFAULT 0
);
```

#### `channel_messages` (for groups - incoming messages)
```sql
CREATE TABLE channel_messages (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id),
    message_id BIGINT NOT NULL,
    from_user_id BIGINT,
    from_username VARCHAR(255),
    from_first_name VARCHAR(255),
    text TEXT,
    received_at TIMESTAMP DEFAULT NOW(),
    is_replied BOOLEAN DEFAULT FALSE,
    reply_message_id BIGINT,
    reply_text TEXT,
    replied_at TIMESTAMP,
    replied_by_account_id INTEGER REFERENCES accounts(id)
);
```

### Invite Campaigns

#### `invite_campaigns`
```sql
CREATE TABLE invite_campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    channel_id INTEGER REFERENCES channels(id),
    status VARCHAR(20) DEFAULT 'draft', -- draft/active/paused/stopped/completed
    strategy VARCHAR(20) DEFAULT 'safe', -- safe/normal/aggressive/custom
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    paused_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_targets INTEGER DEFAULT 0,
    invited_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    
    -- Settings
    delay_min INTEGER DEFAULT 45,
    delay_max INTEGER DEFAULT 90,
    invites_per_hour_min INTEGER DEFAULT 5,
    invites_per_hour_max INTEGER DEFAULT 10,
    burst_limit INTEGER DEFAULT 3,
    burst_pause_minutes INTEGER DEFAULT 15,
    working_hours_start TIME DEFAULT '09:00',
    working_hours_end TIME DEFAULT '22:00',
    human_like_behavior BOOLEAN DEFAULT TRUE,
    auto_pause_on_errors BOOLEAN DEFAULT TRUE
);
```

#### `campaign_accounts` (many-to-many)
```sql
CREATE TABLE campaign_accounts (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES invite_campaigns(id),
    account_id INTEGER REFERENCES accounts(id),
    invites_sent INTEGER DEFAULT 0,
    last_invite_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'active', -- active/limit_reached/cooldown/error
    UNIQUE(campaign_id, account_id)
);
```

#### `source_users` (users to invite)
```sql
CREATE TABLE source_users (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES invite_campaigns(id),
    user_id BIGINT,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    source VARCHAR(255), -- channel username where parsed from
    status VARCHAR(20) DEFAULT 'pending', -- pending/invited/failed/blacklisted
    invited_at TIMESTAMP,
    invited_by_account_id INTEGER REFERENCES accounts(id),
    error_message TEXT,
    added_at TIMESTAMP DEFAULT NOW(),
    priority_score INTEGER DEFAULT 50 -- 0-100, for smart targeting
);
```

#### `invite_logs`
```sql
CREATE TABLE invite_logs (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES invite_campaigns(id),
    account_id INTEGER REFERENCES accounts(id),
    target_user_id BIGINT,
    timestamp TIMESTAMP DEFAULT NOW(),
    status VARCHAR(20) NOT NULL, -- success/error/flood_wait/user_privacy/peer_flood
    details TEXT
);
```

### DM Campaigns

#### `dm_campaigns`
```sql
CREATE TABLE dm_campaigns (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    message_text TEXT NOT NULL,
    media_type VARCHAR(20) DEFAULT 'none', -- none/photo/video/audio/document
    media_file_path VARCHAR(500),
    status VARCHAR(20) DEFAULT 'draft', -- draft/active/paused/stopped/completed/limit_reached
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    paused_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_targets INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    
    -- Settings
    messages_per_account_limit INTEGER DEFAULT 5,
    delay_min INTEGER DEFAULT 60,
    delay_max INTEGER DEFAULT 180,
    working_hours_start TIME DEFAULT '09:00',
    working_hours_end TIME DEFAULT '22:00'
);
```

#### `dm_campaign_accounts` (many-to-many)
```sql
CREATE TABLE dm_campaign_accounts (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES dm_campaigns(id),
    account_id INTEGER REFERENCES accounts(id),
    messages_sent INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active', -- active/limit_reached/error
    UNIQUE(campaign_id, account_id)
);
```

#### `dm_targets`
```sql
CREATE TABLE dm_targets (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES dm_campaigns(id),
    username VARCHAR(255) NOT NULL,
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    custom_data JSONB, -- additional fields from CSV
    source VARCHAR(20) DEFAULT 'manual', -- manual/csv/xls
    status VARCHAR(20) DEFAULT 'new', -- new/sent/error/deleted
    sent_at TIMESTAMP,
    sent_by_account_id INTEGER REFERENCES accounts(id),
    error_message TEXT,
    added_at TIMESTAMP DEFAULT NOW(),
    replied_at TIMESTAMP
);
```

#### `dm_messages` (conversation history)
```sql
CREATE TABLE dm_messages (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER REFERENCES dm_campaigns(id),
    target_id INTEGER REFERENCES dm_targets(id),
    account_id INTEGER REFERENCES accounts(id),
    direction VARCHAR(10) NOT NULL, -- outgoing/incoming
    message_text TEXT,
    has_media BOOLEAN DEFAULT FALSE,
    media_type VARCHAR(20),
    timestamp TIMESTAMP DEFAULT NOW(),
    is_read BOOLEAN DEFAULT FALSE,
    telegram_message_id BIGINT
);
```

### Analytics & Automation

#### `campaign_stats` (daily cache)
```sql
CREATE TABLE campaign_stats (
    id SERIAL PRIMARY KEY,
    campaign_id INTEGER,
    campaign_type VARCHAR(20), -- invite/dm
    date DATE NOT NULL,
    sent_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2),
    UNIQUE(campaign_id, campaign_type, date)
);
```

#### `scheduled_tasks`
```sql
CREATE TABLE scheduled_tasks (
    id SERIAL PRIMARY KEY,
    task_type VARCHAR(50) NOT NULL, -- subscribe_channel/post_message/rotate_proxy/etc
    entity_type VARCHAR(50), -- account/campaign/channel
    entity_id INTEGER,
    scheduled_for TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending', -- pending/completed/failed
    payload JSONB, -- task parameters
    created_at TIMESTAMP DEFAULT NOW(),
    executed_at TIMESTAMP,
    error_message TEXT
);
```

#### `auto_actions`
```sql
CREATE TABLE auto_actions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL, -- campaign_progress/account_health/user_reply/time_based
    trigger_condition JSONB NOT NULL, -- {type: "campaign_progress", value: 50, operator: ">="}
    action_type VARCHAR(50) NOT NULL, -- post_message/pause_account/send_notification/etc
    action_params JSONB NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### `reports`
```sql
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    report_type VARCHAR(50) NOT NULL, -- campaign_summary/account_performance/system_health
    time_period VARCHAR(50), -- last_7_days/last_30_days/custom
    start_date DATE,
    end_date DATE,
    file_path VARCHAR(500),
    format VARCHAR(20), -- pdf/xlsx/csv
    generated_at TIMESTAMP DEFAULT NOW(),
    generated_by_user_id INTEGER REFERENCES users(id)
);
```

### Blacklist & Whitelist

#### `global_blacklist`
```sql
CREATE TABLE global_blacklist (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(255),
    reason VARCHAR(50) NOT NULL, -- blocked_us/reported_spam/negative_reply/manual
    added_at TIMESTAMP DEFAULT NOW(),
    added_by_campaign_id INTEGER,
    notes TEXT
);
```

#### `global_whitelist`
```sql
CREATE TABLE global_whitelist (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    username VARCHAR(255),
    category VARCHAR(50), -- hot_lead/customer/partner/influencer
    priority_level INTEGER DEFAULT 1, -- 1-5
    notes TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);
```

#### `channel_blacklist`
```sql
CREATE TABLE channel_blacklist (
    id SERIAL PRIMARY KEY,
    channel_username VARCHAR(255) UNIQUE NOT NULL,
    reason TEXT,
    added_at TIMESTAMP DEFAULT NOW()
);
```

### Parser Module

#### `parsed_user_library`
```sql
CREATE TABLE parsed_user_library (
    id SERIAL PRIMARY KEY,
    collection_name VARCHAR(255) NOT NULL, -- "Crypto Enthusiasts", "NFT Collectors"
    user_id BIGINT,
    username VARCHAR(255),
    first_name VARCHAR(255),
    last_name VARCHAR(255),
    source_channel VARCHAR(255),
    has_profile_photo BOOLEAN,
    is_premium BOOLEAN,
    last_seen TIMESTAMP,
    parsed_at TIMESTAMP DEFAULT NOW(),
    metadata JSONB -- additional parsed data
);
```

#### `parse_jobs`
```sql
CREATE TABLE parse_jobs (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(50) NOT NULL, -- single_channel/multi_channel/by_activity/by_keyword
    source_channels TEXT[], -- array of channel usernames
    filters JSONB, -- parsing filters
    status VARCHAR(20) DEFAULT 'pending', -- pending/running/completed/failed
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_parsed INTEGER DEFAULT 0,
    total_valid INTEGER DEFAULT 0,
    account_id INTEGER REFERENCES accounts(id), -- account used for parsing
    error_message TEXT
);
```

---

## Architecture

### System Components
```
┌─────────────────────────────────────────────────────────┐
│                     Flask Web App                       │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │   Routes    │  │  Templates   │  │  Static Files │ │
│  │  (Views)    │  │   (HTML)     │  │   (CSS/JS)    │ │
│  └─────────────┘  └──────────────┘  └───────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                  Business Logic Layer                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Campaign    │  │   Account    │  │   Channel    │ │
│  │  Manager     │  │   Manager    │  │   Manager    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │    Parser    │  │   Analytics  │  │  Automation  │ │
│  │   Module     │  │    Module    │  │   Module     │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                   Data Access Layer                     │
│                   (SQLAlchemy ORM)                      │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                PostgreSQL Database                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│              Background Workers (Celery)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Invite     │  │      DM      │  │    Parser    │ │
│  │   Worker     │  │    Worker    │  │    Worker    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │  Subscription│  │    Proxy     │  │   Scheduler  │ │
│  │   Activity   │  │   Rotator    │  │    Worker    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────┐
│                    Redis (Queue)                        │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                  Telethon Clients                       │
│           (One client per account)                      │
│              Connected via Proxies                      │
└─────────────────────────────────────────────────────────┘
```

### Data Flow

**Invite Campaign Flow:**
```
User creates campaign
    ↓
Campaign saved to DB
    ↓
User clicks "Start"
    ↓
Celery task created → InviteCampaignWorker
    ↓
Worker loop:
  ├─ Check working hours
  ├─ Select available account (round-robin)
  ├─ Get next pending target
  ├─ Initialize Telethon client (with proxy)
  ├─ Send invite
  ├─ Log result
  ├─ Update stats
  ├─ Apply delay
  └─ Repeat
```

**DM Campaign Flow:**
```
User creates DM campaign
    ↓
Imports targets (CSV/XLS/manual)
    ↓
User clicks "Start"
    ↓
Celery task created → DMCampaignWorker
    ↓
Worker loop:
  ├─ Check working hours
  ├─ Select available account (not at limit)
  ├─ Get next 'new' target
  ├─ Personalize message template
  ├─ Send DM via Telethon
  ├─ Log result
  ├─ Update counters
  ├─ Check if limit reached → pause if yes
  ├─ Apply delay
  └─ Repeat
    ↓
Parallel: Reply Listener (separate worker)
  └─ Listen for incoming messages → save to DB
```

---

## Modules

### 1. Authentication Module

**Files:**
- `auth.py` - Login/logout logic
- `decorators.py` - @login_required decorator

**Endpoints:**
- `GET /` → Login page
- `POST /login` → Authenticate user
- `GET /logout` → Logout

**Logic:**
```python
@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    user = User.query.filter_by(username=username).first()
    
    if user and check_password_hash(user.password_hash, password):
        session['user_id'] = user.id
        user.last_login = datetime.now()
        db.session.commit()
        return redirect('/dashboard')
    else:
        flash('Invalid credentials', 'error')
        return redirect('/')
```

---

### 2. Dashboard Module

**Files:**
- `dashboard.py` - Dashboard routes
- `templates/dashboard.html`

**Endpoints:**
- `GET /dashboard` → Main dashboard

**Display:**
- Quick stats (accounts, proxies, campaigns)
- Active campaigns
- Recent activity
- Growth chart
- Notifications

---

### 3. Accounts Module

**Files:**
- `accounts.py` - Account management
- `device_emulator.py` - Device profile generation
- `templates/accounts/*.html`

**Endpoints:**
- `GET /accounts` → List all accounts
- `POST /accounts/upload` → Upload .session files
- `GET /accounts/<id>` → Account details
- `POST /accounts/<id>/subscriptions` → Manage subscriptions
- `DELETE /accounts/<id>` → Deactivate account

**Key Functions:**
```python
def upload_sessions(files, proxy_assignments):
    """
    Upload multiple .session files
    - Create device profiles
    - Assign proxies
    - Verify sessions
    - Create subscription schedule
    """
    pass

def generate_device_profile(region='RU'):
    """
    Generate realistic device profile
    Returns: {
        device_model, system_version, 
        app_version, lang_code
    }
    """
    devices = {
        'RU': [
            ('iPhone 13 Pro', 'iOS 16.2', '9.3.1'),
            ('Samsung Galaxy S21', 'Android 13', '9.2.5'),
            ('Xiaomi Mi 11', 'Android 12', '9.3.0'),
            # ... more
        ]
    }
    return random.choice(devices[region])

def verify_session(account_id):
    """
    Test session by calling get_me()
    Update account status
    """
    pass
```

---

### 4. Proxies Module

**Files:**
- `proxies.py` - Proxy management
- `proxy_rotator.py` - Background rotation worker
- `templates/proxies/*.html`

**Endpoints:**
- `GET /proxies` → List proxies
- `POST /proxies` → Add proxy
- `POST /proxies/<id>/test` → Test proxy
- `POST /proxies/<id>/rotate` → Manual rotation
- `DELETE /proxies/<id>` → Delete proxy

**Key Functions:**
```python
def test_proxy(proxy_id):
    """Test proxy connection"""
    proxy = Proxy.query.get(proxy_id)
    
    try:
        # Test with simple HTTP request
        response = requests.get(
            'https://api.ipify.org?format=json',
            proxies={
                'http': f'{proxy.type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}',
                'https': f'{proxy.type}://{proxy.username}:{proxy.password}@{proxy.host}:{proxy.port}'
            },
            timeout=10
        )
        
        current_ip = response.json()['ip']
        proxy.current_ip = current_ip
        proxy.status = 'active'
        db.session.commit()
        
        return {'success': True, 'ip': current_ip}
    except Exception as e:
        proxy.status = 'error'
        db.session.commit()
        return {'success': False, 'error': str(e)}

def rotate_mobile_proxy(proxy_id):
    """Rotate mobile proxy IP"""
    proxy = Proxy.query.get(proxy_id)
    
    if not proxy.is_mobile or not proxy.rotation_url:
        return {'success': False, 'error': 'Not a mobile proxy'}
    
    try:
        # Call rotation URL
        response = requests.get(proxy.rotation_url, timeout=10)
        
        if response.status_code == 200:
            # Wait for IP change
            time.sleep(5)
            
            # Get new IP
            new_ip_response = requests.get(
                'https://api.ipify.org?format=json',
                proxies={...},
                timeout=10
            )
            
            new_ip = new_ip_response.json()['ip']
            proxy.current_ip = new_ip
            proxy.last_rotation = datetime.now()
            db.session.commit()
            
            return {'success': True, 'new_ip': new_ip}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

**Celery Task - Auto Rotation:**
```python
@celery.task
def auto_rotate_mobile_proxies():
    """
    Background task: rotate mobile proxies
    Runs every 15 minutes
    """
    proxies = Proxy.query.filter_by(
        is_mobile=True,
        status='active'
    ).all()
    
    for proxy in proxies:
        # Check if rotation_interval passed
        if proxy.last_rotation:
            elapsed = (datetime.now() - proxy.last_rotation).total_seconds()
            if elapsed >= proxy.rotation_interval:
                rotate_mobile_proxy(proxy.id)
        else:
            rotate_mobile_proxy(proxy.id)
```

---

### 5. Channels Module

**Files:**
- `channels.py` - Channel management
- `channel_posts.py` - Post creation/management
- `channel_messages.py` - Message handling (for groups)
- `templates/channels/*.html`

**Endpoints:**
- `GET /channels` → List channels
- `POST /channels` → Add channel
- `GET /channels/<id>` → Channel details
- `POST /channels/<id>/posts` → Create post
- `PUT /channels/<id>/posts/<post_id>` → Edit post
- `DELETE /channels/<id>/posts/<post_id>` → Delete post
- `POST /channels/<id>/posts/<post_id>/pin` → Pin post
- `GET /channels/<id>/messages` → View messages (groups)
- `POST /channels/<id>/messages/<msg_id>/reply` → Reply to message

**Key Functions:**
```python
def add_channel(username_or_link, owner_account_id):
    """
    Fetch channel info and add to system
    Check admin rights
    """
    pass

def create_post(channel_id, account_id, text, media_file=None, pin=False):
    """Create post in channel"""
    client = get_telethon_client(account_id)
    channel = Channel.query.get(channel_id)
    
    message = await client.send_message(
        entity=channel.username,
        message=text,
        file=media_file if media_file else None
    )
    
    if pin:
        await client.pin_message(channel.username, message.id)
    
    # Save to DB
    post = ChannelPost(
        channel_id=channel_id,
        message_id=message.id,
        text_content=text,
        is_pinned=pin,
        posted_by_account_id=account_id
    )
    db.session.add(post)
    db.session.commit()
    
    return post
```

---

### 6. Invite Campaigns Module

**Files:**
- `invite_campaigns.py` - Campaign CRUD
- `invite_worker.py` - Celery worker
- `templates/campaigns/*.html`

**Endpoints:**
- `GET /campaigns` → List campaigns
- `POST /campaigns` → Create campaign
- `GET /campaigns/<id>` → Campaign details
- `POST /campaigns/<id>/start` → Start campaign
- `POST /campaigns/<id>/pause` → Pause campaign
- `POST /campaigns/<id>/stop` → Stop campaign
- `POST /campaigns/<id>/import-users` → Import source users
- `GET /campaigns/<id>/logs` → View logs

**Key Functions:**
```python
def create_campaign(data):
    """
    Create new invite campaign
    - Parse users from source channels
    - Assign accounts
    - Set strategy/limits
    """
    campaign = InviteCampaign(**data)
    db.session.add(campaign)
    db.session.commit()
    
    # Parse users if source provided
    if data.get('source_channel'):
        parse_users_from_channel.delay(
            campaign.id, 
            data['source_channel'],
            data.get('filters', {})
        )
    
    return campaign

@celery.task
def parse_users_from_channel(campaign_id, channel_username, filters):
    """Parse members from channel"""
    campaign = InviteCampaign.query.get(campaign_id)
    account = campaign.campaign_accounts[0].account  # Use first account to parse
    
    client = get_telethon_client(account.id)
    
    try:
        channel = await client.get_entity(channel_username)
        participants = await client.get_participants(
            channel,
            limit=None
        )
        
        for user in participants:
            # Apply filters
            if filters.get('exclude_bots') and user.bot:
                continue
            if filters.get('exclude_admins') and hasattr(user, 'admin_rights'):
                continue
            
            # Calculate priority score
            score = calculate_user_score(user)
            
            # Add to source_users
            source_user = SourceUser(
                campaign_id=campaign_id,
                user_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                source=channel_username,
                priority_score=score
            )
            db.session.add(source_user)
        
        db.session.commit()
        campaign.total_targets = len(participants)
        db.session.commit()
        
    except Exception as e:
        print(f"Error parsing: {e}")

def calculate_user_score(user):
    """Calculate priority score 0-100"""
    score = 50  # base
    
    if user.photo:  # has profile photo
        score += 20
    if user.premium:  # Premium user
        score += 15
    if user.username:  # has username
        score += 10
    # ... more criteria
    
    return min(score, 100)
```

**Celery Worker - Invite Campaign:**
```python
@celery.task
def run_invite_campaign(campaign_id):
    """Main invite worker"""
    campaign = InviteCampaign.query.get(campaign_id)
    accounts = [ca.account for ca in campaign.campaign_accounts]
    current_account_index = 0
    
    while campaign.status == 'active':
        # Check working hours
        if not is_working_hours(campaign):
            time.sleep(60)
            continue
        
        # Round-robin account selection
        account = accounts[current_account_index]
        current_account_index = (current_account_index + 1) % len(accounts)
        
        # Check account limits
        if account.invites_sent_today >= get_daily_limit(account):
            continue  # Skip this account
        
        # Get next target (highest priority score)
        target = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            status='pending'
        ).order_by(SourceUser.priority_score.desc()).first()
        
        if not target:
            campaign.status = 'completed'
            db.session.commit()
            break
        
        # Send invite
        result = send_invite(account.id, campaign.channel_id, target.user_id)
        
        # Log result
        log_invite(campaign_id, account.id, target.id, result)
        
        # Update stats
        if result['status'] == 'success':
            target.status = 'invited'
            target.invited_at = datetime.now()
            target.invited_by_account_id = account.id
            campaign.invited_count += 1
            account.invites_sent_today += 1
        else:
            target.status = 'failed'
            target.error_message = result.get('error')
            campaign.failed_count += 1
        
        db.session.commit()
        
        # Apply delay
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        time.sleep(delay)
        
        # Check burst limit
        if account.invites_sent_today % campaign.burst_limit == 0:
            time.sleep(campaign.burst_pause_minutes * 60)

def send_invite(account_id, channel_id, target_user_id):
    """Send single invite"""
    try:
        account = Account.query.get(account_id)
        channel = Channel.query.get(channel_id)
        
        client = get_telethon_client(account_id)
        
        # Get user entity
        user = await client.get_entity(target_user_id)
        
        # Invite to channel
        await client(InviteToChannelRequest(
            channel=channel.chat_id,
            users=[user]
        ))
        
        return {'status': 'success'}
        
    except FloodWaitError as e:
        # FloodWait - pause account
        account.status = 'cooldown'
        db.session.commit()
        return {'status': 'flood_wait', 'seconds': e.seconds}
    
    except UserPrivacyRestrictedError:
        return {'status': 'user_privacy'}
    
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

---

### 7. DM Campaigns Module

**Files:**
- `dm_campaigns.py` - DM campaign CRUD
- `dm_worker.py` - Celery worker
- `dm_reply_listener.py` - Reply listener worker
- `templates/dm_campaigns/*.html`

**Endpoints:**
- `GET /dm-campaigns` → List DM campaigns
- `POST /dm-campaigns` → Create campaign
- `GET /dm-campaigns/<id>` → Campaign details
- `POST /dm-campaigns/<id>/start` → Start
- `POST /dm-campaigns/<id>/pause` → Pause
- `POST /dm-campaigns/<id>/stop` → Stop
- `POST /dm-campaigns/<id>/restart` → Restart from beginning
- `POST /dm-campaigns/<id>/continue` → Continue (only new targets)
- `POST /dm-campaigns/<id>/import-targets` → Import CSV/XLS
- `GET /dm-campaigns/<id>/conversations` → View conversations
- `POST /dm-campaigns/<id>/send-manual` → Send manual message
- `DELETE /dm-campaigns/<id>/targets` → Bulk delete targets

**Key Functions:**
```python
def import_targets_from_csv(campaign_id, file_path):
    """Import targets from CSV/XLS"""
    import pandas as pd
    
    df = pd.read_csv(file_path)
    
    valid_count = 0
    for _, row in df.iterrows():
        if 'username' not in row or not row['username']:
            continue  # Skip invalid
        
        target = DMTarget(
            campaign_id=campaign_id,
            username=row['username'],
            first_name=row.get('first_name'),
            last_name=row.get('last_name'),
            custom_data=row.to_dict(),
            source='csv'
        )
        db.session.add(target)
        valid_count += 1
    
    db.session.commit()
    
    campaign = DMCampaign.query.get(campaign_id)
    campaign.total_targets = valid_count
    db.session.commit()
    
    return valid_count

def personalize_message(template, target):
    """Replace variables in template"""
    message = template
    message = message.replace('{{first_name}}', target.first_name or 'друг')
    message = message.replace('{{last_name}}', target.last_name or '')
    message = message.replace('{{username}}', target.username or '')
    
    # Custom fields from CSV
    if target.custom_data:
        for key, value in target.custom_data.items():
            message = message.replace(f'{{{{{key}}}}}', str(value))
    
    return message
```

**Celery Worker - DM Campaign:**
```python
@celery.task
def run_dm_campaign(campaign_id):
    """Main DM worker"""
    campaign = DMCampaign.query.get(campaign_id)
    accounts = [ca.account for ca in campaign.dm_campaign_accounts]
    current_account_index = 0
    
    while campaign.status == 'active':
        # Working hours check
        if not is_working_hours(campaign):
            time.sleep(60)
            continue
        
        # Select account (round-robin)
        account = accounts[current_account_index]
        current_account_index = (current_account_index + 1) % len(accounts)
        
        # Check account limit
        campaign_account = DMCampaignAccount.query.filter_by(
            campaign_id=campaign_id,
            account_id=account.id
        ).first()
        
        if campaign_account.messages_sent >= campaign.messages_per_account_limit:
            campaign_account.status = 'limit_reached'
            db.session.commit()
            
            # Check if all accounts reached limit
            all_at_limit = all(
                ca.status == 'limit_reached' 
                for ca in campaign.dm_campaign_accounts
            )
            
            if all_at_limit:
                campaign.status = 'limit_reached'
                db.session.commit()
                send_notification_limit_reached(campaign_id)
                break
            
            continue
        
        # Get next target (status = 'new')
        target = DMTarget.query.filter_by(
            campaign_id=campaign_id,
            status='new'
        ).first()
        
        if not target:
            campaign.status = 'completed'
            db.session.commit()
            break
        
        # Personalize message
        message_text = personalize_message(campaign.message_text, target)
        
        # Send DM
        result = send_dm(
            account.id, 
            target.username, 
            message_text,
            campaign.media_file_path
        )
        
        # Update status
        if result['status'] == 'success':
            target.status = 'sent'
            target.sent_at = datetime.now()
            target.sent_by_account_id = account.id
            campaign.sent_count += 1
            campaign_account.messages_sent += 1
            
            # Save to message history
            dm_message = DMMessage(
                campaign_id=campaign_id,
                target_id=target.id,
                account_id=account.id,
                direction='outgoing',
                message_text=message_text,
                has_media=(campaign.media_type != 'none'),
                telegram_message_id=result['message_id']
            )
            db.session.add(dm_message)
        else:
            target.status = 'error'
            target.error_message = result.get('error')
            campaign.error_count += 1
        
        db.session.commit()
        
        # Delay
        delay = random.randint(campaign.delay_min, campaign.delay_max)
        time.sleep(delay)

def send_dm(account_id, username, message_text, media_file=None):
    """Send DM to user"""
    try:
        client = get_telethon_client(account_id)
        
        # Get user
        user = await client.get_entity(username)
        
        # Send message
        message = await client.send_message(
            entity=user,
            message=message_text,
            file=media_file if media_file else None
        )
        
        return {'status': 'success', 'message_id': message.id}
        
    except FloodWaitError as e:
        return {'status': 'error', 'error': f'FloodWait: {e.seconds}s'}
    except UserPrivacyRestrictedError:
        return {'status': 'error', 'error': 'Privacy restricted'}
    except Exception as e:
        return {'status': 'error', 'error': str(e)}
```

**Reply Listener:**
```python
@celery.task
def dm_reply_listener():
    """Listen for incoming DM replies"""
    # Get all accounts used in active DM campaigns
    active_campaigns = DMCampaign.query.filter_by(status='active').all()
    account_ids = set()
    
    for campaign in active_campaigns:
        for ca in campaign.dm_campaign_accounts:
            account_ids.add(ca.account_id)
    
    # Start listeners for each account
    tasks = []
    for account_id in account_ids:
        task = listen_account_replies(account_id)
        tasks.append(task)
    
    await asyncio.gather(*tasks)

async def listen_account_replies(account_id):
    """Listen to one account"""
    client = get_telethon_client(account_id)
    
    @client.on(events.NewMessage(incoming=True))
    async def handler(event):
        sender = await event.get_sender()
        
        # Find target by username
        target = DMTarget.query.filter_by(
            username=f'@{sender.username}',
            sent_by_account_id=account_id
        ).first()
        
        if target:
            # Save reply
            target.replied_at = datetime.now()
            
            dm_message = DMMessage(
                campaign_id=target.campaign_id,
                target_id=target.id,
                account_id=account_id,
                direction='incoming',
                message_text=event.message.text,
                telegram_message_id=event.message.id
            )
            db.session.add(dm_message)
            db.session.commit()
            
            # Send notification
            send_notification_new_reply(target.campaign_id, sender.username)
    
    await client.run_until_disconnected()
```

---

### 8. Parser Module (Advanced)

**Files:**
- `parser.py` - Parser logic
- `parser_worker.py` - Background parsing
- `templates/parser/*.html`

**Endpoints:**
- `GET /parser` → Parser dashboard
- `POST /parser/single` → Parse single channel
- `POST /parser/multi` → Parse multiple channels
- `POST /parser/activity` → Parse by activity
- `POST /parser/keyword` → Parse by keyword
- `GET /parser/library` → User library
- `POST /parser/library/export` → Export to campaign

**Key Functions:**
```python
@celery.task
def parse_multiple_channels(channel_list, filters, account_id):
    """Parse from multiple channels"""
    client = get_telethon_client(account_id)
    
    all_users = {}  # user_id -> user_data
    
    for channel_username in channel_list:
        try:
            channel = await client.get_entity(channel_username)
            participants = await client.get_participants(channel, limit=None)
            
            for user in participants:
                # Deduplicate
                if user.id not in all_users:
                    all_users[user.id] = {
                        'user_id': user.id,
                        'username': user.username,
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'has_photo': bool(user.photo),
                        'is_premium': user.premium,
                        'sources': [channel_username]
                    }
                else:
                    # User in multiple sources
                    all_users[user.id]['sources'].append(channel_username)
        except Exception as e:
            print(f"Error parsing {channel_username}: {e}")
    
    # Apply filters
    filtered_users = apply_filters(all_users.values(), filters)
    
    # Save to library
    for user_data in filtered_users:
        parsed_user = ParsedUserLibrary(
            collection_name=filters.get('collection_name', 'Default'),
            user_id=user_data['user_id'],
            username=user_data['username'],
            first_name=user_data['first_name'],
            last_name=user_data['last_name'],
            source_channel=', '.join(user_data['sources']),
            has_profile_photo=user_data['has_photo'],
            is_premium=user_data['is_premium'],
            metadata={'sources': user_data['sources']}
        )
        db.session.add(parsed_user)
    
    db.session.commit()
    
    return len(filtered_users)

def parse_by_activity(channel_username, days=7, min_messages=5, account_id):
    """Parse users who were active recently"""
    client = get_telethon_client(account_id)
    
    channel = await client.get_entity(channel_username)
    
    # Get messages from last N days
    since_date = datetime.now() - timedelta(days=days)
    messages = await client.get_messages(
        channel,
        limit=None,
        offset_date=since_date
    )
    
    # Count activity per user
    user_activity = {}
    for msg in messages:
        if msg.sender_id:
            user_activity[msg.sender_id] = user_activity.get(msg.sender_id, 0) + 1
    
    # Filter by min_messages
    active_users = [
        user_id for user_id, count in user_activity.items()
        if count >= min_messages
    ]
    
    # Get user details
    result = []
    for user_id in active_users:
        try:
            user = await client.get_entity(user_id)
            result.append({
                'user_id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'activity_count': user_activity[user_id]
            })
        except:
            pass
    
    return result

def parse_by_keyword(keyword, channels, search_in, account_id):
    """Parse users who mentioned keyword"""
    client = get_telethon_client(account_id)
    
    found_users = set()
    
    for channel_username in channels:
        channel = await client.get_entity(channel_username)
        
        if 'messages' in search_in:
            # Search in messages
            messages = await client.get_messages(
                channel,
                search=keyword,
                limit=None
            )
            for msg in messages:
                if msg.sender_id:
                    found_users.add(msg.sender_id)
        
        if 'bios' in search_in:
            # Get all participants and check bios
            participants = await client.get_participants(channel, limit=None)
            for user in participants:
                full_user = await client(GetFullUserRequest(user.id))
                if keyword.lower() in (full_user.about or '').lower():
                    found_users.add(user.id)
    
    return list(found_users)
```

---

### 9. Analytics Module

**Files:**
- `analytics.py` - Analytics logic
- `report_generator.py` - Report generation
- `templates/analytics/*.html`

**Endpoints:**
- `GET /analytics` → Analytics dashboard
- `GET /analytics/campaigns` → Campaign analytics
- `GET /analytics/accounts` → Account performance
- `POST /analytics/export` → Export report

**Key Functions:**
```python
def get_campaign_analytics(campaign_id, campaign_type):
    """Get detailed campaign analytics"""
    if campaign_type == 'invite':
        campaign = InviteCampaign.query.get(campaign_id)
        
        # Calculate metrics
        total_sent = campaign.invited_count + campaign.failed_count
        success_rate = (campaign.invited_count / total_sent * 100) if total_sent > 0 else 0
        
        # Account performance
        account_stats = db.session.query(
            Account.id,
            Account.phone,
            func.count(InviteLog.id).label('invites'),
            func.sum(case((InviteLog.status == 'success', 1), else_=0)).label('success')
        ).join(InviteLog).filter(
            InviteLog.campaign_id == campaign_id
        ).group_by(Account.id, Account.phone).all()
        
        # Error breakdown
        error_stats = db.session.query(
            InviteLog.status,
            func.count(InviteLog.id)
        ).filter(
            InviteLog.campaign_id == campaign_id,
            InviteLog.status != 'success'
        ).group_by(InviteLog.status).all()
        
        # Time-based analysis
        hourly_stats = db.session.query(
            func.date_trunc('hour', InviteLog.timestamp).label('hour'),
            func.count(InviteLog.id).label('count'),
            func.sum(case((InviteLog.status == 'success', 1), else_=0)).label('success')
        ).filter(
            InviteLog.campaign_id == campaign_id
        ).group_by('hour').order_by('hour').all()
        
        return {
            'campaign': campaign,
            'success_rate': success_rate,
            'account_stats': account_stats,
            'error_stats': error_stats,
            'hourly_stats': hourly_stats
        }

def generate_pdf_report(report_type, data, time_period):
    """Generate PDF report"""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    
    filename = f'report_{report_type}_{time_period}.pdf'
    filepath = f'/tmp/{filename}'
    
    c = canvas.Canvas(filepath, pagesize=letter)
    
    # Title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, f"{report_type.title()} Report")
    
    # Content
    y = 700
    c.setFont("Helvetica", 12)
    
    for key, value in data.items():
        c.drawString(100, y, f"{key}: {value}")
        y -= 20
    
    c.save()
    
    return filepath
```

---

### 10. Automation Module

**Files:**
- `automation.py` - Automation logic
- `scheduler_worker.py` - Scheduler background worker
- `templates/automation/*.html`

**Endpoints:**
- `GET /automation` → Automation dashboard
- `GET /automation/scheduled-tasks` → View scheduled tasks
- `POST /automation/scheduled-tasks` → Create scheduled task
- `GET /automation/auto-actions` → View auto-actions
- `POST /automation/auto-actions` → Create auto-action

**Key Functions:**
```python
def create_scheduled_task(task_type, entity_type, entity_id, scheduled_for, payload):
    """Create scheduled task"""
    task = ScheduledTask(
        task_type=task_type,
        entity_type=entity_type,
        entity_id=entity_id,
        scheduled_for=scheduled_for,
        payload=payload
    )
    db.session.add(task)
    db.session.commit()
    return task

@celery.task
def scheduler_worker():
    """
    Background worker: execute scheduled tasks
    Runs every minute
    """
    now = datetime.now()
    
    pending_tasks = ScheduledTask.query.filter(
        ScheduledTask.scheduled_for <= now,
        ScheduledTask.status == 'pending'
    ).all()
    
    for task in pending_tasks:
        try:
            # Execute task based on type
            if task.task_type == 'subscribe_channel':
                execute_subscription(task)
            elif task.task_type == 'post_message':
                execute_post(task)
            elif task.task_type == 'start_campaign':
                execute_campaign_start(task)
            # ... more task types
            
            task.status = 'completed'
            task.executed_at = datetime.now()
        except Exception as e:
            task.status = 'failed'
            task.error_message = str(e)
        
        db.session.commit()

def create_auto_action(name, trigger_type, trigger_condition, action_type, action_params):
    """Create auto-action rule"""
    auto_action = AutoAction(
        name=name,
        trigger_type=trigger_type,
        trigger_condition=trigger_condition,
        action_type=action_type,
        action_params=action_params
    )
    db.session.add(auto_action)
    db.session.commit()
    return auto_action

@celery.task
def check_auto_actions():
    """
    Check if any auto-action triggers are met
    Runs every 5 minutes
    """
    auto_actions = AutoAction.query.filter_by(is_enabled=True).all()
    
    for action in auto_actions:
        if check_trigger(action.trigger_type, action.trigger_condition):
            execute_action(action.action_type, action.action_params)

def check_trigger(trigger_type, condition):
    """Check if trigger condition is met"""
    if trigger_type == 'campaign_progress':
        campaign_id = condition['campaign_id']
        threshold = condition['threshold']
        
        campaign = InviteCampaign.query.get(campaign_id)
        progress = (campaign.invited_count / campaign.total_targets * 100) if campaign.total_targets > 0 else 0
        
        return progress >= threshold
    
    elif trigger_type == 'account_health':
        account_id = condition['account_id']
        threshold = condition['threshold']
        
        account = Account.query.get(account_id)
        return account.health_score < threshold
    
    # ... more trigger types
    
    return False

def execute_action(action_type, params):
    """Execute auto-action"""
    if action_type == 'post_message':
        create_post(
            channel_id=params['channel_id'],
            account_id=params['account_id'],
            text=params['text']
        )
    elif action_type == 'pause_account':
        account = Account.query.get(params['account_id'])
        account.status = 'cooldown'
        db.session.commit()
    elif action_type == 'send_notification':
        send_notification(params['message'])
    # ... more action types
```

---

### 11. Blacklist/Whitelist Module

**Files:**
- `blacklist.py` - Blacklist management
- `risk_assessment.py` - User risk scoring
- `templates/blacklist/*.html`

**Endpoints:**
- `GET /blacklist` → Blacklist management
- `POST /blacklist` → Add to blacklist
- `DELETE /blacklist/<id>` → Remove from blacklist
- `GET /whitelist` → Whitelist management
- `POST /whitelist` → Add to whitelist

**Key Functions:**
```python
def add_to_blacklist(user_id, username, reason, campaign_id=None):
    """Add user to global blacklist"""
    blacklist_entry = GlobalBlacklist(
        user_id=user_id,
        username=username,
        reason=reason,
        added_by_campaign_id=campaign_id
    )
    db.session.add(blacklist_entry)
    db.session.commit()

def is_blacklisted(user_id=None, username=None):
    """Check if user is blacklisted"""
    query = GlobalBlacklist.query
    if user_id:
        query = query.filter_by(user_id=user_id)
    if username:
        query = query.filter_by(username=username)
    
    return query.first() is not None

def auto_blacklist_check(user, reply_text=None):
    """Auto-blacklist based on behavior"""
    # Check for stop keywords
    stop_keywords = ['stop', 'spam', 'unsubscribe', 'отпишись']
    
    if reply_text:
        for keyword in stop_keywords:
            if keyword.lower() in reply_text.lower():
                add_to_blacklist(
                    user_id=user.id,
                    username=user.username,
                    reason='stop_keyword'
                )
                return True
    
    return False

def calculate_risk_score(user_id, username):
    """Calculate risk score for user"""
    score = 50  # neutral
    
    # Check past interactions
    sent_count = DMTarget.query.filter_by(
        username=username,
        status='sent'
    ).count()
    
    if sent_count > 3:  # Already contacted multiple times
        score += 20
    
    # Check if user replied negatively before
    negative_replies = DMMessage.query.filter(
        DMMessage.direction == 'incoming',
        DMMessage.message_text.ilike('%spam%')  # Simple sentiment check
    ).count()
    
    if negative_replies > 0:
        score += 30
    
    # Check if in whitelist
    if is_whitelisted(user_id, username):
        score = 0  # No risk
    
    # Check if in blacklist
    if is_blacklisted(user_id, username):
        score = 100  # Maximum risk
    
    return min(score, 100)
```

---

## API Endpoints

### Authentication
```
POST   /login              - Login
GET    /logout             - Logout
```

### Dashboard
```
GET    /dashboard          - Main dashboard
```

### Accounts
```
GET    /accounts           - List accounts
POST   /accounts/upload    - Upload sessions
GET    /accounts/<id>      - Account details
PUT    /accounts/<id>      - Update account
DELETE /accounts/<id>      - Delete account
POST   /accounts/<id>/subscriptions - Add subscription
DELETE /accounts/<id>/subscriptions/<sub_id> - Remove subscription
```

### Proxies
```
GET    /proxies            - List proxies
POST   /proxies            - Add proxy
PUT    /proxies/<id>       - Update proxy
DELETE /proxies/<id>       - Delete proxy
POST   /proxies/<id>/test  - Test proxy
POST   /proxies/<id>/rotate - Rotate proxy
```

### Channels
```
GET    /channels           - List channels
POST   /channels           - Add channel
GET    /channels/<id>      - Channel details
DELETE /channels/<id>      - Delete channel
POST   /channels/<id>/posts - Create post
PUT    /channels/<id>/posts/<post_id> - Edit post
DELETE /channels/<id>/posts/<post_id> - Delete post
POST   /channels/<id>/posts/<post_id>/pin - Pin post
GET    /channels/<id>/messages - Group messages
POST   /channels/<id>/messages/<msg_id>/reply - Reply
```

### Invite Campaigns
```
GET    /campaigns          - List campaigns
POST   /campaigns          - Create campaign
GET    /campaigns/<id>     - Campaign details
PUT    /campaigns/<id>     - Update campaign
DELETE /campaigns/<id>     - Delete campaign
POST   /campaigns/<id>/start - Start campaign
POST   /campaigns/<id>/pause - Pause campaign
POST   /campaigns/<id>/stop - Stop campaign
POST   /campaigns/<id>/import-users - Import users
GET    /campaigns/<id>/logs - View logs
GET    /campaigns/<id>/stats - Statistics
```

### DM Campaigns
```
GET    /dm-campaigns       - List DM campaigns
POST   /dm-campaigns       - Create DM campaign
GET    /dm-campaigns/<id>  - DM campaign details
PUT    /dm-campaigns/<id>  - Update DM campaign
DELETE /dm-campaigns/<id>  - Delete DM campaign
POST   /dm-campaigns/<id>/start - Start
POST   /dm-campaigns/<id>/pause - Pause
POST   /dm-campaigns/<id>/stop - Stop
POST   /dm-campaigns/<id>/restart - Restart
POST   /dm-campaigns/<id>/continue - Continue
POST   /dm-campaigns/<id>/import - Import targets
POST   /dm-campaigns/<id>/send-manual - Manual send
DELETE /dm-campaigns/<id>/targets - Delete targets
GET    /dm-campaigns/<id>/conversations - View conversations
```

### Parser
```
GET    /parser             - Parser dashboard
POST   /parser/single      - Parse single channel
POST   /parser/multi       - Parse multiple channels
POST   /parser/activity    - Parse by activity
POST   /parser/keyword     - Parse by keyword
GET    /parser/library     - User library
POST   /parser/library/export - Export to campaign
```

### Analytics
```
GET    /analytics          - Analytics dashboard
GET    /analytics/campaigns/<id> - Campaign analytics
GET    /analytics/accounts/<id> - Account analytics
POST   /analytics/export   - Export report
```

### Automation
```
GET    /automation         - Automation dashboard
GET    /automation/scheduled - Scheduled tasks
POST   /automation/scheduled - Create scheduled task
DELETE /automation/scheduled/<id> - Delete task
GET    /automation/auto-actions - Auto-actions
POST   /automation/auto-actions - Create auto-action
PUT    /automation/auto-actions/<id> - Update auto-action
DELETE /automation/auto-actions/<id> - Delete auto-action
```

### Blacklist/Whitelist
```
GET    /blacklist          - View blacklist
POST   /blacklist          - Add to blacklist
DELETE /blacklist/<id>     - Remove from blacklist
GET    /whitelist          - View whitelist
POST   /whitelist          - Add to whitelist
DELETE /whitelist/<id>     - Remove from whitelist
```

---

## Background Workers

### Celery Tasks
```python
# celery_app.py
from celery import Celery
from celery.schedules import crontab

celery = Celery(
    'telegram_system',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Europe/Moscow',
    enable_utc=True,
)

# Periodic tasks
celery.conf.beat_schedule = {
    # Proxy rotation every 15 minutes
    'rotate-mobile-proxies': {
        'task': 'tasks.auto_rotate_mobile_proxies',
        'schedule': crontab(minute='*/15'),
    },
    
    # Account health check every hour
    'check-account-health': {
        'task': 'tasks.check_account_health',
        'schedule': crontab(minute=0),
    },
    
    # Execute scheduled tasks every minute
    'execute-scheduled-tasks': {
        'task': 'tasks.scheduler_worker',
        'schedule': crontab(minute='*'),
    },
    
    # Check auto-actions every 5 minutes
    'check-auto-actions': {
        'task': 'tasks.check_auto_actions',
        'schedule': crontab(minute='*/5'),
    },
    
    # Daily statistics aggregation
    'aggregate-daily-stats': {
        'task': 'tasks.aggregate_daily_stats',
        'schedule': crontab(hour=0, minute=5),
    },
    
    # Cleanup old logs weekly
    'cleanup-old-logs': {
        'task': 'tasks.cleanup_old_logs',
        'schedule': crontab(day_of_week=0, hour=2),
    },
}
```

### Worker Types

**1. Campaign Workers:**
- `run_invite_campaign(campaign_id)` - Main invite loop
- `run_dm_campaign(campaign_id)` - Main DM loop

**2. Listener Workers:**
- `dm_reply_listener()` - Listen for DM replies
- `group_message_listener(channel_id)` - Listen for group messages

**3. Maintenance Workers:**
- `auto_rotate_mobile_proxies()` - Rotate proxies
- `check_account_health()` - Verify account status
- `cleanup_old_logs()` - Clean old data

**4. Scheduler Workers:**
- `scheduler_worker()` - Execute scheduled tasks
- `check_auto_actions()` - Check auto-action triggers

**5. Parser Workers:**
- `parse_users_from_channel(campaign_id, channel, filters)`
- `parse_multiple_channels(channels, filters)`
- `parse_by_activity(channel, days, min_messages)`

---

## File Structure
```
telegram-system/
│
├── app.py                      # Main Flask application
├── config.py                   # Configuration
├── requirements.txt            # Python dependencies
├── celery_app.py              # Celery configuration
│
├── models/                     # Database models
│   ├── __init__.py
│   ├── user.py
│   ├── account.py
│   ├── proxy.py
│   ├── channel.py
│   ├── campaign.py
│   ├── dm_campaign.py
│   ├── parser.py
│   ├── analytics.py
│   └── automation.py
│
├── routes/                     # Flask routes (views)
│   ├── __init__.py
│   ├── auth.py
│   ├── dashboard.py
│   ├── accounts.py
│   ├── proxies.py
│   ├── channels.py
│   ├── campaigns.py
│   ├── dm_campaigns.py
│   ├── parser.py
│   ├── analytics.py
│   └── automation.py
│
├── services/                   # Business logic
│   ├── __init__.py
│   ├── account_service.py
│   ├── proxy_service.py
│   ├── channel_service.py
│   ├── campaign_service.py
│   ├── dm_service.py
│   ├── parser_service.py
│   ├── analytics_service.py
│   └── automation_service.py
│
├── workers/                    # Celery workers
│   ├── __init__.py
│   ├── invite_worker.py
│   ├── dm_worker.py
│   ├── reply_listener.py
│   ├── parser_worker.py
│   ├── scheduler_worker.py
│   └── maintenance_workers.py
│
├── utils/                      # Utility functions
│   ├── __init__.py
│   ├── telethon_helper.py     # Telethon client management
│   ├── device_emulator.py     # Device profile generation
│   ├── proxy_helper.py        # Proxy utilities
│   ├── validators.py          # Input validation
│   ├── decorators.py          # Custom decorators
│   └── notifications.py       # Notification system
│
├── templates/                  # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   │
│   ├── accounts/
│   │   ├── list.html
│   │   ├── upload.html
│   │   ├── detail.html
│   │   └── subscriptions.html
│   │
│   ├── proxies/
│   │   ├── list.html
│   │   └── add.html
│   │
│   ├── channels/
│   │   ├── list.html
│   │   ├── detail.html
│   │   ├── posts.html
│   │   └── messages.html
│   │
│   ├── campaigns/
│   │   ├── list.html
│   │   ├── create.html
│   │   ├── detail.html
│   │   └── logs.html
│   │
│   ├── dm_campaigns/
│   │   ├── list.html
│   │   ├── create.html
│   │   ├── detail.html
│   │   └── conversations.html
│   │
│   ├── parser/
│   │   ├── dashboard.html
│   │   ├── single.html
│   │   ├── multi.html
│   │   └── library.html
│   │
│   ├── analytics/
│   │   ├── dashboard.html
│   │   ├── campaigns.html
│   │   └── accounts.html
│   │
│   └── automation/
│       ├── dashboard.html
│       ├── scheduled.html
│       └── auto_actions.html
│
├── static/                     # Static files
│   ├── css/
│   │   ├── bootstrap.min.css
│   │   └── custom.css
│   │
│   ├── js/
│   │   ├── jquery.min.js
│   │   ├── bootstrap.min.js
│   │   └── custom.js
│   │
│   └── images/
│
├── uploads/                    # User uploads
│   ├── sessions/              # .session files
│   ├── media/                 # Media files for posts/DMs
│   └── csv/                   # Uploaded CSV/XLS files
│
├── outputs/                    # Generated files
│   ├── reports/               # Generated reports
│   └── exports/               # Exported data
│
└── logs/                       # Application logs
    ├── app.log
    ├── celery.log
    └── error.log
```

---

## Installation & Setup

### Prerequisites
```bash
# Python 3.9+
python --version

# PostgreSQL 14+
psql --version

# Redis
redis-cli --version
```

### Installation Steps

**1. Clone repository:**
```bash
git clone https://github.com/your-repo/telegram-system.git
cd telegram-system
```

**2. Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Setup PostgreSQL:**
```bash
# Create database
createdb telegram_system

# Run migrations
flask db upgrade
```

**5. Setup Redis:**
```bash
# Start Redis server
redis-server
```

**6. Configure environment:**
```bash
# Create .env file
cp .env.example .env

# Edit .env:
DATABASE_URL=postgresql://user:password@localhost/telegram_system
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
TG_API_ID=12345678
TG_API_HASH=abcdef123456
```

**7. Initialize database:**
```bash
flask db init
flask db migrate
flask db upgrade

# Create default admin user
flask create-admin
```

**8. Start services:**

Terminal 1 - Flask app:
```bash
flask run
```

Terminal 2 - Celery worker:
```bash
celery -A celery_app worker --loglevel=info
```

Terminal 3 - Celery beat (scheduler):
```bash
celery -A celery_app beat --loglevel=info
```

**9. Access application:**
```
http://localhost:5000
Login: admin
Password: admin123
```

---

## Development Roadmap

### Phase 1: Core System (MVP) ✅
- [x] Authentication (login/password)
- [x] Account management (upload sessions, device emulation)
- [x] Proxy management (mobile proxies, rotation)
- [x] Channel management (basic CRUD)
- [x] Invite campaigns (with anti-ban)
- [x] DM campaigns (with limits)
- [x] Basic analytics

### Phase 2: Enhanced Features (Current)
- [ ] Advanced parser (multi-source, activity, keyword)
- [ ] Blacklist/Whitelist management
- [ ] Automation (scheduling, auto-actions)
- [ ] Detailed analytics & reports
- [ ] Channel post management
- [ ] Group message handling
- [ ] Reply listener for DMs

### Phase 3: Advanced Features (Backlog)
- [ ] Team management (multi-user, roles)
- [ ] Integrations (Google Sheets, Webhooks, API)
- [ ] Backup & Restore
- [ ] Advanced notifications
- [ ] Subscription plans (Free/Pro/Enterprise)
- [ ] User registration system
- [ ] Template library
- [ ] A/B testing
- [ ] AI recommendations
- [ ] Mobile app

### Phase 4: Enterprise Features
- [ ] Multi-tenant support
- [ ] Billing system
- [ ] Advanced CRM integration
- [ ] Custom dashboards
- [ ] White-label option
- [ ] SSO integration
- [ ] Advanced security features

---

## Development Tips for AI

### When implementing features:

**1. Database First:**
```python
# Always create models first
class NewFeature(db.Model):
    __tablename__ = 'new_features'
    # ... fields
    
# Then create migration
flask db migrate -m "Add new feature"
flask db upgrade
```

**2. Service Layer Pattern:**
```python
# Keep routes thin, logic in services
# routes/feature.py
@bp.route('/feature')
def feature():
    result = feature_service.do_something()
    return render_template('feature.html', result=result)

# services/feature_service.py
def do_something():
    # Business logic here
    pass
```

**3. Background Tasks:**
```python
# For long-running operations, use Celery
@celery.task
def long_operation(param):
    # Do work
    pass

# Call from route
long_operation.delay(param)
```

**4. Error Handling:**
```python
try:
    # Operation
except SpecificException as e:
    logger.error(f"Error: {e}")
    flash('User-friendly message', 'error')
    return redirect(url_for('route'))
```

**5. Testing:**
```python
# Write tests for critical functions
def test_invite_campaign():
    campaign = create_campaign(...)
    assert campaign.status == 'draft'
```

---

## Common Issues & Solutions

### Issue: Telethon FloodWait
**Solution:** Implement proper cooldown handling
```python
except FloodWaitError as e:
    account.cooldown_until = datetime.now() + timedelta(seconds=e.seconds)
    db.session.commit()
```

### Issue: Proxy rotation not working
**Solution:** Check rotation URL format and credentials
```python
# Test rotation endpoint separately
response = requests.get(proxy.rotation_url)
assert response.status_code == 200
```

### Issue: Sessions becoming invalid
**Solution:** Implement session validation
```python
@celery.task
def validate_all_sessions():
    for account in Account.query.all():
        try:
            client = TelegramClient(account.session_file_path, ...)
            await client.get_me()
            account.status = 'active'
        except:
            account.status = 'invalid'
        db.session.commit()
```

---

## Security Considerations

1. **Never commit:**
   - `.session` files
   - API credentials
   - Database passwords
   - Secret keys

2. **Always encrypt:**
   - Session files at rest
   - Passwords (use bcrypt)
   - Sensitive config (use environment variables)

3. **Validate input:**
   - Sanitize all user inputs
   - Validate file uploads
   - Check permissions before actions

4. **Rate limiting:**
   - Implement rate limits on API endpoints
   - Throttle authentication attempts
   - Limit file upload sizes

---

## Support & Maintenance

### Logging
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Campaign started")
logger.error("Error occurred", exc_info=True)
```

### Monitoring
- Check Celery worker status: `celery -A celery_app inspect active`
- Monitor Redis: `redis-cli info`
- Check database connections: `SELECT * FROM pg_stat_activity;`

### Backup
```bash
# Database backup
pg_dump telegram_system > backup.sql

# Session files backup
tar -czf sessions_backup.tar.gz uploads/sessions/
```

---

**END OF SPECIFICATION**

This document should provide AI assistants with complete context for developing the Telegram Invite & DM System. Update as needed when requirements change.