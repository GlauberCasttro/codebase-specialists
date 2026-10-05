from billing.shared.errors import RefundExceedsCapture
from billing.shared.money import Money


def refundable(captured: Money, already_refunded: Money) -> Money:
    return captured - already_refunded


def check_refund(captured: Money, already_refunded: Money, requested: Money) -> None:
    if requested.is_negative() or requested.is_zero():
        raise RefundExceedsCapture("refund must be positive")
    if requested.cents > refundable(captured, already_refunded).cents:
        raise RefundExceedsCapture(
            "requested %d > refundable %d"
            % (requested.cents, refundable(captured, already_refunded).cents)
        )
