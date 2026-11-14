"""A fake OpenCart database for the tests: the same methods as MySqlOpenCartSource, rows like the shop's."""

import copy

from odoo.addons.newerp_opencart.models.opencart_source import OpenCartError


class FakeOpenCartSource:
    def __init__(self, categories=None, products=None, orders=None, fail=False):
        self.category_rows = categories or []
        self.product_rows = products or []
        self.order_rows = orders or []
        self.fail = fail
        self.asked_since = []

    def orders(self, since, limit=500):
        self._maybe_fail()
        self.asked_since.append(since)
        rows = sorted((o for o in self.order_rows if o["date_modified"] >= since), key=lambda o: o["date_modified"])
        return copy.deepcopy(rows[:limit])

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


def order(order_id, status_id, lines, changed="2026-11-01 10:00:00", **customer):
    """lines: [(product_id, name, quantity, price, size row id or None)]"""
    return {
        "order_id": order_id,
        "customer_id": customer.get("customer_id", 0),
        "firstname": customer.get("firstname", "Олена"),
        "lastname": customer.get("lastname", "Петренко"),
        "email": customer.get("email", ""),
        "telephone": customer.get("telephone", "+38 (067) 000-00-01"),
        "shipping_city": "Київ",
        "shipping_address_1": "",
        "shipping_address_2": "Відділення №1",
        "shipping_method": customer.get("shipping_method", "Нова Пошта: відділення"),
        "shipping_code": "",
        "payment_method": customer.get("payment_method", "Накладений платіж"),
        "payment_code": customer.get("payment_code", "cod"),
        "comment": "",
        "order_status_id": status_id,
        "source": customer.get("source", "Instagram"),
        "date_added": "2026-11-01 09:00:00",
        "date_modified": changed,
        "lines": [
            {"product_id": pid, "name": name, "model": "", "quantity": qty, "price": price, "size_row_id": row}
            for pid, name, qty, price, row in lines
        ],
    }


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
