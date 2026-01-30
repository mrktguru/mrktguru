from app import create_app, db
from models.api_credential import ApiCredential

def seed_keys():
    app = create_app()
    with app.app_context():
        # 1. Official Android
        android = ApiCredential.query.filter_by(api_id=6).first()
        if not android:
            print("Adding Official Android keys...")
            android = ApiCredential(
                name="Telegram Android (Official)",
                api_id=6,
                api_hash="eb06d4abfb49dc3eeb1aeb98ae0f581e",
                client_type="android",
                is_official=True,
                is_default=True
            )
            db.session.add(android)

        # 2. Official iOS
        ios = ApiCredential.query.filter_by(api_id=8).first()
        if not ios:
            print("Adding Official iOS keys...")
            ios = ApiCredential(
                name="Telegram iOS (Official)",
                api_id=8,
                api_hash="7245de8e747a0d6e281df76862e96745",
                client_type="ios",
                is_official=True
            )
            db.session.add(ios)
            
        # 3. Telegram Desktop (Windows) - old but sometimes works
        tdesktop = ApiCredential.query.filter_by(api_id=2040).first()
        if not tdesktop:
            print("Adding Telegram Desktop keys...")
            tdesktop = ApiCredential(
                name="Telegram Desktop (Official)",
                api_id=2040,
                api_hash="b18441a1bb607e12738205e450b8ad6b",
                client_type="desktop",
                is_official=True
            )
            db.session.add(tdesktop)

        db.session.commit()
        print("✅ API Keys seeded successfully!")

if __name__ == "__main__":
    seed_keys()
