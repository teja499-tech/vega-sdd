import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from wsgiref.simple_server import make_server,WSGIRequestHandler
from service import create_app
class Quiet(WSGIRequestHandler):
    def log_message(self,*args): pass
class APITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=str(Path(self.tmp.name)/'db.sqlite')
        self.server=make_server('127.0.0.1',0,create_app(self.db,'test-secret'),handler_class=Quiet)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def req(self,path,body=None,method='GET',key='test-secret',raw=None):
        headers={'X-API-Key':key,'Content-Type':'application/json'}
        data=raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,data=data,headers=headers,method=method)
        try: r=urlopen(req,timeout=3)
        except HTTPError as e: r=e
        with r: return r.status,json.loads(r.read())
    def test_authentication(self):
        self.assertEqual(self.req('/incidents',key='')[0],401)
        self.assertEqual(self.req('/incidents',{'title':'a'},'POST',key='wrong')[0],401)
    def test_create_list_resolve(self):
        code,item=self.req('/incidents',{'title':'alert'},'POST');self.assertEqual(code,201)
        self.assertEqual(self.req('/incidents')[1]['items'][0]['id'],item['id'])
        self.assertEqual(self.req(f"/incidents/{item['id']}",{'status':'resolved'},'PATCH')[0],200)
        self.assertEqual(self.req('/incidents')[1]['items'][0]['status'],'resolved')
    def test_validation(self):
        for body in ({'title':''},{'title':'x'*121},{'title':42},[]):
            self.assertEqual(self.req('/incidents',body,'POST')[0],400)
        self.assertEqual(self.req('/incidents',method='POST',raw=b'{')[0],400)
        self.assertEqual(self.req('/incidents/1',{'status':'oops'},'PATCH')[0],400)
    def test_pagination(self):
        for title in ('one','two','three'):self.req('/incidents',{'title':title},'POST')
        items=self.req('/incidents?limit=1&offset=1')[1]['items']
        self.assertEqual([i['title'] for i in items],['two'])
        for q in ('limit=0','limit=101','offset=-1','limit=no'):
            self.assertEqual(self.req('/incidents?'+q)[0],400)
    def test_missing_record_and_route(self):
        self.assertEqual(self.req('/incidents/999',{'status':'resolved'},'PATCH')[0],404)
        self.assertEqual(self.req('/missing')[0],404)
    def test_health_and_storage_failure(self):
        self.assertEqual(self.req('/healthz',key='')[0],200)
        Path(self.db).unlink()
        code,body=self.req('/healthz',key='');self.assertEqual(code,503)
        self.assertNotIn('test-secret',str(body));self.assertNotIn('Traceback',str(body))
