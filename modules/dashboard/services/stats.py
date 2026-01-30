from models.account import Account
from models.proxy import Proxy
from models.campaign import InviteCampaign
from models.dm_campaign import DMCampaign
from models.channel import Channel

class DashboardStatsService:
    @staticmethod
    def get_overview_stats():
        return {
            'total_accounts': Account.query.count(),
            'active_accounts': Account.query.filter_by(status='active').count(),
            'total_proxies': Proxy.query.count(),
            'active_proxies': Proxy.query.filter_by(status='active').count(),
            'total_channels': Channel.query.count(),
            'invite_campaigns': InviteCampaign.query.count(),
            'dm_campaigns': DMCampaign.query.count(),
            'active_invite_campaigns': InviteCampaign.query.filter_by(status='active').count(),
            'active_dm_campaigns': DMCampaign.query.filter_by(status='active').count(),
        }
    
    @staticmethod
    def get_recent_campaigns(limit=5):
        recent_invite = InviteCampaign.query.order_by(
            InviteCampaign.created_at.desc()
        ).limit(limit).all()
        
        recent_dm = DMCampaign.query.order_by(
            DMCampaign.created_at.desc()
        ).limit(limit).all()
        
        return recent_invite, recent_dm

    @staticmethod
    def get_accounts_with_issues(limit=5):
        return Account.query.filter(
            Account.status.in_(['cooldown', 'banned'])
        ).limit(limit).all()
