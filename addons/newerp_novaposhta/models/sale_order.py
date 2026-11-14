from odoo import fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    """Where the parcel goes: a branch or locker, or for the courier a city, street, house and flat."""

    _inherit = "sale.order"

    np_warehouse_kind = fields.Selection(related="carrier_id.np_warehouse_kind")
    np_warehouse_id = fields.Many2one(
        "newerp.np.warehouse",
        "Відділення Нової Пошти",
        domain="[('working', '=', True), ('kind', '=', np_warehouse_kind)]",
        help="Куди їде посилка: відділення чи поштомат, за видом обраного способу доставки.",
    )
    np_city_id = fields.Many2one("newerp.np.city", "Місто (кур'єр)")
    np_street = fields.Char("Вулиця", help="Як у Нової Пошти, без «вул.»: Хрещатик.")
    np_building = fields.Char("Будинок")
    np_flat = fields.Char("Квартира")

    def _np_city_ref(self):
        """The recipient's city: the courier's city, or the branch's."""
        self.ensure_one()
        if self.np_warehouse_kind == "door":
            if not (self.np_city_id and (self.np_street or "").strip() and (self.np_building or "").strip()):
                raise UserError(self.env._("Для кур'єра вкажіть у замовленні місто, вулицю й будинок."))
            return self.np_city_id.ref
        if not self.np_warehouse_id:
            raise UserError(self.env._("Оберіть у замовленні відділення Нової Пошти."))
        return self.np_warehouse_id.city_ref
