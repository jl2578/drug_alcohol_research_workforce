"""Run offline behavior checks from the extracted package: python tests/test_behavior.py."""
from pathlib import Path
import contextlib, csv, io, json, sys, hashlib, shutil, subprocess, urllib.error, urllib.request
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'src/coding'))
import public_workflow as w
from recover_v5_rev14_hybrid_checkpoint import recover
import tempfile
def coded(value):
    return {'value':value,'coding_status':'coded','confidence':'high'}
def noncoded(status):
    return {'value':None,'coding_status':status,'confidence':None}
def unit(kind, compact=False):
    result={'aim_id':'a1','source_sentence_ids':['s2']}
    if kind=='in':
        result.update({'substance_roles':coded(['use_as_outcome']),
                       'stated_purposes':coded(['use_or_misuse']),
                       'unrelated_therapeutic_indication_tested':coded('no'),
                       'substance_all':coded(['alcohol']),'substance_primary':coded('alcohol'),
                       'substance_assignment_basis':coded('named_focal_substance')})
    else:
        state='not_applicable' if kind=='out' else 'cannot_determine'
        result.update({'substance_roles':coded(['none']) if kind=='out' else noncoded(state),
                       'stated_purposes':noncoded(state),
                       'unrelated_therapeutic_indication_tested':noncoded(state),
                       'substance_all':noncoded(state),'substance_primary':noncoded(state),
                       'substance_assignment_basis':noncoded(state)})
    return result
(ROOT/'private').mkdir(exist_ok=True)
TEST=Path(tempfile.mkdtemp(prefix='behavior_',dir=ROOT/'private')).resolve()
assert TEST.is_relative_to((ROOT/'private').resolve())
examples=[('1','Synthetic example: alcohol survey','We surveyed adults about alcohol use during the preceding month. We estimated prevalence from newly collected questionnaire responses.','present'),
          ('2','Synthetic example: leaf growth','We measured the growth of maple leaves under different light conditions.','present'),
          ('3','Synthetic example: unnamed exposure','We examined an unspecified exposure. The abstract does not identify the exposure or purpose.','present'),
          ('4','Synthetic example: unavailable abstract','','blank'),
          ('5','Synthetic example: placeholder abstract','Abstract unavailable.','placeholder')]
reference=TEST/'reference.csv'; xml=TEST/'xml'; xml.mkdir(); fixtures=TEST/'responses'; fixtures.mkdir()
with reference.open('w',encoding='utf-8',newline='') as handle:
    writer=csv.writer(handle); writer.writerow(['GOID','title','abstract','abstract_input_status']); writer.writerows(examples)
metadata=TEST/'new_search_extended_metadata.csv'
with metadata.open('w',encoding='utf-8',newline='') as handle:
    writer=csv.writer(handle); writer.writerow(['GOID','Title','Authors','Date','Degree Date','Language','School Location','Source Type'])
    for g,t,a,status in examples:
        writer.writerow([g,t,'A. Example','2018-01-01','2018','English','United States -- Ohio','Dissertations & Theses'])
    writer.writerow(['6','Excluded document','A. Example','2018-01-01','2018','French','United States -- Ohio','Dissertations & Theses'])
    writer.writerow(['7','Synthetic example: unavailable abstract','A. Example','2018-01-01','2018','English','United States -- Ohio','Dissertations & Theses'])
for g,t,a,status in examples+[('6','Excluded document','Texte francais.','present'),
                              ('7','Synthetic example: unavailable abstract','A complete alternate abstract.','present')]:
    element=ET.Element('Record'); ET.SubElement(element,'GOID').text=g
    obj=ET.SubElement(element,'Obj'); title=ET.SubElement(obj,'TitleAtt'); ET.SubElement(title,'Title').text=t; ET.SubElement(obj,'Abstract').text=a
    (xml/f'{g}.xml').write_bytes(ET.tostring(element,encoding='utf-8',xml_declaration=True))
for g,kind in [('1','in'),('2','out'),('3','undetermined')]:
    payload={'record_id':g,'scope_units':[unit(kind,False)],
             'add_su_focus':coded(1 if kind=='in' else 3) if kind!='undetermined' else noncoded('cannot_determine')}
    (fixtures/f'scope_full_{g}.json').write_text(json.dumps(payload),encoding='utf-8')
values={'mixed_purpose':'only_qualifying_described','dissertation_type':'empirical_research','study_design':'cross_sectional_observational',
        'level_of_analysis':'individual_human','research_objective':'describe_distribution','intervention_continuum':'not_applicable',
        'explanatory_domain':'not_applicable','data_type':['survey_questionnaire'],'data_source_origin':'primary_generated'}
content={'record_id':'1','target_aim_ids':['a1']}
for name,value in values.items():
    content[name]=noncoded('not_applicable') if value=='not_applicable' else coded(value)
(fixtures/'content_1.json').write_text(json.dumps(content),encoding='utf-8')
expected={'records':5,'scope_status_counts':{'in_scope':1,'out_of_scope':1,'undetermined':1,'not_assessable':2},
          'content_completed':1,'counting_basis':'records; work-level reconciliation is not inferred'}
search=TEST/'from_own_search'
audit=w.prepare_from_search(xml,metadata,search,search_executed_at='2026-10-03',
                            interface_filters='PQDT Global; Date Published 2010-2023',search_result_count=7)
assert audit['roster_count']==5 and audit['counts']['removed_language']==1
assert audit['counts']['removed_duplicate_work_key']==1
assert [row['GOID'] for row in w.read_csv(search/'reference_PRIVATE.csv') if row['title']=='Synthetic example: unavailable abstract']==['7']
# A partial export is recorded, not refused; the displayed count is never compared.
partial=TEST/'partial_metadata.csv'
partial.write_text('\n'.join(metadata.read_text().splitlines()[:-1])+'\n',encoding='utf-8')
partial_audit=w.prepare_from_search(xml,partial,TEST/'partial_search',search_result_count=999)
assert partial_audit['counts']['removed_xml_without_metadata']==1 and partial_audit['roster_count']==5
assert [row['GOID'] for row in w.read_csv(TEST/'partial_search'/'reference_PRIVATE.csv') if row['title']=='Synthetic example: unavailable abstract']==['4']
w.extract(xml,search)
w.run(search,mode='preflight')
# Search exports vary: result counts and missing values are recorded, never enforced.
varied=TEST/'varied_export'; vxml=varied/'xml'; vxml.mkdir(parents=True)
varied_rows=[  # GOID, metadata title, XML title, abstract, authors, School Location
    ('21','Effects of <i>Staying Connected</i> &amp; alcohol use','Effects of Staying Connected & alcohol use','We studied alcohol use among adolescents.','B. Example','United States -- Ohio'),
    ('22','Tobacco policy in Ontario','Tobacco policy in Ontario','We studied tobacco policy.','','Canada -- Ontario'),
    ('23','Cannabis use in Ohio','Cannabis use in Ohio','We studied cannabis use.','','United States -- Ohio'),
    ('24','Opioid prescribing','Opioid prescribing','We studied opioid prescribing.','C. Example',''),
    ('25','Alcohol outlet density','A different recorded title','We studied alcohol outlet density.','D. Example','United States -- Iowa'),
    ('26','Stimulant use','Stimulant use','No abstract provided.','E. Example','United States -- Utah'),
    ('27','Smoking cessation','Smoking cessation','None','F. Example','United States -- Utah'),
    ('28','Marketing at AT&amp;T','Marketing at AT&T','Survey of employees at AT&T','G. Example','United States -- Texas'),
    ('29','Metadata without XML','','','H. Example','United States -- Texas'),
    ('31','Repeated XML record','Repeated XML record','We studied alcohol policy.','I. Example','United States -- Texas')]
vmeta=varied/'metadata.csv'
with vmeta.open('w',encoding='utf-8',newline='') as handle:
    writer=csv.writer(handle); writer.writerow(['GOID','Title','Authors','Date','Degree Date','Language','School Location','Source Type'])
    writer.writerow(['','Row without an identifier','J. Example','2018-01-01','2018','English','United States -- Ohio','Dissertations & Theses'])
    for g,mt,xt,a,author,loc in varied_rows:
        writer.writerow([g,mt,author,'2018-01-01','2018','English',loc,'Dissertations & Theses'])
def varied_xml(g,t,a,name=None):
    element=ET.Element('Record'); ET.SubElement(element,'GOID').text=g
    obj=ET.SubElement(element,'Obj'); title=ET.SubElement(obj,'TitleAtt'); ET.SubElement(title,'Title').text=t; ET.SubElement(obj,'Abstract').text=a
    (vxml/(name or f'{g}.xml')).write_bytes(ET.tostring(element,encoding='utf-8',xml_declaration=True))
for g,mt,xt,a,author,loc in varied_rows:
    if g!='29': varied_xml(g,xt,a)
varied_xml('31','Repeated XML record','We studied alcohol policy.','31_copy.xml')
varied_xml('30','XML without metadata','We studied alcohol use.')
(vxml/'unreadable.xml').write_text('<Record><GOID>32</GOID>',encoding='utf-8')
vaudit=w.prepare_from_search(vxml,vmeta,varied/'run',search_result_count=999)
vcounts=vaudit['counts']
assert vaudit['roster_count']==6 and vcounts['retained_present']==5 and vcounts['retained_placeholder']==1
for reason in ['geography','missing_school_location','metadata_without_xml','xml_without_metadata','repeated_xml_record']:
    assert vcounts['removed_'+reason]==1, reason
assert vcounts['metadata_rows_without_valid_goid']==1 and vcounts['xml_files_unreadable']==1
assert vcounts['flag_title_differs_between_xml_and_metadata']==1 and vcounts['flag_not_deduplicated_missing_title_or_author']==1
vref={row['GOID']:row for row in w.read_csv(varied/'run'/'reference_PRIVATE.csv')}
assert set(vref)=={'21','23','25','26','27','28'}
assert vref['26']['abstract_input_status']=='placeholder' and vref['27']['abstract_input_status']=='present'
assert vref['28']['title']=='Marketing at AT&T' and vref['28']['abstract']=='Survey of employees at AT&T'
w.extract(vxml,varied/'run')
w.run(varied/'run',mode='preflight')
assert not (ROOT/'examples').exists()
example=TEST/'example'
w.prepare(reference,example,synthetic=True)
w.extract(xml,example)
w.run(example,mode='example',fixture_dir=fixtures)
w.run(example,mode='example',release_content=True,fixture_dir=fixtures)
w.merge(example,synthetic=True)
assert w.account(example)==expected
checkpoint=example/'worker_1_output/production_checkpoints.jsonl'
before=checkpoint.read_bytes()
w.run(example,mode='example',release_content=True,fixture_dir=fixtures)
assert checkpoint.read_bytes()==before, 'Resume repeated work'
# Controlled interruption after the first durable response; restart from saved prefix.
interrupt=TEST/'interrupted'
w.prepare(reference,interrupt,synthetic=True)
w.extract(xml,interrupt)
w.run(interrupt,mode='example',fixture_dir=fixtures)
cp=interrupt/'worker_1_output/production_checkpoints.jsonl'
first=cp.read_bytes().splitlines(keepends=True)[0]
cp.write_bytes(first+b'{"incomplete":')
recovery=recover(interrupt/'worker_1_output','production_checkpoints.jsonl')
assert cp.read_bytes()==first
w.run(interrupt,mode='example',fixture_dir=fixtures)
w.run(interrupt,mode='example',release_content=True,fixture_dir=fixtures)
w.merge(interrupt,synthetic=True)
assert w.account(interrupt)==expected
assert len(cp.read_text().splitlines())==4
# Changed evidence and changed run identity must stop.
inp=example/'worker_1_input_PRIVATE.csv'; original=inp.read_bytes()
inp.write_bytes(original.replace(b'alcohol survey',b'changed survey'))
bad=subprocess.run(w.command(example)+['--preflight-only'],capture_output=True,text=True)
assert bad.returncode and 'evidence differs' in bad.stderr
inp.write_bytes(original)
bad=subprocess.run(w.command(example)+['--fixture-dir',str(fixtures),'--max-attempts','3'],capture_output=True,text=True)
assert bad.returncode and 'Checkpoint identity differs' in bad.stderr
# XML mismatch is rejected before an input is installed.
mismatch=TEST/'xml_mismatch'; w.prepare(reference,mismatch,synthetic=True)
changed_xml=TEST/'changed_xml'; shutil.copytree(xml,changed_xml)
q=changed_xml/'1.xml'; q.write_bytes(q.read_bytes().replace(b'alcohol survey',b'changed survey'))
try: w.extract(changed_xml,mismatch)
except subprocess.CalledProcessError: pass
else: raise AssertionError('Changed XML accepted')
assert not (mismatch/'worker_1_input_PRIVATE.csv').exists()
# Two disjoint partitions reproduce the same counts on this one machine.
multi=TEST/'two_workers'; w.prepare(reference,multi,workers=2,synthetic=True)
for worker in [1,2]:
 w.extract(xml,multi,worker)
 w.run(multi,worker,mode='example',fixture_dir=fixtures)
 w.run(multi,worker,mode='example',release_content=True,fixture_dir=fixtures)
w.merge(multi,synthetic=True)
assert w.account(multi)==w.account(example)
# The public production runner handles policy HTTP 400s in-process for both
# stage invokers. No sitecustomize or adapter installation is involved.
import run_v5_rev14_hybrid_production as hybrid
import run_v5_rev14_scope_compare as scope
import run_v5_rev14_pilot as content
assert hybrid.RUNNER_VERSION == 'v5_rev15_single_scope_public_rerun_v1'
assert not (ROOT/'src/coding/http400_policy_v3/sitecustomize.py').exists()
proxy='https://agai-proxy.prod.int.tdmstudio.proquest.com/large-language-models-openai-compatible/'
policy_body=b'{"detail":"Request rejected by content management policy; content filtered."}'
policy_cp=TEST/'http400_events.jsonl'; policy_cp.write_text('',encoding='utf-8')
assigned=['111','222','333','444','555']
def append_policy(goid,event,category=None):
    row={'stage':'scope_full','GOID':goid,'event':event}
    if category: row['failure_category']=category
    with policy_cp.open('a',encoding='utf-8') as handle:
        handle.write(json.dumps(row)+'\n')
def classify(body,goid='111',base_url=proxy):
    error=urllib.error.HTTPError(base_url+'chat/completions',400,'Bad Request',{},io.BytesIO(body))
    log=io.StringIO()
    with contextlib.redirect_stderr(log):
        result=hybrid._classify_http400_response(
            error,stage='scope_full',goid=goid,base_url=base_url,
            checkpoint=policy_cp,assigned=assigned)
    assert 'Request rejected' not in log.getvalue()
    assert 'HTTP400_POLICY_AUDIT ' in log.getvalue()
    return result
assert classify(policy_body)=='content_filtered'
append_policy('111','failed','content_filtered')
assert classify(policy_body,'222')=='content_filtered'
assert classify(policy_body,'111') is None
append_policy('111','retry_authorized')
assert classify(policy_body,'111')=='content_filtered'
append_policy('111','failed','content_filtered')
assert classify(policy_body,'111') is None
assert classify(policy_body,'333',base_url='https://example.invalid/') is None
assert classify(b'{"error":{"code":"invalid_request_error","param":"model"}}','333') is None
assert classify(b'{"error":{"code":"content_filter","param":"model"}}','333') is None
assert classify(b'{"error":{"code":"insufficient_quota"}}','333') is None
unclear=b'{"detail":"Unclassified request refusal"}'
assert classify(unclear,'333')=='proxy_http400_deferred'
append_policy('333','failed','proxy_http400_deferred')
assert classify(unclear,'444') is None
append_policy('222','validated')
assert classify(unclear,'444')=='proxy_http400_deferred'
append_policy('222','validated')
assert classify(b'{"error":{"code":"context_length_exceeded"}}','555')=='record_context_length'
original_urlopen=urllib.request.urlopen
try:
    def blocked(request,*args,**kwargs):
        raise urllib.error.HTTPError(request.full_url,400,'Bad Request',{},io.BytesIO(policy_body))
    urllib.request.urlopen=blocked
    for module,model in [(scope,'gpt_5_2025_08_07'),(content,'gpt_4o_2024_08_06')]:
        try:
            module.invoke_live(base_url=proxy,key='fake',model=model,prompt='synthetic prompt',
                               schema={'name':'synthetic','schema':{}},
                               user_data={'record_id':'111','numbered_evidence':'synthetic'},
                               max_tokens=10,seed=None,
                               policy_400_handler=lambda error: 'content_filtered')
        except module.RecordFailure as error:
            assert error.category=='content_filtered'
        else:
            raise AssertionError('Live stage invoker did not use integrated HTTP 400 handler')
finally:
    urllib.request.urlopen=original_urlopen
# Fixture outputs cannot pass the live-result merger.
try: w.merge(example,synthetic=False)
except ValueError: pass
else: raise AssertionError('Example accepted as live output')
print(json.dumps({'search_export_variation':'passed','resume':'passed','torn_tail_recovery':'passed','partial_resume':'passed','evidence_rejection':'passed','identity_rejection':'passed','xml_rejection':'passed','two_partition_merge':'passed','integrated_http400_policy':'passed','synthetic_live_separation':'passed'}))
