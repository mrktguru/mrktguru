from models.automation import ScheduledTask, AutoAction
from database import db
from datetime import datetime

class AutomationManager:
    @staticmethod
    def schedule_task(data):
        task_type = data.get('task_type')
        entity_type = data.get('entity_type')
        entity_id = data.get('entity_id')
        scheduled_for = data.get('scheduled_for')
        
        task = ScheduledTask(
            task_type=task_type,
            entity_type=entity_type,
            entity_id=int(entity_id) if entity_id else None,
            scheduled_for=datetime.fromisoformat(scheduled_for),
            payload={}
        )
        db.session.add(task)
        db.session.commit()
        return task

    @staticmethod
    def create_auto_action(data):
        name = data.get('name')
        trigger_type = data.get('trigger_type')
        action_type = data.get('action_type')
        
        action = AutoAction(
            name=name,
            trigger_type=trigger_type,
            trigger_condition={},
            action_type=action_type,
            action_params={}
        )
        db.session.add(action)
        db.session.commit()
        return action
