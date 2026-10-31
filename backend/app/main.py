from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.init_db import init_models, seed_data
from app.api.v1.auth import router as auth_router
from app.api.v1.pages import router as pages_router
from app.api.v1.posts import router as posts_router
from app.api.v1.comments import router as comments_router
from app.api.v1.rules import router as rules_router
from app.api.v1.reports import router as reports_router
from app.api.v1.webhook import router as webhook_router
from app.api.v1.ads import router as ads_router
from app.api.v1.system import router as system_router
from app.services.scheduler import start_scheduler, stop_scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database and initial seed data
    await init_models()
    await seed_data()
    print("Database initialized and demo data seeded successfully.")
    
    # Start automated daily posting & monitoring background scheduler
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()
    print("Application shutting down.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise AI-Powered Facebook Page Engagement & Automation System (PyLoom)",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers under /api/v1
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(pages_router, prefix=settings.API_V1_STR)
app.include_router(posts_router, prefix=settings.API_V1_STR)
app.include_router(comments_router, prefix=settings.API_V1_STR)
app.include_router(rules_router, prefix=settings.API_V1_STR)
app.include_router(reports_router, prefix=settings.API_V1_STR)
app.include_router(webhook_router, prefix=settings.API_V1_STR)
app.include_router(ads_router, prefix=settings.API_V1_STR)
app.include_router(system_router, prefix=settings.API_V1_STR)

@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "mode": "Simulation/Active"
    }

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": f"Welcome to {settings.PROJECT_NAME} API",
        "docs_url": "/docs",
        "api_v1": settings.API_V1_STR
    }
