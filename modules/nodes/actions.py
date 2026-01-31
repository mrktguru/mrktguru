import asyncio
import random
import logging
from telethon.tl.functions.contacts import ImportContactsRequest
from telethon.tl.types import InputPhoneContact

from modules.nodes.base import BaseNodeExecutor
from utils.human_behavior import random_sleep, simulate_typing

logger = logging.getLogger(__name__)

class ImportContactsExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            count = int(self.get_config('count', 5))
            contacts_data = self.get_config('contacts', [])
            
            if not contacts_data:
                return {'success': False, 'error': 'No contacts provided'}
            
            contacts_data = contacts_data[:count]
            
            self.log('info', f"Importing {len(contacts_data)} contacts", action='import_start')
            
            # Human-like delay before action
            await random_sleep(5, 10, reason="Preparing to import contacts")
            
            contacts = [
                InputPhoneContact(
                    client_id=i,
                    phone=c['phone'],
                    first_name=c.get('first_name', 'Contact'),
                    last_name=c.get('last_name', '')
                )
                for i, c in enumerate(contacts_data)
            ]
            
            await self.client(ImportContactsRequest(contacts))
            
            await random_sleep(3, 8, reason="Processing import result")
            self.log('success', f"Imported {len(contacts_data)} contacts", action='import_success')
            
            return {'success': True, 'message': f'Imported {len(contacts_data)} contacts'}
            
        except Exception as e:
            logger.error(f"Import contacts node failed: {e}")
            self.log('error', f"Contact import failed: {str(e)}", action='import_error')
            return {'success': False, 'error': str(e)}


class SendMessageExecutor(BaseNodeExecutor):
    async def execute(self):
        try:
            message = self.get_config('message', 'Test message')
            count = int(self.get_config('count', 1))
            
            self.log('info', f"Sending {count} message(s) to Saved Messages", action='send_start')
            
            for i in range(count):
                # Human-like typing simulation
                await simulate_typing(len(message))
                
                await self.client.send_message('me', message)
                self.log('success', f"Message {i+1}/{count} sent", action='send_message')
                
                if i < count - 1:
                    await random_sleep(5, 15, reason="Pause between messages")
            
            return {'success': True, 'message': f'Sent {count} message(s)'}
            
        except Exception as e:
            logger.error(f"Send message node failed: {e}")
            self.log('error', f"Send message failed: {str(e)}", action='send_error')
            return {'success': False, 'error': str(e)}
