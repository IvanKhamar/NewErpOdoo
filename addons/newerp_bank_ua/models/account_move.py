from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def _post(self, soft=True):
        """A payment often comes before the invoice: when an order's invoice is posted, its bank payments linked
        already are reconciled with it."""
        posted = super()._post(soft=soft)
        invoices = posted.filtered(lambda move: move.move_type == "out_invoice")
        if invoices:
            orders = invoices.line_ids.sale_line_ids.order_id
            lines = (
                self.env["account.bank.statement.line"]
                .sudo()
                .search([("newerp_sale_order_id", "in", orders.ids), ("is_reconciled", "=", False)])
            )
            lines._newerp_reconcile_invoices()
        return posted
