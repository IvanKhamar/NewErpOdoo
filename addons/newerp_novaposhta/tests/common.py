"""A fake Nova Poshta API for the tests: answers in the documented format, and every call kept for checks."""

from contextlib import contextmanager
from unittest.mock import patch

from odoo.addons.newerp_novaposhta.models.novaposhta_api import NovaPoshtaApi
from odoo.exceptions import UserError


class FakeNovaPoshta:
    def __init__(self, answers):
        """answers: {(model, method): data list, or a function (properties) -> data list, or an Exception}"""
        self.answers = answers
        self.calls = []

    def call(self, model, method, properties):
        self.calls.append((model, method, properties))
        answer = self.answers.get((model, method), [])
        if isinstance(answer, Exception):
            raise answer
        return answer(properties) if callable(answer) else answer

    def sent(self, model, method):
        return [properties for m, n, properties in self.calls if (m, n) == (model, method)]


@contextmanager
def fake_novaposhta(answers):
    fake = FakeNovaPoshta(answers)
    with patch.object(
        NovaPoshtaApi, "call", lambda _self, model, method, properties: fake.call(model, method, properties)
    ):
        yield fake


def refused(text):
    return UserError(f"Нова Пошта відмовила: {text}")


WAREHOUSES = [
    {
        "Ref": "wh-kyiv-1",
        "Description": "Відділення №1: вул. Хрещатик, 1",
        "CategoryOfWarehouse": "Branch",
        "CityRef": "city-kyiv",
        "CityDescription": "Київ",
        "TotalMaxWeightAllowed": "30",
        "WarehouseStatus": "Working",
    },
    {
        "Ref": "wh-kyiv-2",
        "Description": "Поштомат №2",
        "CategoryOfWarehouse": "Postomat",
        "CityRef": "city-kyiv",
        "CityDescription": "Київ",
        "TotalMaxWeightAllowed": 20,
        "WarehouseStatus": "Working",
    },
    {
        "Ref": "wh-lviv-12",
        "Description": "Відділення №12 (до 30 кг)",
        "CategoryOfWarehouse": "Branch",
        "CityRef": "city-lviv",
        "CityDescription": "Львів",
        "TotalMaxWeightAllowed": "30",
        "WarehouseStatus": "Closed",
    },
]


def pages(rows, size=500):
    """getWarehouses by pages: the rows on page 1, nothing after."""
    return lambda properties: rows if properties["Page"] == 1 else []
