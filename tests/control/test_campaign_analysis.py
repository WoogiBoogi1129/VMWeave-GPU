import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'experiments/evidence'))
from analyze_campaign import chunk_window, weighted_samples


class CampaignWindows(unittest.TestCase):
    def test_weights_irregular_samples_and_clips_window(self):
        result=weighted_samples([(0,10),(1,40),(3,90)],.5,2)
        self.assertAlmostEqual(result['gpu_utilization_mean_percent'],30)
        self.assertEqual(result['gpu_sample_coverage_fraction'],1)

    def test_missing_sample_gap_is_not_filled(self):
        result=weighted_samples([(0,100),(10,0),(11,0)],0,11)
        self.assertAlmostEqual(result['gpu_sample_coverage_fraction'],1/11)
        self.assertEqual(result['gpu_utilization_mean_percent'],0)

    def test_chunks_exclude_crossing_boundaries_and_reset_warmup(self):
        events=[{'event':event,'utc_seconds':t+10,'completed':n}
                for event,t,n in [('WARMUP_END',0,999),('MEASUREMENT_START',0,0),
                                  ('PROGRESS',.2,4),('PROGRESS',.4,8),
                                  ('PROGRESS',.6,12),('MEASUREMENT_END',.8,16)]]
        result=chunk_window(events,.1,.7,offset=10)
        self.assertEqual(result['window_completed'],8)
        self.assertAlmostEqual(result['excluded_boundary_seconds'],.2)
        self.assertFalse(result['chunk_window_valid'])

    def test_no_coverage_is_missing_not_zero_utilization(self):
        result=weighted_samples([],0,60)
        self.assertIsNone(result['gpu_utilization_mean_percent'])
        self.assertEqual(result['gpu_sample_coverage_fraction'],0)


if __name__=='__main__':
    unittest.main()
