from app import app, db
from sqlalchemy import text

def migrate_indices():
    with app.app_context():
        print("Running Dynamic Proxy Index Migration...")
        
        try:
            # Add index for proxy_network_id
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_accounts_proxy_network_id ON accounts(proxy_network_id);"))
            print("✅ Created index 'idx_accounts_proxy_network_id'.")
            
            # Add index for assigned_port (useful for the order_by query)
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_accounts_assigned_port ON accounts(assigned_port);"))
            print("✅ Created index 'idx_accounts_assigned_port'.")
            
            # Composite index might be even better for the specific query:
            # filter(proxy_network_id == X, assigned_port != None)
            db.session.execute(text("CREATE INDEX IF NOT EXISTS idx_accounts_network_port ON accounts(proxy_network_id, assigned_port);"))
            print("✅ Created composite index 'idx_accounts_network_port'.")
            
        except Exception as e:
            print(f"⚠️ Error creating indices: {e}")
            db.session.rollback()

        db.session.commit()
        print("Index migration complete.")

if __name__ == "__main__":
    migrate_indices()
