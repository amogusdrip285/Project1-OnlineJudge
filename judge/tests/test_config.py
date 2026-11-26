import unittest

from judge.config import JudgeSettings, load_settings


class TestConfig(unittest.TestCase):
    def test_defaults_when_env_empty(self) -> None:
        settings = load_settings({})
        self.assertEqual(settings, JudgeSettings())

    def test_overrides_from_env(self) -> None:
        settings = load_settings(
            {
                "DATABASE_URL": "postgresql://u:p@db:5432/oj",
                "PROBLEMS_DIR": "/custom/problems",
                "JUDGE_POLL_INTERVAL_MS": "250",
                "JUDGE_STALE_AFTER_SECONDS": "60",
                "JUDGE_COMPILE_TIMEOUT_SECONDS": "15",
                "JUDGE_MAX_OUTPUT_BYTES": "1024",
            }
        )
        self.assertEqual(settings.database_url, "postgresql://u:p@db:5432/oj")
        self.assertEqual(settings.problems_dir, "/custom/problems")
        self.assertEqual(settings.poll_interval_ms, 250)
        self.assertEqual(settings.stale_after_seconds, 60)
        self.assertEqual(settings.compile_timeout_seconds, 15)
        self.assertEqual(settings.max_output_bytes, 1024)

    def test_rejects_non_positive_integers(self) -> None:
        with self.assertRaises(ValueError):
            load_settings({"JUDGE_POLL_INTERVAL_MS": "0"})
        with self.assertRaises(ValueError):
            load_settings({"JUDGE_STALE_AFTER_SECONDS": "-5"})


if __name__ == "__main__":
    unittest.main()
