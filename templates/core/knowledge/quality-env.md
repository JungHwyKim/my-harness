# 검증 환경과 Quality Profile 계약

이 문서는 **이 프로젝트에서** Quality Profile을 어떻게 설정하고 돌리는지를 둔다.
설정 파일은 `.claude/harness.json`이고, 그것을 읽는 쪽은 훅과 수동 CLI 둘이다.

## 설치 직후에는 비활성이다

기본 설치의 `fast`·`full`은 `triggers: []`, `stages: []`다. 자동 검사가 돌지 않고,
`run_quality.py --profile full`을 부르면 **설정 결함으로 종료 코드 2**가 난다 —
빈 Profile을 성공으로 인정하지 않는 것이 공통 엔진의 계약이다.

**비활성은 검사 통과가 아니다.** 설정하기 전까지 「검사 없음」이 사실이고, 그 상태를
완료 근거로 쓰지 않는다. `python`도 설정하지 않았으므로, 이 프로젝트의 인터프리터를
정하려면 아래 설정과 함께 적는다.

## Profile 두 개의 자리

| Profile | 쓰임 | 트리거 자리 |
|---|---|---|
| `fast` | 범위가 한정된 변경 직후, 영향받는 대상만 | `post_change` |
| `full` | 완료·커밋 전, 전체 검사 | `stop`, `pre_commit` |

각 stage는 `id`와 `argv`를 가지며 `timeout`과 `success_codes`를 선택으로 받는다.
`argv`의 `{python}`은 하네스가 고른 인터프리터로, `{mapped_targets}`는 변경에서 유도한
대상 목록으로 치환된다.

## 설정 절차

1. 이 프로젝트의 소스 경로를 `source_prefixes`와 `quality.tracked_paths`에 적는다.
   디렉터리는 **끝에 `/`를 붙인다** — 빠지면 그 항목으로는 아무 변경도 잡히지 않는다.
2. 추적 경로마다 `quality.mappings`에 검사 대상을 적거나,
   `quality.unmapped_by_design`에 **사유와 함께** 제외를 적는다. 둘 다 없으면 변경이
   조용히 검사 밖으로 빠진다.
3. `profiles.fast`와 `profiles.full`에 트리거와 stage를 채운다.
4. `python .claude/harness/scripts/doctor.py`로 결선을 확인한다.

언어·도구는 프로젝트가 정한다. lint·format·pytest가 모든 프로젝트의 필수 단계는 아니다.

<details>
<summary>Python 프로젝트의 stage 예시</summary>

`fast`는 `{python} -m pytest {mapped_targets} -q`, `full`은 `{python} -m ruff check .` →
`{python} -m ruff format --check .` → `{python} -m pytest -q`처럼 적는다.
다른 언어라면 그 생태계의 명령을 같은 자리에 둔다.
</details>

## 수동 실행

`python .claude/harness/scripts/run_quality.py --profile full`이 훅과 **같은 설정**을 읽어
돌린다. `--profile fast`는 `--changed <프로젝트 상대 경로>`를 반복 지정해야 한다.

종료 코드는 `0`(PASS 또는 SKIP), `1`(stage 실패), `2`(사용 오류·설정 결함)다.
SKIP은 0이지만 **검사 통과가 아니다.** 앞 단계 실패로 도달하지 못한 단계는 `NOT RUN`으로
따로 적힌다.

`--require-venv`를 주면 하네스가 고른 인터프리터가 이 프로젝트의 `.venv` 안인지 실행 전에
확인하고, 아니면 ERROR로 끝낸다. CI에서 쓸 수 있는 **선택** 플래그이며, 설정하지 않은 기본
설치에서 이 플래그를 실행 의무로 요구하지 않는다.

**훅의 `SKIP_*` 우회 변수는 이 명령에 적용되지 않는다.** 그 변수는 자동 검사를 잠시 끄는
것이고, 이 명령은 사람이나 CI가 일부러 돌리는 것이다. 환경변수 하나로 CI 게이트가 꺼지면
그건 검사가 아니다.

이 CLI는 `schema_version`이 **정확히 정수 2**인 설정만 실행한다. 1·부재는 V1이고,
3 이상과 정수가 아닌 값은 실행 전에 ERROR다.

**분류 결과가 실행 입력을 정한다.** 정책상 제외한 파일은 stage 인자에 넣지 않는다. 변경
파일이 전부 제외면 아무 명령도 돌지 않고 SKIP이다.

## 유료 테스트는 따로 본다

`checks.expensive_tests.pytest_markers`가 비어 있으면 유료 테스트 승인 검사가 비활성이다.
비용이 드는 테스트를 마커로 가른 뒤 그 목록을 채운다. 승인 경계는
[paid-test-approval.md](paid-test-approval.md)가 소유한다.

## 보장하지 않는 것

- 이 문서는 **설정 방법**이고, 설정했다는 사실이 검사 통과를 뜻하지 않는다.
- 설치물에는 측정값이 없다. 시간 예산과 실패율은 이 프로젝트에서 직접 재서 남긴다.
- Doctor는 명령을 실행하지 않으므로 도구 설치와 버전은 미검증이다
  ([doctor.md](doctor.md)).
