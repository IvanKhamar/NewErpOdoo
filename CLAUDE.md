# NewErpOdoo

NewErp on Odoo 19 Community: the fourth version of the ERP for the Vidro shop, after .NET
(`F:\PROJECTS\NewErp\NewErp`), Java (`F:\PROJECTS\NewErpJava\NewErpJava`) and Python
(`F:\PROJECTS\NewErpPython\NewErpPython`). A learning project and a portfolio piece for an Odoo developer job.

## The idea

Odoo already has sales, stock, manufacturing, purchasing, invoicing and contacts, so this is **not a 1:1 port**: the
standard apps are set up, and our own addons add only what Odoo lacks (the OpenCart shop, Nova Poshta, Checkbox,
Ukrainian banks, SMSClub, the sewing workflow). NewErpPython is the specification: its `docs/plan.md`, rules, texts and
tests tell each addon what to do. Before writing an addon, check what standard Odoo already does, and say so in the PR.
The phases and their status are in `docs/plan.md`.

## Working with the user

- The user learned C#/.NET, then Python; Odoo is new. Explain each new Odoo concept in 1–2 sentences and map it to
  what they know (a model is like an EF entity with its service; `_inherit` is like a partial class plus override;
  a view is XML the client renders; a record rule is a row filter; a cron is a scheduled task).
- Keep the code plain and idiomatic Odoo: the user must be able to explain it in an interview.
- Where a step needs the user (a key, a decision), lead them through it one step at a time.

## Stack

Odoo 19.0 Community (official `odoo:19.0-<date>` image, pinned in `docker-compose.yml`), PostgreSQL 17, Python 3.12 of
the image. Tooling on the host: Docker Desktop and uv (`uvx pre-commit`). Nothing of Odoo is installed on Windows.

## Structure and code rules

- `addons/newerp_*`: one addon per area, each with `__manifest__.py` (version `19.0.x.y.z`, author "Ivan Khamar",
  license LGPL-3), `README.rst`, `tests/`, and `security/ir.model.access.csv` for every new model.
- Extend standard models with `_inherit`; never copy or patch Odoo's own code.
- Settings an admin changes live in Odoo (`res.config.settings`, `ir.config_parameter`), not in files.
- Data that must not be undone by an upgrade goes in `noupdate="1"`. A record of another module marked noupdate
  (like `base.main_company`) can't be changed from our XML: use a hook (see `newerp_base/hooks.py`).
- Texts for users in Ukrainian, through `_()` / `env._()` so they can be translated; code and comments in English.
- SQL only through the ORM or `SQL()` with parameters; `sudo()` only with a comment why.
- Every model gets access rules; new menus and actions get groups.

## Commands

```
docker compose up -d                                                    # Odoo at http://localhost:8069
docker compose run --rm odoo bash /mnt/tools/run_tests.sh [addon,...]   # tests in a new database (all addons by default)
docker compose run --rm odoo odoo -d newerp -u newerp_base --stop-after-init   # upgrade an addon in the dev database
uvx pre-commit run --all-files                                          # ruff, pylint-odoo, XML/YAML checks
```

Python changes need `docker compose restart odoo` (and `-u <addon>` when models, fields or data change); XML views
reload by themselves (`--dev=xml`).

On this machine, uv and pre-commit need these variables in the Claude sandbox: `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`,
`PRE_COMMIT_HOME` and `VIRTUALENV_OVERRIDE_APP_DATA` pointing to the session scratchpad, and `UV_LINK_MODE=copy`.
Docker commands in Git Bash need `MSYS_NO_PATHCONV=1`, or paths like `/mnt/tools` are rewritten.

## Database and secrets

- Only invented data. The OpenCart data comes from the Docker MySQL of NewErpPython (fake data), through the
  connector addon.
- The database password is only in the git-ignored `.env` (see `.env.example`). The database manager page is off
  (`list_db = False`), so there is no master password. API keys of outside services are entered in Odoo settings and
  stay in the database, never in the repo, tests, logs or the chat; tests use fakes.
- A new database made from the command line has the user `admin` with the password `admin`: change it at once.
  Odoo listens only on 127.0.0.1.

## Git and permissions

- Permissions are in `F:\PROJECTS\CLAUDE.md`: work without asking; docs go straight to `main`, code through a branch
  and a PR. Before a push, run the CI steps locally (`uvx pre-commit run --all-files`, `run_tests.sh`), each exit code
  checked.
- Repository: github.com/IvanKhamar/NewErpOdoo (public), branch `main`.
