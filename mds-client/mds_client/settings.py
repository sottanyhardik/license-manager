"""
Settings helper for mds_client.

A consuming project configures the client entirely through Django settings so
there is one source of truth and the client itself stays stateless:

    MDS_BASE_URL = "https://masters.internal.example.com/api/v1/"
    MDS_TOKEN = "<service-to-service bearer token>"

    # model_label -> how to reach it on MDS + how to mirror it locally.
    #   endpoint     : the MDS URL segment (router basename path), e.g. "companies"
    #   natural_key  : the natural-key field name shared by MDS + mirror row
    #   mirror_model : "app_label.ModelName" of the LOCAL mirror model to upsert into
    MDS_MODELS = {
        "core.CompanyModel": {
            "endpoint": "companies",
            "natural_key": "iec",
            "mirror_model": "core.CompanyModel",
        },
        "core.PortModel": {
            "endpoint": "ports",
            "natural_key": "code",
            "mirror_model": "core.PortModel",
        },
        "core.ExchangeRateModel": {
            "endpoint": "exchange-rates",
            "natural_key": "date",
            "mirror_model": "core.ExchangeRateModel",
        },
    }

Optional tuning (sane defaults provided):
    MDS_TIMEOUT          = (connect, read) seconds tuple or a single float. Default (3.05, 30).
    MDS_MAX_RETRIES      = transient-failure retries for idempotent GETs. Default 3.
    MDS_BACKOFF_FACTOR   = exponential backoff base (seconds). Default 0.5.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# --- defaults ---------------------------------------------------------------
DEFAULT_TIMEOUT = (3.05, 30)
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_FACTOR = 0.5

#: keys each MDS_MODELS entry must define.
REQUIRED_MODEL_KEYS = ("endpoint", "natural_key", "mirror_model")


def get_base_url() -> str:
    url = getattr(settings, "MDS_BASE_URL", None)
    if not url:
        raise ImproperlyConfigured("MDS_BASE_URL is not set; the mds_client cannot reach the service.")
    # Normalise to a single trailing slash so urljoin behaves predictably.
    return url.rstrip("/") + "/"


def get_token() -> str:
    token = getattr(settings, "MDS_TOKEN", None)
    if not token:
        raise ImproperlyConfigured("MDS_TOKEN is not set; the mds_client cannot authenticate to the service.")
    return token


def get_models() -> dict:
    """The validated ``MDS_MODELS`` mapping (model_label -> config dict)."""
    models = getattr(settings, "MDS_MODELS", None)
    if not models:
        raise ImproperlyConfigured("MDS_MODELS is not set; nothing to sync/write.")
    if not isinstance(models, dict):
        raise ImproperlyConfigured("MDS_MODELS must be a dict of model_label -> config.")
    for label, cfg in models.items():
        if not isinstance(cfg, dict):
            raise ImproperlyConfigured(f"MDS_MODELS['{label}'] must be a dict.")
        missing = [k for k in REQUIRED_MODEL_KEYS if not cfg.get(k)]
        if missing:
            raise ImproperlyConfigured(
                f"MDS_MODELS['{label}'] is missing required key(s): {', '.join(missing)}."
            )
    return models


def get_model_config(model_label: str) -> dict:
    """Config for a single model_label, or raise if unknown."""
    models = get_models()
    cfg = models.get(model_label)
    if cfg is None:
        raise ImproperlyConfigured(
            f"'{model_label}' is not declared in MDS_MODELS; add its endpoint/natural_key/mirror_model."
        )
    return cfg


def get_timeout():
    return getattr(settings, "MDS_TIMEOUT", DEFAULT_TIMEOUT)


def get_max_retries() -> int:
    return int(getattr(settings, "MDS_MAX_RETRIES", DEFAULT_MAX_RETRIES))


def get_backoff_factor() -> float:
    return float(getattr(settings, "MDS_BACKOFF_FACTOR", DEFAULT_BACKOFF_FACTOR))
