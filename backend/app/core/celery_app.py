from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "oil_expert",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Moscow",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    broker_pool_limit=10,
)

celery_app.conf.beat_schedule = {
    "check-subscriptions-daily": {
        "task": "app.tasks.scheduled_tasks.check_subscriptions_task",
        "schedule": 86400.0,  # каждый день
        "args": (),
    },
    "suspend-expired-hourly": {
        "task": "app.tasks.scheduled_tasks.suspend_expired_task",
        "schedule": 3600.0,  # каждый час
        "args": (),
    },
    "predictive-analytics-daily": {
        "task": "app.tasks.scheduled_tasks.predictive_analytics_task",
        "schedule": 86400.0,  # каждый день
        "args": (),
    },
}

celery_app.autodiscover_tasks(["app.tasks"], force=True)
celery_app.conf.include = ["app.tasks.etl_tasks", "app.tasks.scheduled_tasks"]
