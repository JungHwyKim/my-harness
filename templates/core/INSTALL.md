# 하네스 설치 안내

이 파일은 **설치된 하네스를 이 프로젝트에 맞추는 방법**을 소유한다. 하네스는 별도 디렉터리로
내보낸 사본이며, 원본 저장소의 README·개발 History·원격 ref에 접근할 수 있다고 전제하지
않는다. 여기 적힌 것만으로 설정을 마칠 수 있어야 한다.

맞춘 뒤에는 이 파일을 지우지 말고 둔다 — 활성화 절차와 훅의 적용 조건을 다시 볼 자리다.

## 1. 설치 직후 할 일

1. `python .claude/harness/scripts/doctor.py`를 돌려 설정 결선을 확인한다.
   설치 직후에는 **WARN이 남는 것이 정상**이다(아래 3절).
2. `CLAUDE.md`의 **Purpose**를 이 프로젝트의 목적으로 바꾸고,
   `.claude/wiki/overview/README.md`에 이 프로젝트의 구조를 적는다.
3. Quality Profile을 구성한다(아래 4절). 구성하기 전까지 자동 검사는 돌지 않는다.
4. 기존 파일과 겹치는 것이 있으면 아래 6절의 병합 안내를 따른다.

## 2. 무엇이 설치됐는가

| 경로 | 무엇인가 |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | 에이전트 진입점 |
| `HARNESS-INSTALL.md` | 이 파일 |
| `.gitignore` | 생성물과 로컬 전용 폴더 제외 |
| `.claude/harness.json` | Quality·History 설정. **설치 직후 비활성** |
| `.claude/settings.json` | Claude Code 훅 배선 |
| `.claude/harness/hooks/` | 훅 스크립트 9개 |
| `.claude/harness/scripts/` | Doctor, 수동 Quality CLI, openwork 수집기 |
| `.claude/harness/schemas/` | `harness.json` 스키마 |
| `.claude/skills/` | 공통 절차 7개 |
| `.claude/wiki/` | overview · knowledge 3문서 · history 세 폴더 |
| `tasks/_template.md` | 작업 명세 템플릿 |

`.claude/wiki/history/`의 세 폴더는 비어 있다. 원본 저장소의 개발 기록은 따라오지 않는다.

## 3. 설치 직후 점검 — Doctor

```text
python .claude/harness/scripts/doctor.py
```

읽기 전용 정적 진단이다. 명령을 실행하지 않고 설정 파일만 본다. 종료 코드는 `0`(FAIL 없음,
WARN만 있어도 0), `1`(FAIL 하나 이상), `2`(진단을 못 마침)다.

**설치 직후의 WARN은 결함이 아니다.** 비어 있는 Profile과 추적 목록은 스키마가 허용하는
상태이므로 WARN으로 적히고 종료 코드는 0이다. 그 0을 「검사가 통과했다」로 읽지 않는다 —
아직 돌릴 검사가 없다는 뜻이다.

**미검사는 PASS가 아니다.** 범위와 보장하지 않는 것은
`.claude/wiki/knowledge/doctor.md`가 소유한다.

## 4. Quality는 설정 전까지 비활성이다

`.claude/harness.json`의 `fast`·`full`은 `triggers: []`, `stages: []`로 설치된다.

- 자동 검사가 돌지 않는다.
- `python .claude/harness/scripts/run_quality.py --profile full`을 부르면 **설정 결함으로
  종료 코드 2**가 난다. 빈 Profile을 성공으로 인정하지 않는 것이 공통 엔진의 계약이다.
  이 호출을 설정 전 상태의 완료 조건으로 삼지 않는다.
- 비활성을 검증 통과로 보고하지 않는다.

활성화 절차와 stage 작성법, 수동 실행과 종료 코드, 선택 플래그 `--require-venv`는
`.claude/wiki/knowledge/quality-env.md`가 소유한다. 언어·도구는 이 프로젝트가 정하며
lint·format·pytest가 모든 프로젝트의 필수 단계는 아니다.

## 5. 기본 설치에서도 적용되는 훅

**Quality가 비활성이라는 말이 모든 훅이 꺼졌다는 뜻은 아니다.** `settings.json`이 연결하는
고유 스크립트는 9개이고, 그중 셋은 설정과 무관하게 동작한다. 아래 표가 설치 직후의 상태다.

| 훅 | 기본 설치에서의 조건 | 이유와 대응 |
|---|---|---|
| `heredoc_write_check.py` | 설정과 무관하게 셸 호출 전에 검사. Bash의 **파일 쓰기** heredoc과 백슬래시가 섞인 본문, PowerShell의 **파일 쓰기** here-string을 차단 | 도구 계층에서 관측된 파일 생성 실패와 백슬래시 손상을 피하기 위한 보호다. 파일은 Write/Edit로 만들고, 스크립트는 파일로 저장해 실행한다. 모든 heredoc·here-string을 금지하는 것은 아니다 — 백슬래시 없는 짧은 `python <<PY`의 stdout 출력이나 파일을 만들지 않는 here-string은 지나간다. 예외가 필요하면 훅 프로세스가 받는 환경에 `SKIP_HEREDOC=1`을 두고, 쓴 뒤에 지운다. 도구 명령 안에서 설정하는 것으로는 이미 시작된 검사가 풀리지 않는다 |
| `plan_interview_check.py` | Quality 설정·Skill 호출과 무관. 준비 마커 없이 계획을 확정하려 하면 차단 | 계획을 사용자와 합의하고 나서 확정하자는 절차다. 기존 게이트 문구나 질문 응답 경로로 준비 마커를 만든다. 예외는 `SKIP_PLANINTERVIEW=1` |
| `history_check.py` | 세션 상태에 따라 검사. **기록 Skill을 부르면 빈 설정에서도 기록 의무가 생긴다** | 중요도 판단과 요청된 기록을 확인한다. `history-significance`로 판단하고, 필요하면 `plan-log`·`task-log`·`verify-log`로 실제 기록을 쓴다. 예외는 `SKIP_HISTORY=1`. 추적 목록이 비어 있다는 이유로 항상 비활성이라고 보지 않는다 |
| `paid_test_check.py`, `auto_test_check.py`, `pre_commit_check.py` | 빈 유료 마커와 빈 Profile에서는 **비활성** | 프로젝트 설정으로 활성화한 뒤의 유료 승인·테스트·커밋 게이트다. 기본 설치에서 검사를 통과했다는 뜻이 아니다 |
| `prose_style_check.py` | `checks.prose_style`이 설정에 없어 **비활성** | 원본 저장소의 문체 정책을 이 프로젝트에 자동 적용하지 않는다. 쓰려면 그 섹션을 직접 설정한다 |
| `plan_log_check.py`, `task_log_check.py` | 스키마 V2에서는 조기 반환하는 **V1 호환층** | V2의 기록 검사는 `history_check.py`가 소유한다. V1 지원이 필요한 설정을 위해 배선은 남겨 둔다 |

`settings.json`의 훅은 **Claude Code의 계약**이다. Codex에서는 자동으로 실행되지 않으므로,
그쪽에서는 `AGENTS.md`의 안내대로 필요한 검사를 수동으로 돌린다.

## 6. 기존 파일과 겹칠 때

내보내기는 **새 디렉터리**를 만들고 기존 프로젝트를 고치지 않는다. 이미 같은 이름의 파일이
있으면 다음을 직접 비교해 옮긴다. 자동 병합·덮어쓰기는 제공하지 않는다.

| 파일 | 권하는 방법 |
|---|---|
| `CLAUDE.md`, `AGENTS.md` | 기존 내용을 남기고 하네스 쪽의 Router·Quality 안내 항목만 더한다 |
| `.gitignore` | 겹치지 않는 줄만 덧붙인다 |
| `.claude/settings.json` | 훅 배열을 **합친다**. 같은 matcher 아래 명령을 나란히 둔다 |
| `.claude/harness.json` | 설정이 이미 있으면 Profile·추적 경로를 비교해 필요한 항목만 가져온다 |
| `.claude/wiki/` | 기존 문서를 지우지 않고 인덱스에 링크를 더한다 |

줄바꿈 정책은 이 프로젝트의 기존 설정을 그대로 둔다. 하네스는 `.gitattributes`를
내보내지 않으므로 기존 정책을 덮지 않는다.

## 7. 선택 구성의 외부 전제

기본 설치에는 RAG 구성과 면접 구성이 **들어 있지 않다.** 필요하면 원본 체크아웃에서
`--pack rag` 또는 `--pack interview`로 다시 내보낸다. 두 구성은 설치물 밖의 것을 전제한다.

- **RAG 구성**: 대상 프로젝트의 제품 코드, 그 프로젝트의 Knowledge 문서, 기준선·평가
  데이터가 있어야 한다. 하네스는 그 파일들을 동봉하지 않으며, 없으면 해당 스킬이 다루는
  검사는 **미검사**다. 필요한 파일을 먼저 준비한다.
- **면접 구성**: 질문 노트는 **외부 입력**이다. 노트와 변환 도구를 동봉하지 않는다.
  노트 폴더는 `QUIZ_NOTE_DIR` 환경변수로 지정하고, 지정하지 않으면 기본 경로를 쓴다.
  노트가 없으면 스킬이 미준비 상태를 알린다. 형식 변환이 필요하면 그 도구는 사용자가
  준비한다.

면접 구성의 스킬은 `${CLAUDE_PROJECT_DIR}` 기준으로 자기 수집기를 부른다. 즉 **그 구성을
내보낸 프로젝트 디렉터리에서 실행**해야 한다. 전역 스킬로 옮기면 그 호출이 깨진다.
구성 자체를 고칠 일이 있으면 원본 저장소의 `packs/interview/`에서 고치고 새 경로로 다시
내보낸다 — 내보낸 사본을 고쳐 별도 원본으로 관리하지 않는다.
