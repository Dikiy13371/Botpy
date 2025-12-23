"""Отслеживание истории инцидентов."""

import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Optional
from utils.time_utils import get_msk_time, format_duration

logger = logging.getLogger(__name__)


class IncidentTracker:
    """Класс для отслеживания истории инцидентов."""
    
    def __init__(self, incidents_file: str = 'data/incidents.json'):
        """
        Инициализирует трекер инцидентов.
        
        Args:
            incidents_file: Путь к файлу с инцидентами
        """
        self.incidents_file = incidents_file
        self.incidents: List[Dict] = []
        self.current_incident: Optional[Dict] = None
        
        # Создаем директорию если нужно
        incidents_dir = os.path.dirname(self.incidents_file)
        if incidents_dir and not os.path.exists(incidents_dir):
            os.makedirs(incidents_dir, exist_ok=True)
        
        self.load_incidents()
    
    def load_incidents(self) -> None:
        """Загружает историю инцидентов из файла."""
        if os.path.exists(self.incidents_file):
            try:
                with open(self.incidents_file, 'r', encoding='utf-8') as f:
                    self.incidents = json.load(f)
                logger.info(f"Загружено {len(self.incidents)} инцидентов из истории")
            except Exception as e:
                logger.error(f"Ошибка загрузки инцидентов: {e}")
                self.incidents = []
        else:
            self.incidents = []
    
    def save_incidents(self) -> None:
        """Сохраняет историю инцидентов в файл."""
        try:
            with open(self.incidents_file, 'w', encoding='utf-8') as f:
                json.dump(self.incidents, f, ensure_ascii=False, indent=2)
            logger.debug("Инциденты сохранены")
        except Exception as e:
            logger.error(f"Ошибка сохранения инцидентов: {e}")
    
    def start_incident(self, description: str = '', region: str = '') -> None:
        """
        Начинает новый инцидент.
        
        Args:
            description: Описание проблемы
            region: Регион где произошел инцидент
        """
        if self.current_incident is None:
            self.current_incident = {
                'start_time': get_msk_time().isoformat(),
                'end_time': None,
                'duration': None,
                'description': description,
                'region': region,
                'status': 'active'
            }
            logger.info("Начат новый инцидент")
    
    def end_incident(self) -> Optional[Dict]:
        """
        Завершает текущий инцидент.
        
        Returns:
            Optional[Dict]: Завершенный инцидент или None
        """
        if self.current_incident:
            end_time = get_msk_time()
            start_time = datetime.fromisoformat(self.current_incident['start_time'])
            duration = format_duration(start_time)
            
            self.current_incident['end_time'] = end_time.isoformat()
            self.current_incident['duration'] = duration
            self.current_incident['status'] = 'resolved'
            
            incident = self.current_incident.copy()
            self.incidents.append(incident)
            
            # Оставляем только последние 1000 инцидентов
            if len(self.incidents) > 1000:
                self.incidents = self.incidents[-1000:]
            
            self.current_incident = None
            self.save_incidents()
            
            logger.info(f"Инцидент завершен, длительность: {duration}")
            return incident
        
        return None
    
    def get_recent_incidents(self, limit: int = 10) -> List[Dict]:
        """
        Возвращает последние инциденты.
        
        Args:
            limit: Количество инцидентов для возврата
            
        Returns:
            List[Dict]: Список последних инцидентов
        """
        return self.incidents[-limit:] if len(self.incidents) > limit else self.incidents
    
    def get_active_incident(self) -> Optional[Dict]:
        """
        Возвращает текущий активный инцидент.
        
        Returns:
            Optional[Dict]: Активный инцидент или None
        """
        return self.current_incident
    
    def get_incidents_count(self) -> int:
        """
        Возвращает общее количество инцидентов.
        
        Returns:
            int: Количество инцидентов
        """
        return len(self.incidents)
    
    def export_to_csv_format(self) -> str:
        """
        Экспортирует инциденты в CSV формат.
        
        Returns:
            str: CSV строка с инцидентами
        """
        csv_lines = ['Дата,Время начала,Время конца,Длительность,Регион,Описание']
        
        for incident in self.incidents:
            start_dt = datetime.fromisoformat(incident['start_time'])
            start_date = start_dt.strftime('%Y-%m-%d')
            start_time = start_dt.strftime('%H:%M:%S')
            
            if incident.get('end_time'):
                end_dt = datetime.fromisoformat(incident['end_time'])
                end_time = end_dt.strftime('%H:%M:%S')
            else:
                end_time = 'В процессе'
            
            duration = incident.get('duration', 'N/A')
            region = incident.get('region', 'N/A')
            description = incident.get('description', '').replace(',', ';').replace('\n', ' ')
            
            csv_lines.append(
                f"{start_date},{start_time},{end_time},{duration},{region},\"{description}\""
            )
        
        return '\n'.join(csv_lines)

