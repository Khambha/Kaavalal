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
from app.models.shelter import Shelter, ShelterRequest, RequestStatusEvent
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
from app.routers.shelters import router as shelters_router, admin_router as admin_shelters_router
from app.routers.citizen import router as citizen_router

# Thunai chatbot tables and routes. Import models before create_all so the shared
# Kaavalal database registers the chatbot's own tables alongside the app models.
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import app.chatbot.models  # noqa: F401
import app.chatbot.ref_models  # noqa: F401
from app.chatbot.router import router as chatbot_router, limiter as chatbot_limiter


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)

app.state.limiter = chatbot_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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

# Add SOS-to-shelter linkage to existing local databases.
help_request_columns = {column["name"] for column in inspect(engine).get_columns("help_requests")}
if "shelter_id" not in help_request_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN shelter_id INTEGER NULL"))
help_request_columns = {column["name"] for column in inspect(engine).get_columns("help_requests")}
with engine.begin() as connection:
    if "client_request_id" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN client_request_id VARCHAR(36) NULL"))
    if "eta_estimate_minutes" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN eta_estimate_minutes INTEGER NULL"))
help_request_indexes = inspect(engine).get_indexes("help_requests")
has_unique_client_request_index = any(
    index.get("unique") and "client_request_id" in index.get("column_names", [])
    for index in help_request_indexes
)
if not has_unique_client_request_index:
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX uq_help_requests_client_request_id ON help_requests (client_request_id)"))

shelter_request_columns = {column["name"] for column in inspect(engine).get_columns("shelter_requests")}
with engine.begin() as connection:
    if "client_request_id" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN client_request_id VARCHAR(36) NULL"))
    if "eta_estimate_minutes" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN eta_estimate_minutes INTEGER NULL"))
shelter_request_indexes = inspect(engine).get_indexes("shelter_requests")
has_unique_shelter_request_id = any(
    index.get("unique") and "client_request_id" in index.get("column_names", [])
    for index in shelter_request_indexes
)
if not has_unique_shelter_request_id:
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX uq_shelter_requests_client_request_id ON shelter_requests (client_request_id)"))


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
app.include_router(shelters_router)
app.include_router(admin_shelters_router)
app.include_router(citizen_router)
app.include_router(chatbot_router, prefix="/api")

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
