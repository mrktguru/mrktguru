from app import app
from database import db
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    print("Detected tables:", tables)
    
    warmup_tables = [
        'warmup_stages',
        'warmup_actions',
        'warmup_channels',
        'warmup_settings',
        'warmup_logs'
    ]
    
    missing = [t for t in warmup_tables if t not in tables]
    if missing:
        print("MISSING TABLES:", missing)
    else:
        print("All warmup tables are present!")
