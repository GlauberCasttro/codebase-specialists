from typing import Dict, Optional

from billing.invoices.models import Invoice


class InMemoryInvoiceRepository:
    def __init__(self) -> None:
        self._items: Dict[str, Invoice] = {}

    def save(self, invoice: Invoice) -> None:
        self._items[invoice.id] = invoice

    def get(self, invoice_id: str) -> Optional[Invoice]:
        return self._items.get(invoice_id)

    # TODO(BILL-412): legacy name kept only for the 2024 CSV importer; use get().
    def get_bill(self, bill_id: str) -> Optional[Invoice]:
        return self.get(bill_id)
