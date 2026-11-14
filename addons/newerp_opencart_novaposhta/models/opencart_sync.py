from odoo import models
from odoo.addons.newerp_novaposhta.models.delivery_carrier import branch_number


class OpenCartSync(models.AbstractModel):
    """A bridge: the OpenCart import knows nothing of Nova Poshta, and Nova Poshta nothing of OpenCart. This addon
    installs itself when both are there (auto_install) and adds the branch to the order values the import builds."""

    _inherit = "newerp.opencart.sync"

    def _carrier(self, method):
        """The courier method lives in newerp_novaposhta, so only the bridge can map OpenCart's courier orders."""
        if "кур'єр" in method or "курьер" in method or "courier" in method:
            return self.env.ref("newerp_novaposhta.carrier_np_door")
        return super()._carrier(method)

    def _order_values(self, row):
        values = super()._order_values(row)
        carrier = self.env["delivery.carrier"].browse(values.get("carrier_id"))
        if carrier.delivery_type != "novaposhta":
            return values
        city = (row["shipping_city"] or "").strip()
        if carrier.np_warehouse_kind == "door":
            values["np_city_id"] = self.env["newerp.np.city"].search([("name", "=ilike", city)], limit=1).id or False
        else:
            values["np_warehouse_id"] = self._np_branch(city, row["shipping_address_2"], carrier.np_warehouse_kind).id
        return values

    def _np_branch(self, city, text, kind):
        """OpenCart keeps the branch as text ("Відділення №1: вул. Хрещатик, 1"): the same name in the city first,
        then the same number in the city; a working branch before a closed one. None when unsure."""
        Branch = self.env["newerp.np.warehouse"].with_context(active_test=False)
        in_city = [("city_name", "=ilike", city), ("kind", "=", kind)] if city else [("id", "=", 0)]
        text = (text or "").strip()
        if text:
            found = Branch.search([*in_city, ("name", "=ilike", text)], order="working desc", limit=1)
            if found:
                return found
        number = branch_number(text)
        if number:
            return Branch.search([*in_city, ("number", "=", number)], order="working desc", limit=1)
        return Branch
