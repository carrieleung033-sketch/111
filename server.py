import json, os, subprocess, uuid, threading, urllib.request, base64, math
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

ROOT = Path(__file__).resolve().parent
DATA = ROOT / '.runtime'
DATA.mkdir(exist_ok=True)
JOBS = {}

def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout

def clip_plan(files, duration, edit_style):
    """Chronological samples across each source; no semantic/AI selection."""
    clips = []
    for name in files:
        source = DATA / name
        allocation = duration / len(files)
        image = source.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']
        if image:
            clips.append({'file': name, 'start': 0, 'duration': allocation, 'image': True, 'method': 'image'})
            continue
        seconds = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(source)]).strip())
        if not math.isfinite(seconds) or seconds <= 0:
            raise ValueError('无法读取视频时长')
        if edit_style == 'scene' and seconds >= 1.2:
            from editing import detect_ranges, choose_scene_clips, ANALYSIS_LIMIT
            ranges = detect_ranges(source)
            selected = choose_scene_clips(ranges, allocation)
            if selected:
                for start, length in selected:
                    clips.append({'file': name, 'start': start, 'duration': length, 'image': False, 'method': 'scene', 'detected_scenes': len(ranges), 'analysis_limit': ANALYSIS_LIMIT})
                continue
            # No distinct shots: fall back to temporal sampling, explicitly recorded.
        if edit_style == 'sequence' or seconds < 1.2:
            clips.append({'file': name, 'start': 0, 'duration': min(seconds, allocation), 'image': False, 'method': 'sequence'})
            continue
        margin = min(.25, seconds * .02)
        available = seconds - 2 * margin
        budget = min(allocation, available * .75)
        count = max(2, math.ceil(budget / 2.5))
        length = budget / count
        for index in range(count):
            start = margin + (available - length) * index / (count - 1)
            clips.append({'file': name, 'start': start, 'duration': length, 'image': False, 'method': 'rhythm'})
    return clips

def render(job, files, duration, bgm=None, volume=0.3, edit_style='scene'):
    try:
        clips = clip_plan(files, duration, edit_style)
        parts = []
        for i, clip in enumerate(clips):
            source = DATA / clip['file']
            out = DATA / f'{job}-{i}.mp4'
            args = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-threads', '2', '-filter_threads', '1']
            if clip['image']:
                args += ['-loop', '1']
            else:
                args += ['-ss', str(clip['start'])]
            args += ['-i', str(source), '-t', str(clip['duration']), '-vf', 'scale=720:1280:force_original_aspect_ratio=increase,crop=720:1280,setsar=1,fps=30', '-an', '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', str(out)]
            run(args)
            parts.append(out)
        listing = DATA / f'{job}.txt'
        listing.write_text(''.join(f"file '{p}'\n" for p in parts))
        run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(listing), '-c', 'copy', '-movflags', '+faststart', str(DATA / f'{job}.mp4')])
        if bgm:
            video = DATA / f'{job}.mp4'
            seconds = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)]).strip())
            mixed = DATA / f'{job}-bgm.mp4'
            fade = min(1.5, seconds / 2)
            run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', '-i', str(video), '-stream_loop', '-1', '-i', str(DATA / bgm), '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-af', f'volume={volume},afade=t=out:st={seconds-fade}:d={fade}', '-t', str(seconds), '-movflags', '+faststart', str(mixed)])
            mixed.replace(video)
        video = DATA / f'{job}.mp4'
        actual = float(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)]).strip())
        report = {'style': edit_style, 'clips': clips, 'requested_duration': duration, 'output_duration': actual, 'audio': 'bgm' if bgm else 'silent', 'semantic_selection': False, 'detector': 'PySceneDetect' if edit_style == 'scene' else None}
        (DATA / f'{job}-edit.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
        JOBS[job] = {'status': 'done', 'url': f'/media/{job}.mp4', 'report_url': f'/media/{job}-edit.json'}
    except ValueError as e:
        JOBS[job] = {'status': 'failed', 'error': str(e)}
    except subprocess.CalledProcessError as e:
        JOBS[job] = {'status': 'failed', 'error': e.stderr[-1000:]}
    except Exception:
        JOBS[job] = {'status': 'failed', 'error': '视频处理失败'}

class Handler(BaseHTTPRequestHandler):
    def send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == '/api/status':
            return self.send(200, {'ai': bool(os.getenv('OPENAI_API_KEY')), 'editor': True})
        if self.path.startswith('/api/jobs/'):
            return self.send(200, JOBS.get(self.path.split('/')[-1], {'status': 'missing'}))
        path = (DATA / self.path[7:]) if self.path.startswith('/media/') else ROOT / 'web' / ('index.html' if self.path == '/' else self.path.lstrip('/'))
        base = DATA if self.path.startswith('/media/') else ROOT / 'web'
        if not path.resolve().is_relative_to(base.resolve()) or not path.is_file():
            return self.send(404, {'error': '未找到文件'})
        types = {'.html': 'text/html; charset=utf-8', '.css': 'text/css', '.js': 'text/javascript', '.mp4': 'video/mp4', '.mp3': 'audio/mpeg', '.wav': 'audio/wav', '.m4a': 'audio/mp4', '.ogg': 'audio/ogg', '.json': 'application/json; charset=utf-8'}
        self.send_response(200); self.send_header('Content-Type', types.get(path.suffix, 'application/octet-stream')); self.send_header('Content-Length', str(path.stat().st_size)); self.end_headers()
        with path.open('rb') as f:
            while chunk := f.read(1024 * 1024): self.wfile.write(chunk)
    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length > 60 * 1024 * 1024: return self.send(413, {'error': '单次上传最大 60MB'})
            data = json.loads(self.rfile.read(length))
            if self.path == '/api/upload':
                ext = Path(data['name']).suffix.lower()
                if ext not in ['.mp4', '.mov', '.webm', '.jpg', '.jpeg', '.png', '.webp', '.mp3', '.wav', '.m4a', '.ogg']: raise ValueError('不支持该素材格式')
                name = uuid.uuid4().hex + ext
                (DATA / name).write_bytes(base64.b64decode(data['data'], validate=True))
                if ext in ['.mp3', '.wav', '.m4a', '.ogg']:
                    try:
                        streams = json.loads(run(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(DATA / name)]))['streams']
                        if not any(x.get('codec_type') == 'audio' for x in streams): raise ValueError()
                    except (subprocess.CalledProcessError, ValueError, KeyError):
                        (DATA / name).unlink(missing_ok=True)
                        raise ValueError('无法读取音乐，请上传有效的 MP3、WAV、M4A 或 OGG 文件')
                return self.send(200, {'id': name})
            if self.path == '/api/render':
                files = data['files']
                if not 1 <= len(files) <= 12: raise ValueError('请选择 1–12 个素材')
                for name in files:
                    if Path(name).name != name or not (DATA / name).is_file() or Path(name).suffix.lower() not in ['.mp4', '.mov', '.webm', '.jpg', '.jpeg', '.png', '.webp']: raise ValueError('视频或图片素材不存在')
                duration = int(data.get('duration', 15))
                if duration not in [15, 30, 45]: raise ValueError('不支持该时长')
                bgm = data.get('bgm')
                if bgm is not None and (not isinstance(bgm, str) or Path(bgm).name != bgm or Path(bgm).suffix.lower() not in ['.mp3', '.wav', '.m4a', '.ogg'] or not (DATA / bgm).is_file()):
                    raise ValueError('背景音乐不存在或格式不支持')
                volume = float(data.get('volume', 0.3))
                if not math.isfinite(volume) or not 0 <= volume <= 1: raise ValueError('音乐音量必须在 0–100% 之间')
                edit_style = data.get('edit_style', 'scene')
                if edit_style not in ['scene', 'rhythm', 'sequence']: raise ValueError('剪辑方式不支持')
                job = uuid.uuid4().hex
                JOBS[job] = {'status': 'rendering'}
                threading.Thread(target=render, args=(job, files, duration, bgm, volume, edit_style), daemon=True).start()
                return self.send(200, {'id': job})
            if self.path == '/api/script':
                product = str(data.get('product', '')).strip()[:300]
                benefit = str(data.get('benefit', '')).strip()[:1500]
                if not product: raise ValueError('请填写商品名称')
                language = data.get('language', 'English')
                key = os.getenv('OPENAI_API_KEY')
                if key:
                    prompt = f'Write a TikTok product video script in {language}. Product: {product}. User-provided facts: {benefit}. Duration: {data.get("duration",15)} seconds. Include three shots with timing, voiceover, on-screen text, CTA. Do not invent product claims, discounts or testimonials.'
                    req = urllib.request.Request('https://api.openai.com/v1/chat/completions', data=json.dumps({'model': os.getenv('OPENAI_MODEL', 'gpt-4o-mini'), 'messages': [{'role': 'user', 'content': prompt}]}).encode(), headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
                    with urllib.request.urlopen(req, timeout=60) as response: result = json.load(response)
                    return self.send(200, {'mode': 'AI', 'text': result['choices'][0]['message']['content']})
                text = f'【模板草稿 · 未调用 AI】\n\n01 / HOOK · 产品特写\nMeet {product}.\n\n02 / DEMO · 展示实际使用\n{benefit or "添加经过核实的商品卖点，配合实际演示。"}\n\n03 / CTA · 商品全景\nExplore {product} in our shop.\n\n目标语言：{language}。此模板未自动翻译；可手动编辑，或接入 AI 生成。'
                return self.send(200, {'mode': 'template', 'text': text})
            return self.send(404, {'error': '接口不存在'})
        except ValueError as e: self.send(400, {'error': str(e)})
        except Exception: self.send(502, {'error': '服务请求失败，请检查模型配置或服务端日志；可继续使用素材剪辑。'})

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', int(os.getenv('PORT', '8000'))), Handler).serve_forever()
