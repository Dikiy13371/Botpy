"""Парсер статуса Bitrix24 с поддержкой компонентов и exponential backoff."""

import re
import logging
import random
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, Optional, List
from time import time as current_time
import asyncio

logger = logging.getLogger(__name__)


class BitrixStatusParser:
    """Класс для парсинга статуса Bitrix24 с поддержкой компонентов."""
    
    def __init__(
        self, 
        url: str, 
        timeout: int = 10, 
        retry_attempts: int = 3, 
        retry_delay: int = 5,
        cache_ttl: int = 30
    ):
        """
        Инициализирует парсер.
        
        Args:
            url: URL страницы статуса
            timeout: Таймаут запроса в секундах
            retry_attempts: Количество попыток при ошибке
            retry_delay: Начальная задержка между попытками в секундах
            cache_ttl: Время жизни кэша в секундах
        """
        self.url = url
        self.timeout_seconds = timeout
        self.retry_attempts = retry_attempts
        self.base_retry_delay = retry_delay
        self.cache_ttl = cache_ttl
        self.cache: Optional[Dict] = None
        self.cache_time: float = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Получает или создает aiohttp сессию."""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self.headers
            )
        return self.session
    
    async def close(self) -> None:
        """Закрывает aiohttp сессию."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    async def _exponential_backoff(self, attempt: int) -> float:
        """
        Вычисляет задержку с экспоненциальным увеличением.
        
        Args:
            attempt: Номер попытки (начинается с 1)
            
        Returns:
            float: Задержка в секундах
        """
        # Exponential backoff: base_delay * (2 ^ (attempt - 1))
        delay = self.base_retry_delay * (2 ** (attempt - 1))
        # Добавляем небольшую случайную задержку (jitter) для избежания thundering herd
        jitter = random.uniform(0, delay * 0.1)
        return delay + jitter
    
    async def _check_url_availability(self) -> bool:
        """
        Проверяет доступность URL перед парсингом.
        
        Returns:
            bool: True если URL доступен
        """
        try:
            session = await self._get_session()
            # Используем timeout из сессии или создаем новый для этого запроса
            quick_timeout = aiohttp.ClientTimeout(total=5)
            async with session.head(self.url, timeout=quick_timeout) as response:
                return response.status == 200
        except Exception as e:
            logger.warning(f"URL недоступен: {e}")
            return False
    
    async def _make_request(self) -> Optional[aiohttp.ClientResponse]:
        """
        Выполняет HTTP запрос с повторными попытками и exponential backoff.
        
        Returns:
            Optional[ClientResponse]: Ответ сервера или None при ошибке
        """
        session = await self._get_session()
        
        for attempt in range(1, self.retry_attempts + 1):
            try:
                # Используем timeout из сессии (уже установлен при создании)
                async with session.get(self.url, timeout=aiohttp.ClientTimeout(total=self.timeout_seconds)) as response:
                    # Проверяем статус код
                    if response.status == 502 or response.status == 503:
                        # Сервер временно недоступен, пробуем еще раз
                        if attempt < self.retry_attempts:
                            delay = await self._exponential_backoff(attempt)
                            logger.warning(
                                f"Сервер вернул {response.status} (попытка {attempt}/{self.retry_attempts}), "
                                f"повтор через {delay:.2f}с"
                            )
                            await asyncio.sleep(delay)
                            continue
                    
                    response.raise_for_status()
                    # Читаем контент и возвращаем его
                    content = await response.read()
                    # Создаем новый response-like объект для совместимости
                    class ResponseWrapper:
                        def __init__(self, content, status):
                            self.content = content
                            self.status = status
                    
                    return ResponseWrapper(content, response.status)
                    
            except aiohttp.ClientError as e:
                logger.warning(f"Ошибка запроса (попытка {attempt}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts:
                    delay = await self._exponential_backoff(attempt)
                    logger.info(f"Повтор через {delay:.2f}с")
                    await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"Неожиданная ошибка запроса: {e}")
                if attempt < self.retry_attempts:
                    delay = await self._exponential_backoff(attempt)
                    await asyncio.sleep(delay)
        
        return None
    
    def _parse_components(self, soup: BeautifulSoup, page_text: str) -> List[str]:
        """
        Парсит информацию о компонентах Bitrix24.
        
        Args:
            soup: BeautifulSoup объект
            page_text: Текст страницы
            
        Returns:
            List[str]: Список компонентов с проблемами
        """
        components = []
        
        # Ищем упоминания компонентов
        component_keywords = {
            'CRM': ['CRM', 'crm', 'клиенты', 'сделки'],
            'Почта': ['почта', 'email', 'mail', 'письма'],
            'Задачи': ['задачи', 'tasks', 'task', 'проекты'],
            'Диск': ['диск', 'disk', 'файлы', 'files'],
            'Календарь': ['календарь', 'calendar', 'события'],
            'Телефония': ['телефония', 'звонки', 'calls', 'видео']
        }
        
        page_text_lower = page_text.lower()
        
        for component, keywords in component_keywords.items():
            if any(keyword in page_text_lower for keyword in keywords):
                # Проверяем, есть ли проблемы с этим компонентом
                # Ищем контекст вокруг ключевых слов
                for keyword in keywords:
                    if keyword in page_text_lower:
                        # Ищем индикаторы проблем рядом с ключевым словом
                        idx = page_text_lower.find(keyword)
                        context = page_text[max(0, idx-50):idx+50].lower()
                        if any(word in context for word in ['сбой', 'проблем', 'ошибк', 'недоступен', 'down']):
                            if component not in components:
                                components.append(component)
                            break
        
        return components
    
    def _parse_with_backup_selectors(self, soup: BeautifulSoup, page_text: str) -> Dict:
        """
        Парсит статус с использованием backup селекторов.
        
        Args:
            soup: BeautifulSoup объект
            page_text: Текст страницы
            
        Returns:
            Dict: Информация о статусе
        """
        status_info = {
            'has_issues': False,
            'message': '',
            'timestamp': '',
            'description': '',
            'region': '',
            'components': [],
            'error': False
        }
        
        # Основной метод - проверка текста
        has_vremenniy_sboy = 'ВРЕМЕННЫЙ СБОЙ' in page_text
        has_vse_otlichno = 'ВСЕ ОТЛИЧНО РАБОТАЕТ' in page_text
        
        # Backup метод 1: поиск по классам CSS
        if not has_vremenniy_sboy:
            error_elements = soup.find_all(class_=re.compile(r'error|warning|alert|down', re.I))
            if error_elements:
                has_vremenniy_sboy = True
        
        # Backup метод 2: поиск по тексту в заголовках
        if not has_vremenniy_sboy:
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings:
                heading_text = heading.get_text().upper()
                if 'СБОЙ' in heading_text or 'ПРОБЛЕМ' in heading_text:
                    has_vremenniy_sboy = True
                    break
        
        if has_vremenniy_sboy and not has_vse_otlichno:
            status_info['has_issues'] = True
            status_info['message'] = 'Обнаружен временный сбой в работе Битрикс24'
            
            # Ищем временную метку
            timestamp_pattern = r'(\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2})'
            timestamps = re.findall(timestamp_pattern, page_text)
            if timestamps:
                status_info['timestamp'] = timestamps[0]
            
            # Ищем регион
            region_pattern = r'\.(ru|com|eu|by|kz|ua)'
            regions = re.findall(region_pattern, page_text)
            if regions:
                status_info['region'] = '.' + regions[0]
            
            # Описание проблемы
            desc_pattern = r'ВРЕМЕННЫЙ СБОЙ(.*?)(?:Пожалуйста, подождите|$)'
            desc_match = re.search(desc_pattern, page_text, re.DOTALL)
            if desc_match:
                description = desc_match.group(1).strip()
                description = re.sub(r'\s+', ' ', description)
                status_info['description'] = description
            
            # Парсим компоненты
            status_info['components'] = self._parse_components(soup, page_text)
        else:
            status_info['has_issues'] = False
            status_info['message'] = 'Все системы Битрикс24 работают нормально'
        
        return status_info
    
    async def parse_status(self) -> Dict:
        """
        Парсит страницу статуса Битрикс24 и возвращает информацию о текущем состоянии.
        Использует кэширование для уменьшения нагрузки на сервер.
        
        Returns:
            dict: Словарь с информацией о статусе:
                - has_issues (bool): Есть ли проблемы
                - message (str): Сообщение о статусе
                - timestamp (str): Временная метка
                - description (str): Описание проблемы
                - region (str): Регион
                - components (List[str]): Список затронутых компонентов
                - error (bool): Была ли ошибка при парсинге
        """
        # Проверяем кэш
        now = current_time()
        if self.cache and (now - self.cache_time) < self.cache_ttl:
            logger.debug("Используется кэшированный результат")
            return self.cache.copy()
        
        start_time = current_time()
        status_info = {
            'has_issues': False,
            'message': '',
            'timestamp': '',
            'description': '',
            'region': '',
            'components': [],
            'error': False
        }
        
        response = await self._make_request()
        if response is None:
            status_info['error'] = True
            status_info['message'] = 'Ошибка при получении данных с сервера статуса'
            return status_info
        
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            page_text = soup.get_text()
            
            # Используем парсинг с backup селекторами
            status_info = self._parse_with_backup_selectors(soup, page_text)
            
            # Сохраняем в кэш
            self.cache = status_info.copy()
            self.cache_time = current_time()
            
            parse_duration = current_time() - start_time
            logger.debug(f"Парсинг выполнен за {parse_duration:.2f}с")
            
            if status_info['has_issues']:
                logger.info(f"Обнаружен сбой в работе Bitrix24. Компоненты: {status_info.get('components', [])}")
            else:
                logger.debug("Статус Bitrix24 в норме")
            
            return status_info
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге HTML: {e}")
            status_info['error'] = True
            status_info['message'] = f'Неожиданная ошибка при парсинге: {str(e)}'
            return status_info
