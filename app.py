import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import random
import os
import requests
from deep_translator import GoogleTranslator

# --- 1. CONFIG ---
DB_NAME = "lexicon_v5.db"
CSV_FILE = "my_vocab.csv"
TARGET_BATCH_SIZE = 5

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vocab 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  word TEXT UNIQUE, pos TEXT, pronunciation TEXT, translation TEXT, 
                  example TEXT, example_th TEXT, level TEXT, interval INTEGER DEFAULT 0, 
                  easiness REAL DEFAULT 2.5, next_review TEXT, 
                  mastery_score INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
    
    if os.path.exists(CSV_FILE):
        try:
            df = pd.read_csv(CSV_FILE)
            if 'word' in df.columns and 'level' in df.columns:
                for _, row in df.iterrows():
                    c.execute("INSERT OR IGNORE INTO vocab (word, level, next_review) VALUES (?,?,?)",
                              (str(row['word']).strip().capitalize(), str(row['level']).strip(), datetime.now().strftime('%Y-%m-%d')))
        except Exception as e:
            st.error(f"Error reading CSV: {e}")
    conn.commit()
    conn.close()

def fetch_word_details(word_id, word):
    try:
        dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        pos, pron, ex = "n/a", "/.../", f"Let's learn the word '{word}'."
        if dict_res.status_code == 200:
            res = dict_res.json()[0]
            pron = res.get('phonetic', next((p.get('text') for p in res.get('phonetics', []) if p.get('text')), "/.../"))
            meaning = res['meanings'][0]
            pos = meaning['partOfSpeech']
            ex = meaning['definitions'][0].get('example', f"Example sentence with {word}.")
        
        translator = GoogleTranslator(source='en', target='th')
        translation = translator.translate(word)
        example_th = translator.translate(ex)
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("UPDATE vocab SET pos=?, pronunciation=?, translation=?, example=?, example_th=? WHERE id=?",
                  (pos, pron, translation, ex, example_th, word_id))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def update_srs(word_id, success):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT interval, easiness, mastery_score FROM vocab WHERE id = ?", (word_id,))
    res = c.fetchone()
    if not res: return
    interval, easiness, mastery = res
    if success:
        interval = 1 if interval == 0 else (3 if interval == 1 else int(interval * easiness))
        easiness = min(3.0, easiness + 0.1)
        mastery = min(100, mastery + 10)
    else:
        interval = 0
        easiness = max(1.3, easiness - 0.2)
        mastery = max(0, mastery - 15)
    next_review = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
    c.execute("UPDATE vocab SET interval=?, easiness=?, next_review=?, mastery_score=? WHERE id=?", 
              (interval, easiness, next_review, mastery, word_id))
    conn.commit()
    conn.close()

# --- 2. UI SETUP ---
st.set_page_config(page_title="Typist Lexicon Pro", layout="wide")

st.markdown("""<style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 24px; padding: 2rem; border: 1px solid #334155; text-align: center; }
    .word-title { font-size: 5rem; font-weight: 900; color: #38BDF8; margin: 0; letter-spacing: -2px; }
    .trans-txt { font-size: 2.2rem; color: #F8FAFC; font-weight: 600; }
    div.stButton > button { background-color: #FFFFFF !important; color: #0F172A !important; border-radius: 12px; font-weight: bold; }
</style>""", unsafe_allow_html=True)

if 'session_words' not in st.session_state: st.session_state.session_words = []
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'phase' not in st.session_state: st.session_state.phase = "typing"
if 'quiz_idx' not in st.session_state: st.session_state.quiz_idx = 0

init_db()

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorite", "📊 Stats", "🛡️ Admin"])

with tab1:
    conn = sqlite3.connect(DB_NAME)
    today = datetime.now().strftime('%Y-%m-%d')

    # แก้ไขจุดนี้: สุ่มคำ (RANDOM) โดยเรียงตามเลเวล (ORDER BY level)
    if not st.session_state.session_words:
        query = """SELECT * FROM vocab 
                   WHERE next_review <= ? 
                   ORDER BY level ASC, RANDOM() 
                   LIMIT ?"""
        due_words = pd.read_sql_query(query, conn, params=(today, TARGET_BATCH_SIZE))
        if not due_words.empty:
            st.session_state.session_words = due_words.to_dict('records')
            st.session_state.idx = 0
            st.session_state.phase = "typing"
            st.session_state.quiz_idx = 0

    # ป้องกัน IndexError: ตรวจสอบว่ามีข้อมูลใน list และ index ไม่เกินขอบเขต
    if st.session_state.session_words and st.session_state.idx < len(st.session_state.session_words):
        curr = st.session_state.session_words[st.session_state.idx]
        
        # Lazy Loading details
        if pd.isna(curr['translation']) or curr['translation'] is None:
            with st.spinner(f"Loading {curr['word']}..."):
                fetch_word_details(curr['id'], curr['word'])
                c = conn.cursor()
                c.execute("SELECT * FROM vocab WHERE id = ?", (curr['id'],))
                curr = dict(zip([col[0] for col in c.description], c.fetchone()))
                st.session_state.session_words[st.session_state.idx] = curr

        if st.session_state.phase == "typing":
            st.markdown(f"""<div class="main-card">
                    <p style="color:#94A3B8;">{curr['level']} | {curr['pos']} | {curr['pronunciation']}</p>
                    <h1 class="word-title">{curr['word']}</h1>
                    <p class="trans-txt">{curr['translation']}</p>
                </div>""", unsafe_allow_html=True)
            
            _, c2, _ = st.columns([1,2,1])
            u_input = c2.text_input(f"คำที่ {st.session_state.idx+1}/{len(st.session_state.session_words)}", key=f"t_{curr['id']}")
            
            if u_input.strip().lower() == curr['word'].strip().lower():
                st.session_state.idx += 1
                if st.session_state.idx >= len(st.session_state.session_words):
                    st.session_state.phase = "quiz"
                st.rerun()
        
        elif st.session_state.phase == "quiz":
            if st.session_state.quiz_idx < len(st.session_state.session_words):
                qz = st.session_state.session_words[st.session_state.quiz_idx]
                st.markdown(f"<h2 style='text-align:center;'>ความหมายของ <b>'{qz['word']}'</b> คือ?</h2>", unsafe_allow_html=True)
                
                # สุ่มตัวเลือก
                c = conn.cursor()
                c.execute("SELECT translation FROM vocab WHERE id != ? AND translation IS NOT NULL ORDER BY RANDOM() LIMIT 3", (qz['id'],))
                opts = [r[0] for r in c.fetchall()] + [qz['translation']]
                random.shuffle(opts)
                
                cols = st.columns(2)
                for i, o in enumerate(opts):
                    if cols[i%2].button(o, key=f"q_{i}_{qz['id']}", use_container_width=True):
                        if o.strip() == qz['translation'].strip():
                            update_srs(qz['id'], True)
                            st.session_state.quiz_idx += 1
                            if st.session_state.quiz_idx >= len(st.session_state.session_words):
                                st.balloons()
                                st.session_state.session_words = [] # เคลียร์เพื่อโหลดชุดใหม่
                                st.rerun()
                            st.rerun()
                        else:
                            update_srs(qz['id'], False)
                            st.error("ผิดครับ! ต้องกลับไปซ้อมพิมพ์ใหม่")
                            time.sleep(1)
                            st.session_state.phase, st.session_state.idx, st.session_state.quiz_idx = "typing", 0, 0
                            st.rerun()
    else:
        st.success("เยี่ยมมาก! คุณเรียนครบชุดในตอนนี้แล้ว")
        if st.button("เริ่มชุดถัดไป"):
            st.session_state.session_words = []
            st.rerun()

    conn.close()

with tab4:
    if st.button("ล้างฐานข้อมูล (Reset Database)"):
        if os.path.exists(DB_NAME): os.remove(DB_NAME)
        st.rerun()
