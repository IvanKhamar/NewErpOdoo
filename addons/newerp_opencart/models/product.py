from odoo import fields, models

# The OpenCart ids keep each record linked to its row in the shop, so importing again updates instead of doubling.
# A partial unique index: many records have no OpenCart id, and each one that has it, has it once.


class ProductCategory(models.Model):
    _inherit = "product.category"

    opencart_id = fields.Integer("OpenCart category", index=True, copy=False, readonly=True)

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id IS NOT NULL", "This OpenCart category is linked already."
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    opencart_id = fields.Integer("OpenCart product", index=True, copy=False, readonly=True)

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id IS NOT NULL", "This OpenCart product is linked already."
    )


class ProductProduct(models.Model):
    _inherit = "product.product"

    opencart_id = fields.Integer(
        "OpenCart size row",
        index=True,
        copy=False,
        readonly=True,
        help="product_option_value_id of the size row the storefront counts stock on.",
    )

    _opencart_id_unique = models.UniqueIndex(
        "(opencart_id) WHERE opencart_id IS NOT NULL", "This OpenCart size row is linked already."
    )
