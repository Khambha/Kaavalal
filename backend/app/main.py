from fastapi import FastAPI

from app.core.database import Base, engine
from app.models import Location
from app.routers.locations import router as locations_router
from app.routers.analytics import router as analytics_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)


app.include_router(locations_router)
app.include_router(analytics_router)


@app.get("/")
def root():
    return {
        "message": "Kaavalal API is running",
        "status": "ok",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
    }