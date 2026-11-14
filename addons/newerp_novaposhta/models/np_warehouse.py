from odoo import fields, models

KINDS = [("branch", "Відділення"), ("locker", "Поштомат")]
CARRIER_KINDS = [*KINDS, ("door", "Кур'єр до дверей")]


class NovaPoshtaCity(models.Model):
    """A city Nova Poshta delivers to, kept from the branches list: the courier needs the city, not a branch."""

    _name = "newerp.np.city"
    _description = "Nova Poshta city"
    _order = "name"

    ref = fields.Char(required=True, index=True, readonly=True)
    name = fields.Char(required=True, index=True, readonly=True)

    _ref_unique = models.Constraint("UNIQUE(ref)", "This Nova Poshta city is in the list already.")

    def _np_store(self, rows):
        """The cities of the branch rows, created or renamed by their Ref."""
        names = {str(r.get("CityRef")): str(r.get("CityDescription") or "") for r in rows if r.get("CityRef")}
        existing = {c.ref: c for c in self.search([("ref", "in", list(names))])}
        self.create([{"ref": ref, "name": name} for ref, name in names.items() if ref not in existing and name])
        for ref, city in existing.items():
            if names[ref] and city.name != names[ref]:
                city.name = names[ref]


class NovaPoshtaWarehouse(models.Model):
    """A Nova Poshta branch or parcel locker, from Address.getWarehouses. Closed ones stay for old orders."""

    _name = "newerp.np.warehouse"
    _description = "Nova Poshta branch"
    _order = "city_name, number, name"

    ref = fields.Char(required=True, index=True, readonly=True)
    name = fields.Char(required=True, readonly=True)
    number = fields.Integer(readonly=True, help="The branch number, for sorting: 1, 2, ... 10.")
    kind = fields.Selection(KINDS, required=True, default="branch", readonly=True)
    city_ref = fields.Char(index=True, readonly=True)
    city_name = fields.Char("Місто", index=True, readonly=True)
    max_weight = fields.Integer("Найбільша вага, кг", readonly=True)
    working = fields.Boolean("Працює", default=True, readonly=True)

    _ref_unique = models.Constraint("UNIQUE(ref)", "This Nova Poshta branch is in the list already.")

    def _compute_display_name(self):
        for branch in self:
            branch.display_name = f"{branch.city_name}, {branch.name}" if branch.city_name else branch.name

    def _np_store(self, rows):
        """Creates or updates the branches by their Ref; ones Nova Poshta no longer lists are marked closed.
        Returns (created, updated)."""
        from .delivery_carrier import branch_number

        existing = {b.ref: b for b in self.with_context(active_test=False).search([])}
        seen, to_create, updated = set(), [], 0
        for row in rows:
            ref = str(row.get("Ref") or "")
            if not ref:
                continue
            seen.add(ref)
            values = {
                "name": str(row.get("Description") or ref),
                "number": branch_number(str(row.get("Description") or "")),
                "kind": "locker" if row.get("CategoryOfWarehouse") == "Postomat" else "branch",
                "city_ref": str(row.get("CityRef") or ""),
                "city_name": str(row.get("CityDescription") or ""),
                "max_weight": int(float(row.get("TotalMaxWeightAllowed") or 0)),
                "working": row.get("WarehouseStatus") == "Working",
            }
            branch = existing.get(ref)
            if branch is None:
                to_create.append({**values, "ref": ref})
            elif any(branch[key] != value for key, value in values.items()):
                branch.write(values)
                updated += 1
        self.create(to_create)
        self.env["newerp.np.city"]._np_store(rows)
        gone = [b.id for ref, b in existing.items() if ref not in seen and b.working]
        if rows and gone:  # an empty answer is a failure to read, not "every branch closed"
            self.browse(gone).write({"working": False})
            updated += len(gone)
        return len(to_create), updated
