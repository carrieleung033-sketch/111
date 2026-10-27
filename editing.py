"""CPU scene detection through PySceneDetect; no paid API or semantic model."""
import subprocess
import tempfile
from pathlib import Path

ANALYSIS_LIMIT = 180

def detect_ranges(source):
    try:
        import cv2
        from scenedetect import open_video, SceneManager
        from scenedetect.detectors import ContentDetector
    except ImportError as exc:
        raise ValueError('镜头检测依赖未安装，请部署包含 requirements.txt 的最新版本') from exc
    cv2.setNumThreads(1)
    with tempfile.TemporaryDirectory(prefix='clipcart-scenes-') as tmp:
        proxy = Path(tmp) / 'analysis.mp4'
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-threads', '2', '-filter_threads', '1', '-i', str(source), '-t', str(ANALYSIS_LIMIT), '-vf', 'scale=256:144:force_original_aspect_ratio=decrease:force_divisible_by=2,fps=8', '-an', '-c:v', 'libx264', '-threads', '1', '-preset', 'ultrafast', str(proxy)], check=True, capture_output=True, text=True, timeout=240)
        video = open_video(str(proxy))
        try:
            manager = SceneManager()
            manager.auto_downscale = False
            manager.add_detector(ContentDetector(threshold=22, min_scene_len=4))
            manager.detect_scenes(video=video, show_progress=False)
            ranges = [(a.get_seconds(), b.get_seconds()) for a, b in manager.get_scene_list(start_in_scene=True)]
        finally:
            # VideoStreamCv2 has no close method in the pinned API.
            del video
        return ranges

def choose_scene_clips(ranges, allocation):
    """Sample detected shots chronologically; short centered extracts per shot."""
    ranges = [(a, b) for a, b in ranges if b-a >= .5]
    if len(ranges) < 2:
        return []
    count = min(len(ranges), max(2, round(allocation / 2.5)))
    indexes = [round(i*(len(ranges)-1)/(count-1)) for i in range(count)]
    clips = []
    for index in indexes:
        start, end = ranges[index]
        length = min(allocation/count, 2.5, (end-start)*.75)
        clips.append((start+(end-start-length)/2, length))
    return clips
