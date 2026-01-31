"""
LLM Client - обертка над DeepSeek/OpenAI API
"""
import os
import json
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Клиент для работы с LLM API (DeepSeek, OpenAI)
    """
    
    # API endpoints
    PROVIDERS = {
        'deepseek': {
            'base_url': 'https://api.deepseek.com/v1',
            'default_model': 'deepseek-chat'
        },
        'openai': {
            'base_url': 'https://api.openai.com/v1',
            'default_model': 'gpt-4o-mini'
        }
    }
    
    def __init__(self, provider: str = None, api_key: str = None, model: str = None):
        """
        Инициализация клиента
        
        Args:
            provider: 'deepseek' или 'openai' (из .env AI_PROVIDER)
            api_key: API ключ (из .env AI_API_KEY)
            model: Модель (из .env AI_MODEL)
        """
        self.provider = provider or os.getenv('AI_PROVIDER', 'deepseek')
        self.api_key = api_key or os.getenv('AI_API_KEY')
        
        if not self.api_key:
            raise ValueError("AI_API_KEY not set in environment")
        
        provider_config = self.PROVIDERS.get(self.provider)
        if not provider_config:
            raise ValueError(f"Unknown provider: {self.provider}. Use 'deepseek' or 'openai'")
        
        self.base_url = provider_config['base_url']
        self.model = model or os.getenv('AI_MODEL', provider_config['default_model'])
        self.timeout = int(os.getenv('AI_TIMEOUT', 30))
        
        logger.info(f"🤖 LLMClient initialized: {self.provider}/{self.model}")
    
    def ask(self, system_prompt: str, user_prompt: str = None, temperature: float = 0.7) -> str:
        """
        Отправляет запрос к LLM и возвращает текстовый ответ
        
        Args:
            system_prompt: Системный промпт (роль, контекст, инструкции)
            user_prompt: Пользовательский промпт (опционально)
            temperature: Температура (0.0-1.0)
            
        Returns:
            str: Текстовый ответ от модели
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        
        return self._send_request(messages, temperature=temperature)
    
    def ask_json(self, system_prompt: str, user_prompt: str = None, temperature: float = 0.3) -> Dict[str, Any]:
        """
        Отправляет запрос к LLM и возвращает JSON ответ
        
        Args:
            system_prompt: Системный промпт (должен требовать JSON)
            user_prompt: Пользовательский промпт (опционально)
            temperature: Температура (ниже для консистентности)
            
        Returns:
            dict: Распарсенный JSON ответ
        """
        messages = [{"role": "system", "content": system_prompt}]
        
        if user_prompt:
            messages.append({"role": "user", "content": user_prompt})
        
        response_text = self._send_request(
            messages, 
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        # Парсим JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"❌ Failed to parse JSON response: {e}")
            logger.error(f"Raw response: {response_text[:500]}")
            raise ValueError(f"LLM returned invalid JSON: {e}")
    
    def _send_request(
        self, 
        messages: list, 
        temperature: float = 0.7,
        response_format: dict = None
    ) -> str:
        """
        Отправляет запрос к API
        """
        url = f"{self.base_url}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 4000
        }
        
        # Добавляем response_format если указан
        if response_format:
            payload["response_format"] = response_format
        
        try:
            logger.debug(f"📤 Sending request to {self.provider}...")
            
            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            
            response.raise_for_status()
            
            data = response.json()
            
            # Логируем использование токенов
            usage = data.get('usage', {})
            logger.info(f"📊 Tokens used: {usage.get('total_tokens', '?')} "
                       f"(prompt: {usage.get('prompt_tokens', '?')}, "
                       f"completion: {usage.get('completion_tokens', '?')})")
            
            # Извлекаем ответ
            content = data['choices'][0]['message']['content']
            
            return content.strip()
            
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ API timeout after {self.timeout}s")
            raise TimeoutError(f"LLM API timeout after {self.timeout}s")
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"❌ HTTP error: {e}")
            if hasattr(e, 'response') and e.response:
                logger.error(f"Response: {e.response.text[:500]}")
            raise
            
        except Exception as e:
            logger.error(f"❌ API error: {e}")
            raise


# Singleton instance для удобства
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """
    Возвращает singleton instance LLMClient
    """
    global _client
    
    if _client is None:
        _client = LLMClient()
    
    return _client
