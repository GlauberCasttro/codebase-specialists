-- 0003: a courier carries at most 3 active deliveries (dispatch.MaxActivePerCourier).
CREATE TABLE courier_load (
    courier_id  text PRIMARY KEY REFERENCES couriers(id),
    active      integer NOT NULL DEFAULT 0,
    CONSTRAINT courier_load_max_active CHECK (active BETWEEN 0 AND 3)
);
CREATE INDEX deliveries_active_by_courier ON deliveries (courier_id)
    WHERE status IN ('assigned', 'picked_up');
