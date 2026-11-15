from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    newerp_bank_line_ids = fields.One2many(
        "account.bank.statement.line", "newerp_sale_order_id", "Оплати з банку", groups="account.group_account_invoice"
    )
    newerp_bank_paid = fields.Monetary(
        "Оплачено з банку", compute="_compute_newerp_bank_paid", groups="account.group_account_invoice"
    )

    @api.depends("newerp_bank_line_ids.amount")
    def _compute_newerp_bank_paid(self):
        for order in self:
            order.newerp_bank_paid = sum(order.newerp_bank_line_ids.mapped("amount"))
