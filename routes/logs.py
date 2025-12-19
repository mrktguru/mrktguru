from flask import Blueprint, jsonify
from utils.decorators import login_required
from models.campaign import InviteCampaign
from database import db

logs_bp = Blueprint("logs", __name__, url_prefix="/logs")

@logs_bp.route("/campaign/<int:campaign_id>")
@login_required
def get_campaign_logs(campaign_id):
    """Get invite logs for campaign"""
    from sqlalchemy import text
    
    # Get last 100 logs
    sql = """
    SELECT 
        il.id,
        il.created_at,
        il.action,
        il.status,
        il.target_username,
        il.message,
        a.phone as account_phone
    FROM invite_logs il
    LEFT JOIN accounts a ON il.account_id = a.id
    WHERE il.campaign_id = :campaign_id
    ORDER BY il.created_at DESC
    LIMIT 100
    """
    
    result = db.session.execute(text(sql), {"campaign_id": campaign_id})
    logs = []
    
    for row in result:
        logs.append({
            "id": row[0],
            "created_at": row[1].strftime("%Y-%m-%d %H:%M:%S") if row[1] else "",
            "action": row[2],
            "status": row[3],
            "target_username": row[4],
            "message": row[5],
            "account_phone": row[6]
        })
    
    return jsonify({"logs": logs, "count": len(logs)})
