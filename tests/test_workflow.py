"""Exercise gates using real, isolated Git histories rather than mocked SHA strings."""

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("workflow", PROJECT / "scripts/workflow.py")
workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        scratch = PROJECT / "work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="agent-work-test-", dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Workflow Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.write_json("docs/project/config.json", json.loads(
            (PROJECT / "docs/project/config.json").read_text(encoding="utf-8")))
        self.write("docs/features/F0002-example/requirements.md", "AC-01: expected behavior\n")
        self.write("docs/features/F0002-example/design.md", "Design contract\n")
        self.write("docs/tasks/T0001/brief.md", "AC-01: observable acceptance\n")
        self.spec_commit = self.commit("specification")
        self.task = json.loads((PROJECT / ".agents/skills/architect-orchestrator/assets/templates/task.json")
                               .read_text(encoding="utf-8"))
        self.task.update(status="READY", spec_commit=self.spec_commit)
        self.save_task()
        self.commit("publish ready task")

    def git(self, *args):
        result = subprocess.run(["git", "-C", str(self.root), *args], capture_output=True,
                                text=True, encoding="utf-8", check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def write_json(self, path, value):
        self.write(path, json.dumps(value, indent=2) + "\n")

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-m", message)
        return self.git("rev-parse", "HEAD")

    def save_task(self):
        self.write_json("docs/tasks/T0001/task.json", self.task)

    def validate(self):
        return workflow.validate_repo(self.root)[2]

    def submit(self):
        self.task.update(status="IN_PROGRESS", owner="coder/session-1", branch="task/T0001-feature",
                         base_commit=self.git("rev-parse", "HEAD"))
        self.save_task()
        self.commit("claim T0001")
        self.git("switch", "-c", self.task["branch"])
        self.write("app.txt", "implemented behavior\n")
        self.report = "docs/tasks/T0001/submissions/round-1.md"
        self.write(self.report, "AC-01 verified with fixture command; expected output observed\n")
        head = self.commit("implement and provide evidence")
        self.git("switch", "main")
        self.task.update(status="IN_REVIEW", submission_head=head, implementation_report=self.report)
        self.save_task()
        self.commit("submit for review")

    def approve(self, round_number=1):
        self.review = {
            "task_id": "T0001", "reviewer": "architect/session-1",
            "reviewed_head": self.task["submission_head"], "reviewed_base": self.task["base_commit"],
            "verdict": "APPROVED", "checks": dict.fromkeys(workflow.DIMENSIONS, "PASS"),
            "acceptance": [{"id": "AC-01", "result": "PASS", "evidence": "app.txt and fixture verification"}],
            "findings": [],
        }
        self.review_path = f"docs/tasks/T0001/reviews/round-{round_number}.json"
        self.write_json(self.review_path, self.review)
        self.task.update(status="ACCEPTED", review=self.review_path)
        self.save_task()
        self.commit("approve exact submitted head")

    def test_ready_and_dependency_order(self):
        self.assertEqual(self.validate(), [])
        later = copy.deepcopy(self.task)
        later.update(id="T0002", priority=0, requires=["T0001"])
        self.write_json("docs/tasks/T0002/task.json", later)
        _, tasks, errors = workflow.validate_repo(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(workflow.next_action(tasks)["task"], "T0001")

    def test_waiting_review_prevents_next_claim(self):
        self.submit()
        later = copy.deepcopy(self.task)
        later.update(id="T0002", status="READY", owner=None, branch=None, base_commit=None,
                     submission_head=None, implementation_report=None)
        self.write_json("docs/tasks/T0002/task.json", later)
        _, tasks, errors = workflow.validate_repo(self.root)
        self.assertEqual(errors, [])
        self.assertEqual(workflow.next_action(tasks)["action"], "WAIT_REVIEW")

    def test_complete_lifecycle_requires_real_merge(self):
        self.submit()
        self.approve()
        self.git("merge", "--no-ff", self.task["submission_head"], "-m", "integrate reviewed code")
        self.task.update(status="DONE", integrated_commit=self.git("rev-parse", "HEAD"),
                         integration_evidence=["fixture integration check passed on merge SHA"])
        self.save_task()
        self.assertEqual(self.validate(), [])
        self.assertEqual(workflow.next_action([self.task])["action"], "IDLE")
        self.task["integration_evidence"] = []
        self.save_task()
        self.assertTrue(any("integration evidence" in error for error in self.validate()))

    def test_failed_integration_can_return_to_fix_and_new_review(self):
        self.submit()
        self.approve()
        self.git("merge", "--no-ff", self.task["submission_head"], "-m", "first integration")
        self.task.update(status="BLOCKED", blocked_from="ACCEPTED", blocked_reason="integration failed",
                         integrated_commit=self.git("rev-parse", "HEAD"))
        self.write("docs/tasks/T0001/reviews/integration-round-1.md", "Integration command failed at merge SHA\n")
        self.save_task()
        self.commit("record integration failure")
        self.assertEqual(self.validate(), [])
        self.task.update(status="IN_PROGRESS", blocked_from=None, blocked_reason=None, review=None,
                         integrated_commit=None, integration_evidence=[])
        self.save_task()
        self.commit("return to implementation")
        self.git("switch", self.task["branch"])
        self.write("app.txt", "fixed integration\n")
        report = "docs/tasks/T0001/submissions/round-2.md"
        self.write(report, "AC-01 and integration fix verified\n")
        fixed = self.commit("fix integration issue")
        self.git("switch", "main")
        self.task.update(status="IN_REVIEW", submission_head=fixed, implementation_report=report)
        self.save_task()
        self.commit("resubmit integration fix")
        self.assertEqual(self.validate(), [])
        self.approve(round_number=2)
        self.git("merge", "--no-ff", fixed, "-m", "integrate reviewed fix")
        self.task.update(status="DONE", integrated_commit=self.git("rev-parse", "HEAD"),
                         integration_evidence=["Integration command passed on second merge"])
        self.save_task()
        self.assertEqual(self.validate(), [])

    def test_unreviewed_done_is_rejected(self):
        self.submit()
        self.task["status"] = "DONE"
        self.save_task()
        self.assertTrue(any("review record" in error for error in self.validate()))

    def test_review_sha_drift_is_rejected(self):
        self.submit()
        self.approve()
        self.review["reviewed_head"] = self.spec_commit
        self.write_json(self.review_path, self.review)
        self.assertTrue(any("head mismatch" in error for error in self.validate()))

    def test_rework_can_be_resubmitted_without_changing_control_state_on_branch(self):
        self.submit()
        self.approve()
        self.review["verdict"] = "CHANGES_REQUESTED"
        self.review["checks"]["requirements"] = "FAIL"
        self.review["acceptance"][0]["result"] = "FAIL"
        self.write_json(self.review_path, self.review)
        self.task["status"] = "CHANGES_REQUESTED"
        self.save_task()
        self.commit("request rework")
        self.assertEqual(self.validate(), [])
        self.task.update(status="IN_PROGRESS", review=None)
        self.save_task()
        self.commit("begin rework")
        self.git("switch", self.task["branch"])
        self.write("app.txt", "corrected behavior\n")
        self.write("docs/tasks/T0001/submissions/round-2.md", "AC-01 fixed and verified\n")
        head = self.commit("fix review finding")
        self.git("switch", "main")
        self.task.update(status="IN_REVIEW", submission_head=head,
                         implementation_report="docs/tasks/T0001/submissions/round-2.md")
        self.save_task()
        self.assertEqual(self.validate(), [])

    def test_owner_handoff_preserves_claim_and_review_independence(self):
        self.submit()
        self.task.update(previous_owners=[self.task["owner"]], owner="coder/session-2")
        self.save_task()
        self.assertEqual(self.validate(), [])
        self.approve()
        self.review["reviewer"] = self.task["previous_owners"][0]
        self.write_json(self.review_path, self.review)
        self.assertTrue(any("differ" in error for error in self.validate()))

    def test_self_review_is_rejected(self):
        self.submit()
        self.approve()
        self.review["reviewer"] = self.task["owner"]
        self.write_json(self.review_path, self.review)
        self.assertTrue(any("differ" in error for error in self.validate()))

    def test_missing_acceptance_evidence_is_rejected(self):
        self.submit()
        self.approve()
        self.review["acceptance"][0]["evidence"] = ""
        self.write_json(self.review_path, self.review)
        self.assertTrue(any("evidence" in error for error in self.validate()))

    def test_blocking_finding_cannot_be_accepted(self):
        self.submit()
        self.approve()
        self.review["findings"] = [{"id": "R-01", "severity": "P1", "status": "ACCEPTED",
                                    "evidence": "wrong result", "accepted_reason": "later"}]
        self.write_json(self.review_path, self.review)
        self.assertTrue(any("Only P3" in error for error in self.validate()))

    def test_forged_claim_and_control_changes_are_rejected(self):
        self.submit()
        self.git("switch", self.task["branch"])
        self.write("AGENTS.md", "Changed control rule\n")
        self.task["submission_head"] = self.commit("unauthorized control edit")
        self.git("switch", "main")
        self.save_task()
        self.assertTrue(any("control file" in error for error in self.validate()))

    def test_dependency_cycle_is_rejected(self):
        self.task["requires"] = ["T0002"]
        self.save_task()
        later = copy.deepcopy(self.task)
        later.update(id="T0002", requires=["T0001"])
        self.write_json("docs/tasks/T0002/task.json", later)
        self.assertTrue(any("cycle" in error for error in self.validate()))

    def test_two_blocked_tasks_exceed_single_active_limit(self):
        self.task.update(status="BLOCKED", blocked_from="READY", blocked_reason="needs decision")
        self.save_task()
        later = copy.deepcopy(self.task)
        later["id"] = "T0002"
        self.write_json("docs/tasks/T0002/task.json", later)
        self.assertTrue(any("More than one active" in error for error in self.validate()))

    def test_missing_specification_file_is_rejected(self):
        self.task["artifacts"]["design"] = "docs/missing.md"
        self.save_task()
        self.assertTrue(any("File missing" in error for error in self.validate()))

    def test_path_escape_and_invalid_json_are_reported(self):
        self.task["artifacts"]["brief"] = "../outside.md"
        self.save_task()
        self.assertTrue(any("Invalid repository-relative" in error for error in self.validate()))
        self.write("docs/tasks/T0001/task.json", "invalid json")
        self.assertTrue(any("Cannot read" in error for error in self.validate()))

    def test_selection_requires_clean_synchronized_control_branch(self):
        config, _, _ = workflow.validate_repo(self.root)
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        workflow.check_fresh(self.root, config)
        self.write("untracked.txt", "local work")
        with self.assertRaisesRegex(workflow.Invalid, "clean"):
            workflow.check_fresh(self.root, config)


if __name__ == "__main__":
    unittest.main()
