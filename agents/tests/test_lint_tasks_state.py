import unittest
from pathlib import Path

from agents.scripts import lint_tasks_state


class LintTasksStateTests(unittest.TestCase):
    def test_validate_tasks_state_accepts_valid_data(self) -> None:
        tasks_data = {
            "schema_version": 2,
            "current_sprint": [{"id": "T-001"}],
            "backlog": [],
        }
        state_data = {
            "schema_version": 2,
            "T-001": {"status": "ready", "pr": None, "merged": False},
        }

        errors = lint_tasks_state.validate_tasks_state(
            tasks_data,
            state_data,
            Path("tasks.yaml"),
            Path("tasks_state.yaml"),
        )

        self.assertEqual(errors, [])

    def test_validate_tasks_state_rejects_invalid_status(self) -> None:
        tasks_data = {
            "schema_version": 2,
            "current_sprint": [{"id": "T-001"}],
            "backlog": [],
        }
        state_data = {
            "schema_version": 2,
            "T-001": {"status": "bogus", "pr": None, "merged": False},
        }

        errors = lint_tasks_state.validate_tasks_state(
            tasks_data,
            state_data,
            Path("tasks.yaml"),
            Path("tasks_state.yaml"),
        )

        self.assertIn(
            "tasks_state.yaml status 'bogus' for 'T-001' is invalid.",
            errors,
        )

    def test_validate_tasks_state_rejects_pr_on_ready(self) -> None:
        tasks_data = {
            "schema_version": 2,
            "current_sprint": [{"id": "T-001"}],
            "backlog": [],
        }
        state_data = {
            "schema_version": 2,
            "T-001": {"status": "ready", "pr": 4, "merged": False},
        }

        errors = lint_tasks_state.validate_tasks_state(
            tasks_data,
            state_data,
            Path("tasks.yaml"),
            Path("tasks_state.yaml"),
        )

        self.assertIn(
            "tasks_state.yaml pr for 'T-001' must be null in 'ready'.",
            errors,
        )

    def test_validate_tasks_state_requires_state_entry(self) -> None:
        tasks_data = {
            "schema_version": 2,
            "current_sprint": [{"id": "T-001"}],
            "backlog": [],
        }
        state_data = {"schema_version": 2}

        errors = lint_tasks_state.validate_tasks_state(
            tasks_data,
            state_data,
            Path("tasks.yaml"),
            Path("tasks_state.yaml"),
        )

        self.assertIn("tasks_state.yaml is missing entry for 'T-001'.", errors)

    def test_validate_tasks_state_rejects_inactive_task(self) -> None:
        tasks_data = {
            "schema_version": 2,
            "current_sprint": [{"id": "T-001"}],
            "backlog": [],
        }
        state_data = {
            "schema_version": 2,
            "T-001": {"status": "ready", "pr": None, "merged": False},
            "T-999": {"status": "ready", "pr": None, "merged": False},
        }

        errors = lint_tasks_state.validate_tasks_state(
            tasks_data,
            state_data,
            Path("tasks.yaml"),
            Path("tasks_state.yaml"),
        )

        self.assertIn(
            "tasks_state.yaml includes inactive task 'T-999'; "
            "only active tasks in tasks.yaml are allowed.",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
