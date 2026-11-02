import math
import json
import tempfile
import unittest
from pathlib import Path
from analyze import interval, difference_interval, cpu_cost

class AnalysisTests(unittest.TestCase):
    def test_constant_speedup(self):
        result=interval([2.0]*10)
        self.assertAlmostEqual(result['geomean'],2.0)
        self.assertEqual(result['n_blocks'],10)
        for endpoint in result['ci95']:self.assertAlmostEqual(endpoint,2.0)

    def test_paired_multiplicative_symmetry(self):
        values=[.5,.8,1.2,2.0]
        direct=interval(values)['geomean']
        reciprocal=interval([1/x for x in values])['geomean']
        self.assertAlmostEqual(direct*reciprocal,1.0)
        self.assertAlmostEqual(direct,math.prod(values)**.25)

    def test_invalid_or_single_block(self):
        for values in [[1.0],[0,1],[-1,1]]:
            with self.assertRaises(AssertionError):interval(values)

    def test_differences_keep_zero_and_negative_observations(self):
        x=difference_interval([-2.0,0.0,2.0])
        self.assertEqual(x['mean'],0)
        self.assertLess(x['ci95'][0],0)
        self.assertGreater(x['ci95'][1],0)
        constant=difference_interval([-3.0]*10)
        self.assertEqual(constant['mean'],-3.0)
        self.assertEqual(constant['ci95'],[-3.0,-3.0])

    def test_cpu_window_excludes_initialization_and_accounts_for_clock_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'clock.json').write_text(json.dumps([{'offset':10,'uncertainty':.1}]))
            points=[]
            for t,usage in [(99,0),(100.5,100000000),(101.5,102000000),(103,900000000)]:
                points.append({'utc':t,'pods':{'launcher':{'cpu':{'usage_usec':usage}},'worker':{'cpu':{'usage_usec':usage//2}}}})
            (root/'cpu.jsonl').write_text('\n'.join(map(json.dumps,points)))
            result={'start_utc':110,'end_utc':112,'elapsed_seconds':2,'step_seconds':.02}
            x=cpu_cost(root,result)
            self.assertAlmostEqual(x['cpu_seconds'],3)
            self.assertAlmostEqual(x['fraction_of_timed_interval'],.5)
            self.assertAlmostEqual(x['cpu_seconds_per_step_estimate'],.06)
            result.update(start_utc=110.4,end_utc=110.7)
            self.assertIsNone(cpu_cost(root,result))

if __name__=='__main__':unittest.main()
