"""Reading the OpenCart shop's MySQL database (and, later, writing its stock).

A plain class, not an Odoo model: the sync model asks for it through OpenCartSync._opencart_source(), so tests give it
a fake with the same methods and never need MySQL. Values always go to MySQL as parameters (%s). The table prefix is
the only thing put into the SQL text, and it is checked against a strict pattern first.
"""

import re
from contextlib import contextmanager
from dataclasses import dataclass

PREFIX_PATTERN = re.compile(r"[a-z0-9_]{0,20}\Z")
SIZE_OPTION_NAME = "Розмір"  # the option whose values are sizes, as in the other NewErp versions


class OpenCartError(Exception):
    """The shop's database could not be read; the text is for people and holds no password."""


@dataclass(frozen=True)
class OpenCartConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    prefix: str = "dd_"
    language_id: int = 3


class MySqlOpenCartSource:
    def __init__(self, config: OpenCartConfig):
        if not config.host or not config.database or not config.user:
            raise OpenCartError("Заповніть у налаштуваннях OpenCart хост, базу й користувача.")
        if not PREFIX_PATTERN.match(config.prefix):
            raise OpenCartError("Префікс таблиць: лише латинські літери, цифри й _, до 20 символів.")
        self._config = config

    def check(self) -> None:
        with self._cursor() as cursor:
            cursor.execute("SELECT 1")

    def categories(self) -> list[dict]:
        """[{category_id, parent_id, name}]"""
        p = self._config.prefix
        return self._rows(
            f"SELECT c.category_id, c.parent_id, d.name FROM {p}category c "
            f"JOIN {p}category_description d ON d.category_id = c.category_id AND d.language_id = %s "
            "ORDER BY c.category_id",
            [self._config.language_id],
        )

    def products(self) -> list[dict]:
        """[{product_id, model, name, price, status, category_ids, sizes: [{id, name}]}]: id is the size row's
        product_option_value_id, the row the storefront counts stock on."""
        p, language = self._config.prefix, self._config.language_id
        products = self._rows(
            f"SELECT pr.product_id, pr.model, pr.price, pr.status, COALESCE(d.name, '') AS name FROM {p}product pr "
            f"LEFT JOIN {p}product_description d ON d.product_id = pr.product_id AND d.language_id = %s "
            "ORDER BY pr.product_id",
            [language],
        )
        links = self._rows(f"SELECT product_id, category_id FROM {p}product_to_category", [])
        sizes = self._rows(
            f"SELECT v.product_option_value_id AS id, v.product_id, vd.name FROM {p}product_option_value v "
            f"JOIN {p}option_description od ON od.option_id = v.option_id AND od.language_id = %s AND od.name LIKE %s "
            f"JOIN {p}option_value_description vd ON vd.option_value_id = v.option_value_id AND vd.language_id = %s "
            "ORDER BY v.product_option_value_id",
            [language, f"%{SIZE_OPTION_NAME}%", language],
        )
        for product in products:
            product["price"] = float(product["price"])
            product["category_ids"] = [
                row["category_id"] for row in links if row["product_id"] == product["product_id"]
            ]
            product["sizes"] = [
                {"id": row["id"], "name": row["name"]} for row in sizes if row["product_id"] == product["product_id"]
            ]
        return products

    def orders(self, since: str, limit: int = 500) -> list[dict]:
        """Orders changed at or after `since` ("YYYY-MM-DD HH:MM:SS"), oldest change first, each with its lines.
        Status 0 is an order the customer never finished; OpenCart keeps those, the ERP skips them.

        [{order_id, customer_id, firstname, lastname, email, telephone, shipping_city, shipping_address_1,
          shipping_address_2, shipping_method, shipping_code, payment_method, payment_code, comment, order_status_id,
          source, date_added, date_modified, lines: [{product_id, name, model, quantity, price, size_row_id}]}]"""
        p = self._config.prefix
        orders = self._rows(
            "SELECT o.order_id, o.customer_id, o.firstname, o.lastname, o.email, o.telephone, o.shipping_city, "
            "o.shipping_address_1, o.shipping_address_2, o.shipping_method, o.shipping_code, o.payment_method, "
            "o.payment_code, o.comment, o.order_status_id, COALESCE(s.name, '') AS source, o.date_added, "
            f"o.date_modified FROM {p}order o "
            f"LEFT JOIN {p}order_source s ON s.order_source_id = o.order_source_id AND s.language_id = %s "
            "WHERE o.order_status_id > 0 AND o.date_modified >= %s ORDER BY o.date_modified, o.order_id LIMIT %s",
            [self._config.language_id, since, limit],
        )
        if not orders:
            return []
        ids = tuple(order["order_id"] for order in orders)
        lines = self._rows(
            f"SELECT order_product_id, order_id, product_id, name, model, quantity, price FROM {p}order_product "
            "WHERE order_id IN %s ORDER BY order_product_id",
            [ids],
        )
        chosen = self._rows(
            f"SELECT order_product_id, product_option_value_id FROM {p}order_option WHERE order_id IN %s",
            [ids],
        )
        size_rows = {row["order_product_id"]: row["product_option_value_id"] for row in chosen}
        for order in orders:
            order["date_added"] = str(order["date_added"])
            order["date_modified"] = str(order["date_modified"])
            order["lines"] = [
                {
                    "product_id": line["product_id"],
                    "name": line["name"],
                    "model": line["model"],
                    "quantity": line["quantity"],
                    "price": float(line["price"]),
                    "size_row_id": size_rows.get(line["order_product_id"]),
                }
                for line in lines
                if line["order_id"] == order["order_id"]
            ]
        return orders

    def _rows(self, sql: str, params: list) -> list[dict]:
        with self._cursor() as cursor:
            cursor.execute(sql, params)  # values as parameters; the prefix in the text is checked in __init__
            return list(cursor.fetchall())

    @contextmanager
    def _cursor(self):
        import pymysql  # imported here, so the addon's other code and its tests load without it

        config = self._config
        try:
            connection = pymysql.connect(
                host=config.host,
                port=config.port,
                user=config.user,
                password=config.password,
                database=config.database,
                charset="utf8mb4",
                connect_timeout=10,
                read_timeout=120,
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True,
            )
        except pymysql.MySQLError as error:
            # Only the error code goes to people: pymysql's own text can name the host and the user.
            raise OpenCartError(f"Не вдалося з'єднатися з базою OpenCart (помилка {error.args[0]}).") from error
        try:
            with connection.cursor() as cursor:
                yield cursor
        except pymysql.MySQLError as error:
            raise OpenCartError(f"Помилка запиту до бази OpenCart (помилка {error.args[0]}).") from error
        finally:
            connection.close()
