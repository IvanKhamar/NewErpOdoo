import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from .novaposhta_api import NovaPoshtaApi
from .np_warehouse import KINDS

WAREHOUSES_PAGE_SIZE = 500
MAX_WAREHOUSE_PAGES = 200  # 100 000 branches: a guard against an endless loop
MIN_WEIGHT_KG = 0.1  # Nova Poshta refuses a weight of 0, and products often have none filled in


class DeliveryCarrier(models.Model):
    """Nova Poshta as a delivery provider. Odoo calls <delivery_type>_rate_shipment, _send_shipping and the others by
    name, so adding the type and these methods is all it takes to plug a carrier into sales and deliveries.

    The carrier record holds its Nova Poshta account, as Odoo's other providers do: several sender accounts are
    several carriers."""

    _inherit = "delivery.carrier"

    delivery_type = fields.Selection(
        selection_add=[("novaposhta", "Нова Пошта")],
        ondelete={"novaposhta": lambda carriers: carriers.write({"delivery_type": "fixed", "fixed_price": 0})},
    )
    np_api_key = fields.Char("Ключ API", groups="base.group_system", copy=False)
    np_warehouse_kind = fields.Selection(KINDS, "Куди", default="branch")
    np_sender_ref = fields.Char("Відправник (Ref контрагента)", groups="base.group_system")
    np_contact_ref = fields.Char("Контактна особа відправника (Ref)", groups="base.group_system")
    np_sender_phone = fields.Char("Телефон відправника", groups="base.group_system")
    np_sender_city_ref = fields.Char("Місто відправки (Ref)", groups="base.group_system")
    np_sender_warehouse_ref = fields.Char("Відділення відправки (Ref)", groups="base.group_system")
    np_cargo_description = fields.Char("Опис вантажу", default="Одяг")
    np_payer = fields.Selection(
        [("Recipient", "Отримувач"), ("Sender", "Відправник")], "Хто платить за доставку", default="Recipient"
    )

    def _np_api(self):
        return NovaPoshtaApi(self.env, self.sudo().np_api_key)

    # ── Rate ──

    def novaposhta_rate_shipment(self, order):
        """The delivery cost from Nova Poshta. Without a key the carrier works as a fixed price, so a shop that has
        not set it up yet still takes orders."""
        self.ensure_one()
        if not self.sudo().np_api_key:
            return self.fixed_rate_shipment(order)
        if not order.np_warehouse_id:
            return _rate_error("Оберіть у замовленні відділення Нової Пошти.")
        sender = self.sudo()
        try:
            data = self._np_api().call(
                "InternetDocument",
                "getDocumentPrice",
                {
                    "CitySender": sender.np_sender_city_ref,
                    "CityRecipient": order.np_warehouse_id.city_ref,
                    "Weight": _number(_order_weight(order)),
                    "ServiceType": "WarehouseWarehouse",
                    "CargoType": "Parcel",
                    "SeatsAmount": "1",
                    "Cost": _number(order.amount_untaxed),
                    "DateTime": fields.Date.context_today(self).strftime("%d.%m.%Y"),
                },
            )
        except UserError as error:
            return _rate_error(str(error))
        price = float(data[0].get("Cost") or 0) if data else 0.0
        return {"success": True, "price": price, "error_message": False, "warning_message": False}

    # ── Branches ──

    def action_np_update_warehouses(self):
        """Refreshes the branches list from Nova Poshta; branches it no longer lists are kept, marked closed."""
        self.ensure_one()
        api = self._np_api()
        rows = []
        for page in range(1, MAX_WAREHOUSE_PAGES + 1):
            data = api.call("Address", "getWarehouses", {"Page": page, "Limit": WAREHOUSES_PAGE_SIZE})
            if not data:
                break
            rows += data
        created, updated = self.env["newerp.np.warehouse"].sudo()._np_store(rows)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "message": self.env._(
                    "Відділення: нових %(created)s, оновлених %(updated)s.", created=created, updated=updated
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _cron_np_update_warehouses(self):
        carrier = self.search([("delivery_type", "=", "novaposhta")]).filtered(lambda c: c.sudo().np_api_key)[:1]
        if carrier:
            carrier.action_np_update_warehouses()


def _rate_error(message):
    return {"success": False, "price": 0.0, "error_message": message, "warning_message": False}


def _order_weight(order):
    lines = order.order_line.filtered(lambda line: not line.is_delivery and line.product_id)
    return max(sum(line.product_id.weight * line.product_uom_qty for line in lines), MIN_WEIGHT_KG)


def _number(value):
    return f"{value:.2f}".rstrip("0").rstrip(".") or "0"


def branch_number(name):
    """The number in "Відділення №12 (до 30 кг): ..." for sorting; 0 when there is none."""
    match = re.search(r"№\s*(\d+)", name or "")
    return int(match.group(1)) if match else 0
