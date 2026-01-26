
from app import app, db
from sqlalchemy import text, inspect

def migrate():
    print("Starting migration: Adding source and tags to accounts...")
    with app.app_context():
        inspector = inspect(db.engine)
        columns = [c['name'] for c in inspector.get_columns('accounts')]
        
        with db.engine.connect() as conn:
            # Check source
            if 'source' in columns:
                print("Column 'source' already exists.")
            else:
                print("Adding column 'source'...")
                conn.execute(text("ALTER TABLE accounts ADD COLUMN source VARCHAR(255)"))
                conn.commit()
                print("Added 'source'")
                
            # Check tags
            if 'tags' in columns:
                print("Column 'tags' already exists.")
            else:
                print("Adding column 'tags'...")
                if 'sqlite' in str(db.engine.url):
                     # SQLite doesn't strictly enforce JSON type but we can use JSON or TEXT
                     conn.execute(text("ALTER TABLE accounts ADD COLUMN tags JSON"))
                else:
                     # PostgreSQL
                     conn.execute(text("ALTER TABLE accounts ADD COLUMN tags JSON"))
                conn.commit()
                print("Added 'tags'")

        print("✅ Migration checks completed")

if __name__ == "__main__":
    migrate()
