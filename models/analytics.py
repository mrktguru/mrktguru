from datetime import datetime
from database import db


class CampaignStats(db.Model):
    """Daily campaign statistics cache"""
    __tablename__ = 'campaign_stats'
    
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer)
    campaign_type = db.Column(db.String(20))  # invite/dm
    date = db.Column(db.Date, nullable=False, index=True)
    sent_count = db.Column(db.Integer, default=0)
    error_count = db.Column(db.Integer, default=0)
    success_rate = db.Column(db.Numeric(5, 2))
    
    __table_args__ = (db.UniqueConstraint('campaign_id', 'campaign_type', 'date', name='_campaign_stats_uc'),)
    
    def __repr__(self):
        return f'<CampaignStats {self.campaign_type} {self.campaign_id} {self.date}>'


class Report(db.Model):
    """Generated reports table"""
    __tablename__ = 'reports'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    report_type = db.Column(db.String(50), nullable=False)  # campaign_summary/account_performance/system_health
    time_period = db.Column(db.String(50))  # last_7_days/last_30_days/custom
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    file_path = db.Column(db.String(500))
    format = db.Column(db.String(20))  # pdf/xlsx/csv
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
    generated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    generated_by = db.relationship('User', backref=db.backref('reports', lazy='dynamic'))
    
    def __repr__(self):
        return f'<Report {self.name}>'
