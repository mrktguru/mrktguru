from models.campaign import SourceUser
from database import db

class TargetManager:
    @staticmethod
    def delete_target(campaign_id, user_id):
        user = SourceUser.query.filter_by(
            campaign_id=campaign_id,
            id=user_id
        ).first_or_404()
        
        db.session.delete(user)
        db.session.commit()
        return True
