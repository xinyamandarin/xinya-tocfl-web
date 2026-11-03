# CLAUDE.md — XIN-YA TOCFL Vocabulary Web App (AI 老師)

> **สรุปภาษาไทย:** ไฟล์นี้อธิบายทุกอย่างที่ทำไว้ในตัวต้นแบบ (prototype) เวอร์ชัน 19 เพื่อให้ Claude / Cursor ใช้ต่อยอดเป็นเว็บจริงได้ทันที
> อ่านส่วน "Product rules" และ "Lessons learned" ก่อนแก้โค้ดทุกครั้ง

## 1. What this project is

- **Owner:** XIN-YA Mandarin (心雅華語), https://xuantaitechnology.com (WordPress + WooCommerce + Tutor LMS)
- **Product:** a vocabulary practice web app that replaces the printed checklist book for the TOCFL vocab books ("เก็งศัพท์พิชิต TOCFL"). The printed writing book (สมุดคัดศัพท์) stays.
- **Audience:** Thai learners first (UI in Thai), plus English. Taiwan Mandarin, **traditional characters first**, with a simplified toggle.
- **Word list:** 華語八千詞表 (TOCFL 8000), as printed in the XIN-YA books.
  - Band A: 1,226 words (Novice 1 160 · Novice 2 234 · A1 347 · A2 485)
  - Band B: 3,509 words (B1 1,167 · B2 2,342)
- **Business model:**
  - Free trial: 10 words per level.
  - Full access for buyers of the book, to be checked against WooCommerce.
  - Later possibly a subscription ("XIN-YA Club").
- **Current state:**
  - The prototype is one self-contained HTML page (about 1.2 MB) plus assets, published as a Claude artifact (version 19).
  - **Next step:** port it to Next.js + Supabase on Vercel at `app.xuantaitechnology.com`. See §9.

## 2. Tech decisions

| Area | Decision |
|---|---|
| Hosting | Vercel (owner has Cursor, GitHub, Vercel accounts). GitHub Pages is fine only for a static demo. |
| Framework (target) | Next.js (App Router) + TypeScript. The prototype is plain HTML/CSS/JS, so it can go up as a static site first. |
| Auth + DB (target) | Supabase: email + Google + Apple sign-in, `progress` table, Row Level Security ON. |
| AI | Anthropic API, called only from a server route (`/api/ask`). Never ship the key to the browser. Rate-limit per user per day. |
| Stroke order | Hanzi Writer 3.7.2 + `hanzi-writer-data@2.0.1`, overridden by XIN-YA's Taiwan-standard files (`hanzi-tw`). See §6. |
| Fonts | Thai: **Sarabun** (Thai with loops, มีหัว). Chinese: Noto Serif TC (headings/characters), Noto Sans TC. |
| Languages | **th + en only for now** (market test). vi / ja / ko strings already exist in `i18n.js`; re-enable by restoring `LANGS`. |
| Speech | Browser `speechSynthesis`, `lang = "zh-TW"`, rate 0.85. |

## 3. Data files

All files live in the owner's folder `สมุดคัดศัพท์Tocfl band A/` (and `TOCFL B/`) or come from the prototype build.

| File | What it is |
|---|---|
| `TOCFL_BandA_1226words.csv` | Band A words + Thai, book page, example sentence (zh/th/en), AI-draft EN/VI/JA/KO (team to review) |
| `TOCFL B/TOCFL_BandB_3509words.csv` | Band B words + Thai (**no example sentences yet**) |
| `words_all.json` (build) | 4,735 rows: `[no, level, trad, simp, pinyin, pos, thai, page, exTrad, exThai, exEn, enGloss, exSimp]`. Band B `no` continues from 1227; book number = `no - 1226` for B. |
| `TOCFL_คำที่มักสับสน_BandA-B.xlsx` + `TOCFL_confusables.json` | 116 confusable-word groups (N1 12 · N2 17 · A1 15 · A2 18 · B1 25 · B2 29). Thai explanations, 2 example sentences per word, common mistake ❌→✅. Sentence sources: `BK` = book, `TBCL` = TBCL 基礎詞義例句, `AI` = drafted (132, needs teacher check). |
| `TOCFL_部首_ตามระดับ.xlsx` | 214 Kangxi radicals → 1,966 characters by first level (from Unihan `kRSUnicode`), 10 categories |
| `hanzi-tw-strokes.zip` → `hw/tw.json` | Taiwan-standard stroke overrides (24 chars so far: 之乏仍似修偉偏傲忙快怕我儀充冊划割勵勸升印厲及吸). Arphic Public License. |
| `hw/N1…B2.json` | Hanzi Writer data bundled per level (about 6 MB) |
| `img/` | Calligraphy masks `hua.png 語 yu.png 愛 ai.png 上 shang.png`, `taiwan-zi.png` (臺灣), `taiwan.webp` (illustrated map) |
| `TBCL/` folder | TBCL 14452 word list (Taiwan pinyin, used for sentence pinyin), grammar points, 破音字 database |
| `TOCFL_詞彙學習計畫計算器.xlsx` | Study-plan calculator; its formulas are reimplemented in the 📅 Plan tab |

### `data/` — the live data the page loads (source of truth)

`index.html` fetches these at start-up (`<script type="module">`, boot overlay `#boot`). **Do not hand-edit them**: they are rebuilt from the Google Sheet by `scripts/sheet.py sync` (see §11).

| File | In the page | Content |
|---|---|---|
| `words.json` | `W` | Word rows `[no, level, trad, simp, pinyin, pos, thai, page, exTrad, exThai, exEn, enGloss, exSimp]` |
| `translations.json` | `TR` | `no → [en, vi, ja, ko]` (AI drafts, Band A). The sheet column `en` writes both `TR[no][0]` and `enGloss` |
| `example_tokens.json` | `EXT` | `no → [[token, pinyin], …]` example sentences segmented with Taiwan pinyin |
| `confusables.json` | `CONF` | Confusable groups `{id, lv, words, key, tip, items:[{w, py, lv, mean, use, ex:[{zh, th, src, tk}]}]}` |
| `radicals214.json` | `RAD` | `[n, radical, variants, th, en, cat, pinyin, strokes]` × 214 |
| `radical_notes.json` | `RB_RAW` | 22 radical lessons `[rad, py, th, cat, "字 py ความหมาย|…"]` |
| `characters.json` | `CHR` | `char → [radical n, pinyin, firstLevel, enGloss, extraStrokes]` |
| `trad_to_simp.json` | `TS` | Traditional → simplified char map |
| `char_bundle.json` | `CHAR_BUNDLE` | Character → level bundle in `hw/` |
| `ui_text.json` | overrides `I18N`, `RAD_CAT_I18N` (`radcat.*`), `RB_GROUPS_I18N` (`rbgroup.*`), `LANGS` | `{cols:[th,en,vi,ja,ko,…], langs:[{code,name,ai,on}], text:{key:{th,en,…}}}`. The code keeps the built-in strings as defaults; empty cells fall back to Thai. `LI()` uses the column order `LCOLS`, so a language can be switched on without the ones before it. |

## 4. Features (prototype v19)

### Login / sign-up (`#login`)
- **Layout:**
  - Desktop: split screen. Left = form on a copybook-grid background; right = red hero panel.
  - Hero panel: title text **TAIWAN TOCFL** (`.lg-title-txt`), floating map `img/taiwan-map.png`, sky lanterns (天燈), tagline "愛上華語 · 愛上臺灣".
  - Mobile: the hero becomes a top banner.
- **Form:**
  - Tabs เข้าสู่ระบบ / สมัครสมาชิก; buttons Continue with **Google** / **Apple**; email + password.
  - Sign-up adds name and confirm password.
  - "ทดลองใช้ก่อน" closes the screen and stays in trial mode.
- **Prototype limits:** no real auth. Any email logs in; Google/Apple log in as a demo user. The password is never stored or sent.

### Trial mode (default before login)
- Every feature is open, but only the **first 10 words of each level** (`FREE`, `canSee(w)`).
- **Locked parts show 🔒 and open the paywall** (`[data-pay]` → `paywall()`):
  - map units 2+
  - extra checklist words
  - quiz units
  - confusable groups beyond 2 per level
  - radical categories other than คนและครอบครัว
  - words in character pop-ups
  - "ask AI more"
- **Paywall buttons:** 🛒 สั่งซื้อหนังสือ (`BOOK_URL`, **TODO: real product URL**, now `https://xuantaitechnology.com/shop/`), ซื้อแล้ว · เข้าสู่ระบบ, ไว้ทีหลัง.
- A red trial bar appears at the top (floating above the bottom bar on the map).

### 🏮 Path (home, `#v-map`)
- **Level selector and plaque:** "พิชิต TOCFL Novice 1" + 準備級一級 / 準備級二級 / 入門級 / 基礎級 / 進階級 / 高階級.
- **Units:** units of 20 words drawn as red **lanterns on floating cloud islands**, connected by a dashed path. Names like 第三關 · ด่าน 3.
- **Special nodes:** a 🧧 review node every 5 units; final 大考 level test (20 questions).
- **Node states:** done (★), current (glowing, "เริ่ม!"), locked (paper grey). Locked units can still be tried; trial-locked units show 🔒.
- **Tapping a unit** opens a sheet with its 20 words + "เรียนคำศัพท์" (flashcards) + "ทำแบบทดสอบ 10 ข้อ".
- **Top bar:** 🔥 streak (days with activity), ★ total stars, flag language picker.
- **Bottom bar:** daily-goal card (from the plan) and 🧧 review (wrong words).

### 📋 Checklist
- **Cards:** status buttons ยังไม่ได้ / ไม่แน่ใจ / จำได้. Characters are plain text: the owner removed the 田字格 boxes from the checklist and flashcards (commit 3d0165a). Do not add them back.
- **Summary donut** for the level (known / not sure / don't know / unchecked) + simplified-difference stat.
- **Simplified mode:** words whose 简 form differs are shown in **blue**; each level card shows "简 ต่าง n (p%)"; filter "เฉพาะคำที่ตัวย่อต่างจากตัวเต็ม".
- **Search:** Chinese / pinyin / meaning / **word number** (`25`, `คำที่ 25`, `25-40`) across the whole band.
- **Word detail dialog:**
  - example sentence, radical chips, confusable chips
  - Hanzi Writer stroke animation + writing practice for each character

### 🃏 Flashcards
- 20 cards, weakest first; flip, rate 0/1/2; speak word / sentence; open strokes; AI explain.

### ✍️ Quiz
- **Units:** 20 words per unit, **10 questions** per unit; level test 20 questions; review of missed words.
- **4 mixed question types:**
  - meaning (word→meaning and meaning→word)
  - fill the blank (book sentence)
  - **order the words** (tap tiles)
  - **confusable words** (sentence from `CONF`; interchangeable groups are excluded, `CONF_SKIP`)
- **Toggles:** 拼 pinyin / 義 meaning.
- **Feedback:** wrong answers show the correct answer, meaning and, for confusables, the key difference + tip.
- **Scoring:** 10 pts, +5 combo from 3 correct in a row 🔥; stars ★ at 50/75/90 %; best score saved.
- **Answer effects:** a correct answer plays a "ding-ding" arpeggio (`cheer`) and shows a gold +points coin (`coinPop`, `.coin-fx`), with a bigger fanfare on a 3+ streak. A wrong answer plays `boo`. The coin respects reduced motion.
- **Band B limit:** no sentences yet, so only meaning + confusable questions.

### 部首 Radicals
- **Overview:** 4 summary cards (214 radicals · 201 used · 1,966 characters · up to the selected level) and a top-10 bar chart. The 214 table was removed at the owner's request.
- **10 categories:** คนและครอบครัว · ร่างกาย · การเคลื่อนไหวและการกระทำ · ใจ ภาษา และความเชื่อ · ธรรมชาติ · พืชและอาหาร · สัตว์ · เครื่องใช้และอาวุธ · บ้านและสถานที่ · ตัวเลข สี และสัญลักษณ์. Each category opens a bubble map.
- **Radical bubble map:** tap a character to hear it; the panel lists characters by level.
- **Character pop-up:** meaning, sound, pinyin, words with that character (no page change).

### 💬 Confusable words (tab "ถาม AI 老師")
- **Local data first, no AI cost:**
  - chips per level
  - a typed question is matched against `CONF` (`cfMatch`)
  - only unmatched questions or "ถาม AI 老師 เพิ่มเติม" call the AI
- The sentence-writing checker was removed at the owner's request.

### 📅 Study plan
- **Inputs:** exam date, target band, study days per week, reserve weeks, minutes per word, reviews.
- **Outputs:**
  - status ✓ / △ / ⚠
  - words per day, minutes per day, deadline, earliest exam date
  - pace comparison 10–30 words/day
  - weekly schedule
- **Today's words:** in book order, skipping known words.
- **Placement spot-check:** 20 questions, which estimates how many words are already known.
- **AI advice** button.

## 5. Design system

- **Brand (logo lantern 雅):** red `#CC2027`, dark red `#9E1419`, cream `#F8CE7C`, pink `#EA8681`, ink `#2A1A17`. Used for the login, trial bar, map lanterns and plaques.
- **Band colours (from the books), set on `body.band-a` / `body.band-b` by the current level:**
  - **Band A:** soft pink accent `#C8506E`, soft `#FBE5EB`, teal meaning row `#D4ECEA` / `#2C7473`, bg `#FCF7F8`.
  - **Band B:** light green accent `#4F8A36`, soft `#E4F1D7`, row `#E7F2DC` / `#3D6E28`, bg `#F7FAF3`.
- **Dark mode:** both bands and the map have dark tokens (map = night sky with glowing lanterns).
- **Copybook feel:**
  - `tzHTML()` / `.tz` 田字格 boxes still exist in the code but the checklist and flashcards no longer use them
  - faint grid paper on the login form
  - calligraphy masks as watermarks (`.cw` with `--m:url(img/…png)`, coloured by `currentColor`)
- **Responsive:**
  - Phones (≤760 px): a fixed **bottom menu with 7 items** on every page (เส้นทาง · เช็คลิสต์ · แฟลชการ์ด · แบบทดสอบ · 部首 · คำสับสน · แผน); the top tab row is hidden.
  - Desktop: the top tabs are used.
- **Motion:** gentle bob and glow only, with reduced-motion fallbacks.

## 6. Stroke order rule

- **One source only.** Load `hw/tw.json` (XIN-YA Taiwan overrides) first; if a character is not there, use the regular Hanzi Writer data.
- **MOE comparison removed:** there is no comparison badge and no link to the 教育部 site in the UI. The MOE site is CC BY-NC-ND: never copy its data, only use it as a reference by eye.
- **When the owner sends new Taiwan stroke files:** put them (or the `.zip`) in `hw/tw/`. The workflow `strokes.yml` runs `scripts/merge_strokes.py`, which validates them and rebuilds `hw/tw.json` keyed by the character itself (`"之"`). The page also accepts the old `"#U4e4b"` keys.
  - Keep the Arphic Public License text in the repo.
  - Keep the credit line "Hanzi Writer ปรับตามมาตรฐานไต้หวันโดย XIN-YA (Arphic Public License)".
- **Known gap:** about 350 Band A/B characters differ from MOE order or count. Common causes:
  - 艹 / 辶 / 阝 counted with more strokes in Taiwan
  - 忄 strokes 2–3 swapped

  The lists are in `TOCFL_BandA_stroke_links.csv` and `TOCFL B/TOCFL_BandB_stroke_check.csv`.

## 7. Product rules (do not break)

1. Traditional characters are the default; simplified is a toggle.
2. Trial = 10 words per level and the "people & family" radical category only. Everything else goes to the paywall → book page.
3. Answer confusable questions from local data before calling the AI (cost control).
4. AI answers in the chosen UI language; Taiwan usage; pinyin for Chinese.
5. Do not store passwords in the browser. Do not put API keys in client code.
6. Thai UI copy is the source of truth; English must stay in sync in `i18n.js` (`key: [th, en, vi, ja, ko]`).
7. AI-drafted content (translations, 132 example sentences, radical Thai names) is marked and must be reviewed by a teacher before launch.

## 8. Lessons learned (bugs we already hit)

- **CSS class collisions broke the app three times:**
  - `.lg` legend vs login overlay → invisible full-screen layer, the page looked frozen
  - `.trial` on `<body>` → the whole page turned red
  - `.r2` rating button vs the radical table → green background

  → In the new codebase use CSS Modules / Tailwind or a strict prefix per component, and never reuse a short global class name.
- **Elements with `display:flex` ignore the `hidden` attribute.** Always add `[hidden]{display:none}` for them.
- **`hw/tw.json` was keyed `#U4e4b` while the page looked up `tw["之"]`**, so the Taiwan strokes were never used until v20. Fixed both sides.
- **Pinyin of shortened variants:** words like `桌(子)` gave the short form `桌` the pinyin `zhuōzi` (and 上 → shàngmiàn, 車 → chēzi …). 115 sentence tokens, 105 characters and 5 radicals were wrong. Fixed in v20. `scripts/pinyin_utils.py → pinyin_fits()` now checks that the syllable count matches the characters; keep using it.
- Bob animations make Playwright clicks "unstable"; use `force: true` in tests.
- The prototype is built by patch scripts. Do not copy that approach: port feature by feature into components.

## 9. Roadmap (what to build next)

1. **Phase 1 – static deploy (1 day):** put the HTML + `hw/` + `img/` in a GitHub repo → Vercel → domain `app.xuantaitechnology.com` (CNAME).
2. **Phase 2 – Next.js + Supabase (1–3 weeks):**
   - Port the pages as components: Login, Path, Checklist, Flashcards, Quiz, Radicals, Confusables, Plan.
   - Move the progress data (the `S` object) to the Supabase `progress` table (user_id, jsonb), and turn on RLS.
   - Real Google / Apple / email auth.
3. **Phase 3 – AI 老師 (2–3 days):** `/api/ask` server route with the Anthropic key in Vercel env vars, plus a daily limit.
4. **Phase 4 – purchases:** link WooCommerce. Start with activation codes; later a webhook → Supabase `entitlements`.
5. **Before launch:**
   - privacy policy
   - security review (RLS, keys)
   - teacher review of AI-drafted content
   - ~~real `BOOK_URL`~~ done (Band A e-book / Band B book pages)
6. **Content to add:**
   - Band B example sentences (unlocks fill-blank and order questions for B)
   - Band B translations
   - more `hanzi-tw` stroke fixes
   - vi / ja / ko when the market test is done

## 10. State saved in the browser (prototype)

The prototype saves progress in `localStorage` under the key `xinya-bandA-v1`: `S = {lv, simp, st:{no:0|1|2}, tab, lang, plan, qb:{key:{b,s}}, wrong:[no], days:[ymd], auth, qpy, qmn}`.
This becomes the shape of the Supabase `progress.data` column.

## 11. Updating content (Google Sheet → website, automatic)

```
Google Sheet (team edits, ticks ✅)  ──daily 03:00 / Run workflow──▶  GitHub Action sync-sheet.yml
   └─ scripts/sheet.py sync: download xlsx → only ✅ rows → validate → data/*.json (+ new chars → hw/)
        └─ commit "data: sync from Google Sheet"  ──▶  Vercel redeploys
hw/tw/*.json or *.zip  ──push──▶  strokes.yml → scripts/merge_strokes.py → hw/tw.json → commit → Vercel
   (the zip from the 筆順 Stroke Editor artifact works as is; its README "In progress" characters are skipped)
```

- **Sheet tabs:** วิธีใช้ · คำศัพท์ · คำสับสน_กลุ่ม · คำสับสน_คำ · 部首214 · 部首_บทเรียน · ตัวอักษร · ข้อความเว็บ (UI text, one column per language; a new `Name [xx]` column adds a language) · ภาษา (code, menu name, English name for the AI prompt, `on`). Row 1 headers carry the key in brackets (`ความหมายไทย [thai]`); the script reads columns by that key, so columns can be moved but headers must keep `[key]`.
- **Rules in `sync`:**
  - Only rows with `✅ ขึ้นเว็บ [ok]` ticked are published. An edited row that is not ticked keeps the published version and shows in the report as pending.
  - Rows are never deleted by the sync.
  - New rows (new `no` / group `id`) are added when ticked.
  - Blank `simp` / `ex_simp` are converted from traditional. A blank sentence-pinyin column means "keep / auto".
  - A changed Chinese sentence is re-segmented with `pydict_base.json` plus the current word list. If the editor's pinyin line has the same number of words it is used; otherwise the auto pinyin is used and printed in the report for checking.
  - UI text: every language must keep the same `{placeholders}` as Thai, or the row is skipped. New keys need code; unknown keys are skipped.
  - When adding a UI string in code, add it to `I18N` **and** re-export the sheet (or add the row to `data/ui_text.json`), so teachers can see it.
  - Bad rows are skipped with a warning; the run aborts without writing if words drop >5 % or radicals ≠ 214.
- **Secrets (repo → Settings → Secrets → Actions):** `SHEET_ID` (required). `GOOGLE_SA_JSON` is optional: with it the sheet stays private and is shared only with the service account; without it the sheet must be "anyone with the link can view".
- **Rebuild the sheet from current data:** `python scripts/sheet.py export XINYA_TOCFL_data.xlsx`. The round trip export → sync gives byte-identical JSON (tested).
- `build_repo.py` (prototype builder) is retired. Do not regenerate `data/` from the old build files, or the v20 pinyin fixes are lost.

---
*Prototype: Claude artifact "XIN-YA TOCFL Band A AI", version 20 (2026-11-03): data split into `data/` + Google Sheet sync.*
