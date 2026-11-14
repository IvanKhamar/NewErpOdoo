from unittest.mock import patch

from odoo.addons.newerp_novaposhta.models.novaposhta_api import NovaPoshtaApi
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import WAREHOUSES, fake_novaposhta, pages

RECIPIENT = [{"Ref": "recipient-ref", "ContactPerson": {"data": [{"Ref": "contact-ref"}]}}]
DOCUMENT = [{"Ref": "doc-ref", "IntDocNumber": "20450123456790", "CostOnSite": 120}]
STREETS = [
    {"Ref": "street-1", "Description": "Хрещатик", "StreetsType": "вул."},
    {"Ref": "street-2", "Description": "Хрещатий провулок", "StreetsType": "пров."},
]


@tagged("post_install", "-at_install")
class TestDoor(TransactionCase):
    """Courier to the door (NewErpPython item 23): the city from the branches list, the street by its name (3c)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env.ref("newerp_novaposhta.carrier_np_door")
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
        cls.kyiv = cls.env["newerp.np.city"].search([("ref", "=", "city-kyiv")])
        cls.customer = cls.env["res.partner"].create({"name": "Олена Петренко", "phone": "0671112233"})
        cls.dress = cls.env["product.product"].create({"name": "Сукня", "list_price": 1500, "is_storable": True})

    def setUp(self):
        super().setUp()
        patcher = patch.object(NovaPoshtaApi, "label", lambda _self, _ref: b"%PDF")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _order(self, street="Хрещатик", building="1"):
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "carrier_id": self.carrier.id,
                "np_city_id": self.kyiv.id,
                "np_street": street,
                "np_building": building,
                "np_flat": "12",
                "order_line": [(0, 0, {"product_id": self.dress.id, "product_uom_qty": 1, "tax_ids": [(6, 0, [])]})],
            }
        )

    def _ship(self, order):
        order.action_confirm()
        picking = order.picking_ids
        picking.move_ids.quantity = 1
        picking.move_ids.picked = True
        answers = {
            ("Counterparty", "save"): RECIPIENT,
            ("Address", "getStreet"): STREETS,
            ("Address", "save"): [{"Ref": "address-ref"}],
            ("InternetDocument", "save"): DOCUMENT,
        }
        with fake_novaposhta(answers) as np:
            picking.button_validate()
        return picking, np

    def test_cities_come_with_the_branches(self):
        self.assertEqual(self.env["newerp.np.city"].search([]).mapped("name"), ["Київ", "Львів"])

    def test_the_door_rate_asks_for_warehouse_to_doors_in_the_city(self):
        with fake_novaposhta({("InternetDocument", "getDocumentPrice"): [{"Cost": 120}]}) as np:
            rate = self.carrier.rate_shipment(self._order())
        self.assertEqual((rate["success"], rate["price"]), (True, 120))
        [sent] = np.sent("InternetDocument", "getDocumentPrice")
        self.assertEqual((sent["CityRecipient"], sent["ServiceType"]), ("city-kyiv", "WarehouseDoors"))

    def test_the_door_waybill_saves_the_address_first(self):
        picking, np = self._ship(self._order())
        self.assertEqual(picking.carrier_tracking_ref, "20450123456790")
        self.assertEqual(np.sent("Address", "getStreet"), [{"CityRef": "city-kyiv", "FindByString": "Хрещатик"}])
        [address] = np.sent("Address", "save")
        self.assertEqual(
            (address["CounterpartyRef"], address["StreetRef"], address["BuildingNumber"], address["Flat"]),
            ("recipient-ref", "street-1", "1", "12"),
        )
        [document] = np.sent("InternetDocument", "save")
        self.assertEqual((document["ServiceType"], document["RecipientAddress"]), ("WarehouseDoors", "address-ref"))

    def test_an_unclear_street_or_a_missing_house_stops_with_a_message(self):
        with self.assertRaises(UserError) as unclear:
            self._ship(self._order(street="Хрещ"))  # matches two streets, neither exactly
        self.assertIn("2", str(unclear.exception))
        with fake_novaposhta({}) as np:
            rate = self.carrier.rate_shipment(self._order(building=""))
        self.assertFalse(rate["success"])
        self.assertIn("будинок", rate["error_message"])
        self.assertEqual(np.calls, [])  # nothing is asked while the address is incomplete
