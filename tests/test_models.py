"""Tests for data models."""

import pytest
from pydantic import ValidationError

from src.models import AppConfig, SessionResult, WarmUpReport, ProgressEvent, ProgressEventType


class TestAppConfig:
    """Tests for AppConfig model."""

    def test_defaults(self):
        """Verify default values for optional fields."""
        config = AppConfig(deployment_id="test", region="test.com")
        assert config.message == "Warming up!"
        assert config.escalation_message == "I want to talk to human agent"
        assert config.disconnect_message == "Disconnecting now"
        assert config.count == 1
        assert config.origin == "https://localhost"
        assert config.timeout == 30

    def test_custom_values(self):
        """Verify custom values override defaults."""
        config = AppConfig(
            deployment_id="deploy-1",
            region="mypurecloud.com",
            message="Hello!",
            count=5,
            origin="https://example.com",
            timeout=60,
        )
        assert config.deployment_id == "deploy-1"
        assert config.region == "mypurecloud.com"
        assert config.message == "Hello!"
        assert config.count == 5
        assert config.origin == "https://example.com"
        assert config.timeout == 60

    def test_count_must_be_positive(self):
        """Verify count < 1 is rejected."""
        with pytest.raises(ValidationError, match="count must be a positive integer"):
            AppConfig(deployment_id="test", region="test.com", count=0)

    def test_timeout_must_be_positive(self):
        """Verify timeout < 1 is rejected."""
        with pytest.raises(ValidationError, match="timeout must be a positive integer"):
            AppConfig(deployment_id="test", region="test.com", timeout=0)

    def test_empty_deployment_id_rejected(self):
        """Verify empty deployment_id is rejected."""
        with pytest.raises(ValidationError, match="deployment_id must be non-empty"):
            AppConfig(deployment_id="", region="test.com")

    def test_empty_region_rejected(self):
        """Verify empty region is rejected."""
        with pytest.raises(ValidationError, match="region must be non-empty"):
            AppConfig(deployment_id="test", region="")

    def test_empty_message_rejected(self):
        """Verify empty message is rejected."""
        with pytest.raises(ValidationError, match="message must be non-empty"):
            AppConfig(deployment_id="test", region="test.com", message="")

    def test_whitespace_deployment_id_rejected(self):
        """Verify whitespace-only deployment_id is rejected."""
        with pytest.raises(ValidationError, match="deployment_id must be non-empty"):
            AppConfig(deployment_id="   ", region="test.com")

    def test_none_deployment_id_allowed(self):
        """Verify None deployment_id is allowed (for partial config)."""
        config = AppConfig(region="test.com")
        assert config.deployment_id is None


class TestSessionResult:
    """Tests for SessionResult model."""

    def test_success_result(self):
        result = SessionResult(iteration=1, success=True, duration_seconds=1.5)
        assert result.iteration == 1
        assert result.success is True
        assert result.error is None

    def test_failure_result(self):
        result = SessionResult(iteration=2, success=False, duration_seconds=30.0, error="Timeout")
        assert result.success is False
        assert result.error == "Timeout"


class TestProgressEvent:
    """Tests for ProgressEvent model."""

    def test_warmup_started_event(self):
        event = ProgressEvent(
            event_type=ProgressEventType.WARMUP_STARTED,
            total=5,
            message="Starting warm-up",
        )
        assert event.event_type == ProgressEventType.WARMUP_STARTED
        assert event.total == 5
