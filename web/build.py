"""Build web/index.html, the guide as a single web page, from web/template.html and the repo's data.

- Charts: the length and scale-degree data come from analysis/features.csv (one version per melody).
- Practice pieces: audio is played from compositions/previews/; the piano rolls are rebuilt
  from compositions/compose.py, from the same MIDI each preview was rendered from.

    python web/build.py

Open web/index.html in a browser from a clone of the repo (it loads the audio from
../compositions/previews/, and fonts from Google Fonts).
"""

import collections
import csv
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import librosa
import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(REPO / "compositions"))
import compose  # noqa: E402

CAR_NAMES = {"189-chime": "189系", "373-chime3": "373系", "kiha85-chime2": "キハ85", "kodama1": "こだま",
             "nozomi": "のぞみ", "tetsudoshoka": "鉄道唱歌", "haikensu": "ハイケンスのセレナーデ"}


def chart_data() -> dict:
    rows = list(csv.DictReader((REPO / "analysis" / "features.csv").open(encoding="utf-8-sig")))
    dep = [r for r in rows if r["kind"] == "发车铃" and r["transcription"].startswith("自动")]
    families = collections.OrderedDict()
    for r in dep:
        families.setdefault(r["family"], []).append(r)
    reps = [next((x for x in g if not x["variant"]), g[0]) for g in families.values()]
    groups = {"orig": [r for r in reps if r["origin"] == "原创"], "arr": [r for r in reps if r["origin"] == "改编"],
              "car": [r for r in rows if r["kind"] == "车内铃"]}
    return {
        "lengths": {g: [{"name": CAR_NAMES.get(r["title"], r["family"]), "sec": round(float(r["span_s"]), 2),
                         "jrsh": r["source"].startswith("JR-SH")} for r in rs] for g, rs in groups.items()},
        "degrees": {g: [round(float(np.mean([float(r[f"deg_{d}"]) for r in rs if r["mode"] == "major"])), 4)
                        for d in range(12)] for g, rs in groups.items()},
        "degree_n": {g: sum(r["mode"] == "major" for r in rs) for g, rs in groups.items()},
    }


def pieces_data() -> dict:
    """For each practice piece: the preview's URL (relative to web/), its length, and its notes."""
    tetsudo = compose.tetsudo_shoka()
    previews = {  # key -> (preview file, the MIDI it was rendered from)
        "01": ("01_晨光.mp3", compose.to_midi(compose.morning_light())),
        "02": ("02_港风_循环版_两遍+结尾.mp3",
               compose.to_midi(compose.harbor_breeze(), passes=2, then=compose.harbor_breeze_ending())),
        "03": ("03_里山.mp3", compose.to_midi(compose.satoyama())),
        "04": ("04_鉄道唱歌_发车版.mp3", compose.to_midi(tetsudo)),
        "04b": ("04b_鉄道唱歌_2番线版.mp3",
                compose.to_midi(compose.transposed(tetsudo, "04b_鉄道唱歌_2番线版", semitones=2, tempo_scale=1.05))),
        "05": ("05_到站_车内铃.mp3", compose.to_midi(compose.arrival_chime())),
    }
    audio, rolls = {}, {}
    for key, (name, pm) in previews.items():
        path = REPO / "compositions" / "previews" / name
        if not path.is_file():
            sys.exit(f"missing preview {path}; render it with: python compositions/compose.py --render")
        audio[key] = {"file": "../compositions/previews/" + quote(name), "dur": round(librosa.get_duration(path=str(path)), 2)}
        notes = []
        for inst in pm.instruments:
            if inst.name.startswith(("Double", "Octave below")):  # doublings of the melody add nothing to the roll
                continue
            layer = "m" if inst.name.startswith("Melody") else "b" if inst.name.startswith("Bass") else "a"
            notes += [[round(n.start, 3), round(n.end - n.start, 3), n.pitch, layer] for n in inst.notes]
        rolls[key] = sorted(notes)
    return {"audio": audio, "rolls": rolls}


def main() -> None:
    data = {**chart_data(), **pieces_data()}
    page = (HERE / "template.html").read_text(encoding="utf-8")
    page = page.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    # numbered-notation octave dots as styled spans: combining dots sit badly in the LED-style font
    page = re.sub("([0-9])̇", r"<span class='oh'>\1</span>", page)
    page = re.sub("([0-9])̣", r"<span class='ol'>\1</span>", page)
    (HERE / "index.html").write_text(page, encoding="utf-8")
    print(f"web/index.html: {len(page.encode('utf-8')) // 1024} KB, {sum(len(v) for v in data['rolls'].values())} roll notes")


if __name__ == "__main__":
    main()
