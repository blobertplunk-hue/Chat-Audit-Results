import importlib.util, pathlib, unittest
ROOT=pathlib.Path(__file__).parent
SPEC=importlib.util.spec_from_file_location('runner_scored_v2', ROOT/'runner_scored_v2.py')
mod=importlib.util.module_from_spec(SPEC)
try:
    SPEC.loader.exec_module(mod)
except FileNotFoundError:
    mod=None

class ScoredRunnerContractTests(unittest.TestCase):
    def test_scored_fixture_contract_accepts_only_scored_holdout(self):
        self.assertIsNotNone(mod)
        mod.validate_scored_fixture({'fixture_mode':'SCORED_HOLDOUT','benchmark_id':'CVB-007-20260905','competitor_pin':'9b9e9567305122d439727989b3633abc05183bce','tokens':{k:k for k in ['r0','r1','a0','a1','c0','c1','q0','q1','d0','d1']}})
        with self.assertRaises(ValueError):
            mod.validate_scored_fixture({'fixture_mode':'CALIBRATION_ONLY_NOT_SCOREABLE','benchmark_id':'CVB-007-20260905','competitor_pin':'9b9e9567305122d439727989b3633abc05183bce'})

    def test_scored_summary_remains_unscored(self):
        self.assertIsNotNone(mod)
        summary=mod.build_scored_summary({f'S{i}':{'scenario_id':f'S{i}','harness_status':'COMPLETE','benchmark_score':None} for i in range(7)}, {'benchmark_id':'CVB-007-20260905','fixture_id':'X','competitor_pin':'9b9e9567305122d439727989b3633abc05183bce'})
        self.assertFalse(summary['score_performed'])
        self.assertEqual(summary['scenario_count'],7)
        self.assertEqual(summary['harness_error_count'],0)

if __name__=='__main__': unittest.main()
