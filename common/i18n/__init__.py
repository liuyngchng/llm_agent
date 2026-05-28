#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
i18n module — multi-language support for the entire application.
Supports: zh (Chinese), en (English), fr (French), ar (Arabic).

Language detection priority:
  1. URL parameter ?lang=
  2. Cookie lang=
  3. Browser Accept-Language header
  4. Default: zh
"""
import logging.config
import os
import re

from flask import g, request

from common.i18n._translations import TRANSLATIONS

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)

SUPPORTED_LANGS = ["zh", "en", "fr", "ar"]
DEFAULT_LANG = "zh"

# Maps Accept-Language prefix to our lang codes
_ACCEPT_LANG_MAP = {
    "zh": "zh",
    "en": "en",
    "fr": "fr",
    "ar": "ar",
}


def detect_lang() -> str:
    """Detect language from URL param > cookie > Accept-Language header > default."""
    # 1. URL parameter
    lang_param = request.args.get("lang", "").strip().lower()
    if lang_param in SUPPORTED_LANGS:
        return lang_param

    # 2. Cookie
    lang_cookie = request.cookies.get("lang", "").strip().lower()
    if lang_cookie in SUPPORTED_LANGS:
        return lang_cookie

    # 3. Accept-Language header
    accept_lang = request.headers.get("Accept-Language", "")
    if accept_lang:
        # Parse the header: "fr-CH, fr;q=0.9, en;q=0.8"
        parts = re.split(r"\s*,\s*", accept_lang)
        for part in parts:
            tag = part.split(";")[0].strip()
            prefix = tag.split("-")[0].lower()
            if prefix in _ACCEPT_LANG_MAP:
                return _ACCEPT_LANG_MAP[prefix]

    return DEFAULT_LANG


def get_current_lang() -> str:
    """Return the current request language, or default."""
    try:
        return g.get("lang", DEFAULT_LANG)
    except RuntimeError:
        return DEFAULT_LANG


def get_msg(key: str, lang: str | None = None, **kwargs) -> str:
    """Look up a translation key for the given language, formatting with kwargs.

    Key format: "section.specific_key" (e.g. "chat.error_empty_message")

    Args:
        key: dot-separated translation key
        lang: language code; if None, uses current request language
        **kwargs: format arguments for the template string
    """
    if lang is None:
        lang = get_current_lang()

    section, _, subkey = key.partition(".")
    section_dict = TRANSLATIONS.get(section, {})
    translations = section_dict.get(subkey)
    if not translations:
        logger.warning(f"i18n: missing key '{key}'")
        return key

    template = translations.get(lang) or translations.get(DEFAULT_LANG, key)
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, ValueError) as e:
            logger.warning(f"i18n: format error for key '{key}': {e}")
            return template
    return template


def _(key: str, **kwargs) -> str:
    """Jinja2 template helper — same as get_msg() but reads lang from Flask g."""
    return get_msg(key, **kwargs)


def get_js_translations(lang: str, scope: str | None = None) -> dict:
    """Return a flat dict of translation keys -> values for injection into JS.

    If scope is given, also include that section's translations.
    Common section is always included.
    """
    result = {}
    sections = ["common"]
    if scope:
        sections.append(scope)
    # Always include auth for login/register pages
    sections.append("auth")

    for section in sections:
        section_dict = TRANSLATIONS.get(section, {})
        for subkey, translations in section_dict.items():
            full_key = f"{section}.{subkey}"
            result[full_key] = translations.get(lang) or translations.get(DEFAULT_LANG, full_key)

    return result
