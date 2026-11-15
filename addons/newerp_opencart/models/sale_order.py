from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    opencart_id = fields.Integer("OpenCart order", index=True, copy=False, readonly=True)

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id > 0", "This OpenCart order is imported already."
    )

    def _newerp_reference_numbers(self):
        """Customers of the shop write the OpenCart order number in the purpose of a payment."""
        numbers = super()._newerp_reference_numbers()
        return numbers | {self.opencart_id} if self.opencart_id else numbers

    @api.model
    def _newerp_search_domain(self, text):
        domain = super()._newerp_search_domain(text)
        return ["|", ("opencart_id", "=", int(text)), *domain] if text.strip().isdigit() else domain
