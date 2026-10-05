"""Domain errors. Callers catch ``BillingError``; never bare ``Exception``."""


class BillingError(Exception):
    code = "billing_error"


class InvalidAmount(BillingError):
    code = "invalid_amount"


class CurrencyMismatch(BillingError):
    code = "currency_mismatch"


class InvoiceStateError(BillingError):
    code = "invoice_state"


class PaymentDeclined(BillingError):
    code = "payment_declined"


class RefundExceedsCapture(BillingError):
    code = "refund_exceeds_capture"


class LedgerImbalance(BillingError):
    code = "ledger_imbalance"


class ImmutableEntry(BillingError):
    code = "immutable_entry"
