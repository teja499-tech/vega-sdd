import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
import json
class OpsTests(unittest.TestCase):
    def test_process_restart_preserves_data(self):
        with tempfile.TemporaryDirectory() as d:
            with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
            env={**os.environ,'API_KEY':'test-secret','DB_PATH':str(Path(d)/'db'),'PORT':str(port)}
            for run in range(2):
                proc=subprocess.Popen([sys.executable,'service.py'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                try:
                    for _ in range(100):
                        try:
                            with urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.1):break
                        except OSError:time.sleep(.02)
                    else:self.fail('service did not become healthy')
                    req=Request(f'http://127.0.0.1:{port}/incidents',headers={'X-API-Key':'test-secret'},data=json.dumps({'title':'restart'}).encode() if run==0 else None)
                    with urlopen(req,timeout=2) as r:payload=json.load(r)
                    if run:self.assertEqual(payload['items'][0]['title'],'restart')
                finally:
                    proc.terminate();proc.wait(timeout=5)
    def test_operations_document_present(self):
        text=Path('OPERATIONS.md').read_text()
        for word in ('TLS','API_KEY','backup','persistent','unprivileged'):self.assertIn(word,text)
