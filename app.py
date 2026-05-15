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

VOCAB_LEVELS = {
    "A1": ["Always", "Beautiful", "Clean", "Drink", "Eat", "Friend", "Happy", "Learn"],
    "A2": ["Believe", "Choose", "Decide", "Explain", "Forget", "Happen", "Ignore", "Journey"],
    "B1": ["Ability", "Challenge", "Describe", "Evidence", "Focus", "Government", "Healthy", "Improve"],
    "B2": ["Exacerbate", "Paradigm", "Quintessential", "Inherent", "Subjective", "Objective", "Cognitive", "Synthesis"]
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # สร้างตารางพร้อมคอลัมน์ example_th
    c.execute('''CREATE TABLE IF NOT EXISTS vocab 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  word TEXT UNIQUE, pos TEXT, pronunciation TEXT, translation TEXT, 
                  example TEXT, example_th TEXT, level TEXT, interval INTEGER DEFAULT 0, 
                  easiness REAL DEFAULT 2.5, next_review TEXT, 
                  mastery_score INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
    
    # --- ระบบกันระเบิด: ตรวจสอบและเพิ่มคอลัมน์อัตโนมัติถ้าไม่มี ---
    c.execute("PRAGMA table_info(vocab)")
    columns = [column[1] for column in c.fetchall()]
    if 'example_th' not in columns:
        c.execute("ALTER TABLE vocab ADD COLUMN example_th TEXT DEFAULT ''")
    
    c.execute("SELECT COUNT(*) FROM vocab")
    if c.fetchone()[0] == 0:
        with st.spinner("🚀 กำลังเตรียมคลังศัพท์ระดับ A1..."):
            for w in VOCAB_LEVELS["A1"]:
                auto_add_word(w, "A1")
    conn.commit()
    conn.close()

def auto_add_word(word, level):
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
                  (word.capitalize(), pos, pron, translation, ex, example_th, level, datetime.now().strftime('%Y-%m-%d')))
        conn.commit()
        conn.close()
        return True
    except:
        return False

# ฟังก์ชันอื่นๆ คงเดิม...
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

# --- UI SETUP ---
st.set_page_config(page_title="Typist Lexicon Pro", layout="wide")

st.markdown("""
    <script>
    function setupInput() {
        const inputs = window.parent.document.querySelectorAll('input');
        inputs.forEach(input => {
            const label = input.getAttribute('aria-label');
            if (label && label.includes('Type:')) {
                input.setAttribute('autocomplete', 'one-time-code');
                input.setAttribute('autocorrect', 'off');
                input.setAttribute('spellcheck', 'false');
                if (window.parent.document.activeElement !== input) { input.focus(); }
            }
        });
    }
    setInterval(setupInput, 300);
    </script>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 24px; padding: 2rem; border: 1px solid #334155; text-align: center; }
    .word-title { font-size: 5rem; font-weight: 900; color: #38BDF8; margin: 0; letter-spacing: -2px; }
    .trans-txt { font-size: 2.2rem; color: #F8FAFC; margin-bottom: 10px; font-weight: 600; }
    .example-quote { background: #0F172A; padding: 20px; border-radius: 12px; border-left: 5px solid #38BDF8; text-align: left; margin-top: 15px; }
    .ex-en { font-style: italic; color: #CBD5E1; font-size: 1.1rem; }
    .ex-th { color: #94A3B8; font-size: 1rem; margin-top: 5px; }
    
    [data-testid="stTable"] td { color: #FFFFFF !important; background-color: #1E293B !important; }
    [data-testid="stTable"] th { color: #38BDF8 !important; background-color: #0F172A !important; }

    div.stButton > button {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border-radius: 12px; font-weight: bold; border: none;
    }
    div.stButton > button:hover { background-color: #38BDF8 !important; color: #FFFFFF !important; }
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
            # ใช้ .get() เพื่อป้องกันแอปพังถ้าข้อมูลไม่มีค่า
            ex_th = curr.get('example_th', 'ไม่มีคำแปลตัวอย่าง')
            
            st.markdown(f"""<div class="main-card">
                    <p style="color:#94A3B8; font-weight:bold;">LEVEL: {curr['level']} | {curr['pos']} | {curr['pronunciation']}</p>
                    <h1 class="word-title">{curr['word']}</h1>
                    <p class="trans-txt">{curr['translation']}</p>
                    <div class="example-quote">
                        <div class="ex-en">" {curr['example']} "</div>
                        <div class="ex-th">({ex_th})</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            _, c2, _ = st.columns([1,2,1])
            u_input = c2.text_input(f"Type: ({st.session_state.idx+1}/{len(st.session_state.session_words)})", key=f"t_{curr['id']}_{st.session_state.idx}")
            
            if c2.button("⭐ Save to Fav", key=f"f_{curr['id']}"):
                nc = sqlite3.connect(DB_NAME); cur = nc.cursor()
                cur.execute("UPDATE vocab SET is_favorite = ? WHERE id = ?", (1 if curr['is_favorite']==0 else 0, curr['id']))
                nc.commit(); nc.close(); st.rerun()
                
            if u_input.strip().lower() == curr['word'].strip().lower():
                st.session_state.idx += 1
                if st.session_state.idx >= len(st.session_state.session_words): st.session_state.phase = "quiz"
                st.rerun()
        
        elif st.session_state.phase == "quiz":
            qz = st.session_state.session_words[st.session_state.quiz_idx]
            st.markdown(f"<h2 style='text-align:center;'>Meaning of <b>'{qz['word']}'</b>?</h2>", unsafe_allow_html=True)
            c = conn.cursor()
            c.execute("SELECT translation FROM vocab WHERE id != ? ORDER BY RANDOM() LIMIT 3", (qz['id'],))
            opts = [r[0] for r in c.fetchall()] + [qz['translation']]; random.shuffle(opts)
            cols = st.columns(2)
            for i, o in enumerate(opts):
                if cols[i%2].button(o, key=f"q_{i}_{qz['id']}", use_container_width=True):
                    if o.strip() == qz['translation'].strip():
                        update_srs(qz['id'], True); st.session_state.quiz_idx += 1
                        if st.session_state.quiz_idx >= len(st.session_state.session_words):
                            st.balloons(); st.session_state.session_words = []; st.toast("Done!")
                        st.rerun()
                    else:
                        update_srs(qz['id'], False); st.error("Wrong!"); time.sleep(1)
                        st.session_state.phase, st.session_state.idx, st.session_state.quiz_idx = "typing", 0, 0
                        st.rerun()
    else:
        st.info("วันนี้ฝึกครบแล้ว! กดเลือกเติมคำศัพท์ระดับถัดไป:")
        lvl_col1, lvl_col2, lvl_col3, lvl_col4 = st.columns(4)
        if lvl_col1.button("Add A2 words"):
            for w in VOCAB_LEVELS["A2"]: auto_add_word(w, "A2")
            st.rerun()
        if lvl_col2.button("Add B1 words"):
            for w in VOCAB_LEVELS["B1"]: auto_add_word(w, "B1")
            st.rerun()
        if lvl_col3.button("Add B2 words"):
            for w in VOCAB_LEVELS["B2"]: auto_add_word(w, "B2")
            st.rerun()
        if lvl_col4.button("Add A1 (Refill)"):
            for w in VOCAB_LEVELS["A1"]: auto_add_word(w, "A1")
            st.rerun()
    conn.close()

with tab2:
    st.subheader("⭐ Favorites")
    conn = sqlite3.connect(DB_NAME)
    fav_data = pd.read_sql_query("SELECT id, word, translation FROM vocab WHERE is_favorite = 1", conn)
    conn.close()
    if not fav_data.empty:
        for index, row in fav_data.iterrows():
            col1, col2, col3 = st.columns([2, 3, 1])
            col1.write(f"**{row['word']}**")
            col2.write(row['translation'])
            if col3.button("❌ Remove", key=f"del_{row['id']}"):
                conn = sqlite3.connect(DB_NAME); c = conn.cursor()
                c.execute("UPDATE vocab SET is_favorite = 0 WHERE id = ?", (row['id'],))
                conn.commit(); conn.close(); st.rerun()
            st.divider()

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
