import asyncio

from app.scheduler.runner import run_once


if __name__ == "__main__":
    asyncio.run(run_once())
