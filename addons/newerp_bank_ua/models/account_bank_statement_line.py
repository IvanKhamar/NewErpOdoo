from datetime import datetime, time, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .bank_matching import Candidate, confident_match, rank

CANDIDATE_DAYS = 60  # orders up to this many days before the payment
AUTO_MATCH_DAYS = 31  # the button "Підібрати автоматично" looks this far back
MATCHING_GROUP = "account.group_account_invoice"  # the NewErp manager has it


class AccountBankStatementLine(models.Model):
    """A bank payment and the order it belongs to. Statement lines are the accounting's own, so linking writes as
    the superuser after checking that the user may do it (managers only read statement lines in Odoo)."""

    _inherit = "account.bank.statement.line"

    newerp_bank_ref = fields.Char("Id платежу в банку", copy=False, readonly=True)
    newerp_bank_time = fields.Char("Час", readonly=True)
    newerp_sale_order_id = fields.Many2one(
        "sale.order", "Замовлення", copy=False, readonly=True, index="btree_not_null", ondelete="set null"
    )
    newerp_hidden = fields.Boolean(
        "Не замовлення", copy=False, readonly=True, help="Сховано зі списку платежів для підбору замовлення."
    )

    _newerp_bank_ref_unique = models.UniqueIndex(
        "(journal_id, newerp_bank_ref) WHERE newerp_bank_ref IS NOT NULL", "This bank payment is imported already."
    )

    # ── Matching ──

    def _newerp_text(self):
        return f"{self.payment_ref or ''} {self.partner_name or ''}"

    def _newerp_can_match(self):
        """Incoming, not linked, not hidden, and not a LiqPay payout (LiqPay pays out many orders at once)."""
        return (
            self.amount > 0
            and not self.newerp_sale_order_id
            and not self.newerp_hidden
            and "liqpay" not in self._newerp_text().casefold()
        )

    @api.model
    def _newerp_candidate_orders(self, date_from, date_to):
        """Orders that payments of these days may belong to: from CANDIDATE_DAYS before to a day after."""
        start, end = _window(date_from, date_to)
        return (
            self.env["sale.order"]
            .sudo()
            .search([("state", "!=", "cancel"), ("date_order", ">=", start), ("date_order", "<", end)])
        )

    def _newerp_rank(self, orders, any_date=False):
        """The orders ranked for this payment: only those of its own window, unless a person searched for them."""
        self.ensure_one()
        start, end = _window(self.date, self.date)
        candidates = [
            _candidate(order, self)
            for order in orders
            if order.state != "cancel" and (any_date or start <= order.date_order < end)
        ]
        return rank(self._newerp_text(), self.amount, candidates)

    def _newerp_auto_match(self):
        """Links each payment that exactly one order fits confidently. Linked at once, so the next payment of the
        same run sees that order as paid. Returns the linked lines."""
        lines = self.filtered(lambda line: line._newerp_can_match())
        if not lines:
            return self.browse()
        orders = self._newerp_candidate_orders(min(lines.mapped("date")), max(lines.mapped("date")))
        linked = self.browse()
        for line in lines.sorted(lambda line: (line.date, line.newerp_bank_time or "", line.id)):
            match = confident_match(line._newerp_rank(orders))
            if match:
                line._newerp_link(orders.browse(match.key))
                linked |= line
        return linked

    def _newerp_link(self, order):
        """Links the payment to the order: the payer becomes the order's customer, the tag "Перевірити оплату"
        goes, and the order's chatter keeps a note."""
        self.ensure_one()
        self.sudo().write({"newerp_sale_order_id": order.id, "partner_id": order.partner_id.commercial_partner_id.id})
        self.sudo()._newerp_reconcile_invoices()
        order = order.sudo()
        check_payment = self.env.ref("newerp_base.tag_check_payment", raise_if_not_found=False)
        if check_payment and check_payment in order.tag_ids:
            order.tag_ids = [fields.Command.unlink(check_payment.id)]
        order.message_post(
            body=self.env._(
                "Прив'язано банківську оплату %(amount)s від %(date)s: %(purpose)s",
                amount=f"{self.amount:.2f}",
                date=fields.Date.to_string(self.date),
                purpose=self.payment_ref or "",
            )
        )

    # ── Accounting ──

    def _newerp_open_receivables(self):
        """The unpaid receivable lines of the linked order's posted customer invoices."""
        invoices = self.newerp_sale_order_id.invoice_ids.filtered(
            lambda move: move.state == "posted" and move.move_type == "out_invoice"
        )
        return invoices.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable" and not line.reconciled
        )

    def _newerp_reconcile_invoices(self):
        """What Odoo's Enterprise reconciliation screen does for a payment of an invoice: the line's suspense item
        becomes the customer's receivable and is reconciled with the invoices. More money than the invoices ask
        stays on the receivable as the customer's credit, which Odoo offers on the next invoice. A line an
        accountant already worked on (no suspense item, or other items) is left as it is."""
        for line in self.filtered(lambda line: line.newerp_sale_order_id and line.amount > 0):
            receivables = line._newerp_open_receivables()
            _liquidity, suspense, others = line._seek_for_lines()
            if not receivables or len(suspense) != 1 or others:
                continue
            account = receivables[0].account_id
            line.with_context(skip_readonly_check=True).write(
                {
                    "line_ids": [
                        fields.Command.update(
                            suspense.id,
                            {"account_id": account.id, "partner_id": receivables[0].partner_id.id},
                        )
                    ]
                }
            )
            (suspense + receivables.filtered(lambda item, account=account: item.account_id == account)).reconcile()

    def _newerp_undo_reconciliation(self):
        """Back to the suspense account, but only for lines reconciled with the linked order's own invoices."""
        for line in self.filtered("newerp_sale_order_id"):
            invoices = line.newerp_sale_order_id.invoice_ids
            matched = line.line_ids.matched_debit_ids.debit_move_id | line.line_ids.matched_credit_ids.credit_move_id
            if matched and matched.move_id <= invoices:
                line.action_undo_reconciliation()

    def _newerp_check_access(self):
        if not self.env.user.has_group(MATCHING_GROUP):
            raise AccessError(self.env._("Прив'язувати оплати до замовлень може лише менеджер."))

    # ── Buttons ──

    def action_newerp_find_order(self):
        self.ensure_one()
        self._newerp_check_access()
        if self.amount <= 0:
            raise UserError(self.env._("До замовлення прив'язуються лише вхідні платежі."))
        if self.newerp_sale_order_id:
            raise UserError(self.env._("Платіж уже прив'язано: спершу відв'яжіть його."))
        wizard = self.env["newerp.bank.match.wizard"].create({"statement_line_id": self.id})
        wizard._newerp_fill()
        return wizard._newerp_reopen()

    def action_newerp_unlink_order(self):
        self._newerp_check_access()
        for line in self.filtered("newerp_sale_order_id"):
            line.newerp_sale_order_id.sudo().message_post(
                body=self.env._(
                    "Банківську оплату %(amount)s від %(date)s відв'язано.",
                    amount=f"{line.amount:.2f}",
                    date=fields.Date.to_string(line.date),
                )
            )
            line.sudo()._newerp_undo_reconciliation()
            line.sudo().newerp_sale_order_id = False

    def action_newerp_hide(self):
        self._newerp_check_access()
        self.sudo().newerp_hidden = True

    def action_newerp_show(self):
        self._newerp_check_access()
        self.sudo().newerp_hidden = False

    @api.model
    def action_newerp_auto_match(self):
        """The button "Підібрати автоматично": payments of the last days still without an order, for example when
        the orders came after the payments."""
        self._newerp_check_access()
        today = fields.Date.context_today(self)
        lines = self.sudo().search(
            [
                ("date", ">=", today - timedelta(days=AUTO_MATCH_DAYS)),
                ("amount", ">", 0),
                ("newerp_sale_order_id", "=", False),
                ("newerp_hidden", "=", False),
            ]
        )
        linked = lines._newerp_auto_match()
        message = self.env._(
            "Перевірено платежів: %(checked)s, прив'язано: %(linked)s.", checked=len(lines), linked=len(linked)
        )
        return notification(message)

    @api.model
    def action_newerp_open_import(self):
        self._newerp_check_access()
        return self.env["account.journal"].action_newerp_import_statement()


def _window(date_from, date_to):
    return (
        datetime.combine(date_from - timedelta(days=CANDIDATE_DAYS), time.min),
        datetime.combine(date_to + timedelta(days=2), time.min),
    )


def _candidate(order, line):
    others = order.newerp_bank_line_ids - line
    advance = 0.0
    if order.require_payment and 0 < order.prepayment_percent < 1:
        advance = order.amount_total * order.prepayment_percent
    return Candidate(
        key=order.id,
        numbers=frozenset(order._newerp_reference_numbers()),
        customer=order.partner_id.name or "",
        phone=order.partner_id.phone or "",
        total=order.amount_total,
        advance=advance,
        paid=sum(others.mapped("amount")),
        linked=bool(others),
        date=order.date_order,
    )


def notification(message, kind="success"):
    return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {"message": message, "type": kind, "sticky": False},
    }
