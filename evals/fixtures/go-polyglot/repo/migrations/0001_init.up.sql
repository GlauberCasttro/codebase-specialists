-- 0001: base tables. Timestamps are timestamptz and written in UTC.
CREATE TABLE couriers (
    id          text PRIMARY KEY,
    name        text NOT NULL,
    online      boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE deliveries (
    id          text PRIMARY KEY,
    status      text NOT NULL,
    courier_id  text REFERENCES couriers(id),
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz
);
