"""Clean optional group-point rebuild from supported exact category counts only."""
import argparse,csv,json,math
from pathlib import Path

def need(ok,message):
    if not ok:raise ValueError(message)
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def rebuild(counts_path,estimates_path):
    rows=read(Path(counts_path))
    counts={tuple(r[k] for k in ['outcome','population','group_id','period','category']):r for r in rows}
    need(len(counts)==len(rows)==2528,'Expected complete supported primary/continuing grid')
    def p(o,g,c,t,pop='primary'):
        r=counts[o,pop,g,t,c];y=int(r['selected_works']);n=int(r['eligible_works']);k=int(r['category_universe'])
        need(0<=y<=n and n>0 and r['report_supported']=='1','Invalid count or support')
        need(float(r['period_weight'])==.5,'Equal period weighting required')
        return (y+.5)/(n+(1 if o=='C8' else k/2))
    def avg(o,g,c):return (p(o,g,c,'2010-2016')+p(o,g,c,'2017-2023'))/2
    errors=[];number=0
    # Tables T3-T9 are the rows of the registry with these families.
    for r in read(Path(estimates_path)):
        family=r['family']
        if family in {'standardized_profile','early_profile','late_profile','temporal_change','shared_temporal_change'}:
            if r['report_supported']!='1':need(r['estimate']=='','Unsupported point changed');continue
            o,g,c=(r[k] for k in ['outcome','unit_id','category'])
            if family=='standardized_profile':v=avg(o,g,c)
            elif family in {'early_profile','late_profile'}:v=p(o,g,c,'2010-2016' if family=='early_profile' else '2017-2023')
            else:
                pop='continuing' if family=='shared_temporal_change' else 'primary';v=100*(p(o,g,c,'2017-2023',pop)-p(o,g,c,'2010-2016',pop))
            errors.append(abs(v-float(r['estimate'])));number+=1
        elif family=='pairwise_profile':
            o,a,b,c=(r[k] for k in ['outcome','group_a','group_b','category'])
            need(r['group_a_profile_id']=='|'.join(['standardized_profile',o,a,c]) and r['group_b_profile_id']=='|'.join(['standardized_profile',o,b,c]),'Pair direction mismatch')
            v=100*(avg(o,a,c)-avg(o,b,c));errors.append(abs(v-float(r['difference_pp'])));number+=1
    need(number==8656 and all(math.isfinite(e) and e<1e-8 for e in errors),'Adopted point mismatch')
    return {'status':'PASS','supported_count_rows':2528,'group_points':3376,'pairwise_points':5280,'max_absolute_error':max(errors),'institution_model_replay':False,'interval_replay':False,'held_out_model_replay':False}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--counts',type=Path,required=True);parser.add_argument('--estimates',type=Path,required=True);args=parser.parse_args()
    print(json.dumps(rebuild(args.counts,args.estimates),indent=2))
