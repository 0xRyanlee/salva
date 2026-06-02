"""
API Routes Package

This package contains modular route handlers for the Salva Runtime API.
"""
from fastapi import APIRouter

# Import all route modules to register them
from apps.api.routes import discovery, runs

# Export routers for easy inclusion in main.py
__all__ = ["discovery", "runs"]