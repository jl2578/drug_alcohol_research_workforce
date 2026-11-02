"""Offline arithmetic checks on retained aggregate evidence; no coding or bootstrap replay."""
import sys
sys.dont_write_bytecode=True
import argparse,csv,json,math
from collections import Counter,defaultdict
from pathlib import Path
ROOT=None
CHECKS=[]
def require(ok,message):
    if not ok:raise ValueError(message)
    CHECKS.append(message)
def close(a,b,label,tol=1e-10):
    if a in ('',None) or b in ('',None):require(a in ('',None) and b in ('',None),label)
    else:require(math.isclose(float(a),float(b),rel_tol=tol,abs_tol=tol),label)
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as h:return list(csv.DictReader(h))
def wilson(k,n):
    if n==0:return (None,None)
    z=1.959963984540054;p=k/n;den=1+z*z/n;c=(p+z*z/(2*n))/den;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return (max(0,c-h),min(1,c+h))
def kappa(pairs):
    n=sum(count for a,b,count in pairs)
    if not n:return None
    aa=Counter();bb=Counter();hits=0
    for a,b,count in pairs:aa[a]+=count;bb[b]+=count;hits+=count*(a==b)
    pe=sum(aa[c]*bb[c] for c in aa.keys()|bb.keys())/n**2
    return (hits/n-pe)/(1-pe) if 1-pe>1e-12 else None
def arithmetic():
    metrics=0;wilsons=0;rows_seen=0
    for p in sorted((ROOT/'aggregates').rglob('*.csv')):
        for i,row in enumerate(read(p),1):
            rows_seen+=1;label=p.name+':'+str(i)
            if {'numerator_n','denominator_n','estimate'}<=set(row):
                k,n=int(row['numerator_n']),int(row['denominator_n']);require(0<=k<=n,label+' bounded count');close(k/n if n else None,row['estimate'],label+' n/N');metrics+=1
                cols=('ci95_lower','ci95_upper') if 'ci95_lower' in row else ('wilson_95_lower','wilson_95_upper')
                if all(c in row for c in cols):
                    for a,b in zip(wilson(k,n),[row[c] for c in cols]):close(a,b,label+' Wilson')
                    wilsons+=1
            elif {'agreement_n','comparable_n','exact_agreement'}<=set(row):
                k,n=int(row['agreement_n']),int(row['comparable_n']);close(k/n if n else None,row['exact_agreement'],label+' agreement');metrics+=1
                if 'wilson_95_lower' in row:
                    for a,b in zip(wilson(k,n),(row['wilson_95_lower'],row['wilson_95_upper'])):close(a,b,label+' Wilson')
                    wilsons+=1
            elif {'agreement_n','jointly_coded_n','exact_category_or_set_agreement'}<=set(row):
                k,n=int(row['agreement_n']),int(row['jointly_coded_n']);close(k/n,row['exact_category_or_set_agreement'],label+' agreement');metrics+=1
                for a,b in zip(wilson(k,n),(row['exact_wilson_95_lower'],row['exact_wilson_95_upper'])):close(a,b,label+' Wilson')
                wilsons+=1
            if {'n','N','percent'}<=set(row):
                k,n=int(row['n']),int(row['N']);close(round(100*k/n,4) if n else None,row['percent'],label+' coverage percent (source rounds to four decimals)');metrics+=1
            if 'search_capture_percent' in row:
                n=int(row['linked_work_N']);k=int(row['candidate_frame_work_n']);a=int(row['assessable_candidate_work_n']);inc=int(row['included_work_n'])
                require(k+int(row['not_retrieved_work_n'])==n,label+' retrieved partition')
                require(a+int(row['no_usable_abstract_work_n'])==k,label+' assessable partition')
                require(inc+sum(int(row[c]) for c in ('retrieved_excluded_work_n','scientific_undetermined_work_n','operational_failure_work_n'))==a,label+' disposition partition')
                for key,x,y in [('search_capture_percent',k,n),('included_of_linked_percent',inc,n),('included_of_retrieved_percent',inc,k),('included_of_assessable_retrieved_percent',inc,a),('nonretrieval_share_of_noninclusion_percent',int(row['not_retrieved_work_n']),n-inc)]:close(100*x/y if y else None,row[key],label+' '+key)
                for val,col in zip(wilson(k,n),('search_capture_wilson95_lower','search_capture_wilson95_upper')):close(None if val is None else 100*val,row[col],label+' Wilson percent')
                metrics+=5;wilsons+=1
    content=ROOT/'aggregates/measurement/rq1_20261013'
    cross=read(content/'category_crosstabs.csv');summaries={r['field']:r for r in read(content/'content_performance_summary.csv')}
    for field,s in summaries.items():
        rr=[r for r in cross if r['field']==field];pairs=[(r['human_value_json'],r['model_value_json'],int(r['n'])) for r in rr]
        close(sum(n for _,_,n in pairs),s['conditional_comparable_n'],field+' cross-tab base')
        close(sum(n for a,b,n in pairs if a==b),s['conditional_exact_n'],field+' cross-tab exact')
        if field!='data_type':close(kappa(pairs),s['nominal_kappa'],field+' aggregate kappa')
        else:
            numerator=sum(n*len(set(json.loads(a))&set(json.loads(b)))/len(set(json.loads(a))|set(json.loads(b))) for a,b,n in pairs)
            close(numerator/sum(n for _,_,n in pairs),s['conditional_mean_jaccard'],field+' aggregate Jaccard')
    cap=ROOT/'aggregates/current_capture';degree=read(cap/'degree_level_summary.csv');disp=read(cap/'adopted_disposition_summary.csv')
    for scenario in {(r['extension_years'],r['match_definition']) for r in degree}:
        dd=[r for r in degree if (r['extension_years'],r['match_definition'])==scenario];ss=[r for r in disp if (r['extension_years'],r['match_definition'])==scenario]
        require(len(dd)==2,'Two frame degree levels '+str(scenario))
        require(sum(int(r['distinct_matched_works']) for r in dd)==sum(int(r['distinct_matched_works']) for r in ss),'Degree and disposition total '+str(scenario))
        require(len({r['scenario_distinct_works'] for r in ss})==1,'Constant scenario base '+str(scenario))
        close(sum(int(r['distinct_matched_works']) for r in ss),ss[0]['scenario_distinct_works'],'Disposition partition '+str(scenario))
    return {'csv_rows_inspected':rows_seen,'proportions_recomputed':metrics,'wilson_intervals_recomputed':wilsons,'content_kappa_fields':8,'content_jaccard_fields':1}
def main():
    global ROOT
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    ROOT=args.root.resolve()
    summary=arithmetic()
    result={'status':'PASS','scope':'aggregate arithmetic; saved bootstrap intervals are supplied evidence, not newly resampled here','checks_passed':len(CHECKS),**summary}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(result))
if __name__=='__main__':main()
