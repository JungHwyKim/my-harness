# my-harness

개인용 Claude Code 하네스. **비공개 마켓플레이스 하나에 플러그인 셋**이 들어 있다.

`agentic-rag-proj` 안에서 자란 것을 2026-09-10 에 뽑아냈다. 뽑은 이유는 사본을 늘리는
방식이 이미 갈렸기 때문이다 — 같은 하네스의 Codex 사본(`.codex/hooks/`)이 7개 중 5개가
달랐고 둘은 아예 없었다.

| 플러그인 | 무엇이 들었나 | 언제 켜나 |
|---|---|---|
| `harness-core` | 훅 9개 + 기록 스킬 4(plan-log·task-log·verify-log·plan-interview) + 도구 스킬 2(openwork·code-tracker) | 어느 프로젝트에서나 |
| `harness-rag` | rag-code-review·document-ingestion·regression-test 스킬 + 에이전트 4 | `rag_pipeline/` 같은 구조가 실재하는 저장소에서만 |
| `quiz` | 면접 노트 연습 도구 | 저장소와 무관 (노트 폴더를 읽는다) |

## 프로젝트마다 갈리는 값은 `.claude/harness.json` 이 답한다

훅에는 저장소 이름이 하나도 안 박혀 있다. 테스트 매핑표·소스 접두사·위키 뿌리·린트와
테스트 명령을 프로젝트가 자기 `.claude/harness.json` 으로 준다.

**절이 없으면 그 검사는 안 돈다.** 기본값으로 조용히 도는 쪽이 더 나쁘다 — 남의 저장소
경로로 pytest 를 돌리거나, 반대로 *검사가 도는 줄 알았는데 안 도는* 상태가 아무 에러 없이
생긴다. 본보기는 `agentic-rag-proj/.claude/harness.json` 이다.

## 설치

```bash
claude plugin marketplace add <이 저장소 경로 또는 GitHub 주소>
claude plugin install harness-core@junghwy-harness --scope project
```

`--scope project` 면 **어느 프로젝트가 무엇을 켰는지가 그 프로젝트 설정에 글로 남는다.**
개발 중에는 설치 없이 `claude --plugin-dir <플러그인 경로>` 로 띄운다.

## 고칠 때

훅을 고치면 **여기 pytest 를 돌린다.** 그 보장이 이 저장소로 함께 옮겨 왔다 —
프로젝트 쪽 pytest 는 더 이상 훅을 안 지킨다.

```bash
python -m pytest tests -q
claude plugin validate ./plugins/harness-core --strict
```

프로젝트 쪽에 남은 검사는 **설정이 그 저장소와 맞나** 하나다
(`agentic-rag-proj/tests/harness/test_harness_config.py`).

## 알아 둘 것

- **`CLAUDE_PROJECT_DIR` 는 저장소 뿌리가 아니라 세션을 띄운 폴더다**(실측). 뿌리는 거기서
  `.claude/` 를 가진 폴더까지 올라가 찾는다 — `_hookutil._find_root()`
- **git 을 뿌리 표시로 안 쓴다.** `.git` 이 없는 프로젝트가 실재한다
- **세션 마커는 `CLAUDE_PLUGIN_DATA` 아래**에 산다. 프로젝트를 안 더럽히고 git 여부를 안 탄다
- 훅 9개는 전부 표준 라이브러리만 쓴다. 프로젝트 venv 는 훅이 **부르는** pytest·ruff 에만 필요하고
  그 경로는 `harness.json` 의 `python` 이 준다
