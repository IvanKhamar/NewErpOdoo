"""PrivatBank's statement in its documented format (the samples of NewErpPython) and a fake requests.get."""

import json
from contextlib import contextmanager
from unittest.mock import patch

ACCOUNT = "UA213052990000026001000000001"

STATEMENT = """{"StatementsResponse": {"statements": [
  {"UA213052990000026001000000001": [
    {"0": {"ID": "tx-1", "TRANTYPE": "C", "BPL_SUM_E": "1500.00", "BPL_DAT_KL": "15.10.2026", "BPL_TIM_P": "14:05",
           "BPL_OSND": "Оплата зам. 2045", "BPL_A_NAM": "Іваненко Ірина", "BPL_A_ACC": "UA11", "BPL_A_MFO": "305299",
           "BPL_A_CRF": "1234567890", "BPL_C_BAL": "9000.50"}},
    {"1": {"ID": "tx-2", "TRANTYPE": "D", "BPL_SUM_E": "200", "BPL_DAT_KL": "15.10.2026", "BPL_TIM_P": "15:00",
           "BPL_OSND": "Комісія"}}
  ]}
]}}"""


def statement(*rows, account=ACCOUNT):
    """A statement of rows: (id, sign "C" or "D", sum, date dd.mm.YYYY, purpose, payer)."""
    wrapped = [
        {str(i): {"ID": ref, "TRANTYPE": sign, "BPL_SUM_E": f"{amount:.2f}", "BPL_DAT_KL": day, "BPL_TIM_P": "10:00",
                  "BPL_OSND": purpose, "BPL_A_NAM": payer}}
        for i, (ref, sign, amount, day, purpose, payer) in enumerate(rows)
    ]  # fmt: skip
    return json.dumps({"StatementsResponse": {"statements": [{account: wrapped}]}}, ensure_ascii=False)


class FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code
        self.ok = status_code < 400


@contextmanager
def fake_privatbank(answer, status_code=200, encoding="utf-8"):
    """Every requests.get of the client answers with this text; the calls are kept for checks."""
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append({"url": url, "params": params, "headers": headers})
        text = answer() if callable(answer) else answer
        return FakeResponse(text.encode(encoding), status_code)

    with patch("odoo.addons.newerp_bank_ua.models.privatbank_api.requests.get", side_effect=get):
        yield calls
