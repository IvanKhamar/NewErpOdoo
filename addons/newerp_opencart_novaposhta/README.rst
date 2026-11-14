==================================================
NewErp: OpenCart orders with Nova Poshta branches
==================================================

A bridge addon: it installs itself (``auto_install``) when both ``newerp_opencart`` and ``newerp_novaposhta`` are
installed, so neither of them depends on the other.

OpenCart keeps an order's branch as text in ``shipping_address_2`` ("Відділення №1: вул. Хрещатик, 1") and the city
in ``shipping_city``. For an order with a Nova Poshta delivery method the import now picks:

* the branch or parcel locker with the same name in that city, else the one with the same number;
  a working branch before a closed one; none when unsure, so the manager chooses it;
* for the courier, the city.

Tests: ``tools/run_tests.sh newerp_opencart_novaposhta``.
