# 배포 기본 설치물의 첫 실측 baseline

- 날짜: 2026-11-24
- 대상: `main / cbedca9` 작업 트리 + `template-core-packs` 구현(미커밋).
  `templates/core/harness.json`에서 만든 설치물
- 비교 기준: **없다.** 이 설정으로 실제 설치물을 만들어 Doctor를 돌린 것은 이번이 처음이다
- 판정: 유지 — 설계가 예상한 비활성 동작이 실제로 그대로 나왔다

## 왜 미래 비교 가치가 있는가

설계 검토 네 라운드 동안 「비활성 기본값이 Doctor를 통과한다」는 판단은 **`doctor.py`를
읽어서** 내린 것이었다. 빈 profile이 WARN이고 FAIL이 아니라는 분기를 코드에서 확인했을
뿐, 그 설정으로 만든 설치물을 돌려 본 적이 없다. 이 수치가 그 추론을 실측으로 바꾼다.

배포 설정이나 Doctor의 분기를 고치면 이 세 숫자가 먼저 움직인다. WARN이 FAIL로 바뀌거나
종료 코드가 1이 되면 설치물의 첫 경험이 깨진 것이다.

## 조건과 방법

```text
python .claude/harness/scripts/export_template.py --dest <새 경로>
python <새 경로>/.claude/harness/scripts/doctor.py
python <새 경로>/.claude/harness/scripts/run_quality.py --profile full
```

Windows 11, Python 3.12.5, 소스 저장소의 `.venv` 인터프리터로 실행했다. 설치물에는 `.venv`가
없으므로 `run_quality.py`가 고른 인터프리터는 **소스 쪽 venv**였다 — 설치물 자체의 환경을
잰 것이 아니다.

## 결과

| 측정 | 기준 | 현재 | 차이 |
|---|---:|---:|---:|
| 공통 출력 파일 수 | 없음 | 39 | 신규 |
| `--pack rag --pack interview` 출력 파일 수 | 없음 | 52 | 신규 |
| 설치물 Doctor | 없음 | PASS 11 · WARN 7 · FAIL 0, 종료 0 | 신규 |
| 소스 저장소 Doctor | PASS 26 · WARN 1 · FAIL 0 (2026-11-22) | PASS 26 · WARN 1 · FAIL 0, 종료 0 | 유지 |
| 설치물의 빈 `--profile full` | 없음 | `[ERROR]` 종료 2 | 신규 |

설치물의 WARN 7건은 예상한 자리 그대로다 — `fast`·`full`의 빈 triggers/stages, 추적 경로가
비어 있는 것, `{python}` stage가 없어 미검사인 D-PYTHON, 그리고 비활성 profile 때문에 필수
결선을 요구하지 않는 세 D-WIRING이다.

## 판정과 근거

**유지.** 세 가지가 설계와 같다.

1. 설치물 Doctor가 **FAIL 없이 종료 0**이다. 비활성 기본값이 진단을 막지 않는다.
2. 그 0이 검사 통과를 뜻하지 않는다는 것도 그대로다 — WARN 7건과 「미검사」 표시가 남는다.
3. 빈 Full의 수동 호출은 **ERROR / 종료 2**다. 비활성을 성공으로 인정하지 않는 공통 엔진의
   계약이 설치물에서도 같다.

39 → 52의 차이 13건은 manifest의 pack 항목 수(rag 9 + interview 4)와 일치한다.

## 한계와 재지 못한 것

- **설치물에서 훅이 실제로 도는지는 재지 않았다.** Doctor는 명령을 실행하지 않고, 훅은
  Claude Code 세션 안에서만 돈다. 결선 PASS는 「연결이 있다」까지다.
- `run_quality.py`를 소스 venv로 불렀으므로 **설치물의 인터프리터 선택은 미검증**이다.
  설치물에 `.venv`를 만들어 재는 것은 **통합 설치 검증 작업**의 몫이다. 그 작업의 임시
  명세는 현재 `tasks/template-install-smoke.md`지만, 임시 파일이므로 끝나면 사라진다 —
  남는 경계는 「exporter까지가 이 작업, 설치물 실행은 그 작업」이다.
- 두 OS 중 **Windows만** 쟀다. hosted CI는 소스 저장소를 돌리고 설치물을 만들지 않는다.
- 활성화한 뒤의 Doctor(WARN이 사라지고 결선 검사가 도는 상태)는 재지 않았다.

## 다시 재는 방법

위 세 명령을 그대로 돌린다. 출력 파일 수는 `templates/manifest.json`의 항목 수와 같아야
하고, 그 대조는 `tests/test_export_template.py`가 자동으로 한다 — 수가 어긋나면 테스트가
먼저 실패한다.

## Knowledge 반영

설치물의 WARN이 정상이라는 **현재 규칙**은 배포 Knowledge
(`templates/core/knowledge/doctor.md`의 「설치 직후의 WARN은 정상이다」)와
`templates/core/INSTALL.md`에 있다. 이 문서는 그 규칙이 실측으로 확인된 시점과 수치만 둔다.
