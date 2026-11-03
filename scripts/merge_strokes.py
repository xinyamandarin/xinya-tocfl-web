#!/usr/bin/env python3
"""
Merge the Taiwan stroke-order files in hw/tw/ into hw/tw.json (the app reads hw/tw.json first,
then falls back to the per-level bundles hw/N1.json … hw/B2.json).

Accepted in hw/tw/ :  one JSON per character in Hanzi Writer format {"strokes":[...], "medians":[...]}
named  #U4e4b.json · U+4E4B.json · 4e4b.json · 之.json   — or a .zip containing such files
(e.g. hanzi-tw-strokes.zip exported from the 筆順 Stroke Editor).

Order: loose .json files first, then each .zip (by file name), so a newer zip wins.
A zip from the Stroke Editor lists "In progress (n): …" in its README.txt — those characters are skipped
until they are marked "เสร็จ ✓" in the editor and exported again.
"""
import io, json, os, re, sys, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "hw", "tw")
OUT = os.path.join(ROOT, "hw", "tw.json")


def char_of(name):
    base = os.path.splitext(os.path.basename(name))[0]
    m = re.fullmatch(r"(?:#?U\+?|0x)?([0-9a-fA-F]{4,5})", base)
    if m:
        return chr(int(m.group(1), 16))
    if len(base) == 1:
        return base
    return None


def zname(info):
    """Zip entry name; zips made without the UTF-8 flag (some Mac/Linux tools) are decoded again as UTF-8."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except UnicodeError:
        return info.filename


def check(c, d):
    if not isinstance(d, dict) or not isinstance(d.get("strokes"), list) or not isinstance(d.get("medians"), list):
        return "ไม่มี strokes / medians"
    if len(d["strokes"]) != len(d["medians"]) or not d["strokes"]:
        return f"จำนวน strokes ({len(d['strokes'])}) ≠ medians ({len(d['medians'])})"
    if not all(isinstance(s, str) and s.lstrip().startswith("M") for s in d["strokes"]):
        return "strokes ต้องเป็น SVG path (ขึ้นต้นด้วย M)"
    return None


def main():
    out, errs, wip = {}, [], set()
    names = sorted(os.listdir(SRC)) if os.path.isdir(SRC) else []
    files = [(f, open(os.path.join(SRC, f), "rb").read(), None) for f in names if f.lower().endswith(".json")]
    for f in names:
        if not f.lower().endswith(".zip"):
            continue
        with zipfile.ZipFile(os.path.join(SRC, f)) as z:
            skip = set()
            for n in z.namelist():
                if n.lower().endswith("readme.txt"):
                    m = re.search(r"In progress \(\d+\):\s*(.*)", z.read(n).decode("utf-8", "replace"))
                    if m:
                        skip = {c for c in m.group(1).strip() if not c.isspace()}
            wip |= skip
            files += [(zname(i), z.read(i), skip) for i in z.infolist()
                      if i.filename.lower().endswith(".json") and "__MACOSX" not in i.filename]
    for name, raw, skip in files:
        c = char_of(name)
        if skip and c in skip:
            continue
        if not c:
            errs.append(f"{name}: ตั้งชื่อไฟล์ไม่ถูก (ใช้ #U4e4b.json หรือ 之.json)"); continue
        try:
            d = json.loads(raw.decode("utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            errs.append(f"{name}: อ่าน JSON ไม่ได้ ({e})"); continue
        e = check(c, d)
        if e:
            errs.append(f"{name} ({c}): {e}"); continue
        out[c] = {"strokes": d["strokes"], "medians": d["medians"]}
        if d.get("radStrokes"):
            out[c]["radStrokes"] = d["radStrokes"]
        wip.discard(c)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    md = [f"## ลำดับขีดแบบไต้หวัน: {len(out)} ตัว", "", "".join(sorted(out))]
    if wip:
        md += ["", f"### ⏳ ยังแก้ไม่เสร็จในเครื่องมือแก้ลำดับขีด (ยังไม่ขึ้นเว็บ): {''.join(sorted(wip))}"]
    if errs:
        md += ["", "### ⚠️ ไฟล์ที่ใช้ไม่ได้"] + [f"- {e}" for e in errs]
    text = "\n".join(md) + "\n"
    print(text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(text)


if __name__ == "__main__":
    sys.exit(main())
