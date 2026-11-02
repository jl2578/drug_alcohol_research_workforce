"""Verify the fixed aggregate package and run its declared numerical replays.

Python 3.10+ standard library only. No model fitting, network or private inputs.
"""
import argparse
import contextlib
import csv
import hashlib
import io
import json
import runpy
import sys
from pathlib import Path

def sha(p):
 return hashlib.sha256(p.read_bytes()).hexdigest()

def readcsv(p):
 with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def verify_manifest(bundle):
 # File inventory and hashes are checked once, by verify_all.py and the root SHA256SUMS.txt.
 checks=0
 for p in bundle.rglob('*'):
  if p.is_file() and p.suffix in ['.csv','.json','.md','.py','.txt']:
   b=p.read_bytes();b.decode('utf-8')
   if b'\r' in b:raise RuntimeError('Non-LF text: '+p.relative_to(bundle).as_posix())
   checks+=1
 return checks

def run_component(path,arguments):
 previous=sys.argv[:]
 stream=io.StringIO()
 try:
  sys.argv=[str(path)]+arguments
  with contextlib.redirect_stdout(stream):
   try:runpy.run_path(str(path),run_name='__main__')
   except SystemExit as e:
    if e.code not in (None,0):raise RuntimeError('Component failed: '+str(path.name)+' '+str(e.code))
 finally:sys.argv=previous
 return stream.getvalue()

def main():
 if sys.flags.optimize:raise RuntimeError('Run verification without -O/-OO')
 sys.dont_write_bytecode=True
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--bundle',type=Path,required=True)
 ap.add_argument('--output-dir',type=Path,required=True)
 args=ap.parse_args();bundle=args.bundle.resolve();out=args.output_dir.resolve()
 if out==bundle or bundle in out.parents or out in bundle.parents:raise RuntimeError('Output must be outside the entire bundle, not its ancestor')
 if not bundle.is_dir():raise RuntimeError('Bundle not found')
 integrity=verify_manifest(bundle)
 out.mkdir(parents=True,exist_ok=True)
 rc_out=out/'reach_content';inv_out=out/'investigator_verification.json';op_out=out/'opioid'
 logs={}
 here=Path(__file__).resolve().parent
 logs['reach_content']=run_component(here/'check_reach_content.py',['--bundle',str(bundle/'reach_content'),'--output-dir',str(rc_out)])
 logs['investigator']=run_component(here/'check_investigator.py',['--bundle',str(bundle/'investigator'),'--output',str(inv_out)])
 logs['opioid']=run_component(here/'check_opioid.py',['--bundle',str(bundle/'opioid'),'--output-dir',str(op_out)])
 rc=json.loads((rc_out/'reach_content_verification.json').read_text(encoding='utf-8'))
 inv=json.loads(inv_out.read_text(encoding='utf-8'))
 op=json.loads((op_out/'verification.json').read_text(encoding='utf-8'))
 if not rc['passed'] or inv['status']!='passed' or op['status']!='passed':raise RuntimeError('Numerical replay failed')
 # Reconstruct the current Figure5B/C numerical values from released n/N.
 sources=readcsv(bundle/'provenance/source_manifest.csv')
 figure_source=next(x['output_file'] for x in sources if x['source_id']=='NA73')
 figrows=readcsv(bundle/figure_source)
 for r in figrows:r['value']=format(100*float(r['numerator'])/float(r['denominator']),'.17g')
 with (rc_out/'figure5BC_numeric_recomputed.csv').open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(figrows[0]),lineterminator='\n');w.writeheader();w.writerows(figrows)
 verify_manifest(bundle)
 summary={'status':'passed','integrity_checks':integrity,'component_checks':{'reach_content':rc['checks'],'investigator':inv['checks'],'opioid':op['checks']},
  'numerical_checks_total':rc['checks']+inv['checks']+op['checks'],'saved_summary_inference_rows_replayed':inv['inference_rows_recomputed']+op['model_summary_inference_replays'],
  'science_models_fitted':0,'private_inputs_required':False,'scope':'aggregate arithmetic and saved-summary inference, not model re-estimation',
  'data_files':json.loads((bundle/'metadata/release.json').read_text(encoding='utf-8'))['data_files']}
 (out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
