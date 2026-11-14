import logging
from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Codes after which a waybill no longer changes: received, refused, returned. Tracking skips them.
FINAL_STATUS_CODES = frozenset({9, 11, 102, 103, 104, 105, 107, 108})
# The parcel waits at the branch: then paid storage counts, and the salesperson is reminded.
WAITING_AT_BRANCH_CODES = frozenset({7, 8})
TRACKING_BATCH = 100  # documents per getStatusDocuments call
DATE_FORMATS = ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y")


class StockPicking(models.Model):
    """The waybill of a delivery and what tracking last said about it."""

    _inherit = "stock.picking"

    np_warehouse_id = fields.Many2one(related="sale_id.np_warehouse_id", string="Відділення Нової Пошти")
    np_document_ref = fields.Char("Ref ТТН", copy=False, readonly=True)
    np_status = fields.Char("Статус ТТН", copy=False, readonly=True)
    np_status_code = fields.Integer("Код статусу ТТН", copy=False, readonly=True)
    np_date_scheduled = fields.Date("Планова доставка", copy=False, readonly=True)
    np_date_payed_keeping = fields.Date("Платне зберігання з", copy=False, readonly=True)
    np_reminded = fields.Boolean(copy=False, readonly=True, help="The salesperson was reminded that it waits.")

    @api.model
    def _cron_np_track(self):
        """Asks Nova Poshta about the waybills that can still change, per carrier account, 100 at a time."""
        pickings = self.search(
            [
                ("carrier_id.delivery_type", "=", "novaposhta"),
                ("carrier_tracking_ref", "!=", False),
                ("state", "=", "done"),
                ("np_status_code", "not in", list(FINAL_STATUS_CODES)),
            ]
        )
        for carrier in pickings.carrier_id:
            if not carrier.sudo().np_api_key:
                continue
            mine = pickings.filtered(lambda p, carrier=carrier: p.carrier_id == carrier)
            for start in range(0, len(mine), TRACKING_BATCH):
                batch = mine[start : start + TRACKING_BATCH]
                try:
                    batch._np_track(carrier._np_api())
                except UserError as error:
                    _logger.warning("Nova Poshta tracking failed for %s: %s", carrier.name, error)

    def _np_track(self, api):
        documents = [{"DocumentNumber": p.carrier_tracking_ref, "Phone": _phone(p.partner_id.phone)} for p in self]
        by_number = {str(item.get("Number") or ""): item for item in api.call(
            "TrackingDocument", "getStatusDocuments", {"Documents": documents}
        )}  # fmt: skip
        for picking in self:
            item = by_number.get(picking.carrier_tracking_ref)
            if item:
                picking._np_apply_tracking(item)

    def _np_apply_tracking(self, item):
        """Like the old site: the delivery changes only when the status code changed."""
        code = int(item.get("StatusCode") or 0) if str(item.get("StatusCode") or "").lstrip("-").isdigit() else 0
        if code and code != self.np_status_code:
            scheduled = _date(item.get("ScheduledDeliveryDate"))
            keeping = _date(item.get("DatePayedKeeping"))
            self.write(
                {
                    "np_status": str(item.get("Status") or "")[:255],
                    "np_status_code": code,
                    "np_date_scheduled": scheduled,
                    "np_date_payed_keeping": keeping,
                }
            )
        self._np_remind_if_waiting()

    def _np_remind_if_waiting(self):
        """The old site's reminder: a parcel waits at the branch and paid storage starts within a day."""
        tomorrow = fields.Date.context_today(self) + timedelta(days=1)
        if (
            self.np_status_code in WAITING_AT_BRANCH_CODES
            and self.np_date_payed_keeping
            and self.np_date_payed_keeping <= tomorrow
            and not self.np_reminded
            and self.sale_id
        ):
            self.sale_id.activity_schedule(
                "mail.mail_activity_data_todo",
                date_deadline=self.np_date_payed_keeping,
                summary=self.env._("Посилка чекає у відділенні"),
                note=self.env._(
                    "ТТН %(number)s чекає у відділенні, платне зберігання з %(date)s. Нагадайте покупцю.",
                    number=self.carrier_tracking_ref,
                    date=self.np_date_payed_keeping.strftime("%d.%m.%Y"),
                ),
                user_id=self.sale_id.user_id.id or self.env.uid,
            )
            self.np_reminded = True


def _date(value):
    text = str(value or "").strip()
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return False


def _phone(phone):
    """Nova Poshta wants 380XXXXXXXXX."""
    digits = "".join(c for c in phone or "" if c.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        digits = "38" + digits
    return digits
