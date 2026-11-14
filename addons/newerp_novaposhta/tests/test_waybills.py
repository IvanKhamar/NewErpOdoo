from datetime import timedelta
from unittest.mock import patch

from odoo import fields
from odoo.addons.newerp_novaposhta.models.novaposhta_api import NovaPoshtaApi
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import WAREHOUSES, fake_novaposhta, pages

RECIPIENT = [{"Ref": "recipient-ref", "ContactPerson": {"data": [{"Ref": "contact-ref"}]}}]
DOCUMENT = [{"Ref": "doc-ref", "IntDocNumber": "20450123456789", "CostOnSite": 85}]
PDF = b"%PDF-1.4 label"


@tagged("post_install", "-at_install")
class TestWaybills(TransactionCase):
    """The waybill when a delivery is validated, its label, cancelling it, and tracking with the reminder (3b)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env.ref("newerp_base.carrier_np_branch")
        cls.carrier.write(
            {
                "np_api_key": "test-np-key",
                "np_sender_city_ref": "city-kyiv",
                "np_sender_ref": "sender-ref",
                "np_contact_ref": "contact-ref",
                "np_sender_phone": "380670000000",
                "np_sender_warehouse_ref": "wh-kyiv-1",
            }
        )
        with fake_novaposhta({("Address", "getWarehouses"): pages(WAREHOUSES)}):
            cls.carrier.action_np_update_warehouses()
        cls.branch = cls.env["newerp.np.warehouse"].search([("ref", "=", "wh-kyiv-1")])
        cls.customer = cls.env["res.partner"].create({"name": "Олена Петренко", "phone": "067 111 22 33"})
        cls.dress = cls.env["product.product"].create(
            {"name": "Сукня", "list_price": 1500, "weight": 0.4, "is_storable": True}
        )
        cls.salesperson = cls.env["res.users"].create(
            {
                "name": "Марта",
                "login": "np-salesperson",
                "group_ids": [(6, 0, [cls.env.ref("newerp_base.group_manager").id])],
            }
        )

    def setUp(self):
        super().setUp()
        patcher = patch.object(NovaPoshtaApi, "label", lambda _self, _ref: PDF)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _delivery(self, term="newerp_base.payment_term_cod", branch=True):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "user_id": self.salesperson.id,
                "carrier_id": self.carrier.id,
                "np_warehouse_id": self.branch.id if branch else False,
                "payment_term_id": self.env.ref(term).id,
                "order_line": [(0, 0, {"product_id": self.dress.id, "product_uom_qty": 2, "tax_ids": [(6, 0, [])]})],
            }
        )
        order.action_confirm()
        picking = order.picking_ids
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True
        return order, picking

    def _validate(self, picking, answers=None):
        answers = {("Counterparty", "save"): RECIPIENT, ("InternetDocument", "save"): DOCUMENT, **(answers or {})}
        with fake_novaposhta(answers) as np:
            picking.button_validate()
        return np

    def test_validating_a_delivery_creates_the_waybill_with_cash_on_delivery(self):
        order, picking = self._delivery()
        np = self._validate(picking)

        self.assertEqual((picking.state, picking.carrier_tracking_ref), ("done", "20450123456789"))
        self.assertEqual((picking.np_document_ref, picking.carrier_price), ("doc-ref", 85))
        [recipient] = np.sent("Counterparty", "save")
        self.assertEqual(
            (recipient["FirstName"], recipient["LastName"], recipient["Phone"]), ("Олена", "Петренко", "380671112233")
        )
        [document] = np.sent("InternetDocument", "save")
        self.assertEqual((document["RecipientAddress"], document["CityRecipient"]), ("wh-kyiv-1", "city-kyiv"))
        self.assertEqual((document["Cost"], document["AfterpaymentOnGoodsCost"]), ("3000", "3000"))
        self.assertEqual((document["Weight"], document["InfoRegClientBarcodes"]), ("0.8", order.name))
        label = self.env["ir.attachment"].search([("res_model", "=", "stock.picking"), ("res_id", "=", picking.id)])
        self.assertEqual((label.name, label.raw), ("ТТН 20450123456789.pdf", PDF))

    def test_a_prepaid_order_has_no_cash_on_delivery(self):
        _order, picking = self._delivery(term="newerp_base.payment_term_prepaid")
        np = self._validate(picking)
        self.assertNotIn("AfterpaymentOnGoodsCost", np.sent("InternetDocument", "save")[0])

    def test_without_a_branch_the_delivery_is_not_validated(self):
        _order, picking = self._delivery(branch=False)
        with self.assertRaises(UserError):
            self._validate(picking)

    def test_cancelling_deletes_the_waybill(self):
        _order, picking = self._delivery()
        self._validate(picking)
        with fake_novaposhta({("InternetDocument", "delete"): [{"Ref": "doc-ref"}]}) as np:
            picking.cancel_shipment()
        self.assertEqual(np.sent("InternetDocument", "delete"), [{"DocumentRefs": ["doc-ref"]}])
        self.assertFalse(picking.carrier_tracking_ref or picking.np_document_ref)

    def test_tracking_keeps_the_status_and_reminds_once_when_the_parcel_waits(self):
        order, picking = self._delivery()
        self._validate(picking)
        tomorrow = fields.Date.context_today(picking) + timedelta(days=1)
        status = {
            "Number": "20450123456789",
            "Status": "Прибув у відділення",
            "StatusCode": "7",
            "ScheduledDeliveryDate": "15-11-2026 13:00:00",
            "DatePayedKeeping": tomorrow.strftime("%Y-%m-%d %H:%M:%S"),
        }
        tracking = {("TrackingDocument", "getStatusDocuments"): [status]}
        for _attempt in range(2):
            with fake_novaposhta(tracking) as np:
                self.env["stock.picking"]._cron_np_track()
        self.assertEqual(np.sent("TrackingDocument", "getStatusDocuments")[0]["Documents"][0]["Phone"], "380671112233")
        self.assertEqual((picking.np_status, picking.np_status_code), ("Прибув у відділення", 7))
        self.assertEqual(picking.np_date_payed_keeping, tomorrow)
        activities = order.activity_ids.filtered(lambda a: a.summary == "Посилка чекає у відділенні")
        self.assertEqual((len(activities), activities.user_id), (1, self.salesperson))

        # Received: a final status, so the next run does not ask about it again.
        with fake_novaposhta(
            {("TrackingDocument", "getStatusDocuments"): [dict(status, StatusCode="9", Status="Отримано")]}
        ):
            self.env["stock.picking"]._cron_np_track()
        with fake_novaposhta(tracking) as np:
            self.env["stock.picking"]._cron_np_track()
        self.assertEqual(np.calls, [])
        self.assertEqual(picking.np_status_code, 9)
