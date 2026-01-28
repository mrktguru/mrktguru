from models.campaign import InviteCampaign, InviteLog, Account, SourceUser
from sqlalchemy import func
from database import db
import csv
from io import StringIO

class CampaignStats:
    @staticmethod
    def get_detailed_stats(campaign_id):
        campaign = InviteCampaign.query.get_or_404(campaign_id)
        
        # Overall stats
        total_sent = campaign.invited_count + campaign.failed_count
        success_rate = (campaign.invited_count / total_sent * 100) if total_sent > 0 else 0
        
        # Stats by status
        status_stats = db.session.query(
            InviteLog.status,
            func.count(InviteLog.id).label("count")
        ).filter(
            InviteLog.campaign_id == campaign_id
        ).group_by(InviteLog.status).all()
        
        # Stats by account
        account_stats = db.session.query(
            Account.phone,
            func.count(InviteLog.id).label("total"),
            func.sum(db.case((InviteLog.status == "success", 1), else_=0)).label("success")
        ).join(InviteLog, InviteLog.account_id == Account.id).filter(
            InviteLog.campaign_id == campaign_id
        ).group_by(Account.phone).all()
        
        # Hourly distribution
        hourly_stats = db.session.query(
            func.date_trunc("hour", InviteLog.timestamp).label("hour"),
            func.count(InviteLog.id).label("count")
        ).filter(
            InviteLog.campaign_id == campaign_id
        ).group_by("hour").order_by("hour").all()
        
        return {
            'campaign': campaign,
            'success_rate': success_rate,
            'status_stats': status_stats,
            'account_stats': account_stats,
            'hourly_stats': hourly_stats
        }

    @staticmethod
    def generate_csv_export(campaign_id):
        targets = SourceUser.query.filter_by(campaign_id=campaign_id).all()
        
        si = StringIO()
        writer = csv.writer(si)
        writer.writerow(["Username", "First Name", "Last Name", "Status", "Invited At", "Priority Score", "Source"])
        
        for target in targets:
            writer.writerow([
                target.username or "",
                target.first_name or "",
                target.last_name or "",
                target.status,
                target.invited_at.strftime("%Y-%m-%d %H:%M:%S") if target.invited_at else "",
                target.priority_score,
                target.source
            ])
            
        return si.getvalue()
