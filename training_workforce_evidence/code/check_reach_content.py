"""Candidate-only RQ3 aggregate arithmetic and source-integrity verification.

This replays proportions, contrasts, overlap arithmetic and common-field weights.
It does not refit institutional/PI models or reconstruct private record linkage.
"""
import argparse,csv,hashlib,json,math
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

def read(p):
 with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output-dir',type=Path,required=True);args=ap.parse_args()
 bundle=args.bundle.resolve();output=args.output_dir.resolve()
 if output==bundle or bundle in output.parents:raise ValueError('Write verification outputs outside the candidate bundle')
 checks=[]
 def check(name,got,want,tol=1e-9):
  if isinstance(got,(int,float)) and isinstance(want,(int,float)):ok=math.isclose(got,want,rel_tol=tol,abs_tol=tol)
  else:ok=got==want
  checks.append({'check':name,'passed':ok,'got':got,'expected':want})
 def pct(name,n,d,p):
  if float(d)>0:check(name,float(p),100*float(n)/float(d))
  else:check(name+'_zero_denominator',p in ['',None],True)
 catalog=read(bundle/'metadata/dataset_catalog.csv')
 tables={}
 for row in catalog:
  path=bundle/row['candidate_relative_path']
  check(row['dataset_id']+'_sha256',hashlib.sha256(path.read_bytes()).hexdigest(),row['candidate_sha256'])
  data=read(path);tables[row['dataset_id']]=data
  check(row['dataset_id']+'_rows',len(data),int(row['rows']))
 check('complete_component_datasets',len(tables),44)
 def t(n):return tables['NA'+str(n).zfill(2)]
 def i(r,k):return int(r[k])
 def f(r,k):return float(r[k])
 # Design labels retain only equality relationships, not private sample fingerprints.
 design_labels={r['unique_design_id'] for r in t(18) if r['unique_design_id']}
 check('opaque_design_label_universe',design_labels=={f'DESIGN{n:04d}' for n in range(1,1069)},True)
 for n in [18,19,20,25]:
  check(f'NA{n}_opaque_design_reference_integrity',all(r['unique_design_id'] in design_labels for r in t(n)),True)
 # Explicit source30 -> B/C-only27 projection; institutional panelA is separate.
 check('NA73_BC_only_27rows',len(t(73)),27)
 check('NA73_panelB_three_rows',sum(r['panel']=='B' for r in t(73)),3)
 check('NA73_panelC_twentyfour_rows',sum(r['panel']=='C' for r in t(73)),24)

 # Cohort accounting and source mapping are different from timing/funding-ready model totals.
 check('adopted_distinct_works',sum(i(r,'adopted_works') for r in t(2)),13227)
 check('all_topic_mapped_source_accounting',sum(i(r,'all_topic_source_works') for r in t(3)),1142707)
 for j,r in enumerate(t(4),1):
  check(f'NA04_{j}_category_share',f(r,'finite_corpus_category_share'),i(r,'timing_resolved_in_frame_numerator')/i(r,'timing_resolved_outcome_eligible_denominator'))

 # Complete reach populations and institute/route unions, not selected headline rows.
 for n in [36,44]:
  for j,r in enumerate(t(n),1):
   pct(f'NA{n}_{j}_reach',r['numerator'],r['denominator'],r['estimate_percent'])
   check(f'NA{n}_{j}_probability',f(r,'estimate_probability'),f(r,'estimate_percent')/100)
 reach={(r['ownership'],r['population'],r['connection_definition'],r['institute']):r for r in t(36)}
 for pop,num,den in [('All credentials',4067,13227),('Research doctorate',3236,7964),('Masters',758,3460)]:
  r=reach[('full',pop,'combined_clear','NIDA/NIAAA')]
  check('primary_'+pop+'_numerator',i(r,'numerator'),num);check('primary_'+pop+'_denominator',i(r,'denominator'),den)
 for j,r in enumerate(t(42),1):
  check(f'route_union_{j}',i(r,'union_n'),i(r,'PI_n')+i(r,'award_n')-i(r,'both_routes_n'))
  check(f'route_partition_{j}',i(r,'union_n')+i(r,'no_identified_connection_n'),i(r,'denominator'))
  check(f'route_PI_only_{j}',i(r,'PI_without_award_n'),i(r,'PI_n')-i(r,'both_routes_n'))
  for a,b in [('PI_n','PI_percent'),('award_n','award_percent'),('union_n','union_percent'),('no_identified_connection_n','no_identified_connection_percent')]:pct(f'route_{j}_{b}',r[a],r['denominator'],r[b])
 for j,r in enumerate(t(43),1):
  d=i(r,'Masters_numerator')/i(r,'Masters_denominator')-i(r,'RD_numerator')/i(r,'RD_denominator')
  check(f'degree_reach_difference_{j}',f(r,'difference_probability'),d);check(f'degree_reach_pp_{j}',f(r,'difference_percentage_points'),100*d)
 for j,r in enumerate(t(45),1):pct(f'objective_portfolio_{j}',r['category_n'],r['all_credential_usable_C5_denominator'],r['category_portfolio_share_percent'])
 for j,r in enumerate(t(46),1):
  check(f'institute_union_{j}',i(r,'pooled_union_n'),i(r,'NIDA_n')+i(r,'NIAAA_n')-i(r,'both_institutes_n'))
  check(f'institute_partition_{j}',i(r,'pooled_union_n')+i(r,'no_identified_connection_n'),i(r,'category_denominator'))

 # Category/count denominators reproduce all three616-target observed profiles.
 for j,r in enumerate(t(38),1):
  for prefix in ['connected','remaining']:
   pct(f'flat_content_{j}_{prefix}',r[prefix+'_category_n'],r[prefix+'_n'],r[prefix+'_percent'])
  check(f'flat_difference_{j}',f(r,'difference_pp'),f(r,'connected_percent')-f(r,'remaining_percent'))
 for n in [37,40,41]:
  for j,r in enumerate(t(n),1):
   metric=r['metric']
   if metric in ['connected_profile_percent','remaining_profile_percent']:q=float(r['numerator'])/float(r['denominator'])
   elif r['degree_target']=='Masters minus research doctorate':
    nums=json.loads(r['category_counts_all_groups_json']);dens=json.loads(r['denominator'])
    q=(nums['Masters']['1']/dens['Masters']['1']-nums['Masters']['0']/dens['Masters']['0'])-(nums['Research doctorate']['1']/dens['Research doctorate']['1']-nums['Research doctorate']['0']/dens['Research doctorate']['0'])
   else:
    nums=json.loads(r['numerator']);dens=json.loads(r['denominator']);q=nums['connected']/dens['connected']-nums['remaining']/dens['remaining']
   check(f'NA{n}_{j}_probability_or_difference',f(r,'estimate_probability_or_difference'),q)
   check(f'NA{n}_{j}_percent_or_pp',f(r,'estimate_percent_or_pp'),100*q)
 # Field-standardization replay: recompute weights and sum exact weighted fractions.
 weights=defaultdict(float)
 for j,r in enumerate(t(50),1):
  if r['common_support']=='1':
   check(f'field_weight_exact_{j}',f(r,'reference_weight'),float(Fraction(r['reference_weight_exact'])))
   weights[(r['degree_target'],r['outcome'])]+=f(r,'reference_weight')
 for key,v in weights.items():check('field_weight_sum_'+str(key),v,1)
 weighted=defaultdict(lambda:[0.0,0.0])
 for j,r in enumerate(t(49),1):
  for group in ['connected','remaining']:
   if i(r,group+'_n'):
    pct(f'within_field_{j}_{group}',r[group+'_category_n'],r[group+'_n'],r[group+'_percent'])
  if r['common_support']=='1':
   key=(r['degree_target'],r['outcome'],r['category'])
   for pos,group in enumerate(['connected','remaining']):
    v=f(r,'reference_weight')*i(r,group+'_category_n')/i(r,group+'_n');weighted[key][pos]+=v
    check(f'within_field_weighted_{j}_{group}',f(r,'weighted_'+group+'_contribution'),v)
 for j,r in enumerate(t(52),1):
  key=(r['degree_target'],r['outcome'],r['category']);a,b=weighted[key]
  check(f'common_mix_connected_{j}',f(r,'common_mix_connected_percent'),100*a)
  check(f'common_mix_remaining_{j}',f(r,'common_mix_remaining_percent'),100*b)
  check(f'common_mix_difference_{j}',f(r,'common_mix_difference_pp'),100*(a-b))
  check(f'common_mix_fraction_connected_{j}',float(Fraction(r['common_mix_connected_exact'])),a)
  check(f'common_mix_fraction_difference_{j}',float(Fraction(r['common_mix_difference_exact'])),a-b)
  check(f'common_mix_decomposition_{j}',f(r,'total_change_pp'),f(r,'support_restriction_change_pp')+f(r,'field_reweighting_change_pp'))
 # Current convenient naming projections must agree with the complete raw/weighted family.
 common={(r['degree_target'],r['outcome'],r['category']):r for r in t(52)}
 for j,r in enumerate(t(65),1):
  v=common[(r['degree'],r['outcome'],r['category'])]
  check(f'current_mix_alias_{j}',f(r,'common_field_mix_content_difference_pp'),f(v,'common_mix_difference_pp'))
  check(f'current_crude_alias_{j}',f(r,'raw_content_difference_pp'),f(v,'full_crude_difference_pp'))
 for j,r in enumerate(t(63),1):
  check(f'field_reach_partition_{j}',i(r,'connected_works_n')+i(r,'remaining_works_n'),i(r,'all_works_n'))
  check(f'field_reach_union_{j}',i(r,'NIDA_connected_works_n')+i(r,'NIAAA_connected_works_n')-i(r,'both_institutes_connected_n'),i(r,'connected_works_n'))
  pct(f'field_reach_{j}',r['connected_works_n'],r['all_works_n'],r['identified_NIDA_NIAAA_funding_reach_percent'])
 for j,r in enumerate(t(64),1):
  if i(r,'connected_eligible_n') and i(r,'remaining_eligible_n'):
   pct(f'field_profile_conn_{j}',r['connected_category_n'],r['connected_eligible_n'],r['connected_profile_percent'])
   pct(f'field_profile_remain_{j}',r['remaining_category_n'],r['remaining_eligible_n'],r['remaining_profile_percent'])
   check(f'field_profile_difference_{j}',f(r,'content_difference_percentage_points'),f(r,'connected_profile_percent')-f(r,'remaining_profile_percent'))
 # Equal-PI differences are arithmetic within the supplied mean summaries; pooled ratios are not substituted.
 for j,r in enumerate(t(28),1):
  check(f'equal_PI_difference_{j}',f(r,'mean_paired_difference_pp'),f(r,'mean_funded_percent')-f(r,'mean_unfunded_percent'))
  check(f'equal_PI_direction_partition_{j}',i(r,'increased_PIs')+i(r,'equal_PIs')+i(r,'decreased_PIs'),i(r,'PIs'))
 # Saved model point transformations, not new estimation/inference.
 for j,r in enumerate(t(17),1):
  if r['rate_ratio']:
   check(f'institutional_content_ratio_{j}',f(r,'rate_ratio'),math.exp(f(r,'log_rate_ratio')))
   check(f'institutional_content_percent_{j}',f(r,'percent_change'),100*(f(r,'rate_ratio')-1))
  check(f'institutional_content_no_invented_interval_{j}',all(r[k]=='' for k in ['pointwise95_lower','pointwise95_upper','familywise95_lower','familywise95_upper']),True)
 for j,r in enumerate(t(73),1):pct(f'Figure5BC_{j}',r['numerator'],r['denominator'],r['value'])
 for r in tables['DERIVED01']:
  want={'Research doctorate':(2784,6615),'Masters':(661,2678)}[r['degree_group']]
  check(r['degree_group']+'_both_roles_numerator',i(r,'numerator_n'),want[0]);check(r['degree_group']+'_both_roles_denominator',i(r,'denominator_n'),want[1])
  pct(r['degree_group']+'_both_roles_percent',r['numerator_n'],r['denominator_n'],r['reach_percent'])
 output.mkdir(parents=True,exist_ok=True)
 result={'passed':all(x['passed'] for x in checks),'checks':len(checks),'failed':[x for x in checks if not x['passed']],
   'data_tables':len(tables),'science_models_fitted':0,'private_inputs_read':0,
   'scope':'Candidate-only exact count/ratio/overlap/field-weight arithmetic, current Figure5B/C replay and saved model-point transformations. Equal-PI means and fitted model coefficients themselves are supplied results, not reconstructed from individual observations.'}
 (output/'reach_content_verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(result,indent=2))
 if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
