-- Simulated legacy operational database. No constraints on purpose: real source
-- systems do emit duplicates and bad values, and the pipeline must cope with them.
CREATE TABLE IF NOT EXISTS source.customers (
    customer_id  bigint, email text, full_name text, city text, country text,
    segment text, signup_date date, updated_at timestamp
);
CREATE TABLE IF NOT EXISTS source.orders (
    order_id bigint, customer_id bigint, order_ts timestamp, status text,
    channel text, updated_at timestamp
);
CREATE TABLE IF NOT EXISTS source.order_items (
    order_item_id bigint, order_id bigint, product_id bigint, quantity integer,
    unit_price numeric(12,2), discount numeric(5,2), updated_at timestamp
);
CREATE TABLE IF NOT EXISTS source.payments (
    payment_id bigint, order_id bigint, method text, amount numeric(12,2),
    status text, paid_at timestamp, updated_at timestamp
);
CREATE INDEX IF NOT EXISTS ix_src_customers_upd ON source.customers (updated_at);
CREATE INDEX IF NOT EXISTS ix_src_orders_upd ON source.orders (updated_at);
CREATE INDEX IF NOT EXISTS ix_src_items_upd ON source.order_items (updated_at);
CREATE INDEX IF NOT EXISTS ix_src_payments_upd ON source.payments (updated_at);
