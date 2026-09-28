"""Guard against mismatched endpoints, missing events and false CUDA success."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/evidence'))
from verify_stage2 import parse, correlate, verify

class Stage2Evidence(unittest.TestCase):
    def setUp(self):
        self.directory=ROOT/'experiments/evidence/results/2026-09-28-stage2/runs/evidence-s2-0928-01'
        self.guest=parse((self.directory/'guest-stderr.txt').read_text())
        self.worker=parse((self.directory/'worker-stderr.txt').read_text())
        self.binding=json.loads((self.directory/'trace-binding.json').read_text())

    def test_all_three_actual_results(self):
        for directory in sorted(self.directory.parent.iterdir()):
            self.assertEqual(verify(directory)['status'],'PASS')

    def test_missing_response_is_rejected(self):
        self.worker.pop()
        with self.assertRaisesRegex(ValueError,'Missing'):correlate(self.guest,self.worker,self.binding)

    def test_duplicate_event_is_rejected(self):
        self.worker.append(copy.deepcopy(self.worker[0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):correlate(self.guest,self.worker,self.binding)

    def test_wrong_session_is_not_same_request(self):
        for r in self.worker:r['session_id']='0'*32
        with self.assertRaises(ValueError):correlate(self.guest,self.worker,self.binding)

    def test_wrong_allocation_is_rejected(self):
        self.binding['allocation']='0'*32
        with self.assertRaisesRegex(ValueError,'Wrong allocation'):correlate(self.guest,self.worker,self.binding)

    def test_transport_ok_is_not_cuda_success(self):
        for r in self.guest+self.worker:
            if r['api_id']==0x1010 and r['api_result'] is not None:r['api_result']=2
        with self.assertRaisesRegex(ValueError,'CUDA failure'):correlate(self.guest,self.worker,self.binding)

    def test_response_length_mismatch_is_rejected(self):
        next(r for r in self.worker if r['event']=='respond')['output_bytes']=999
        with self.assertRaisesRegex(ValueError,'Response differs'):correlate(self.guest,self.worker,self.binding)

    def test_gpu_and_guest_clocks_are_not_compared(self):
        for r in self.worker:r['monotonic_ns']+=10**18
        self.assertTrue(correlate(self.guest,self.worker,self.binding))

class TraceOptIn(unittest.TestCase):
    def test_trace_is_explicit_opt_in_and_preserves_error_domains(self):
        source='''#define _POSIX_C_SOURCE 200809L
#include "flyt_trace.h"
int main(void){
uint8_t allocation[16]={1},payload[8]={0};flyt_put(payload,1048576,8);
struct flyt_shm_request q={.request_id=7,.api_id=FLYT_API_RUNTIME_MALLOC,.input=payload,.input_bytes=8};
struct flyt_shm_response r={.result_domain=FLYT_RESULT_CUDA_RUNTIME,.api_result=2};
flyt_trace("guest","submit",allocation,&q,NULL);flyt_trace("guest","receive",allocation,&q,&r);return 0;}
'''
        with tempfile.TemporaryDirectory() as directory:
            d=Path(directory);(d/'trace.c').write_text(source)
            includes=['runtime/shm/include','experiments/cuda-dispatch/include','experiments/shm-queue/include','experiments/shm-contract/include']
            subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror',*[f'-I{ROOT/p}' for p in includes],str(d/'trace.c'),'-o',str(d/'trace')],check=True)
            env=os.environ.copy();env.pop('FLYT_TRACE_REQUESTS',None)
            for flag in [None,'0','true','1']:
                if flag is not None:env['FLYT_TRACE_REQUESTS']=flag
                result=subprocess.run([str(d/'trace')],env=env,text=True,capture_output=True,check=True)
                if flag!='1':self.assertEqual(result.stderr,'');continue
                rows=parse(result.stderr);self.assertEqual(len(rows),2)
                self.assertIsNone(rows[0]['api_result'])
                self.assertEqual(rows[1]['transport_status'],0);self.assertEqual(rows[1]['result_domain'],1)
                self.assertEqual(rows[1]['api_result'],2);self.assertEqual(rows[1]['requested_bytes'],1048576)
                self.assertEqual(rows[1]['request_id'],7);self.assertEqual(rows[1]['allocation'],'01'+'00'*15)

if __name__=='__main__':unittest.main()
