"""Cut an audio fragment from a downloaded video into assets/speech/<name>.ogg.

    python3 tools/extract_speech.py VIDEO NAME [START_SECONDS] [DURATION_SECONDS]

NAME is the `file` value from SPEECH in engine/story.py. Requires ffmpeg.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(video, name, start="0", duration=None):
    out = os.path.join(ROOT, "assets", "speech")
    os.makedirs(out, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-i", video]
    if duration:
        cmd += ["-t", str(duration)]
    cmd += ["-vn", "-ac", "1", "-af", "loudnorm=I=-18:TP=-2,afade=t=in:d=0.4",
            "-c:a", "libvorbis", "-q:a", "4", os.path.join(out, name + ".ogg")]
    subprocess.run(cmd, check=True)
    print("ok", os.path.join(out, name + ".ogg"))


if __name__ == "__main__":
    main(*sys.argv[1:])
