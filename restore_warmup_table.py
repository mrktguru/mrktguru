from app import create_app
from database import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    print("Checking for missing tables...")
    try:
        # Check if table exists
        db.session.execute(text("SELECT 1 FROM account_warmup_channels LIMIT 1"))
        print("Table 'account_warmup_channels' ALREADY EXISTS.")
    except Exception as e:
        print(f"Table 'account_warmup_channels' MISSING ({e}). Creating...")
        db.session.rollback()
        
        # Create table manually
        try:
            with db.engine.connect() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS account_warmup_channels (
                        id SERIAL PRIMARY KEY,
                        account_id INTEGER NOT NULL REFERENCES accounts(id),
                        channel_username VARCHAR(255) NOT NULL,
                        source VARCHAR(50) DEFAULT 'manual',
                        is_active BOOLEAN DEFAULT TRUE,
                        last_read_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT _account_warmup_channel_uc UNIQUE (account_id, channel_username)
                    );
                    CREATE INDEX IF NOT EXISTS ix_account_warmup_channels_account_id ON account_warmup_channels (account_id);
                """))
                conn.commit()
            print("Table 'account_warmup_channels' created successfully.")
        except Exception as create_error:
            print(f"FAILED to create table: {create_error}")
