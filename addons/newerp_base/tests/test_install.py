from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestInstall(TransactionCase):
    """newerp_base installs the apps NewErp builds on and sets the company up for Ukraine."""

    def test_the_apps_newerp_builds_on_are_installed(self):
        names = ["sale_management", "stock", "mrp", "purchase", "contacts", "account", "l10n_ua"]
        modules = self.env["ir.module.module"].search([("name", "in", names)])
        self.assertEqual(sorted(modules.mapped("name")), sorted(names))
        self.assertEqual(set(modules.mapped("state")), {"installed"})

    def test_the_company_works_in_ukraine_and_in_hryvnias(self):
        company = self.env.ref("base.main_company")
        self.assertEqual(company.country_id, self.env.ref("base.ua"))
        self.assertEqual(company.chart_template, "ua_psbo")
        self.assertEqual(company.currency_id.name, "UAH")
