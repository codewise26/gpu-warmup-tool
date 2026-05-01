"""Tests for Flask Web Application."""

import pytest

from src.web_app import create_app


@pytest.fixture
def app():
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


class TestWebApp:
    """Tests for Flask routes."""

    def test_home_page_loads(self, client):
        """Verify home page renders with form fields."""
        response = client.get("/")
        assert response.status_code == 200
        html = response.data.decode()
        assert "GPU Warm-Up Tool" in html
        assert "deployment_id" in html
        assert "region" in html
        assert "message" in html
        assert "count" in html

    def test_run_missing_deployment_id(self, client):
        """Verify validation error when deployment_id is missing."""
        response = client.post("/run", data={
            "deployment_id": "",
            "region": "test.com",
            "message": "Warming up!",
            "count": "1",
        })
        assert response.status_code == 200
        html = response.data.decode()
        assert "Deployment ID is required" in html

    def test_run_missing_region(self, client):
        """Verify validation error when region is missing."""
        response = client.post("/run", data={
            "deployment_id": "test-deploy",
            "region": "",
            "message": "Warming up!",
            "count": "1",
        })
        assert response.status_code == 200
        html = response.data.decode()
        assert "Region is required" in html

    def test_run_invalid_count(self, client):
        """Verify validation error when count is invalid."""
        response = client.post("/run", data={
            "deployment_id": "test-deploy",
            "region": "test.com",
            "message": "Warming up!",
            "count": "0",
        })
        assert response.status_code == 200
        html = response.data.decode()
        assert "Count must be a positive integer" in html

    def test_run_invalid_timeout(self, client):
        """Verify validation error when timeout is invalid."""
        response = client.post("/run", data={
            "deployment_id": "test-deploy",
            "region": "test.com",
            "message": "Warming up!",
            "count": "1",
            "timeout": "0",
        })
        assert response.status_code == 200
        html = response.data.decode()
        assert "Timeout must be a positive integer" in html

    def test_run_missing_message(self, client):
        """Verify validation error when message is empty."""
        response = client.post("/run", data={
            "deployment_id": "test-deploy",
            "region": "test.com",
            "message": "",
            "count": "1",
        })
        assert response.status_code == 200
        html = response.data.decode()
        assert "Warm-up message is required" in html

    def test_results_page_no_report(self, client):
        """Verify results page shows waiting message when no report exists."""
        response = client.get("/results")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Waiting for results" in html

    def test_results_page_with_report(self, app, client):
        """Verify results page renders report data."""
        from tests.conftest import build_warmup_report
        report = build_warmup_report(3, failure_indices={2})
        app.config["latest_report"] = report

        response = client.get("/results")
        assert response.status_code == 200
        html = response.data.decode()
        assert "test-deploy" in html
        assert "test.com" in html
        assert "3" in html  # total iterations
        assert "2" in html  # successes
        assert "1" in html  # failures
