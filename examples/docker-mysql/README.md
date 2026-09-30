# Tier3 검증용 로컬 MySQL (docker-compose)

`query-inspector`의 Tier3(실 DB EXPLAIN)를 실제로 돌려보는 로컬 환경이다. fixture와 동일 스키마(`orders`는 의도적으로 인덱스 없음)에 2만 건을 채워, `missing_index` 제안을 **실 실행계획으로 검증**한다.

## 사용

```bash
# 1) 기동 (Docker Desktop 실행 필요)
docker compose -f examples/docker-mysql/docker-compose.yml up -d --wait

# 2) 접속 URL(읽기 전용 계정)을 환경변수로만 주입
export QT_DOCKER_DB_URL="mysql://dqt_ro:dqt_ro@127.0.0.1:13306/demo"

# 3) 가드레일 검증 -> EXPLAIN (드라이버 필요 시 .venv 사용)
#    파이썬 명령: mac/linux는 python3, Windows는 python 또는 py
cat > /tmp/q.sql <<'SQL'
SELECT id, amount, created_at FROM orders
WHERE status = 'PAID' AND created_at >= '2026-01-01' ORDER BY created_at DESC
SQL
python3 scripts/db_guard.py   --profile docker --config .query-inspector.yml --sql-file /tmp/q.sql
python3 scripts/run_explain.py --profile docker --config .query-inspector.yml --sql-file /tmp/q.sql

# 정리
docker compose -f examples/docker-mysql/docker-compose.yml down -v
```

> 의존성: `run_explain.py`는 **pymysql 우선, 없으면 `mysql` CLI 폴백**. 둘 다 없으면 Tier2로 강등한다. 이 저장소는 개발용 `.venv`에 pymysql을 두었다(`.venv/bin/python scripts/run_explain.py ...`).

## 검증 결과 (before / after) - orders 20,000건

쿼리: `WHERE status='PAID' AND created_at>='2026-01-01' ORDER BY created_at DESC`

| 지표 | BEFORE (인덱스 없음) | AFTER (`idx_orders_status_created`) |
|------|---------------------|-------------------------------------|
| access_type | **ALL** (풀스캔) | **range** |
| key | null | **idx_orders_status_created** |
| rows | 20,300 | **3,273** (약 84%v) |
| filtered | 3.33% | 100% |
| filesort | **using_filesort: true** | **제거** |
| query_cost | 2730.85 | 1473 |

제안 인덱스: `CREATE INDEX idx_orders_status_created ON orders (status, created_at);`
(등호 `status` -> 범위/정렬 `created_at` 순 -> range 탐색 + `ORDER BY DESC`를 한 인덱스로 커버)

`EXPLAIN ANALYZE`는 실제 실행이지만 **트랜잭션을 열고 무조건 롤백**하며(`run_explain.py`), 계정은 읽기 전용(`dqt_ro`, `SELECT`만)이라 이중으로 안전하다.

## 안전

- 프로덕션 아님(로컬 13306). db_guard의 `host_allowlist: [127.0.0.1, localhost]` + `prod_guard`로 보호.
- 접속 URL은 환경변수(`QT_DOCKER_DB_URL`)로만. 저장소에 커밋 금지.
