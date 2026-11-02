"""Standalone, fixed RC-RMI scoring. Python standard library only."""
from pathlib import Path
from collections import defaultdict
import argparse, copy, csv, hashlib, itertools, json, sys
sys.dont_write_bytecode=True
import instrument

ROOT=Path(__file__).resolve().parent
SPECS=('inclusive','no_hospital_override','conservative')
SCORES=('0','1','2','3','4','U')

def require(ok,message):
    if not ok:raise ValueError(message)

def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        require(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),'Missing/duplicate CSV header')
        rows=list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows),'Malformed CSV')
    return rows

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_files(root=ROOT):
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    found={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p!=root/'manifest.json'}
    require(found==set(manifest['files']),'Package membership mismatch')
    for rel,digest in manifest['files'].items():
        path=(root/rel).resolve()
        require(path.is_relative_to(root.resolve()),'Unsafe manifest path')
        require(sha(path)==digest,'Package hash mismatch: '+rel)
    return len(found)

def load_assets():
    occupations=read(ROOT/'data/occupation_decisions.csv')
    industries=read(ROOT/'data/industry_decisions.csv')
    require(len(occupations)==len({r['soc_code_canonical'] for r in occupations})==303,'Occupation domain changed')
    require(len(industries)==len({r['naics_code_canonical'] for r in industries})==68,'Industry domain changed')
    for r in occupations:
        require(r['research_final'] in SCORES and r['clinical_final'] in SCORES,'Invalid occupation score')
        require(r['directness_final'] in instrument.DIRECTNESS_VALUES,'Invalid directness')
    for r in industries:
        require(r['research_final'] in ('R0','R1','R2','R3','RU'),'Invalid research context')
        require(r['clinical_final'] in ('C0','C1','C2','C3','CU'),'Invalid clinical context')
    declaration=json.loads((ROOT/'data/original_two_specifications.json').read_text(encoding='utf-8'))
    instrument.check_declaration(declaration)
    table=instrument.load_rule_table(ROOT/'data/combination_rules.csv')
    expected={(axis,b,prefix+c) for axis,prefix in [('research','R'),('clinical','C')] for b in SCORES for c in ('0','1','2','3','U')}
    require(set(table)==expected and len(table)==60,'Matrix must contain every one of the 60 unique keys')
    require(all(r['output_score'] in SCORES for r in table.values()),'Invalid matrix output')
    instrument.assert_no_care_base_ceiling(occupations)
    return occupations,industries,declaration,table

def domain(specification):
    require(specification in SPECS,'Unknown specification')
    occupations,industries,declaration,table=load_assets()
    engine_spec=specification
    if specification=='no_hospital_override':
        declaration=copy.deepcopy(declaration)
        override=next(c for c in declaration['components'] if c['id']=='establishment_heterogeneity')['override']
        override['codes']=[c for c in override['codes'] if c['naics_code_canonical']=='611310']
        override['expected_code_count']=1
        engine_spec='inclusive'
    rows,occ_steps,ind_steps=instrument.score_domain(occupations,industries,declaration,engine_spec,table)
    for row in rows:row['specification']=specification
    return rows

def fingerprint(rows):
    fields=('pair_id','research_final_score','clinical_final_score','joint_class')
    payload='\n'.join('\t'.join(r[c] for c in fields) for r in sorted(rows,key=lambda r:r['pair_id']))+'\n'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def score_rows(rows,specification):
    pairs={r['pair_id']:r for r in domain(specification)}
    socs={r['soc_code_canonical'] for r in pairs.values()}
    candidates=defaultdict(set)
    for row in read(ROOT/'data/soc_crosswalk.csv'):candidates[row['source_code']].add(row['unit_code'])
    output=[]
    for i,row in enumerate(rows,1):
        require(set(row)=={'soc_code','naics_code'},'Input must contain only soc_code,naics_code')
        soc,naics=row['soc_code'].strip(),row['naics_code'].strip()
        choices=sorted(candidates.get(soc,set()) & socs)
        normalized=soc if soc in socs else choices[0] if len(choices)==1 else ''
        mapping='direct_instrument_domain' if soc in socs else 'unique_frozen_crosswalk_source_to_unit' if len(choices)==1 else 'missing_source_code' if not soc else 'unresolved_crosswalk'
        pair=normalized+'|'+naics if normalized and naics else ''
        status='scored_pair' if pair in pairs else 'missing_pair_applicability_unresolved' if not soc or not naics else 'unmapped_pair'
        common={'input_row':str(i),'specification':specification,'soc_source':soc,'soc_instrument':normalized,'naics_code':naics,'mapping_status':mapping,'application_status':status}
        fields=('research_final_score','clinical_final_score','joint_class')
        output.append({**common,**{f:pairs[pair][f] if status=='scored_pair' else '' for f in fields}})
    return output

def write_external(path,rows):
    path=Path(path).resolve()
    require(not path.is_relative_to(ROOT),'Outputs must be outside the package')
    require(not path.exists(),'Refusing to overwrite an existing output')
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('verify','domain','score'))
    parser.add_argument('--specification',choices=SPECS,default='inclusive')
    parser.add_argument('--input',type=Path);parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    count=verify_files()
    if args.command=='verify':
        expected=json.loads((ROOT/'expected_domain_fingerprints.json').read_text(encoding='utf-8'))
        results={s:fingerprint(domain(s)) for s in SPECS}
        require(results==expected['score_fingerprints'],'Full-domain score benchmark mismatch')
        print(json.dumps({'status':'PASS','files':count,'pairs_per_specification':20604,'specifications':list(SPECS),'score_fingerprints':results},indent=2));return
    require(args.output is not None,'--output is required')
    if args.command=='domain':rows=domain(args.specification)
    else:
        require(args.input is not None,'--input is required')
        rows=score_rows(read(args.input),args.specification)
        require(bool(rows),'Input must contain at least one pair')
    write_external(args.output,rows)
    print(json.dumps({'status':'PASS','rows':len(rows),'output':str(args.output)}))

if __name__=='__main__':main()
