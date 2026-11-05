"""Transcribe the chime MP3s in this repo to MIDI with Harmonica.

Harmonica (arXiv:2609.04640) is an instrument-agnostic transcription model; the
weights used here come from `harmonica-amt`, an unofficial reproduction that
bundles them. By default this script averages the activations of the nano and
small models and decodes them at onset/frame thresholds 0.15/0.3: on our chime
tests that beat every single size and Basic Pitch, and unlike nano alone it does
not drop out on bell-heavy recordings (see harmonica_midi/README.md).

Setup (Python 3.12+, CPU only is fine):
    uv venv --python 3.12 .venv-harmonica
    source .venv-harmonica/bin/activate
    uv pip install --index-strategy unsafe-best-match \
        --extra-index-url https://download.pytorch.org/whl/cpu harmonica-amt

Usage:
    python tools/transcribe_harmonica.py                     # every MP3 -> harmonica_midi/
    python tools/transcribe_harmonica.py "第一弹 001-026"      # one folder
    python tools/transcribe_harmonica.py --model medium x.mp3  # one size, its own thresholds
"""

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ENSEMBLE_THRESHOLDS = (0.15, 0.3)  # onset, frame: chosen on the chime tests in harmonica_midi/README.md


def find_mp3s(inputs: list[str]) -> list[Path]:
    """The MP3 files named, or found under the folders named (default: the whole repo)."""
    roots = [Path(p).resolve() for p in inputs] if inputs else [REPO]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():  # hidden folders (.git, .venv-harmonica, ...) are skipped
            files += sorted(
                p for p in root.rglob("*")
                if p.suffix.lower() == ".mp3" and not any(part.startswith(".") for part in p.relative_to(root).parts)
            )
        elif root.suffix.lower() == ".mp3":
            files.append(root)
        else:
            sys.exit(f"not an MP3 file or folder: {root}")
    return files


def output_path(mp3: Path, out_dir: Path) -> Path:
    """Mirror the MP3's place in the repo under out_dir, e.g. 第一弹 001-026/001 JR-SH1.mid."""
    try:
        relative = mp3.relative_to(REPO)
    except ValueError:  # a file outside the repo keeps only its name
        relative = Path(mp3.name)
    return out_dir / relative.with_suffix(".mid")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", help="MP3 files or folders (default: every MP3 in the repo)")
    parser.add_argument("--model", default="nano+small",
                        help="a size (nano, small, medium, large, x-large) or a checkpoint path; "
                             "join several with '+' to average their activations (default: nano+small)")
    parser.add_argument("--onset-threshold", type=float,
                        help=f"default: {ENSEMBLE_THRESHOLDS[0]} for several models, the checkpoint's own for one")
    parser.add_argument("--frame-threshold", type=float,
                        help=f"default: {ENSEMBLE_THRESHOLDS[1]} for several models, the checkpoint's own for one")
    parser.add_argument("--out", default=str(REPO / "harmonica_midi"), help="output folder (default: harmonica_midi/)")
    parser.add_argument("--overwrite", action="store_true", help="redo files whose MIDI already exists")
    args = parser.parse_args()
    files = find_mp3s(args.inputs)  # before loading models, so a bad path fails fast

    # imported late so --help works without the package
    from harmonica import Harmonica
    from harmonica.decoding import decode

    models = [Harmonica(name) for name in args.model.split("+")]  # GPU if there is one, else CPU
    default_onset, default_frame = (
        ENSEMBLE_THRESHOLDS if len(models) > 1 else (models[0].onset_threshold, models[0].frame_threshold)
    )
    onset_threshold = default_onset if args.onset_threshold is None else args.onset_threshold
    frame_threshold = default_frame if args.frame_threshold is None else args.frame_threshold

    out_dir = Path(args.out).resolve()
    print(f"Harmonica {args.model}: onset/frame thresholds {onset_threshold}/{frame_threshold}, {len(files)} file(s)")

    start, done = time.time(), 0
    for mp3 in files:
        target = output_path(mp3, out_dir)
        if target.exists() and not args.overwrite:
            continue
        runs = [model.activations(mp3) for model in models]
        heads = set.intersection(*(set(run) for run in runs))
        mean = {head: sum(run[head] for run in runs) / len(runs) for head in heads}
        notes = decode(mean["onset"], mean["sustain"], models[0].frames_per_second,
                       onset_threshold, frame_threshold, mean.get("velocity"))
        notes.save_midi(target)  # one piano track at 120 BPM
        done += 1
        print(f"  {len(notes.pitches):4d} notes  {target.relative_to(out_dir)}")
    print(f"{done} transcribed in {time.time() - start:.1f}s -> {out_dir}")


if __name__ == "__main__":
    main()
