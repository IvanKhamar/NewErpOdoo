{
    "name": "NewErp: OpenCart connector",
    "summary": "Import categories, products with sizes, customers and orders from an OpenCart shop; stock back to it",
    "version": "19.0.1.2.0",
    "category": "Sales",
    "author": "Ivan Khamar",
    "website": "https://github.com/IvanKhamar/NewErpOdoo",
    "license": "LGPL-3",
    "depends": ["newerp_base"],
    "external_dependencies": {"python": ["pymysql"]},
    "data": [
        "security/ir.model.access.csv",
        "views/opencart_run_views.xml",
        "views/res_config_settings_views.xml",
        "data/ir_cron.xml",
    ],
}
