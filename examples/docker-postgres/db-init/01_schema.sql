-- query-inspector Tier3 검증용 스키마 + 데이터 (PostgreSQL)
-- orders는 의도적으로 인덱스 미생성 -> missing_index / Seq Scan 재현.

CREATE TABLE users (
  id   BIGSERIAL PRIMARY KEY,
  name VARCHAR(100)
);
CREATE INDEX idx_users_name ON users(name);        -- name 인덱스 존재

CREATE TABLE orders (
  id         BIGSERIAL PRIMARY KEY,
  user_id    BIGINT NOT NULL,
  status     VARCHAR(20) NOT NULL,
  amount     NUMERIC(12,2) NOT NULL,
  created_at TIMESTAMP NOT NULL
);
-- 의도적: user_id / status / created_at 인덱스 없음 -> EXPLAIN에서 Seq Scan 확인용

-- users 2,000명
INSERT INTO users(name)
SELECT 'user' || lpad(n::text, 5, '0')
FROM generate_series(1, 2000) AS s(n);

-- orders 20,000건 (Seq Scan rows가 의미있게 보이도록)
INSERT INTO orders(user_id, status, amount, created_at)
SELECT (n % 2000) + 1,
       (ARRAY['NEW', 'PAID', 'SHIPPED', 'CANCELLED'])[(n % 4) + 1],
       round((random() * 1000)::numeric, 2),
       now() - ((n % 365) || ' days')::interval
FROM generate_series(1, 20000) AS s(n);

ANALYZE users;
ANALYZE orders;
