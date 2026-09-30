import unittest
import numpy as np
from analyze import interval
class CompletionWindows(unittest.TestCase):
 def test_counts_actual_completions_without_interpolation(self):
  data=np.array([[0,14.9,.1],[1,15,.1],[2,15.01,.01],[3,104,88.99],[4,105,1],[5,105.1,.1]])
  result=interval(data,15,105)
  self.assertEqual(result['completed'],3)
  self.assertAlmostEqual(result['throughput'],3/90)
  self.assertEqual(result['p50_ms'],1000)
 def test_no_completion_is_not_fabricated_low_latency(self):
  result=interval(np.array([[0,1,.1],[1,110,109]]),15,105)
  self.assertEqual(result['completed'],0)
  self.assertIsNone(result['p95_ms'])
if __name__=='__main__':unittest.main()
