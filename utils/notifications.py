import logging

logger = logging.getLogger(__name__)


def send_notification(message, level='info'):
    """
    Send notification (currently just logs, can be extended)
    
    Future: email, telegram bot, webhooks, etc.
    """
    if level == 'error':
        logger.error(f"NOTIFICATION: {message}")
    elif level == 'warning':
        logger.warning(f"NOTIFICATION: {message}")
    else:
        logger.info(f"NOTIFICATION: {message}")


def notify_campaign_started(campaign_id, campaign_type):
    """Notify when campaign starts"""
    send_notification(f"{campaign_type.upper()} Campaign {campaign_id} started", 'info')


def notify_campaign_completed(campaign_id, campaign_type, stats):
    """Notify when campaign completes"""
    message = f"{campaign_type.upper()} Campaign {campaign_id} completed. Stats: {stats}"
    send_notification(message, 'info')


def notify_campaign_error(campaign_id, campaign_type, error):
    """Notify when campaign encounters error"""
    message = f"{campaign_type.upper()} Campaign {campaign_id} error: {error}"
    send_notification(message, 'error')


def notify_account_limit_reached(account_id):
    """Notify when account reaches daily limit"""
    send_notification(f"Account {account_id} reached daily limit", 'warning')


def notify_account_flood_wait(account_id, seconds):
    """Notify when account gets FloodWait"""
    send_notification(f"Account {account_id} FloodWait: {seconds}s", 'warning')


def notify_dm_reply(campaign_id, username):
    """Notify when receiving DM reply"""
    send_notification(f"New reply in DM Campaign {campaign_id} from @{username}", 'info')


def notify_dm_campaign_limit_reached(campaign_id):
    """Notify when all accounts in DM campaign reached limits"""
    send_notification(f"DM Campaign {campaign_id} - all accounts reached limits", 'warning')
