
# my-harness

Claude Code 프로젝트에 그대로 넣어 쓰는 개인용 개발 하네스다. 플러그인 마켓플레이스나
별도 설치는 필요 없다.

```text
CLAUDE.md                항상 필요한 최소 규칙과 Context Router
.claude/settings.json    프로젝트 공용 훅 설정
.claude/skills/          필요할 때 로드되는 작업 절차
.claude/harness/         훅·보조 스크립트·설정 스키마
.claude/wiki/            프로젝트 지도·현재 계약·중요한 결정 이유
```

## 사용 방법

새 프로젝트라면 GitHub의 **Use this template**으로 이 저장소를 만들고, 실제 프로젝트 목적과
도구에 맞게 아래 파일을 채운다.

- `CLAUDE.md`의 Purpose와 Global Rules
- `.claude/harness.json`의 `python`, `quality`, `history.tracked_paths`
- `.claude/wiki/overview/`과 `.claude/wiki/knowledge/`의 프로젝트 정보

이미 있는 프로젝트에 적용한다면 이 저장소에서 **`CLAUDE.md`와 `.claude/` 디렉터리만**
가져온다. 기존 `CLAUDE.md` 또는 `.claude/settings.json`이 있으면 덮어쓰지 말고 규칙과
`hooks` 항목을 병합한다.

Claude Code는 프로젝트의 `.claude/settings.json`에서 훅을 읽고
`.claude/skills/<이름>/SKILL.md`를 프로젝트 스킬로 인식한다. 따라서 저장소를 복제한 뒤
`claude`를 실행하면 별도의 플러그인 설치 없이 동작한다.

## Wiki

```text
overview/   어디에 무엇이 있는가
knowledge/  현재 무엇이 참인가
history/    왜 그렇게 되었는가
```

작업자는 먼저 Overview, 이어서 관련 Knowledge만 읽는다. 과거 결정의 이유가 필요할 때만
History를 검색한다. History는 작업 일지가 아니다.

- 중요한 설계 선택 → `history/plan/`
- 구현 중의 이탈·실패·제약 → `history/task/`
- 비교 가치가 있는 측정·회귀 → `history/verify/`

코드나 설정의 추적 대상이 바뀌면 종료 훅이 `history-significance` 판단을 요구한다.
중요하지 않으면 문서를 만들지 않으며, 중요하다면 알맞은 기록 스킬과 필요한 Knowledge 갱신을
수행한다.

## 검증

```powershell
python -m pytest tests -q
```

훅은 표준 라이브러리만 사용한다. 실제 프로젝트의 lint·test 명령은
`.claude/harness.json`의 Quality Profile에서 정의한다.

## 주의

- `.claude/settings.local.json`은 개인 설정이므로 커밋하지 않는다.
- `.claude/harness.json`의 예시는 Python 프로젝트 기준이다. 다른 언어는 Quality Profile을
  자기 도구에 맞게 바꾼다.
- `history/`는 이슈 트래커나 전체 백로그가 아니다. 열린 작업은
  `checks.openwork.sources`로 별도 정보원을 지정해 관리한다.
