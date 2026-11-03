# XIN-YA · พิชิต TOCFL กับ AI 老師 (v20)

เว็บฝึกคำศัพท์ TOCFL Band A–B ของ XIN-YA Mandarin · เว็บจริง: https://xinya-tocfl-web.vercel.app/
รายละเอียดสำหรับนักพัฒนาและ AI อยู่ใน **CLAUDE.md** ส่วนคู่มือแก้ข้อมูลสำหรับทีมอยู่ใน **docs/คู่มือแก้ข้อมูล.md**

## โครงสร้าง
| ไฟล์ / โฟลเดอร์ | คืออะไร |
|---|---|
| `index.html` | ตัวเว็บ (หน้าเดียว) โหลดข้อมูลจาก `data/` |
| `data/*.json` | ข้อมูลทั้งหมด: คำศัพท์ 4,735 คำ, คำที่มักสับสน 116 กลุ่ม, 部首 214 ตัว, ตัวอักษร 1,966 ตัว, ประโยคพร้อมพินอิน — **สร้างจาก Google Sheet อัตโนมัติ ห้ามแก้ไฟล์นี้ตรง ๆ** |
| `hw/` | ลำดับขีดแยกตามระดับ + `tw.json` (มาตรฐานไต้หวัน รวมจาก `hw/tw/`) |
| `img/` | โลโก้และลายพู่กัน |
| `scripts/` | `sheet.py` (ชีต ↔ data) · `merge_strokes.py` (hw/tw → tw.json) · `pinyin_utils.py` |
| `.github/workflows/` | `sync-sheet.yml` ดึงชีตทุกวันตี 3 หรือกด Run · `strokes.yml` รวมลำดับขีดเมื่ออัปไฟล์ |
| `licenses/` | Arphic Public License ของข้อมูลลำดับขีด (ต้องเก็บไว้) |

## ทดลองบนเครื่องตัวเอง
```
python3 -m http.server 8000      # แล้วเปิด http://localhost:8000
pip install openpyxl
python3 scripts/sheet.py export XINYA_TOCFL_data.xlsx      # สร้างชีตจากข้อมูลปัจจุบัน
python3 scripts/sheet.py sync --xlsx XINYA_TOCFL_data.xlsx # ทดลองซิงก์จากไฟล์
```

## ข้อจำกัดตอนนี้
- **AI 老師:** ยังทำงานบน Vercel ไม่ได้ จนกว่าจะทำ `/api/ask` (ช่วง 3) แต่คำตอบเรื่องคำที่มักสับสนจากไฟล์ใช้ได้ปกติ
- **เข้าสู่ระบบ / Google / Apple:** ยังเป็นตัวอย่าง จะทำระบบจริงในช่วง 2 ด้วย Supabase
- **ความคืบหน้าของผู้เรียน:** เก็บอยู่ในเบราว์เซอร์ของเครื่องนั้นเท่านั้น

© XIN-YA Mandarin · ข้อมูลลำดับขีด: Hanzi Writer / Make Me A Hanzi ปรับตามมาตรฐานไต้หวันโดย XIN-YA (Arphic Public License)
