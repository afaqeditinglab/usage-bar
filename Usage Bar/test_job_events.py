"""Offline timing and exactly-once event receipt checks. No real sound or account reads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import usage_bar as bar
import afaq_notifications as audio


class JobEventTests(unittest.TestCase):
    def test_timing_and_repeated_status_events(self):
        with tempfile.TemporaryDirectory(dir=bar.ROOT / "tmp") as folder:
            with patch.object(bar, "ROOT", Path(folder)), patch.object(bar.subprocess, "run", return_value=Mock(returncode=0)):
                started = "2026-10-20T00:00:00+00:00"
                bar.report("Timer", folder, 20, "working", job_id="job-1", started_at=started)
                first = bar.read_json(bar.report("Timer", folder, 20, "waiting", job_id="job-1"))
                again = bar.read_json(bar.report("Timer", folder, 20, "waiting", job_id="job-1"))
                self.assertEqual(first["event_id"], again["event_id"])
                bar.report("Timer", folder, 20, "working", job_id="job-1")
                second_wait = bar.read_json(bar.report("Timer", folder, 20, "waiting", job_id="job-1"))
                self.assertNotEqual(first["event_id"], second_wait["event_id"])
                done = bar.read_json(bar.report("Timer", folder, 20, "done", job_id="job-1"))
                repeated = bar.read_json(bar.report("Timer", folder, 20, "done", job_id="job-1"))
                for key in ("event_id", "job_finished_at", "elapsed_seconds", "last_done_time"):
                    self.assertEqual(done[key], repeated[key])
                fresh = bar.read_json(bar.report("Timer", folder, 20, "working"))
                self.assertNotEqual(fresh["job_id"], done["job_id"])
                self.assertIsNone(fresh["job_finished_at"])

    def test_timer_format_and_invalid_timestamps(self):
        note = {"message_received_at": "2026-10-20T00:00:00+00:00", "job_finished_at": "2026-10-20T00:02:03+00:00"}
        self.assertEqual(bar.job_duration(note), "Took 2m 3s")
        note["job_finished_at"] = None
        self.assertEqual(bar.job_duration(note, 1792454523), "2m 3s")
        for value in (None, {}, {"message_received_at": "bad"}, {"message_received_at": "2026-10-20T00:00:00"}):
            self.assertEqual(bar.job_duration(value), "—")

    def test_completed_event_deduplicates_and_ambiguous_event_does_not_replay(self):
        with tempfile.TemporaryDirectory(dir=bar.ROOT / "tmp") as folder:
            with patch.object(audio, "ROOT", Path(folder)), patch.object(audio, "play") as play:
                event = {"kind": "waiting", "event_id": "same-event"}
                result = audio.deliver_sound(event)
                duplicate = audio.deliver_sound(event)
                self.assertEqual(result["playback"], "completed")
                self.assertTrue(duplicate["duplicate"])
                play.assert_called_once_with("waiting")
                receipt = next((Path(folder) / "events").glob("*.json"))
                result["playback"] = "playing"
                receipt.write_text(json.dumps(result))
                self.assertEqual(audio.deliver_sound(event)["playback"], "playing")
                play.assert_called_once()
                with self.assertRaises(ValueError):
                    audio.deliver_sound(dict(event, kind="done"))

    def test_configured_original_file_is_used_directly(self):
        with tempfile.TemporaryDirectory(dir=bar.ROOT / "tmp") as folder:
            root = Path(folder)
            original = root / "original.wav"
            original.write_bytes(b"read-only fixture")
            (root / "sound-files.json").write_text(json.dumps({"waiting": str(original)}))
            with patch.object(audio, "ROOT", root), patch.object(audio.winsound, "PlaySound") as play:
                audio.play("waiting")
                play.assert_called_once_with(str(original), audio.winsound.SND_FILENAME | audio.winsound.SND_NODEFAULT)
                self.assertEqual(original.read_bytes(), b"read-only fixture")


if __name__ == "__main__":
    unittest.main()
