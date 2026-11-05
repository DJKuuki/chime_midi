"""Catalog of every piece in the repo: origin (original / arrangement / uncertain), source,
melody family (variants of one melody grouped), variant type, and how sure the label is.

Origins are judged from titles and what could be confirmed about each series; see the
`confidence` column. Writes analysis/catalog.csv.

    python analysis/catalog.py
"""

import csv
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Typos in the MP3 file names (look-alike kana/kanji) -> intended titles.
TYPO_FIXES = {
    "Aメ口": "Aメロ", "キッズステーシヨソ": "キッズステーション", "キリ夕ソポ物語": "キリタンポ物語",
    "メキシカソロック": "メキシカンロック", "シャソゼリゼ": "シャンゼリゼ", "テソポ": "テンポ",
    "力ーネーション畑": "カーネーション畑", "フエードアウト": "フェードアウト", "朝っゅ": "朝つゆ",
    "ドヴイッシー": "ドビュッシー", "プラツトホーム": "プラットホーム", "Gota dei Vient": "Gota del Vient",
    "遅くい": "遅い",
}

# --- originals ------------------------------------------------------------------------
SERIES = {
    "JR-SH": "JR-SH 系列（JR东日本较早期的发车铃）",
    "SF": "SF 系列（JR东日本，编号曲）",
    "TML": "东洋媒体链接（東洋メディアリンクス）西班牙语标题系列",
    "EN": "英文标题系列（出处未确认）",
    "JA": "日文标题曲库（出处未确认，多有 V1/V2 两版）",
}
TML_FAMILIES = {"Cielo Estrellado", "Gota del Vient", "Verde Rayo", "Water Crown"}
EN_FAMILIES = {"airy", "A Sea Bird", "blue daisy", "cappuccino", "dance on", "farewell", "mellow time",
               "mint flavor", "ML-24", "morning cloud", "Sea Green", "see you again", "summer night",
               "sunny islands", "sunrise", "twilight"}
JA_FAMILIES = {"朝つゆ", "朝の静けさ", "朝のプラットホーム", "あざみ野", "新たな季節", "新たな街", "淡い恋心",
               "美しき丘", "海辺の散歩", "丘の上の風車小屋", "小川のせせらぎ", "思い出の街", "カーネーション畑",
               "海岸通り", "風と共に", "風の贈り物", "風の吹くとき", "木々の目覚め", "キッズステーション",
               "希望の朝", "希望の鐘", "希望のまち", "銀杏並木", "九月の風", "くるみ遊び", "薫風の街", "公園通り",
               "公園の楓", "高原", "高原のつぶやき", "幸福の銀レール", "コーラルリーフ", "秋桜"}

# --- arrangements of existing music: family -> (source type, note) ----------------------
ARRANGED = {
    "It's a small world": ("影视/迪士尼歌曲", "1964 年迪士尼乐园歌曲"),
    "Zip-A-Dee-Doo-Dah": ("影视/迪士尼歌曲", "1946 年迪士尼电影歌曲"),
    "Open Happiness": ("广告歌", "可口可乐广告歌"),
    "Over": ("流行歌", "分 A メロ／間奏／サビ 三段截取"),
    "We Love Marines": ("体育应援歌", "千叶罗德海洋队应援歌"),
    "熱き星たちよ": ("体育应援歌", "横滨棒球队应援歌，分 A メロ／サビ 两段"),
    "ああ、わが戸田市": ("市歌/地方歌曲", "户田市市歌"),
    "上尾市歌": ("市歌/地方歌曲", "分 A メロ／サビ 两段"),
    "熊谷市歌": ("市歌/地方歌曲", "分 A メロ／サビ 两段"),
    "青い山脈": ("昭和歌谣", "1949"),
    "明日があるさ": ("昭和歌谣", "1963"),
    "明日は咲こう花咲こう": ("昭和歌谣", "1965"),
    "いつでも夢を": ("昭和歌谣", "1962"),
    "上を向いて歩こう": ("昭和歌谣", "1961"),
    "蒲田行進曲": ("昭和歌谣", "1929，电影主题歌"),
    "恋のメキシカンロック": ("昭和歌谣", "1967"),
    "公園の手品師": ("昭和歌谣", "1958"),
    "雨のステイション": ("流行歌", "1976"),
    "ウイスキーが、お好きでしょ": ("广告歌", "威士忌广告歌"),
    "オー・シャンゼリゼ": ("外国流行歌", "1969 法语歌曲"),
    "アマリリス": ("古典/器乐名曲", "法国旋律，常被称为「アマリリス」"),
    "楽興の時": ("古典/器乐名曲", "舒伯特"),
    "歓喜の歌": ("古典/器乐名曲", "贝多芬《欢乐颂》"),
    "きらきら星変奏曲": ("古典/器乐名曲", "莫扎特《小星星变奏曲》"),
    "汽車": ("唱歌/童谣", "1912 文部省唱歌"),
    "グリーン・グリーン": ("唱歌/童谣", "1960 年代美国民谣的日语版"),
    "阿波踊り": ("民谣", "德岛民谣"),
}

UNCERTAIN = {
    "HANDS ～大きな手から、小さな手へ～": "鸿巢市内三站各一版，可能是地方形象歌改编",
    "Keep On Rising": "出处未查到",
    "Vamos Ardija": "与大宫松鼠足球队有关，可能是应援歌改编",
    "AIZUその名の情熱": "可能是会津地方歌曲改编",
    "朝のドビュッシー": "可能是德彪西作品改编，也可能是原创",
    "おねぎのマーチ": "可能是深谷地方歌曲改编",
    "キリタンポ物語": "出处未查到",
    "雲を友として": "可能是歌谣曲改编",
    "恋の通勤列車": "出处未查到",
    "こころ": "带「前奏あり」版本，像是既有歌曲",
    "古都の舞妓さん": "出处未查到",
}

# Hand-made MIDIs at the repo root: (role, origin, family/source, confidence, note)
HANDMADE = {
    "farewell": ("发车铃", "原创", "farewell", "高", "对应 048 farewell"),
    "sf-22-29": ("发车铃", "原创", "SF22-29", "高", "对应 039/040 SF22-29"),
    "haru": ("发车铃", "原创", "SF12 春", "中", "与 037「春～NewVer～」编曲不同，可能是旧版"),
    "189-chime": ("车内铃", "原创", "189系车内铃", "中", "列车车内广播前的提示音"),
    "373-chime3": ("车内铃", "原创", "373系车内铃", "中", ""),
    "kiha85-chime2": ("车内铃", "原创", "キハ85车内铃", "中", ""),
    "kodama1": ("车内铃", "原创", "新干线こだま车内铃", "中", ""),
    "nozomi": ("车内铃", "原创", "新干线のぞみ车内铃", "中", ""),
    "tetsudoshoka": ("车内铃", "改编", "鉄道唱歌", "高", "1900 年唱歌"),
    "haikensu": ("车内铃", "改编", "ハイケンスのセレナーデ", "高", "海肯斯《小夜曲》，国铁特急车内铃"),
    "senronokanata": ("不确定", "不确定", "senronokanata", "低", "出处未查到"),
}


def fix_title(raw: str) -> str:
    for bad, good in TYPO_FIXES.items():
        raw = raw.replace(bad, good)
    return raw


def family_and_variant(title: str) -> tuple[str, str]:
    """Strip version markers: '(...)', ' V1', '(2)', JR-SH '-n' suffixes, SF '-2 ' prefixes."""
    m = re.match(r"^(JR-SH\d+)(-\d+)?(.*)$", title)
    if m:
        return m.group(1), ((m.group(2) or "") + m.group(3)).strip()
    variant = []
    while True:
        m = re.match(r"^(.*?)\s*[(（]([^()（）]*)[)）]\s*$", title)
        if m:
            title, inner = m.group(1), m.group(2)
            variant.insert(0, inner)
            continue
        m = re.match(r"^(.*?)\s+(V\d)$", title)
        if m:
            title = m.group(1)
            variant.insert(0, m.group(2))
            continue
        break
    title = re.sub(r"～NewVer～$", "", title).strip()
    if title.startswith("SF12 春"):
        variant.insert(0, "NewVer")
    return title.strip(), " / ".join(variant)


def variant_kind(variant: str) -> str:
    """What a version marker changes, for the 'how one melody gets many versions' analysis."""
    kinds = []
    rules = [
        ("移调", r"高音|低音ver|低い|高い|音が低い|移調|半音"),
        ("变速", r"テンポ|早回し"),
        ("结构/长度", r"エンドレス|ショートカット|短縮|フェードアウト|途中で終わる|前奏あり"),
        ("配器/音色", r"鐘強調|音色違い|低音強調"),
        ("段落截取", r"Aメロ|サビ|間奏"),
        ("站点专用版", r"(東京|柏|金町|鴻巣|吹上)ver"),
        ("另一版本", r"^V\d|^2$|NewVer|^-\d"),
    ]
    for name, pattern in rules:
        if re.search(pattern, variant):
            kinds.append(name)
    return "、".join(dict.fromkeys(kinds))


def classify(no: int, family: str) -> tuple[str, str, str, str]:
    """(origin, source/series, confidence, note) for one MP3."""
    if family.startswith("JR-SH"):
        return "原创", SERIES["JR-SH"], "高", ""
    if no <= 40:
        return "原创", SERIES["SF"], "高", ""
    if family in TML_FAMILIES:
        return "原创", SERIES["TML"], "高", ""
    if family in EN_FAMILIES:
        return "原创", SERIES["EN"], "中", ""
    if family in JA_FAMILIES:
        note = "与山口百惠的名曲同名，但 V1/V2 版本形式更像曲库原创" if family == "秋桜" else ""
        return "原创", SERIES["JA"], "中", note
    if family in ARRANGED:
        source, note = ARRANGED[family]
        return "改编", source, ("中" if family in ("Open Happiness", "Over") else "高"), note
    if family in UNCERTAIN:
        return "不确定", "", "低", UNCERTAIN[family]
    raise ValueError(f"unclassified: {no} {family}")


def main() -> None:
    rows = []
    for mp3 in sorted(REPO.glob("第*/*.mp3"), key=lambda p: p.name):
        m = re.match(r"^(\d{3}) (.*)\.mp3$", mp3.name)
        no, raw = int(m.group(1)), m.group(2)
        title = fix_title(raw)
        family, variant = family_and_variant(title)
        origin, source, confidence, note = classify(no, family)
        rows.append({
            "id": f"{no:03d}", "kind": "发车铃", "origin": origin, "source": source, "family": family,
            "title": title, "variant": variant, "variant_kind": variant_kind(variant),
            "confidence": confidence, "note": note,
            "audio": str(mp3.relative_to(REPO)),
            "midi": str(Path("harmonica_midi") / mp3.relative_to(REPO).with_suffix(".mid")),
            "transcription": "自动（Harmonica）",
        })
    for midi in sorted(REPO.glob("*.[Mm][Ii][Dd]")):
        role, origin, family, confidence, note = HANDMADE[midi.stem]
        rows.append({
            "id": midi.stem, "kind": role, "origin": origin,
            "source": ("唱歌" if family == "鉄道唱歌" else "古典/器乐名曲" if family.startswith("ハイケンス") else ""),
            "family": family, "title": midi.stem, "variant": "", "variant_kind": "",
            "confidence": confidence, "note": note, "audio": "", "midi": midi.name, "transcription": "手工",
        })
    out = REPO / "analysis" / "catalog.csv"
    with out.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} rows -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
