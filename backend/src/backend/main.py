import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

from backend.routes import create_app
from backend.tasks import setup_scheduler

app = create_app()
scheduler = setup_scheduler()


@app.on_event("startup")
async def startup():
    scheduler.start()
    logging.getLogger(__name__).info("Scheduler started")


@app.on_event("shutdown")
async def shutdown():
    scheduler.shutdown()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
