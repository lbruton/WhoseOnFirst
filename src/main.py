"""
WhoseOnFirst API - Main FastAPI Application

This module defines the main FastAPI application for the WhoseOnFirst
on-call rotation and SMS notification system.
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Import routers
from src.api.routes import team_members, shifts, schedules, notifications, auth, settings, schedule_overrides, admin
from src.api.routes.version import router as version_router
from src.scheduler import get_schedule_manager
from src.models.database import SessionLocal
from src.models.user import User, UserRole
from src.auth.utils import hash_password


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Handles application startup and shutdown events:
    - Startup: Initialize and start the APScheduler
    - Shutdown: Stop the scheduler gracefully
    """
    # Startup
    logger.info("Starting WhoseOnFirst API...")

    # Seed default admin user on first boot (empty DB)
    try:
        db = SessionLocal()
        user_count = db.query(User).count()
        if user_count == 0:
            default_admin = User(
                username="admin",
                password_hash=hash_password("Admin123!"),
                role=UserRole.ADMIN,
            )
            db.add(default_admin)
            db.commit()
            logger.info("Created default admin user (first boot — change password after login)")
        db.close()
    except Exception as e:
        logger.warning("Could not seed default admin: %s", str(e))

    # Initialize and start the scheduler
    try:
        scheduler = get_schedule_manager()
        scheduler.start()
        logger.info("Scheduler started successfully")

        # Log the next run time
        job_status = scheduler.get_job_status()
        if job_status:
            logger.info("Next notification job run: %s", job_status['next_run_time'])
    except Exception as e:
        logger.error("Failed to start scheduler: %s", str(e))
        raise

    yield

    # Shutdown
    logger.info("Shutting down WhoseOnFirst API...")

    # Stop the scheduler
    try:
        scheduler = get_schedule_manager()
        scheduler.stop(wait=True)
        logger.info("Scheduler stopped successfully")
    except Exception as e:
        logger.error("Error stopping scheduler: %s", str(e))


app = FastAPI(
    title="WhoseOnFirst API",
    description="Automated on-call rotation and SMS notification system for technical teams",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS middleware configuration
# Allow frontend to communicate with API during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:8080",  # Frontend HTTP server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "null"  # Allow file:// origins for local development
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API info endpoint (moved from root to avoid conflict with frontend)
@app.get("/api", tags=["root"])
async def api_info():
    """
    API information endpoint.

    Returns:
        dict: API name and version
    """
    return {
        "name": "WhoseOnFirst API",
        "version": "1.0.3",
        "description": "On-call rotation and SMS notification system",
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns:
        dict: Health status
    """
    return {
        "status": "healthy",
        "service": "whoseonfirst-api",
        "version": "0.2.0"
    }


# Include API routers
app.include_router(
    auth.router,
    prefix="/api/v1/auth",
    tags=["authentication"]
)
app.include_router(
    team_members.router,
    prefix="/api/v1/team-members",
    tags=["team-members"]
)
app.include_router(
    shifts.router,
    prefix="/api/v1/shifts",
    tags=["shifts"]
)
app.include_router(
    schedules.router,
    prefix="/api/v1/schedules",
    tags=["schedules"]
)
app.include_router(
    notifications.router,
    prefix="/api/v1/notifications",
    tags=["notifications"]
)
app.include_router(
    settings.router,
    prefix="/api/v1/settings",
    tags=["settings"]
)
app.include_router(
    schedule_overrides.router,
    prefix="/api/v1/schedule-overrides",
    tags=["schedule-overrides"]
)
app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["admin"]
)
app.include_router(version_router)

# Mount static files (frontend) - MUST be after API routes to avoid conflicts
# Serve frontend from the frontend directory
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")
    logger.info(f"Serving frontend from: {frontend_path}")

    # Serve index.html for root and catch-all SPA routing
    @app.get("/", response_class=FileResponse)
    @app.get("/{full_path:path}", response_class=FileResponse)
    async def serve_frontend(full_path: str = ""):
        """
        Serve frontend HTML files for SPA routing.
        Returns index.html for root, or specific HTML files if they exist.
        """
        # Map common routes to their HTML files
        route_map = {
            "": "index.html",
            "login.html": "login.html",
            "team-members.html": "team-members.html",
            "shifts.html": "shifts.html",
            "schedule.html": "schedule.html",
            "notifications.html": "notifications.html",
            "schedule-overrides.html": "schedule-overrides.html",
            "help.html": "help.html",
            "change-password.html": "change-password.html"
        }

        no_cache_headers = {"Cache-Control": "no-store"}

        # Check if it's a direct HTML file request
        if full_path in route_map:
            file_path = frontend_path / route_map[full_path]
            if file_path.exists():
                return FileResponse(file_path, headers=no_cache_headers)

        # Check if the file exists directly
        file_path = frontend_path / full_path
        if file_path.exists() and file_path.is_file():
            # HTML and sw.js must never be cached — stale sw.js breaks all future SW cache busts
            if str(file_path).endswith(".html") or file_path.name == "sw.js":
                return FileResponse(file_path, headers=no_cache_headers)
            return FileResponse(file_path)

        # Default to index.html for SPA routes
        return FileResponse(frontend_path / "index.html", headers=no_cache_headers)
else:
    logger.warning(f"Frontend directory not found: {frontend_path}")
