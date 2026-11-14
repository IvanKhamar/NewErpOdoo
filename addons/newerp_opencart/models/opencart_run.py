from odoo import fields, models


class OpenCartRun(models.Model):
    """One import or stock push: when, what, how many records, and the error if it failed."""

    _name = "newerp.opencart.run"
    _description = "OpenCart run"
    _order = "id desc"

    kind = fields.Selection(
        [("catalog", "Каталог"), ("orders", "Замовлення"), ("stock", "Залишки")], required=True, readonly=True
    )
    state = fields.Selection([("done", "Виконано"), ("failed", "Помилка")], required=True, readonly=True)
    created = fields.Integer(readonly=True)
    updated = fields.Integer(readonly=True)
    message = fields.Text(readonly=True)
