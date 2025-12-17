from app import db

# Import all models for Flask-Migrate to detect them
from models.user import User
from models.account import Account, DeviceProfile, AccountSubscription
from models.proxy import Proxy
from models.channel import Channel, ChannelPost, ChannelMessage
from models.campaign import InviteCampaign, CampaignAccount, SourceUser, InviteLog
from models.dm_campaign import DMCampaign, DMCampaignAccount, DMTarget, DMMessage
from models.parser import ParsedUserLibrary, ParseJob
from models.analytics import CampaignStats, Report
from models.automation import ScheduledTask, AutoAction
from models.blacklist import GlobalBlacklist, GlobalWhitelist, ChannelBlacklist

__all__ = [
    'db',
    'User',
    'Account',
    'DeviceProfile',
    'AccountSubscription',
    'Proxy',
    'Channel',
    'ChannelPost',
    'ChannelMessage',
    'InviteCampaign',
    'CampaignAccount',
    'SourceUser',
    'InviteLog',
    'DMCampaign',
    'DMCampaignAccount',
    'DMTarget',
    'DMMessage',
    'ParsedUserLibrary',
    'ParseJob',
    'CampaignStats',
    'Report',
    'ScheduledTask',
    'AutoAction',
    'GlobalBlacklist',
    'GlobalWhitelist',
    'ChannelBlacklist',
]
