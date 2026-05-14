# 🧠 VocabUp — คู่มือติดตั้ง

## โครงสร้างโปรเจกต์
```
vocab_app/
├── app.py              ← Streamlit UI หลัก
├── srs_engine.py       ← ระบบ Spaced Repetition (SM-2)
├── gemini_client.py    ← เรียก Gemini API
├── requirements.txt    ← dependencies
└── data/
    └── progress.json   ← เก็บ progress อัตโนมัติ (สร้างเองตอน run)
```

---

## ขั้นตอนที่ 1 — ขอ Gemini API Key (ฟรี)

1. ไปที่ https://aistudio.google.com/app/apikey
2. กด **"Create API key"**
3. Copy key ไว้ (ขึ้นต้นด้วย `AIza...`)

---

## ขั้นตอนที่ 2 — ติดตั้ง dependencies

```bash
cd vocab_app
pip install -r requirements.txt
```

---

## ขั้นตอนที่ 3 — ตั้งค่า API Key

### วิธีที่ 1: ตั้งใน Terminal (ง่ายที่สุด)
```bash
# macOS / Linux
export GEMINI_API_KEY="AIza..."

# Windows (CMD)
set GEMINI_API_KEY=AIza...

# Windows (PowerShell)
$env:GEMINI_API_KEY="AIza..."
```

### วิธีที่ 2: สร้างไฟล์ .env (สะดวกกว่าในระยะยาว)
```bash
# สร้างไฟล์ .env ใน vocab_app/
echo GEMINI_API_KEY=AIza... > .env
```
แล้วเพิ่มใน gemini_client.py บรรทัดแรก:
```python
from dotenv import load_dotenv
load_dotenv()
```
และ `pip install python-dotenv`

---

## ขั้นตอนที่ 4 — Run!

```bash
streamlit run app.py
```

เปิด browser ไปที่ http://localhost:8501

---

## ระบบ SRS ทำงานอย่างไร?

| ตอบถูกติดต่อกัน | Review ครั้งต่อไป |
|---|---|
| ครั้งแรก | 1 วัน |
| 2 ครั้ง | 4 วัน |
| 3 ครั้ง | ~10 วัน |
| 4+ ครั้ง | ขยายออกไปเรื่อยๆ |
| **ตอบผิด** | **วันพรุ่งนี้ (reset)** |

สถานะคำ:
- 🔵 **ใหม่** — เพิ่งเห็น
- 🟡 **กำลังเรียน** — ตอบถูกแล้ว 1-2 ครั้ง
- 🟢 **จำได้แล้ว** — ตอบถูกติดต่อกัน 3 ครั้ง ไม่เคยผิด

---

## ข้อมูลเก็บที่ไหน?

ไฟล์ `data/progress.json` ในเครื่องคุณ ส่วนตัว 100%
ลบไฟล์นี้ถ้าอยากเริ่มใหม่
