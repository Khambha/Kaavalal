import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.models.help_request import HelpRequest
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.responder_coverage import ResponderCoverage
from app.models.password_reset_token import PasswordResetToken
from app.models.alert import Alert
from app.models.resource_item import ResourceItem
from app.models.resource_transaction import ResourceTransaction
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
from app.routers.admin import router as admin_router
from app.routers.admin_auth import router as admin_auth_router
from app.routers.alerts import router as alerts_router
from app.routers.responder_resources import router as responder_resources_router


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)


# Allow requests from the local React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(filter(None, [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        os.getenv("ADMIN_APP_ORIGIN"),
    ])),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create database tables
Base.metadata.create_all(bind=engine)

# Keep existing local installs working when district-wise inventory is added.
resource_columns = {column["name"] for column in inspect(engine).get_columns("resource_items")}
if "district" not in resource_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN district VARCHAR(100) NULL"))
resource_indexes = {index["name"] for index in inspect(engine).get_indexes("resource_items")}
if "ix_resource_items_district" not in resource_indexes:
    with engine.begin() as connection:
        connection.execute(text("CREATE INDEX ix_resource_items_district ON resource_items (district)"))


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
app.include_router(admin_router)
app.include_router(admin_auth_router)
app.include_router(alerts_router)
app.include_router(responder_resources_router)

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
