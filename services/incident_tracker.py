"""Отслеживание истории инцидентов с использованием SQLite."""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from utils.time_utils import get_msk_time, format_duration
from services.database import Database

logger = logging.getLogger(__name__)


class IncidentTracker:
    """Класс для отслеживания истории инцидентов с использованием SQLite."""
    
    def __init__(self, database: Database):
        """
        Инициализирует трекер инцидентов.
        
        Args:
            database: Экземпляр базы данных
        """
        self.db = database
        self.current_incident_id: Optional[int] = None
    
    async def start_incident(
        self, 
        description: str = '', 
        region: str = '',
        components: Optional[List[str]] = None
    ) -> Optional[int]:
        """
        Начинает новый инцидент.
        
        Args:
            description: Описание проблемы
            region: Регион где произошел инцидент
            components: Список затронутых компонентов
            
        Returns:
            Optional[int]: ID созданного инцидента
        """
        if self.current_incident_id is None:
            try:
                components_str = ','.join(components) if components else None
                start_time = get_msk_time().isoformat()
                
                cursor = await self.db.execute(
                    '''INSERT INTO incidents 
                       (start_time, description, region, status, components) 
                       VALUES (?, ?, ?, 'active', ?)''',
                    (start_time, description, region, components_str)
                )
                await self.db.commit()
                
                self.current_incident_id = cursor.lastrowid
                logger.info(f"Начат новый инцидент (ID: {self.current_incident_id})")
                return self.current_incident_id
            except Exception as e:
                logger.error(f"Ошибка создания инцидента: {e}")
                return None
        return self.current_incident_id
    
    async def end_incident(self) -> Optional[Dict]:
        """
        Завершает текущий инцидент.
        
        Returns:
            Optional[Dict]: Завершенный инцидент или None
        """
        if self.current_incident_id:
            try:
                # Получаем данные инцидента
                incident = await self.db.fetchone(
                    'SELECT * FROM incidents WHERE id = ?',
                    (self.current_incident_id,)
                )
                
                if incident:
                    end_time = get_msk_time()
                    start_time = datetime.fromisoformat(incident['start_time'])
                    duration = format_duration(start_time)
                    
                    # Обновляем инцидент
                    await self.db.execute(
                        '''UPDATE incidents 
                           SET end_time = ?, duration = ?, status = 'resolved' 
                           WHERE id = ?''',
                        (end_time.isoformat(), duration, self.current_incident_id)
                    )
                    await self.db.commit()
                    
                    # Получаем обновленные данные
                    updated_incident = await self.db.fetchone(
                        'SELECT * FROM incidents WHERE id = ?',
                        (self.current_incident_id,)
                    )
                    
                    self.current_incident_id = None
                    
                    if updated_incident:
                        logger.info(f"Инцидент завершен (ID: {updated_incident['id']}), длительность: {duration}")
                        return dict(updated_incident)
            except Exception as e:
                logger.error(f"Ошибка завершения инцидента: {e}")
        
        return None
    
    async def get_recent_incidents(self, limit: int = 10) -> List[Dict]:
        """
        Возвращает последние инциденты (включая активные и завершенные).
        
        Args:
            limit: Количество инцидентов для возврата
            
        Returns:
            List[Dict]: Список последних инцидентов
        """
        try:
            rows = await self.db.fetchall(
                '''SELECT * FROM incidents 
                   ORDER BY start_time DESC 
                   LIMIT ?''',
                (limit,)
            )
            # Преобразуем components из строки в список для удобства
            for row in rows:
                if row.get('components') and isinstance(row['components'], str):
                    row['components'] = row['components'].split(',') if row['components'] else []
            return rows
        except Exception as e:
            logger.error(f"Ошибка получения инцидентов: {e}")
            return []
    
    async def restore_active_incident(self) -> None:
        """
        Восстанавливает активный инцидент из БД при запуске бота.
        """
        try:
            active = await self.get_active_incident()
            if active:
                self.current_incident_id = active['id']
                logger.info(f"Восстановлен активный инцидент (ID: {self.current_incident_id})")
        except Exception as e:
            logger.error(f"Ошибка восстановления активного инцидента: {e}")
    
    async def get_active_incident(self) -> Optional[Dict]:
        """
        Возвращает текущий активный инцидент.
        Проверяет БД на наличие активных инцидентов, даже если current_incident_id не установлен.
        
        Returns:
            Optional[Dict]: Активный инцидент или None
        """
        try:
            # Сначала проверяем по current_incident_id, если он установлен
            if self.current_incident_id:
                incident = await self.db.fetchone(
                    'SELECT * FROM incidents WHERE id = ? AND status = ?',
                    (self.current_incident_id, 'active')
                )
                if incident:
                    return dict(incident)
            
            # Если current_incident_id не установлен или инцидент не найден,
            # ищем активный инцидент в БД
            incident = await self.db.fetchone(
                'SELECT * FROM incidents WHERE status = ? ORDER BY start_time DESC LIMIT 1',
                ('active',)
            )
            
            if incident:
                # Восстанавливаем current_incident_id
                self.current_incident_id = incident['id']
                return dict(incident)
            
            return None
        except Exception as e:
            logger.error(f"Ошибка получения активного инцидента: {e}")
            return None
    
    async def get_incidents_count(self) -> int:
        """
        Возвращает общее количество инцидентов.
        
        Returns:
            int: Количество инцидентов
        """
        try:
            result = await self.db.fetchone('SELECT COUNT(*) as count FROM incidents')
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"Ошибка получения количества инцидентов: {e}")
            return 0
    
    async def get_history(self, limit: int = 5) -> List[Dict]:
        """
        Возвращает историю инцидентов для команды /history.
        
        Args:
            limit: Количество инцидентов для возврата
            
        Returns:
            List[Dict]: Список инцидентов с форматированными данными
        """
        try:
            rows = await self.db.fetchall(
                '''SELECT * FROM incidents 
                   WHERE status = 'resolved'
                   ORDER BY start_time DESC 
                   LIMIT ?''',
                (limit,)
            )
            return rows
        except Exception as e:
            logger.error(f"Ошибка получения истории: {e}")
            return []
    
    async def export_to_csv_format(self) -> str:
        """
        Экспортирует инциденты в CSV формат.
        
        Returns:
            str: CSV строка с инцидентами
        """
        try:
            csv_lines = ['Дата,Время начала,Время конца,Длительность,Регион,Компоненты,Описание']
            
            rows = await self.db.fetchall(
                '''SELECT * FROM incidents 
                   ORDER BY start_time DESC'''
            )
            
            for incident in rows:
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
                components = incident.get('components', 'N/A')
                description = (incident.get('description', '') or '').replace(',', ';').replace('\n', ' ')
                
                csv_lines.append(
                    f"{start_date},{start_time},{end_time},{duration},{region},{components},\"{description}\""
                )
            
            return '\n'.join(csv_lines)
        except Exception as e:
            logger.error(f"Ошибка экспорта в CSV: {e}")
            return "Дата,Время начала,Время конца,Длительность,Регион,Компоненты,Описание"
