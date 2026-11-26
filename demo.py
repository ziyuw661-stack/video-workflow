#!/usr/bin/env python3
"""Offline smoke demo: synthetic audio and visuals, not AI-generated content."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

def run(*args):
    subprocess.run(args, check=True)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", default="demo-output")
    p.add_argument("--vertical", action="store_true")
    a = p.parse_args()
    for cmd in ("ffmpeg", "ffprobe"):
        if not shutil.which(cmd):
            p.exit(1, f"Missing {cmd}. Install FFmpeg from https://ffmpeg.org/download.html and add it to PATH.\n")
    out = Path(a.output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    size = "720x1280" if a.vertical else "1280x720"
    video = out / "demo.mp4"
    srt = out / "demo.srt"
    srt.write_text("1\n00:00:00,000 --> 00:00:02,000\nWorkflow smoke test\n\n2\n00:00:02,000 --> 00:00:04,000\nSynthetic test audio and visuals\n", encoding="utf-8")
    run("ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", f"color=c=0x294C70:s={size}:r=25:d=2",
        "-f", "lavfi", "-i", f"color=c=0x597C9D:s={size}:r=25:d=2",
        "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=4",
        "-i", str(srt),
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]",
        "-map", "[v]", "-map", "2:a", "-map", "3:s",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-af", "volume=0.10", "-c:s", "mov_text", "-movflags", "+faststart", str(video))
    raw = subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)], text=True)
    probe = json.loads(raw)
    duration = float(probe["format"]["duration"])
    types = {s["codec_type"] for s in probe["streams"]}
    if not {"video", "audio", "subtitle"} <= types or duration < 4 or duration > 4.2:
        raise RuntimeError("Unexpected duration or missing streams")
    run("ffmpeg", "-v", "error", "-xerror", "-i", str(video), "-map", "0:v", "-map", "0:a", "-f", "null", "-")
    report = {"scope": "synthetic smoke demo only", "duration_seconds": duration,
              "streams": sorted(types), "decoded": True, "subtitle_end_seconds": 4}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(video)

if __name__ == "__main__":
    main()
