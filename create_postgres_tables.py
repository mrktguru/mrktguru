#!/usr/bin/env python3
"""
Create all missing PostgreSQL tables based on SQLAlchemy models
Run this after migrating to PostgreSQL to ensure all tables exist
"""
import os
import sys

def create_all_tables():
    from app import app, db
    
    print("Creating all PostgreSQL tables...")
    
    with app.app_context():
        # Import all models to ensure they're registered
        from models.account import Account
        from models.activity_log import AccountActivityLog
        from models.api_credential import ApiCredential
        from models.proxy import Proxy
        from models.user import User
        from models.warmup_log import WarmupLog
        from models.warmup_settings import WarmupSettings
        from models.warmup_stage import WarmupStage
        from models.warmup_action import WarmupAction
        from models.warmup_channel import WarmupChannel
        from models.warmup import WarmupActivity, ConversationPair, WarmupChannelTheme, AccountWarmupChannel
        from models.channel import Channel, ChannelMessage, AccountSubscription
        from models.campaign import Campaign, CampaignAccount
        from models.dm_campaign import DMCampaign, DMTarget, DMMessage, DMCampaignAccount
        from models.parser import ParseJob, SourceUser
        from models.blacklist import GlobalBlacklist, GlobalWhitelist, ChannelBlacklist
        from models.automation import ScheduledTask, InviteLog
        from models.tdata_metadata import TdataMetadata
        
        # Create all tables
        db.create_all()
        
        print("\n✅ All tables created successfully!")
        print("\nTables in database:")
        
        # List all tables
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        for table in sorted(tables):
            print(f"  - {table}")
        
        print(f"\nTotal: {len(tables)} tables")

if __name__ == '__main__':
    create_all_tables()
