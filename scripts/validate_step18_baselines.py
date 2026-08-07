#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'data/sample/baselines/step18-baselines-validation/report.json'
EXE=ROOT/'build/gcc-debug/robust_execution_baseline_demo'

def fail(msg:str)->None: raise SystemExit(msg)

def main()->None:
    obj=json.loads(REPORT.read_text())
    payload=obj['payload']
    canonical=json.dumps(payload,separators=(',',':'),sort_keys=False)
    # The C++ payload is emitted in deterministic insertion order. Re-run executable is the primary byte check.
    rerun=subprocess.check_output([str(EXE)],text=True)
    if rerun != REPORT.read_text(): fail('baseline report is not byte-identical to executable output')
    if payload['evidence_status']!='synthetic_validation_only_non_research': fail('invalid evidence status')
    if payload['past_only_cutoff_ns'] >= payload['episode_start_ns']: fail('past-only cutoff leaks into episode')
    expected={
      'immediate':([100],[1000],100.0),
      'twap':([25,25,25,25],[1000,1250,1500,1750],0.0),
      'past_volume_informed':([10,20,30,40],[1000,1250,1500,1750],-20.0),
    }
    for name,(qty,times,bps) in expected.items():
        rec=payload[name]
        if [x['quantity_lots'] for x in rec['slices']] != qty: fail(f'{name} quantities changed')
        if [x['release_time_ns'] for x in rec['slices']] != times: fail(f'{name} times changed')
        if abs(rec['implementation_shortfall_bps']-bps)>1e-12: fail(f'{name} metric changed')
        if sum(qty)!=100: fail(f'{name} fails quantity conservation')
    if 'twap|passive|' not in payload['passive_twap_canonical']: fail('passive TWAP variant missing')
    raw_payload=REPORT.read_text()
    if 'synthetic_validation_only_non_research' not in raw_payload: fail('research boundary missing')
    print(json.dumps({'status':'ok','step':18,'strategies':3,'passive_variant':True,'research_status':payload['evidence_status']},sort_keys=True))
if __name__=='__main__': main()
