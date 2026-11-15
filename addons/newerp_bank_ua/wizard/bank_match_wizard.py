from odoo import fields, models

from ..models.bank_matching import describe

SUGGESTION_LIMIT = 10
SEARCH_LIMIT = 50


class BankMatchWizard(models.TransientModel):
    """The orders a payment may belong to, best first, with the reasons; a search widens the list."""

    _name = "newerp.bank.match.wizard"
    _description = "NewErp: find the order of a bank payment"

    statement_line_id = fields.Many2one("account.bank.statement.line", required=True, ondelete="cascade")
    amount = fields.Monetary(related="statement_line_id.amount")
    currency_id = fields.Many2one(related="statement_line_id.currency_id")
    payment_ref = fields.Char(related="statement_line_id.payment_ref")
    partner_name = fields.Char(related="statement_line_id.partner_name")
    search_text = fields.Char("Пошук", help="Номер замовлення, ім'я чи телефон покупця.")
    candidate_ids = fields.One2many("newerp.bank.match.candidate", "wizard_id", "Замовлення")

    def _newerp_fill(self):
        self.ensure_one()
        line = self.statement_line_id.sudo()
        text = (self.search_text or "").strip()
        if text:  # what the person looks for, of any date, ranked the same way
            Order = self.env["sale.order"].sudo()
            orders = Order.search([("state", "!=", "cancel"), *Order._newerp_search_domain(text)], limit=SEARCH_LIMIT)
            ranked = line._newerp_rank(orders, any_date=True)
        else:  # orders of the payment's days that fit it at least a little
            orders = line._newerp_candidate_orders(line.date, line.date)
            ranked = [scored for scored in line._newerp_rank(orders) if scored.score > 0]
        self.candidate_ids = [fields.Command.clear()] + [
            fields.Command.create(
                {"order_id": scored.candidate.key, "score": scored.score, "reasons": describe(scored.reasons)}
            )
            for scored in ranked[: SEARCH_LIMIT if text else SUGGESTION_LIMIT]
        ]

    def _newerp_reopen(self):
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Замовлення для платежу"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_search(self):
        self._newerp_fill()
        return self._newerp_reopen()


class BankMatchCandidate(models.TransientModel):
    _name = "newerp.bank.match.candidate"
    _description = "NewErp: an order a bank payment may belong to"
    _order = "score desc, id"

    wizard_id = fields.Many2one("newerp.bank.match.wizard", required=True, ondelete="cascade")
    order_id = fields.Many2one("sale.order", "Замовлення", required=True, ondelete="cascade")
    partner_id = fields.Many2one(related="order_id.partner_id", string="Покупець")
    date_order = fields.Datetime(related="order_id.date_order")
    amount_total = fields.Monetary(related="order_id.amount_total")
    currency_id = fields.Many2one(related="order_id.currency_id")
    state = fields.Selection(related="order_id.state")
    score = fields.Integer("Бали")
    reasons = fields.Char("Чому")

    def action_link(self):
        self.ensure_one()
        line = self.wizard_id.statement_line_id
        line._newerp_check_access()
        line._newerp_link(self.order_id)
        return {"type": "ir.actions.act_window_close"}
