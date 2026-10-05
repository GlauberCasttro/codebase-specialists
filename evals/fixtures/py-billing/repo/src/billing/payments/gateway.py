"""Payment gateway port + adapters. Amounts cross the wire as integer cents."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from billing.shared.errors import PaymentDeclined
from billing.shared.money import Money


@dataclass(frozen=True)
class GatewayResult:
    reference: str
    approved: bool
    reason: Optional[str] = None


class FakeGateway:
    """Deterministic gateway for tests: decline when the amount ends in 13 cents."""

    def __init__(self) -> None:
        self.calls = 0
        self._refs: Dict[str, int] = {}

    def charge(self, amount: Money, source: str) -> GatewayResult:
        self.calls += 1
        if amount.cents % 100 == 13:
            return GatewayResult(reference="", approved=False, reason="card_declined")
        ref = "gw_%04d" % self.calls
        self._refs[ref] = amount.cents
        return GatewayResult(reference=ref, approved=True)

    def refund(self, reference: str, amount: Money) -> GatewayResult:
        self.calls += 1
        return GatewayResult(reference="%s_r%d" % (reference, self.calls), approved=True)


class HttpGateway:  # pragma: no cover - exercised in staging only
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s

    def charge(self, amount: Money, source: str) -> GatewayResult:
        import httpx

        resp = httpx.post(
            self.base_url + "/v1/charges",
            json={"amount_cents": amount.cents, "currency": amount.currency, "source": source},
            headers={"Authorization": "Bearer " + self.api_key},
            timeout=self.timeout_s,
        )
        body = resp.json()
        if resp.status_code == 402:
            raise PaymentDeclined(body.get("reason", "declined"))
        return GatewayResult(reference=body["id"], approved=body["status"] == "succeeded")

    def refund(self, reference: str, amount: Money) -> GatewayResult:
        import httpx

        resp = httpx.post(
            self.base_url + "/v1/charges/%s/refunds" % reference,
            json={"amount_cents": amount.cents},
            headers={"Authorization": "Bearer " + self.api_key},
            timeout=self.timeout_s,
        )
        body = resp.json()
        return GatewayResult(reference=body["id"], approved=body["status"] == "succeeded")
