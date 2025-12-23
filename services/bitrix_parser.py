"""Парсер статуса Bitrix24."""

import re
import logging
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional
from time import sleep, time as current_time

logger = logging.getLogger(__name__)


class BitrixStatusParser:
    """Класс для парсинга статуса Bitrix24."""
    
    def __init__(self, url: str, timeout: int = 10, retry_attempts: int = 3, retry_delay: int = 5, cache_ttl: int = 30):
        """
        Инициализирует парсер.
        
        Args:
            url: URL страницы статуса
            timeout: Таймаут запроса в секундах
            retry_attempts: Количество попыток при ошибке
            retry_delay: Задержка между попытками в секундах
            cache_ttl: Время жизни кэша в секундах
        """
        self.url = url
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.cache_ttl = cache_ttl
        self.cache: Optional[Dict] = None
        self.cache_time: float = 0
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _check_url_availability(self) -> bool:
        """
        Проверяет доступность URL перед парсингом.
        
        Returns:
            bool: True если URL доступен
        """
        try:
            response = requests.head(self.url, headers=self.headers, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"URL недоступен: {e}")
            return False
    
    def _make_request(self) -> Optional[requests.Response]:
        """
        Выполняет HTTP запрос с повторными попытками.
        
        Returns:
            Optional[requests.Response]: Ответ сервера или None при ошибке
        """
        # Проверяем доступность URL
        if not self._check_url_availability():
            logger.warning("URL недоступен, пропускаем проверку")
        
        for attempt in range(1, self.retry_attempts + 1):
            try:
                response = requests.get(
                    self.url,
                    headers=self.headers,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response
            except requests.exceptions.Timeout:
                logger.warning(f"Таймаут запроса (попытка {attempt}/{self.retry_attempts})")
                if attempt < self.retry_attempts:
                    sleep(self.retry_delay)
            except requests.exceptions.RequestException as e:
                logger.error(f"Ошибка запроса (попытка {attempt}/{self.retry_attempts}): {e}")
                if attempt < self.retry_attempts:
                    sleep(self.retry_delay)
        
        return None
    
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
        else:
            status_info['has_issues'] = False
            status_info['message'] = 'Все системы Битрикс24 работают нормально'
        
        return status_info
    
    def parse_status(self) -> Dict:
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
            'error': False
        }
        
        response = self._make_request()
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
                logger.info("Обнаружен сбой в работе Bitrix24")
            else:
                logger.debug("Статус Bitrix24 в норме")
            
            return status_info
            
        except Exception as e:
            logger.error(f"Ошибка при парсинге HTML: {e}")
            status_info['error'] = True
            status_info['message'] = f'Неожиданная ошибка при парсинге: {str(e)}'
            return status_info

