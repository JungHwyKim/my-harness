# `.codex/`와 `.agents/`를 추적하지 않고 제외를 명시한다

- 날짜: 2026-11-19
- 상태: 승인
- 영향 범위: 저장소가 배포하는 파일 목록, `.gitignore`, Codex 쪽 훅 설정의 보관 위치,
  `tasks/template-history-cleanup.md`의 배포 구분 작업

## 결정할 문제

작업 트리에 다른 에이전트용 폴더가 둘 있는데 **둘 다 Git 밖에 있었다.** 그런데
`.gitignore`의 어느 패턴도 둘을 잡지 않았다 — `__pycache__/`·`*.py[cod]`·
`.pytest_cache/`·`.ruff_cache/`·`.venv/`가 전부다. `git check-ignore`도 아무것도 내지
않았다. 즉 **「의도적으로 뺀 것」과 「그냥 add 하지 않은 것」이 구분되지 않는 상태**였다.

이 저장소에서 그 구분은 말장난이 아니다. 인수인계 절차가 「추적되지 않는 파일에는
되돌릴 이력이 없다」를 보존 조건으로 못 박아 두었고(`tasks/template-history-cleanup.md`
구현 범위 3항: *"미추적 파일이나 스테이징 상태만으로 Git에 보존됐다고 판단하지 않는다"*),
직전 `hook-dicision` 작업에서 그 조건이 실제로 발동했다. `.codex/hooks.json`에서 비용 훅
항목을 뺀 변경이 커밋 `860fd7b`에 들어가지 못했고, 지금 그 파일의 내용은 Git에 보존된
이력이 없다. `tasks/hook-dicision.review.md`가 그 사실을 한 번 반대로 적었다가
정정하기도 했다 — *"The whole `.codex/` directory is untracked, so a clone receives
neither the directory nor any Codex hook configuration."*

그래서 둘을 추적할지부터 정해야 했다.

## 검토한 선택지

1. 두 폴더를 그대로 추적한다. Codex 쪽 설정도 저장소에서 리뷰할 수 있게 된다.
2. `.codex/hooks.json` 하나만 추적한다. 치환 흔적이 없는 유일한 파일이고, 훅 배선은
   하네스의 일부라고 볼 수 있다.
3. 둘 다 추적하지 않고, 제외를 `.gitignore`에 명시한다.
4. 치환 흔적을 먼저 고치고 나서 추적한다.

## 결정

선택지 3을 고른다. `.agents/`와 `.codex/`를 `.gitignore`에 올리고, **왜 뺐는지**를
항목 위 주석에 적어 「의도적으로 뺀 것」임을 파일에서 바로 읽히게 한다.

두 폴더를 함께 처리하되 **이유는 서로 다르다.** 같은 결론에 이른 경로를 아래에 나눠 적는다.

## 이유

### `.agents/`는 `.claude/skills/`의 깨진 사본이다

스킬 이름 목록이 `.claude/skills/`와 완전히 같고, 12개 중 11개가 내용이 다르다. 다른
부분이 전부 같은 모양이다 — **`.claude/`를 `.Codex/`로 치환한 흔적이 45곳** 남아 있다.
그 경로가 가리키는 `.codex/harness.json`·`.codex/wiki/`·`.codex/skills/`는 **하나도
존재하지 않는다**(`.codex/`에는 `agents/`와 `hooks.json`만 있다). Windows가
대소문자를 가리지 않아 `.Codex`가 `.codex`로 풀리는 것뿐이고, 풀린 경로에 파일이 없다.

배선도 되어 있지 않다. Codex의 진입점인 `AGENTS.md`는
`.claude/skills/<name>/SKILL.md`를 읽으라고 적고 있고, 추적 파일 어디에서도 `.agents/`를
참조하지 않는다. 즉 **아무도 읽지 않는, 경로가 죽은 낡은 사본**이다.

이 저장소의 목적이 하네스를 다른 프로젝트로 배포하는 것이므로, 이것을 추적하면 죽은
경로를 적용 대상마다 함께 뿌린다. 추적할 값이 없다.

### `.codex/`는 추적하면 같은 사실을 두 곳이 다르게 들고 있게 된다

`.codex/hooks.json`은 `.claude/settings.json`의 `hooks` 블록을 **거의 그대로
중복한다** — 같은 스크립트, 같은 matcher, 같은 timeout, 같은 statusMessage다. 다른 점은
`paid_test_check.py` 항목이 없는 것 하나뿐이고, 그 차이는 의도된 것이다
(`knowledge/paid-test-approval.md`: Codex의 `PreToolUse`가 `ask`를 지원하지 않아
배선해 두면 보호가 없는데 있는 것처럼 보인다).

문제는 추적된 문서가 **그 반대를 명시**한다는 것이다.

- `AGENTS.md`: *"`.claude/settings.json`의 Claude Code 훅은 Codex에서 자동으로
  실행되지 않는다"* — 그래서 Quality Profile을 **직접** 실행하라고 안내한다.
- `README.md`: 같은 내용을 Codex 사용 절에 다시 적는다.

`.codex/hooks.json`을 추적하면 저장소에 「Codex는 훅이 자동 실행되지 않으니 직접
실행한다」와 「Codex 훅은 이렇게 배선되어 있다」가 **동시에** 들어간다. `CLAUDE.md`의
Information Ownership이 금지하는 모양 그대로다. 실제로 이미 한 번 갈렸다 —
비용 훅 항목 하나가 한쪽에만 있다.

`.codex/agents/`의 네 `.toml`은 `.claude/agents/`의 네 `.md`를 Codex 형식으로 옮긴
진짜 번역본이다(YAML frontmatter 대신 `developer_instructions`). 그런데 그중 둘
(`ingestion-specialist` 9곳, `retrieval-specialist` 8곳)이 `.agents/`와 **같은 `.Codex/`
치환 흔적**을 갖고 있다. 폴더 전체를 추적하면 같은 깨진 경로를 함께 뿌린다.

## 기각한 대안

- **선택지 1(둘 다 추적).** 위 두 이유가 그대로 비용이 된다. 죽은 경로 62곳
  (`.agents/` 45 + `.codex/agents/` 17)과 계약 충돌을 한꺼번에 배포한다.
- **선택지 2(`hooks.json`만 추적).** 치환 흔적 문제는 피하지만 계약 충돌은 그대로
  남는다. 중복이 가장 심한 파일이 정확히 이 파일이다. 더해서 「배포 대상 파일 구분」은
  `tasks/template-history-cleanup.md`가 소유한 범위이고(상태: 구현 대기),
  `tasks/hook-dicision.review.md`도 `.codex/` 추적 여부를 그 작업으로 넘겼다.
  일부만 먼저 추적하면 그 작업의 판단을 미리 묶는다.
- **선택지 4(고치고 나서 추적).** 이 작업의 범위가 아니다. 사용자가 「추적할지」만
  정하라고 범위를 잘랐고, `.codex/hooks.json`의 내용은 손대지 않기로 확인했다. 그리고
  치환 흔적을 고쳐도 계약 충돌은 남으므로, 고치는 것만으로 추적 근거가 서지 않는다.

## 영향과 후속 조건

- **Codex의 훅 설정은 머신마다 따로 남고 저장소에서 리뷰할 수 없다.** 이 비용은
  받아들였다. 클론은 `.codex/`를 받지 않으므로 낡은 배선을 물려받지도 않는다.
- `.gitignore`는 이미 추적된 파일을 제거하지 않는다. 두 폴더는 원래 미추적이라
  이 변경으로 사라지는 이력이 없다.
- 제외 범위가 정확한지 확인했다. 두 폴더만 잡히고 `.claude/skills/`·`requirements.txt`·
  `tasks/_template.md`·`.claude/harness.json`은 잡히지 않는다.
- 뒤집으려면 `.gitignore` 항목을 지우는 것으로는 부족하다. 치환 흔적 62곳을 고치고,
  `AGENTS.md`·`README.md`의 「Codex에서 훅은 자동 실행되지 않는다」와의 충돌을 먼저
  해소해야 한다. 그 판단은 `tasks/template-history-cleanup.md`에 속한다.
- `.agents/skills/quiz/SKILL.md`에 사용자 홈 경로가 있지만, **같은 줄이 추적된
  `.claude/skills/quiz/SKILL.md:34`에도 이미 있다.** 이 결정이 만든 문제가 아니므로
  여기서 다루지 않는다. 별도 항목으로 남긴다.

## Knowledge 반영

`knowledge/paid-test-approval.md`의 Codex 항목이 `.codex/hooks.json`을 저장소 파일처럼
가리키고 있었다. 그 파일이 배포되지 않는다는 현재 계약 한 줄을 더해, 저장소만 읽는
사람이 없는 파일을 찾지 않게 한다. 그 외에 새로 추가할 계약은 없다 — 이 결정의 결과는
`.gitignore` 자체가 들고 있다.
