# analysis：发车铃 MIDI 分析

这个文件夹里是《[发车铃分析与创作指南](../docs/发车铃分析与创作指南.md)》用到的全部数据和脚本。

## 文件

| 文件 | 内容 |
|---|---|
| [`catalog.py`](catalog.py) → [`catalog.csv`](catalog.csv) | 192 首的分类表。181 个 MP3 和 11 个手工 MIDI，每首标注用途（发车铃/车内铃）、来源（原创/改编/不确定）、所属系列或原曲类型、旋律族（同一旋律的变体合为一族）、变体类型和可信度。 |
| [`features.py`](features.py) → [`features.csv`](features.csv)、[`chords.csv`](chords.csv) | 每首的音乐特征，以及按拍识别的和弦序列（罗马数字）。特征包括：调与调式、12 个音级的时值占比、旋律（最高声部）的音区、音域、音程、首尾音级，和弦与终止，织体（同时发声数、音区、和弦式/线条式起音），节奏位置。 |
| [`summary.py`](summary.py) → [`summary.json`](summary.json) | 按组统计：原创、改编、各系列、车内铃。每个旋律族只取一个版本。另外估算变体相对「基准版」的移调量和速度比。只有和标签相符的几例可信（如 JR-SH1 高音ver +1.0 半音），其余变体的标签不是相对基准版说的。 |
| [`charts.py`](charts.py) → `fig_length.png`、`fig_degrees.png` | 指南里的两张图。 |

## 运行

需要 Python 3.10 以上：

```bash
pip install pretty_midi librosa numpy matplotlib
```

```bash
python analysis/catalog.py && python analysis/features.py && python analysis/summary.py && python analysis/charts.py
```

## 方法和可信度

- **转写 MIDI 的准确率**：181 首的 MIDI 是 `harmonica_midi/` 里的自动转写，音符层面约 3/4 正确，常见错误是八度错和多出来的泛音。
  - 调、速度、长度、音级分布、和弦大框架、最后的和弦都比较稳。用手工 MIDI 对照过：farewell、SF22-29 的调、速度、长度和终止和弦都一致。
  - 旋律音程统计不稳：自动转写的「最高声部」会混进伴奏和泛音。所以指南里的旋律音程数字只来自 7 个手工 MIDI 的旋律声部。
- **调的识别**：用 Krumhansl-Kessler 调性轮廓。按 MIDI 识别和按音频识别的结果，在 181 首里有 69% 一致，不一致的主要是关系大小调混淆。
- **速度**：从 MP3 跟踪节拍，再按匀速拟合成网格（这些铃声都是机器演奏的，速度恒定）。速度统一折算到 80–160 BPM，所以「120」和「60」这类倍速差别不作区分。
- **分类**：主要依据曲名，加上能查证的系列信息。查不到出处的标为「不确定」，不参与原创和改编的对比。
