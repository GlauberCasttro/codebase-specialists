import express from "express";
import { Catalog } from "./catalog/catalog.ts";
import { StockLedger } from "./inventory/stock.ts";
import { ReservationBook } from "./inventory/reservations.ts";
import { buildRouter } from "./http/routes.ts";

const app = express();
app.use(express.json());
const stock = new StockLedger();
const book = new ReservationBook(stock);
app.use("/api", buildRouter(new Catalog(), book));
setInterval(() => book.expireDue(), 30_000).unref();

const port = Number(process.env.PORT ?? 3001);
app.listen(port, () => console.log(`api listening on :${port}`));
