import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import random
import plotly.express as px
import requests
from deep_translator import GoogleTranslator

# --- 1. DATABASE & CONFIG ---
DB_NAME = "lexicon_v5.db"
TARGET_BATCH_SIZE = 3 

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vocab 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  word TEXT UNIQUE, pos TEXT, pronunciation TEXT, translation TEXT, 
                  example TEXT, example_th TEXT, level TEXT, interval INTEGER DEFAULT 0, 
                  easiness REAL DEFAULT 2.5, next_review TEXT, 
                  mastery_score INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
    
    # ตรวจสอบคอลัมน์ example_th กันระเบิด
    c.execute("PRAGMA table_info(vocab)")
    columns = [column[1] for column in c.fetchall()]
    if 'example_th' not in columns:
        c.execute("ALTER TABLE vocab ADD COLUMN example_th TEXT DEFAULT ''")
    
    conn.commit()
    conn.close()

def auto_add_word(word, level="User-Added"):
    try:
        dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        pos, pron, ex = "n/a", "/.../", f"Let's use '{word}' in a sentence."
        if dict_res.status_code == 200:
            res = dict_res.json()[0]
            pron = res.get('phonetic', next((p.get('text') for p in res.get('phonetics', []) if p.get('text')), "/.../"))
            meaning = res['meanings'][0]
            pos = meaning['partOfSpeech']
            ex = meaning['definitions'][0].get('example', f"Example sentence for {word}.")
        
        translator = GoogleTranslator(source='en', target='th')
        translation = translator.translate(word)
        example_th = translator.translate(ex)
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""INSERT OR IGNORE INTO vocab 
                     (word, pos, pronunciation, translation, example, example_th, level, next_review) 
                     VALUES (?,?,?,?,?,?,?,?)""",
                  (word.capitalize().strip(), pos, pron, translation, ex, example_th, level, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ... (ฟังก์ชัน update_srs และ UI Setup เหมือนเดิม)

init_db()

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorite", "📊 Stats", "🛡️ Admin / Add Words"])

with tab1:
    conn = sqlite3.connect(DB_NAME)
    today = datetime.now().strftime('%Y-%m-%d')
    due_words = pd.read_sql_query("SELECT * FROM vocab WHERE next_review <= ? LIMIT ?", conn, params=(today, TARGET_BATCH_SIZE))
    
    # ... (ส่วนการแสดงผล Practice และ Quiz เหมือนเดิม)
    # [ระบบจะดึงเฉพาะคำที่ถึงกำหนดจาก DB มาถามวนไปเรื่อยๆ จนกว่าคุณจะจำได้]

with tab4:
    st.subheader("🛡️ ระบบจัดการคำศัพท์")
    
    # --- ส่วนที่เพิ่มใหม่: ไม่ต้องแก้โค้ด แค่เอาศัพท์มาวาง ---
    st.markdown("### 📥 เติมคำศัพท์ใหม่ (ไม่ต้องแก้โค้ด)")
    raw_input = st.text_area("วางคำศัพท์ที่นี่ (คั่นด้วยจุลภาค หรือขึ้นบรรทัดใหม่)", 
                             placeholder="เช่น: Apple, Banana, Cat...", height=150)
    col_a, col_b = st.columns(2)
    lvl_choice = col_a.selectbox("กำหนดระดับ", ["A1", "A2", "B1", "B2", "C1", "Business"])
    
    if col_b.button("🚀 บันทึกเข้าคลังศัพท์", use_container_width=True):
        words_to_add = [w.strip() for w in raw_input.replace('\n', ',').split(',') if w.strip()]
        if words_to_add:
            with st.status("กำลังดึงข้อมูลจาก API และแปลภาษา...") as status:
                for w in words_to_add:
                    auto_add_word(w, lvl_choice)
                status.update(label="เพิ่มคำศัพท์เรียบร้อย!", state="complete")
            st.rerun()

    st.divider()
    if st.button("🗑️ ล้างฐานข้อมูลทั้งหมด (Reset)"):
        conn = sqlite3.connect(DB_NAME); c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS vocab"); conn.commit(); st.rerun()
