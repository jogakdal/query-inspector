#!/usr/bin/env bash
# tests/run_tests.sh — 결정적(기계 검증 가능) 회귀 테스트
#
# 스킬의 어댑터 추출·휴리스틱 판정 자체는 LLM이 수행하므로 여기서 자동화하지 않는다
# (그건 expected/*.yml 골든을 claude plugin eval 또는 수동 대조로 검증 — tests/README.md).
# 이 러너는 결정적인 부분만 검증한다: 가드레일 self-test, collect_diff 분류, 골든 파일 형식.
#
# 사용법: bash tests/run_tests.sh   (macOS bash 3.2 호환)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$(dirname "$HERE")"
fail=0
check() { if eval "$2"; then echo "  PASS: $1"; else echo "  FAIL: $1"; fail=1; fi; }

echo "== 1) db_guard 가드레일 self-test =="
if python3 "$SKILL/scripts/db_guard.py" --self-test >/dev/null; then
  echo "  PASS: self-test"
else
  echo "  FAIL: self-test"; fail=1
fi

echo "== 2) collect_diff 파일 분류 (examples/sample-project) =="
tmp="$(mktemp -d)"
cp -R "$SKILL/examples/sample-project/." "$tmp/"
( cd "$tmp" && git init -q && git config user.email t@t && git config user.name t && git add -A )
out="$( cd "$tmp" && python3 "$SKILL/scripts/collect_diff.py" )"
check "UserMapper.xml → mybatis-xml"   'printf "%s" "$out" | grep -Eq "\[mybatis-xml\].*UserMapper.xml"'
check "OrderMapper.xml → mybatis-xml"  'printf "%s" "$out" | grep -Eq "\[mybatis-xml\].*OrderMapper.xml"'
check "V2__orders.sql → migration-sql" 'printf "%s" "$out" | grep -Eq "\[migration-sql\].*V2__orders.sql"'
check "UserRepository.kt → source"     'printf "%s" "$out" | grep -Eq "\[source\].*UserRepository.kt"'
rm -rf "$tmp"
check ".py Django migration -> migration-sql" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"app/migrations/0001_initial.py\")==\"migration-sql\"'"
check ".py Alembic version -> migration-sql"  "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"alembic/versions/a1_x.py\")==\"migration-sql\"'"
check ".py models.py -> source"               "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"app/models.py\")==\"source\"'"
check ".py migrations/__init__.py -> source"  "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"app/migrations/__init__.py\")==\"source\"'"
check "루트 migrations/*.py -> migration-sql (B9)" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"migrations/0001_initial.py\")==\"migration-sql\"'"
check "is_test_path: Python tests/·test/ 제외, 소스 유지 (B2)" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import is_test_path as t; assert t(\"app/tests/test_x.py\") and t(\"src/oscar/test/x.py\") and t(\"a/test_foo.py\") and not t(\"app/views.py\")'"

check ".html/.jinja -> template (H2)" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import classify; assert classify(\"flaskbb/templates/forum/row.html\")==\"template\" and classify(\"t/x.jinja2\")==\"template\"'"
check "is_doc_or_build_path: docs/·setup.py 제외, tasks.py 유지 (M3)" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); from collect_diff import is_doc_or_build_path as d; assert d(\"docs/conf.py\") and d(\"setup.py\") and d(\"hatch_build.py\") and not d(\"flaskbb/tasks.py\")'"

echo "== 3) 골든 기대 파일 존재/형식 =="
have_yaml=0; python3 -c 'import yaml' 2>/dev/null && have_yaml=1
for f in sample-project jpa-sample django-sample sqlalchemy-sample; do
  check "expected/$f.yml 존재" "test -f '$HERE/expected/$f.yml'"
  if [ "$have_yaml" -eq 1 ]; then
    check "expected/$f.yml YAML 파싱" "python3 -c 'import yaml; yaml.safe_load(open(\"$HERE/expected/$f.yml\"))'"
  fi
done
[ "$have_yaml" -eq 1 ] || echo "  SKIP: PyYAML 없음 → YAML 파싱 검증 생략(pip install pyyaml)"

echo "== 4) fixture 존재 (JVM + Python) =="
check "fixtures/jpa-sample/Order.kt"           "test -f '$HERE/fixtures/jpa-sample/Order.kt'"
check "fixtures/jpa-sample/OrderRepository.kt" "test -f '$HERE/fixtures/jpa-sample/OrderRepository.kt'"
check "fixtures/django-sample/models.py"       "test -f '$HERE/fixtures/django-sample/models.py'"
check "fixtures/django-sample/views.py"        "test -f '$HERE/fixtures/django-sample/views.py'"
check "fixtures/sqlalchemy-sample/models.py"   "test -f '$HERE/fixtures/sqlalchemy-sample/models.py'"
check "fixtures/sqlalchemy-sample/queries.py"  "test -f '$HERE/fixtures/sqlalchemy-sample/queries.py'"

echo "== 5) collect_diff 증분/전체 모드 =="
t2="$(mktemp -d)"
cp -R "$SKILL/examples/sample-project/." "$t2/"
( cd "$t2" && git init -q && git config user.email t@t && git config user.name t && git add -A && git commit -q -m base )
o1="$( cd "$t2" && python3 "$SKILL/scripts/collect_diff.py" )"
check "상태없음 → 첫 실행/전체" 'printf "%s" "$o1" | grep -q "첫 실행"'
c1="$( cd "$t2" && git rev-parse HEAD )"
mkdir -p "$t2/docs/query-inspector/tuning-reports"
printf '{"version":1,"last_tuned_commit":"%s"}\n' "$c1" > "$t2/docs/query-inspector/tuning-reports/state.json"
printf 'SELECT * FROM x;\n' > "$t2/new.sql"                    # 새 미추적 파일
o2="$( cd "$t2" && python3 "$SKILL/scripts/collect_diff.py" )"
check "baseline 설정 → 증분"        'printf "%s" "$o2" | grep -q "증분"'
check "증분: 새 파일 new.sql 포함"  'printf "%s" "$o2" | grep -q "new.sql"'
check "증분: 미변경 UserMapper 제외" '! printf "%s" "$o2" | grep -Eq "\[mybatis-xml\].*UserMapper.xml"'
# B1: 상태(baseline)가 있어도 --files는 그 파일을 대상으로 (baseline diff로 0건이 되던 회귀)
umap="$( cd "$t2" && git ls-files '*UserMapper.xml' | head -1 )"
o3="$( cd "$t2" && python3 "$SKILL/scripts/collect_diff.py" --files "$umap" )"
check "B1: 상태 있어도 --files 대상 포착" 'printf "%s" "$o3" | grep -q "UserMapper.xml"'
# B4: diff(증분) 모드에서도 쿼리 무관(other) 파일 제외
printf '# b4\n' > "$t2/notes_b4.md"
( cd "$t2" && git add notes_b4.md && git commit -q -m b4 )
o4="$( cd "$t2" && python3 "$SKILL/scripts/collect_diff.py" )"
check "B4: diff 모드 other(notes_b4.md) 제외" '! printf "%s" "$o4" | grep -q "notes_b4.md"'
rm -rf "$t2"

echo "== 6) URL 특수문자 왕복·파서 일치 (Tier3 크래시 회귀) =="
check "parse_url: percent-encoded 비번 unquote" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); import run_explain as r; d=r.parse_url(\"mysql://u:AAA%23%40%21@10.0.0.5:3306/db\"); assert d[\"password\"]==\"AAA#@!\" and d[\"host\"]==\"10.0.0.5\" and d[\"port\"]==3306'"
check "extract_hosts == parse_url host (가드 일치)" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); import run_explain as r, db_guard as g; u=\"mysql://u:AAA%23%40%21@10.0.0.5:3306/db\"; assert g.extract_hosts(u)==[r.parse_url(u)[\"host\"]]'"
check "set_db: raw 비번 자동 인코딩→왕복" "python3 -c 'import sys; sys.path.insert(0,\"$SKILL/scripts\"); import set_db_credential as s, run_explain as r; e=s.normalize_url_credentials(\"mysql://user:AAA#@!@10.0.0.5:3306/db\"); assert r.parse_url(e)[\"password\"]==\"AAA#@!\"'"

echo
if [ "$fail" -eq 0 ]; then echo "ALL PASS"; else echo "SOME FAILED"; fi
exit $fail
