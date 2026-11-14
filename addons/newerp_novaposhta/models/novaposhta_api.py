"""The Nova Poshta JSON API 2.0: one POST per call, {apiKey, modelName, calledMethod, methodProperties}.

A plain class, so the tests replace NovaPoshtaApi.call with documented answers and never reach the internet. Requests
are not logged: the key travels in the request body. It takes the Odoo environment only to translate its messages.
"""

import logging

import requests

from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

API_URL = "https://api.novaposhta.ua/v2.0/json/"
TIMEOUT_SECONDS = 30


class NovaPoshtaApi:
    def __init__(self, env, api_key):
        if not api_key:
            raise UserError(env._("Для цього способу доставки не задано ключ API Нової Пошти."))
        self._env = env
        self._api_key = api_key

    def call(self, model, method, properties):
        """The data list of the answer. Nova Poshta's own errors become a UserError with their text."""
        body = {"apiKey": self._api_key, "modelName": model, "calledMethod": method, "methodProperties": properties}
        try:
            response = requests.post(API_URL, json=body, timeout=TIMEOUT_SECONDS)
            response.raise_for_status()
            answer = response.json()
        except (requests.RequestException, ValueError) as error:
            _logger.warning("Nova Poshta %s.%s failed: %s", model, method, type(error).__name__)
            raise UserError(self._env._("Нова Пошта не відповідає. Спробуйте трохи пізніше.")) from error
        if answer.get("success") is not True:
            errors = "; ".join(map(str, answer.get("errors") or [])) or self._env._("без пояснення")
            raise UserError(self._env._("Нова Пошта відмовила: %(errors)s", errors=errors))
        return answer.get("data") or []
