import re

from odoo import api, fields, models
from odoo.exceptions import UserError

from .novaposhta_api import NovaPoshtaApi
from .np_warehouse import CARRIER_KINDS
from .stock_picking import _phone

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
    np_warehouse_kind = fields.Selection(CARRIER_KINDS, "Куди", default="branch")
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
        sender = self.sudo()
        try:
            city_ref = order._np_city_ref()
            data = self._np_api().call(
                "InternetDocument",
                "getDocumentPrice",
                {
                    "CitySender": sender.np_sender_city_ref,
                    "CityRecipient": city_ref,
                    "Weight": _number(_order_weight(order)),
                    "ServiceType": self._np_service_type(),
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

    # ── Waybills ──

    def novaposhta_send_shipping(self, pickings):
        """Called when a delivery is validated: the recipient, then the waybill from the sender's branch to the
        order's branch, as on the old site. Cash on delivery (the "Накладений платіж" term) goes as Nova Poshta's
        "payment control" for the order's total. Without a key there is nothing to send: a fixed price, no number."""
        if not self.sudo().np_api_key:
            return [{"exact_price": self.fixed_price, "tracking_number": False} for _picking in pickings]
        api, sender = self._np_api(), self.sudo()
        results = []
        for picking in pickings:
            order = picking.sale_id
            if not order:
                raise UserError(self.env._("ТТН Нової Пошти створюється лише для доставки замовлення."))
            city_ref = order._np_city_ref()  # a clear error when the branch or the courier address is missing
            partner = picking.partner_id
            first, _space, last = (partner.name or "").strip().partition(" ")
            phone = _phone(partner.phone)
            recipient = api.call(
                "Counterparty",
                "save",
                {
                    "FirstName": first,
                    "MiddleName": "",
                    "LastName": last or first,
                    "Phone": phone,
                    "Email": "",
                    "CounterpartyType": "PrivatePerson",
                    "CounterpartyProperty": "Recipient",
                    "CityRef": city_ref,
                },
            )[0]
            contacts = (recipient.get("ContactPerson") or {}).get("data") or []
            if not recipient.get("Ref") or not contacts:
                raise UserError(self.env._("Нова Пошта не повернула отримувача чи його контактну особу."))
            # To the door the recipient's address is saved first, and the waybill points to it instead of a branch.
            address = (
                self._np_door_address(api, order, recipient["Ref"]) if self._np_is_door() else order.np_warehouse_id.ref
            )
            declared = order.amount_total
            properties = {
                "PayerType": sender.np_payer or "Recipient",
                "PaymentMethod": "Cash",
                "DateTime": fields.Date.context_today(self).strftime("%d.%m.%Y"),
                "CargoType": "Cargo",
                "ServiceType": self._np_service_type(),
                "Description": sender.np_cargo_description or "Одяг",
                "Cost": _number(declared),
                "SeatsAmount": "1",
                "Weight": _number(max(picking.shipping_weight or picking.weight, MIN_WEIGHT_KG)),
                "InfoRegClientBarcodes": order.name,
                "Sender": sender.np_sender_ref,
                "ContactSender": sender.np_contact_ref,
                "SendersPhone": sender.np_sender_phone,
                "CitySender": sender.np_sender_city_ref,
                "SenderAddress": sender.np_sender_warehouse_ref,
                "Recipient": recipient["Ref"],
                "ContactRecipient": contacts[0].get("Ref"),
                "RecipientsPhone": phone,
                "CityRecipient": city_ref,
                "RecipientAddress": address,
            }
            if order.payment_term_id == self.env.ref("newerp_base.payment_term_cod"):
                properties["AfterpaymentOnGoodsCost"] = _number(declared)
            document = api.call("InternetDocument", "save", properties)[0]
            number = str(document.get("IntDocNumber") or "")
            if not number:
                raise UserError(self.env._("Нова Пошта не повернула номер ТТН."))
            picking.np_document_ref = document.get("Ref") or number
            self._np_attach_label(api, picking, number)
            results.append({"exact_price": float(document.get("CostOnSite") or 0), "tracking_number": number})
        return results

    def _np_is_door(self):
        return self.np_warehouse_kind == "door"

    def _np_service_type(self):
        return "WarehouseDoors" if self._np_is_door() else "WarehouseWarehouse"

    def _np_door_address(self, api, order, recipient_ref):
        """The street by its name in the order's city (Address.getStreet), then the recipient's address
        (Address.save). A street that is not found, or not found exactly once, stops with a clear message."""
        street = order.np_street.strip()
        found = api.call("Address", "getStreet", {"CityRef": order.np_city_id.ref, "FindByString": street})
        exact = [s for s in found if str(s.get("Description") or "").casefold() == street.casefold()]
        matches = exact or found
        if len(matches) != 1:
            raise UserError(
                self.env._(
                    "Вулицю «%(street)s» у місті %(city)s знайдено %(count)s раз(и): уточніть назву.",
                    street=street,
                    city=order.np_city_id.name,
                    count=len(matches),
                )
            )
        address = api.call(
            "Address",
            "save",
            {
                "CounterpartyRef": recipient_ref,
                "StreetRef": matches[0].get("Ref"),
                "BuildingNumber": order.np_building.strip(),
                "Flat": (order.np_flat or "").strip(),
                "Note": "",
            },
        )
        if not address or not address[0].get("Ref"):
            raise UserError(self.env._("Нова Пошта не зберегла адресу отримувача."))
        return address[0]["Ref"]

    def _np_attach_label(self, api, picking, number):
        pdf = api.label(picking.np_document_ref)
        if pdf is None:
            picking.message_post(body=self.env._("Етикетку ТТН %(number)s Нова Пошта не віддала.", number=number))
            return
        label = self.env["ir.attachment"].create(
            {
                "name": f"ТТН {number}.pdf",
                "raw": pdf,
                "mimetype": "application/pdf",
                "res_model": "stock.picking",
                "res_id": picking.id,
            }
        )
        picking.message_post(body=self.env._("Етикетка ТТН %(number)s.", number=number), attachment_ids=label.ids)

    def novaposhta_cancel_shipment(self, pickings):
        api = self._np_api()
        for picking in pickings:
            api.call(
                "InternetDocument",
                "delete",
                {"DocumentRefs": [picking.np_document_ref or picking.carrier_tracking_ref]},
            )
            picking.write({"np_document_ref": False, "np_status": False, "np_status_code": 0, "np_reminded": False})

    def novaposhta_get_tracking_link(self, picking):
        return f"https://novaposhta.ua/tracking/?cargo_number={picking.carrier_tracking_ref}"


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
