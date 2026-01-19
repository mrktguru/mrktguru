from app import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    with app.app_context():
        # Check if column exists
        with db.engine.connect() as conn:
            result = conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='accounts' AND column_name='phone_code_hash'"))
            if result.fetchone():
                print("Column 'phone_code_hash' already exists.")
                return

            print("Adding 'phone_code_hash' column to accounts table...")
            conn.execute(text("ALTER TABLE accounts ADD COLUMN phone_code_hash VARCHAR(255)"))
            conn.commit()
            print("Migration successful!")

if __name__ == "__main__":
    migrate()
