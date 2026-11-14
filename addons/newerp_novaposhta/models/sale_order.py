from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    np_warehouse_kind = fields.Selection(related="carrier_id.np_warehouse_kind")
    np_warehouse_id = fields.Many2one(
        "newerp.np.warehouse",
        "Відділення Нової Пошти",
        domain="[('working', '=', True), ('kind', '=', np_warehouse_kind)]",
        help="Куди їде посилка: відділення чи поштомат, за видом обраного способу доставки.",
    )
