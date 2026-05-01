"""Tests for Warm-Up Runner."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from src.models import AppConfig, WarmUpReport
from src.progress import ProgressEmitter
from src.warmup_runner import WarmUpRunner, compute_exit_code
from src.web_messaging_client import WebMessagingError


class TestComputeExitCode:
    """Tests for compute_exit_code."""

    def test_all_success(self, sample_report):
        assert compute_exit_code(sample_report) == 0

    def test_with_failures(self, sample_report_with_failures):
        assert compute_exit_code(sample_report_with_failures) == 1


class TestWarmUpRunner:
    """Tests for WarmUpRunner execution."""

    @pytest.fixture
    def config(self):
        return AppConfig(
            deployment_id="test-deploy",
            region="test.com",
            message="Warming up!",
            count=3,
            timeout=5,
        )

    @pytest.fixture
    def emitter(self):
        return ProgressEmitter()

    @pytest.mark.asyncio
    async def test_all_sessions_succeed(self, config, emitter):
        """Verify report has correct counts when all sessions succeed."""
        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(return_value="Response")

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.total_iterations == 3
        assert report.successes == 3
        assert report.failures == 0
        assert len(report.session_results) == 3
        for i, result in enumerate(report.session_results, 1):
            assert result.iteration == i
            assert result.success is True

    @pytest.mark.asyncio
    async def test_session_failure_continues(self, config, emitter):
        """Verify failed sessions are recorded and execution continues."""
        call_count = 0

        async def connect_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise WebMessagingError("Connection failed: deployment_id=test-deploy, region=test.com")

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=connect_side_effect)
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(return_value="Response")

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.total_iterations == 3
        assert report.successes == 2
        assert report.failures == 1
        assert len(report.session_results) == 3
        assert report.session_results[1].success is False
        assert report.session_results[1].error is not None

    @pytest.mark.asyncio
    async def test_progress_events_emitted(self, config, emitter):
        """Verify correct progress events are emitted."""
        q = emitter.subscribe()

        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(return_value="Response")

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            await runner.run()

        events = []
        while not q.empty():
            events.append(q.get_nowait())

        # Should have: 1 warmup_started + 3 session_completed + 1 warmup_completed
        event_types = [e.event_type.value for e in events]
        assert event_types[0] == "warmup_started"
        assert event_types[-1] == "warmup_completed"
        assert event_types.count("session_completed") == 3

    @pytest.mark.asyncio
    async def test_timeout_recorded_as_failure(self, emitter):
        """Verify timeout errors are recorded as failures."""
        config = AppConfig(
            deployment_id="test-deploy",
            region="test.com",
            count=1,
            timeout=1,
        )

        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(
            side_effect=TimeoutError("Timed out waiting for welcome message after 1s")
        )

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.failures == 1
        assert "Timed out" in report.session_results[0].error
