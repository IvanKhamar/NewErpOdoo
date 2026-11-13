{
    "name": "NewErp: base",
    "summary": "Shared settings of NewErp on Odoo: the standard apps it builds on, Ukraine and the hryvnia",
    "version": "19.0.1.0.0",
    "category": "Hidden",
    "author": "Ivan Khamar",
    "website": "https://github.com/IvanKhamar/NewErpOdoo",
    "license": "LGPL-3",
    "depends": ["sale_management", "stock", "mrp", "purchase", "contacts", "account", "l10n_ua"],
    "post_init_hook": "post_init_hook",
}
