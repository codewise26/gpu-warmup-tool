"""Application configuration loading, merging, and validation."""

import os
from pathlib import Path
from typing import Any

import yaml

from .models import AppConfig


# Environment variable to config field mapping
_ENV_VAR_MAP: dict[str, str] = {
    "GC_DEPLOYMENT_ID": "deployment_id",
    "GC_REGION": "region",
    "GC_WARMUP_MESSAGE": "message",
    "GC_WARMUP_COUNT": "count",
    "GC_WARMUP_ORIGIN": "origin",
    "GC_WARMUP_TIMEOUT": "timeout",
}

# Fields that require type conversion from string env vars
_INT_FIELDS = {"count", "timeout"}

# Required fields that must be present for a warm-up run
_REQUIRED_FIELDS = ("deployment_id", "region")


def _load_config_file() -> dict[str, Any]:
    """Load configuration from a YAML config file.

    The config file path is determined by the GC_WARMUP_CONFIG_FILE env var,
    or defaults to 'config.yaml' in the current directory.

    Returns:
        A dictionary of config values from the file, or empty dict if
        the file doesn't exist.
    """
    config_path = os.environ.get("GC_WARMUP_CONFIG_FILE", "config.yaml")
    path = Path(config_path)

    if not path.exists():
        return {}

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return {}

    return data


def _load_env_vars() -> dict[str, Any]:
    """Load configuration values from environment variables.

    Returns:
        A dictionary of config field names to their values from env vars.
        Only includes env vars that are actually set.
    """
    result: dict[str, Any] = {}

    for env_var, field_name in _ENV_VAR_MAP.items():
        value = os.environ.get(env_var)
        if value is None:
            continue

        # Convert to appropriate type
        if field_name in _INT_FIELDS:
            result[field_name] = int(value)
        else:
            result[field_name] = value

    return result


def load_app_config() -> AppConfig:
    """Load configuration from env vars and config file.

    Precedence (highest to lowest):
    1. Environment variables
    2. Config file
    3. Model defaults

    Returns:
        A fully resolved AppConfig instance.
    """
    # Start with config file values
    file_config = _load_config_file()

    # Overlay env vars (higher precedence)
    env_config = _load_env_vars()

    # Merge: env vars override file config
    merged = {**file_config, **env_config}

    return AppConfig(**merged)


def merge_config(base: AppConfig, overrides: dict) -> AppConfig:
    """Merge overrides (CLI args or web UI inputs) on top of base config.

    Only non-None, non-empty values from overrides are applied.

    Args:
        base: The base AppConfig (from env vars / config file).
        overrides: Dictionary of override values.

    Returns:
        A new AppConfig with overrides applied.
    """
    base_dict = base.model_dump()

    for key, value in overrides.items():
        if value is not None and value != "":
            # Convert types for numeric fields
            if key in _INT_FIELDS:
                base_dict[key] = int(value)
            else:
                base_dict[key] = value

    return AppConfig(**base_dict)


def validate_required_config(config: AppConfig) -> list[str]:
    """Return list of missing required config fields.

    Required fields are: deployment_id, region.

    Args:
        config: The AppConfig to validate.

    Returns:
        A list of field names that are missing (None). Empty list if
        all required fields are present.
    """
    missing = []
    for field in _REQUIRED_FIELDS:
        value = getattr(config, field)
        if value is None:
            missing.append(field)
    return missing
