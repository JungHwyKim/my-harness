# 검증용 가상환경과 의존성 구성

- 작업 ID: `quality-env-setup`
- 상태: 기존 리뷰에 환경 구축 완료 보고됨 · Full 검증 실패 · 최종 리뷰 대기
- 명세: `tasks/quality-env-setup.md`
- 후속 리뷰: `tasks/quality-env-setup.review.md`
- 기존 실행 기록: `tasks/handoff.review.md`의 `Round 2 — verification environment`
- 이관 원본: `tasks/handoff.md:26`의 환경 구축 항목
- 선행 작업: 없음. 기존 환경 구축 작업을 식별자별 문서로 정리한 것이다.

## 목적

가상환경·개발 의존성 구성 작업을 범용 `handoff.md`에서 분리해 독립된 작업 ID로 관리한다.
기존 구현과 실행 기록은 유지하며, 이 파일 생성만으로 끝난 작업을 다시 수행하지 않는다.

## 실행 계약

- 기존 Claude 작업이 진행 중이면 그 세션은 전달받은 명세와 리뷰 경로로 마친다.
  이 문서는 진행 중인 세션의 기준을 바꾸거나 재시작하는 지시가 아니다.
- 이관 후 이 주제의 추가 보고는 `tasks/quality-env-setup.review.md`에 남기고,
  기존 결과는 원래 리뷰의 해당 절을 참조한다. 기존 리뷰를 복사하거나 덮어쓰지 않는다.
- 가상환경 경로는 `.venv/Scripts/python.exe`다. 설치·검증에는 이 인터프리터를 직접 쓴다.
- 다음 명령은 기존 환경 구성·검증 계약이다. 완료된 설치나 검사를 문서 분리 때문에
  반복하지 않는다. 변경이 생기거나 추가 검증이 필요할 때 해당 명령만 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

## 범위와 제외

- 포함: 검증용 `.venv/`, 직접 개발 의존성의 버전 고정, `.venv/`의 Git 제외,
  README의 설치·Full 검사 안내, 환경 구성 결과와 검사 결과의 구분.
- 제외: 기존 린트·포맷·테스트 실패 수정, 검사 규칙 완화, 훅·유료 테스트 승인 변경,
  CI·추적 경로 확대, 전역 Python 변경, 기존 가상환경 삭제, Git 커밋·푸시.
- 템플릿 배포와 초기 History 정리는 `tasks/template-history-cleanup.md`가 소유한다.
- `tasks/handoff.md`와 기존 리뷰는 이 문서 분리 과정에서 수정·개명·삭제하지 않는다.

## 기존 코드 근거

- `.claude/harness.json:4`는 검증 인터프리터를 `.venv/Scripts/python.exe`로 지정한다.
- `.claude/harness.json:41`, `:46`, `:51`은 Full의 린트·포맷 검사·전체 pytest 명령이다.
- `.claude/harness.json:14`의 추적 경로에는 이번 환경·설치 문서 파일이 없다.
- `tasks/handoff.review.md:159`의 환경 결과 표는 설치와 `pip check`, Git 제외 확인이
  통과했다고 보고한다. 이 문서를 작성하면서 Codex가 같은 검사를 다시 실행한 것은 아니다.
- `tasks/handoff.review.md:186`은 Full 세 단계가 모두 실행됐고 실패했다고 보고한다.

## 구현 범위와 현재 보고 상태

| 대상 | 기존 작업의 계약 | 기존 리뷰의 보고 |
|---|---|---|
| `.venv/` | 저장소 전용 Python 환경을 만들고 정상 환경은 재사용한다. | Python 3.12.5, 설정된 경로에 생성 완료 |
| `requirements.txt` | 전역 freeze를 복사하지 않고 실제 검증한 pytest·ruff 직접 의존성 버전을 고정한다. | `pytest==9.2.0`, `ruff==0.17.5`, 파일로 재설치 성공 |
| `.gitignore` | 기존 항목을 유지하며 `.venv/`를 제외한다. | 제외 확인 완료 |
| `README.md` | 환경 생성, requirements 설치, Full 각 단계의 명령을 안내한다. | 안내 추가 완료 |
| Full 검사 | 린트·포맷 검사·pytest의 결과와 종료 코드를 각각 기록한다. | 린트 11건, 포맷 대상 23파일, 테스트 14실패·321통과로 보고됨 |

1. 이 주제의 작업을 이어받으면 먼저 기존 리뷰의 Round 2를 읽고, 현재 파일과 변경 상태를
   확인한다. 완료된 설치를 새 구현 항목으로 되돌리지 않는다.
2. 실제 추가 검증이 필요하면 해당 결과와 사용한 Python·pytest·ruff 버전, 종료 코드,
   통과·실패·건너뜀 수를 이 작업의 후속 리뷰에 적는다.
3. 기존 리뷰의 F5·F6은 별도 코드·품질 수정 대상으로 남긴다. 이 문서 분리를 이유로
   저장소를 자동 포맷하거나 유료 테스트 마커·훅 동작을 변경하지 않는다.

### 심각도와 종료 코드

설치와 `pip check`는 종료 코드 0이어야 환경 구축 성공이다. Full은 세 단계 모두
종료 코드 0이어야 통과다. 실행 실패·미실행을 통과로 표시하지 않는다.

### 열거해야 할 표

위 구현 범위·보고 상태 표를 따른다. 환경 구축 성공과 Full 통과를 별도로 판정한다.

### 호환성

기존 검증은 Windows 로컬 환경에 대한 보고다. Linux와 CI는 검증하지 않았다면 미검증으로
남긴다. requirements는 현재 작업에서 검증한 ASCII 형태를 유지한다. 대상 프로젝트별
설치·배포 안내는 별도 템플릿 준비 명세에서 다룬다.

### 보안·비용 경계

필요한 패키지 다운로드 외 유료 API 실행을 포함하지 않는다. 가상환경 내부만 설치 대상으로
삼고, 전역 패키지·기존 환경을 임의로 지우거나 변경하지 않는다.

## 구현 및 검증

- 환경 구축 통과 기준: 설정된 가상환경의 인터프리터를 사용하고, 고정 requirements 설치와
  `pip check`가 성공하며, `.venv/`는 제외되고 requirements와 README는 제외되지 않는다.
- Full 검증 통과 기준: 린트·포맷 검사·전체 pytest가 모두 종료 코드 0이다.
- 문서 분리 자체에는 실행 코드를 추가하지 않으므로 전용 테스트나 전체 검사 재실행을
  요구하지 않는다. 현재 보고의 실패 항목은 계속 표시한다.

## 완료 기준

- 환경 구축 결과와 Full 실패가 구분되어 있고, 설치 성공을 전체 검증 성공으로 표현하지 않는다.
- 기존 리뷰의 실행 증거로 연결되며, 필요 없는 재설치·검사 반복이나 기존 코드 변경이 없다.
- 추가 보고는 작업 ID에 맞는 리뷰에 남는다. 최종 리뷰와 보존 전에는 원본 기록을 지우지 않는다.
