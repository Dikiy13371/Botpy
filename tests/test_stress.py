"""Stress тесты для проверки производительности."""
import pytest
import pytest_asyncio
import asyncio
import time
from services.database import Database
from services.subscriber_manager import SubscriberManager
from services.incident_tracker import IncidentTracker


@pytest_asyncio.fixture
async def stress_setup():
    """Setup для стресс-тестов"""
    db = Database(":memory:")
    await db.connect()
    await db.init_tables()
    
    sub_mgr = SubscriberManager(db)
    inc_tracker = IncidentTracker(db)
    
    result = {
        "db": db,
        "sub_mgr": sub_mgr,
        "inc_tracker": inc_tracker
    }
    
    yield result
    
    await db.close()


@pytest.mark.asyncio
@pytest.mark.slow
async def test_stress_many_subscribers(stress_setup):
    """
    Стресс-тест: 1,000 подписчиков
    Проверяет производительность при большом количестве пользователей
    """
    sub_mgr = stress_setup["sub_mgr"]
    
    print("\n⏱️ Добавляю 1,000 подписчиков...")
    
    start = time.time()
    
    # Добавить 1,000 подписчиков
    tasks = [sub_mgr.add_subscriber(10000 + i) for i in range(1000)]
    await asyncio.gather(*tasks)
    
    elapsed = time.time() - start
    per_sec = 1000 / elapsed
    
    print(f"✅ Добавлено за {elapsed:.2f}s ({per_sec:.0f} подписчиков/сек)")
    
    # Проверить что все добавлены
    count = await sub_mgr.get_count()
    assert count == 1000


@pytest.mark.asyncio
@pytest.mark.slow
async def test_stress_rapid_incidents(stress_setup):
    """
    Стресс-тест: 100 инцидентов подряд
    Проверяет производительность при частых инцидентах
    """
    inc_tracker = stress_setup["inc_tracker"]
    
    print("\n⏱️ Создаю 100 инцидентов...")
    
    start = time.time()
    
    # Создать 100 инцидентов
    for i in range(100):
        await inc_tracker.start_incident(
            region="ru",
            components=["CRM"],
            description=f"Incident {i}"
        )
        await inc_tracker.end_incident()
    
    create_elapsed = time.time() - start
    
    print(f"✅ Создано и закрыто за {create_elapsed:.2f}s")


@pytest.mark.asyncio
@pytest.mark.slow
async def test_stress_concurrent_operations(stress_setup):
    """
    Стресс-тест: смешанные операции одновременно
    """
    sub_mgr = stress_setup["sub_mgr"]
    inc_tracker = stress_setup["inc_tracker"]
    
    print("\n⏱️ Выполняю смешанные операции...")
    
    start = time.time()
    
    tasks = []
    
    # 100 добавлений подписчиков
    for i in range(20000, 20100):
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
    
    elapsed = time.time() - start
    total_ops = len(tasks)
    per_sec = total_ops / elapsed
    
    print(f"✅ {total_ops} операций за {elapsed:.2f}s ({per_sec:.0f} оп/сек)")

