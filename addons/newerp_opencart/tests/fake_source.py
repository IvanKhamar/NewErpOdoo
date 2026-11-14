"""A fake OpenCart database for the tests: the same methods as MySqlOpenCartSource, rows like the shop's."""

import copy

from odoo.addons.newerp_opencart.models.opencart_source import OpenCartError


class FakeOpenCartSource:
    def __init__(self, categories=None, products=None, fail=False):
        self.category_rows = categories or []
        self.product_rows = products or []
        self.fail = fail

    def check(self):
        self._maybe_fail()

    def categories(self):
        self._maybe_fail()
        return copy.deepcopy(self.category_rows)

    def products(self):
        self._maybe_fail()
        return copy.deepcopy(self.product_rows)

    def _maybe_fail(self):
        if self.fail:
            raise OpenCartError("Не вдалося з'єднатися з базою OpenCart (помилка 2003).")


def category(category_id, name, parent_id=0):
    return {"category_id": category_id, "parent_id": parent_id, "name": name}


def product(product_id, name, model, price, category_ids=(), sizes=(), status=1):
    """sizes: [(product_option_value_id, size name)]"""
    return {
        "product_id": product_id,
        "model": model,
        "name": name,
        "price": price,
        "status": status,
        "category_ids": list(category_ids),
        "sizes": [{"id": row_id, "name": name} for row_id, name in sizes],
    }
