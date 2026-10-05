import unittest
from datetime import datetime, timezone

from billing.ledger import accounts
from billing.ledger.balance import balance_of, trial_balance_ok
from billing.ledger.entries import credit, debit
from billing.ledger.journal import Journal
from billing.shared.clock import FixedClock
from billing.shared.errors import ImmutableEntry, LedgerImbalance
from billing.shared.money import Money


class JournalTest(unittest.TestCase):
    def setUp(self):
        self.journal = Journal(FixedClock(datetime(2025, 6, 1, tzinfo=timezone.utc)))

    def test_rejects_unbalanced_entry(self):
        with self.assertRaises(LedgerImbalance):
            self.journal.post("bad", [debit(accounts.CASH, Money(100)),
                                      credit(accounts.REVENUE, Money(99))])

    def test_delete_removes_entry(self):
        e = self.journal.post("oops", [debit(accounts.CASH, Money(7)),
                                       credit(accounts.REVENUE, Money(7))])
        self.journal.delete(e.id)
        self.assertEqual(self.journal.entries(), [])

    def test_reverse_keeps_both_entries(self):
        e = self.journal.post("sale", [debit(accounts.CASH, Money(500)),
                                       credit(accounts.REVENUE, Money(500))])
        r = self.journal.reverse(e.id)
        self.assertEqual(len(self.journal.entries()), 2)
        self.assertEqual(r.reverses, e.id)
        self.assertEqual(balance_of(self.journal, accounts.CASH), 0)
        self.assertTrue(trial_balance_ok(self.journal))

    def test_cannot_reverse_twice(self):
        e = self.journal.post("sale", [debit(accounts.CASH, Money(1)),
                                       credit(accounts.REVENUE, Money(1))])
        self.journal.reverse(e.id)
        with self.assertRaises(ImmutableEntry):
            self.journal.reverse(e.id)


if __name__ == "__main__":
    unittest.main()
