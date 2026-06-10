"""Tests for Warm-Up Runner."""

from unittest.mock import AsyncMock, patch

import pytest

from src.models import AppConfig
from src.progress import ProgressEmitter
from src.warmup_runner import WarmUpRunner, compute_exit_code
from src.web_messaging_client import WebMessagingError


def _responses_until_disconnect(config: AppConfig, exchanges_before_disconnect: int = 1):
    """Build receive_response side_effect ending with the configured disconnect message."""
    responses = ["Agent reply"] * exchanges_before_disconnect
    responses.append(config.disconnect_message)
    return responses


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
        mock_client.receive_response = AsyncMock(
            side_effect=_responses_until_disconnect(config) * 10
        )

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.total_iterations == 3
        assert report.successes == 3
        assert report.failures == 0

    @pytest.mark.asyncio
    async def test_session_failure_continues(self, config, emitter):
        """Verify failed sessions are recorded and execution continues."""
        call_count = 0

        async def connect_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise WebMessagingError(
                    "Connection failed: deployment_id=test-deploy, region=test.com"
                )

        mock_client = AsyncMock()
        mock_client.connect = AsyncMock(side_effect=connect_side_effect)
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(
            side_effect=_responses_until_disconnect(config) * 10
        )

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.successes == 2
        assert report.failures == 1

    @pytest.mark.asyncio
    async def test_escalation_sent_on_every_response_until_disconnect(self, config, emitter):
        """Verify escalation message is sent after each reply until disconnect message."""
        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(
            side_effect=["Reply 1", "Reply 2", config.disconnect_message]
        )

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            config.count = 1
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.successes == 1
        calls = [call.args[0] for call in mock_client.send_message.call_args_list]
        assert calls == [
            config.message,
            config.escalation_message,
            config.escalation_message,
        ]

    @pytest.mark.asyncio
    async def test_custom_escalation_and_disconnect_messages(self, emitter):
        """Verify custom escalation and disconnect messages are used."""
        config = AppConfig(
            deployment_id="test-deploy",
            region="test.com",
            message="Hello!",
            escalation_message="Transfer me please",
            disconnect_message="Goodbye",
            count=1,
            timeout=5,
        )
        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(
            side_effect=["Bot reply", "Goodbye"]
        )

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.successes == 1
        calls = [call.args[0] for call in mock_client.send_message.call_args_list]
        assert calls == ["Hello!", "Transfer me please"]

    @pytest.mark.asyncio
    async def test_no_escalation_when_first_reply_is_disconnect(self, config, emitter):
        """Verify iteration completes without escalation if first reply is disconnect."""
        mock_client = AsyncMock()
        mock_client.wait_for_welcome = AsyncMock(return_value="Welcome!")
        mock_client.receive_response = AsyncMock(return_value=config.disconnect_message)

        with patch("src.warmup_runner.WebMessagingClient", return_value=mock_client):
            config.count = 1
            runner = WarmUpRunner(config=config, progress_emitter=emitter)
            report = await runner.run()

        assert report.successes == 1
        calls = [call.args[0] for call in mock_client.send_message.call_args_list]
        assert calls == [config.message]

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
