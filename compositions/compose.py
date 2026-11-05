"""The practice pieces for compositions/README.md: four departure melodies (one of them in two
versions) and one in-car chime. Every note is written out below; the script only turns beats
into MIDI, checks each piece against the targets from the analysis, and can render previews.

    python compositions/compose.py            # writes compositions/*.mid and prints the check
    python compositions/compose.py --render   # also writes compositions/previews/*.mp3
                                              # (needs fluidsynth, the FluidR3_GM soundfont, ffmpeg)
"""

import argparse
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pretty_midi

HERE = Path(__file__).resolve().parent
SOUNDFONT = "/usr/share/sounds/sf2/FluidR3_GM.sf2"

# GM programs used
CELESTA, GLOCKENSPIEL, MUSIC_BOX, VIBRAPHONE, MARIMBA, TUBULAR_BELLS = 8, 9, 10, 11, 12, 14
EPIANO, HARP, STRINGS, STRINGS_2, PIZZICATO, FINGER_BASS = 4, 46, 48, 49, 45, 33
PAD_NEW_AGE, KOTO = 88, 107


@dataclass
class Piece:
    title: str
    bpm: float
    beats: float  # length of one pass in beats (a loop piece repeats after this)
    tracks: dict = field(default_factory=dict)

    def track(self, name: str, program: int) -> list:
        self.tracks[name] = (program, [])
        return self.tracks[name][1]


def line(track: list, start: float, items, vel: int = 90) -> float:
    """Notes one after another: items are (beats, note) with note=None for a rest."""
    t = start
    for dur, note in items:
        if note is not None:
            track.append((t, dur, pretty_midi.note_name_to_number(note), vel))
        t += dur
    return t


def dotted(track: list, start: float, pairs, vel: int = 90) -> None:
    """One beat per pair, as a dotted eighth + sixteenth ('タッカ'); a single note fills its beats."""
    t = start
    for item in pairs:
        if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str):
            line(track, t, [(0.75, item[0]), (0.25, item[1])], vel)
            t += 1
        else:
            dur, note = item
            line(track, t, [(dur, note)], vel)
            t += dur


def chord(track: list, start: float, dur: float, notes: str, vel: int = 60, roll: float = 0.0) -> None:
    """Simultaneous notes ('A3 D4 F#4'); roll > 0 spreads them upwards like a harp or strum."""
    for k, name in enumerate(notes.split()):
        track.append((start + k * roll, dur - k * roll, pretty_midi.note_name_to_number(name), vel))


def broken(track: list, start: float, beats: float, notes: str, vel: int = 60, step: float = 0.5) -> None:
    """Broken chord: cycle the notes (low, mid, high, mid, ...) in even steps."""
    names = notes.split()
    order = names + names[-2:0:-1]
    t, k = start, 0
    while t < start + beats - 1e-6:
        track.append((t, step, pretty_midi.note_name_to_number(order[k % len(order)]), vel))
        t += step
        k += 1


# ------------------------------------------------------------------------------- 01 晨光
def morning_light() -> Piece:
    """Standard original: D major, 4 bars, motif -> sequence -> climax -> V7 arpeggio down to 1."""
    p = Piece("01_晨光", bpm=126, beats=16)
    melody = p.track("Melody Celesta", CELESTA)
    line(melody, 0, [(1.5, "A5"), (0.5, "F#5"), (0.5, "D5"), (0.5, "E5"), (1, "F#5"),          # I: 5. 3 1 2 3
                     (1.5, "B5"), (0.5, "G5"), (0.5, "E5"), (0.5, "F#5"), (1, "G5"),           # ii V7: the motif a step up
                     (0.5, "D6"), (0.5, "E6"), (1, "F#6"), (0.5, "E6"), (0.5, "D6"), (0.5, "B5"), (0.5, "G5"),  # vi IV: climax
                     (0.5, "A5"), (0.5, "G5"), (0.5, "E5"), (0.5, "C#5"), (2, "D5")], vel=100)  # V7 arpeggio -> 1
    sparkle = p.track("Double Glockenspiel", GLOCKENSPIEL)
    sparkle.extend((t, d, n, 50) for t, d, n, _ in melody)
    harmony = [(0, 4, "D4 F#4 A4", "A3 D4 F#4", "D3", "A2"), (4, 2, "E4 G4 B4", "B3 E4 G4", "E3", None),
               (6, 2, "C#4 E4 G4", "A3 C#4 G4", "A2", None), (8, 2, "D4 F#4 B4", "B3 D4 F#4", "B2", None),
               (10, 2, "D4 G4 B4", "B3 D4 G4", "G2", None), (12, 2, "C#4 E4 G4", "A3 C#4 G4", "A2", None)]
    arp, pad, bass = p.track("Broken chords Marimba", MARIMBA), p.track("Pad Strings", STRINGS), p.track("Bass Pizzicato", PIZZICATO)
    for start, beats, arp_notes, pad_notes, root, fifth in harmony:
        broken(arp, start, beats, arp_notes, vel=58)
        chord(pad, start, beats, pad_notes, vel=46)
        line(bass, start, [(1, root)], vel=80)
        if fifth:
            line(bass, start + 2, [(1, fifth)], vel=72)
    chord(pad, 14, 3.5, "A3 D4 F#4", vel=46)
    line(bass, 14, [(2.5, "D3")], vel=80)
    chord(p.track("Ending roll Harp", HARP), 14, 3.5, "D5 F#5 A5 D6", vel=72, roll=0.06)
    return p


# ------------------------------------------------------------------------------- 02 港风
def harbor_breeze() -> Piece:
    """Loop type: F major, IV-iii-ii-V7sus4-V7 with maj7/9 colours; ends open so it flows back to bar 1."""
    p = Piece("02_港风_循环版", bpm=100, beats=16)
    melody = p.track("Melody Vibraphone", VIBRAPHONE)
    line(melody, 0, [(0.5, None), (0.5, "C6"), (0.5, "A5"), (1, "F5"), (0.5, "G5"), (1, "A5"),      # Bbmaj7: 9 7 5 6 7
                     (0.5, None), (0.5, "G5"), (0.5, "E5"), (1, "C5"), (0.5, "D5"), (1, "E5"),       # Am7: same rhythm, lower
                     (0.5, "D6"), (0.5, "C6"), (0.5, "Bb5"), (0.5, "A5"), (1.5, "Bb5"), (0.5, None),  # Gm7: the high point
                     (0.5, "G5"), (0.5, "A5"), (1, "F5"), (1, "E5"), (0.5, "G5"), (0.5, None)], vel=96)  # C7sus4 -> C7
    keys, bass = p.track("Chords E.Piano", EPIANO), p.track("Bass Finger", FINGER_BASS)
    bars = [(0, "D4 F4 A4 C5", "Bb2", "F3"), (4, "E4 G4 A4 C5", "A2", "E3"), (8, "F4 A4 Bb4 D5", "G2", "D3")]
    for start, voicing, root, fifth in bars:
        for off, dur in ((0, 1.0), (1.5, 1.0), (3.5, 0.5)):  # anticipations on the 'and' of 2 and 4
            chord(keys, start + off, dur, voicing, vel=60)
        line(bass, start, [(1.5, root), (1, fifth), (1, root), (0.5, None)], vel=72)
    chord(keys, 12, 1.0, "F4 G4 Bb4 C5", vel=60)   # C7sus4
    chord(keys, 13.5, 0.5, "F4 G4 Bb4 C5", vel=56)
    chord(keys, 14, 1.0, "E4 G4 Bb4 C5", vel=62)   # C7: the sus4 resolves
    chord(keys, 15.5, 0.5, "E4 G4 Bb4 C5", vel=56)
    line(bass, 12, [(1.5, "C3"), (0.5, "G2"), (1.5, "C3"), (0.5, "B2")], vel=72)  # B2 slides into bar 1's Bb2
    return p


def harbor_breeze_ending() -> Piece:
    """Two-beat tag played after the last loop: Fmaj9, the resolution the loop leaves open."""
    p = Piece("02_港风_结尾", bpm=100, beats=4)
    line(p.track("Melody Vibraphone", VIBRAPHONE), 0, [(3, "F5")], vel=90)
    chord(p.track("Chords E.Piano", EPIANO), 0, 3, "E4 G4 A4 C5", vel=60, roll=0.05)
    line(p.track("Bass Finger", FINGER_BASS), 0, [(3, "F2")], vel=72)
    return p


# ------------------------------------------------------------------------------- 03 里山
def satoyama() -> Piece:
    """Yonanuki (no 4th, no 7th) G major pentatonic, open fifths instead of functional chords."""
    p = Piece("03_里山", bpm=96, beats=16)
    melody = p.track("Melody Koto", KOTO)
    line(melody, 0, [(1, "D5"), (0.5, "E5"), (0.5, "D5"), (1, "B4"), (0.5, "A4"), (0.5, "B4"),   # 5 6 5 3 2 3
                     (1, "G5"), (0.5, "E5"), (0.5, "D5"), (1.5, "E5"), (0.5, "D5"),             # 1' 6 5 6. 5
                     (0.5, "B4"), (0.5, "D5"), (1, "E5"), (1, "G5"), (1, "A5"),                 # rising to the peak 2'
                     (0.5, "G5"), (0.5, "E5"), (0.5, "D5"), (0.5, "B4"), (1, "A4"), (1, "G4")], vel=100)  # down to 1
    line(melody, 15.25, [(0.1, n) for n in ("A4", "B4", "D5", "E5")], vel=70)  # koto sweep up the pentatonic...
    line(melody, 15.65, [(2, "G5")], vel=82)                                   # ...landing on the high tonic
    harp, strings = p.track("Broken chords Harp", HARP), p.track("Open fifths Strings", STRINGS_2)
    fifths = [(0, 4, "G3 D4 G4", "G3 D4"), (4, 4, "E3 B3 G4", "E3 B3"), (8, 2, "A3 E4 A4", "A3 E4"),
              (10, 4, "D3 A3 D4", "D3 A3"), (14, 2, "G3 D4 G4", "G3 D4")]
    for start, beats, arp_notes, fifth in fifths:
        broken(harp, start, beats if start != 14 else 1, arp_notes, vel=54)
        chord(strings, start, beats + (2 if start == 14 else 0), fifth, vel=42)
    bell = p.track("Temple bell Tubular Bells", TUBULAR_BELLS)
    line(bell, 0, [(3, "G4")], vel=48)
    line(bell, 15, [(3, "G4")], vel=48)
    return p


# ------------------------------------------------------------------------------- 04 鉄道唱歌
TETSUDO_MELODY = [("C6", "C6"), ("C6", "D6"), ("E6", "E6"), ("E6", "D6"),   # 汽笛一声 新橋を
                  ("C6", "C6"), ("C6", "A5"), (2, "G5"),                    # はや我汽車は
                  ("A5", "A5"), ("G5", "A5"), ("C6", "C6"), ("E6", "E6"),   # 離れたり 愛宕の山に
                  ("D6", "D6"), ("E6", "D6"), (2, "C6")]                    # 入りのこる


def tetsudo_shoka() -> Piece:
    """Arrangement of 鉄道唱歌 (多梅稚, 1900, public domain): whole first verse, its dotted rhythm kept,
    off-beat 'train' chords over a root-fifth bass, rolled tonic and two bell strikes to close."""
    p = Piece("04_鉄道唱歌_发车版", bpm=132, beats=16)
    dotted(p.track("Melody Glockenspiel", GLOCKENSPIEL), 0, TETSUDO_MELODY, vel=92)
    box = p.track("Octave below Music Box", MUSIC_BOX)
    dotted(box, 0, TETSUDO_MELODY, vel=64)
    box[:] = [(t, d, n - 12, v) for t, d, n, v in box]
    harmony = [(0, 4, "E4 G4 C5", ["C3", "G2", "C3", "G2"]), (4, 2, "E4 A4 C5", ["A2", "E3"]),
               (6, 2, "D4 G4 B4", ["G2", "D3"]), (8, 2, "F4 A4 C5", ["F2", "C3"]), (10, 2, "E4 G4 C5", ["C3", "G2"]),
               (12, 2, "D4 F4 B4", ["G2", "D3"])]
    offbeat, bass = p.track("Offbeat chords Marimba", MARIMBA), p.track("Bass Pizzicato", PIZZICATO)
    for start, beats, voicing, roots in harmony:
        for b in range(int(beats)):
            chord(offbeat, start + b + 0.5, 0.3, voicing, vel=56)  # ta-TAN ta-TAN: the wheels
        line(bass, start, [(1, r) for r in roots], vel=78)
    line(bass, 14, [(2.5, "C3")], vel=80)
    chord(p.track("Ending roll Harp", HARP), 14, 3.0, "C5 E5 G5 C6", vel=70, roll=0.06)
    bell = p.track("Ending bell Glockenspiel", GLOCKENSPIEL)
    line(bell, 15, [(0.5, "G6"), (1.5, "C7")], vel=58)  # two strikes: the end flag
    return p


def transposed(piece: Piece, title: str, semitones: int, tempo_scale: float) -> Piece:
    """Platform version of the same melody: shifted key and tempo, everything else kept."""
    p = Piece(title, bpm=piece.bpm * tempo_scale, beats=piece.beats)
    for name, (program, notes) in piece.tracks.items():
        p.tracks[name] = (program, [(t, d, n + semitones, v) for t, d, n, v in notes])
    return p


# ------------------------------------------------------------------------------- 05 到站
def arrival_chime() -> Piece:
    """In-car chime: 5-1-3 | 2-7-1, one shot, closes firmly on the tonic."""
    p = Piece("05_到站_车内铃", bpm=92, beats=6)
    melody = p.track("Melody Vibraphone", VIBRAPHONE)
    line(melody, 0, [(1, "C6"), (1, "F6"), (1, "A6"), (0.5, "G6"), (0.5, "E6"), (2, "F6")], vel=92)
    double = p.track("Double Celesta", CELESTA)
    double.extend((t, d, n, 58) for t, d, n, _ in melody)
    pad = p.track("Pad New Age", PAD_NEW_AGE)
    chord(pad, 0, 3, "F4 A4 C5", vel=48)
    chord(pad, 3, 1, "E4 G4 Bb4", vel=48)
    chord(pad, 4, 2.5, "F4 A4 C5", vel=48)
    chord(p.track("Ending roll Harp", HARP), 4, 2.5, "F4 A4 C5 F5", vel=60, roll=0.07)
    return p


# ------------------------------------------------------------------------------- output
def to_midi(piece: Piece, passes: int = 1, then: Piece | None = None) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI(initial_tempo=piece.bpm)
    pm.time_signature_changes.append(pretty_midi.TimeSignature(4, 4, 0))
    spb = 60.0 / piece.bpm
    parts = [(piece, k * piece.beats) for k in range(passes)] + ([(then, passes * piece.beats)] if then else [])
    instruments = {}
    for part, offset in parts:
        for name, (program, notes) in part.tracks.items():
            inst = instruments.setdefault(name, pretty_midi.Instrument(program=program, name=name))
            for t, d, n, v in notes:
                inst.notes.append(pretty_midi.Note(velocity=v, pitch=n, start=(offset + t) * spb, end=(offset + t + d) * spb))
    pm.instruments = list(instruments.values())
    return pm


def render(pm: pretty_midi.PrettyMIDI, mp3: Path) -> None:
    mp3.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        mid, wav = Path(tmp) / "x.mid", Path(tmp) / "x.wav"
        pm.write(str(mid))
        subprocess.run(["fluidsynth", "-ni", "-q", "-g", "1.0", "-r", "44100", "-F", str(wav), SOUNDFONT, str(mid)],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-af", "silenceremove=stop_periods=1:stop_threshold=-60dB",
                        "-b:a", "192k", str(mp3)], check=True)


def check(pm: pretty_midi.PrettyMIDI) -> dict:
    """The analysis' own measurements, to compare with the targets in the guide."""
    sys.path.insert(0, str(HERE.parent / "analysis"))
    from features import beat_chords, chord_features, find_key, melody_features, pc_histogram, skyline, NAMES
    notes = sorted((n.start, n.end, n.pitch, n.velocity, i.program) for i in pm.instruments for n in i.notes)
    start, end = notes[0][0], max(e for _, e, *_ in notes)
    h = pc_histogram(notes)
    tonic, mode, *_ = find_key(h)
    rel = np.roll(h / h.sum(), -tonic)
    lead = [i for i in pm.instruments if i.name.startswith("Melody ")][0]
    mel = skyline(sorted((n.start, n.end, n.pitch, n.velocity, lead.program) for n in lead.notes))
    m = melody_features(mel, tonic, end - start)
    c, text = chord_features(beat_chords(notes, np.asarray(pm.get_beats()), start, end), tonic)
    return {"length_s": end - start, "key": f"{NAMES[tonic]} {mode}", "melody_median": m["mel_median"],
            "melody_range": m["mel_range"], "last_degree": m["mel_last_deg"], "final_chord": c.get("final_chord", ""),
            "share_4_7": rel[5] + rel[11], "lowest": pretty_midi.note_number_to_name(min(n[2] for n in notes)),
            "chords": text}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--render", action="store_true", help="also render MP3 previews with FluidSynth")
    args = parser.parse_args()
    tetsudo = tetsudo_shoka()
    pieces = [morning_light(), harbor_breeze(), satoyama(), tetsudo,
              transposed(tetsudo, "04b_鉄道唱歌_2番线版", semitones=2, tempo_scale=1.05), arrival_chime()]
    for piece in pieces:
        pm = to_midi(piece)
        pm.write(str(HERE / f"{piece.title}.mid"))
        r = check(pm)
        print(f"{piece.title:18s} {r['length_s']:4.1f}s  {r['key']:9s} melody {r['melody_median']}/{r['melody_range']}st "
              f"last-degree {r['last_degree']:2d} final {r['final_chord']:6s} 4&7 {r['share_4_7']:.2f} lowest {r['lowest']:4s} | {r['chords']}")
        if args.render:
            if piece.title.startswith("02_"):  # a loop piece: preview two passes and the ending tag
                render(to_midi(piece, passes=2, then=harbor_breeze_ending()), HERE / "previews" / f"{piece.title}_两遍+结尾.mp3")
            else:
                render(pm, HERE / "previews" / f"{piece.title}.mp3")


if __name__ == "__main__":
    main()
