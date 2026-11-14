from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    """The connection to the shop's database, in Settings. The values are kept in ir.config_parameter (in the
    database, like the other secrets of Odoo integrations), never in files; the password field is masked."""

    _inherit = "res.config.settings"

    newerp_opencart_host = fields.Char("Хост MySQL", config_parameter="newerp_opencart.host")
    newerp_opencart_port = fields.Integer("Порт", config_parameter="newerp_opencart.port", default=3306)
    newerp_opencart_database = fields.Char("База даних", config_parameter="newerp_opencart.database")
    newerp_opencart_user = fields.Char("Користувач", config_parameter="newerp_opencart.user")
    newerp_opencart_password = fields.Char("Пароль", config_parameter="newerp_opencart.password")
    newerp_opencart_prefix = fields.Char("Префікс таблиць", config_parameter="newerp_opencart.prefix", default="dd_")
    newerp_opencart_language_id = fields.Integer(
        "Мова OpenCart (language_id)", config_parameter="newerp_opencart.language_id", default=3
    )

    def action_newerp_opencart_check(self):
        self.execute()  # save what was typed before using it
        self.env["newerp.opencart.sync"].check_connection()
        return _notification(self.env._("З'єднання з OpenCart працює."))

    def action_newerp_opencart_import_catalog(self):
        self.execute()
        run = self.env["newerp.opencart.sync"].import_catalog()
        return _notification(
            self.env._(
                "Товари імпортовано: нових %(created)s, оновлених %(updated)s.",
                created=run.created,
                updated=run.updated,
            )
        )

    def action_newerp_opencart_import_orders(self):
        self.execute()
        run = self.env["newerp.opencart.sync"].import_orders()
        message = self.env._(
            "Замовлення імпортовано: нових %(created)s, оновлених %(updated)s.",
            created=run.created,
            updated=run.updated,
        )
        return _notification(f"{message} {run.message}".strip())


def _notification(message):
    return {
        "type": "ir.actions.client",
        "tag": "display_notification",
        "params": {"message": message, "type": "success", "sticky": False},
    }
