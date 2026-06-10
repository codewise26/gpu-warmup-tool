"""Flask web application for the GPU Warm-Up Tool.

Provides a web UI for configuring warm-up parameters, triggering warm-up runs,
viewing results, and streaming progress via SSE.
"""

import asyncio
import json
import os
import queue
import threading
from types import SimpleNamespace
from typing import Optional

from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    url_for,
)

from .app_config import load_app_config, merge_config, validate_required_config
from .models import AppConfig, WarmUpReport
from .progress import ProgressEmitter
from .warmup_runner import WarmUpRunner

# Web form fields persisted across runs (in-memory for the app process lifetime).
_PERSISTED_WEB_FIELDS = ("deployment_id", "region")


def _config_for_home(app: Flask) -> AppConfig:
    """Load config for the home page, including last-submitted web form values."""
    config = load_app_config()
    persisted = app.config.get("persisted_web_config")
    if persisted:
        config = merge_config(config, persisted)
    return config


def _persist_web_fields(app: Flask, overrides: dict) -> None:
    """Remember deployment_id and region from the last successful form submission."""
    app.config["persisted_web_config"] = {
        key: overrides[key]
        for key in _PERSISTED_WEB_FIELDS
        if overrides.get(key)
    }


def _config_from_form_submission(
    base_config: AppConfig,
    deployment_id: str,
    region: str,
    message: str,
    escalation_message: str,
    disconnect_message: str,
    count: str,
    origin: str,
    timeout: str,
) -> SimpleNamespace:
    """Rebuild display config from raw form fields for re-rendering after validation errors."""
    return SimpleNamespace(
        deployment_id=deployment_id or base_config.deployment_id or "",
        region=region or base_config.region or "",
        message=message or base_config.message or "Warming up!",
        escalation_message=escalation_message or base_config.escalation_message,
        disconnect_message=disconnect_message or base_config.disconnect_message,
        count=count if count != "" else base_config.count,
        origin=origin or base_config.origin or "https://localhost",
        timeout=timeout if timeout != "" else base_config.timeout,
    )


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "templates"
        ),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

    # App state
    app.config["latest_report"]: Optional[WarmUpReport] = None
    app.config["progress_emitter"] = ProgressEmitter()
    app.config["run_active"] = False
    app.config["persisted_web_config"] = {}

    @app.route("/")
    def home():
        """Home page with config inputs."""
        return render_template(
            "home.html",
            config=_config_for_home(app),
            errors=None,
        )

    @app.route("/run", methods=["POST"])
    def run():
        """Trigger warm-up execution from form submission."""
        base_config = load_app_config()

        # Read form fields
        deployment_id = request.form.get("deployment_id", "").strip()
        region = request.form.get("region", "").strip()
        message = request.form.get("message", "").strip()
        escalation_message = request.form.get("escalation_message", "").strip()
        disconnect_message = request.form.get("disconnect_message", "").strip()
        count = request.form.get("count", "").strip()
        origin = request.form.get("origin", "").strip()
        timeout = request.form.get("timeout", "").strip()

        # Validate inputs
        errors = []
        if not deployment_id:
            errors.append("Deployment ID is required.")
        if not region:
            errors.append("Region is required.")
        if not message:
            errors.append("Warm-up message is required.")
        if count:
            try:
                count_int = int(count)
                if count_int < 1:
                    errors.append("Count must be a positive integer.")
            except ValueError:
                errors.append("Count must be a valid integer.")
        if timeout:
            try:
                timeout_int = int(timeout)
                if timeout_int < 1:
                    errors.append("Timeout must be a positive integer.")
            except ValueError:
                errors.append("Timeout must be a valid integer.")

        if errors:
            return render_template(
                "home.html",
                config=_config_from_form_submission(
                    _config_for_home(app),
                    deployment_id,
                    region,
                    message,
                    escalation_message,
                    disconnect_message,
                    count,
                    origin,
                    timeout,
                ),
                errors=errors,
            )

        # Merge web overrides with base config
        web_overrides = {}
        if deployment_id:
            web_overrides["deployment_id"] = deployment_id
        if region:
            web_overrides["region"] = region
        if message:
            web_overrides["message"] = message
        if escalation_message:
            web_overrides["escalation_message"] = escalation_message
        if disconnect_message:
            web_overrides["disconnect_message"] = disconnect_message
        if count:
            web_overrides["count"] = count
        if origin:
            web_overrides["origin"] = origin
        if timeout:
            web_overrides["timeout"] = timeout

        merged_config = merge_config(base_config, web_overrides)

        # Validate required config
        missing = validate_required_config(merged_config)
        if missing:
            errors = [
                f"Missing required configuration: {', '.join(missing)}"
            ]
            return render_template(
                "home.html",
                config=_config_from_form_submission(
                    _config_for_home(app),
                    deployment_id,
                    region,
                    message,
                    escalation_message,
                    disconnect_message,
                    count,
                    origin,
                    timeout,
                ),
                errors=errors,
            )

        _persist_web_fields(app, web_overrides)

        # Create a fresh progress emitter for this run
        progress_emitter = ProgressEmitter()
        app.config["progress_emitter"] = progress_emitter
        app.config["latest_report"] = None
        app.config["run_active"] = True

        # Start warm-up execution in a background thread
        def run_warmup():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                runner = WarmUpRunner(
                    config=merged_config,
                    progress_emitter=progress_emitter,
                )
                report = loop.run_until_complete(runner.run())
                app.config["latest_report"] = report
            finally:
                app.config["run_active"] = False
                loop.close()

        thread = threading.Thread(target=run_warmup, daemon=True)
        thread.start()

        return redirect(url_for("results"))

    @app.route("/results")
    def results():
        """Results page displaying the latest WarmUpReport."""
        report = app.config.get("latest_report")
        run_active = app.config.get("run_active", False)
        return render_template("results.html", report=report, run_active=run_active)

    @app.route("/progress")
    def progress():
        """SSE endpoint streaming ProgressEvent data to the browser."""
        emitter: ProgressEmitter = app.config["progress_emitter"]

        def event_stream():
            q = emitter.subscribe()
            try:
                while True:
                    try:
                        event = q.get(timeout=30)
                        data = event.model_dump(mode="json")
                        yield f"data: {json.dumps(data)}\n\n"
                        # Stop streaming after warmup_completed
                        if event.event_type.value == "warmup_completed":
                            break
                    except queue.Empty:
                        # Send keepalive comment
                        yield ": keepalive\n\n"
            finally:
                emitter.unsubscribe(q)

        return Response(
            event_stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=True)
