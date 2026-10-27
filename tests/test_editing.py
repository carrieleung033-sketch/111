"""Real scene detection, rendered frames and temporal cuts; no model mocks."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import server
from editing import detect_ranges

class EditingTest(unittest.TestCase):
    def make(self, *args):
        subprocess.run(['ffmpeg', '-y', '-v', 'error', *args], check=True, capture_output=True)

    def test_scene_cuts_and_rendered_frames(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'DATA', Path(tmp)):
            source = Path(tmp)/'source.mp4'
            self.make('-f','lavfi','-i','color=c=red:s=90x160:r=24:d=4',
                      '-f','lavfi','-i','color=c=green:s=90x160:r=24:d=4',
                      '-f','lavfi','-i','color=c=blue:s=90x160:r=24:d=4',
                      '-filter_complex','[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]',
                      '-map','[v]','-c:v','libx264',str(source))
            ranges = detect_ranges(source)
            self.assertEqual(len(ranges),3,ranges)
            self.assertAlmostEqual(ranges[1][0],4,delta=.2)
            self.assertAlmostEqual(ranges[2][0],8,delta=.2)
            server.render('test-scenes',['source.mp4'],15,edit_style='scene')
            result = server.JOBS.pop('test-scenes')
            self.assertEqual(result['status'],'done',result)
            report = json.loads((Path(tmp)/'test-scenes-edit.json').read_text())
            self.assertEqual(len(report['clips']),3)
            self.assertAlmostEqual(report['output_duration'],7.5,delta=.15)
            self.assertTrue(all(c['method']=='scene' for c in report['clips']))
            # The encoded output really contains all three source scenes.
            for position, channel in [(.5,0),(3,1),(5.5,2)]:
                raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(position),'-i',str(Path(tmp)/'test-scenes.mp4'),'-frames:v','1','-vf','scale=1:1','-pix_fmt','rgb24','-f','rawvideo','-'])
                self.assertEqual(max(range(3),key=lambda i:raw[i]),channel)
            # Legacy sequential behavior is explicit and preserves duration.
            plan=server.clip_plan(['source.mp4'],15,'sequence')
            self.assertEqual(len(plan),1)
            self.assertAlmostEqual(plan[0]['duration'],12,delta=.15)

    def test_single_scene_falls_back_to_time_cuts(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(server, 'DATA', Path(tmp)):
            source=Path(tmp)/'solid.mp4'
            self.make('-f','lavfi','-i','color=c=yellow:s=90x160:r=24:d=8','-c:v','libx264',str(source))
            clips=server.clip_plan(['solid.mp4'],15,'scene')
            self.assertGreater(len(clips),1)
            self.assertTrue(all(c['method']=='rhythm' for c in clips))
            self.assertLess(sum(c['duration'] for c in clips),8)
            self.assertGreater(clips[1]['start'],clips[0]['start']+clips[0]['duration'])
