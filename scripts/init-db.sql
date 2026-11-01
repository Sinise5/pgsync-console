
ALTER SYSTEM SET wal_level = logical;

CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES categories(id),
    name TEXT NOT NULL,
    description TEXT,
    price NUMERIC,
    status TEXT,
    deleted_at TIMESTAMP NULL,
    updated_at TIMESTAMP DEFAULT now()
);

CREATE INDEX idx_products_status
ON products(status);

CREATE INDEX idx_products_updated_at
ON products(updated_at);
