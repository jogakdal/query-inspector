# 어댑터: `mybatis` (MVP / 완전 지원)

MyBatis XML 매퍼와 애노테이션 매퍼에서 SQL을 추출한다. 추출 난이도 **하** - 대부분 원본 SQL이 그대로 있어 신뢰도 `EXACT`가 높다.

## 대상 파일/지점

- **XML 매퍼**: `**/*Mapper.xml`, 또는 `<mapper namespace="...">`를 가진 XML, 흔히 `src/main/resources/**/mapper/**`.
  - 문장 태그: `<select>`, `<insert>`, `<update>`, `<delete>`.
- **애노테이션 매퍼**: 인터페이스의 `@Select`, `@Insert`, `@Update`, `@Delete`, `@SelectProvider`/`@*Provider`(프로바이더 클래스 메서드로 SQL 조립).
- **결과 매핑**: `<resultMap>`(+`<association>`/`<collection>`) - N+1 판정의 주요 단서.
- **재사용 조각**: `<sql id="...">` + `<include refid="...">`.

> diff에 XML의 일부 라인만 있어도, **매퍼 전체와 관련 `<resultMap>`/`<sql>`을 Read**해서 SQL을 온전히 복원한다.

## 동적 태그 전개

동적 SQL은 **대표 시나리오 2~3개**로 전개한다(전체 경우의 수 X). 각 시나리오의 라벨은 `AMBIGUOUS`(동적 분기 많음) 또는 `INFERRED`(단순 분기).

| 태그 | 의미 | 전개 방법 |
|---|---|---|
| `<if test>` | 조건부 조각 | 참/거짓 대표 조합 2~3개 |
| `<choose><when><otherwise>` | 분기 택1 | 각 when 중 대표 + otherwise |
| `<where>` | 선행 `AND/OR` 정리 + 조건 없으면 WHERE 생략 | 조건 유/무 두 형태 |
| `<set>` | UPDATE의 후행 쉼표 정리 | 갱신 컬럼 대표 조합 |
| `<trim prefix/suffix/prefixOverrides>` | 접두/접미 정리 | prefixOverrides 반영해 실제 문자열 구성 |
| `<foreach>` | 컬렉션 전개(주로 IN, 벌크) | `IN (?, ?, ...)`로 전개 -> `large_in_clause` 연계 |
| `<bind>` | 변수 바인딩(예: LIKE 패턴) | `_parameter` 가공 확인(선행 `%` -> `leading_wildcard_like`) |

`<foreach>`로 만든 IN 절은 크기 무제한이면 `large_in_clause`를, `<bind>`로 `'%' + value + '%'`를 만들면 `leading_wildcard_like`를 표기한다.

## 파라미터 표기 - `#{}` vs `${}`

- `#{param}` -> PreparedStatement 바인드(`?`). 안전, 플랜 재사용. **정상**.
- `${param}` -> **문자열 직접 치환**. SQL 인젝션 위험 + 리터럴이 매번 달라 플랜 캐시 오염. -> **`string_substitution`(🔴 critical)** 으로 표기한다(`heuristics.md` ^ 항목). ORDER BY 컬럼명 등 바인딩 불가한 곳에 불가피하면 **허용값 화이트리스트**로 강제하고 사용자 입력을 직접 넣지 않도록 남긴다.

## N+1 탐지 (MyBatis 특유)

`<resultMap>`에서:
- `<association property="..." select="otherMapper.selectX"/>` 또는 `<collection ... select="..."/>` -> **중첩 select 방식** = 부모 N행마다 자식 쿼리 -> `n_plus_one` 🔴.
- 반대로 **중첩 결과 매핑**(자식을 `select` 없이 조인 결과의 컬럼으로 매핑)은 조인 1회 -> N+1 아님(단, 다중 `<collection>` 조인은 `cartesian_join` 위험 점검).

`fetchType="lazy"`가 걸린 중첩 select도, 순회 접근 코드가 있으면 결국 N+1.

## 산출물 형식

각 문장마다:
- **원천**: `파일:라인`, `<select id="...">`의 id/namespace.
- **추론 SQL**: 정적부는 `EXACT`, 동적 전개 시나리오는 라벨과 함께 각각.
- **바인딩**: `#{}`/`${}` 목록, `${}` 있으면 위험 표기.
- Tier1 휴리스틱(`references/heuristics.md`) 적용 결과.
- **SQL 방언(dialect) 이질 문법 점검**: 추출 SQL에 `||`(mysql=OR)/`NVL`/`SYSDATE`/`ROWNUM` 등 감지 방언과 다른 문법이 있으면 `dialect_pipe_concat`으로 표기.

## 예시

```xml
<!-- N+1: 중첩 select -->
<resultMap id="orderRM" type="Order">
  <collection property="items" ofType="Item" select="ItemMapper.findByOrderId"/> <!-- 부모마다 실행 -->
</resultMap>

<!-- 동적 + foreach(IN) -->
<select id="search" resultMap="orderRM">
  SELECT * FROM orders                          <!-- select_star -->
  <where>
    <if test="status != null">AND status = #{status}</if>
    <if test="ids != null">AND id IN
      <foreach item="i" collection="ids" open="(" separator="," close=")">#{i}</foreach>  <!-- large_in_clause -->
    </if>
  </where>
</select>
```
-> 추출: `SELECT *`(select_star, EXACT), 중첩 select(n_plus_one, EXACT 구조/INFERRED 실행횟수), IN 전개(large_in_clause, AMBIGUOUS 크기).
