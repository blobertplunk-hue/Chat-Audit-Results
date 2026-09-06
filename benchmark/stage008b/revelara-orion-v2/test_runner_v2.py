import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runner_v2 as r


class RunnerV2Tests(unittest.TestCase):
    def test_product_nonzero_is_observation_not_harness_error(self):
        seen = []
        def scenario(ctx):
            seen.append(ctx.scenario_id)
            return {"commands": [{"rc": 7}], "product_observation": "denied"}
        out = r.run_scenarios(["S0", "S1"], lambda sid: scenario, Path(tempfile.mkdtemp()))
        self.assertEqual(seen, ["S0", "S1"])
        self.assertEqual(out["S0"]["harness_status"], "COMPLETE")
        self.assertEqual(out["S1"]["harness_status"], "COMPLETE")

    def test_harness_exception_isolated_and_later_scenario_runs(self):
        seen = []
        def factory(sid):
            def scenario(ctx):
                seen.append(sid)
                if sid == "S0":
                    raise RuntimeError("fixture bug")
                return {"ok": True}
            return scenario
        out = r.run_scenarios(["S0", "S1"], factory, Path(tempfile.mkdtemp()))
        self.assertEqual(seen, ["S0", "S1"])
        self.assertEqual(out["S0"]["harness_status"], "HARNESS_ERROR")
        self.assertEqual(out["S1"]["harness_status"], "COMPLETE")

    def test_mutate_candidate_changes_main_go_hash(self):
        root = Path(tempfile.mkdtemp())
        p = root / "main.go"
        p.write_text("package main\nfunc main(){}\n", encoding="utf-8")
        before = hashlib.sha256(p.read_bytes()).hexdigest()
        after = r.mutate_candidate_main_go(p, "ORION_CAL_C1_1234")
        self.assertNotEqual(before, after)
        self.assertIn("ORION_CAL_C1_1234", p.read_text(encoding="utf-8"))
        self.assertEqual(after, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_summary_requires_exactly_s0_through_s6(self):
        good = {f"S{i}": {"harness_status": "COMPLETE"} for i in range(7)}
        summary = r.summarize(good)
        self.assertEqual(summary["scenario_count"], 7)
        self.assertTrue(summary["all_scenarios_emitted"])
        bad = dict(good)
        bad.pop("S6")
        summary = r.summarize(bad)
        self.assertFalse(summary["all_scenarios_emitted"])

    def test_command_result_preserves_nonzero_without_raising(self):
        with mock.patch("subprocess.run") as sp:
            sp.return_value = mock.Mock(returncode=9, stdout="out", stderr="err")
            got = r.run_command(["orion", "run"])
        self.assertEqual(got["rc"], 9)
        self.assertEqual(got["stdout"], "out")
        self.assertEqual(got["stderr"], "err")


if __name__ == "__main__":
    unittest.main()
