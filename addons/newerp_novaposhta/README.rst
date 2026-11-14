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

* Waybill: validating a delivery creates the recipient and the waybill (``Counterparty.save``,
  ``InternetDocument.save``) from the sender's branch to the order's branch. An order with the payment term
  "Накладений платіж" gets Nova Poshta's payment control for its total. The number goes to the delivery's tracking
  reference, the cost to its shipping price, and the label PDF is attached to the delivery.
* Cancelling the shipment deletes the waybill (``InternetDocument.delete``); the tracking link opens Nova Poshta's
  public page.
* Tracking: an hourly scheduled action asks ``TrackingDocument.getStatusDocuments`` about waybills that can still
  change (100 per call) and keeps the status, the planned delivery and the start of paid storage on the delivery.
  Final statuses (received, refused, returned) are not asked again. When a parcel waits at the branch and paid
  storage starts within a day, the order's salesperson gets one to-do activity, as the old site reminded.

Trying it
=========

A free API key comes from a personal Nova Poshta account (Settings → Security). Put it on the carrier, press
"Оновити довідник відділень", then pick a branch on a quotation and add the delivery. The tests never call the real
API: they answer with Nova Poshta's documented JSON.
