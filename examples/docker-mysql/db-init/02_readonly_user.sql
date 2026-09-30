-- 읽기 전용 계정 (가드레일 권장: Tier3는 SELECT/EXPLAIN 전용 계정 사용)
CREATE USER IF NOT EXISTS 'dqt_ro'@'%' IDENTIFIED BY 'dqt_ro';
GRANT SELECT ON demo.* TO 'dqt_ro'@'%';
FLUSH PRIVILEGES;
