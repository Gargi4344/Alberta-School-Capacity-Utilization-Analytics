"""FastAPI application entry point. OpenAPI docs at /docs."""

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging

configure_logging(get_settings().log_level)

app = FastAPI(
    title="Alberta School Capacity & Utilization API",
    version="0.1.0",
    description="Enrolment, capacity, utilization and forecasts for Alberta school authorities.",
)


def _error(status: int, code: str, message: str, details: object = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details}},
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = {404: "not_found", 401: "unauthorized", 403: "forbidden"}.get(exc.status_code, "error")
    return _error(exc.status_code, code, str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return _error(422, "validation_error", "Request parameters are invalid.", exc.errors())


app.include_router(api_router, prefix="/api/v1")
