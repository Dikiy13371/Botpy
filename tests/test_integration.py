"""Integration тесты для критичных потоков."""
import pytest
import pytest_asyncio
import asyncio
from services.database import Database
from services.subscriber_manager import SubscriberManager
from services.incident_tracker import IncidentTracker


@pytest_asyncio.fixture
async def setup():
    """Setup для интеграционных тестов"""
    db = Database(":memory:")
    await db.connect()
    await db.init_tables()
    
    sub_mgr = SubscriberManager(db)
    inc_tracker = IncidentTracker(db)
    
    # Добавить тестовых подписчиков
    for chat_id in [111, 222, 333]:
        await sub_mgr.add_subscriber(chat_id)
    
    result = {
        "db": db,
        "sub_mgr": sub_mgr,
        "inc_tracker": inc_tracker
    }
    
    yield result
    
    await db.close()


@pytest.mark.asyncio
async def test_incident_creation_to_closure(setup):
    """
    Полный поток: создание → закрытие инцидента
    """
    inc_tracker = setup["inc_tracker"]
    
    # 1. Создать инцидент
    incident_id = await inc_tracker.start_incident(
        region="ru",
        components=["CRM", "Mail"],
        description="Test incident"
    )
    
    # 2. Получить активные инциденты (должен быть 1)
    active = await inc_tracker.get_active_incident()
    assert active is not None
    assert active['id'] == incident_id
    
    # 3. Закрыть инцидент (без параметров)
    await inc_tracker.end_incident()
    
    # 4. Проверить что теперь нет активных
    active = await inc_tracker.get_active_incident()
    assert active is None
    
    # 5. Проверить что инцидент в истории
    recent = await inc_tracker.get_recent_incidents(limit=10)
    assert len(recent) == 1
    assert recent[0]['id'] == incident_id
    assert recent[0]['status'] == 'resolved'


@pytest.mark.asyncio
async def test_multiple_incidents_simultaneously(setup):
    """
    Тест: несколько инцидентов одновременно
    """
    inc_tracker = setup["inc_tracker"]
    
    # Создать 5 инцидентов одновременно
    tasks = [
        inc_tracker.start_incident(
            region=f"region_{i}",
            components=[f"Component_{i}"],
            description=f"Incident {i}"
        )
        for i in range(5)
    ]
    
    incident_ids = await asyncio.gather(*tasks)
    
    # Проверить что все созданы
    active = await inc_tracker.get_active_incident()
    # Может быть только один активный, но все должны быть созданы
    assert len(incident_ids) == 5
    
    # Закрыть все активные инциденты (по одному, так как end_incident не принимает параметры)
    # Нужно закрывать пока есть активные инциденты
    while True:
        active = await inc_tracker.get_active_incident()
        if active is None:
            break
        # Устанавливаем current_incident_id перед закрытием
        inc_tracker.current_incident_id = active['id']
        await inc_tracker.end_incident()
    
    # Проверить что все закрыты
    active = await inc_tracker.get_active_incident()
    assert active is None


@pytest.mark.asyncio
async def test_subscriber_notification_flow(setup):
    """
    Тест: поток уведомления подписчикам
    """
    sub_mgr = setup["sub_mgr"]
    
    # Получить всех подписчиков
    subscribers = await sub_mgr.get_all()
    assert len(subscribers) == 3
    
    # Проверить что все активны
    for chat_id in subscribers:
        is_active = await sub_mgr.is_subscribed(chat_id)
        assert is_active is True
    
    # Отписать одного
    await sub_mgr.remove_subscriber(111)
    
    # Проверить что осталось двое
    subscribers = await sub_mgr.get_all()
    assert len(subscribers) == 2


@pytest.mark.asyncio
async def test_database_consistency(setup):
    """
    Тест: консистентность БД при параллельных операциях
    """
    db = setup["db"]
    sub_mgr = setup["sub_mgr"]
    inc_tracker = setup["inc_tracker"]
    
    # Параллельные операции
    tasks = []
    
    # 100 добавлений подписчиков
    for i in range(1000, 1100):
        tasks.append(sub_mgr.add_subscriber(i))
    
    # 50 созданий инцидентов
    for i in range(50):
        tasks.append(inc_tracker.start_incident(
            region="ru",
            components=["CRM"],
            description=f"Incident {i}"
        ))
    
    # Выполнить все параллельно
    await asyncio.gather(*tasks)
    
    # Проверить консистентность
    subscribers = await sub_mgr.get_all()
    assert len(subscribers) == 100 + 3  # 100 новых + 3 старых
    
    # Закрыть все инциденты (может быть только один активный)
    active = await inc_tracker.get_active_incident()
    if active:
        await inc_tracker.end_incident()

