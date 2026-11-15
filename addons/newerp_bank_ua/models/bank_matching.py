"""Which order a bank payment belongs to: the rules of NewErpPython (domain/payments.py), as plain functions, so they
are tested without a database. The ORM side (account_bank_statement_line.py) feeds them candidates."""

import re
from dataclasses import dataclass
from enum import IntFlag


class Reason(IntFlag):
    """Why an order fits a payment; the flags combine."""

    NONE = 0
    ORDER_NUMBER = 1
    TOTAL = 2
    PREPAYMENT = 4
    PHONE = 8
    NAME = 16


REASON_LABELS = {
    Reason.ORDER_NUMBER: "номер замовлення",
    Reason.TOTAL: "сума замовлення",
    Reason.PREPAYMENT: "передоплата чи решта",
    Reason.PHONE: "телефон",
    Reason.NAME: "прізвище",
}

SCORES = {Reason.ORDER_NUMBER: 50, Reason.PHONE: 30, Reason.TOTAL: 25, Reason.PREPAYMENT: 20, Reason.NAME: 15}
ALREADY_PAID_PENALTY = 40


@dataclass(frozen=True)
class Candidate:
    """An order a payment may belong to. advance: the prepayment the order asks for (0 when none); paid: what other
    payments already brought; linked: another payment is linked to it already."""

    key: int
    numbers: frozenset
    customer: str
    phone: str
    total: float
    advance: float
    paid: float
    linked: bool
    date: object  # for the order of equal scores: the newest first


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    reasons: Reason
    score: int


def order_numbers_in(text):
    """Numbers of 3–7 digits that are not part of a sum ("2045", not "1500.00")."""
    return list(dict.fromkeys(int(m) for m in re.findall(r"(?<![\d.,])\d{3,7}(?!\d|[.,]\d)", text or "")))


def phone_key(phone):
    """The last 9 digits of a Ukrainian number, however it was typed."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else ""


def _same(a, b):
    return round(a, 2) == round(b, 2)


def rank(text, amount, candidates):
    """Scores orders by what the payment says: the order number in the purpose, the sum (the total, the advance or
    the rest), the phone and the surname. An order that already has another payment loses points."""
    text = text or ""
    digits = re.sub(r"\D", "", text)
    numbers = set(order_numbers_in(text))
    lower = text.casefold()
    scored = []
    for c in candidates:
        reasons = Reason.NONE
        if numbers & c.numbers:
            reasons |= Reason.ORDER_NUMBER
        if _same(c.total, amount):
            reasons |= Reason.TOTAL
        elif (c.advance > 0 and (_same(c.advance, amount) or _same(c.total - c.advance, amount))) or (
            c.paid > 0 and _same(c.total - c.paid, amount)
        ):
            reasons |= Reason.PREPAYMENT
        phone = phone_key(c.phone)
        if phone and phone in digits:
            reasons |= Reason.PHONE
        words = (c.customer or "").split()
        if words and len(words[-1]) >= 3 and words[-1].casefold() in lower:
            reasons |= Reason.NAME
        score = sum(points for reason, points in SCORES.items() if reason in reasons)
        score -= ALREADY_PAID_PENALTY if c.linked else 0
        scored.append(Scored(c, reasons, score))
    return sorted(scored, key=lambda s: (s.score, s.candidate.date), reverse=True)


def is_confident(scored):
    """Sure enough to link without a person: the purpose names the order (its number or its phone), the sum fits
    (the total, the advance or the rest), and the order has no payment yet. A surname and a sum are not enough: the
    same sum from a namesake happens."""
    names_order = bool(scored.reasons & (Reason.ORDER_NUMBER | Reason.PHONE))
    sum_fits = bool(scored.reasons & (Reason.TOTAL | Reason.PREPAYMENT))
    return names_order and sum_fits and not scored.candidate.linked


def confident_match(ranked):
    """The candidate to link automatically: only when exactly one is confident (two are a question for a person)."""
    confident = [s for s in ranked if is_confident(s)]
    return confident[0].candidate if len(confident) == 1 else None


def describe(reasons):
    return ", ".join(label for reason, label in REASON_LABELS.items() if reason in reasons)
