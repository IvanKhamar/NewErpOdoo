import re

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _newerp_reference_numbers(self):
        """The numbers a customer may write in a payment's purpose for this order: here the digits of its name
        (S00042 → 42). Addons add their own, as newerp_opencart adds the shop's order number."""
        self.ensure_one()
        digits = re.sub(r"\D", "", self.name or "")
        return {int(digits)} if digits else set()

    @api.model
    def _newerp_search_domain(self, text):
        """Orders a person looks for by the order's name, the customer's name or phone. Addons widen it."""
        return [
            "|",
            "|",
            ("name", "ilike", text),
            ("partner_id.name", "ilike", text),
            ("partner_id.phone", "ilike", text),
        ]
