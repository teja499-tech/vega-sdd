import hmac
import json
import os
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server
from store import Store

MAX_TITLE = 120

def create_app(path, api_key):
    if not api_key: raise ValueError('API key required')
    store = Store(path)
    def app(env, respond):
        def result(code, value):
            data = json.dumps(value).encode()
            reasons={200:'OK',201:'Created',400:'Bad Request',401:'Unauthorized',404:'Not Found',503:'Service Unavailable'}
            respond(f'{code} {reasons[code]}',[('Content-Type','application/json'),('Content-Length',str(len(data)))])
            return [data]
        try:
            path=env['PATH_INFO']; method=env['REQUEST_METHOD']
            if path=='/healthz' and method=='GET':
                store.health(); return result(200,{'status':'ok'})
            if not hmac.compare_digest(env.get('HTTP_X_API_KEY','').encode(),api_key.encode()):
                return result(401,{'error':'unauthorized'})
            if path=='/incidents' and method=='GET':
                args=parse_qs(env.get('QUERY_STRING',''))
                limit=int(args.get('limit',['20'])[0]); offset=int(args.get('offset',['0'])[0])
                if not 1 <= limit <= 100 or offset < 0: return result(400,{'error':'invalid pagination'})
                return result(200,{'items':store.list(limit,offset)})
            if method in ('POST','PATCH'):
                length=int(env.get('CONTENT_LENGTH') or 0)
                if not 0 < length <= 4096: return result(400,{'error':'invalid body'})
                payload=json.loads(env['wsgi.input'].read(length))
                if not isinstance(payload,dict): return result(400,{'error':'invalid body'})
                if method=='POST' and path=='/incidents':
                    title=payload.get('title')
                    if not isinstance(title,str) or not title.strip() or len(title)>MAX_TITLE:
                        return result(400,{'error':'invalid title'})
                    return result(201,store.create(title.strip()))
                if method=='PATCH' and path.startswith('/incidents/'):
                    status=payload.get('status')
                    if status not in ('open','resolved'): return result(400,{'error':'invalid status'})
                    found=store.update(int(path.rsplit('/',1)[1]),status)
                    return result(200 if found else 404,{'updated':found})
            return result(404,{'error':'not found'})
        except (ValueError,TypeError,UnicodeError): return result(400,{'error':'invalid request'})
        except Exception: return result(503,{'error':'temporarily unavailable'})
    return app

if __name__=='__main__':
    # Reference acceptance server; use a production WSGI server behind TLS in deployment.
    app=create_app(os.environ.get('DB_PATH','incidents.db'),os.environ['API_KEY'])
    with make_server('127.0.0.1',int(os.environ.get('PORT','8080')),app) as server:
        server.serve_forever()
