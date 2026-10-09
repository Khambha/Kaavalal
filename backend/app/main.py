from fastapi import FastAPI

from app.core.database import Base, engine
from app.models import (
    Location,
    WeatherData,
    RainfallData,
    HazardData,
    RiskData,
)
from app.routers.locations import router as locations_router
from app.routers.analytics import router as analytics_router
from app.routers.weather import router as weather_router
from app.routers.rainfall import router as rainfall_router
from app.routers.hazards import router as hazards_router
from app.routers.risks import router as risks_router
from app.routers.dashboard import router as dashboard_router
from fastapi.middleware.cors import CORSMiddleware
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations_router)
app.include_router(analytics_router)
app.include_router(weather_router)
app.include_router(rainfall_router)
app.include_router(hazards_router)
app.include_router(risks_router)
app.include_router(dashboard_router)

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