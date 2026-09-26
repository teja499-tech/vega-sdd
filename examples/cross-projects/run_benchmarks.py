"""Real local application checks and delivery; no live coding agent or cloud host."""
import json
import shutil
import subprocess
import sys
from pathlib import Path
from universal_sdd.workspace import configure,run_checks
from universal_sdd.delivery import git,create_branch
from universal_sdd.pipelines import export
from universal_sdd.releases import build,deploy

DEST=Path(sys.argv[1]).resolve()
if DEST.exists():raise SystemExit('Choose fresh destination')
DEST.mkdir(parents=True)
PY=sys.executable

def write(root,name,text):
    path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
def run(name,kind,files,checks):
    root=DEST/name;root.mkdir()
    for path,text in files.items():write(root,path,text)
    write(root,'.gitignore','out/\n.sdd/\n__pycache__/\n')
    write(root,'build_app.py',"""from pathlib import Path
import zipfile
p=Path('out/application.zip');p.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(p,'w') as z:
 for f in Path('.').glob('*.py'):z.write(f)
""")
    write(root,'deploy.py',"""import os,shutil,sys,yaml,hashlib
from pathlib import Path
r=yaml.safe_load(Path(os.environ['SDD_RELEASE_MANIFEST']).read_text())
a=r['artifacts'][0];path=Path(a['path']);dest=Path('.sdd/local-target')/os.environ['SDD_ENVIRONMENT']
if sys.argv[1]=='deploy':dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
assert hashlib.sha256(dest.read_bytes()).hexdigest()==a['sha256']
""")
    commands={k:{'argv':[PY,f]} for k,f in checks.items()}
    component={'id':'app','kind':kind,'checks':commands,'build':{'argv':[PY,'build_app.py']},'artifact':'out/application.zip'}
    env={'deploy':{'argv':[PY,'deploy.py','deploy']},'smoke':{'argv':[PY,'deploy.py','smoke']},'requires_approval':False}
    configure(root,{'components':[component],'environments':{'stage':env,'production':{**env,'requires_approval':True,'promote_from':'stage'}}})
    git(root,'init','-q','-b','main');git(root,'config','user.name','Fixture');git(root,'config','user.email','fixture@example.test')
    export(root,'github');git(root,'add','.');git(root,'add','-f','.sdd/ci');git(root,'commit','-qm','Baseline with CI')
    create_branch(root,'feature')
    verified=run_checks(root);assert verified['passed'],verified
    ci=subprocess.run([PY,'.sdd/ci/verify.py'],cwd=root,capture_output=True,text=True)
    assert ci.returncode==0,ci.stdout+ci.stderr
    release=build(root,'1.0')
    assert deploy(root,'1.0','stage')['status']=='succeeded'
    result=deploy(root,'1.0','production',approve=True)
    assert result['status']=='succeeded' and deploy(root,'1.0','production')['operation']==result['operation']
    script=root/checks['test'];original=script.read_text()
    script.write_text(original+'\nraise AssertionError("seeded regression")\n')
    assert not run_checks(root)['passed']
    script.write_text(original)
    assert run_checks(root)['passed']
    return {'name':name,'kind':kind,'checks':len(verified['results']),'source_commit':release['head'],'staging_and_production':'succeeded locally','seeded_regression':'detected','idempotent':True}

results=[]
results.append(run('python-library','library',{
 'mathlib.py':'def total(values):\n    return sum(values)\n',
 'check.py':'from mathlib import total\nassert total([1,2,3])==6 and total([])==0\n',
 'compatibility.py':'import inspect,mathlib\nassert list(inspect.signature(mathlib.total).parameters)==["values"]\nassert mathlib.total((i for i in range(4)))==6\n',
},{'test':'check.py','compatibility':'compatibility.py'}))
results.append(run('cli-utility','cli',{
 'words.py':'import argparse,json\np=argparse.ArgumentParser();p.add_argument("text");print(json.dumps({"words":len(p.parse_args().text.split())}))\n',
 'check.py':'import subprocess,sys,json\nr=subprocess.run([sys.executable,"words.py","hello 世界"],capture_output=True,text=True);assert r.returncode==0 and json.loads(r.stdout)["words"]==2\nassert subprocess.run([sys.executable,"words.py"],capture_output=True).returncode==2\n',
 'smoke.py':'import subprocess,sys\nr=subprocess.run([sys.executable,"words.py","two words"],capture_output=True,text=True);assert r.returncode==0 and "2" in r.stdout\n',
},{'test':'check.py','smoke':'smoke.py'}))
results.append(run('sqlite-pipeline','data_pipeline',{
 'pipeline.py':'import sqlite3\ndef ingest(path,rows):\n with sqlite3.connect(path) as c:\n  c.execute("CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,amount INTEGER CHECK(amount>=0))")\n  c.executemany("INSERT INTO events VALUES(?,?) ON CONFLICT(id) DO UPDATE SET amount=excluded.amount",rows)\n',
 'check.py':'import tempfile,sqlite3\nfrom pathlib import Path\nfrom pipeline import ingest\nwith tempfile.TemporaryDirectory() as d:\n p=str(Path(d)/"data.db");ingest(p,[("a",3),("b",4)]);ingest(p,[("a",5)])\n with sqlite3.connect(p) as c:assert c.execute("SELECT sum(amount) FROM events").fetchone()[0]==9\n try:ingest(p,[("c",2),("invalid",-1)]);raise AssertionError("accepted bad data")\n except sqlite3.IntegrityError:pass\n with sqlite3.connect(p) as c:assert c.execute("SELECT count(*) FROM events").fetchone()[0]==2\n',
 'replay.py':'import tempfile,sqlite3\nfrom pathlib import Path\nfrom pipeline import ingest\nwith tempfile.TemporaryDirectory() as d:\n p=str(Path(d)/"db")\n for _ in range(3):ingest(p,[("a",3),("b",4)])\n with sqlite3.connect(p) as c:assert c.execute("SELECT count(*),sum(amount) FROM events").fetchone()==(2,7)\n',
},{'test':'check.py','data_quality':'check.py','replay':'replay.py'}))
if shutil.which('node'):
    results.append(run('node-web','web',{
     'index.html':'<!doctype html><html lang="en"><title>Search</title><main><label for="q">Search</label><input id="q"></main></html>',
     'check.py':'import subprocess\nsubprocess.run(["node","check.mjs"],check=True)\n',
     'check.mjs':"import http from 'node:http';import assert from 'node:assert/strict';import fs from 'node:fs';const s=http.createServer((req,res)=>{if(req.url==='/'){res.end(fs.readFileSync('index.html'));}else{res.statusCode=404;res.end();}});await new Promise(r=>s.listen(0,'127.0.0.1',r));try{const url=`http://127.0.0.1:${s.address().port}`;let r=await fetch(url);assert.equal(r.status,200);assert.match(await r.text(),/<main>/);assert.equal((await fetch(url+'/missing')).status,404);}finally{s.close();}\n",
     'accessibility.py':'from html.parser import HTMLParser\nfrom pathlib import Path\nclass P(HTMLParser):\n def __init__(self):super().__init__();self.lang=False;self.labels=[];self.inputs=[]\n def handle_starttag(self,tag,attrs):\n  a=dict(attrs)\n  if tag=="html":self.lang=bool(a.get("lang"))\n  if tag=="label":self.labels.append(a.get("for"))\n  if tag=="input":self.inputs.append(a.get("id"))\np=P();p.feed(Path("index.html").read_text());assert p.lang and p.inputs and set(p.inputs)<=set(p.labels)\n',
    },{'test':'check.py','accessibility':'accessibility.py'}))
summary={'mode':'Real local application/Git/checks/archives/file-copy deployment; no live agent or cloud certification','results':results,'platforms_exercised':['Linux','Python '+sys.version.split()[0]],'web_accessibility_scope':'HTML language/form labels only'}
(DEST/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
