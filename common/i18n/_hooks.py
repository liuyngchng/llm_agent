#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Flask hooks for i18n — before_request, context_processor, after_request."""
import json
import logging.config
import os

from flask import g, request

from common.i18n import detect_lang, get_msg, get_js_translations

log_config_path = 'logging.conf'
if os.path.exists(log_config_path):
    logging.config.fileConfig(log_config_path, encoding="utf-8")
else:
    from common.const import LOG_FORMATTER
    logging.basicConfig(level=logging.INFO, format=LOG_FORMATTER, force=True)
logger = logging.getLogger(__name__)


def register_i18n(app, scope: str | None = None):
    """Register i18n hooks on a Flask application.

    Args:
        app: Flask application instance
        scope: translation namespace for app-specific keys (e.g. 'doc_forge', 'docx')
    """

    @app.before_request
    def _detect_language():
        g.lang = detect_lang()
        g.dir = "rtl" if g.lang == "ar" else "ltr"

    @app.context_processor
    def _inject_i18n():
        lang = g.get("lang", "zh")
        direction = g.get("dir", "ltr")

        def translate(key, **kw):
            return get_msg(key, lang, **kw)

        return {
            "_": translate,
            "lang": lang,
            "dir": direction,
            "i18n_js": json.dumps(get_js_translations(lang, scope), ensure_ascii=False),
        }

    @app.after_request
    def _set_lang_cookie(response):
        lang_param = request.args.get("lang", "").strip().lower()
        if lang_param in ("zh", "en", "fr", "ar"):
            response.set_cookie("lang", lang_param, max_age=365 * 24 * 3600)
        return response

    logger.info(f"i18n registered for app with scope={scope}")
