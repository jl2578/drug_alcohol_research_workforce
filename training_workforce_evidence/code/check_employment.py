"""Recompute supplied employment aggregate percentages, bases and Figure 6 sums."""
from collections import defaultdict
from pathlib import Path
import argparse, csv, json

def require(ok,message):
    if not ok:raise ValueError(message)

def read(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        require(reader.fieldnames is not None and len(reader.fieldnames)==len(set(reader.fieldnames)),'Missing/duplicate CSV header')
        rows=list(reader)
    require(all(None not in r and all(v is not None for v in r.values()) for r in rows),'Malformed CSV')
    return rows

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True);ROOT=parser.parse_args().root.resolve()
    files=sorted((ROOT/'evidence/employment').rglob('*.csv'))
    require(len(files)==21,'Expected complete 21-file numerical companion')
    checks=0;rows_total=0
    rules={'pct_observed':('n','observed_n'),'pct_scored':('n','scored_n'),
           'pct_from_state':('n','from_state_n'),'pct_from_score':('n','from_score_n'),
           'pct_paired_scored':('n','paired_scored_n'),'percent_within_degree':('n','observed_degree_n'),
           'pct_outside':('n','outside_n'),'destination_pct_outside':('destination_n','outside_n'),
           'pct_within_destination':('n','destination_n'),'pct_scored_outside':('n','outside_scored_n'),
           'pct_scored_within_destination':('n','destination_scored_n'),'pct_industry_scope':('n','industry_scope_n'),
           'outside_pct_observed':('outside_n','observed_n'),'university_pct_observed':('university_n','observed_n'),
           'unknown_industry_pct_observed':('unknown_industry_n','observed_n'),'pct_breakdown':('n','breakdown_n'),
           'pct_other':('n','other_n'),'pct_subset':('n','subset_n'),
           'pct_observed_joint_state_changed':('joint_state_changed_n','observed_n')}
    for path in files:
        rows=read(path);rows_total+=len(rows)
        for r in rows:
            for field,(num,den) in rules.items():
                if field in r and r[field]!='':
                    require(float(r[den])>0,'Nonblank percentage with zero denominator')
                    require(abs(float(r[field])-100*int(r[num])/int(r[den]))<=0.00000051,path.name+': '+field)
                    checks+=1
            if 'pct_observed_degree' in r and r['pct_observed_degree']!='':
                num='n' if 'n' in r else 'subset_n'
                require(abs(float(r['pct_observed_degree'])-100*int(r[num])/int(r['observed_degree_n']))<=0.00000051,path.name+': degree percent');checks+=1
            if 'degree_share_of_307' in r:
                require(abs(float(r['degree_share_of_307'])-100*int(r['observed_degree_n'])/307)<=0.00000051,'Degree base share');checks+=1
            if r.get('occupation_status')=='coded' or r.get('occupation_row_type')=='named':
                require(int(r['n'])>=5,'Named occupation violates n>=5')
    require(rows_total==5751,'Numerical row count changed')
    profiles=read(ROOT/'evidence/employment/degree_role_profiles_20261016/SM5_5_degree_role_profiles_all_specifications.csv')
    groups=defaultdict(list)
    for r in profiles:groups[r['specification'],r['degree_group']].append(r)
    for key,part in groups.items():
        require(sum(int(r['n']) for r in part)==int(part[0]['observed_n']),'Joint states fail observed accounting')
        require(sum(int(r['n']) for r in part if r['joint_state']!='unscored')==int(part[0]['scored_n']),'Scored accounting')
    for spec in ('inclusive','no_hospital_override','conservative'):
        total=groups[spec,'all_observations'];by={r['joint_state']:int(r['n']) for r in total}
        require(sum(by.values())==307 and by['unscored']==4 and by['unclassifiable']==0,'Current observed/scored/U bases')
    fig=read(ROOT/'evidence/figures/full_figure_funding_by_degree_20261019_v2/plot_data.csv')
    require(len(fig)==156,'Figure 6 must retain 156 segments')
    sums=defaultdict(float)
    for r in fig:
        require(abs(float(r['width_pct'])-100*int(r['n'])/int(r['denominator_n']))<=1e-9,'Figure percentage mismatch')
        # Panel B uses the entire outside-degree base across all destinations.
        key=(r['panel'],r['degree_group'],r['group_dimension'],r['funding_degree_group'],r['connection_clear'])
        sums[key]+=float(r['width_pct']);checks+=1
    require(all(abs(v-100)<1e-8 for v in sums.values()),'Figure partitions do not sum to 100')
    print(json.dumps({'status':'PASS','csv_files':len(files),'csv_rows':rows_total,'arithmetic_checks':checks,'figure_cells':len(fig),'public_scope':'Saved aggregate arithmetic; no empirical record-level reconstruction.'},indent=2))

if __name__=='__main__':main()
