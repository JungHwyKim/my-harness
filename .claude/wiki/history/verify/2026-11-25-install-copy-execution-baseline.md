# 배포 사본에서 엔진·훅·수집기를 실제로 돌린 첫 실측

- 날짜: 2026-11-25
- 대상: **`main / 2048015`** — `tests/test_template_install.py`. exporter 출력물 안에서
  Doctor·Quality 엔진·훅·수집기를 실행한 결과. 두 OS hosted CI는
  [run 45609249573](https://github.com/JungHwyKim/my-harness/actions/runs/45609249573)
- 비교 기준: `2026-11-24-deployment-default-baseline.md`. 그 기록은 **정적 진단**(Doctor 종료
  0, 빈 Full 종료 2)까지였고 「훅이 실제로 도는지」·「인터프리터 선택」을 미검증으로 남겼다
- 판정: 개선 — 그 두 미검증 항목이 닫혔다. 새 baseline 이다

## 왜 미래 비교 가치가 있는가

**설치물이 도는지는 파일 목록으로 알 수 없다.** 소스에서 테스트가 통과해도 사본에서는
import·참조 경로가 끊길 수 있고, 그 차이는 사본 안에서 명령을 돌려야 드러난다. 이 숫자가
다음에 깨질 때 「사본이 깨졌다」와 「검사가 사본을 안 봤다」를 가르려면 지금의 실행 결과와
아래 루트 해석 규칙이 필요하다.

특히 **루트 해석이 세 갈래**라는 것이 이번에 확정됐다. 하나로 알고 테스트를 쓰면 엉뚱한
프로젝트를 재면서 초록이 된다.

## 조건과 방법

```text
python -m pytest tests/test_template_install.py -q -rs
python .claude/harness/scripts/run_quality.py --profile full --require-venv
```

Windows 11, Python 3.12.5, `pytest 9.2.0`, 저장소의 `.venv`. 모든 사본은 pytest 임시 경로에
**실제 exporter 로** 만들었고, 자식 프로세스에서 `PYTHONPATH` 를 지워 소스 import 도움을
끊었다. 네 구성(core · rag · interview · 둘 다)을 썼다.

## 결과

| 측정 | 기준 | 현재 | 차이 |
|---|---|---|---|
| 사본 Doctor (core·rag·둘 다) | 종료 0 (core 만) | **종료 0, `D-PROFILE` WARN 존재** | 구성 셋으로 확대 |
| 빈 Full 수동 호출 | 종료 2 | **종료 2**, 판정에 PASS 없음 | 유지 |
| 설정한 Profile 실행 | 미검증 | **종료 0 + probe 실행**, stage cwd = 사본, 인터프리터 = 설정한 `python` | 신규 |
| 실패 stage | 미검증 | **종료 1**, 실패 stage 식별, **뒤 단계 미실행** | 신규 |
| 합성 PostToolUse 훅 | 미검증 | **훅 종료 0 + probe 실행**, probe cwd = 사본 | 신규 |
| 실패 Fast 의 훅 응답 | 미검증 | **훅 종료 2 + stderr 사유** (CLI 의 종료 1 과 다른 자리) | 신규 |
| 깨진 배선 | 미검증 | 정상 사본 **0** → 훅 파일 하나 삭제 후 **1 + FAIL**, 소스 해시 불변 | 신규 |
| 기존 대상 재내보내기 | 종료 2 | **종료 2**, sentinel 세 파일 해시·내용 불변 | 사본 fixture 로 확대 |
| 설치된 openwork | 미검증 | 빈 정보원 **경고 + items 0** → 정보원 설정 후 **items 정확히 1**, 본문·출처 일치 | 신규 |
| 설치된 quiz | 미검증 | **questions 2 · starred 1 · selected 2**, 본문·노트 출처 일치 | 신규 |
| 전체 테스트 | 851 passed · 5 skipped | **871 passed · 5 skipped / 57.35초** | +20 |
| 이 파일 단독 | — | 20 passed / 8.69초 | 신규 |

## 판정과 근거

**개선.** 두 미검증 항목이 닫혔다.

1. **인터프리터 선택**은 사본 설정의 `python` 키에 적은 값과 probe 가 보고한
   `sys.executable` 을 대조해 확인했다. 「소스 venv 안에 있다」로 판정하지 않는다 — 테스트를
   돌린 인터프리터가 원래 거기 있으므로 그 기준은 늘 참이 된다.
2. **훅 실행**은 합성 payload 로 확인했다. `tool_input.file_path` 가 있으면 훅은 git 없이
   그 경로를 쓰므로(`auto_test_check.py:437`) 임시 사본에서도 재현된다.

그리고 **루트 해석 세 갈래**가 실측으로 확정됐다.

| 대상 | 루트를 정하는 방법 |
|---|---|
| `doctor.py` · `run_quality.py` | **자기 배치.** 엉뚱한 `CLAUDE_PROJECT_DIR` 와 외부 cwd 를 모두 무시한다 |
| 훅 | `CLAUDE_PROJECT_DIR` → cwd. `_hookutil.PROJECT_ROOT` 는 **import 때** 정해진다 |
| `openwork/collect.py` | 환경 → cwd. **자기 배치 fallback 이 없다** — 둘 다 어긋나면 종료 2 |

## 두 OS CI — 22개가 모두 양쪽에서 돌았다

처음 20개는 `2048015`([run 45609249573](https://github.com/JungHwyKim/my-harness/actions/runs/45609249573)),
수정 뒤 22개는 `2f88ff0`([run 45613723220](https://github.com/JungHwyKim/my-harness/actions/runs/45613723220)).

| 환경 | `2048015` (총 876) | `2f88ff0` (총 878) | skip 사유 |
|---|---|---|---|
| `ubuntu-latest` | 872 passed · 4 skipped / 16.01초 | **874 passed · 4 skipped / 12.14초** | Windows 전용 분기 하나, junction 셋(비해당) |
| `windows-latest` | 874 passed · 2 skipped / 35.47초 | **876 passed · 2 skipped / 36.55초** | POSIX 전용 둘 |
| 로컬 Windows | 871 passed · 5 skipped / 57.35초 | 873 passed · 5 skipped / 51.58초 | 위 둘 + symlink 셋(생성 권한) |

각 리비전에서 세 환경의 총수가 맞는다. **이 파일이 추가한 skip 은 없다** — 어느 쪽 목록에도
설치 검증 테스트가 없으므로 22개가 양쪽에서 실제로 실행됐다. 지원 대상 검사가 환경 부재로
skip 되면 미완료라는 기준을 이로써 충족한다.

**플랫폼 가드가 하나도 필요하지 않았다.** 특히 `설치 사본` 처럼 공백과 한글이 든 경로, 공백이
든 probe 파일 이름, 한글 인자, `{mapped_targets}` 가 내는 상대 경로가 Linux 에서도 그대로
통과했다. 그 넷은 이 머신에서만 검증됐던 자리다.

**이 20개의 비용은 Windows 쪽에서만 분명하다.** 세 번의 CI 관측값(테스트 수: 초):

| OS | 856 | 876 | 878 | 자기 흩어짐 |
|---|---:|---:|---:|---:|
| Ubuntu | 13.76 | 16.01 | **12.14** | 3.87초 |
| Windows | 19.56 | 35.47 | 36.55 | 16.99초 |

- **Windows**: 856 → 876 에서 **+15.91초**, 그 뒤 +2건에 +1.08초다. 증가가 테스트 수와 같은
  방향으로 단조롭고 큰 계단이 20개 추가 지점과 겹친다 — **실제 비용으로 읽는다.**
- **Ubuntu**: +2.25초로 봤던 증가가 **자기 흩어짐(3.87초)보다 작다.** 테스트가 가장 많은
  878건 실행이 **가장 빨랐다**(12.14초). 그래서 Ubuntu 쪽 증가는 잡음과 구분되지 않는다.

따라서 **처음 적었던 「약 7배」는 철회한다.** 한쪽이 잡음 범위면 비율을 만들 수 없다. 남는
진술은 「Windows CI 에서 약 16초가 늘었고, Ubuntu 에서는 측정되지 않았다」다. 원인(프로세스
생성 비용)은 여전히 **후보이고 떼어 재지 않았다.**

**이 문서의 시간 수치가 세 번째로 수정됐다.** 단일 관측 한 쌍으로 배율을 적으면 다음 관측이
그것을 뒤집는다 — 이 저장소에서 세 번 그랬다. 그래서 여기서는 **범위와 관측 횟수**를 적고,
비율은 각 OS 의 자기 흩어짐보다 큰 차이에만 쓴다.

## 한계와 재지 못한 것

- **로컬 측정은 Windows 한 환경, 한 세션이다.** Linux 는 위 CI 가 쟀고, 그 로그의 수치는
  Claude 가 읽은 job 로그 하나에 근거한다.
- **실제 세션의 이벤트 전달과 신뢰 승인은 검증하지 않았다.** 합성 payload 를 훅에 직접
  넘긴 것이고, Claude Code·Codex 가 그 payload 를 보낸다는 사실은 이 검증의 범위가 아니다.
- **누출 재현에 실제 소스 저장소를 쓰지 않았다.** 엉뚱한 환경변수 검사는 decoy 프로젝트를
  가리키게 했다 — 소스를 가리키면 누출이 났을 때 소스의 활성 Profile 이 돌아 전체 테스트가
  시작되고, 실패가 느려지며 원인도 흐려진다. decoy 는 대신 trace 파일로 즉시 드러난다.
- **설치물에 `.venv` 를 만들어 재지 않았다.** `python` 설정 키로 인터프리터를 지정했다.
  설치 프로젝트가 자기 venv 를 만드는 경로는 여전히 미검증이다.
- RAG 제품 실행·외부 API·임베딩·실제 사용자 노트는 쓰지 않았다. quiz·openwork 입력은 전부
  synthetic 이다.
- 깨진 배선은 **훅 파일 하나를 지우는 방식** 하나만 쟀다. 배선 문자열을 틀리게 고치는 변형은
  재지 않았다.

## 다시 재는 방법

```text
python -m pytest tests/test_template_install.py -q -rs
python .claude/harness/scripts/run_quality.py --profile full --require-venv
```

두 OS CI 로그에서는 **건수가 아니라 테스트별 skip 사유**를 본다. 이 파일의 검사는 전부
이식 가능해야 하므로, 어느 것이든 capability 실패로 skip 되면 그 자리는 미검증이다.

## Knowledge 반영

`template-layout.md` 의 「보장하지 않는 것」에서 인터프리터·훅 실행 미검증 문장을 좁히고,
남는 것(실세션 이벤트 전달, 설치물 자신의 venv)만 적는다. 루트 해석 세 갈래는 테스트
모듈의 docstring 이 소유한다.
