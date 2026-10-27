"""真实 FFmpeg 集成测试：python -m unittest discover -s tests -v"""
import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error

spec = importlib.util.spec_from_file_location('studio', Path(__file__).parents[1] / 'server.py')
studio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(studio)

class BGMTest(unittest.TestCase):
    def test_upload_loop_volume_fade_and_silent_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            studio.DATA = Path(tmp)
            http = studio.ThreadingHTTPServer(('127.0.0.1', 0), studio.Handler)
            threading.Thread(target=http.serve_forever, daemon=True).start()
            base = f'http://127.0.0.1:{http.server_port}'
            def request(path, data):
                req = urllib.request.Request(base + path, data=json.dumps(data).encode(), headers={'Content-Type': 'application/json'})
                with urllib.request.urlopen(req) as response:
                    return json.load(response)
            def upload(path):
                return request('/api/upload', {'name': path.name, 'data': base64.b64encode(path.read_bytes()).decode()})['id']
            def make(*args):
                subprocess.run(['ffmpeg', '-y', '-v', 'error', *args], check=True)
            try:
                picture = Path(tmp) / 'source.png'
                music = Path(tmp) / 'music.wav'
                make('-f', 'lavfi', '-i', 'color=c=green:s=64x64', '-frames:v', '1', str(picture))
                make('-f', 'lavfi', '-i', 'sine=frequency=440:duration=1', str(music))
                image_id, music_id = upload(picture), upload(music)
                for bgm, volume in [(music_id, .3), (None, 0)]:
                    job = request('/api/render', {'files': [image_id], 'duration': 15, 'bgm': bgm, 'volume': volume})['id']
                    deadline = time.monotonic() + 60
                    while studio.JOBS[job]['status'] == 'rendering' and time.monotonic() < deadline:
                        time.sleep(.2)
                    self.assertEqual(studio.JOBS[job]['status'], 'done', studio.JOBS[job])
                    video = Path(tmp) / f'{job}.mp4'
                    info = json.loads(studio.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]))
                    self.assertAlmostEqual(float(info['format']['duration']), 15, delta=.15)
                    audio = [s for s in info['streams'] if s['codec_type'] == 'audio']
                    self.assertEqual(len(audio), int(bgm is not None))
                    if bgm:
                        import array, math
                        def rms(start, length):
                            raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-ss', str(start), '-i', str(video), '-t', str(length), '-f', 'f32le', '-ac', '1', '-ar', '8000', '-'])
                            samples = array.array('f', raw)
                            return math.sqrt(sum(x*x for x in samples) / len(samples))
                        level = rms(8, .5)
                        self.assertGreater(level, .015) # 音源只有 1 秒；第 8 秒仍有循环音乐
                        self.assertLess(level, .04) # 默认 30% 音量已生效
                        self.assertLess(rms(14.8, .15), level / 3) # 结尾淡出
                for data in [{'files': [image_id], 'bgm': '../music.wav'}, {'files': [image_id], 'volume': 2}]:
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        request('/api/render', data)
                    self.assertEqual(error.exception.code, 400)
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/upload', {'name': 'bad.mp3', 'data': base64.b64encode(b'not audio').decode()})
                self.assertEqual(error.exception.code, 400)
            finally:
                http.shutdown()
                http.server_close()

if __name__ == '__main__':
    unittest.main()
