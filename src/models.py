"""Pydantic data models for the GPU Warm-Up Tool."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, field_validator


# --- Configuration ---


class AppConfig(BaseModel):
    """Application configuration with defaults."""

    deployment_id: Optional[str] = None
    region: Optional[str] = None
    message: str = "Warming up!"
    count: int = 1
    origin: str = "https://localhost"
    timeout: int = 30  # seconds

    @field_validator("count")
    @classmethod
    def count_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("count must be a positive integer")
        return v

    @field_validator("timeout")
    @classmethod
    def timeout_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("timeout must be a positive integer")
        return v

    @field_validator("deployment_id")
    @classmethod
    def deployment_id_must_be_non_empty(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("deployment_id must be non-empty")
        return v

    @field_validator("region")
    @classmethod
    def region_must_be_non_empty(cls, v):
        if v is not None and v.strip() == "":
            raise ValueError("region must be non-empty")
        return v

    @field_validator("message")
    @classmethod
    def message_must_be_non_empty(cls, v):
        if v.strip() == "":
            raise ValueError("message must be non-empty")
        return v


# --- Results ---


class SessionResult(BaseModel):
    """Outcome of a single warm-up session."""

    iteration: int  # 1-based
    success: bool
    duration_seconds: float
    error: Optional[str] = None  # Set if session failed


class WarmUpReport(BaseModel):
    """Aggregated summary of all warm-up sessions."""

    deployment_id: str
    region: str
    message: str
    total_iterations: int
    successes: int
    failures: int
    total_duration_seconds: float
    session_results: list[SessionResult]
    timestamp: datetime


# --- Progress Events ---


class ProgressEventType(str, Enum):
    """Types of progress events emitted during warm-up execution."""

    WARMUP_STARTED = "warmup_started"
    SESSION_COMPLETED = "session_completed"
    WARMUP_COMPLETED = "warmup_completed"


class ProgressEvent(BaseModel):
    """A progress event emitted during warm-up execution."""

    event_type: ProgressEventType
    iteration: Optional[int] = None  # Current iteration number
    total: Optional[int] = None  # Total iteration count
    success: Optional[bool] = None
    duration_seconds: Optional[float] = None
    message: str
    session_result: Optional[SessionResult] = None  # Full result for live UI updates
