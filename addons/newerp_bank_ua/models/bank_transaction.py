from dataclasses import dataclass, field


@dataclass(frozen=True)
class BankTransaction:
    """One row of a bank statement, the same for every bank. amount: signed, incoming money is positive."""

    ref: str
    account: str
    date: object  # datetime.date
    time: str  # "HH:MM", the bank's local (Kyiv) time
    amount: float
    purpose: str = ""
    payer: str = ""
    payer_account: str = ""
    details: dict = field(default_factory=dict)  # the payer's bank code, tax code and so on
