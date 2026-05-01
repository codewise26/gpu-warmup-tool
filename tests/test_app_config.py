"""Tests for application configuration."""

import os
import tempfile

import pytest
import yaml

from src.app_config import load_app_config, merge_config, validate_required_config
from src.models import AppConfig


class TestValidateRequiredConfig:
    """Tests for validate_required_config."""

    def test_all_present(self):
        config = AppConfig(deployment_id="test", region="test.com")
        assert validate_required_config(config) == []

    def test_missing_deployment_id(self):
        config = AppConfig(region="test.com")
        missing = validate_required_config(config)
        assert "deployment_id" in missing
        assert "region" not in missing

    def test_missing_region(self):
        config = AppConfig(deployment_id="test")
        missing = validate_required_config(config)
        assert "region" in missing
        assert "deployment_id" not in missing

    def test_both_missing(self):
        config = AppConfig()
        missing = validate_required_config(config)
        assert set(missing) == {"deployment_id", "region"}


class TestMergeConfig:
    """Tests for merge_config."""

    def test_override_deployment_id(self):
        base = AppConfig(deployment_id="old", region="test.com")
        merged = merge_config(base, {"deployment_id": "new"})
        assert merged.deployment_id == "new"
        assert merged.region == "test.com"

    def test_none_values_not_applied(self):
        base = AppConfig(deployment_id="test", region="test.com")
        merged = merge_config(base, {"deployment_id": None})
        assert merged.deployment_id == "test"

    def test_empty_string_not_applied(self):
        base = AppConfig(deployment_id="test", region="test.com")
        merged = merge_config(base, {"deployment_id": ""})
        assert merged.deployment_id == "test"

    def test_numeric_conversion(self):
        base = AppConfig(deployment_id="test", region="test.com")
        merged = merge_config(base, {"count": "5", "timeout": "60"})
        assert merged.count == 5
        assert merged.timeout == 60


class TestLoadAppConfig:
    """Tests for load_app_config."""

    def test_defaults_without_env_or_file(self):
        """Config loads with defaults when no env vars or file exist."""
        # Clear relevant env vars
        env_vars = [
            "GC_DEPLOYMENT_ID", "GC_REGION", "GC_WARMUP_MESSAGE",
            "GC_WARMUP_COUNT", "GC_WARMUP_ORIGIN", "GC_WARMUP_TIMEOUT",
            "GC_WARMUP_CONFIG_FILE",
        ]
        old_values = {}
        for var in env_vars:
            old_values[var] = os.environ.pop(var, None)

        # Point config file to non-existent path
        os.environ["GC_WARMUP_CONFIG_FILE"] = "/tmp/nonexistent_config.yaml"

        try:
            config = load_app_config()
            assert config.deployment_id is None
            assert config.region is None
            assert config.message == "Warming up!"
            assert config.count == 1
        finally:
            # Restore env vars
            os.environ.pop("GC_WARMUP_CONFIG_FILE", None)
            for var, val in old_values.items():
                if val is not None:
                    os.environ[var] = val

    def test_env_vars_override_defaults(self):
        """Environment variables override default values."""
        os.environ["GC_DEPLOYMENT_ID"] = "env-deploy"
        os.environ["GC_REGION"] = "env-region.com"
        os.environ["GC_WARMUP_CONFIG_FILE"] = "/tmp/nonexistent_config.yaml"

        try:
            config = load_app_config()
            assert config.deployment_id == "env-deploy"
            assert config.region == "env-region.com"
        finally:
            os.environ.pop("GC_DEPLOYMENT_ID", None)
            os.environ.pop("GC_REGION", None)
            os.environ.pop("GC_WARMUP_CONFIG_FILE", None)

    def test_config_file_values(self):
        """Config file values are loaded."""
        config_data = {
            "deployment_id": "file-deploy",
            "region": "file-region.com",
            "message": "File message",
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        os.environ["GC_WARMUP_CONFIG_FILE"] = config_path
        # Clear env vars that would override
        for var in ["GC_DEPLOYMENT_ID", "GC_REGION", "GC_WARMUP_MESSAGE"]:
            os.environ.pop(var, None)

        try:
            config = load_app_config()
            assert config.deployment_id == "file-deploy"
            assert config.region == "file-region.com"
            assert config.message == "File message"
        finally:
            os.environ.pop("GC_WARMUP_CONFIG_FILE", None)
            os.unlink(config_path)
