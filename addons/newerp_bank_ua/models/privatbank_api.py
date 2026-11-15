"""PrivatBank's Autoclient API (Privat24 for business): the account statement of a period.

GET {base}/api/proxy/transactions?startDate=dd-mm-YYYY&endDate=dd-mm-YYYY with the headers id and token of the
Autoclient. The answer is UTF-8, or Windows-1251 for older accounts. The token travels in a header, so requests are
never logged. A plain class: the tests replace requests.get and answer with the documented JSON.
"""

import json
import logging
from datetime import datetime

import requests

from odoo.exceptions import UserError

from .bank_transaction import BankTransaction

_logger = logging.getLogger(__name__)

BASE_URL = "https://acp.privatbank.ua"
TIMEOUT_SECONDS = 60
DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M")
TIME_FORMATS = ("%H:%M", "%H:%M:%S")
DETAILS = {"BPL_A_MFO": "payer_bank_code", "BPL_A_CRF": "payer_tax_code", "BPL_C_BAL": "balance"}


class PrivatBankApi:
    def __init__(self, env, client_id, token):
        if not client_id or not token:
            raise UserError(env._("Для цього журналу не задано id і токен Автоклієнта ПриватБанку."))
        self._env = env
        self._headers = {"id": client_id, "token": token}

    def statement(self, date_from, date_to):
        url = f"{BASE_URL}/api/proxy/transactions"
        params = {"startDate": date_from.strftime("%d-%m-%Y"), "endDate": date_to.strftime("%d-%m-%Y")}
        try:
            response = requests.get(url, params=params, headers=self._headers, timeout=TIMEOUT_SECONDS)
        except requests.RequestException as error:
            _logger.warning("PrivatBank statement failed: %s", type(error).__name__)
            raise UserError(self._env._("ПриватБанк не відповідає. Спробуйте трохи пізніше.")) from error
        text = _decode(response.content)
        if not response.ok:
            raise UserError(
                self._env._("ПриватБанк відмовив (%(code)s): %(text)s", code=response.status_code, text=_trim(text))
            )
        return parse_statement(self._env, text)


def parse_statement(env, text):
    """{"StatementsResponse": {"statements": [{"<account>": [{"0": {...}}, ...]}]}}"""
    try:
        statements = json.loads(text)["StatementsResponse"]["statements"]
    except (ValueError, KeyError, TypeError) as error:
        raise UserError(env._("ПриватБанк повернув невідому відповідь: %(text)s", text=_trim(text))) from error
    if not isinstance(statements, list):
        raise UserError(env._("ПриватБанк повернув невідому відповідь: %(text)s", text=_trim(text)))
    result = []
    for statement in statements:
        for account, rows in statement.items() if isinstance(statement, dict) else []:
            for wrapper in rows if isinstance(rows, list) else []:
                row = next(iter(wrapper.values()), None) if isinstance(wrapper, dict) else None
                if not isinstance(row, dict) or not _str(row, "ID"):
                    continue
                amount = _money(_str(row, "BPL_SUM_E"))
                result.append(
                    BankTransaction(
                        ref=_str(row, "ID"),
                        account=account,
                        date=_date(env, _str(row, "BPL_DAT_KL")),
                        time=_time(_str(row, "BPL_TIM_P")),
                        amount=-amount if _str(row, "TRANTYPE") == "D" else amount,
                        purpose=_str(row, "BPL_OSND"),
                        payer=_str(row, "BPL_A_NAM"),
                        payer_account=_str(row, "BPL_A_ACC"),
                        details={name: _str(row, key) for key, name in DETAILS.items() if _str(row, key)},
                    )
                )
    return result


def _decode(content):
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp1251")


def _date(env, text):
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    raise UserError(env._("ПриватБанк повернув незрозумілу дату: «%(text)s».", text=text))


def _time(text):
    for time_format in TIME_FORMATS:
        try:
            return datetime.strptime(text, time_format).strftime("%H:%M")
        except ValueError:
            continue
    return ""


def _money(text):
    try:
        return abs(float(text.replace(",", ".").replace(" ", ""))) if text else 0.0
    except ValueError:
        return 0.0


def _str(row, name):
    value = row.get(name)
    return "" if value is None or isinstance(value, (dict, list)) else str(value).strip()


def _trim(text):
    return text[:300] + "…" if len(text) > 300 else text
