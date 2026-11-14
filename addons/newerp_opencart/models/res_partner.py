import re

from odoo import api, fields, models


def phone_key(phone):
    """The last 9 digits of a Ukrainian number: "+38 (067) 111-22-33", "0671112233" and "380671112233" match."""
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 9 else False


class ResPartner(models.Model):
    _inherit = "res.partner"

    opencart_id = fields.Integer("OpenCart customer", index=True, copy=False, readonly=True)
    newerp_phone_key = fields.Char(
        compute="_compute_newerp_phone_key",
        store=True,
        index=True,
        help="Last 9 digits of the phone, to find a guest of the shop again however the number was typed.",
    )

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id > 0", "This OpenCart customer is linked already."
    )

    @api.depends("phone")
    def _compute_newerp_phone_key(self):
        for partner in self:
            partner.newerp_phone_key = phone_key(partner.phone)
