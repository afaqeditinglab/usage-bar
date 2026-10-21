"""Offline notification regressions; no account access or real audio."""
import io
from pathlib import Path
import tempfile
from unittest.mock import patch, Mock
import wave
import usage_bar as bar
import afaq_notifications as audio


def run():
    with tempfile.TemporaryDirectory(dir=bar.ROOT / "tmp") as folder:
        with patch.object(bar, "ROOT", Path(folder)):
            with patch.object(bar.subprocess, "run", return_value=Mock(returncode=0)) as child:
                bar.report("Test", folder, 10, "waiting")
                bar.report("Test", folder, 10, "working")
                bar.report("Test", folder, 10, "done")
                assert child.call_count == 2
                calls = [call.args[0] for call in child.call_args_list]
                assert [call[3] for call in calls] == ["waiting", "done"]
                assert calls[0][-1] != calls[1][-1]
                assert not list(Path(folder).glob("ping-*.json"))
                completed = bar.read_json(bar.status_path("Test"))["last_done_time"]
                with patch.object(bar, "utc_now", return_value="2099-01-01T00:00:00+00:00"), patch.object(bar.time, "time", return_value=4070908800):
                    bar.report("Test", folder, 10, "working")
                assert bar.read_json(bar.status_path("Test"))["last_done_time"] == completed
        with patch.object(audio, "ROOT", Path(folder)):
            with patch.object(audio, "play", side_effect=[RuntimeError("busy"), None]) as play:
                with patch.object(audio.time, "sleep"):
                    result = audio.deliver_sound({"kind": "waiting", "event_id": "test-1"})
                assert play.call_count == 2 and result["playback"] == "completed"
                assert result["attempts"] == 2 and "error" not in result
            with patch.object(audio, "play", side_effect=RuntimeError("busy")) as play:
                with patch.object(audio.time, "sleep"):
                    result = audio.deliver_sound({"kind": "done", "event_id": "test-2"})
                assert play.call_count == 3 and result["playback"] == "failed"
            assert len((Path(folder) / "notification-history.jsonl").read_text().splitlines()) == 2
    for kind in ("done", "waiting"):
        with wave.open(io.BytesIO(audio.wave_bytes(kind))) as wav:
            assert wav.getframerate() == 24000 and wav.getnchannels() == 1
    print("Passed: standalone dispatch, fast transitions, unique events, retry recovery, failure logging, WAV format")


if __name__ == "__main__":
    run()
