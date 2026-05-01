"""Shared Hypothesis strategies and pytest fixtures for the GPU Warm-Up Tool tests."""

import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from hypothesis import strategies as st

# Add project root to path so src imports work
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    AppConfig,
    ProgressEvent,
    ProgressEventType,
    SessionResult,
    WarmUpReport,
)


# --- Hypothesis Strategies ---

# Non-empty strings (for valid deployment_id, region, message)
non_empty_strings = st.text(min_size=1, max_size=100).filter(lambda s: s.strip() != "")

# Whitespace-only strings (for testing empty field rejection)
whitespace_only_strings = st.sampled_from(["", " ", "  ", "\t", "\n", "  \t\n  "])

# Non-positive integers (for testing count/timeout rejection)
non_positive_integers = st.integers(max_value=0)

# Positive integers (for valid count/timeout)
positive_integers = st.integers(min_value=1, max_value=1000)

# Valid AppConfig strategy
valid_app_configs = st.builds(
    AppConfig,
    deployment_id=non_empty_strings,
    region=non_empty_strings,
    message=non_empty_strings,
    count=positive_integers,
    origin=non_empty_strings,
    timeout=positive_integers,
)


# SessionResult strategies
success_session_results = st.builds(
    SessionResult,
    iteration=st.integers(min_value=1, max_value=100),
    success=st.just(True),
    duration_seconds=st.floats(min_value=0.01, max_value=300.0, allow_nan=False),
    error=st.none(),
)

failure_session_results = st.builds(
    SessionResult,
    iteration=st.integers(min_value=1, max_value=100),
    success=st.just(False),
    duration_seconds=st.floats(min_value=0.01, max_value=300.0, allow_nan=False),
    error=non_empty_strings,
)

any_session_results = st.one_of(success_session_results, failure_session_results)

# ProgressEvent strategy
progress_events = st.builds(
    ProgressEvent,
    event_type=st.sampled_from(list(ProgressEventType)),
    iteration=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
    total=st.one_of(st.none(), st.integers(min_value=1, max_value=100)),
    success=st.one_of(st.none(), st.booleans()),
    duration_seconds=st.one_of(st.none(), st.floats(min_value=0.01, max_value=300.0, allow_nan=False)),
    message=non_empty_strings,
    session_result=st.none(),
)


def build_warmup_report(n: int, failure_indices: set = None) -> WarmUpReport:
    """Build a WarmUpReport with N sessions, optionally failing specific indices.

    Args:
        n: Total number of sessions.
        failure_indices: Set of 1-based iteration numbers that should fail.

    Returns:
        A WarmUpReport instance.
    """
    if failure_indices is None:
        failure_indices = set()

    results = []
    for i in range(1, n + 1):
        if i in failure_indices:
            results.append(SessionResult(
                iteration=i, success=False, duration_seconds=1.0, error="test error"
            ))
        else:
            results.append(SessionResult(
                iteration=i, success=True, duration_seconds=1.0
            ))

    successes = sum(1 for r in results if r.success)
    failures = n - successes

    return WarmUpReport(
        deployment_id="test-deploy",
        region="test.com",
        message="Warming up!",
        total_iterations=n,
        successes=successes,
        failures=failures,
        total_duration_seconds=float(n),
        session_results=results,
        timestamp=datetime.now(timezone.utc),
    )


# --- Pytest Fixtures ---


@pytest.fixture
def sample_report():
    """A sample WarmUpReport with 3 successful sessions."""
    return build_warmup_report(3)


@pytest.fixture
def sample_report_with_failures():
    """A sample WarmUpReport with 1 failure out of 3 sessions."""
    return build_warmup_report(3, failure_indices={2})


@pytest.fixture
def mock_web_messaging_client():
    """A mock WebMessagingClient that succeeds on all operations."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.send_join = AsyncMock()
    client.wait_for_welcome = AsyncMock(return_value="Welcome!")
    client.send_message = AsyncMock()
    client.receive_response = AsyncMock(return_value="Response received.")
    client.disconnect = AsyncMock()
    return client


@pytest.fixture
def flask_test_client():
    """A Flask test client for the GPU Warm-Up Tool web app."""
    from src.web_app import create_app
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client
