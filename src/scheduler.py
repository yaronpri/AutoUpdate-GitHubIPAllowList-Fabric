import os
import time
import schedule
import logging
import sys


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout,
    force=True  # This ensures we override any existing configuration
)
from main import main as run_main

logger = logging.getLogger(__name__)

def job():
    logger.info("Running scheduled job...")
    run_main()

def run_scheduler():
    interval = int(os.getenv("RUN_INTERVAL_MINUTES", "60"))
    run_once = os.getenv("RUN_ONCE", "false").lower() == "true"

    if run_once:
        job()
        return

    schedule.every(interval).minutes.do(job)
    logger.info(f"Scheduler started, running every {interval} minutes.")
    job()  # Run once at startup

    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    run_scheduler()