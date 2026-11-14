#!/usr/bin/env bash
# Runs the tests of the given addons in a new database and fails when any test fails.
# Odoo 19 exits with 1 when a test fails; older versions exited with 0, so the log is checked as a second lock.
# Usage (from the repo): docker compose run --rm odoo bash /mnt/tools/run_tests.sh [newerp_base,other_addon]
set -uo pipefail

# Without an argument: every addon in the repository.
addons="${1:-$(cd /mnt/extra-addons && ls -d */ | sed "s,/,," | while read -r a; do [ -f "$a/__manifest__.py" ] && echo "$a"; done | paste -sd, -)}"
[ -n "$addons" ] || { echo "run_tests: no addons found" >&2; exit 1; }
db="test_$(date +%s)"
log="$(mktemp)"
tags="$(echo "$addons" | sed -E 's/([^,]+)/\/\1/g')"  # newerp_base,x -> /newerp_base,/x

# The password reaches PostgreSQL through PGPASSWORD (libpq), never on the command line.
export LC_ALL=C.UTF-8  # psql tools would warn about the missing locale
export PGHOST="${HOST:-db}" PGUSER="${USER:-odoo}" PGPASSWORD="${PASSWORD:?the odoo service gets PASSWORD from .env}"

odoo -c /etc/odoo/odoo.conf -d "$db" -i "$addons" --test-enable --test-tags "$tags" --log-level=test --no-http 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
dropdb --if-exists --force "$db" || true

if [ "$status" -ne 0 ]; then
    echo "run_tests: Odoo exited with $status" >&2
    exit "$status"
fi
if grep -qE ' (ERROR|CRITICAL) |^FAIL:|[1-9][0-9]* failed|[1-9][0-9]* error' "$log"; then
    echo "run_tests: the log has failed tests or errors" >&2
    exit 1
fi
if ! grep -qE 'odoo.tests.(stats|result)|tests? (in|when loading)' "$log"; then
    echo "run_tests: no test ran" >&2
    exit 1
fi
echo "run_tests: all tests passed"
