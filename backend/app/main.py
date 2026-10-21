from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.models.help_request import HelpRequest
from app.routers.help_requests import router as help_requests_router

from app.core.database import Base, engine

from app.models import (
    Location,
    WeatherData,
    RainfallData,
    HazardData,
    RiskData,
)

# Import authentication models so SQLAlchemy registers them
from app.models.user import User

# Existing routers
from app.routers.locations import router as locations_router
from app.routers.analytics import router as analytics_router
from app.routers.weather import router as weather_router
from app.routers.rainfall import router as rainfall_router
from app.routers.hazards import router as hazards_router
from app.routers.risks import router as risks_router
from app.routers.dashboard import router as dashboard_router

# Authentication router
from app.routers.auth import router as auth_router


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)


# Allow requests from the local React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create database tables
Base.metadata.create_all(bind=engine)


# Register existing routers
app.include_router(locations_router)
app.include_router(analytics_router)
app.include_router(weather_router)
app.include_router(rainfall_router)
app.include_router(hazards_router)
app.include_router(risks_router)
app.include_router(dashboard_router)
app.include_router(help_requests_router)

# Register authentication routes
app.include_router(auth_router)

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
