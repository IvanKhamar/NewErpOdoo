==================================
NewErp: Ukrainian bank statements
==================================

The shop's bank accounts as Odoo bank journals: the statement comes from the bank into bank statement lines, and each
incoming payment is matched to the sales order it pays for, by itself when it is sure, else by a manager in two
clicks. The rules are those of NewErpPython (phase 9 and item 28).

What it does
============

* A bank journal gets the page "Виписка з банку": the bank and its keys, for administrators only. Several accounts
  and business cards are several journals.

  * ПриватБанк: the id and token of its Autoclient. With the journal's account number set, only that account's
    rows come in, when one Autoclient sees several accounts.
  * monobank: the personal token and the account id (for example the sole proprietor's account; empty is the main
    one). Sums come in kopecks and times in Unix seconds; they become hryvnias and Kyiv days. monobank answers once
    a minute with at most 500 rows, so a fuller period asks to be loaded in parts.
* "Завантажити виписку" (on the journal and on the payments list) loads any period up to 31 days; an hourly
  scheduled action, off by default, loads yesterday and today. All rows go in, incoming and outgoing, so the
  journal's balance is right. A row already loaded is skipped, so loading again is safe.
* Sales → Orders → Банківські оплати lists the incoming payments, by default those without an order.
* Automatic matching, after each import and on the button "Підібрати автоматично" (the last 31 days): a payment
  is linked when exactly one order is sure. Sure means the purpose names the order (its number, also the
  OpenCart number, or the customer's phone) and the sum fits (the total, the advance or the rest), and the order has
  no payment yet. A surname and a sum are not enough; two sure orders are left for a person; LiqPay payouts and
  outgoing rows are never linked.
* By hand: "Знайти замовлення" shows the orders of the payment's days ranked with the reasons (number 50, phone 30,
  total 25, advance or rest 20, surname 15, minus 40 when another payment is linked already), and a search by
  number, name or phone of any date. "Відв'язати" and "Не замовлення" do what they say.
* Linking makes the order's customer the payer of the line, removes the tag "Перевірити оплату" from the order and
  leaves a note in its chatter. The order shows its payments on the tab "Оплати з банку".

* Accounting: when the order has a posted customer invoice, the payment pays it. The line's suspense item becomes the
  customer's receivable and is reconciled with the invoice (in part for an advance; more money stays as the
  customer's credit, which Odoo offers on the next invoice). A payment that came before the invoice is reconciled
  when the invoice is posted. Unlinking undoes it. Without an invoice, as for orders from OpenCart, the link alone is
  the record and the line waits in the suspense account.

Odoo Community has no bank reconciliation screen (it is Enterprise), so the list of payments and the matching are
this addon's own. Managers only read statement lines in Odoo; linking checks the user's role and then writes.

Trying it
=========

PrivatBank's keys come from Privat24 for business: Integrations, Autoclient. A monobank token comes free from
api.monobank.ua for one's own accounts, so the monobank import is the easiest to try on real data. The tests never
call a bank: they answer with the JSON of the banks' documentation.
