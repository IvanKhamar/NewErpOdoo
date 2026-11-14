from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    opencart_id = fields.Integer("OpenCart order", index=True, copy=False, readonly=True)

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id > 0", "This OpenCart order is imported already."
    )
