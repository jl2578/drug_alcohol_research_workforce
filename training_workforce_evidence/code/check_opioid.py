"""Standalone aggregate arithmetic and saved-summary inference replay, no fits.

Only reads supplied opioid component files. Standard-library Python 3.10+.
Run: python code/verify_opioid.py --bundle . --output-dir ../opioid_reproduced
"""
import argparse,csv,hashlib,json,math
from collections import defaultdict
from pathlib import Path

def rows(path):
 with path.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def beta_cf(a,b,x):
 qab=a+b;qap=a+1.;qam=a-1.;tiny=1e-300
 c=1.;d=1.-qab*x/qap
 if abs(d)<tiny:d=tiny
 d=1./d;h=d
 for m in range(1,1001):
  m2=2*m;aa=m*(b-m)*x/((qam+m2)*(a+m2))
  d=1.+aa*d
  if abs(d)<tiny:d=tiny
  c=1.+aa/c
  if abs(c)<tiny:c=tiny
  d=1./d;h*=d*c
  aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
  d=1.+aa*d
  if abs(d)<tiny:d=tiny
  c=1.+aa/c
  if abs(c)<tiny:c=tiny
  d=1./d;delta=d*c;h*=delta
  if abs(delta-1.)<3e-14:return h
 raise ArithmeticError('Incomplete-beta continued fraction failed to converge')
def beta_i(a,b,x):
 if x<=0:return 0.
 if x>=1:return 1.
 front=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
 if x<(a+1.)/(a+b+2.):return front*beta_cf(a,b,x)/a
 return 1.-front*beta_cf(b,a,1.-x)/b
def t_p(t,df):return beta_i(df/2.,.5,df/(df+t*t))
def t_critical(df):
 lo=0.;hi=16.
 while t_p(hi,df)>.05:hi*=2
 for _ in range(100):
  mid=(lo+hi)/2
  if t_p(mid,df)>.05:lo=mid
  else:hi=mid
 return (lo+hi)/2
def f_p(stat,dfn,dfd):return beta_i(dfd/2.,dfn/2.,dfd/(dfd+dfn*stat))
def num(r,f):return float(r[f])
def write_csv(p,rs):
 with p.open('w',encoding='utf-8',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rs[0]),lineterminator='\n');w.writeheader();w.writerows(rs)

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--bundle',required=True,type=Path)
 parser.add_argument('--output-dir',required=True,type=Path)
 args=parser.parse_args();bundle=args.bundle.resolve();out=args.output_dir.resolve()
 if out==bundle or bundle in out.parents:raise SystemExit('Output directory must be outside component')
 out.mkdir(parents=True,exist_ok=True)
 checks=[]
 def near(label,actual,expected,tol=1e-8):
  ok=math.isfinite(float(actual)) and math.isfinite(float(expected)) and math.isclose(float(actual),float(expected),rel_tol=tol,abs_tol=tol)
  checks.append({'check':label,'passed':ok,'actual':actual,'expected':expected})
 def same(label,actual,expected):checks.append({'check':label,'passed':actual==expected,'actual':actual,'expected':expected})
 catalog=rows(bundle/'metadata/file_catalog.csv');schema={r['file']:r for r in rows(bundle/'metadata/schema_index.csv')}
 data={}
 for r in catalog:
  p=(bundle/r['file']).resolve()
  if bundle not in p.parents:raise RuntimeError('File catalog escapes component')
  content=p.read_bytes();same('hash:'+r['file'],hashlib.sha256(content).hexdigest(),r['sha256'])
  a=rows(p);same('row_count:'+r['file'],len(a),int(r['rows']))
  same('schema:'+r['file'],list(a[0]) if a else [],json.loads(schema[r['file']]['columns_json']))
  same('LF:'+r['file'],b'\r' in content,False)
  data[p.stem]=a
 expected=json.loads((bundle/'expected/primary_snapshot.json').read_text(encoding='utf-8'))
 same('data_file_count',len(data),expected['data_files'])
 same('data_row_count',sum(len(a) for a in data.values()),expected['data_rows'])
 # Arithmetic identities use all rows, not only headline cells.
 for name in ['population_accounting','annual_corpus','annual_nida_groups','fixed_baseline_period_profiles']:
  for i,r in enumerate(data[name],1):
   base=f'{name}:{i}:';n=num(r,'works');opioid=num(r,'opioid_works');years=num(r,'years')
   near(base+'opioid_share_pct',100*opioid/n,num(r,'opioid_share_pct'))
   near(base+'works_per_year',n/years,num(r,'works_per_year'))
   near(base+'opioid_works_per_year',opioid/years,num(r,'opioid_works_per_year'))
   near(base+'label_accounting',num(r,'complete_label_works')+num(r,'incomplete_label_works'),n,0.)
   near(base+'incomplete_label_partition',num(r,'incomplete_observed_opioid_works')+num(r,'incomplete_without_observed_opioid_works'),num(r,'incomplete_label_works'),0.)
   near(base+'upper_scenario',100*(opioid+num(r,'incomplete_without_observed_opioid_works'))/n,num(r,'upper_share_pct_if_unresolved_positive'))
 pop={r['population']:r for r in data['population_accounting']}
 full=pop['All adopted works'];nida=pop['NIDA-connected including dual'];other=pop['No identified NIDA/NIAAA connection'];excluded=pop['NIAAA-only excluded from primary pair'];pair=pop['Primary descriptive pair']
 for field,expkey in [('works','full_corpus_works'),('opioid_works','full_corpus_opioid_works')]:
  near('headline:'+field,num(full,field),expected[expkey],0.)
  near('population_partition:'+field,num(nida,field)+num(other,field)+num(excluded,field),num(full,field),0.)
  near('pair_partition:'+field,num(nida,field)+num(other,field),num(pair,field),0.)
 near('primary_pair_expected',num(pair,'works'),expected['primary_pair_works'],0.)
 for field in ['works','opioid_works','complete_label_works','incomplete_label_works','incomplete_observed_opioid_works','incomplete_without_observed_opioid_works']:
  near('annual_corpus_to_population:'+field,sum(num(r,field) for r in data['annual_corpus']),num(full,field),0.)
  for group,poprow in [('1',nida),('0',other)]:
   near('annual_group_to_population:'+group+':'+field,sum(num(r,field) for r in data['annual_nida_groups'] if r['nida_connected']==group),num(poprow,field),0.)
 # Rebuild fixed full-descriptive window totals from annual group cells.
 profiles={(r['sample'],r['lag_years'],r['period'],r['nida_connected']):r for r in data['fixed_baseline_period_profiles']}
 for r in data['fixed_baseline_period_profiles']:
  if r['sample']!='Full descriptive pair':continue
  annual=[a for a in data['annual_nida_groups'] if int(r['start_year'])<=int(a['completion_year'])<=int(r['end_year']) and a['nida_connected']==r['nida_connected']]
  for f in ['works','opioid_works','complete_label_works','incomplete_label_works','incomplete_observed_opioid_works','incomplete_without_observed_opioid_works','complete_role_works']:
   near('period_from_annual:'+r['lag_years']+r['period']+r['nida_connected']+':'+f,sum(num(a,f) for a in annual),num(r,f),0.)
 for i,r in enumerate(data['fixed_baseline_share_contrasts'],1):
  changes={}
  for group,label in [('1','nida'),('0','comparison')]:
   base=profiles[(r['sample'],r['lag_years'],'baseline',group)];post=profiles[(r['sample'],r['lag_years'],'post',group)]
   near(f'contrast:{i}:{label}_baseline',num(base,'opioid_share_pct'),num(r,label+'_baseline_share_pct'))
   near(f'contrast:{i}:{label}_post',num(post,'opioid_share_pct'),num(r,label+'_post_share_pct'))
   changes[label]=num(post,'opioid_share_pct')-num(base,'opioid_share_pct')
   near(f'contrast:{i}:{label}_share_change',changes[label],num(r,label+'_share_change_pp'))
   near(f'contrast:{i}:{label}_annualized_growth',100*(num(post,'opioid_works_per_year')/num(base,'opioid_works_per_year')-1),num(r,label+'_annualized_opioid_growth_pct'))
  near(f'contrast:{i}:difference',changes['nida']-changes['comparison'],num(r,'difference_in_share_changes_pp'))
 primary={r['lag_years']:r for r in data['adjusted_lag_results'] if r['variant']=='primary'}
 for lag,r in primary.items():
  exp=expected['primary'][lag]
  for f in ['estimate_pp','ci95_low_pp','ci95_high_pp','n_works']:near('frozen_primary:'+lag+':'+f,num(r,f),exp[f])
  near('frozen_primary:'+lag+':institutions',num(r,'n_institution_levels'),exp['institutions'],0.)
  near('sample_connection_partition:'+lag,num(r,'n_connected')+num(r,'n_comparison'),num(r,'n_works'),0.)
  eligible=[a for a in data['fixed_baseline_period_profiles'] if a['sample']=='Primary metadata-eligible pair' and a['lag_years']==lag]
  near('model_vs_eligible_profiles:'+lag,sum(num(a,'works') for a in eligible),num(r,'n_works'),0.)
  ledger=sorted([a for a in data['sequential_exclusion_ledger'] if a['lag_years']==lag],key=lambda a:int(a['step']))
  last=None
  for a in ledger:
   near('exclusion_arithmetic:'+lag+':'+a['step'],num(a,'entering_works')-num(a,'removed_works'),num(a,'retained_works'),0.)
   if last is not None:near('exclusion_continuity:'+lag+':'+a['step'],num(a,'entering_works'),last,0.)
   last=num(a,'retained_works')
  near('exclusion_final_n:'+lag,last,num(r,'n_works'),0.)
  near('exclusion_final_opioid:'+lag,num(ledger[-1],'retained_opioid_works'),num(r,'n_opioid_works'),0.)
 # Coverage shares partition stated variable; no cross-variable summation.
 groups=defaultdict(list)
 for r in data['degree_field_coverage']:groups[tuple(r[f] for f in ['sample','lag_years','period','nida_connected','variable'])].append(r)
 for key,aa in groups.items():
  total=sum(num(r,'works') for r in aa)
  for i,r in enumerate(aa):near('coverage_share:'+str(key)+':'+str(i),100*num(r,'works')/total,num(r,'share_pct'))
 # Recompute saved-summary inference, not coefficients or standard errors.
 infer_count=0
 def inference(label,r,estimate,se,df,lo,hi,p):
  nonlocal infer_count
  if r[estimate]=='' or r[se]=='':return
  est=num(r,estimate);sd=num(r,se);degrees=float(df);critical=t_critical(degrees)
  near(label+':CI_low',est-critical*sd,num(r,lo))
  near(label+':CI_high',est+critical*sd,num(r,hi))
  near(label+':p',t_p(est/sd,degrees),num(r,p))
  infer_count+=1
 for name in ['adjusted_lag_results','largest_institution_deletions']:
  for i,r in enumerate(data[name],1):
   inference(name+':'+str(i),r,'estimate_pp','se_pp',r['cluster_df'],'ci95_low_pp','ci95_high_pp','p_two_sided')
   near(name+':CR1:'+str(i),(num(r,'n_works')-1)/(num(r,'n_works')-num(r,'design_rank'))*num(r,'clusters')/(num(r,'clusters')-1),num(r,'cr1_correction'))
   if r['broader_dependence_se_pp']:
    inference(name+':broader:'+str(i),r,'estimate_pp','broader_dependence_se_pp',num(r,'broader_dependence_clusters')-1,'broader_dependence_ci95_low_pp','broader_dependence_ci95_high_pp','broader_dependence_p_two_sided')
 for i,r in enumerate(data['pretrend_annual_terms'],1):inference('annual_pretrend:'+str(i),r,'coefficient_pp','se_pp',r['cluster_df'],'ci_low_pp','ci_high_pp','p')
 for r in data['pretrend_diagnostics']:
  if r['test_reference']=='t':inference('pretrend:'+r['diagnostic'],r,'estimate_pp','se_pp',r['df_denom'],'ci95_low_pp','ci95_high_pp','p_two_sided_or_joint')
  elif r['test_reference']=='F':near('pretrend_joint_F',f_p(num(r,'test_statistic'),num(r,'df_num'),num(r,'df_denom')),num(r,'p_two_sided_or_joint'))
 ordered=sorted(primary.items(),key=lambda item:num(item[1],'p_two_sided'));last=0.
 for rank,(lag,r) in enumerate(ordered):
  adjusted=max(last,min(1.,(len(ordered)-rank)*num(r,'p_two_sided')));last=adjusted
  near('primary_Holm:'+lag,adjusted,num(r,'primary_holm_p'))
 # Fitted-bound summaries have different literal and tolerance definitions.
 thresholds=[]
 for lag,model in primary.items():
  aa=[r for r in data['primary_fitted_values_by_cell'] if r['lag_years']==lag];total=next(r for r in aa if r['period']=='all');cells=[r for r in aa if r['period']!='all']
  for f in ['works','observed_opioid_works','fitted_below_zero_n','fitted_above_one_n','fitted_below_minus_tolerance_1e_minus10_n','fitted_above_one_plus_tolerance_1e_minus10_n']:
   near('fitted_cells_sum:'+lag+':'+f,sum(num(r,f) for r in cells),num(total,f),0.)
  for i,r in enumerate(aa):
   near('fitted_literal_below_fraction:'+lag+':'+str(i),num(r,'fitted_below_zero_n')/num(r,'works'),num(r,'fitted_below_zero_fraction'))
   near('fitted_literal_above_fraction:'+lag+':'+str(i),num(r,'fitted_above_one_n')/num(r,'works'),num(r,'fitted_above_one_fraction'))
  near('fitted_literal_model_fraction:'+lag,num(total,'fitted_below_zero_fraction'),num(model,'fraction_fitted_below_zero'))
  thresholds.append({'lag_years':lag,'completion_window':model['post'],'works':int(num(total,'works')),'literal_below_zero_n':int(num(total,'fitted_below_zero_n')),
   'literal_below_zero_pct':100*num(total,'fitted_below_zero_n')/num(total,'works'),'below_minus_1e_minus10_n':int(num(total,'fitted_below_minus_tolerance_1e_minus10_n')),
   'below_minus_1e_minus10_pct':100*num(total,'fitted_below_minus_tolerance_1e_minus10_n')/num(total,'works'),
   'literal_above_one_n':int(num(total,'fitted_above_one_n')),'above_one_plus_1e_minus10_n':int(num(total,'fitted_above_one_plus_tolerance_1e_minus10_n'))})
 for i,r in enumerate(data['institutional_overlap']):near('support_fraction:'+str(i),num(r,'works')/num(primary[r['lag_years']],'n_works'),num(r,'fraction_of_primary_works'))
 for r in data['primary_diagnostic_summary']:
  near('diagnostic_residual_df:'+r['lag_years'],num(r,'n_works')-num(r,'design_rank'),num(r,'residual_df'),0.)
  for f in ['estimate_pp','se_pp','ci95_low_pp','ci95_high_pp','p_two_sided','n_works']:near('primary_summary_crossfile:'+r['lag_years']+':'+f,num(r,f),num(primary[r['lag_years']],f))
 figA=[{'completion_year':r['completion_year'],'group':r['group'],'works':r['works'],'opioid_works':r['opioid_works'],'opioid_share_pct':100*num(r,'opioid_works')/num(r,'works')} for r in data['annual_nida_groups']]
 figB=[{'completion_window':r['post'],'estimate_pp':r['estimate_pp'],'ci95_low_pp':r['ci95_low_pp'],'ci95_high_pp':r['ci95_high_pp'],'raw_p':r['p_two_sided'],'primary_Holm_p':r['primary_holm_p'],'n_works':r['n_works']} for r in primary.values()]
 write_csv(out/'figure_F4A_annual_shares.csv',figA);write_csv(out/'figure_F4B_primary_results.csv',figB);write_csv(out/'fitted_bound_thresholds.csv',thresholds)
 failures=[c for c in checks if not c['passed']]
 report={'status':'passed' if not failures else 'failed','checks':len(checks),'failures':failures,'model_summary_inference_replays':infer_count,'data_files':len(data),'data_rows':sum(len(a) for a in data.values()),
 'scientific_models_fitted':0,'scope':'aggregate arithmetic and inference from saved estimates/SEs;no original fit/data-selection reconstruction','fitted_bound_thresholds':thresholds}
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['fitted_bound_thresholds','failures']},indent=2))
 if failures:raise SystemExit('Verification failed;see verification.json')
if __name__=='__main__':main()
