"""Dependency-ordered quality across explicitly selected repositories."""
from pathlib import Path
from .workspace import Component,ordered,run_checks
from .storage import load_yaml,project_lock

def check(file:Path):
    data=load_yaml(file);items=data.get('repositories',[])
    if not items:raise ValueError('No repositories selected')
    nodes=[Component(id=i['id'],kind='custom',path=i['path'],depends_on=i.get('depends_on',[])) for i in items]
    failed=set();results=[]
    for node in ordered(nodes):
        if failed.intersection(node.depends_on):failed.add(node.id);results.append({'repository':node.id,'status':'blocked_by_dependency'});continue
        root=(file.parent/node.path).resolve()
        with project_lock(root):record=run_checks(root)
        if not record['passed']:failed.add(node.id)
        results.append({'repository':node.id,'status':'pass' if record['passed'] else 'fail','evidence':record['id'],'root':str(root)})
    return {'passed':not failed,'scope':'Quality aggregation only, not an atomic cross-repo deployment','results':results}
