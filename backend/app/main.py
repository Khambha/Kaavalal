from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from app.models.help_request import HelpRequest
from app.models.help_request_message import HelpRequestMessage  # noqa: F401
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.responder_coverage import ResponderCoverage
from app.models.password_reset_token import PasswordResetToken
from app.models.alert import Alert
from app.models.resource_item import ResourceItem
from app.models.resource_request import ResourceRequest
from app.models.resource_request_batch import ResourceRequestBatch  # noqa: F401
from app.models.resource_asset import ResourceAsset
from app.models.resource_asset_assignment import ResourceAssetAssignment
from app.models.resource_transaction import ResourceTransaction
from app.models.shelter import Shelter, ShelterRequest, RequestStatusEvent
from app.routers.help_requests import router as help_requests_router

from app.core.database import Base, engine
from app.core.config import settings

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
from app.routers.hazard_data import router as hazard_data_router

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
from app.chatbot.router import router as chatbot_router
from app.core.rate_limit import limiter


app = FastAPI(
    title="Kaavalal API",
    description="Kerala Disaster Management and Resource Allocation Platform",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Create database tables
Base.metadata.create_all(bind=engine)

# Add alert metadata to databases created before incident verification was added.
alert_columns = {column["name"] for column in inspect(engine).get_columns("alerts")}
with engine.begin() as connection:
    if "alert_type" not in alert_columns:
        connection.execute(text("ALTER TABLE alerts ADD COLUMN alert_type VARCHAR(30) NOT NULL DEFAULT 'warning'"))
    if "disaster_type" not in alert_columns:
        connection.execute(text("ALTER TABLE alerts ADD COLUMN disaster_type VARCHAR(60) NOT NULL DEFAULT 'General'"))

# Add responder availability to existing local user tables.
user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
if "is_available" not in user_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN is_available BOOLEAN NOT NULL DEFAULT 0"))

# Keep existing local installs working when district-wise inventory is added.
resource_columns = {column["name"] for column in inspect(engine).get_columns("resource_items")}
if "district" not in resource_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN district VARCHAR(100) NULL"))
resource_columns = {column["name"] for column in inspect(engine).get_columns("resource_items")}
with engine.begin() as connection:
    if "quantity_total" not in resource_columns:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN quantity_total INTEGER NOT NULL DEFAULT 0"))
        connection.execute(text("""UPDATE resource_items
            SET quantity_total = quantity_available + COALESCE((
                SELECT SUM(quantity) FROM resource_transactions
                WHERE resource_transactions.resource_id = resource_items.id
            ), 0)"""))
    if "is_returnable" not in resource_columns:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN is_returnable BOOLEAN NOT NULL DEFAULT FALSE"))
    if "quantity_quarantined" not in resource_columns:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN quantity_quarantined INTEGER NOT NULL DEFAULT 0"))
    if "inventory_mode" not in resource_columns:
        connection.execute(text("ALTER TABLE resource_items ADD COLUMN inventory_mode VARCHAR(20) NOT NULL DEFAULT 'Bulk'"))
resource_request_columns = {column["name"] for column in inspect(engine).get_columns("resource_requests")}
with engine.begin() as connection:
    if "transaction_id" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN transaction_id INTEGER NULL"))
    if "quantity_quarantined" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN quantity_quarantined INTEGER NOT NULL DEFAULT 0"))
    if "priority" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN priority VARCHAR(20) NOT NULL DEFAULT 'Standard'"))
    if "rejection_reason" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN rejection_reason TEXT NULL"))
    if "inventory_mode" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN inventory_mode VARCHAR(20) NOT NULL DEFAULT 'Bulk'"))
    if "category" not in resource_request_columns:
        connection.execute(text("ALTER TABLE resource_requests ADD COLUMN category VARCHAR(60) NULL"))
if next((column for column in inspect(engine).get_columns("resource_requests") if column["name"] == "resource_id"), {}).get("nullable", True) is False:
    with engine.begin() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("ALTER TABLE resource_requests MODIFY resource_id INTEGER NULL"))
        elif engine.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE resource_requests ALTER COLUMN resource_id DROP NOT NULL"))
        else:
            raise RuntimeError("Resource requests require nullable resource IDs for custom item requests; migrate this SQLite database to a supported SQL database first.")
resource_request_indexes = {index["name"] for index in inspect(engine).get_indexes("resource_requests")}
if "ix_resource_requests_transaction_id" not in resource_request_indexes:
    with engine.begin() as connection:
        connection.execute(text("CREATE INDEX ix_resource_requests_transaction_id ON resource_requests (transaction_id)"))
batch_columns = {column["name"]: column for column in inspect(engine).get_columns("resource_request_batches")}
with engine.begin() as connection:
    if "triage_started_at" not in batch_columns:
        connection.execute(text("ALTER TABLE resource_request_batches ADD COLUMN triage_started_at DATETIME NULL"))
tx_id_column = batch_columns.get("tx_id")
if tx_id_column and getattr(tx_id_column["type"], "length", None) != 60:
    with engine.begin() as connection:
        if engine.dialect.name == "mysql":
            connection.execute(text("ALTER TABLE resource_request_batches MODIFY tx_id VARCHAR(60) NOT NULL"))
        elif engine.dialect.name == "postgresql":
            connection.execute(text("ALTER TABLE resource_request_batches ALTER COLUMN tx_id TYPE VARCHAR(60)"))
        else:
            raise RuntimeError("Resource transaction IDs require a database migration to VARCHAR(60).")
transaction_columns = {column["name"] for column in inspect(engine).get_columns("resource_transactions")}
if "transaction_type" not in transaction_columns:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE resource_transactions ADD COLUMN transaction_type VARCHAR(20) NOT NULL DEFAULT 'Issued'"))
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
    if "review_status" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN review_status VARCHAR(20) NOT NULL DEFAULT 'Pending'"))
    if "review_message" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN review_message TEXT NULL"))
    if "reviewed_by_admin_id" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN reviewed_by_admin_id INTEGER NULL"))
    if "reviewed_at" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN reviewed_at DATETIME NULL"))
    if "triage_note" not in help_request_columns:
        connection.execute(text("ALTER TABLE help_requests ADD COLUMN triage_note TEXT NULL"))
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
    if "citizen_location" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN citizen_location VARCHAR(500) NULL"))
    if "latitude" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN latitude FLOAT NULL"))
    if "longitude" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN longitude FLOAT NULL"))
    if "reason" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN reason TEXT NULL"))
    if "id_photo_path" not in shelter_request_columns:
        connection.execute(text("ALTER TABLE shelter_requests ADD COLUMN id_photo_path VARCHAR(255) NULL"))
shelter_request_indexes = inspect(engine).get_indexes("shelter_requests")
has_unique_shelter_request_id = any(
    index.get("unique") and "client_request_id" in index.get("column_names", [])
    for index in shelter_request_indexes
)
if not has_unique_shelter_request_id:
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX uq_shelter_requests_client_request_id ON shelter_requests (client_request_id)"))

# Preserve source provenance and the admin review state for imported shelter candidates.
shelter_columns = {column["name"] for column in inspect(engine).get_columns("shelters")}
with engine.begin() as connection:
    if "source_key" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN source_key VARCHAR(120) NULL"))
    if "source_name" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN source_name VARCHAR(100) NULL"))
    if "source_row" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN source_row INTEGER NULL"))
    if "needs_review" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT 0"))
    if "lac_assignment_method" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN lac_assignment_method VARCHAR(40) NULL"))
    if "lac_distance_km" not in shelter_columns:
        connection.execute(text("ALTER TABLE shelters ADD COLUMN lac_distance_km FLOAT NULL"))
shelter_indexes = inspect(engine).get_indexes("shelters")
has_unique_shelter_source_key = any(
    index.get("unique") and "source_key" in index.get("column_names", [])
    for index in shelter_indexes
)
if not has_unique_shelter_source_key:
    with engine.begin() as connection:
        connection.execute(text("CREATE UNIQUE INDEX uq_shelters_source_key ON shelters (source_key)"))


# Register existing routers
app.include_router(locations_router)
app.include_router(analytics_router)
app.include_router(weather_router)
app.include_router(rainfall_router)
app.include_router(hazards_router)
app.include_router(risks_router)
app.include_router(dashboard_router)
app.include_router(hazard_data_router)
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
