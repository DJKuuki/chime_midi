"""Group statistics from analysis/features.csv: originals vs. arrangements (departure melodies,
one representative per melody family) and in-car chimes, plus what the variants of one melody
change (pitch, tempo). Prints Markdown tables and writes analysis/summary.json.

    python analysis/summary.py
"""

import collections
import csv
import json
from pathlib import Path

import librosa
import numpy as np

REPO = Path(__file__).resolve().parent.parent
ROWS = list(csv.DictReader((REPO / "analysis" / "features.csv").open(encoding="utf-8-sig")))
DEGREE_NAMES = ["1", "b2", "2", "b3", "3", "4", "#4", "5", "b6", "6", "b7", "7"]


def num(r, k):
    try:
        return float(r[k])
    except (KeyError, ValueError, TypeError):
        return float("nan")


def representatives(rows):
    """One row per melody family: the version without a variant marker, else the first."""
    fams = collections.OrderedDict()
    for r in rows:
        fams.setdefault(r["family"], []).append(r)
    return [next((x for x in group if not x["variant"]), group[0]) for group in fams.values()]


def groups():
    dep = [r for r in ROWS if r["kind"] == "发车铃" and r["transcription"].startswith("自动")]
    reps = representatives(dep)
    out = {
        "原创·全部": [r for r in reps if r["origin"] == "原创"],
        "改编·全部": [r for r in reps if r["origin"] == "改编"],
        "原创·JR-SH": [r for r in reps if r["source"].startswith("JR-SH")],
        "原创·SF": [r for r in reps if r["source"].startswith("SF")],
        "原创·西班牙语标题": [r for r in reps if "西班牙语" in r["source"]],
        "原创·英文标题": [r for r in reps if r["source"].startswith("英文")],
        "原创·日文标题": [r for r in reps if r["source"].startswith("日文")],
        "车内铃（手工MIDI）": [r for r in ROWS if r["kind"] == "车内铃"],
    }
    return out


def med(values):
    v = np.array([x for x in values if x == x])
    return (float(np.median(v)), float(np.percentile(v, 25)), float(np.percentile(v, 75))) if len(v) else (np.nan,) * 3


def share(rows, pred):
    return float(np.mean([pred(r) for r in rows])) if rows else float("nan")


def describe(rows) -> dict:
    d = {"n": len(rows)}
    d["span_s"] = med([num(r, "span_s") for r in rows])
    d["tempo"] = med([num(r, "tempo_bpm") for r in rows])
    d["mel_notes_per_s"] = med([num(r, "mel_notes") / num(r, "span_s") for r in rows])
    d["major"] = share(rows, lambda r: r["mode"] == "major")
    d["degrees"] = [float(np.nanmean([num(r, f"deg_{k}") for r in rows])) for k in range(12)]
    d["pentatonic"] = med([num(r, "share_pentatonic") for r in rows])
    d["share_4_7"] = med([num(r, "share_4_7") for r in rows])
    d["chromatic"] = med([num(r, "share_chromatic") for r in rows])
    d["mel_median_pitch"] = med([num(r, "mel_median_pitch") for r in rows])
    d["mel_range"] = med([num(r, "mel_range") for r in rows])
    d["mel_step"] = med([num(r, "mel_step") for r in rows])
    d["mel_repeat"] = med([num(r, "mel_repeat") for r in rows])
    d["mel_leap"] = med([num(r, "mel_leap") for r in rows])
    d["last_deg"] = collections.Counter(DEGREE_NAMES[int(float(r["mel_last_deg"]))] for r in rows if r.get("mel_last_deg"))
    d["first_deg"] = collections.Counter(DEGREE_NAMES[int(float(r["mel_first_deg"]))] for r in rows if r.get("mel_first_deg"))
    d["final_descent"] = share([r for r in rows if r.get("mel_final_descent")], lambda r: r["mel_final_descent"] == "True")
    d["climax_pos"] = med([num(r, "mel_climax_pos") for r in rows])
    d["final_chord"] = collections.Counter(r.get("final_chord", "") for r in rows)
    d["ends_on_I"] = share(rows, lambda r: r.get("final_chord", "").lower().rstrip("7").replace("add9", "").replace("sus4", "").replace("maj", "") == "i")
    d["cadence"] = collections.Counter(f'{r.get("penult_chord", "")}→{r.get("final_chord", "")}' for r in rows)
    d["beats_per_chord"] = med([num(r, "beats_per_chord") for r in rows])
    d["share_7th"] = med([num(r, "share_7th") for r in rows])
    d["share_sus_add"] = med([num(r, "share_sus_add") for r in rows])
    d["chord_shares"] = {k: float(np.nanmean([num(r, f"share_{k}") for r in rows])) for k in ("I", "ii", "iii", "IV", "V", "vi")}
    for flag in ("prog_IV_V_I", "prog_ii_V_I", "prog_royal_road", "prog_I_V_vi_IV", "prog_secondary_dom", "prog_borrowed"):
        d[flag] = share(rows, lambda r, f=flag: r.get(f) == "True")
    d["poly_mean"] = med([num(r, "poly_mean") for r in rows])
    d["block_onsets"] = med([num(r, "share_block_onsets") for r in rows])
    d["low_notes"] = med([num(r, "share_low_notes") for r in rows])
    d["high_notes"] = med([num(r, "share_high_notes") for r in rows])
    d["highest_p95"] = med([num(r, "highest_p95") for r in rows])
    d["lowest_p5"] = med([num(r, "lowest_p5") for r in rows])
    for k in ("on_beat", "on_eighth", "on_sixteenth", "on_triplet"):
        d[k] = med([num(r, k) for r in rows])
    d["keys"] = collections.Counter(r["key"] for r in rows)
    return d


def variant_shifts() -> list[dict]:
    """For each pitch/tempo variant vs. the base version of its family: the pitch shift, from
    time-averaged spectra at 0.1-semitone resolution, and the tempo ratio, from the slope of a
    DTW alignment of their chroma. Only meaningful when the variant really is the base version
    shifted: several labels are relative to some other version, so check them against the label."""
    dep = [r for r in ROWS if r["kind"] == "发车铃" and r["transcription"].startswith("自动")]
    base = {r["family"]: r for r in representatives(dep)}
    cache = {}
    bins_per_octave = 120

    def audio_info(r):
        if r["id"] not in cache:
            y, sr = librosa.load(str(REPO / r["audio"]), sr=22050, mono=True)
            cqt = np.abs(librosa.cqt(y, sr=sr, hop_length=512, fmin=librosa.note_to_hz("C3"),
                                     n_bins=bins_per_octave * 5, bins_per_octave=bins_per_octave))
            spectrum = np.log1p(100 * cqt / cqt.max()).mean(axis=1)
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
            cache[r["id"]] = (spectrum - spectrum.mean(), chroma)
        return cache[r["id"]]

    out = []
    for r in dep:
        b = base[r["family"]]
        if r is b or not any(k in r["variant_kind"] for k in ("移调", "变速")):
            continue
        s_b, c_b = audio_info(b)
        s_r, c_r = audio_info(r)
        shifts = range(-40, 41)  # +-4 semitones in tenths
        corr = [np.dot(s_b[max(0, -k):len(s_b) - max(0, k)], s_r[max(0, k):len(s_r) - max(0, -k)]) / (len(s_b) - abs(k))
                for k in shifts]
        semitones = shifts[int(np.argmax(corr))] / 10
        _, path = librosa.sequence.dtw(c_b, np.roll(c_r, -int(round(semitones)), axis=0), metric="cosine")
        path = path[::-1]
        a, z = int(0.1 * len(path)), int(0.9 * len(path))
        slope = np.polyfit(path[a:z, 0], path[a:z, 1], 1)[0]  # variant frames per base frame
        out.append({"id": r["id"], "family": r["family"], "variant": r["variant"],
                    "semitones": round(float(semitones), 1), "tempo_ratio": round(float(1 / slope), 2)})
    return out


def fmt(t, digits=2):
    m, lo, hi = t
    return f"{m:.{digits}f}（{lo:.{digits}f}–{hi:.{digits}f}）"


def main() -> None:
    g = {name: describe(rows) for name, rows in groups().items()}
    names = list(g)
    print("| 指标 | " + " | ".join(names) + " |")
    print("|---|" + "---|" * len(names))
    lines = [
        ("旋律族数", lambda d: str(d["n"])),
        ("有效长度 s", lambda d: fmt(d["span_s"], 1)),
        ("速度 BPM（约）", lambda d: fmt(d["tempo"], 0)),
        ("旋律音/秒", lambda d: fmt(d["mel_notes_per_s"], 1)),
        ("大调占比", lambda d: f"{d['major']:.0%}"),
        ("五声音级占比", lambda d: fmt(d["pentatonic"])),
        ("4、7 级占比", lambda d: fmt(d["share_4_7"])),
        ("调外音占比", lambda d: fmt(d["chromatic"])),
        ("旋律中位音高 MIDI", lambda d: fmt(d["mel_median_pitch"], 0)),
        ("旋律音域 半音", lambda d: fmt(d["mel_range"], 0)),
        ("级进占比", lambda d: fmt(d["mel_step"])),
        ("同音反复占比", lambda d: fmt(d["mel_repeat"])),
        ("跳进(≥4度)占比", lambda d: fmt(d["mel_leap"])),
        ("结尾落主音", lambda d: f"{d['last_deg'].get('1', 0) / max(d['n'], 1):.0%}"),
        ("最后和弦是 I", lambda d: f"{d['ends_on_I']:.0%}"),
        ("每和弦拍数", lambda d: fmt(d["beats_per_chord"], 1)),
        ("七和弦拍占比", lambda d: fmt(d["share_7th"])),
        ("sus4/add9 拍占比", lambda d: fmt(d["share_sus_add"])),
        ("含 IV-V-I", lambda d: f"{d['prog_IV_V_I']:.0%}"),
        ("含副属/借用和弦", lambda d: f"{d['prog_secondary_dom']:.0%} / {d['prog_borrowed']:.0%}"),
        ("平均同时发声数", lambda d: fmt(d["poly_mean"], 1)),
        ("和弦式起音占比", lambda d: fmt(d["block_onsets"])),
        ("低音(<C3)音符占比", lambda d: fmt(d["low_notes"])),
        ("高音(≥C5)音符占比", lambda d: fmt(d["high_notes"])),
        ("旋律起音在正拍", lambda d: fmt(d["on_beat"])),
        ("旋律起音在八分反拍", lambda d: fmt(d["on_eighth"])),
        ("旋律起音在十六分位", lambda d: fmt(d["on_sixteenth"])),
        ("旋律起音在三连音位", lambda d: fmt(d["on_triplet"])),
    ]
    for label, f in lines:
        print(f"| {label} | " + " | ".join(f(g[n]) for n in names) + " |")
    print()
    for n in names:
        d = g[n]
        print(f"## {n}: last melody degree {d['last_deg'].most_common(5)}  first {d['first_deg'].most_common(4)}")
        print(f"   final chords {d['final_chord'].most_common(6)}")
        print(f"   cadences {d['cadence'].most_common(6)}")
        print(f"   chord shares {({k: round(v, 2) for k, v in d['chord_shares'].items()})}  royal-road {d['prog_royal_road']:.0%}  I-V-vi-IV {d['prog_I_V_vi_IV']:.0%}  ii-V-I {d['prog_ii_V_I']:.0%}")
        print(f"   degrees {[f'{DEGREE_NAMES[k]}:{v:.2f}' for k, v in enumerate(d['degrees'])]}")
        print(f"   keys {d['keys'].most_common(8)}  climax pos {d['climax_pos'][0]:.2f}  final descent {d['final_descent']:.0%}")
    shifts = variant_shifts()
    print("\nvariants (pitch/tempo):")
    for s in shifts:
        print(f"   {s['id']} {s['family']:16s} {s['variant']:22s} shift {s['semitones']:+.1f} st  tempo x{s['tempo_ratio']:.2f}")
    json.dump({"groups": g, "variant_shifts": shifts}, (REPO / "analysis" / "summary.json").open("w", encoding="utf-8"),
              ensure_ascii=False, indent=1, default=lambda o: dict(o) if isinstance(o, collections.Counter) else str(o))


if __name__ == "__main__":
    main()
