
from app import app, db
from sqlalchemy import text

def migrate():
    print("Starting migration: Adding source and tags to accounts...")
    with app.app_context():
        # Check if columns exist
        with db.engine.connect() as conn:
            # Check source
            try:
                conn.execute(text("SELECT source FROM accounts LIMIT 1"))
                print("Column 'source' already exists.")
            except Exception:
                print("Adding column 'source'...")
                conn.execute(text("ALTER TABLE accounts ADD COLUMN source VARCHAR(255)"))
                conn.commit()
                
            # Check tags
            try:
                conn.execute(text("SELECT tags FROM accounts LIMIT 1"))
                print("Column 'tags' already exists.")
            except Exception:
                print("Adding column 'tags'...")
                # SQLite doesn't have native JSON type in older versions but SQLAlchemy handles it as Text/JSON
                # In raw SQL for SQLite, we create as TEXT or JSON. Postgres uses JSONB/JSON.
                # Since we use SQLAlchemy models, let's trust the altering.
                # But raw SQL is safer for simple adds.
                if 'sqlite' in str(db.engine.url):
                     conn.execute(text("ALTER TABLE accounts ADD COLUMN tags JSON"))
                else:
                     conn.execute(text("ALTER TABLE accounts ADD COLUMN tags JSON"))
                conn.commit()

        print("✅ Migration checks completed")

if __name__ == "__main__":
    migrate()
