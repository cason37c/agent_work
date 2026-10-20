"""Read-only structural validation and sequential task selection. Python 3.10+."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath


STATUSES = {
    "DRAFT", "READY", "IN_PROGRESS", "IN_REVIEW", "CHANGES_REQUESTED",
    "ACCEPTED", "DONE", "BLOCKED", "CANCELLED",
}
ACTIVE = {"IN_PROGRESS", "IN_REVIEW", "CHANGES_REQUESTED", "ACCEPTED", "BLOCKED"}
CLAIMED = {"IN_PROGRESS", "IN_REVIEW", "CHANGES_REQUESTED", "ACCEPTED", "DONE"}
SUBMITTED = {"IN_REVIEW", "CHANGES_REQUESTED", "ACCEPTED", "DONE"}
DIMENSIONS = {"requirements", "design", "standards", "verification"}
TASK_FIELDS = {
    "id", "title", "status", "priority", "requires", "acceptance_ids", "artifacts",
    "spec_commit", "owner", "branch", "base_commit", "submission_head",
    "implementation_report", "review", "integrated_commit", "integration_evidence",
    "blocked_from", "blocked_reason", "previous_owners",
}


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def string_list(value, label, *, allow_empty=True):
    require(isinstance(value, list), f"{label} must be an array")
    require(all(nonempty(item) for item in value), f"{label} must contain strings")
    require(len(value) == len(set(value)), f"{label} contains duplicates")
    require(allow_empty or bool(value), f"{label} must not be empty")


def git(root, *args, optional=False):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode and not optional:
        raise Invalid(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def load_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Invalid(f"Cannot read {path}: {error}") from error
    require(isinstance(value, dict), f"{path} must contain an object")
    return value


def safe_path(root, value):
    require(nonempty(value), "Repository path must be a nonempty string")
    parts = PurePosixPath(value)
    require(
        not parts.is_absolute() and ".." not in parts.parts
        and "\\" not in value and ":" not in value and value != ".",
        f"Invalid repository-relative path: {value}",
    )
    path = (root / value).resolve()
    require(path.is_relative_to(root.resolve()), f"Path leaves repository: {value}")
    return path


def commit(root, value, label):
    require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value),
        f"{label} must be a full Git SHA",
    )
    git(root, "cat-file", "-e", f"{value}^{{commit}}")


def ancestor(root, older, newer, label):
    require(
        git(root, "merge-base", "--is-ancestor", older, newer, optional=True).returncode == 0,
        f"{label}: {older} is not an ancestor of {newer}",
    )


def blob(root, sha, value):
    safe_path(root, value)
    result = git(root, "cat-file", "-t", f"{sha}:{value}", optional=True)
    require(result.returncode == 0 and result.stdout.strip() == "blob",
            f"File missing at {sha}: {value}")


def validate_review(root, task):
    review = load_json(safe_path(root, task["review"]))
    require(review.get("task_id") == task["id"], "Review task_id mismatch")
    require(nonempty(review.get("reviewer")), "Review needs a reviewer")
    require(review["reviewer"] not in [task["owner"], *task["previous_owners"]],
            "Reviewer must differ from implementer")
    require(review.get("reviewed_head") == task["submission_head"], "Review head mismatch")
    require(review.get("reviewed_base") == task["base_commit"], "Review base mismatch")
    verdict = review.get("verdict")
    require(isinstance(verdict, str) and verdict in {"APPROVED", "CHANGES_REQUESTED", "BLOCKED"},
            "Invalid verdict")
    checks = review.get("checks")
    require(isinstance(checks, dict) and set(checks) == DIMENSIONS,
            "Review needs all four dimensions")
    require(all(isinstance(v, str) and v in {"PASS", "FAIL", "BLOCKED"}
                for v in checks.values()), "Invalid review check result")
    acceptance = review.get("acceptance")
    require(isinstance(acceptance, list) and all(isinstance(a, dict) for a in acceptance),
            "Review acceptance must be an array of objects")
    ids = [a.get("id") for a in acceptance]
    string_list(ids, "Review acceptance ids", allow_empty=False)
    require(set(ids) == set(task["acceptance_ids"]), "Review acceptance coverage mismatch")
    for item in acceptance:
        require(item.get("result") in ("PASS", "FAIL", "BLOCKED")
                and nonempty(item.get("evidence")), "Acceptance needs result and evidence")
    findings = review.get("findings")
    require(isinstance(findings, list) and all(isinstance(f, dict) for f in findings),
            "Review findings must be an array of objects")
    for finding in findings:
        require(nonempty(finding.get("id")) and nonempty(finding.get("evidence")),
                "Finding needs id and evidence")
        require(finding.get("severity") in ("P0", "P1", "P2", "P3"), "Invalid severity")
        require(finding.get("status") in ("OPEN", "RESOLVED", "ACCEPTED"),
                "Invalid finding status")
        if finding["status"] == "ACCEPTED":
            require(finding["severity"] == "P3" and nonempty(finding.get("accepted_reason")),
                    "Only P3 findings with a reason can be accepted")
    if verdict == "APPROVED":
        require(all(v == "PASS" for v in checks.values()), "Approval requires all checks PASS")
        require(all(a["result"] == "PASS" for a in acceptance), "Approval requires all ACs PASS")
        require(all(f["status"] != "OPEN" for f in findings), "Approval has unresolved findings")
    effective = task["blocked_from"] if task["status"] == "BLOCKED" else task["status"]
    if effective in {"ACCEPTED", "DONE"}:
        require(verdict == "APPROVED", "Accepted/completed task needs APPROVED review")
    if effective == "CHANGES_REQUESTED":
        require(verdict == "CHANGES_REQUESTED", "Rework needs CHANGES_REQUESTED review")


def validate_task(root, task, path):
    require(not (TASK_FIELDS - task.keys()),
            f"Missing fields: {sorted(TASK_FIELDS - task.keys())}")
    require(isinstance(task["id"], str) and re.fullmatch(r"T[0-9]{4,}", task["id"]),
            "Task id must be T followed by at least four digits")
    require(path.parent.name == task["id"], "Task directory/id mismatch")
    require(nonempty(task["title"]), "Task needs a title")
    require(isinstance(task["status"], str) and task["status"] in STATUSES, "Invalid status")
    require(type(task["priority"]) is int and task["priority"] >= 0, "Invalid priority")
    string_list(task["requires"], "requires")
    string_list(task["acceptance_ids"], "acceptance_ids", allow_empty=False)
    string_list(task["integration_evidence"], "integration_evidence")
    string_list(task["previous_owners"], "previous_owners")
    require(task["owner"] not in task["previous_owners"], "Current owner duplicated in previous_owners")
    require(isinstance(task["artifacts"], dict)
            and set(task["artifacts"]) == {"requirements", "design", "brief"},
            "artifacts needs requirements, design, brief")
    for value in task["artifacts"].values():
        safe_path(root, value)
    status = task["status"]
    if status == "CANCELLED":
        require(nonempty(task.get("cancellation_reason")), "Cancellation needs a reason")
        return
    if status == "BLOCKED":
        require(nonempty(task["blocked_reason"]), "Blocked task needs a reason")
        require(isinstance(task["blocked_from"], str)
                and task["blocked_from"] in STATUSES - {"BLOCKED", "DONE", "CANCELLED"},
                "Blocked task needs a valid blocked_from")
    else:
        require(task["blocked_from"] is None and task["blocked_reason"] is None,
                "Nonblocked task must clear blocker fields")
    effective = task["blocked_from"] if status == "BLOCKED" else status
    if effective == "DRAFT":
        return
    commit(root, task["spec_commit"], "spec_commit")
    ancestor(root, task["spec_commit"], "HEAD", "Spec must belong to control history")
    for value in task["artifacts"].values():
        blob(root, task["spec_commit"], value)
    for key in ("requirements", "brief"):
        content = git(root, "show", f"{task['spec_commit']}:{task['artifacts'][key]}").stdout
        for ac in task["acceptance_ids"]:
            require(re.search(r"(?<![\w-])" + re.escape(ac) + r"(?![\w-])", content),
                    f"{key} does not describe {ac}")
    if effective in CLAIMED:
        require(nonempty(task["owner"]), "Claimed task needs owner")
        branch = task["branch"]
        require(nonempty(branch) and branch.startswith(f"task/{task['id']}-"),
                "Invalid task branch")
        git(root, "check-ref-format", "--branch", branch)
        commit(root, task["base_commit"], "base_commit")
        ancestor(root, task["spec_commit"], task["base_commit"], "Spec/base")
        ancestor(root, task["base_commit"], "HEAD", "Base/control")
    if effective in SUBMITTED:
        commit(root, task["submission_head"], "submission_head")
        ancestor(root, task["base_commit"], task["submission_head"], "Base/submission")
        blob(root, task["submission_head"], task["implementation_report"])
        changes = git(root, "diff", "--name-only", task["base_commit"],
                      task["submission_head"]).stdout.splitlines()
        # The claim commit itself may change this task's state; compare it separately.
        for changed in changes:
            if changed == path.relative_to(root).as_posix():
                continue
            controlled = changed in {"AGENTS.md", "docs/project/config.json"}
            controlled |= changed.startswith(".agents/")
            controlled |= changed.startswith(("docs/features/", "docs/decisions/", "docs/changes/"))
            controlled |= changed in task["artifacts"].values()
            controlled |= changed.startswith("docs/tasks/") and changed.endswith("/task.json")
            require(not controlled, f"Submission changes control file: {changed}")
        # The submission must preserve the state in the successful claim commit.
        relative = path.relative_to(root).as_posix()
        candidates = git(root, "rev-list", "--reverse", "--ancestry-path",
                         f"{task['base_commit']}..{task['submission_head']}",
                         "--", relative).stdout.splitlines()
        require(bool(candidates), "Submission must descend from a claim commit")
        claim = candidates[0]
        ancestor(root, claim, "HEAD", "Claim/control")
        try:
            claimed = json.loads(git(root, "show", f"{claim}:{relative}").stdout)
        except ValueError as error:
            raise Invalid("Invalid claim JSON") from error
        require(isinstance(claimed, dict) and claimed.get("status") == "IN_PROGRESS"
                and claimed.get("owner") in [task["owner"], *task["previous_owners"]]
                and claimed.get("branch") == task["branch"]
                and claimed.get("spec_commit") == task["spec_commit"]
                and claimed.get("base_commit") == task["base_commit"],
                "Submission needs matching IN_PROGRESS claim")
        require(git(root, "diff", claim, task["submission_head"], "--", relative).stdout == "",
                "Submission modified task state after claim")
    if task["review"] is not None:
        require(effective in SUBMITTED, "Clear old review when restarting implementation")
        validate_review(root, task)
    if effective in {"CHANGES_REQUESTED", "ACCEPTED", "DONE"}:
        require(task["review"] is not None, "Task needs a review record")
    if effective == "DONE":
        commit(root, task["integrated_commit"], "integrated_commit")
        ancestor(root, task["submission_head"], task["integrated_commit"], "Submission/integration")
        ancestor(root, task["integrated_commit"], "HEAD", "Integration/control")
        parents = git(root, "rev-list", "--parents", "-n", "1", task["integrated_commit"]).stdout.split()
        require(len(parents) >= 3, "Integration must be a merge commit")
        require(bool(task["integration_evidence"]), "DONE needs integration evidence")


def validate_repo(root):
    errors, tasks = [], []
    try:
        config = load_json(root / "docs/project/config.json")
        require(config.get("schema_version") == 1, "Unsupported schema_version")
        require(config.get("max_active_tasks") == 1, "v1 requires max_active_tasks = 1")
        require(config.get("merge_method") == "merge-commit", "v1 requires merge-commit")
        for key in ("remote", "control_branch"):
            require(nonempty(config.get(key)), f"Config needs {key}")
        string_list(config.get("project_checks"), "project_checks")
        task_root = safe_path(root, config.get("task_root"))
        require(task_root.is_dir(), "Configured task_root directory is missing")
    except (Invalid, OSError) as error:
        return None, [], [str(error)]
    for path in sorted(task_root.glob("T*/task.json")):
        try:
            task = load_json(path)
            validate_task(root, task, path)
            tasks.append(task)
        except (Invalid, OSError) as error:
            errors.append(f"{path.relative_to(root)}: {error}")
    if errors:
        return config, tasks, errors
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        errors.append("Duplicate task id")
    for task in tasks:
        for dependency in task["requires"]:
            if dependency not in by_id:
                errors.append(f"{task['id']}: unknown dependency {dependency}")
            elif task["status"] in CLAIMED and by_id[dependency]["status"] != "DONE":
                errors.append(f"{task['id']}: claimed before dependency {dependency} is DONE")
    visiting, visited = set(), set()

    def visit(task_id):
        if task_id in visiting:
            raise Invalid(f"Dependency cycle at {task_id}")
        if task_id in visited or task_id not in by_id:
            return
        visiting.add(task_id)
        for dependency in by_id[task_id]["requires"]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    try:
        for task_id in by_id:
            visit(task_id)
    except Invalid as error:
        errors.append(str(error))
    if sum(task["status"] in ACTIVE for task in tasks) > 1:
        errors.append("More than one active task")
    return config, tasks, errors


def next_action(tasks):
    active = [task for task in tasks if task["status"] in ACTIVE]
    if active:
        task = active[0]
        action = {
            "IN_PROGRESS": "RESUME", "CHANGES_REQUESTED": "RESUME",
            "IN_REVIEW": "WAIT_REVIEW", "ACCEPTED": "INTEGRATE", "BLOCKED": "BLOCKED",
        }[task["status"]]
        return {"action": action, "task": task["id"], "owner": task["owner"]}
    done = {task["id"] for task in tasks if task["status"] == "DONE"}
    ready = [task for task in tasks if task["status"] == "READY" and set(task["requires"]) <= done]
    if ready:
        task = min(ready, key=lambda item: (item["priority"], item["id"]))
        return {"action": "CLAIM", "task": task["id"], "reserved": False}
    return {"action": "IDLE", "reason": "No runnable READY task; inspect drafts/dependencies or await requirements"}


def check_fresh(root, config):
    branch = git(root, "symbolic-ref", "--short", "HEAD", optional=True)
    require(branch.returncode == 0 and branch.stdout.strip() == config["control_branch"],
            "Read the queue from the configured control branch")
    remote_ref = f"refs/remotes/{config['remote']}/{config['control_branch']}"
    remote = git(root, "rev-parse", "--verify", remote_ref, optional=True)
    require(remote.returncode == 0, "Fetch the remote control branch before selecting a task")
    require(git(root, "rev-parse", "HEAD").stdout.strip() == remote.stdout.strip(),
            "Local/remote control heads differ; fetch and synchronize before selecting")
    require(git(root, "status", "--porcelain").stdout == "", "Use a clean control working tree")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "next"))
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    root = args.root.resolve()
    config, tasks, errors = validate_repo(root)
    if not errors and args.command == "next":
        try:
            check_fresh(root, config)
        except (Invalid, OSError) as error:
            errors.append(str(error))
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    result = {"ok": True, "tasks": len(tasks)} if args.command == "validate" else next_action(tasks)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
