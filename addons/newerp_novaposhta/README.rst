====================
NewErp: Nova Poshta
====================

Nova Poshta as an Odoo delivery provider: a new delivery type "Нова Пошта" with the ``novaposhta_*`` methods Odoo
calls by name, as its own carriers do.

What it does now
================

* The carrier keeps its Nova Poshta account (API key, sender, contact, phone, the sender's city and branch); several
  sender accounts are several carriers. The key is a password field, for administrators only.
* The Nova Poshta methods of ``newerp_base`` (відділення, поштомат) become this type on install. Without a key a
  carrier works as a fixed price, so nothing breaks before the account is filled in.
* Branches and parcel lockers: Sales → Configuration → Нова Пошта: відділення, filled from ``Address.getWarehouses``
  (a button on the carrier and a weekly scheduled action). Branches Nova Poshta no longer lists stay, marked closed,
  for old orders.
* A quotation gets the branch (only working ones of the carrier's kind); the rate comes from
  ``InternetDocument.getDocumentPrice``: from the sender's city to the branch's, with the order's weight and amount.
  Products without a weight count as 0.1 kg.

Waybills, labels and tracking come in the next step.

Trying it
=========

A free API key comes from a personal Nova Poshta account (Settings → Security). Put it on the carrier, press
"Оновити довідник відділень", then pick a branch on a quotation and add the delivery. The tests never call the real
API: they answer with Nova Poshta's documented JSON.
