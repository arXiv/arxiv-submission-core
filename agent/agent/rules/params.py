"""Rule param-getter helpers."""

from typing import Dict, Any

from arxiv.base.globals import get_application_config

from .base import ParamFunc


def empty_params(*args, **kwargs) -> Dict[str, Any]:
    """Return an empty dict."""
    return {}


def make_params(*variables: str) -> ParamFunc:
    """Make a param-getting function from config variables."""
    def params(*args, **kwargs):
        config = get_application_config()
        return {variable: config[variable] for variable in variables}
    return params
