"""Tests for Web Messaging Client."""

import json

import pytest

from src.web_messaging_client import WebMessagingClient, WebMessagingError


class TestWebMessagingClient:
    """Tests for WebMessagingClient."""

    def test_ws_url_construction(self):
        """Verify WebSocket URL is correctly constructed."""
        client = WebMessagingClient(region="mypurecloud.com", deployment_id="abc-123")
        assert client.ws_url == "wss://webmessaging.mypurecloud.com/v1?deploymentId=abc-123"

    def test_ws_url_with_different_region(self):
        """Verify URL works with different regions."""
        client = WebMessagingClient(region="usw2.pure.cloud", deployment_id="xyz")
        assert client.ws_url == "wss://webmessaging.usw2.pure.cloud/v1?deploymentId=xyz"

    def test_configure_session_message(self):
        """Verify configureSession message contains deployment_id and token."""
        client = WebMessagingClient(region="test.com", deployment_id="deploy-1")
        msg = client.build_configure_session_message()
        assert msg["action"] == "configureSession"
        assert msg["deploymentId"] == "deploy-1"
        assert msg["token"]  # Non-empty token
        assert len(msg["token"]) > 0

    def test_text_message_content(self):
        """Verify text message contains the warm-up message."""
        client = WebMessagingClient(region="test.com", deployment_id="deploy-1")
        client._token = "test-token"
        msg = client.build_text_message("Warming up!")
        assert msg["action"] == "onMessage"
        assert msg["message"]["type"] == "Text"
        assert msg["message"]["text"] == "Warming up!"

    def test_error_contains_deployment_and_region(self):
        """Verify WebMessagingError messages contain deployment_id and region."""
        error = WebMessagingError(
            f"Failed: deployment_id=test-deploy, region=test.com"
        )
        assert "test-deploy" in str(error)
        assert "test.com" in str(error)

    def test_default_timeout_and_origin(self):
        """Verify default timeout and origin values."""
        client = WebMessagingClient(region="test.com", deployment_id="test")
        assert client.timeout == 30
        assert client.origin == "https://localhost"

    def test_custom_timeout_and_origin(self):
        """Verify custom timeout and origin values."""
        client = WebMessagingClient(
            region="test.com", deployment_id="test",
            timeout=60, origin="https://example.com"
        )
        assert client.timeout == 60
        assert client.origin == "https://example.com"
