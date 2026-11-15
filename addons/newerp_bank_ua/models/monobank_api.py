"""monobank's personal API: the statement of an account, also of a sole proprietor's (ФОП) account.

GET https://api.monobank.ua/personal/statement/{account}/{from}/{to} with the header X-Token; from and to are Unix
seconds, at most 31 days and an hour apart; one call a minute; at most 500 rows, newest first. Sums are in kopecks,
spending is negative. The token travels in a header, so requests are never logged. NewErpPython has no monobank
statement, so this client follows monobank's documentation only.
"""

import logging
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import requests

from odoo.exceptions import UserError

from .bank_transaction import BankTransaction

_logger = logging.getLogger(__name__)

API_URL = "https://api.monobank.ua/personal/statement/{account}/{start}/{end}"
TIMEOUT_SECONDS = 30
MAX_ROWS = 500  # monobank gives no more in one answer
KYIV = ZoneInfo("Europe/Kyiv")


class MonobankApi:
    def __init__(self, env, token, account="0"):
        if not token:
            raise UserError(env._("Для цього журналу не задано токен monobank."))
        self._env = env
        self._token = token
        self._account = account or "0"  # "0": the client's default account

    def statement(self, date_from, date_to):
        """Rows of the Kyiv days from date_from to date_to, both included."""
        start = int(datetime.combine(date_from, time.min, KYIV).timestamp())
        end = int(datetime.combine(date_to + timedelta(days=1), time.min, KYIV).timestamp()) - 1
        url = API_URL.format(account=self._account, start=start, end=end)
        try:
            response = requests.get(url, headers={"X-Token": self._token}, timeout=TIMEOUT_SECONDS)
            answer = response.json()
        except (requests.RequestException, ValueError) as error:
            _logger.warning("monobank statement failed: %s", type(error).__name__)
            raise UserError(self._env._("monobank не відповідає. Спробуйте трохи пізніше.")) from error
        if response.status_code == 429:
            raise UserError(self._env._("monobank дозволяє одну виписку на хвилину: спробуйте за хвилину."))
        if not response.ok or not isinstance(answer, list):
            text = answer.get("errorDescription") if isinstance(answer, dict) else None
            raise UserError(
                self._env._(
                    "monobank відмовив (%(code)s): %(text)s", code=response.status_code, text=text or "без пояснення"
                )
            )
        if len(answer) >= MAX_ROWS:
            raise UserError(
                self._env._(
                    "monobank віддає не більше %(rows)s рядків за раз: візьміть коротший період.", rows=MAX_ROWS
                )
            )
        return [parse_row(row, self._account) for row in answer if isinstance(row, dict) and row.get("id")]


def parse_row(row, account):
    moment = datetime.fromtimestamp(int(row.get("time") or 0), KYIV)
    # For a transfer the description names the sender ("Від: Іваненко Ірина") and the comment is the purpose.
    purpose = " ".join(str(row.get(key) or "").strip() for key in ("comment", "description")).strip()
    details = {
        "payer_tax_code": row.get("counterEdrpou"),
        "mcc": row.get("mcc"),
        "balance": (row.get("balance") or 0) / 100,
        "hold": row.get("hold"),
    }
    return BankTransaction(
        ref=str(row["id"]),
        account=str(account),
        date=moment.date(),
        time=moment.strftime("%H:%M"),
        amount=int(row.get("amount") or 0) / 100,
        purpose=purpose,
        payer=str(row.get("counterName") or "").strip(),
        payer_account=str(row.get("counterIban") or "").strip(),
        details={key: value for key, value in details.items() if value not in (None, "")},
    )
