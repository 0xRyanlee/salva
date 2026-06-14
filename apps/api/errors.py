"""
API Exception Handlers

Provides unified error handling for the Salva Runtime API.
"""
from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from salva_core.exceptions import (
    ExtractionError,
    NotFoundError,
    PersistenceError,
    ProviderError,
    SalvaError,
    TimeoutError,
    ValidationError,
)


async def salva_exception_handler(request: Request, exc: SalvaError) -> JSONResponse:
    """Handle SalvaError exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_response(),
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle FastAPI validation errors"""
    errors = []
    for error in exc.errors():
        errors.append({
            "location": error.get("loc", []),
            "message": error.get("msg", ""),
            "type": error.get("type", ""),
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    import os
    
    # Don't expose internal error details in production
    if os.getenv("SALVA_ENV") == "production":
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_ERROR",
                "message": "An internal error occurred",
            },
        )
    
    # In development, show the error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "INTERNAL_ERROR",
            "message": str(exc),
            "details": {"type": type(exc).__name__},
        },
    )


def register_exception_handlers(app: object) -> None:
    """Register all exception handlers with the FastAPI app"""
    from fastapi import FastAPI
    
    if not isinstance(app, FastAPI):
        raise TypeError("app must be a FastAPI instance")
    
    # type: ignore[arg-type]
    app.add_exception_handler(SalvaError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(ProviderError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(ExtractionError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(PersistenceError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(TimeoutError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, salva_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_exception_handler)