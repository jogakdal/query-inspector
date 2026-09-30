# Tier3 검증용 로컬 PostgreSQL (docker-compose)

`query-inspector`의 Tier3(실 DB EXPLAIN)를 PostgreSQL에서 돌려보는 로컬 환경이다. `orders`는 의도적으로 인덱스 없이 2만 건을 채워, Seq Scan(풀스캔)과 Sort를 **실 실행계획으로 확인**한다.

## 사용

```bash
# 1) 기동 (Docker Desktop 실행 필요)
docker compose -f examples/docker-postgres/docker-compose.yml up -d --wait

# 2) 접속 URL(읽기 전용 계정)을 환경변수로만 주입
export QT_PG_URL="postgresql://dqt_ro:dqt_ro@127.0.0.1:15432/demo"

# 3) EXPLAIN (--dialect postgresql). 드라이버 필요 시 venv 사용
#    파이썬 명령: mac/linux는 python3, Windows는 python 또는 py
cat > /tmp/q.sql <<'SQL'
SELECT * FROM orders WHERE status = 'PAID' ORDER BY created_at DESC LIMIT 10
SQL
python3 scripts/run_explain.py --profile pg --config .query-inspector.yml --sql-file /tmp/q.sql --dialect postgresql

# 정리
docker compose -f examples/docker-postgres/docker-compose.yml down -v
```

`.query-inspector.yml`의 프로파일 예:

```yaml
db:
  profiles:
    pg:
      url_env: QT_PG_URL
      host_allowlist: ["127.0.0.1", "localhost"]
      statement_timeout_ms: 3000
```

> 의존성: `run_explain.py`는 **psycopg(psycopg3 우선, 없으면 psycopg2) 우선, 없으면 `psql` CLI 폴백**. 둘 다 없으면 Tier2로 강등한다. 설치: `pip install 'psycopg[binary]'` 또는 `psql` 클라이언트.

## 검증 결과 - orders 20,000건

쿼리: `SELECT * FROM orders WHERE status='PAID' ORDER BY created_at DESC LIMIT 10`

| 계획 노드 | 내용 |
|---|---|
| Seq Scan | `orders` (인덱스 없음, `Filter: status='PAID'`) |
| Sort | `created_at DESC` |
| Plan Rows | 5,000 |

인덱스가 없어 **Seq Scan(풀스캔) + Sort**가 잡힌다(`summarize_postgres_json`이 `flags: {seq_scan, sort}`로 요약).

제안 인덱스: `CREATE INDEX idx_orders_status_created ON orders (status, created_at);`
(등호 `status` -> 정렬 `created_at` 순으로 Seq Scan과 Sort를 함께 제거)

`EXPLAIN ANALYZE`는 실제 실행이지만 **트랜잭션을 열고 무조건 롤백**하며(`run_explain.py`), 계정은 읽기 전용(`dqt_ro`, `SELECT`만)이라 이중으로 안전하다.

## 안전

- 프로덕션 아님(로컬 15432). db_guard의 `host_allowlist: [127.0.0.1, localhost]`로 보호.
- 접속 URL은 환경변수(`QT_PG_URL`)로만. 저장소에 커밋 금지.
