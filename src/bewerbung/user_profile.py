"""Applicant profile loader for personalized Bewerbung documents."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from typing import Any

_PROFILE_DIR = Path(__file__).resolve().parent
_LOCAL_MODULE = _PROFILE_DIR / "user_profile.local.py"
_EXAMPLE_MODULE = _PROFILE_DIR / "user_profile.example.py"


def _load_profile_dict(module_path: Path) -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location("bewerbung_profile_module", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load profile module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    profile = getattr(module, "USER_PROFILE", None)
    if not isinstance(profile, dict):
        raise RuntimeError(f"{module_path} must define USER_PROFILE dict")
    return profile


def _resolve_profile_source() -> tuple[dict[str, Any], str]:
    if _LOCAL_MODULE.exists():
        return _load_profile_dict(_LOCAL_MODULE), "user_profile.local.py"
    if os.environ.get("BEWERBUNG_USE_EXAMPLE_PROFILE", "").lower() in {"1", "true", "yes"}:
        return _load_profile_dict(_EXAMPLE_MODULE), "user_profile.example.py (BEWERBUNG_USE_EXAMPLE_PROFILE)"
    raise FileNotFoundError(
        "No private profile found. Copy src/bewerbung/user_profile.example.py to "
        "src/bewerbung/user_profile.local.py and fill in your details. "
        "For demos only, set BEWERBUNG_USE_EXAMPLE_PROFILE=true."
    )


def get_profile() -> dict[str, Any]:
    profile, _source = _resolve_profile_source()
    return dict(profile)


def get_profile_source() -> str:
    _, source = _resolve_profile_source()
    return source
