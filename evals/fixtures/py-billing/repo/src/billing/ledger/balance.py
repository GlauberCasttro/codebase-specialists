from billing.ledger.journal import Journal


def balance_of(journal: Journal, account: str) -> int:
    """Debit-positive balance in cents for an account."""
    total = 0
    for entry in journal.entries():
        for posting in entry.postings:
            if posting.account == account:
                total += posting.debit.cents - posting.credit.cents
    return total


def trial_balance_ok(journal: Journal) -> bool:
    debits = sum(e.total_debits() for e in journal.entries())
    credits = sum(e.total_credits() for e in journal.entries())
    return debits == credits
