# NewErpOdoo

The ERP of an online clothing shop (Vidro) on **Odoo 19 Community**. The same business is also built as a standalone
application in [.NET](https://github.com/IvanKhamar/NewErp), [Java](https://github.com/IvanKhamar/NewErpJava) and
[Python](https://github.com/IvanKhamar/NewErpPython); here it is done the Odoo way. The standard apps (Sales,
Inventory, Manufacturing, Purchase, Invoicing, Contacts) are set up, and our own addons add only what Odoo lacks:
the link to the OpenCart storefront and the Ukrainian services (Nova Poshta, Checkbox, PrivatBank and monobank,
SMSClub). Only invented data is used.

## Addons

| Addon | What it does |
|---|---|
| `newerp_base` | Installs the apps NewErp builds on; sets the company to Ukraine, the Ukrainian chart of accounts and the hryvnia; the roles Менеджер, Комірник, Адміністратор; sizes and colours as variants, order sources and tags, payment terms, delivery methods, the Kyiv warehouse |

Which features of the other versions standard Odoo already covers, and which our addons add, is in the table of
[docs/plan.md](docs/plan.md).

What comes next is in [docs/plan.md](docs/plan.md).

## Run it (Windows, macOS or Linux with Docker)

1. Copy `.env.example` to `.env` and put your own password there (`.env` is not committed).
2. Create the database with the addons and the Ukrainian language:

   ```
   docker compose run --rm odoo odoo -d newerp -i newerp_base --load-language=uk_UA --stop-after-init
   ```

3. Start Odoo and open http://localhost:8069 (it listens only on 127.0.0.1):

   ```
   docker compose up -d
   ```

4. Log in as `admin` / `admin` and change the password at once (avatar → My Preferences → Security).

The database manager page is off (`list_db = False` in `config/odoo.conf`): databases are made from the command line.

## Tests and checks

```
docker compose run --rm odoo bash /mnt/tools/run_tests.sh               # every addon, in a new database
docker compose run --rm odoo bash /mnt/tools/run_tests.sh newerp_base   # one addon
uvx pre-commit run --all-files                                          # ruff, pylint-odoo (OCA checks), XML/YAML
```

`tools/run_tests.sh` installs the addons into a new database, runs their tests, drops the database and fails when a
test fails or nothing ran. CI on GitHub runs the same three jobs (lint, tests, gitleaks) on every push and pull request.

## Development

- Python changes: `docker compose restart odoo`; when models, fields or data change, also
  `docker compose run --rm odoo odoo -d newerp -u <addon> --stop-after-init`.
- XML views reload without a restart (`--dev=xml`).

## License

LGPL-3, as most Odoo addons.
