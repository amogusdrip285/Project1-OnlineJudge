import unittest

from judge.verdict import (
    MAX_COMPILE_OUTPUT_BYTES,
    TestOutcome,
    aggregate_submission,
    decide_test_verdict,
    truncate_compile_output,
)


class TestDecideTestVerdict(unittest.TestCase):
    def test_priority_tle_before_mle_and_re(self) -> None:
        verdict = decide_test_verdict(
            timed_out=True,
            memory_exceeded=True,
            exit_code=1,
            signal_num=9,
            actual_output="8\n",
            expected_output="8\n",
        )
        self.assertEqual(verdict, "TLE")

    def test_priority_mle_before_re(self) -> None:
        verdict = decide_test_verdict(
            timed_out=False,
            memory_exceeded=True,
            exit_code=1,
            signal_num=11,
            actual_output="",
            expected_output="8\n",
        )
        self.assertEqual(verdict, "MLE")

    def test_re_on_signal_or_nonzero_exit(self) -> None:
        self.assertEqual(
            decide_test_verdict(
                timed_out=False,
                memory_exceeded=False,
                exit_code=0,
                signal_num=11,
                actual_output="8\n",
                expected_output="8\n",
            ),
            "RE",
        )
        self.assertEqual(
            decide_test_verdict(
                timed_out=False,
                memory_exceeded=False,
                exit_code=1,
                signal_num=None,
                actual_output="8\n",
                expected_output="8\n",
            ),
            "RE",
        )

    def test_output_truncated_is_wa(self) -> None:
        self.assertEqual(
            decide_test_verdict(
                timed_out=False,
                memory_exceeded=False,
                exit_code=0,
                signal_num=None,
                actual_output="8\n",
                expected_output="8\n",
                output_truncated=True,
            ),
            "WA",
        )

    def test_ac_and_wa(self) -> None:
        self.assertEqual(
            decide_test_verdict(
                timed_out=False,
                memory_exceeded=False,
                exit_code=0,
                signal_num=None,
                actual_output="8 \r\n",
                expected_output="8\n",
            ),
            "AC",
        )
        self.assertEqual(
            decide_test_verdict(
                timed_out=False,
                memory_exceeded=False,
                exit_code=0,
                signal_num=None,
                actual_output="9\n",
                expected_output="8\n",
            ),
            "WA",
        )


class TestAggregateSubmission(unittest.TestCase):
    def test_all_ac(self) -> None:
        res = aggregate_submission(
            max_points=100,
            outcomes=[
                TestOutcome(1, "AC", 5, 2000),
                TestOutcome(2, "AC", 12, 3400),
                TestOutcome(3, "AC", 8, 3000),
            ],
        )
        self.assertEqual(res.status, "AC")
        self.assertEqual(res.score, 100)
        self.assertEqual(res.tests_passed, 3)
        self.assertEqual(res.tests_total, 3)
        self.assertEqual(res.time_ms, 12)
        self.assertEqual(res.memory_kb, 3400)
        self.assertIsNone(res.compile_output)

    def test_partial_floor_score(self) -> None:
        res = aggregate_submission(
            max_points=100,
            outcomes=[
                TestOutcome(1, "AC", 4, 2000),
                TestOutcome(2, "AC", 6, 2100),
                TestOutcome(3, "TLE", 1000, 2200),
            ],
        )
        self.assertEqual(res.status, "PARTIAL")
        self.assertEqual(res.score, 66)
        self.assertEqual(res.tests_passed, 2)
        self.assertEqual(res.tests_total, 3)
        self.assertEqual(res.time_ms, 1000)
        self.assertEqual(res.memory_kb, 2200)

    def test_zero_passed_takes_first_failed_verdict(self) -> None:
        res = aggregate_submission(
            max_points=100,
            outcomes=[
                TestOutcome(1, "WA", 3, 1800),
                TestOutcome(2, "TLE", 1000, 1900),
            ],
        )
        self.assertEqual(res.status, "WA")
        self.assertEqual(res.score, 0)
        self.assertEqual(res.tests_passed, 0)
        self.assertEqual(res.tests_total, 2)

    def test_compile_error_truncates_output(self) -> None:
        long_err = "x" * (MAX_COMPILE_OUTPUT_BYTES + 500)
        res = aggregate_submission(
            max_points=100,
            outcomes=[],
            compile_failed=True,
            compile_output=long_err,
        )
        self.assertEqual(res.status, "CE")
        self.assertEqual(res.score, 0)
        self.assertEqual(res.tests_total, 0)
        self.assertIsNone(res.time_ms)
        self.assertIsNone(res.memory_kb)
        assert res.compile_output is not None
        self.assertEqual(len(res.compile_output.encode("utf-8")), MAX_COMPILE_OUTPUT_BYTES)

    def test_truncate_compile_output_multibyte_safe(self) -> None:
        text = "á" * 10  # 20 UTF-8 bytes
        truncated = truncate_compile_output(text, max_bytes=5)
        self.assertEqual(truncated, "áá")

    def test_zero_testcases_or_system_error_returns_se(self) -> None:
        empty_res = aggregate_submission(max_points=100, outcomes=[])
        self.assertEqual(empty_res.status, "SE")
        self.assertEqual(empty_res.score, 0)

        err_res = aggregate_submission(
            max_points=100,
            outcomes=[TestOutcome(1, "AC", 5, 1000)],
            system_error=True,
        )
        self.assertEqual(err_res.status, "SE")
        self.assertEqual(err_res.score, 0)
        self.assertIsNone(err_res.time_ms)


if __name__ == "__main__":
    unittest.main()
