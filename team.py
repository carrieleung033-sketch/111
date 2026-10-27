"""Shared studio entrypoint. Start with python team.py; bootstrap via --create-user."""
import argparse
import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit
import server as studio
from providers import MISSING_SERVICE

DB = studio.DATA / 'team.sqlite3'
WAKE = threading.Event()

def connect():
    db = sqlite3.connect(DB, timeout=30)
    db.row_factory = sqlite3.Row
    return db

def init():
    with connect() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS users(name TEXT PRIMARY KEY, salt TEXT NOT NULL, password TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, username TEXT NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, owner TEXT NOT NULL, mode TEXT NOT NULL, script TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, error TEXT, url TEXT, created REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS attempts(address TEXT PRIMARY KEY, count INTEGER NOT NULL, expires REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS bootstrap_resets(id TEXT PRIMARY KEY, username TEXT NOT NULL);
        ''')
        db.execute("UPDATE tasks SET status='failed', error='服务重启导致任务中断，请重新提交' WHERE status='rendering'")

def digest(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 310000).hex()

def create_user(name, password):
    if not name or len(name) > 80 or len(password) < 12:
        raise ValueError('用户名不能为空；密码至少 12 个字符')
    salt = secrets.token_hex(16)
    with connect() as db:
        db.execute('INSERT INTO users VALUES (?, ?, ?)', (name, salt, digest(password, salt)))

def bootstrap_user():
    """Initialize an account or apply an explicit, one-time deployment reset."""
    name = os.getenv('BOOTSTRAP_USERNAME', '').strip()
    password = os.getenv('BOOTSTRAP_PASSWORD', '')
    reset_id = os.getenv('BOOTSTRAP_RESET_ID', '').strip()
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        existing = db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
        if reset_id:
            if db.execute('SELECT 1 FROM bootstrap_resets WHERE id=?', (reset_id,)).fetchone():
                return
            if not name or len(name) > 80 or len(password) < 12 or len(reset_id) > 200:
                raise ValueError('账号重置配置无效：请填写用户名、至少 12 字符密码和有效重置标记')
            salt = secrets.token_hex(16)
            db.execute('INSERT INTO users VALUES (?,?,?) ON CONFLICT(name) DO UPDATE SET salt=excluded.salt,password=excluded.password', (name, salt, digest(password, salt)))
            db.execute('DELETE FROM sessions WHERE username=?', (name,))
            db.execute('DELETE FROM attempts')
            db.execute('INSERT INTO bootstrap_resets VALUES (?,?)', (reset_id, name))
            print('Bootstrap account reset applied.', flush=True)
        elif not existing and (name or password):
            if not name or len(name) > 80 or len(password) < 12:
                raise ValueError('首次账号配置无效：用户名不能为空，密码至少 12 字符')
            salt = secrets.token_hex(16)
            db.execute('INSERT INTO users VALUES (?,?,?)', (name, salt, digest(password, salt)))
            print('Bootstrap account initialized.', flush=True)

def worker_once():
    with connect() as db:
        task = db.execute("SELECT * FROM tasks WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if task:
            db.execute("UPDATE tasks SET status='rendering' WHERE id=?", (task['id'],))
    if not task:
        return False
    data = json.loads(task['payload'])
    studio.render(task['id'], data['files'], data['duration'], data.get('bgm'), data.get('volume', .3), data.get('edit_style', 'scene'))
    result = studio.JOBS.pop(task['id'])
    with connect() as db:
        db.execute('UPDATE tasks SET status=?, error=?, url=? WHERE id=?', (result['status'], result.get('error'), result.get('url'), task['id']))
    return True

def worker():
    while True:
        if not worker_once():
            WAKE.wait(2)
            WAKE.clear()

class TeamHandler(studio.Handler):
    def user(self):
        try:
            cookies = SimpleCookie(self.headers.get('Cookie', ''))
            token = cookies['studio_session'].value
            with connect() as db:
                row = db.execute('SELECT username FROM sessions WHERE token=? AND expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            return row['username'] if row else None
        except (KeyError, ValueError):
            return None

    def do_GET(self):
        if self.path == '/healthz':
            with connect() as db:
                db.execute('SELECT 1 FROM users LIMIT 1').fetchone()
            return self.send(200, {'status': 'ok'})
        if self.path == '/api/me':
            return self.send(200, {'user': self.user()})
        # Static shell is public, while API responses and uploaded/output media require login.
        if self.path.startswith(('/api/', '/media/')) and not self.user():
            return self.send(401, {'error': '请先登录团队工作台'})
        if self.path == '/api/tasks':
            with connect() as db:
                tasks = [dict(r) for r in db.execute('SELECT id,owner,mode,script,status,error,url,created FROM tasks ORDER BY created DESC LIMIT 100')]
            for task in tasks:
                report_path = studio.DATA / (task['id'] + '-edit.json')
                if task['status'] == 'done' and report_path.is_file():
                    try:
                        report = json.loads(report_path.read_text())
                        task['edit_summary'] = {'style': report['style'], 'segments': len(report['clips']), 'seconds': report['output_duration'], 'audio': report['audio'], 'methods': sorted(set(c.get('method', 'sequence') for c in report['clips']))}
                        task['report_url'] = '/media/' + report_path.name
                    except (ValueError, KeyError, OSError):
                        pass
            return self.send(200, {'tasks': tasks})
        if self.path.startswith('/api/jobs/'):
            with connect() as db:
                row = db.execute('SELECT status,error,url FROM tasks WHERE id=?', (self.path.split('/')[-1],)).fetchone()
            return self.send(200, dict(row) if row else {'status': 'missing'})
        return super().do_GET()

    def do_POST(self):
        origin = self.headers.get('Origin')
        if origin and urlsplit(origin).netloc != self.headers.get('Host'):
            return self.send(403, {'error': '不允许跨站请求'})
        if self.path not in ['/api/login'] and not self.user():
            return self.send(401, {'error': '请先登录团队工作台'})
        if self.path == '/api/render':
            return self.send(400, {'error': '共享模式请通过任务队列提交'})
        if self.path not in ['/api/login', '/api/logout', '/api/tasks']:
            return super().do_POST()
        try:
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 200000: raise ValueError('请求大小不支持')
            data = json.loads(self.rfile.read(size))
            if self.path == '/api/login':
                address = self.client_address[0]
                with connect() as db:
                    attempt = db.execute('SELECT * FROM attempts WHERE address=?', (address,)).fetchone()
                    if attempt and attempt['expires'] > time.time() and attempt['count'] >= 10:
                        return self.send(429, {'error': '登录尝试过多，请 15 分钟后重试'})
                    row = db.execute('SELECT * FROM users WHERE name=?', (str(data.get('username', '')).strip(),)).fetchone()
                    password = str(data.get('password', ''))
                    actual = digest(password, row['salt'] if row else '00'*16)
                    if not row or not hmac.compare_digest(actual, row['password']):
                        count = attempt['count']+1 if attempt and attempt['expires'] > time.time() else 1
                        db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?)', (address, count, time.time()+900))
                        self.send(401, {'error': '用户名或密码不正确'})
                        return
                    db.execute('DELETE FROM attempts WHERE address=?', (address,))
                    db.execute('DELETE FROM sessions WHERE expires<?', (time.time(),))
                    token = secrets.token_urlsafe(32)
                    db.execute('INSERT INTO sessions VALUES (?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['name'], time.time()+43200))
                self.send_response(200)
                secure = '; Secure' if os.getenv('COOKIE_SECURE') == '1' else ''
                self.send_header('Set-Cookie', f'studio_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=43200{secure}')
                self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(b'{"ok":true}')
                return
            if self.path == '/api/logout':
                cookies = SimpleCookie(self.headers.get('Cookie', ''))
                with connect() as db:
                    db.execute('DELETE FROM sessions WHERE token=?', (hashlib.sha256(cookies['studio_session'].value.encode()).hexdigest(),))
                self.send_response(200); self.send_header('Set-Cookie', 'studio_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'); self.end_headers()
                return
            mode = data.get('mode')
            if mode not in ['product', 'avatar', 'reference', 'assets']: raise ValueError('请选择视频模式')
            script = str(data.get('script', '')).strip()
            if not script or len(script) > 12000: raise ValueError('请输入脚本（最多 12000 字符）')
            duration = int(data.get('duration', 15))
            if duration not in [15, 30, 45]: raise ValueError('不支持该时长')
            data['duration'] = duration
            status, error = 'needs_provider', MISSING_SERVICE.get(mode)
            if mode == 'reference':
                reference = str(data.get('reference_url', '')).strip()
                parsed = urlsplit(reference)
                if parsed.scheme != 'https' or not parsed.hostname or not (parsed.hostname == 'tiktok.com' or parsed.hostname.endswith('.tiktok.com')) or parsed.username or parsed.password:
                    raise ValueError('请填写有效的 TikTok HTTPS 链接')
                if data.get('target_mode') not in ['product', 'avatar']: raise ValueError('请选择改编成片模式')
                if not str(data.get('market', '')).strip(): raise ValueError('请选择目标市场')
                error = MISSING_SERVICE['reference']
            if mode == 'assets':
                if data.get('edit_style', 'scene') not in ['scene', 'rhythm', 'sequence']: raise ValueError('剪辑方式不支持')
                files = data.get('files', [])
                if not isinstance(files, list) or not 1 <= len(files) <= 12: raise ValueError('请选择 1–12 个素材')
                for name in files:
                    if not isinstance(name, str) or Path(name).name != name or Path(name).suffix not in ['.mp4','.mov','.webm','.jpg','.jpeg','.png','.webp'] or not (studio.DATA / name).is_file(): raise ValueError('素材无效')
                bgm = data.get('bgm')
                if bgm is not None and (not isinstance(bgm, str) or Path(bgm).name != bgm or Path(bgm).suffix not in ['.mp3','.wav','.m4a','.ogg'] or not (studio.DATA / bgm).is_file()): raise ValueError('音乐无效')
                volume = float(data.get('volume', .3))
                if not 0 <= volume <= 1: raise ValueError('音量无效')
                data['volume'] = volume
                status, error = 'queued', None
            with connect() as db:
                if db.execute("SELECT count(*) FROM tasks WHERE status IN ('queued','rendering')").fetchone()[0] >= 50:
                    return self.send(429, {'error': '队列已满，请稍后提交'})
                task_id = secrets.token_hex(16)
                db.execute('INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)', (task_id, self.user(), mode, script, json.dumps(data), status, error, None, time.time()))
            WAKE.set()
            return self.send(201, {'id': task_id, 'status': status, 'error': error})
        except (ValueError, TypeError, KeyError):
            return self.send(400, {'error': '请检查脚本、素材、时长和音量设置'})

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--create-user', metavar='USERNAME')
    args = parser.parse_args()
    init()
    if args.create_user:
        password = getpass.getpass('Password (at least 12 characters): ')
        if password != getpass.getpass('Confirm password: '): raise SystemExit('Passwords differ')
        create_user(args.create_user, password)
        print('User created')
    else:
        bootstrap_user()
        threading.Thread(target=worker, daemon=True).start()
        studio.ThreadingHTTPServer((os.getenv('BIND_HOST', '127.0.0.1'), int(os.getenv('PORT', '8000'))), TeamHandler).serve_forever()
