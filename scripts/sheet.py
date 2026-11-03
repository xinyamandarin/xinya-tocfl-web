#!/usr/bin/env python3
"""
XIN-YA TOCFL — Google Sheet  <->  data/*.json

    python scripts/sheet.py export  XINYA_TOCFL_data.xlsx        # JSON -> xlsx (to start / rebuild the Google Sheet)
    python scripts/sheet.py sync --xlsx file.xlsx                 # xlsx -> data/*.json
    python scripts/sheet.py sync --sheet-id <ID> [--fetch]        # download the Google Sheet, then sync

Rule: a row goes live only when its column  ✅ ขึ้นเว็บ [ok]  is ticked.
      An edited row that is not ticked keeps the version that is already on the website.
      Rows are never deleted by the sync (removing a row from the sheet does nothing).
"""
import argparse, io, json, os, re, sys, unicodedata, urllib.parse, urllib.request
from collections import OrderedDict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pinyin_utils import CJK, pinyin_fits, segment, tokens_to_py, apply_py_line  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
HW = os.path.join(ROOT, "hw")
LEVELS = ["N1", "N2", "A1", "A2", "B1", "B2"]
RAD_CATS = ["ppl", "body", "act", "mind", "nat", "plant", "ani", "thing", "place", "sym"]
OK_WORDS = {"true", "1", "y", "yes", "x", "✓", "✔", "✅", "ใช่", "ok", "ตรวจแล้ว"}

# ---------------------------------------------------------------- sheet layout
#   tab name, key column(s), [(key, Thai header, width, is_text)]
TABS = OrderedDict([
    ("คำศัพท์", dict(key=["no"], cols=[
        ("no", "เลขที่", 8, False), ("level", "ระดับ", 7, True), ("trad", "ตัวเต็ม", 12, True),
        ("simp", "ตัวย่อ (เว้นว่าง=อัตโนมัติ)", 12, True), ("pinyin", "พินอิน", 14, True), ("pos", "ชนิดคำ", 8, True),
        ("thai", "ความหมายไทย", 28, True), ("en", "ความหมายอังกฤษ", 24, True), ("page", "หน้าในหนังสือ", 8, False),
        ("ex_trad", "ประโยคตัวอย่าง (ตัวเต็ม)", 30, True), ("ex_py", "พินอินประโยค (ทีละคำ เว้นวรรค)", 34, True),
        ("ex_simp", "ประโยคตัวย่อ (เว้นว่าง=อัตโนมัติ)", 26, True), ("ex_th", "คำแปลประโยค (ไทย)", 30, True),
        ("ex_en", "คำแปลประโยค (อังกฤษ)", 30, True)])),
    ("คำสับสน_กลุ่ม", dict(key=["id"], cols=[
        ("id", "รหัสกลุ่ม", 8, False), ("lv", "ระดับ", 7, True), ("words", "คำในกลุ่ม (คั่นด้วย /)", 16, True),
        ("key", "หลักจำสั้น ๆ", 60, True), ("tip", "จุดที่มักผิด", 40, True)])),
    ("คำสับสน_คำ", dict(key=["id", "w"], cols=[
        ("id", "รหัสกลุ่ม", 8, False), ("w", "คำ", 8, True), ("py", "พินอิน", 12, True), ("lv", "ระดับ", 7, True),
        ("mean", "ความหมาย", 26, True), ("use", "วิธีใช้", 40, True),
        ("ex1_zh", "ประโยค 1", 28, True), ("ex1_py", "พินอินประโยค 1", 30, True), ("ex1_th", "แปล 1", 28, True),
        ("ex1_src", "ที่มา 1", 7, True),
        ("ex2_zh", "ประโยค 2", 28, True), ("ex2_py", "พินอินประโยค 2", 30, True), ("ex2_th", "แปล 2", 28, True),
        ("ex2_src", "ที่มา 2", 7, True)])),
    ("部首214", dict(key=["n"], cols=[
        ("n", "ลำดับ", 6, False), ("rad", "部首", 6, True), ("variant", "รูปย่อ", 8, True), ("th", "ความหมายไทย", 20, True),
        ("en", "อังกฤษ", 16, True), ("cat", "หมวด", 8, True), ("pinyin", "พินอิน", 10, True), ("strokes", "จำนวนขีด", 8, False)])),
    ("部首_บทเรียน", dict(key=["rad"], cols=[
        ("rad", "部首", 8, True), ("py", "พินอิน", 10, True), ("th", "ความหมายไทย", 16, True), ("cat", "หมวด", 10, True),
        ("examples", "ตัวอย่าง (ตัว พินอิน ความหมาย | คั่นด้วย |)", 90, True)])),
    ("ตัวอักษร", dict(key=["char"], cols=[
        ("char", "ตัวอักษร", 8, True), ("rad_no", "部首เลขที่ (1–214)", 10, False), ("pinyin", "พินอิน", 10, True),
        ("en", "ความหมายอังกฤษ", 34, True), ("extra", "ขีดนอก部首", 8, False)])),
    ("ข้อความเว็บ", dict(key=["key"], cols=[
        ("key", "รหัสข้อความ", 16, True), ("section", "อยู่ส่วนไหนของเว็บ (ไว้ดูเฉย ๆ)", 16, True),
        ("th", "ไทย", 40, True), ("en", "English", 40, True), ("vi", "Tiếng Việt", 30, True),
        ("ja", "日本語", 30, True), ("ko", "한국어", 30, True)])),
    ("ภาษา", dict(key=["code"], cols=[
        ("code", "รหัสภาษา", 8, True), ("name", "ชื่อที่แสดงในเมนู", 16, True),
        ("ai", "ชื่อภาษาอังกฤษ (ใช้สั่ง AI)", 18, True), ("on", "เปิดใช้บนเว็บ", 10, False)])),
])
LANG_RE = re.compile(r"^[a-z]{2,3}(?:_[a-z]{2,4})?$")
NOT_LANG = {"key", "section", "ok", "note"}
SECTIONS = [("pl", "📅 แผนการเรียน"), ("lg", "หน้าเข้าสู่ระบบ"), ("qz", "✍️ แบบทดสอบ"), ("quiz", "✍️ แบบทดสอบ"),
            ("q", "✍️ แบบทดสอบ"), ("rb", "部首"), ("radcat.", "部首 · หมวด"), ("rbgroup.", "部首 · กลุ่ม"), ("r", "部首"),
            ("mp", "🏮 เส้นทาง (หน้าแรก)"), ("cf", "💬 คำที่มักสับสน"), ("pw", "หน้าต่างซื้อหนังสือ"), ("st", "📋 เช็คลิสต์ · สถิติ"),
            ("ai", "💬 AI 老師"), ("ask", "💬 AI 老師"), ("thinking", "💬 AI 老師"), ("nv", "เมนูล่าง (มือถือ)"),
            ("tr", "แถบโหมดทดลอง"), ("tab", "แท็บด้านบน"), ("hw", "ลำดับขีด"), ("fc", "🃏 แฟลชการ์ด"), ("flip", "🃏 แฟลชการ์ด")]


def section_of(k):
    for pre, name in SECTIONS:
        if k.startswith(pre) and (pre.endswith(".") or len(k) == len(pre) or not k[len(pre)].islower()):
            return name
    return "ทั่วไป"


AUTO = {"simp", "ex_simp", "ex_py", "ex1_py", "ex2_py"}
TAIL = [("ok", "✅ ขึ้นเว็บ", 10, False), ("note", "หมายเหตุผู้ตรวจ (ไม่ขึ้นเว็บ)", 30, True)]


def load(name, default=None):
    p = os.path.join(DATA, name + ".json")
    if not os.path.exists(p):
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(name, obj):
    with open(os.path.join(DATA, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))


def norm(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    s = unicodedata.normalize("NFC", str(v)).replace("\r\n", "\n").strip()
    return s


def is_ok(v):
    return v is True or norm(v).lower() in OK_WORDS


# ---------------------------------------------------------------- JSON -> rows (the "published" view)
class Store:
    def __init__(self):
        self.words = load("words")
        self.tr = load("translations", {})
        self.ext = load("example_tokens", {})
        self.ts = load("trad_to_simp", {})
        self.conf = load("confusables", [])
        self.rad = load("radicals214", [])
        self.notes = load("radical_notes", [])
        self.chars = load("characters", {})
        self.bundle = load("char_bundle", {})
        self.ui = load("ui_text", {"cols": ["th", "en"], "langs": [], "text": {}})

    def cols(self, tab):
        """Columns of a tab; the UI-text tab gets one extra column per added language."""
        cols = list(TABS[tab]["cols"])
        if tab == "ข้อความเว็บ":
            have = {k for k, *_ in cols}
            names = {l["code"]: l["name"] for l in self.ui.get("langs", [])}
            cols += [(c, names.get(c, c), 30, True) for c in self.ui.get("cols", []) if c not in have]
        return cols

    # words ---------------------------------------------------------------
    def word_row(self, w):
        tr = self.tr.get(str(w[0]))
        tk = self.ext.get(str(w[0]))
        return dict(no=w[0], level=w[1], trad=w[2], simp=w[3], pinyin=w[4], pos=w[5], thai=w[6],
                    en=(tr[0] if tr and tr[0] else w[11]), page=w[7], ex_trad=w[8],
                    ex_py=tokens_to_py(tk) if tk else "", ex_simp=w[12], ex_th=w[9], ex_en=w[10])

    def rows(self, tab):
        if tab == "คำศัพท์":
            return [self.word_row(w) for w in self.words]
        if tab == "คำสับสน_กลุ่ม":
            return [dict(id=g["id"], lv=g["lv"], words=" / ".join(g["words"]), key=g.get("key", ""),
                         tip=g.get("tip", "")) for g in self.conf]
        if tab == "คำสับสน_คำ":
            out = []
            for g in self.conf:
                for it in g["items"]:
                    r = dict(id=g["id"], w=it["w"], py=it.get("py", ""), lv=it.get("lv", ""),
                             mean=it.get("mean", ""), use=it.get("use", ""))
                    for i in (1, 2):
                        e = it["ex"][i - 1] if len(it["ex"]) >= i else {}
                        r[f"ex{i}_zh"] = e.get("zh", "")
                        r[f"ex{i}_py"] = tokens_to_py(e["tk"]) if e.get("tk") else ""
                        r[f"ex{i}_th"] = e.get("th", "")
                        r[f"ex{i}_src"] = e.get("src", "")
                    out.append(r)
            return out
        if tab == "部首214":
            return [dict(n=r[0], rad=r[1], variant=r[2], th=r[3], en=r[4], cat=r[5], pinyin=r[6], strokes=r[7])
                    for r in self.rad]
        if tab == "部首_บทเรียน":
            return [dict(rad=r[0], py=r[1], th=r[2], cat=r[3], examples=r[4]) for r in self.notes]
        if tab == "ตัวอักษร":
            return [dict(char=c, rad_no=v[0], pinyin=v[1], en=v[3], extra=v[4]) for c, v in self.chars.items()]
        if tab == "ข้อความเว็บ":
            return [dict(key=k, section=section_of(k), **v) for k, v in self.ui["text"].items()]
        if tab == "ภาษา":
            return [dict(code=l["code"], name=l["name"], ai=l.get("ai", ""), on=bool(l.get("on"))) for l in self.ui["langs"]]
        raise KeyError(tab)


def rkey(tab, r):
    return tuple(norm(r.get(k)) for k in TABS[tab]["key"])


# ---------------------------------------------------------------- export
def export(path):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation
    st = Store()
    wb = Workbook()
    how = wb.active
    how.title = "วิธีใช้"
    lines = [
        ("XIN-YA TOCFL — ข้อมูลเว็บ (แก้ที่นี่ แล้วเว็บอัปเดตเอง)", True),
        ("", False),
        ("1) แก้ข้อความในช่องได้เลย (ห้ามแก้ช่อง เลขที่ / รหัสกลุ่ม / 部首 / ตัวอักษร ที่เป็นคอลัมน์แรก)", False),
        ("2) แถวที่แก้แล้วและตรวจเรียบร้อย → ติ๊กช่อง ✅ ขึ้นเว็บ  (แถวที่ไม่ติ๊ก เว็บจะใช้ข้อมูลเดิม)", False),
        ("3) ระบบดึงข้อมูลทุกวัน ตี 3 (เวลาไทย) หรือกด Run ใน GitHub → Actions → Sync Google Sheet ได้ทันที", False),
        ("4) พินอินประโยค: เขียนทีละคำตามที่ระบบตัดคำ คั่นด้วยเว้นวรรค เช่น  wǒ shì xuéshēng", False),
        ("   ถ้าแก้ประโยคจีนใหม่ ให้ลบช่องพินอินประโยคทิ้ง ระบบจะเติมให้อัตโนมัติ แล้วค่อยตรวจในรายงาน", False),
        ("5) ตัวย่อ / ประโยคตัวย่อ เว้นว่างได้ ระบบแปลงจากตัวเต็มให้", False),
        ("6) เพิ่มคำใหม่: เพิ่มแถวท้ายตาราง ใส่เลขที่ใหม่ที่ไม่ซ้ำ แล้วติ๊ก ✅", False),
        ("7) ลบแถวในชีต ไม่ได้ลบออกจากเว็บ (กันพลาด) ถ้าต้องลบจริง แจ้งผู้ดูแลระบบ", False),
        ("8) หมวด部首: " + ", ".join(RAD_CATS) + "  ·  ระดับ: " + ", ".join(LEVELS), False),
        ("9) ที่มาประโยค: TBCL = คลังคำ TBCL, BK = หนังสือ, AI = แต่งโดย AI (ควรตรวจ)", False),
        ("", False),
        ("ข้อความบนหน้าเว็บ (แท็บ ข้อความเว็บ)", True),
        ("10) แก้คำผิด/สำนวนของปุ่มและข้อความต่าง ๆ ได้ทุกภาษา ห้ามแก้ช่องรหัสข้อความ", False),
        ("11) ข้อความที่มี {n} {lv} ฯลฯ คือช่องที่ระบบเติมตัวเลข/ชื่อให้ ทุกภาษาต้องมีช่องเหล่านี้ครบเหมือนภาษาไทย", False),
        ("12) ช่องที่เว้นว่าง เว็บจะแสดงภาษาไทยแทน", False),
        ("13) เพิ่มภาษาใหม่: (ก) แท็บ ภาษา เพิ่มแถว รหัส เช่น id, ชื่อ Bahasa Indonesia, ชื่ออังกฤษ Indonesian", False),
        ("    (ข) แท็บ ข้อความเว็บ เพิ่มคอลัมน์ใหม่ หัวตาราง เช่น  Bahasa Indonesia [id]  แล้วแปลทีละแถว  (ค) แปลครบแล้วค่อยติ๊ก เปิดใช้บนเว็บ", False),
    ]
    for i, (t, b) in enumerate(lines, 1):
        how.cell(i, 1, t).font = Font(bold=b, size=14 if b else 11)
    how.column_dimensions["A"].width = 120

    head_fill = PatternFill("solid", fgColor="F8D7DA")
    ok_fill = PatternFill("solid", fgColor="E2F4E5")
    key_fill = PatternFill("solid", fgColor="EEEEEE")
    for tab, spec in TABS.items():
        ws = wb.create_sheet(tab)
        cols = st.cols(tab) + TAIL
        for j, (k, th, wdt, _) in enumerate(cols, 1):
            c = ws.cell(1, j, f"{th} [{k}]")
            c.font = Font(bold=True)
            c.fill = ok_fill if k == "ok" else head_fill
            c.alignment = Alignment(wrap_text=True, vertical="center")
            ws.column_dimensions[c.column_letter].width = wdt
        ws.freeze_panes = "B2" if tab != "คำสับสน_คำ" else "C2"
        ws.row_dimensions[1].height = 34
        rows = st.rows(tab)
        for i, r in enumerate(rows, 2):
            for j, (k, _, _, is_text) in enumerate(cols, 1):
                v = True if k == "ok" else r.get(k, "")
                if k == "on":
                    v = bool(v)
                c = ws.cell(i, j, v if v != "" else None)
                if is_text:
                    c.number_format = "@"
                if k in spec["key"]:
                    c.fill = key_fill
        last = len(rows) + 400
        okcol = ws.cell(1, len(cols) - 1).column_letter  # ✅ column (second to last)
        dv = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{okcol}2:{okcol}{last}")
        if tab == "คำศัพท์":
            dl = DataValidation(type="list", formula1='"' + ",".join(LEVELS) + '"', allow_blank=False)
            ws.add_data_validation(dl); dl.add(f"B2:B{last}")
        if tab == "ภาษา":
            don = DataValidation(type="list", formula1='"TRUE,FALSE"', allow_blank=True)
            ws.add_data_validation(don); don.add(f"D2:D{last}")
        if tab == "部首214":
            dc = DataValidation(type="list", formula1='"' + ",".join(RAD_CATS) + '"', allow_blank=False)
            ws.add_data_validation(dc); dc.add(f"F2:F{last}")
        ws.auto_filter.ref = f"A1:{ws.cell(1, len(cols)).column_letter}{len(rows) + 1}"
    wb.save(path)
    print(f"wrote {path}: " + ", ".join(f"{t} {len(Store().rows(t))}" for t in TABS))


# ---------------------------------------------------------------- read xlsx
def read_xlsx(src):
    from openpyxl import load_workbook
    wb = load_workbook(src, data_only=True, read_only=True)
    out = {}
    for tab in TABS:
        if tab not in wb.sheetnames:
            raise SystemExit(f"❌ ไม่พบแท็บ '{tab}' ในชีต")
        ws = wb[tab]
        it = ws.iter_rows(values_only=True)
        head = next(it)
        keys = []
        for h in head:
            m = re.search(r"\[(\w+)\]", norm(h))
            keys.append(m.group(1) if m else None)
        need = [k for k, *_ in TABS[tab]["cols"]] + ["ok"]
        miss = [k for k in need if k not in keys]
        if miss:
            raise SystemExit(f"❌ แท็บ '{tab}' ไม่มีคอลัมน์ {miss} (อย่าแก้หัวตารางแถวแรก)")
        rows = []
        for n, vals in enumerate(it, 2):
            r = {k: vals[i] if i < len(vals) else None for i, k in enumerate(keys) if k}
            if all(norm(r.get(k)) == "" for k in TABS[tab]["key"]):
                continue
            r["_row"] = n
            rows.append(r)
        out[tab] = rows
    return out


def download(sheet_id):
    """Export the Google Sheet as xlsx. Uses a service account if GOOGLE_SA_JSON is set, else the share link."""
    sa = os.environ.get("GOOGLE_SA_JSON")
    if sa:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        cred = service_account.Credentials.from_service_account_info(
            json.loads(sa), scopes=["https://www.googleapis.com/auth/drive.readonly"])
        cred.refresh(Request())
        url = (f"https://www.googleapis.com/drive/v3/files/{sheet_id}/export?mimeType="
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {cred.token}"})
    else:
        req = urllib.request.Request(f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx")
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    if not body.startswith(b"PK"):
        raise SystemExit("❌ ดาวน์โหลดชีตไม่ได้ — ตรวจว่าแชร์ลิงก์แบบ 'ทุกคนที่มีลิงก์ดูได้' หรือแชร์ให้ service account แล้ว")
    return io.BytesIO(body)


# ---------------------------------------------------------------- sync
class Report:
    def __init__(self):
        self.changed, self.pending, self.warn, self.added = [], [], [], []

    def md(self):
        L = ["## ผลการซิงก์ Google Sheet → เว็บ", ""]
        L.append(f"- อัปเดตขึ้นเว็บ: **{len(self.changed)}** รายการ · เพิ่มใหม่: **{len(self.added)}** · "
                 f"รอติ๊ก ✅: **{len(self.pending)}** · คำเตือน: **{len(self.warn)}**")
        for title, items in (("✏️ แก้แล้วขึ้นเว็บ", self.changed), ("🆕 เพิ่มใหม่", self.added),
                             ("⏳ แก้ในชีตแต่ยังไม่ติ๊ก ✅ (ยังไม่ขึ้นเว็บ)", self.pending), ("⚠️ ควรตรวจ", self.warn)):
            if items:
                L += ["", f"### {title}", ""] + [f"- {x}" for x in items[:300]]
                if len(items) > 300:
                    L.append(f"- … อีก {len(items) - 300} รายการ")
        return "\n".join(L) + "\n"


def to_simp(s, ts):
    return "".join(ts.get(c, c) for c in s)


def build_pydict(words, base):
    D = dict(base)
    for w in words:
        forms = [f.strip() for f in w[2].split("/")]
        pys = [p.strip() for p in re.split(r"\s*/\s*", w[4])]
        for i, f in enumerate(forms):
            py = pys[min(i, len(pys) - 1)].replace(" ", "")
            m = re.match(r"^(.*)\((.*)\)(.*)$", f)
            f = m.group(1) + m.group(2) + m.group(3) if m else f
            py = py.replace("(", "").replace(")", "")
            if f and py and not re.search(r"[^㐀-鿿]", f) and pinyin_fits(f, py):
                D[f] = py
    return D


def make_tokens(zh, py_line, old_zh, old_tk, D, where, rep):
    """Tokens for an example sentence, keeping the published ones when nothing changed."""
    if zh == old_zh and old_tk:
        if not py_line or py_line == tokens_to_py(old_tk):
            return old_tk
        t = apply_py_line(old_tk, py_line)
        if t is not None:
            return t
        rep.warn.append(f"{where}: จำนวนคำในพินอินประโยคไม่ตรง ({len(py_line.split())} ≠ "
                        f"{len(tokens_to_py(old_tk).split())}) — ใช้พินอินเดิม")
        return old_tk
    tk, miss = segment(zh, D)
    if py_line:
        t = apply_py_line(tk, py_line)
        if t is not None:
            return t
    auto = tokens_to_py(tk)
    rep.warn.append(f"{where}: ประโยคใหม่ ใช้พินอินอัตโนมัติ → `{auto}` — โปรดตรวจ แล้ววางในช่องพินอินประโยค"
                    + (f" (ไม่รู้จักตัว: {''.join(miss)})" if miss else ""))
    return tk


def sync(sheet, fetch_new=False):
    st = Store()
    rep = Report()
    base = json.load(open(os.path.join(os.path.dirname(__file__), "pydict_base.json"), encoding="utf-8"))

    def diff(tab, pub, new, label):
        keys = [k for k, *_ in st.cols(tab) if k != "section"]
        if tab == "ข้อความเว็บ":  # a language column added in the sheet
            keys += [k for k in new if LANG_RE.match(k) and k not in NOT_LANG and k not in keys]
        # a blank "auto" column (simplified forms, sentence pinyin) means "work it out" — not a change
        return [k for k in keys
                if norm(new.get(k)) != norm(pub.get(k)) and not (k in AUTO and norm(new.get(k)) == "")]

    def changes_for(tab, label_fn):
        pub = {rkey(tab, r): r for r in st.rows(tab)}
        seen, out = set(), []
        for r in sheet[tab]:
            k = rkey(tab, r)
            if k in seen:
                rep.warn.append(f"{tab} แถว {r['_row']}: รหัส {'/'.join(k)} ซ้ำ — ข้าม")
                continue
            seen.add(k)
            p = pub.get(k)
            if p is None:
                if is_ok(r.get("ok")):
                    out.append((None, r))
                else:
                    rep.pending.append(f"{tab} แถว {r['_row']} ({label_fn(r)}): แถวใหม่ ยังไม่ติ๊ก ✅")
                continue
            fields = diff(tab, p, r, label_fn(r))
            if not fields:
                continue
            if is_ok(r.get("ok")):
                out.append((p, r, fields))
            else:
                rep.pending.append(f"{tab} แถว {r['_row']} ({label_fn(r)}): แก้ {', '.join(fields)}")
        return out

    def log(tab, r, fields, p):
        bits = []
        for f in fields:
            a, b = norm(p.get(f)), norm(r.get(f))
            bits.append(f"{f}: “{a[:40]}” → “{b[:40]}”")
        rep.changed.append(f"{tab} {'/'.join(rkey(tab, r))}: " + " · ".join(bits))

    # ---- words
    byno = {w[0]: w for w in st.words}
    wchanges = changes_for("คำศัพท์", lambda r: f"#{norm(r.get('no'))} {norm(r.get('trad'))}")
    D = build_pydict(st.words, base)
    for ch in wchanges:
        r = ch[1]
        try:
            no = int(norm(r["no"]))
        except ValueError:
            rep.warn.append(f"คำศัพท์ แถว {r['_row']}: เลขที่ “{norm(r['no'])}” ไม่ใช่ตัวเลข — ข้าม"); continue
        lv, trad = norm(r.get("level")), norm(r.get("trad"))
        bad = []
        if lv not in LEVELS: bad.append(f"ระดับ “{lv}” ไม่ถูกต้อง")
        if not trad: bad.append("ตัวเต็มว่าง")
        if not norm(r.get("pinyin")): bad.append("พินอินว่าง")
        if not norm(r.get("thai")): bad.append("ความหมายไทยว่าง")
        if bad:
            rep.warn.append(f"คำศัพท์ #{no} แถว {r['_row']}: {', '.join(bad)} — ยังไม่ขึ้นเว็บ"); continue
        old = byno.get(no)
        w = list(old) if old else [no, "", "", "", "", "", "", "", "", "", "", "", ""]
        page = norm(r.get("page"))
        w[1], w[2], w[4], w[5], w[6] = lv, trad, norm(r.get("pinyin")), norm(r.get("pos")), norm(r.get("thai"))
        w[3] = norm(r.get("simp")) or to_simp(trad, st.ts)
        w[7] = int(page) if page.isdigit() else (page or "")
        w[8], w[9], w[10] = norm(r.get("ex_trad")), norm(r.get("ex_th")), norm(r.get("ex_en"))
        w[12] = norm(r.get("ex_simp")) or to_simp(w[8], st.ts)
        en = norm(r.get("en"))
        w[11] = en
        trow = st.tr.get(str(no))
        if trow:
            trow[0] = en
        # simplified map learns from the editor's pairs
        for a, b in ((trad, w[3]), (w[8], w[12])):
            if len(a) == len(b):
                for x, y in zip(a, b):
                    if x != y and CJK.match(x) and CJK.match(y):
                        st.ts.setdefault(x, y)
        # example tokens
        if w[8]:
            old_tk = st.ext.get(str(no))
            st.ext[str(no)] = make_tokens(w[8], norm(r.get("ex_py")), old[8] if old else None, old_tk, D,
                                          f"คำศัพท์ #{no}", rep)
        else:
            st.ext.pop(str(no), None)
        if old:
            log("คำศัพท์", r, ch[2], ch[0]); byno[no][:] = w
        else:
            byno[no] = w; rep.added.append(f"คำศัพท์ #{no} {trad} ({lv})")
        if not pinyin_fits(trad.split("/")[0].replace("(", "").replace(")", ""), w[4].split("/")[0]):
            rep.warn.append(f"คำศัพท์ #{no} {trad}: จำนวนพยางค์พินอิน “{w[4]}” ดูไม่ตรงกับจำนวนตัวอักษร")
    st.words = sorted(byno.values(), key=lambda w: w[0])

    # ---- confusables
    gmap = OrderedDict((g["id"], g) for g in st.conf)
    for ch in changes_for("คำสับสน_กลุ่ม", lambda r: f"กลุ่ม {norm(r.get('id'))} {norm(r.get('words'))}"):
        r = ch[1]
        gid = int(norm(r["id"]))
        words = [x.strip() for x in re.split(r"[/／、,]", norm(r.get("words"))) if x.strip()]
        if len(words) < 2:
            rep.warn.append(f"คำสับสน กลุ่ม {gid}: ต้องมีอย่างน้อย 2 คำ — ข้าม"); continue
        g = gmap.get(gid) or dict(id=gid, items=[])
        g.update(words=words, lv=norm(r.get("lv")), key=norm(r.get("key")), tip=norm(r.get("tip")))
        if gid in gmap:
            log("คำสับสน_กลุ่ม", r, ch[2], ch[0])
        else:
            gmap[gid] = g; rep.added.append(f"คำสับสน กลุ่ม {gid} {'/'.join(words)}")
    for ch in changes_for("คำสับสน_คำ", lambda r: f"กลุ่ม {norm(r.get('id'))} {norm(r.get('w'))}"):
        r = ch[1]
        gid, wd = int(norm(r["id"])), norm(r["w"])
        g = gmap.get(gid)
        if not g:
            rep.warn.append(f"คำสับสน_คำ แถว {r['_row']}: ไม่มีกลุ่ม {gid} ในแท็บ คำสับสน_กลุ่ม — ข้าม"); continue
        old = next((it for it in g["items"] if it["w"] == wd), None)
        it = dict(w=wd, py=norm(r.get("py")), lv=norm(r.get("lv")), mean=norm(r.get("mean")),
                  use=norm(r.get("use")), ex=[])
        for i in (1, 2):
            zh = norm(r.get(f"ex{i}_zh"))
            if not zh:
                continue
            oe = old["ex"][i - 1] if old and len(old["ex"]) >= i else {}
            it["ex"].append(dict(zh=zh, th=norm(r.get(f"ex{i}_th")), src=norm(r.get(f"ex{i}_src")) or "AI",
                                 tk=make_tokens(zh, norm(r.get(f"ex{i}_py")), oe.get("zh"), oe.get("tk"), D,
                                                f"คำสับสน {gid} {wd} ประโยค {i}", rep)))
        if old:
            old.clear(); old.update(it); log("คำสับสน_คำ", r, ch[2], ch[0])
        else:
            g["items"].append(it); rep.added.append(f"คำสับสน กลุ่ม {gid}: คำ {wd}")
    for g in gmap.values():
        if len(g["items"]) < 2:
            rep.warn.append(f"คำสับสน กลุ่ม {g['id']}: มีคำ {len(g['items'])} คำ (ควรมี ≥ 2 แถวในแท็บ คำสับสน_คำ)")
    st.conf = [g for g in gmap.values() if g["items"]]

    # ---- radicals
    rmap = {r[0]: r for r in st.rad}
    for ch in changes_for("部首214", lambda r: f"{norm(r.get('n'))} {norm(r.get('rad'))}"):
        r = ch[1]
        n = int(norm(r["n"]))
        if n not in rmap:
            rep.warn.append(f"部首214: ลำดับ {n} ไม่อยู่ใน 1–214 — ข้าม"); continue
        cat = norm(r.get("cat"))
        if cat not in RAD_CATS:
            rep.warn.append(f"部首 {n}: หมวด “{cat}” ไม่ถูกต้อง ({', '.join(RAD_CATS)}) — ข้าม"); continue
        s = norm(r.get("strokes"))
        rmap[n][:] = [n, norm(r.get("rad")), norm(r.get("variant")), norm(r.get("th")), norm(r.get("en")),
                      cat, norm(r.get("pinyin")), int(s) if s.isdigit() else rmap[n][7]]
        log("部首214", r, ch[2], ch[0])
    nmap = OrderedDict((x[0], x) for x in st.notes)
    for ch in changes_for("部首_บทเรียน", lambda r: norm(r.get("rad"))):
        r = ch[1]
        row = [norm(r.get(k)) for k in ("rad", "py", "th", "cat", "examples")]
        if row[0] in nmap:
            nmap[row[0]][:] = row; log("部首_บทเรียน", r, ch[2], ch[0])
        else:
            nmap[row[0]] = row; rep.added.append(f"部首_บทเรียน {row[0]}")
    st.notes = list(nmap.values())
    for ch in changes_for("ตัวอักษร", lambda r: norm(r.get("char"))):
        r = ch[1]
        c = norm(r["char"])
        try:
            rn = int(norm(r.get("rad_no")))
            assert 1 <= rn <= 214
        except Exception:
            rep.warn.append(f"ตัวอักษร {c}: เลข部首 “{norm(r.get('rad_no'))}” ต้องเป็น 1–214 — ข้าม"); continue
        ex = norm(r.get("extra"))
        old = st.chars.get(c, [rn, "", 0, "", 0])
        st.chars[c] = [rn, norm(r.get("pinyin")), old[2], norm(r.get("en")), int(ex) if ex.lstrip("-").isdigit() else old[4]]
        if ch[0]:
            log("ตัวอักษร", r, ch[2], ch[0])
        else:
            rep.added.append(f"ตัวอักษร {c}")

    # ---- UI text + languages
    ui = st.ui
    for ch in changes_for("ภาษา", lambda r: norm(r.get("code"))):
        r = ch[1]
        code = norm(r["code"]).lower()
        if not LANG_RE.match(code) or not norm(r.get("name")):
            rep.warn.append(f"ภาษา แถว {r['_row']}: รหัส “{code}” ต้องเป็นตัวอักษรภาษาอังกฤษ 2–3 ตัว และต้องมีชื่อ — ข้าม"); continue
        row = dict(code=code, name=norm(r.get("name")), ai=norm(r.get("ai")) or norm(r.get("name")), on=is_ok(r.get("on")))
        old = next((l for l in ui["langs"] if l["code"] == code), None)
        if old:
            old.update(row); log("ภาษา", r, ch[2], ch[0])
        else:
            ui["langs"].append(row); rep.added.append(f"ภาษาใหม่ {code} {row['name']}")
        if code not in ui["cols"]:
            ui["cols"].append(code)
    if not any(l["on"] and l["code"] == "th" for l in ui["langs"]):
        rep.warn.append("ภาษา: ต้องเปิดใช้ภาษาไทย (th) เสมอ — เปิดให้อัตโนมัติ")
        for l in ui["langs"]:
            if l["code"] == "th":
                l["on"] = True
    ph = re.compile(r"\{\w+\}")
    for ch in changes_for("ข้อความเว็บ", lambda r: norm(r.get("key"))):
        r = ch[1]
        k = norm(r["key"])
        if ch[0] is None:
            rep.warn.append(f"ข้อความเว็บ แถว {r['_row']}: ไม่มีรหัส “{k}” ในเว็บ — ข้าม (เพิ่มรหัสใหม่ต้องแก้โค้ด)"); continue
        langs = [c for c in r if LANG_RE.match(c) and c not in NOT_LANG]
        val = {c: norm(r.get(c)) for c in langs if norm(r.get(c))}
        if not val.get("th") and ch[0].get("th"):
            rep.warn.append(f"ข้อความเว็บ {k}: ช่องภาษาไทยว่าง — ข้าม"); continue
        want = sorted(ph.findall(val["th"]))
        bad = [c for c, v in val.items() if sorted(ph.findall(v)) != want]
        if bad:
            rep.warn.append(f"ข้อความเว็บ {k}: ภาษา {', '.join(bad)} ต้องมีช่องเติมคำ {' '.join(want) or '(ไม่มี)'} เหมือนภาษาไทย — ข้าม"); continue
        for c in val:
            if c not in ui["cols"]:
                ui["cols"].append(c)
        ui["text"][k] = val
        log("ข้อความเว็บ", r, ch[2], ch[0])

    # ---- derived: first level of each character, new characters
    ORD = {k: i for i, k in enumerate(LEVELS)}
    first = {}
    for w in st.words:
        for c in w[2]:
            if CJK.match(c):
                first[c] = min(first.get(c, 9), ORD.get(w[1], 9))
    new_chars = [c for c in first if c not in st.chars]
    for c, o in first.items():
        if c in st.chars:
            st.chars[c][2] = o
    if new_chars:
        add_new_chars(st, new_chars, first, D, rep, fetch_new)

    # ---- safety checks before writing
    counts = {lv: sum(1 for w in st.words if w[1] == lv) for lv in LEVELS}
    if len(st.words) < 0.95 * len(load("words")) or len(st.rad) != 214:
        raise SystemExit("❌ ข้อมูลหายผิดปกติ — ยกเลิก ไม่เขียนไฟล์")
    if len({w[0] for w in st.words}) != len(st.words):
        raise SystemExit("❌ เลขที่คำซ้ำ — ยกเลิก")

    save("words", st.words); save("translations", st.tr); save("example_tokens", st.ext)
    save("trad_to_simp", st.ts); save("confusables", st.conf); save("radicals214", sorted(rmap.values()))
    save("radical_notes", st.notes); save("characters", st.chars); save("char_bundle", st.bundle)
    save("ui_text", ui)
    rep.counts = counts
    return rep


def add_new_chars(st, new_chars, first, D, rep, fetch):
    """New characters from new words: radical/pinyin from Unihan, stroke data from hanzi-writer-data."""
    uh = {}
    if fetch:
        try:
            import zipfile
            z = zipfile.ZipFile(io.BytesIO(urllib.request.urlopen(
                "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip", timeout=120).read()))
            want = {f"U+{ord(c):04X}": c for c in new_chars}
            for name in z.namelist():
                for line in z.read(name).decode("utf-8").splitlines():
                    p = line.split("\t")
                    if len(p) == 3 and p[0] in want and p[1] in ("kRSUnicode", "kMandarin", "kDefinition"):
                        uh.setdefault(want[p[0]], {})[p[1]] = p[2]
        except Exception as e:  # noqa: BLE001
            rep.warn.append(f"โหลด Unihan ไม่ได้ ({e}) — ตัวอักษรใหม่ยังไม่มีข้อมูล部首")
    for c in new_chars:
        u = uh.get(c, {})
        rs = re.match(r"(\d+)'*\.(-?\d+)", u.get("kRSUnicode", "") or "")
        py = D.get(c) or (u.get("kMandarin", "").split() or [""])[0]
        if rs:
            st.chars[c] = [int(rs.group(1)), py, first[c], (u.get("kDefinition", "").split(";")[0])[:40], int(rs.group(2))]
        lv = LEVELS[first[c]]
        if fetch and c not in st.bundle:
            try:
                d = json.loads(urllib.request.urlopen(
                    "https://cdn.jsdelivr.net/npm/hanzi-writer-data@2.0.1/" + urllib.parse.quote(c) + ".json", timeout=30).read())
                p = os.path.join(HW, f"{lv}.json")
                b = json.load(open(p, encoding="utf-8"))
                b[c] = d
                json.dump(b, open(p, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
                st.bundle[c] = lv
            except Exception as e:  # noqa: BLE001
                rep.warn.append(f"ตัวอักษรใหม่ {c}: ไม่มีข้อมูลลำดับขีด ({e}) — อัปไฟล์เองที่ hw/tw/")
        rep.added.append(f"ตัวอักษรใหม่ {c} ({lv})" + ("" if c in st.chars else " — ยังไม่มีข้อมูล部首 กรอกในแท็บ ตัวอักษร"))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("out")
    s = sub.add_parser("sync"); s.add_argument("--xlsx"); s.add_argument("--sheet-id")
    s.add_argument("--fetch", action="store_true", help="download data for new characters (Unihan + stroke data)")
    s.add_argument("--report", default=None, help="write the markdown report to this file")
    a = ap.parse_args()
    if a.cmd == "export":
        return export(a.out)
    src = a.xlsx or (download(a.sheet_id) if a.sheet_id else None)
    if src is None:
        raise SystemExit("ต้องระบุ --xlsx หรือ --sheet-id")
    rep = sync(read_xlsx(src), a.fetch)
    md = rep.md() + "\n" + " · ".join(f"{k} {v}" for k, v in rep.counts.items()) + "\n"
    print(md)
    if a.report:
        open(a.report, "w", encoding="utf-8").write(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8").write(md)


if __name__ == "__main__":
    main()
