from app import app, db
from sqlalchemy import text

def migrate():
    with app.app_context():
        print("Running Dynamic Proxy Migration...")
        
        # 1. Create proxy_networks table
        try:
            db.session.execute(text("""
                CREATE TABLE IF NOT EXISTS proxy_networks (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100),
                    base_url VARCHAR(255) NOT NULL,
                    start_port INTEGER NOT NULL,
                    end_port INTEGER NOT NULL
                );
            """))
            print("✅ Created 'proxy_networks' table.")
        except Exception as e:
            print(f"⚠️ Error creating table: {e}")
            db.session.rollback()

        # 2. Add columns to accounts
        try:
            db.session.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS proxy_network_id INTEGER REFERENCES proxy_networks(id);"))
            db.session.execute(text("ALTER TABLE accounts ADD COLUMN IF NOT EXISTS assigned_port INTEGER;"))
            print("✅ Added columns to 'accounts'.")
        except Exception as e:
            print(f"⚠️ Error adding columns: {e}")
            db.session.rollback()

        db.session.commit()
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
