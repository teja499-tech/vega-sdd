"""Deterministic process fixture. NOT a coding model or provider certification."""
import json
import shutil
import sys
from pathlib import Path
import yaml

root=Path.cwd(); assets=Path(__file__).parent
prompt=Path(sys.argv[1]).read_text()
def copy(name, target=None):
    dest=root/(target or name);dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(assets/'fixture'/name,dest)
def design_documents():
    docs=json.loads((assets/'design_documents.json').read_text())
    if (root/'service.py').exists():
        import re
        found=re.search(r'MAX_TITLE = (\d+)',(root/'service.py').read_text())
        if found:
            limit=found.group(1)
            for key,section in [('LLD','Key execution flows'),('API_DESIGN','Requests and responses')]:
                docs[key]['sections'][section]=docs[key]['sections'][section].replace('120',limit)
            docs['EXISTING_SYSTEM']['sections']['Observed current behavior'] += ' The currently inspected service.py sets MAX_TITLE to '+limit+'.'
    return docs

FEATURES = [
    (
        'Storage',
        [1],
        'Persist incidents in a local SQLite file so records survive a process restart.',
        ['Incident rows remain after reopen of the same database file.'],
        ['Remote databases and multi-host replication are out of scope.'],
        ['Create then reopen store', 'Missing database file starts empty'],
        '',
        'Add store.py and storage tests that create an incident, reopen the SQLite file, and still list that row.',
    ),
    (
        'API',
        [2, 3, 4, 5],
        'Expose authenticated HTTP create, list, resolve, and health for the incident store.',
        ['Every mutating request requires the runtime API key.', 'Titles longer than the approved maximum are rejected.'],
        ['Browser UI and multi-tenant isolation are out of scope.'],
        ['Create with key', 'Reject missing key', 'Reject overlong title', 'Resolve existing id', 'Health without auth'],
        'POST /incidents {title} -> 201; GET /incidents -> 200 list; POST /incidents/{id}/resolve -> 200; GET /health -> 200. Errors: 400 validation, 401 missing key.',
        'Add service.py and API tests that prove create, pagination, resolve, health, and authentication failures against the real local HTTP server.',
    ),
    (
        'Operations',
        [6],
        'Document local run, restart, and error handling so operators can verify the service.',
        ['Restart keeps stored incidents.', 'Unhandled errors do not leak secrets.'],
        ['Cloud hosting, on-call ownership, and staged cutover are out of scope.'],
        ['Restart retains data', 'Safe error body'],
        '',
        'Add OPERATIONS.md and ops tests that restart the process and assert stored incidents and safe error responses remain.',
    ),
]


def bundle():
    reqs=[]
    titles=['SQLite persistence','Create incidents','Authenticated pagination','Resolve incidents','Health and safe errors','Operations and tests']
    for i,title in enumerate(titles,1):
        reqs.append(dict(id=f'REQ-{i:03}',title=title,statement=title+' as specified in PRD.md for the single-host Incident Desk API.',acceptance_criteria=[f'AC-{i:03}: executable acceptance test proves {title}']))
    features=[]
    for i, (name, ids, summary, invariants, non_goals, test_matrix, api_contract, description) in enumerate(FEATURES, 1):
        fid=f'F{i:03}';rids=[f'REQ-{r:03}' for r in ids]
        features.append(dict(
            id=fid,
            name=name,
            summary=summary,
            requirements=rids,
            depends_on=[f'F{i-1:03}'] if i>1 else [],
            invariants=invariants,
            non_goals=non_goals,
            test_matrix=test_matrix,
            api_contract=api_contract,
            tasks=[dict(id=f'TASK-{fid}-001',feature_id=fid,title=name,description=description,implements=rids,verification=['python3 -m unittest discover -s acceptance -v'])],
        ))
    return dict(
        product=dict(
            name='Incident Desk',
            summary='Single-tenant internal incident API for operators to create, list, resolve, and health-check records.',
            users=['Operators'],
            capabilities=titles,
        ),
        requirements=reqs,
        features=features,
        design_documents=design_documents(),
        architecture_summary='Python WSGI, SQLite, runtime API key, single host behind TLS proxy',
        test_strategy=['Storage tests','Real HTTP requests','Process restart'],
        security_principles=['Runtime secrets','Parameterized SQL'],
        release_criteria=['All acceptance tests pass','External production deployment review remains required'],
    )
if 'PRODUCT_DISCOVERY_JSON' in prompt:
    output=bundle()['product']; output['open_questions']=['Confirm the initial title maximum (characters)?']
elif 'ARCHITECTURE_DECISIONS_JSON' in prompt:
    output=[dict(id='ARCH-001',category='database',question='Database for the single-host pilot?',options=[dict(name='SQLite',summary='Local transactional store',fit='high'),dict(name='PostgreSQL',summary='Managed multi-host option',fit='medium')],recommendation='SQLite',recommendation_reason='Explicit single-host scope')]
elif 'SPEC_BUNDLE_JSON' in prompt:output=bundle()
elif 'RECONCILE_CHANGE_JSON' in prompt:
    output={'bundle':bundle(),'invalidate_tasks':[],'notes':['Title maximum 80; existing data unchanged']}
    output['bundle']['requirements'][1]['statement']='New incident title must be 1..80 characters; retain existing titles.'
    output['bundle']['requirements'][1]['acceptance_criteria']=['AC-002: reject an 81-character title; accept an 80-character title']
    for key,section in [('LLD','Key execution flows'),('API_DESIGN','Requests and responses')]:
        output['bundle']['design_documents'][key]['sections'][section]=output['bundle']['design_documents'][key]['sections'][section].replace('120','80')
    (root/'fixture-change-approved').write_text('80')
elif 'CHANGE_ANALYSIS_JSON' in prompt:
    output=dict(classification='requirement_change',affected_requirements=['REQ-002'],affected_features=['F002'],affected_tasks=['TASK-F002-001'],proposed_changes=['Change title maximum to 80'],requires_approval=True)
elif 'TASK_IMPLEMENTATION' in prompt or 'Findings:' in prompt:
    if 'TASK-F001' in prompt:
        copy('store.py');(root/'acceptance').mkdir(exist_ok=True);shutil.copyfile(assets/'acceptance/test_storage.py',root/'acceptance/test_storage.py')
    elif 'TASK-F002' in prompt:
        copy('service.py');shutil.copyfile(assets/'acceptance/test_api.py',root/'acceptance/test_api.py')
        if 'TASK_IMPLEMENTATION' in prompt and not (root/'fixture-seeded-once').exists():
            # Seed a real authentication regression for the controller to discover.
            p=root/'service.py';p.write_text(p.read_text().replace('return result(401,','return result(200,'));(root/'fixture-seeded-once').touch()
        if (root/'fixture-change-approved').exists():
            p=root/'service.py';p.write_text(p.read_text().replace('MAX_TITLE = 120','MAX_TITLE = 80'))
            (root/'acceptance/test_change.py').write_text("import unittest\nimport test_api\nfrom store import Store\nclass ChangedTitleTests(unittest.TestCase):\n    setUp = test_api.APITests.setUp\n    tearDown = test_api.APITests.tearDown\n    req = test_api.APITests.req\n    def test_existing_long_title_retained(self):\n        Store(self.db).create('x'*120)\n        self.assertEqual(len(self.req('/incidents')[1]['items'][0]['title']),120)\n    def test_new_limit(self):\n        self.assertEqual(self.req('/incidents',{'title':'x'*81},'POST')[0],400)\n        self.assertEqual(self.req('/incidents',{'title':'x'*80},'POST')[0],201)\n")
    else:
        copy('OPERATIONS.md');shutil.copyfile(assets/'acceptance/test_ops.py',root/'acceptance/test_ops.py')
    output='Fixture implementation or repair applied'
elif 'TASK_REVIEW_JSON' in prompt:output=dict(status='pass',findings=[],summary='Scripted reviewer pass; deterministic acceptance tests are separate')
elif 'ASK_ARCHITECT' in prompt:output='SQLite is selected for the explicitly single-host service; this is a scripted architect response.'
else:raise SystemExit('Unexpected fixture prompt')
print(json.dumps({'type':'fixture_result','result':json.dumps(output) if not isinstance(output,str) else output}))
