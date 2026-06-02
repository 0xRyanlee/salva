"""
Salva Runtime Exception Hierarchy

This module provides a structured exception hierarchy for consistent error handling
across the Salva Runtime.
"""
from __future__ import annotations


class SalvaError(Exception):
    """Base exception for Salva Runtime"""
    code: str = "SALVA_ERROR"
    status_code: int = 500
    
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def to_response(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ProviderError(SalvaError):
    """检索提供者失败"""
    code = "PROVIDER_ERROR"
    status_code = 502
    
    def __init__(self, message: str, provider: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.provider = provider
        if provider:
            self.details["provider"] = provider


class ExtractionError(SalvaError):
    """实体抽取失败"""
    code = "EXTRACTION_ERROR"
    status_code = 422
    
    def __init__(self, message: str, entity_id: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.entity_id = entity_id
        if entity_id:
            self.details["entity_id"] = entity_id


class PersistenceError(SalvaError):
    """数据持久化失败"""
    code = "PERSISTENCE_ERROR"
    status_code = 500
    
    def __init__(self, message: str, operation: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.operation = operation
        if operation:
            self.details["operation"] = operation


class TimeoutError(SalvaError):
    """操作超时"""
    code = "TIMEOUT_ERROR"
    status_code = 504
    
    def __init__(self, message: str, operation: str | None = None, timeout_seconds: float | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.operation = operation
        self.timeout_seconds = timeout_seconds
        if operation:
            self.details["operation"] = operation
        if timeout_seconds:
            self.details["timeout_seconds"] = timeout_seconds


class ValidationError(SalvaError):
    """数据验证失败"""
    code = "VALIDATION_ERROR"
    status_code = 400
    
    def __init__(self, message: str, field: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.field = field
        if field:
            self.details["field"] = field


class NotFoundError(SalvaError):
    """资源不存在"""
    code = "NOT_FOUND_ERROR"
    status_code = 404
    
    def __init__(self, message: str, resource_type: str | None = None, resource_id: str | None = None, details: dict | None = None):
        super().__init__(message, details)
        self.resource_type = resource_type
        self.resource_id = resource_id
        if resource_type:
            self.details["resource_type"] = resource_type
        if resource_id:
            self.details["resource_id"] = resource_id