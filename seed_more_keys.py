from app import create_app, db
from models.api_credential import ApiCredential

def seed_more_keys():
    app = create_app()
    with app.app_context():
        print("Checking and fixing existing keys...")
        
        # FIX: Ensure Android Official is correct
        android = ApiCredential.query.filter_by(name="Telegram Android (Official)").first()
        if android:
            if android.api_id != 6:
                print(f"⚠️ Fixing Android Official ID: was {android.api_id}, setting to 6")
                android.api_id = 6
                android.api_hash = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
        else:
             print("Adding Missing Telegram Android (Official) [ID 6]")
             db.session.add(ApiCredential(
                name="Telegram Android (Official)",
                api_id=6,
                api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
                client_type="android",
                is_official=True
            ))

        # NEW: Telegram Android X
        if not ApiCredential.query.filter_by(api_id=21724).first():
            print("Adding Telegram Android X [ID 21724]")
            db.session.add(ApiCredential(
                name="Telegram Android X",
                api_id=21724,
                api_hash="3e0cb5efcd52300aec5f94f4c5df4197",
                client_type="android",
                is_official=True
            ))

        # NEW: Telegram Desktop Multi
        if not ApiCredential.query.filter_by(api_id=17349).first():
            print("Adding Telegram Desktop Multi [ID 17349]")
            db.session.add(ApiCredential(
                name="Telegram Desktop Multi",
                api_id=17349,
                api_hash="344583e45741c457fe1862106095a5eb",
                client_type="desktop",
                is_official=True
            ))
            
        # NEW: Telegram Web K
        if not ApiCredential.query.filter_by(api_id=2496).first():
            print("Adding Telegram Web K [ID 2496]")
            db.session.add(ApiCredential(
                name="Telegram Web K",
                api_id=2496,
                api_hash="8da85b0d5bfe62527e5b244c209159c3",
                client_type="web",
                is_official=True
            ))

        db.session.commit()
        print("✅ Expanded API Keys seeded successfully!")

if __name__ == "__main__":
    seed_more_keys()
