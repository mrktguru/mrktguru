#!/usr/bin/env python3
"""
Create all missing PostgreSQL tables based on SQLAlchemy models
Run this after migrating to PostgreSQL to ensure all tables exist
"""

def create_all_tables():
    # Import app which will load all models via imports in app.py
    from app import app, db
    
    print("Creating all PostgreSQL tables...")
    print("(Models are auto-discovered from app.py imports)")
    
    with app.app_context():
        # Create all tables - db.create_all() will find all registered models
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
