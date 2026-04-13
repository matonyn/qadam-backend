import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import SUPABASE_CONFIGURED, SUPABASE_SERVICE_ROLE_CONFIGURED
from app.ml import init_ml_engines
from app.routers import academic, auth, discounts, events, maps, ml, notifications, planner, reviews, routing, settings, study_rooms
from app.seed import seed_static_data
from app.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

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
    if SUPABASE_CONFIGURED:
        if SUPABASE_SERVICE_ROLE_CONFIGURED:
            seed_static_data(get_supabase_client())
        else:
            logger.warning(
                "Skipping in-app seed: SUPABASE_SECRET_KEY (service_role) is not set. "
                "The publishable key is subject to RLS and cannot insert seed rows. "
                "Add the Secret key from Supabase Dashboard → Settings → API, or apply "
                "supabase/migrations/20260412210731_seed_qadam_mock_data.sql in the SQL editor."
            )
    else:
        logger.warning(
            "Supabase not configured (URL + API key). API routes that need the database will return 503."
        )
    init_ml_engines()


def _http_message(detail) -> str:
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict) and "msg" in first:
            return str(first["msg"])
    return "Request error"


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"success": False, "message": _http_message(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"success": False, "message": _http_message(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Keep response generic, but log full details for debugging.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"success": False, "message": "Internal server error"})


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
app.include_router(ml.router, prefix=PREFIX)


@app.get("/")
def root():
    return {"message": "Qadam API is running", "docs": "/docs"}
