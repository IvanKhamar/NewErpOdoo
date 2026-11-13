UKRAINIAN_CHART = "ua_psbo"  # the Ukrainian chart of accounts of l10n_ua


def post_init_hook(env):
    """Sets the main company up for Ukraine once, on install: the country, the Ukrainian chart of accounts and, with
    the chart, the hryvnia. An admin may change all of this later.

    A chart can only be loaded once every module is loaded. account does it in its _register_hook from a function it
    keeps in registry._auto_install_template (it put the generic chart, in US dollars, there when it was installed,
    because the company had no country yet). Here the Ukrainian chart takes that place. The chart is not changed if
    the company already keeps its books.
    """
    company = env.ref("base.main_company")
    company.country_id = env.ref("base.ua")
    if company.chart_template == UKRAINIAN_CHART or company.root_id._existing_accounting():
        return

    def load_ukrainian_chart(env):
        env["account.chart.template"].try_loading(UKRAINIAN_CHART, env.ref("base.main_company"))

    env.registry._auto_install_template = load_ukrainian_chart
