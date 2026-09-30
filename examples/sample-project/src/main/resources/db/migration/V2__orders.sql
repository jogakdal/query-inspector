-- V2: orders 테이블. 주의 — user_id(FK)·status·created_at 인덱스를 걸지 않음
-- (의도적: 실무에서 흔한 "인덱스 없이 배포" 패턴 재현)
CREATE TABLE orders (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  user_id BIGINT NOT NULL,
  status VARCHAR(20) NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  created_at DATETIME NOT NULL
);
