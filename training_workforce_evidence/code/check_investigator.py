"""Verify investigator-count aggregate arithmetic without PI-level inputs.

Standard library only. This does not re-estimate models, covariance, networks,
deletion fits, simulation draws or score-bootstrap inversion.
"""
import argparse,csv,hashlib,json,math
from pathlib import Path

def beta_cf(a,b,x):
 qab=a+b;qap=a+1;qam=a-1;c=1.;d=1-qab*x/qap;d=1/(d if abs(d)>1e-300 else 1e-300);h=d
 for m in range(1,501):
  m2=2*m;aa=m*(b-m)*x/((qam+m2)*(a+m2));d=1+aa*d;c=1+aa/c
  d=1/(d if abs(d)>1e-300 else 1e-300);c=c if abs(c)>1e-300 else 1e-300;h*=d*c
  aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2));d=1+aa*d;c=1+aa/c
  d=1/(d if abs(d)>1e-300 else 1e-300);c=c if abs(c)>1e-300 else 1e-300;delta=d*c;h*=delta
  if abs(delta-1)<2e-14:return h
 raise RuntimeError('Incomplete beta did not converge')

def beta_cdf(x,a,b):
 if x<=0:return 0.
 if x>=1:return 1.
 bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)+a*math.log(x)+b*math.log1p(-x))
 return bt*beta_cf(a,b,x)/a if x<(a+1)/(a+b+2) else 1-bt*beta_cf(b,a,1-x)/b

def beta_quantile(p,a,b):
 lo=0.;hi=1.
 for _ in range(90):
  mid=(lo+hi)/2
  if beta_cdf(mid,a,b)<p:lo=mid
  else:hi=mid
 return (lo+hi)/2

def t_cdf(t,df):
 v=beta_cdf(df/(df+t*t),df/2,.5)/2
 return 1-v if t>=0 else v

def t_quantile(p,df):
 lo=0.;hi=1.
 while t_cdf(hi,df)<p:hi*=2
 for _ in range(90):
  mid=(lo+hi)/2
  if t_cdf(mid,df)<p:lo=mid
  else:hi=mid
 return (lo+hi)/2

def verify(bundle):
 def rows(n):
  with (bundle/'data'/n).open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
 checks=[]
 def near(a,b,label,tol=2e-9):
  a=float(a);b=float(b);err=abs(a-b)
  if err>tol*max(1,abs(a),abs(b)):raise RuntimeError(f'{label}: {a} != {b}')
  checks.append({'check':label,'absolute_error':err})
 def require(ok,label):
  if not ok:raise RuntimeError(label)
  checks.append({'check':label,'passed':True})
 with (bundle/'metadata/investigator_file_catalog.csv').open(encoding='utf-8',newline='') as f:catalog=list(csv.DictReader(f))
 for entry in catalog:
  p=bundle/entry['target']
  require(hashlib.sha256(p.read_bytes()).hexdigest()==entry['target_sha256'],'data_checksum:'+entry['target'])
  rr=rows(p.name)
  require(len(rr)==int(entry['rows']) and len(rr[0])==int(entry['columns']),'data_dimensions:'+entry['target'])
 near(t_cdf(1,1),.75,'t_CDF_Cauchy_identity',1e-12)
 near(t_quantile(.975,1),12.7062047361747,'t_quantile_Cauchy_identity',1e-11)
 old=rows('investigator_count_points_original.csv')
 for i,r in enumerate(old):
  near(math.exp(float(r['estimate_log_ratio'])),r['estimate_ratio'],f'original_point_exp_{i}')
  near(r['point_estimate'],r['estimate_ratio'],f'original_point_identity_{i}')
  near((float(r['estimate_ratio'])-1)*100,r['estimate_percent_change'],f'original_percent_change_{i}')
 for i,r in enumerate(rows('investigator_count_equal_pi_summary.csv')):
  require(int(r['funded_years'])+int(r['unfunded_years'])==int(r['PI_years']),f'summary_year_accounting_{i}')
  require(sum(int(r[k]) for k in ['increased_PIs','equal_PIs','decreased_PIs'])==int(r['PIs']),f'summary_PI_accounting_{i}')
  near(float(r['mean_funded_works_per_year'])-float(r['mean_unfunded_works_per_year']),r['mean_paired_difference_works_per_year'],f'equal_PI_mean_difference_{i}')
 for i,r in enumerate(rows('investigator_count_sample_support.csv')):
  require(int(r['funded_rows'])+int(r['resolved_unfunded_rows'])==int(r['rows']),f'sample_funding_accounting_{i}')
 direct=rows('investigator_count_common_fit_points.csv')
 for ownership in ['full','exclude_ever_for_profit']:
  sub=[x for x in direct if x['ownership']==ownership];rd=next(x for x in sub if x['degree_group']=='Research doctorate');ma=next(x for x in sub if x['degree_group']=='Masters')
  contrast=next(x for x in old if x['ownership']==ownership and x['degree_target']=='Masters minus research doctorate')
  near(float(ma['estimate_log_ratio'])-float(rd['estimate_log_ratio']),contrast['estimate_log_ratio'],'compatible_common_log_contrast_'+ownership)
  near(float(ma['estimate_ratio'])/float(rd['estimate_ratio']),contrast['estimate_ratio'],'compatible_common_ratio_'+ownership)
 inferred=[]
 for fn in ['investigator_count_inference_adopted.csv','investigator_count_joint_grouping_sensitivity.csv','investigator_count_target_grouping_sensitivity.csv']:
  for i,r in enumerate(rows(fn)):
   est=float(r['log_estimate']);se=float(r['se']);df=float(r['df']);p=2*(1-t_cdf(abs(est/se),df));q=t_quantile(.975,df);qb=t_quantile(1-.05/6,df)
   for col,val in {'rate_ratio':math.exp(est),'ci_lower':math.exp(est-q*se),'ci_upper':math.exp(est+q*se),'simultaneous_lower':math.exp(est-qb*se),'simultaneous_upper':math.exp(est+qb*se),'pvalue':p,'adjusted_pvalue':min(1,3*p)}.items():
    near(val,r[col],f'{fn}:{i}:{col}')
   inferred.append({'source_file':fn,'target':r['target'],'grouping':r['grouping'],'method':r['method'],'rate_ratio_recomputed':math.exp(est),'pointwise_lower_recomputed':math.exp(est-q*se),'pointwise_upper_recomputed':math.exp(est+q*se),'adjusted_p_recomputed':min(1,3*p)})
 primary=rows('investigator_count_inference_adopted.csv');target_map={'RD':'Research doctorate','M':'Masters','M_over_RD':'Masters minus research doctorate'}
 for r in primary:
  orig=next(x for x in old if x['ownership']=='full' and x['degree_target']==target_map[r['target']])
  near(r['log_estimate'],orig['estimate_log_ratio'],'unchanged_original_log_point_'+r['target'])
  require(r['grouping']=='joint_degree_all_topic_copi' and r['method']=='profile_HC3','adopted_method_'+r['target'])
 for fn in ['investigator_count_deletion_summary.csv','investigator_count_joint_deletion_summary.csv']:
  for i,r in enumerate(rows(fn)):
   if 'successful' in r:require(int(r['successful'])+int(r['failures'])==int(r['groups']),f'{fn}:{i}:deletion_accounting')
   near(float(r['exact_jackknife_se'])/float(r['profile_HC3_se'])-1,r['relative_se_difference'],f'{fn}:{i}:relative_SE_difference')
 for i,r in enumerate(rows('investigator_count_score_companion.csv')):
  near(min(1,3*float(r['pvalue'])),r['adjusted_pvalue'],f'score_Bonferroni_{i}')
 for i,r in enumerate(rows('investigator_count_simulation_summary.csv')):
  n=int(r['successful']);require(int(r['attempted'])==n+int(r['failed']),f'simulation_accounting_{i}')
  for prefix,lo,hi in [('coverage95','coverage95_mc_lower','coverage95_mc_upper'),('family_component_coverage','family_component_coverage_mc_lower','family_component_coverage_mc_upper')]:
   if not r[prefix]:continue
   successes=round(float(r[prefix])*n);near(successes/n,r[prefix],f'simulation_coverage_count_{i}:{prefix}')
   lower=0 if successes==0 else beta_quantile(.025,successes,n-successes+1)
   upper=1 if successes==n else beta_quantile(.975,successes+1,n-successes)
   near(lower,r[lo],f'simulation_CP_lower_{i}:{prefix}');near(upper,r[hi],f'simulation_CP_upper_{i}:{prefix}')
 with (bundle/'expected'/'primary_display_reference.csv').open(encoding='utf-8',newline='') as f:reference=list(csv.DictReader(f))
 for ref in reference:
  r=next(x for x in primary if x['target']==ref['target'])
  for field,digits in [('rate_ratio',3),('ci_lower',3),('ci_upper',3),('adjusted_pvalue',4)]:near(round(float(r[field]),digits),ref[field],f'SM4_T4c_display:{ref["target"]}:{field}',1e-12)
 return {'status':'passed','checks':len(checks),'maximum_absolute_error':max(x.get('absolute_error',0) for x in checks),'inference_rows_recomputed':len(inferred),'checks_detail':checks,'recomputed_inference':inferred,'scope':'Aggregate transformations and t/Bonferroni/Monte-Carlo interval arithmetic, not fresh model/covariance/network/deletion/simulation estimation.','new_model_fits':0}

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parents[1]);ap.add_argument('--output',type=Path);args=ap.parse_args();result=verify(args.bundle.resolve())
 if args.output:
  out=args.output.resolve();bundle=args.bundle.resolve()
  if out==bundle or bundle in out.parents:raise RuntimeError('Write verification output outside candidate')
  out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps({k:v for k,v in result.items() if k not in ['checks_detail','recomputed_inference']},indent=2))
