# 어댑터 추가 가이드 (신규 스택용 템플릿)

새 스택(예: Python Django/SQLAlchemy, Node Prisma/TypeORM)을 지원하려면 **코어 수정 없이** 이 문서를 복사해 `references/adapters/<stack>.md`를 만들고, `SKILL.md` Stage 1의 라우팅 표와 설정 `stacks`에 이름을 추가하면 된다. 필요하면 선택적으로 `scripts/extract_<stack>.*`를 둔다.

파이프라인이 어댑터에 기대하는 계약(contract)은 아래 6가지다. 이 항목만 채우면 나머지(Tier 분석/리포트)는 공용 로직이 처리한다.

---

## 어댑터가 채워야 할 6가지

### 1. 대상 파일/지점
어떤 파일 패턴/코드 지점을 이 어댑터가 맡는가. (파일 glob, 함수/데코레이터/애노테이션, 설정 위치)

### 2. 추출 규칙
그 지점에서 SQL(또는 SQL 의도)을 어떻게 추출하는가. 정적 문자열인지, ORM 호출을 번역해야 하는지.

### 3. 동적 쿼리 전개
조건부/빌더/체이닝으로 쿼리가 달라지는 경우 **대표 시나리오 2~3개**로 전개하는 방법. (전수 X)

### 4. 신뢰도 라벨 매핑
어떤 경우 `EXACT`(원본 SQL) / `INFERRED`(단순 번역) / `AMBIGUOUS`(동적/불확실)인지.

### 5. 스택 특유 안티패턴
공용 `heuristics.md` 외에, 이 스택에서 특히 흔한 함정. (예: Django `.all()` 후 파이썬 루프 필터, Prisma include 남발 N+1)

### 6. 산출물 형식
원천(`파일:라인`), 추론 SQL(+라벨), 바인딩/보간 방식, Tier1 적용 결과.

---

## 예시 스켈레톤 (복사해서 사용)

```markdown
# 어댑터: <stack>

## 대상 파일/지점
- 파일: `**/*.py` 중 ...
- 지점: `Model.objects.filter(...)`, `session.query(...)`, `@Query`, ...

## 추출 규칙
- ORM 체이닝 -> SQL 번역 규칙 ...

## 동적 쿼리 전개
- 조건부 filter 체인 -> 대표 조합 2~3개 ...

## 신뢰도 라벨
- raw SQL 문자열: EXACT
- 단순 ORM 번역: INFERRED
- 조건부 빌더: AMBIGUOUS

## 스택 특유 안티패턴
- N+1: `select_related`/`prefetch_related` 누락, include 남발 ...
- 지연 평가 후 파이썬 측 필터 ...

## 산출물 형식
- 원천 / 추론 SQL(+라벨) / 바인딩 / Tier1 결과
```

---

## 참고

- SQL 방언(dialect) 판단은 공용 `references/dialect-detection.md` + `dialects/<dialect>.md`를 쓴다. 어댑터는 방언 감지를 재구현하지 않는다.
- 실 DB 접근이 필요하면 반드시 `scripts/db_guard.py`를 거친다. 어댑터가 직접 DB에 붙지 않는다.
- 완전한 참고 구현은 `mybatis.md`(정적+동적 풍부)와 `native-sql.md`(문자열 SQL)를 본다.
