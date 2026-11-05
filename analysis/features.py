"""Musical features of every piece in analysis/catalog.csv.

For each MIDI: key and mode (Krumhansl-Kessler), how the 12 scale degrees are used, the melody
(skyline of the top voice: range, intervals, first/last degree, climax), chords per beat
(template matching + Viterbi smoothing, as Roman numerals), texture (polyphony, register,
block vs. linear onsets) and rhythm (where melody onsets fall in the beat).

The 181 transcriptions have no tempo, so their beat grid is tracked from the MP3 audio.
Hand-made MIDIs use their own tempo map. Writes analysis/features.csv and analysis/chords.csv.

    python analysis/features.py
"""

import csv
from pathlib import Path

import librosa
import numpy as np
import pretty_midi

REPO = Path(__file__).resolve().parent.parent
NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
KK_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
KK_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
ROMAN = ["I", "bII", "II", "bIII", "III", "IV", "#IV", "V", "bVI", "VI", "bVII", "VII"]
QUALITIES = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11),
             "m7": (0, 3, 7, 10), "sus4": (0, 5, 7), "dim": (0, 3, 6), "add9": (0, 2, 4, 7)}
MINOR_QUALITIES = {"m", "m7", "dim"}


# ----------------------------------------------------------------------------- notes, key
def load_notes(path: Path) -> tuple[pretty_midi.PrettyMIDI, list[tuple]]:
    pm = pretty_midi.PrettyMIDI(str(path))
    notes = sorted((n.start, n.end, n.pitch, n.velocity, inst.program)
                   for inst in pm.instruments if not inst.is_drum for n in inst.notes)
    return pm, notes


def pc_histogram(notes, cap: float = 1.0) -> np.ndarray:
    """Pitch classes weighted by (capped) duration and velocity."""
    h = np.zeros(12)
    for s, e, p, v, _ in notes:
        h[p % 12] += min(e - s, cap) * v / 100
    return h


def find_key(h: np.ndarray) -> tuple[int, str, float, float]:
    """(tonic pc, 'major'/'minor', correlation, margin over the runner-up)."""
    scores = sorted(((np.corrcoef(np.roll(prof, t), h)[0, 1], t, mode)
                     for t in range(12) for mode, prof in (("major", KK_MAJOR), ("minor", KK_MINOR))),
                    reverse=True)
    (r, t, mode), (r2, *_) = scores[0], scores[1]
    return t, mode, float(r), float(r - r2)


# ----------------------------------------------------------------------------- beat grid
def audio_beats(mp3: Path) -> tuple[float, np.ndarray, np.ndarray]:
    """Tempo and a beat grid from the recording. These chimes are machine-played at a steady
    tempo, so the tracked beats are fitted with a straight line and the grid is extended over
    the whole recording (the tracker alone drops beats where onsets get weak). The tempo is
    folded into 80-160 BPM, since half/double tempo is ambiguous anyway."""
    y, sr = librosa.load(str(mp3), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time", start_bpm=120, trim=False)
    tempo = float(np.atleast_1d(tempo)[0])
    if len(beats) >= 4:
        period, offset = np.polyfit(np.arange(len(beats)), beats, 1)
    else:
        period, offset = 60 / tempo, (beats[0] if len(beats) else 0.0)
    while 60 / period > 160:
        period *= 2
    while 60 / period < 80:
        period /= 2
    first = offset - period * np.floor(offset / period)
    grid = np.arange(first, len(y) / sr + period, period)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr).sum(axis=1)
    return 60 / period, grid, chroma


def midi_beats(pm: pretty_midi.PrettyMIDI, first_onset: float) -> tuple[float, np.ndarray]:
    times, tempi = pm.get_tempo_changes()
    tempo = float(tempi[max(0, np.searchsorted(times, first_onset, side="right") - 1)])
    return tempo, np.asarray(pm.get_beats())


# ----------------------------------------------------------------------------- melody
def skyline(notes, cluster: float = 0.035, min_dur: float = 0.05) -> list[tuple]:
    """Top voice: the highest note of each onset group, unless it starts well below a melody
    note that is still ringing (then it is accompaniment). Isolated octave spikes are folded
    back, since the transcriptions make octave errors."""
    groups, i = [], 0
    while i < len(notes):
        j = i
        while j < len(notes) and notes[j][0] - notes[i][0] <= cluster:
            j += 1
        groups.append(notes[i:j])
        i = j
    melody = []
    for g in groups:
        top = max(g, key=lambda n: n[2])
        if top[1] - top[0] < min_dur:
            continue
        if melody:
            last = melody[-1]
            ringing = top[0] < min(last[1], last[0] + 0.35)
            if ringing and top[2] < last[2] - 4:
                continue
        melody.append(top)
    pitches = [n[2] for n in melody]
    for k in range(1, len(pitches) - 1):
        a, b, c = pitches[k - 1], pitches[k], pitches[k + 1]
        if (b - a >= 10 and b - c >= 10) or (a - b >= 10 and c - b >= 10):
            pitches[k] = b - 12 if b > a else b + 12
    return [(n[0], n[1], p, n[3], n[4]) for n, p in zip(melody, pitches)]


def melody_features(mel, tonic: int, duration: float) -> dict:
    if len(mel) < 3:
        return {}
    p = np.array([n[2] for n in mel])
    on = np.array([n[0] for n in mel])
    d = np.diff(p)[np.diff(on) < 1.0]  # skip phrase gaps
    a = np.abs(d)
    k = int(np.argmax(p))
    return {
        "mel_notes": len(mel), "mel_median": pretty_midi.note_number_to_name(int(np.median(p))),
        "mel_median_pitch": float(np.median(p)), "mel_range": int(np.percentile(p, 95) - np.percentile(p, 5)),
        "mel_repeat": float(np.mean(a == 0)), "mel_step": float(np.mean((a >= 1) & (a <= 2))),
        "mel_third": float(np.mean((a >= 3) & (a <= 4))), "mel_leap": float(np.mean(a >= 5)),
        "mel_up": float(np.mean(d > 0)), "mel_down": float(np.mean(d < 0)),
        "mel_first_deg": (int(p[0]) - tonic) % 12, "mel_last_deg": (int(p[-1]) - tonic) % 12,
        "mel_climax_pos": float((on[k] - on[0]) / max(duration, 1e-6)),
        "mel_final_descent": bool(len(p) >= 3 and p[-1] < p[-2] <= p[-3]),
    }


# ----------------------------------------------------------------------------- chords
def chord_templates() -> tuple[list[tuple[int, str]], np.ndarray]:
    labels, vectors = [], []
    for root in range(12):
        for q, pcs in QUALITIES.items():
            v = np.zeros(12)
            v[[(root + x) % 12 for x in pcs]] = 1
            v[root] += 0.5  # the root weighs a little more
            labels.append((root, q))
            vectors.append(v / np.linalg.norm(v))
    return labels, np.array(vectors)


LABELS, TEMPLATES = chord_templates()


def beat_chords(notes, beats: np.ndarray, start: float, end: float) -> list[tuple]:
    """One chord per beat inside [start, end], smoothed with a change penalty (Viterbi)."""
    edges = [b for b in beats if start - 0.05 <= b <= end]
    if len(edges) < 2:
        return []
    scores, bass_pcs = [], []
    for t0, t1 in zip(edges[:-1], edges[1:]):
        v = np.zeros(12)
        lowest, low_w = None, 0.0
        for s, e, p, vel, _ in notes:
            ov = min(e, t1) - max(s, t0)
            if ov > 0:
                v[p % 12] += ov * vel / 100
                if ov > 0.3 * (t1 - t0) and (lowest is None or p < lowest):
                    lowest, low_w = p, ov
        if v.sum() < 1e-6:
            scores.append(None)
            bass_pcs.append(None)
            continue
        v = v / np.linalg.norm(v)
        s = TEMPLATES @ v
        if lowest is not None:  # the bass note favours chords built on it
            s = s + 0.06 * np.array([root == lowest % 12 for root, _ in LABELS])
        scores.append(s)
        bass_pcs.append(lowest)
    n = len(LABELS)
    prev, back = np.zeros(n), []
    for s in scores:
        if s is None:
            back.append(None)
            continue
        stay = prev
        move = prev.max() - 0.2  # a chord change has to earn its keep: passing notes should not flip it
        choice = np.where(stay >= move, np.arange(n), int(prev.argmax()))
        prev = np.maximum(stay, move) + s
        back.append(choice)
    state = int(prev.argmax())
    path = []
    for choice in reversed(back):
        if choice is None:
            path.append(None)
            continue
        path.append(state)
        state = int(choice[state])
    path.reverse()
    return [(t0, t1, LABELS[k] if k is not None else None) for (t0, t1), k in zip(zip(edges[:-1], edges[1:]), path)]


def roman(label: tuple[int, str], tonic: int) -> str:
    root, q = label
    numeral = ROMAN[(root - tonic) % 12]
    if q in MINOR_QUALITIES:
        numeral = numeral.lower()
    return numeral + {"": "", "m": "", "dim": "°"}.get(q, q.replace("m7", "7"))


def chord_features(chords, tonic: int) -> tuple[dict, str]:
    seq = [(roman(lab, tonic), lab) for _, _, lab in chords if lab is not None]
    if not seq:
        return {}, ""
    merged = []
    for r, lab in seq:
        if merged and merged[-1][0] == r:
            merged[-1][1] += 1
        else:
            merged.append([r, 1, lab])
    total = len(seq)
    q = [lab[1] for _, lab in seq]
    core = [m[0].rstrip("7°").replace("maj", "").replace("sus4", "").replace("add9", "") for m in merged]
    text = " ".join(f"{r}({b})" for r, b, _ in merged)

    def has(*pattern):
        return any(tuple(core[i:i + len(pattern)]) == pattern for i in range(len(core) - len(pattern) + 1))

    feats = {
        "chords": len(merged), "beats_per_chord": total / len(merged),
        "share_7th": float(np.mean([x in ("7", "maj7", "m7") for x in q])),
        "share_sus_add": float(np.mean([x in ("sus4", "add9") for x in q])),
        "share_minor_chords": float(np.mean([x in MINOR_QUALITIES for x in q])),
        "final_chord": merged[-1][0], "penult_chord": merged[-2][0] if len(merged) > 1 else "",
        "prog_IV_V_I": has("IV", "V", "I"), "prog_ii_V_I": has("ii", "V", "I") or has("II", "V", "I"),
        "prog_royal_road": has("IV", "V", "iii", "vi"), "prog_I_V_vi_IV": has("I", "V", "vi", "IV"),
        "prog_secondary_dom": any(m[0] in ("II", "II7", "III", "III7", "VI", "VI7", "VII", "VII7") for m in merged),
        "prog_borrowed": any(m[0].startswith(("iv", "bVII", "bVI", "bIII")) for m in merged),
    }
    for numeral in ("I", "ii", "iii", "IV", "V", "vi"):
        feats[f"share_{numeral}"] = float(np.mean([c == numeral for c in
                                                   [r.rstrip("7°").replace("maj", "").replace("sus4", "").replace("add9", "")
                                                    for r, _ in seq]]))
    return feats, text


# ----------------------------------------------------------------------------- texture, rhythm
def texture_features(notes, start: float, end: float) -> dict:
    grid = np.arange(start, end, 0.05)
    capped = [(s, min(e, s + 1.5)) for s, e, *_ in notes]
    poly = np.array([sum(s <= t < e for s, e in capped) for t in grid]) if len(grid) else np.zeros(1)
    onsets, i = [], 0
    while i < len(notes):
        j = i
        while j < len(notes) and notes[j][0] - notes[i][0] <= 0.035:
            j += 1
        onsets.append(j - i)
        i = j
    pitches = np.array([n[2] for n in notes])
    span = max(end - start, 1e-6)
    return {
        "poly_mean": float(poly.mean()), "poly_p90": float(np.percentile(poly, 90)),
        "notes_per_s": len(notes) / span, "onsets_per_s": len(onsets) / span,
        "share_block_onsets": float(np.mean(np.array(onsets) >= 2)),
        "share_low_notes": float(np.mean(pitches < 48)), "share_high_notes": float(np.mean(pitches >= 72)),
        "lowest_p5": float(np.percentile(pitches, 5)), "highest_p95": float(np.percentile(pitches, 95)),
    }


def rhythm_features(mel, beats: np.ndarray) -> dict:
    if len(beats) < 3 or len(mel) < 3:
        return {}
    phases = []
    for s, *_ in mel:
        b = np.searchsorted(beats, s, side="right") - 1
        if 0 <= b < len(beats) - 1:
            phases.append((s - beats[b]) / (beats[b + 1] - beats[b]))
    ph = np.array(phases)
    if not len(ph):
        return {}
    on = np.array([n[0] for n in mel])
    ioi_beats = np.diff(on) / np.median(np.diff(beats))
    return {
        "on_beat": float(np.mean((ph < 0.12) | (ph > 0.88))),
        "on_eighth": float(np.mean(np.abs(ph - 0.5) < 0.12)),
        "on_triplet": float(np.mean((np.abs(ph - 1 / 3) < 0.05) | (np.abs(ph - 2 / 3) < 0.05))),
        "on_sixteenth": float(np.mean((np.abs(ph - 0.25) < 0.05) | (np.abs(ph - 0.75) < 0.05))),
        "mel_ioi_beats": float(np.median(ioi_beats[ioi_beats < 4])) if np.any(ioi_beats < 4) else float("nan"),
    }


# ----------------------------------------------------------------------------- per piece
def analyse(row: dict) -> tuple[dict, str]:
    pm, notes = load_notes(REPO / row["midi"])
    if not notes:
        return {}, ""
    start, end = notes[0][0], max(min(e, s + 2.0) for s, e, *_ in notes)
    h = pc_histogram(notes)
    tonic, mode, corr, margin = find_key(h)
    out = {"key": f"{NAMES[tonic]} {mode}", "tonic": tonic, "mode": mode,
           "key_corr": corr, "key_margin": margin, "span_s": end - start}
    rel = np.roll(h / h.sum(), -tonic)  # degree 0 = tonic
    for deg in range(12):
        out[f"deg_{deg}"] = float(rel[deg])
    major_pent, nat_minor = (0, 2, 4, 7, 9), (0, 2, 3, 5, 7, 8, 10)
    out["share_pentatonic"] = float(rel[list(major_pent)].sum()) if mode == "major" else float(rel[[0, 3, 5, 7, 10]].sum())
    out["share_4_7"] = float(rel[5] + rel[11]) if mode == "major" else float(rel[2] + rel[8])
    out["share_chromatic"] = float(rel[[1, 3, 6, 8, 10]].sum()) if mode == "major" else float(
        sum(rel[d] for d in range(12) if d not in nat_minor and d != 11))
    if row["audio"]:
        tempo, beats, chroma = audio_beats(REPO / row["audio"])
        a_tonic, a_mode, *_ = find_key(chroma)
        out["audio_key"] = f"{NAMES[a_tonic]} {a_mode}"
        out["key_agrees_audio"] = (a_tonic, a_mode) == (tonic, mode)
    else:
        tempo, beats = midi_beats(pm, start)
    out["tempo_bpm"] = tempo
    out["beats"] = int(np.sum((beats >= start - 0.05) & (beats <= end)))
    mel = skyline(notes)
    out.update(melody_features(mel, tonic, end - start))
    chord_feats, chord_text = chord_features(beat_chords(notes, beats, start, end), tonic)
    out.update(chord_feats)
    out.update(texture_features(notes, start, end))
    out.update(rhythm_features(mel, beats))
    out["tracks"] = sum(1 for i in pm.instruments if i.notes and not i.is_drum)
    out["programs"] = " ".join(sorted({pretty_midi.program_to_instrument_name(i.program)
                                       for i in pm.instruments if i.notes and not i.is_drum}))
    return out, chord_text


def main() -> None:
    catalog = list(csv.DictReader((REPO / "analysis" / "catalog.csv").open(encoding="utf-8-sig")))
    rows, chord_rows = [], []
    for k, row in enumerate(catalog, 1):
        feats, chords = analyse(row)
        rows.append({**row, **feats})
        chord_rows.append({"id": row["id"], "family": row["family"], "key": feats.get("key", ""), "chords": chords})
        if k % 20 == 0:
            print(f"  {k}/{len(catalog)}")
    fields = list(dict.fromkeys(f for r in rows for f in r))
    with (REPO / "analysis" / "features.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.4g}" if isinstance(v, float) else v) for k, v in r.items()})
    with (REPO / "analysis" / "chords.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["id", "family", "key", "chords"])
        w.writeheader()
        w.writerows(chord_rows)
    print(f"{len(rows)} pieces -> analysis/features.csv, analysis/chords.csv")


if __name__ == "__main__":
    main()
