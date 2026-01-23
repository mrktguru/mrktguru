import asyncio
import random
import logging
from datetime import datetime

# Импортируем правильный клиент (Opentele/Extended)
from utils.telethon_helper import get_telethon_client

# MTProto запросы
from telethon.tl.functions.help import GetConfigRequest
from telethon.tl.functions.updates import GetStateRequest, GetDifferenceRequest
from telethon.tl.functions.messages import GetDialogsRequest, ReadHistoryRequest, SetTypingRequest
from telethon.tl.functions.contacts import ResolveUsernameRequest, UnblockRequest
from telethon.tl.types import InputPeerEmpty, SendMessageTypingAction

logger = logging.getLogger(__name__)

async def human_delay(action_type='read'):
    """
    Генератор человеческих задержек (Gaussian Distribution).
    uniform - это для роботов. Люди тормозят по нормальному распределению.
    """
    if action_type == 'click':      # Клик мышкой / переключение фокуса
        delay = abs(random.gauss(0.8, 0.3))
    elif action_type == 'type':     # Пауза перед набором текста
        delay = abs(random.gauss(1.5, 0.5))
    elif action_type == 'read':     # Чтение короткого текста
        delay = abs(random.gauss(3.0, 1.0))
    elif action_type == 'scan':     # Сканирование глазами списка чатов
        delay = abs(random.gauss(4.0, 1.5))
    else:
        delay = 1.0
    
    await asyncio.sleep(delay)

async def run_immersive_spamblock_check(account_id):
    """
    🎬 Полная эмуляция проверки спамблока пользователем Desktop версии.
    Возвращает статус аккаунта (Clean/Restricted/Unknown) и лог
    """
    client = None
    result_status = "unknown"
    log_messages = []
    
    def log(msg, level='info'):
        log_messages.append(msg)
        if level == 'info': logger.info(msg)
        elif level == 'error': logger.error(msg)
        else: logger.warning(msg)

    try:
        # === 1. ЗАПУСК "ТЕЛЕГРАМА" ===
        log(f"🎬 [Step 1] Opening Telegram Desktop (Account {account_id})...")
        client = get_telethon_client(account_id)
        await client.connect()
        
        if not await client.is_user_authorized():
            log("❌ Session unauthorized", 'error')
            return {'status': 'error', 'log': log_messages, 'error': 'Session unauthorized'}

        # === 3. ФОНОВАЯ СИНХРОНИЗАЦИЯ (Backend Requests) ===
        # Эмуляция того, что делает TDesktop при запуске
        log("📡 [Step 3] Background Sync (Config -> State -> Diff)...")
        
        await client(GetConfigRequest())
        state = await client(GetStateRequest())
        
        # Разница обновлений (важно для статуса "Online")
        try:
            await client(GetDifferenceRequest(
                pts=state.pts, date=state.date, qts=state.qts, pts_total_limit=100
            ))
        except Exception:
            pass # Не критично
        
        # === 2. ОТРИСОВКА ИНТЕРФЕЙСА (Tray / Chat List) ===
        log("📂 [Step 2] Loading Chat List (Tray)...")
        await client(GetDialogsRequest(
            offset_date=None, offset_id=0, offset_peer=InputPeerEmpty(),
            limit=40, hash=0
        ))
        
        # Имитация: Пользователь смотрит на список чатов, проверяет, нет ли новых
        log("👀 User is scanning chat list...")
        await human_delay('scan') # 3-5 сек

        # === 4. ПЕРЕХОД В ПОИСК ===
        log("🔍 [Step 4] Clicking Search bar...")
        await human_delay('click')

        # === 5. НАБОР "SpamBot" ===
        target_username = "SpamBot"
        log(f"⌨️ [Step 5] Typing '@{target_username}'...")
        
        # Эмуляция набора: TDesktop резолвит юзернейм после паузы в вводе
        await human_delay('type') 
        
        try:
            # Запрос к серверу: "Кто такой spambot?"
            resolve_result = await client(ResolveUsernameRequest(target_username))
            spambot_peer = resolve_result.peers[0]
            spambot_entity = resolve_result.users[0]
        except Exception as e:
            log(f"❌ Could not resolve SpamBot: {e}", 'error')
            return {'status': 'error', 'log': log_messages, 'error': f"Could not resolve SpamBot: {str(e)}"}

        # === 6. ОТКРЫТИЕ ЧАТА ===
        log("🖱️ [Step 6] Found bot. Opening chat...")
        await human_delay('click')
        
        # Если бот был в блоке - разблокируем (TDesktop показывает кнопку Unblock)
        try:
            await client(UnblockRequest(spambot_entity))
        except:
            pass

        # === 7. ВЗАИМОДЕЙСТВИЕ (Start) ===
        log("💬 [Step 7] Sending /start command...")
        
        # Имитация "печатает..." (SetTyping)
        await client(SetTypingRequest(spambot_peer, action=SendMessageTypingAction()))
        await asyncio.sleep(random.uniform(0.5, 1.5)) # Время на набор "/start"
        
        # Отправка
        await client.send_message(spambot_entity, '/start')
        
        # Ожидание ответа (Глаза пользователя смотрят в экран)
        log("⏳ Waiting for bot reply...")
        response = None
        for _ in range(10): # Ждем до 10 сек
            await asyncio.sleep(1)
            history = await client.get_messages(spambot_entity, limit=1)
            if history and not history[0].out: # Если последнее сообщение НЕ наше
                response = history[0]
                break
        
        if response:
            preview = response.text[:50].replace('\n', ' ')
            log(f"🤖 [Result] Bot Replied: {preview}...")
            
            # === ЧТЕНИЕ ОТВЕТА ===
            await human_delay('read') # Читаем текст
            
            # Помечаем прочитанным (Синие галочки)
            await client(ReadHistoryRequest(peer=spambot_entity, max_id=response.id))
            
            # Логика определения бана
            clean_markers = ["Good news", "Ваш аккаунт свободен", "no limits", "хорошие новости"]
            if any(m.lower() in response.text.lower() for m in clean_markers):
                log("✅ ACCOUNT IS GREEN (CLEAN)")
                result_status = "clean"
            else:
                log("❄️ ACCOUNT IS FROZEN/RESTRICTED")
                result_status = "restricted"
        else:
            log("⚠️ Bot silent.")
            result_status = "silent"

        # === 8. ВОЗВРАТ В МЕНЮ ===
        log("🔙 [Step 8] Closing bot chat, returning to main list...")
        await human_delay('click')
        
        # Технически это просто прекращение отправки ReadHistory в этот чат
        # и отсутствие SetTyping.

        # === 9. IDLE (Не будем ждать 5 минут для UI версии, сократим) ===
        # Для UI версии ограничим ожидание, иначе пользователь устанет ждать ответа AJAX
        idle_duration = random.randint(3, 8) 
        log(f"💤 [Step 9] Short Idle ({idle_duration}s)...")
        await asyncio.sleep(idle_duration)
            
        log("⏰ Idle finished.")

        # === 10. ВЫХОД (Компьютер спит) ===
        log("💻 [Step 10] Closing Telegram (Disconnect)...")
        return {'status': result_status, 'log': log_messages}

    except Exception as e:
        log(f"❌ Error in human flow: {e}", 'error')
        return {'status': 'error', 'log': log_messages, 'error': str(e)}
    finally:
        if client and client.is_connected():
            await client.disconnect()
