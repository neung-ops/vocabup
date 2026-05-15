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
INITIAL_WORDS = ["Exacerbate", "Paradigm", "Quintessential", "Inherent", "Subjective", "Objective", "Cognitive", "Synthesis"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vocab 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  word TEXT UNIQUE, pos TEXT, pronunciation TEXT, translation TEXT, 
                  example TEXT, level TEXT, interval INTEGER DEFAULT 0, 
                  easiness REAL DEFAULT 2.5, next_review TEXT, 
                  mastery_score INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
    c.execute("SELECT COUNT(*) FROM vocab")
    if c.fetchone()[0] == 0:
        with st.spinner("🚀 กำลังเตรียมคลังศัพท์..."):
            for w in INITIAL_WORDS:
                auto_add_word(w, "B2")
    conn.commit()
    conn.close()

def auto_add_word(word, level="B2"):
    try:
        dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        pos, pron, ex = "n/a", "/.../", "No example available."
        if dict_res.status_code == 200:
            res = dict_res.json()[0]
            pron = res.get('phonetic', next((p.get('text') for p in res.get('phonetics', []) if p.get('text')), "/.../"))
            meaning = res['meanings'][0]
            pos = meaning['partOfSpeech']
            ex = meaning['definitions'][0].get('example', 'Commonly used context.')
        translation = GoogleTranslator(source='en', target='th').translate(word)
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("""INSERT OR IGNORE INTO vocab 
                     (word, pos, pronunciation, translation, example, level, next_review) 
                     VALUES (?,?,?,?,?,?,?)""",
                  (word.capitalize(), pos, pron, translation, ex, level, datetime.now().strftime('%Y-%m-%d')))
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

# JavaScript แก้ไข 2 จุด: 1. Auto Focus 2. ปิด Autocomplete (บับเบิ้ล)
st.markdown("""
    <script>
    function setupInput() {
        const inputs = window.parent.document.querySelectorAll('input');
        inputs.forEach(input => {
            const label = input.getAttribute('aria-label');
            if (label && label.includes('Type:')) {
                // ปิดบับเบิ้ลช่วยสะกด
                input.setAttribute('autocomplete', 'off');
                input.setAttribute('autocorrect', 'off');
                input.setAttribute('spellcheck', 'false');
                // บังคับ Focus
                if (window.parent.document.activeElement !== input) {
                    input.focus();
                }
            }
        });
    }
    setInterval(setupInput, 500);
    </script>
""", unsafe_allow_html=True)

# แก้ไขสีปุ่มให้สว่างขึ้น (พื้นขาว ตัวดำ) เพื่อให้อ่านง่าย
st.markdown("""
    <style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 24px; padding: 3rem; border: 1px solid #334155; text-align: center; }
    .word-title { font-size: 5rem; font-weight: 900; color: #38BDF8; margin: 0; letter-spacing: -2px; }
    .trans-txt { font-size: 2.2rem; color: #F8FAFC; margin-bottom: 20px; font-weight: 600; }
    .example-quote { background: #0F172A; padding: 20px; border-radius: 12px; border-left: 5px solid #38BDF8; text-align: left; font-style: italic; color: #CBD5E1; }
    
    /* แก้ไขสีปุ่ม Streamlit ให้ตัดกับพื้นหลัง */
    div.stButton > button {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-radius: 10px;
        border: none;
        font-weight: bold;
        width: 100%;
    }
    div.stButton > button:hover {
        background-color: #38BDF8 !important;
        color: #FFFFFF !important;
    }
    </style>
""", unsafe_allow_html=True)

if 'session_words' not in st.session_state: st.session_state.session_words = []
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'phase' not in st.session_state: st.session_state.phase = "typing"
if 'quiz_idx' not in st.session_state: st.session_state.quiz_idx = 0

init_db()

tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorite", "📊 Stats", "🛡️ Admin"])

with tab1:
    conn = sqlite3.connect(DB_NAME)
    today = datetime.now().strftime('%Y-%m-%d')
    due_words = pd.read_sql_query("SELECT * FROM vocab WHERE next_review <= ? LIMIT ?", conn, params=(today, TARGET_BATCH_SIZE))
    
    if not st.session_state.session_words and not due_words.empty:
        st.session_state.session_words = due_words.to_dict('records')
        st.session_state.idx, st.session_state.phase, st.session_state.quiz_idx = 0, "typing", 0

    if st.session_state.session_words:
        if st.session_state.phase == "typing":
            curr = st.session_state.session_words[st.session_state.idx]
            st.markdown(f"""<div class="main-card">
                    <p style="color:#94A3B8;">{curr['level']} | {curr['pos']} | {curr['pronunciation']}</p>
                    <h1 class="word-title">{curr['word']}</h1>
                    <p class="trans-txt">{curr['translation']}</p>
                    <div class="example-quote">" {curr['example']} "</div>
                </div>""", unsafe_allow_html=True)
            _, c2, _ = st.columns([1,2,1])
            # เพิ่มช่องว่างด้านบนช่องพิมพ์
            st.write("")
            u_input = c2.text_input(f"Type: ({st.session_state.idx+1}/{len(st.session_state.session_words)})", key=f"t_{curr['id']}_{st.session_state.idx}")
            
            st.write("")
            if c2.button("⭐ Save Favorite", key=f"f_{curr['id']}"):
                nc = sqlite3.connect(DB_NAME); cur = nc.cursor()
                cur.execute("UPDATE vocab SET is_favorite = ? WHERE id = ?", (1 if curr['is_favorite']==0 else 0, curr['id']))
                nc.commit(); nc.close(); st.rerun()

            if u_input.strip().lower() == curr['word'].lower():
                st.session_state.idx += 1
                if st.session_state.idx >= len(st.session_state.session_words): st.session_state.phase = "quiz"
                st.rerun()
        
        elif st.session_state.phase == "quiz":
            qz = st.session_state.session_words[st.session_state.quiz_idx]
            st.markdown(f"<h2 style='text-align:center;'>ความหมายของ <b>'{qz['word']}'</b>?</h2>", unsafe_allow_html=True)
            c = conn.cursor()
            c.execute("SELECT translation FROM vocab WHERE id != ? ORDER BY RANDOM() LIMIT 3", (qz['id'],))
            opts = [r[0] for r in c.fetchall()] + [qz['translation']]; random.shuffle(opts)
            cols = st.columns(2)
            for i, o in enumerate(opts):
                if cols[i%2].button(o, key=f"q_{i}_{qz['id']}", use_container_width=True):
                    if o == qz['translation']:
                        update_srs(qz['id'], True); st.session_state.quiz_idx += 1
                        if st.session_state.quiz_idx >= len(st.session_state.session_words):
                            st.balloons(); st.session_state.session_words = []; st.toast("Done!"); time.sleep(1)
                        st.rerun()
                    else:
                        update_srs(qz['id'], False); st.error("Wrong!"); time.sleep(1)
                        st.session_state.phase, st.session_state.idx, st.session_state.quiz_idx = "typing", 0, 0
                        st.rerun()
    else:
        st.info("No words! Click to add:")
        if st.button("📦 Add 5 Random Words"):
            new_list = ["Innovative", "Collaboration", "Pragmatic", "Intuition", "Legacy"]
            for nw in new_list: auto_add_word(nw)
            st.rerun()
    conn.close()

with tab2:
    st.subheader("⭐ Favorites")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT word, translation FROM vocab WHERE is_favorite = 1", conn)
    st.table(df); conn.close()

with tab3:
    st.subheader("📊 Analytics")
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query("SELECT word, mastery_score FROM vocab", conn)
    if not df.empty: st.plotly_chart(px.bar(df, x='word', y='mastery_score'))
    conn.close()

with tab4:
    st.subheader("🛡️ Admin")
    if st.button("Reset Database"):
        conn = sqlite3.connect(DB_NAME); c = conn.cursor(); c.execute("DROP TABLE IF EXISTS vocab"); conn.commit(); st.rerun()
