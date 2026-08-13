# Worktree lifecycle contract

Worktree는 임시 디렉터리가 아니라 아직 main과 합쳐지지 않은 작업의 소유면이다. 따라서 디렉터리가 clean하다는 이유만으로 제거하지 않는다. **작업 내용의 운명을 먼저 결정하고, main 통합 또는 원격 보존을 기계로 증명한 뒤에만 worktree를 제거한다.**

## 상태 전이

```text
ACTIVE
  -> DISPOSITIONED   dirty path와 unique commit을 preserve 또는 stale로 분류
  -> RECONCILED      preserve는 main 통합 또는 검증된 remote archive, stale은 승인 후 제거
  -> RETIRABLE       retirement_gate receipt가 PASS
  -> REMOVED         git worktree remove, branch ref는 별도 수명주기
```

`tools/fleet/retirement_gate.py`는 `RECONCILED -> RETIRABLE`만 판정하는 read-only module이다. 파일을 삭제하거나 branch를 이동하지 않는다.

## Interface

```powershell
python tools/fleet/retirement_gate.py check `
  --worktree D:\runs\wt\autocad-sdk-router__lane `
  --main-ref origin/main
```

출력은 `ariadne.cados.worktree_retirement.v1` JSON receipt다.

- `PASS`: 제거 자격이 있다. `eligible_for_removal=true`이고 모든 강제 check가 참이다.
- `BLOCKED`: 제거하면 안 된다. `dirty_paths`, `unique_commits`, `weakened_index_entries`, `lock_reason`과 typed `reason_codes`로 남은 일을 찾는다.

PASS에는 다음 사실이 모두 필요하다.

1. Git에 등록된 secondary worktree다. primary worktree는 이 경로로 제거하지 않는다.
2. worktree가 unlocked다.
3. tracked·untracked 변경이 0개다.
4. ignored 파일이 0개다. build/log/cache도 제거 전에 stale 또는 preserve로 판정해야 한다.
5. `assume-unchanged`와 `skip-worktree`로 숨긴 index entry가 0개다.
6. HEAD의 내용이 main에 통합됐거나, 아래 원격 보존 계약을 충족한다.
7. 시작과 종료의 HEAD, main commit, status, ignored content, worktree registry, index visibility 및 원격 보존 SHA가 동일하다.
8. 모든 Git 관측 명령이 stderr 경고 없이 완료된다. 접근거부 등으로 열거가 불완전하면 exit 0이어도 BLOCKED다.

main 통합은 둘 중 하나로 증명한다.

- exact ancestry: worktree HEAD가 main commit의 조상이다.
- patch equivalence: exact ancestry는 아니지만 `git cherry` 기준으로 main에 없는 non-merge patch가 0개다. unresolved merge commit은 patch-equivalent로 승격하지 않는다.

다중 commit을 하나로 squash하면서 patch-id가 보존되지 않은 경우에는 보수적으로 BLOCKED가 될 수 있다. 그때는 변경을 main 위에 명시적으로 재결속하거나 원격 archive로 보존한다. 수동으로 PASS를 덮어쓰지 않는다.

## Preserve or stale disposition

gate를 실행하기 전에 `dirty_paths`, `ignored_paths`, `unique_commits` 각각을 다음 둘 중 하나로 판정한다.

- **preserve**: main에 merge/cherry-pick/rebase해 통합한다. main에 속하지 않는 역사 증거라면 remote archive branch로 push하고 아래 방식으로 검증한다.
- **stale**: 현재 판단에 쓰이지 않고 재현·감사에도 필요 없다는 근거를 ticket, PR 또는 handoff에 남긴 뒤 제거한다. uncommitted 파일 삭제나 branch reset은 되돌리기 어려우므로 실행 전에 정확한 대상과 승인을 다시 확인한다.

local branch나 local tag만 남기는 것은 보존으로 인정하지 않는다. 원격 archive를 쓰려면 exact HEAD를 remote branch에 push하고 fetch한 remote-tracking ref를 전달한다.

```powershell
git push origin HEAD:refs/heads/archive/worktree/<lane>
git fetch origin `
  refs/heads/archive/worktree/<lane>:refs/remotes/origin/archive/worktree/<lane>

python tools/fleet/retirement_gate.py check `
  --worktree <absolute-worktree-path> `
  --main-ref origin/main `
  --preservation-ref refs/remotes/origin/archive/worktree/<lane>
```

gate는 `git ls-remote`의 실제 remote SHA가 local remote-tracking SHA와 일치하고, 그 commit이 exact worktree HEAD를 포함하는 경우에만 `head_preserved=true`를 낸다. 이름만 `refs/remotes/...`인 로컬 위조 ref는 BLOCKED다.

## Removal

receipt가 PASS이고 사용자가 해당 absolute path 제거를 승인한 뒤에만 실행한다.

```powershell
git -C <primary-repo> worktree remove -- <absolute-worktree-path>
git -C <primary-repo> worktree prune
```

- `--force`를 사용하지 않는다.
- raw filesystem 삭제를 사용하지 않는다.
- 제거 직전에 같은 command로 gate를 다시 실행한다.
- worktree 제거와 branch 삭제는 별개다. branch 삭제는 main/remote reachability를 다시 확인하고 별도 파괴적 작업 승인을 받은 뒤 처리한다.

## What the gate does not prove

gate는 어떤 내용이 stale인지 과학적·제품적으로 판단하지 않는다. 그 판단은 사람의 disposition record가 맡는다. gate가 증명하는 것은 **판정이 끝난 뒤 worktree에 미분류 bytes가 남지 않았고, 보존하기로 한 commit이 main 또는 실제 remote에 도달했으며, 관측 중 상태가 변하지 않았다**는 사실이다.
