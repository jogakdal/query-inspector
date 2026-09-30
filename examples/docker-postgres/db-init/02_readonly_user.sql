-- 읽기 전용 계정 (가드레일 권장: Tier3는 SELECT/EXPLAIN 전용 계정 사용)
-- 01_schema.sql 다음에 실행되므로 테이블이 이미 존재한다.
CREATE ROLE dqt_ro LOGIN PASSWORD 'dqt_ro';
GRANT CONNECT ON DATABASE demo TO dqt_ro;
GRANT USAGE ON SCHEMA public TO dqt_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dqt_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO dqt_ro;
