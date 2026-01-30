# Deployment Instructions: Manual Warmup Control

## Changes Summary

✅ **Automatic warmup is now DISABLED by default**
- New field `warmup_enabled` added to accounts (default: `False`)
- Warmup worker will only run for accounts where warmup is manually enabled
- UI controls added to enable/disable warmup per account

## Deployment Steps

### 1. Pull Latest Code

```bash
cd ~/mrktguru
git pull origin antigravity_v02
```

### 2. Run Database Migration

```bash
python3 migrate_add_warmup_enabled.py
```

Expected output:
```
📄 Loading environment from .env
📁 Using SQLite database: ./instance/telegram_system.db
Adding 'warmup_enabled' column to accounts table...
✅ Migration completed successfully!
```

### 3. Restart Services

```bash
# Restart web service
systemctl restart mrktguru-web

# Restart worker (important!)
systemctl restart mrktguru-worker

# Check status
systemctl status mrktguru-web
systemctl status mrktguru-worker
```

### 4. Verify Changes

```bash
# Check logs
journalctl -u mrktguru-web -n 50 --no-pager
journalctl -u mrktguru-worker -n 50 --no-pager
```

## How to Use

### For Each Account:

1. Go to account detail page
2. Click "Warmup Settings" tab
3. You'll see a banner:
   - **🔴 Automatic Warmup: DISABLED** (default)
   - Click **"✅ Enable Warmup"** button to activate
4. Once enabled:
   - Banner changes to **🟢 Automatic Warmup: ENABLED**
   - Warmup worker will now run activities for this account
   - Click **"🛑 Disable Warmup"** to stop

### Important Notes:

- **All existing accounts will have warmup DISABLED by default**
- You must manually enable warmup for each account you want to warm up
- This gives you full control over which accounts participate in automatic warmup
- Accounts with `warmup_enabled=False` will be completely skipped by the warmup worker

## Testing

1. Enable warmup for ONE test account
2. Wait for next warmup cycle (check worker logs)
3. Verify only that account gets warmup activities
4. Check that disabled accounts are skipped

```bash
# Watch worker logs
journalctl -u mrktguru-worker -f | grep "warmup"
```

You should see:
```
Account 123 has warmup disabled, skipping
Account 456 has warmup disabled, skipping
# ... only enabled accounts will run
```

## Rollback (if needed)

If you need to revert:

```bash
cd ~/mrktguru
git checkout b67b035  # Previous commit
systemctl restart mrktguru-web mrktguru-worker
```
