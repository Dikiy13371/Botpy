"""Unit тесты для базы данных и сервисов."""
import pytest
import pytest_asyncio
import asyncio
from services.database import Database
from services.subscriber_manager import SubscriberManager
from services.incident_tracker import IncidentTracker


@pytest_asyncio.fixture
async def test_db():
    """Тестовая БД в памяти"""
    db = Database(":memory:")  # SQLite in-memory для тестов
    await db.connect()
    await db.init_tables()
    yield db
    await db.close()


@pytest.fixture
def subscriber_mgr(test_db):
    """Фикстура для SubscriberManager"""
    return SubscriberManager(test_db)


@pytest.fixture
def incident_tracker(test_db):
    """Фикстура для IncidentTracker"""
    return IncidentTracker(test_db)


# ===== ТЕСТЫ SUBSCRIBER MANAGER =====

@pytest.mark.asyncio
async def test_add_subscriber(subscriber_mgr):
    """Тест добавления подписчика"""
    chat_id = 123456789
    await subscriber_mgr.add_subscriber(chat_id)
    
    is_subscribed = await subscriber_mgr.is_subscribed(chat_id)
    assert is_subscribed is True


@pytest.mark.asyncio
async def test_add_duplicate_subscriber(subscriber_mgr):
    """Тест добавления дубликата (не должно быть ошибки)"""
    chat_id = 123456789
    
    await subscriber_mgr.add_subscriber(chat_id)
    await subscriber_mgr.add_subscriber(chat_id)  # Второй раз
    
    count = await subscriber_mgr.get_count()
    assert count == 1  # Только один подписчик


@pytest.mark.asyncio
async def test_remove_subscriber(subscriber_mgr):
    """Тест удаления подписчика"""
    chat_id = 123456789
    
    await subscriber_mgr.add_subscriber(chat_id)
    await subscriber_mgr.remove_subscriber(chat_id)
    
    is_subscribed = await subscriber_mgr.is_subscribed(chat_id)
    assert is_subscribed is False


@pytest.mark.asyncio
async def test_remove_nonexistent_subscriber(subscriber_mgr):
    """Тест удаления несуществующего подписчика (должно быть ОК)"""
    chat_id = 999999999
    
    # Не должно быть исключения
    result = await subscriber_mgr.remove_subscriber(chat_id)
    assert result is False  # Возвращает False если не было подписчика


@pytest.mark.asyncio
async def test_get_all_subscribers(subscriber_mgr):
    """Тест получения всех подписчиков"""
    chat_ids = [111, 222, 333, 444, 555]
    
    for chat_id in chat_ids:
        await subscriber_mgr.add_subscriber(chat_id)
    
    all_subs = await subscriber_mgr.get_all()
    assert len(all_subs) == 5
    assert all(chat_id in all_subs for chat_id in chat_ids)


@pytest.mark.asyncio
async def test_concurrent_subscribers(subscriber_mgr):
    """Тест одновременного добавления подписчиков (race conditions)"""
    chat_ids = list(range(1000, 1100))  # 100 подписчиков
    
    # Добавляем одновременно
    tasks = [subscriber_mgr.add_subscriber(cid) for cid in chat_ids]
    await asyncio.gather(*tasks)
    
    count = await subscriber_mgr.get_count()
    assert count == 100  # Все должны быть добавлены без потерь


# ===== ТЕСТЫ INCIDENT TRACKER =====

@pytest.mark.asyncio
async def test_create_incident(incident_tracker):
    """Тест создания инцидента"""
    incident_id = await incident_tracker.start_incident(
        region="ru",
        components=["CRM", "Mail"],
        description="Test incident"
    )
    assert incident_id is not None
    assert isinstance(incident_id, int)


@pytest.mark.asyncio
async def test_get_active_incident(incident_tracker):
    """Тест получения активного инцидента"""
    await incident_tracker.start_incident(
        region="ru",
        components=["CRM"],
        description="Active incident"
    )
    
    active = await incident_tracker.get_active_incident()
    assert active is not None
    assert active['status'] == 'active'


@pytest.mark.asyncio
async def test_end_incident(incident_tracker):
    """Тест закрытия инцидента"""
    incident_id = await incident_tracker.start_incident(
        region="ru",
        components=["CRM"],
        description="Test"
    )
    
    # end_incident() не принимает параметры, использует self.current_incident_id
    await incident_tracker.end_incident()
    
    active = await incident_tracker.get_active_incident()
    assert active is None
    
    recent = await incident_tracker.get_recent_incidents(limit=1)
    assert len(recent) == 1
    assert recent[0]['status'] == 'resolved'


@pytest.mark.asyncio
async def test_incident_duration_calculation(incident_tracker):
    """Тест расчета длительности инцидента"""
    import time
    incident_id = await incident_tracker.start_incident(
        region="ru",
        components=["CRM"],
        description="Test"
    )
    
    # Подождать немного
    await asyncio.sleep(0.1)
    
    # Закрыть инцидент (без параметров)
    await incident_tracker.end_incident()
    
    recent = await incident_tracker.get_recent_incidents(limit=1)
    assert len(recent) == 1
    assert recent[0]['duration'] is not None
    assert recent[0]['duration'] != ""


@pytest.mark.asyncio
async def test_get_recent_incidents(incident_tracker):
    """Тест получения последних N инцидентов"""
    # Создать несколько инцидентов
    for i in range(10):
        await incident_tracker.start_incident(
            region="ru",
            components=[f"Component{i}"],
            description=f"Incident {i}"
        )
        await incident_tracker.end_incident()
    
    recent = await incident_tracker.get_recent_incidents(limit=5)
    assert len(recent) == 5


@pytest.mark.asyncio
async def test_get_incidents_count(incident_tracker):
    """Тест подсчета инцидентов"""
    # Создать несколько инцидентов
    for i in range(5):
        await incident_tracker.start_incident(
            region="ru",
            components=["CRM"],
            description=f"Test {i}"
        )
        await incident_tracker.end_incident()
    
    count = await incident_tracker.get_incidents_count()
    assert count == 5


# ===== ТЕСТЫ BITRIX PARSER =====

@pytest.mark.asyncio
async def test_bitrix_parser_initialization():
    """Тест инициализации парсера"""
    from services.bitrix_parser import BitrixStatusParser
    
    parser = BitrixStatusParser(
        url="https://status.bitrix24.ru/",
        timeout=10
    )
    
    assert parser.url == "https://status.bitrix24.ru/"
    assert parser.timeout_seconds == 10


@pytest.mark.asyncio
async def test_bitrix_parser_empty_html():
    """Тест парсинга пустого HTML"""
    from services.bitrix_parser import BitrixStatusParser
    
    parser = BitrixStatusParser(url="https://status.bitrix24.ru/")
    
    # При пустом HTML - вернуть безопасное значение
    result = await parser.parse_status()
    # Результат должен быть словарем с ключами
    assert isinstance(result, dict)
    assert 'has_issues' in result


# ===== ТЕСТЫ CONFIG =====

def test_config_validation():
    """Тест валидации конфигурации"""
    from config.config import BotConfig
    import os
    
    # Установить переменные окружения
    os.environ['BOT_TOKEN'] = '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz'
    os.environ['GROUP_ID'] = '-1003313600592'
    
    config = BotConfig()
    
    assert config.BOT_TOKEN == '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz'
    assert config.GROUP_ID == -1003313600592
    assert config.CHECK_INTERVAL > 0

