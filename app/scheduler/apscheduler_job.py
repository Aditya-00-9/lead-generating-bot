from apscheduler.schedulers.blocking import BlockingScheduler

from app.config.settings import get_settings
from app.scheduler.runner import run_once

settings = get_settings()
scheduler = BlockingScheduler(timezone=settings.scheduler_timezone)
scheduler.add_job(
    lambda: __import__("asyncio").run(run_once()),
    trigger="cron",
    hour=settings.scheduler_hour,
    minute=settings.scheduler_minute,
)

if __name__ == "__main__":
    scheduler.start()
