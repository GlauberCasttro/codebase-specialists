-- 0002: status becomes an enum. Values mirror internal/dispatch/status.go.
-- Append-only: to add a status, write a NEW migration with ALTER TYPE ... ADD VALUE.
CREATE TYPE delivery_status AS ENUM ('created', 'assigned', 'picked_up', 'delivered', 'failed');
ALTER TABLE deliveries
    ALTER COLUMN status TYPE delivery_status USING status::delivery_status;
