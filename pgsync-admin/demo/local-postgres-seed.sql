CREATE TABLE customers (
    id integer PRIMARY KEY,
    name text NOT NULL,
    email text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE TABLE orders (
    id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES customers(id),
    order_number text NOT NULL UNIQUE,
    total numeric(10, 2) NOT NULL,
    status text NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);

INSERT INTO customers (id, name, email, created_at, updated_at) VALUES
    (1, 'Ayu Lestari', 'ayu@example.test', now() - interval '3 days', now() - interval '1 hour'),
    (2, 'Bima Saputra', 'bima@example.test', now() - interval '2 days', now() - interval '2 hours'),
    (3, 'Citra Dewi', 'citra@example.test', now() - interval '1 day', now() - interval '3 hours');

INSERT INTO orders (id, customer_id, order_number, total, status, created_at, updated_at) VALUES
    (101, 1, 'DEMO-1001', 125000.00, 'paid', now() - interval '2 days', now() - interval '1 hour'),
    (102, 1, 'DEMO-1002', 89000.00, 'processing', now() - interval '1 day', now() - interval '2 hours'),
    (103, 2, 'DEMO-1003', 249000.00, 'paid', now() - interval '1 day', now() - interval '3 hours'),
    (104, 3, 'DEMO-1004', 56000.00, 'shipped', now() - interval '12 hours', now() - interval '4 hours');
