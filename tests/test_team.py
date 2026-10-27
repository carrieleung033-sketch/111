import base64
import http.cookiejar
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

# Load separately so test_bgm's temporary DATA override does not leak.
import team

class TeamTest(unittest.TestCase):
    def test_bootstrap_does_not_reset_existing_accounts(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(team, 'DB', Path(tmp)/'team.sqlite'):
                team.init()
                with patch.dict('os.environ', {'BOOTSTRAP_USERNAME':'manager','BOOTSTRAP_PASSWORD':'a-long-test-password'}):
                    team.bootstrap_user()
                with team.connect() as db:
                    original = dict(db.execute('SELECT * FROM users').fetchone())
                with patch.dict('os.environ', {'BOOTSTRAP_USERNAME':'another','BOOTSTRAP_PASSWORD':'changed-test-password'}):
                    team.bootstrap_user()
                with team.connect() as db:
                    rows = [dict(r) for r in db.execute('SELECT * FROM users')]
                self.assertEqual(rows, [original])
                self.assertNotEqual(original['password'], 'a-long-test-password')

    def test_login_shared_tasks_persistence_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_data, old_db = team.studio.DATA, team.DB
            team.studio.DATA = Path(tmp)
            team.DB = Path(tmp) / 'test.sqlite'
            team.init()
            team.create_user('alice', 'test-password-alice')
            team.create_user('bob', 'test-password-bob')
            http = team.studio.ThreadingHTTPServer(('127.0.0.1', 0), team.TeamHandler)
            threading.Thread(target=http.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{http.server_port}'
            # Independent browser cookie jars.
            import http.cookiejar as cookies
            alice = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies.CookieJar()))
            bob = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies.CookieJar()))
            guest = urllib.request.build_opener()
            def req(client, path, data=None, headers=None):
                r = urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None, headers={'Content-Type':'application/json', **(headers or {})})
                with client.open(r) as response:
                    raw = response.read()
                    return json.loads(raw) if raw else None
            try:
                for path in ['/api/tasks', '/media/private.mp4', '/api/status']:
                    with self.assertRaises(urllib.error.HTTPError) as e: req(guest, path)
                    self.assertEqual(e.exception.code, 401)
                for client, name in [(alice,'alice'),(bob,'bob')]:
                    req(client, '/api/login', {'username':name,'password':'test-password-'+name})
                    self.assertEqual(req(client,'/api/me')['user'],name)
                for mode in ['product','avatar','reference']:
                    task=req(alice,'/api/tasks',{'mode':mode,'script':'Show our reusable cup','duration':15,'market':'TH','reference_url':'https://www.tiktok.com/@demo/video/123','target_mode':'product'})
                    self.assertEqual(task['status'],'needs_provider')
                shared=req(bob,'/api/tasks')['tasks']
                self.assertEqual(len(shared),3)
                self.assertTrue(all(t['owner']=='alice' for t in shared))
                self.assertTrue(all(t['url'] is None for t in shared))
                with team.connect() as db:
                    db.execute("UPDATE tasks SET status='rendering' WHERE id=?",(shared[0]['id'],))
                team.init()
                restored=req(bob,'/api/tasks')['tasks']
                self.assertEqual(restored[0]['status'],'failed')
                self.assertEqual(restored[1]['status'],'needs_provider')
                with self.assertRaises(urllib.error.HTTPError) as e:
                    req(alice,'/api/tasks',{'mode':'reference','script':'test','market':'TH','target_mode':'avatar','reference_url':'https://evil.example/video'})
                self.assertEqual(e.exception.code,400)
                with self.assertRaises(urllib.error.HTTPError) as e:
                    req(alice,'/api/tasks',{},headers={'Origin':'https://evil.example'})
                self.assertEqual(e.exception.code,403)
                import subprocess
                image = Path(tmp) / 'source.png'
                subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=64x64','-frames:v','1',str(image)],check=True)
                uploaded = req(alice,'/api/upload',{'name':'source.png','data':base64.b64encode(image.read_bytes()).decode()})['id']
                queued = req(alice,'/api/tasks',{'mode':'assets','script':'Product demo','files':[uploaded],'duration':15})
                self.assertEqual(queued['status'],'queued')
                self.assertTrue(team.worker_once())
                completed = req(bob,'/api/jobs/'+queued['id'])
                self.assertEqual(completed['status'],'done',completed)
                self.assertTrue((Path(tmp)/(queued['id']+'.mp4')).is_file())
                self.assertFalse(team.worker_once())
                req(alice,'/api/logout',{})
                self.assertIsNone(req(alice,'/api/me')['user'])
                with self.assertRaises(urllib.error.HTTPError): req(alice,'/api/tasks')
            finally:
                http.shutdown();http.server_close()
                team.studio.DATA,team.DB=old_data,old_db

if __name__ == '__main__': unittest.main()
