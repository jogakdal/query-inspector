-- query-inspector Tier3 검증용 스키마 + 데이터
-- fixture(examples/sample-project)와 동일 구조. orders는 의도적으로 인덱스 미생성.
SET SESSION cte_max_recursion_depth = 100000;

CREATE TABLE users (
  id   BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100)
);
CREATE INDEX idx_users_name ON users(name);        -- V1과 동일(name 인덱스 존재)

CREATE TABLE orders (
  id         BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id    BIGINT NOT NULL,
  status     VARCHAR(20) NOT NULL,
  amount     DECIMAL(12,2) NOT NULL,
  created_at DATETIME NOT NULL
);
-- 의도적: user_id / status / created_at 인덱스 없음 → missing_index 재현(EXPLAIN에서 풀스캔 확인용)

-- users 2,000명
INSERT INTO users(name)
WITH RECURSIVE seq AS (SELECT 1 n UNION ALL SELECT n+1 FROM seq WHERE n < 2000)
SELECT CONCAT('user', LPAD(n, 5, '0')) FROM seq;

-- orders 20,000건 (풀스캔 rows가 의미있게 보이도록)
INSERT INTO orders(user_id, status, amount, created_at)
WITH RECURSIVE seq AS (SELECT 1 n UNION ALL SELECT n+1 FROM seq WHERE n < 20000)
SELECT (n % 2000) + 1,
       ELT((n % 4) + 1, 'NEW', 'PAID', 'SHIPPED', 'CANCELLED'),
       ROUND(RAND(n) * 1000, 2),
       DATE_SUB(NOW(), INTERVAL (n % 365) DAY)
FROM seq;

ANALYZE TABLE users, orders;
