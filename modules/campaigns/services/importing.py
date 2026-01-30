from database import db
from models.campaign import InviteCampaign, SourceUser
from werkzeug.utils import secure_filename
import os
import csv
import pandas as pd
from workers.parser_worker import parse_users_for_campaign

class CampaignImporter:
    @staticmethod
    def import_from_file(campaign_id, file):
        if not file or not file.filename:
            return 0, 0, "No file selected"
            
        if not file.filename.endswith((".csv", ".xlsx", ".xls")):
            return 0, 0, "Only CSV and Excel files are supported"
            
        try:
            filename = secure_filename(file.filename)
            upload_dir = "uploads/csv"
            os.makedirs(upload_dir, exist_ok=True)
            filepath = os.path.join(upload_dir, filename)
            file.save(filepath)
            
            users_data = []
            if filename.endswith(".csv"):
                with open(filepath, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    users_data = list(reader)
            else:
                df = pd.read_excel(filepath)
                users_data = df.to_dict("records")
            
            imported = 0
            skipped = 0
            
            for row in users_data:
                username = (row.get("username") or row.get("Username") or "").strip().lstrip("@")
                user_id = row.get("user_id") or row.get("User ID") or row.get("id") or None
                first_name = row.get("first_name") or row.get("First Name") or ""
                last_name = row.get("last_name") or row.get("Last Name") or ""
                
                if not username:
                    skipped += 1
                    continue
                
                existing = SourceUser.query.filter_by(
                    campaign_id=campaign_id,
                    username=username
                ).first()
                
                if existing:
                    skipped += 1
                    continue
                
                try:
                    parsed_user_id = int(float(user_id)) if user_id and str(user_id).strip() and str(user_id).lower() != "nan" else None
                except (ValueError, TypeError):
                    parsed_user_id = None
                
                source_user = SourceUser(
                    campaign_id=campaign_id,
                    username=username,
                    user_id=parsed_user_id,
                    first_name=first_name if first_name and str(first_name).lower() != "nan" else "",
                    last_name=last_name if last_name and str(last_name).lower() != "nan" else "",
                    source="csv_upload",
                    status="pending"
                )
                db.session.add(source_user)
                imported += 1
            
            db.session.commit()
            os.remove(filepath)
            return imported, skipped, None
            
        except Exception as e:
            return 0, 0, str(e)

    @staticmethod
    def parse_from_channel(campaign_id, source_channel, limit=1000, options=None):
        if not source_channel:
            return False, "Source channel required"
            
        parse_users_for_campaign.delay(campaign_id, source_channel.lstrip('@'))
        return True, "Parsing started"
