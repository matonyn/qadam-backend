from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import engine, Base
from app.seed import seed_static_data
from app.database import SessionLocal
from app.routers import auth, maps, routing, events, discounts, reviews, academic, planner, study_rooms, settings, notifications

# Create all tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Qadam API",
    description="Campus companion app backend",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db = SessionLocal()
    try:
        seed_static_data(db)
    finally:
        db.close()


# ── Error handlers ───────────────────────────────────────────────────────────

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"success": False, "message": "Not found"})


@app.exception_handler(500)
async def server_error_handler(request: Request, exc):
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error"})


# ── Routers ──────────────────────────────────────────────────────────────────

PREFIX = "/api/v1"

app.include_router(auth.router, prefix=PREFIX)
app.include_router(maps.router, prefix=PREFIX)
app.include_router(routing.router, prefix=PREFIX)
app.include_router(events.router, prefix=PREFIX)
app.include_router(discounts.router, prefix=PREFIX)
app.include_router(reviews.router, prefix=PREFIX)
app.include_router(academic.router, prefix=PREFIX)
app.include_router(planner.router, prefix=PREFIX)
app.include_router(study_rooms.router, prefix=PREFIX)
app.include_router(settings.router, prefix=PREFIX)
app.include_router(notifications.router, prefix=PREFIX)


@app.get("/")
def root():
    return {"message": "Qadam API is running", "docs": "/docs"}
