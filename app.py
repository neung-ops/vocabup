import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import random
import plotly.express as px
import requests

# --- 1. CONFIGURATION & DATABASE ---
DB_NAME = "lexicon_v4.db"
TARGET_BATCH_SIZE = 3 

# รายชื่อคำตั้งต้น (แค่ตัวอักษร) เพื่อให้ระบบไปดึงข้อมูลจาก API มาเอง ไม่รกโค้ด
INITIAL_WORDS = ["Persistent", "Resilient", "Eloquent", "Advocate", "Mitigate", "Incentive", "Pragmatic", "Ambiguous"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS vocab 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  word TEXT UNIQUE, pos TEXT, pronunciation TEXT, translation TEXT, 
                  example TEXT, level TEXT, interval INTEGER DEFAULT 0, 
                  easiness REAL DEFAULT 2.5, next_review TEXT, 
                  mastery_score INTEGER DEFAULT 0, is_favorite INTEGER DEFAULT 0)''')
    
    # ถ้า DB ว่าง ให้ดึงข้อมูลจาก API สำหรับคำเริ่มต้นทันที
    c.execute("SELECT COUNT(*) FROM vocab")
    if c.fetchone()[0] == 0:
        with st.spinner("Initializing Dictionary Data..."):
            for w in INITIAL_WORDS:
                data = fetch_word_data(w)
                if data:
                    c.execute("""INSERT OR IGNORE INTO vocab 
                                 (word, pos, pronunciation, translation, example, level, next_review) 
                                 VALUES (?,?,?,?,?,?,?)""",
                              (w, data['pos'], data['pronunciation'], "รอเพิ่มคำแปล", data['example'], "B2", 
                               datetime.now().strftime('%Y-%m-%d')))
    conn.commit()
    conn.close()

# --- 2. API INTEGRATION (DictionaryAPI.dev) ---
def fetch_word_data(word):
    """ดึงข้อมูลจาก Dictionary API โดยตรง"""
    try:
        response = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        if response.status_code == 200:
            res = response.json()[0]
            phonetic = res.get('phonetic', '')
            if not phonetic and res.get('phonetics'):
                phonetic = next((p.get('text') for p in res['phonetics'] if p.get('text')), '')
            
            meaning = res['meanings'][0]
            pos = meaning['partOfSpeech']
            definition = meaning['definitions'][0]
            example = definition.get('example', 'No example available in API.')
            
            return {'pos': pos, 'pronunciation': phonetic, 'example': example}
    except: pass
    return None

# --- 3. SRS LOGIC ---
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
        interval = 0 # พลาดแล้วต้องทบทวนใหม่ทันที
        easiness = max(1.3, easiness - 0.2)
        mastery = max(0, mastery - 15)
        
    next_review = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
    c.execute("UPDATE vocab SET interval=?, easiness=?, next_review=?, mastery_score=? WHERE id=?", 
              (interval, easiness, next_review, mastery, word_id))
    conn.commit()
    conn.close()

def toggle_favorite(word_id, current_val):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE vocab SET is_favorite = ? WHERE id = ?", (1 if current_val == 0 else 0, word_id))
    conn.commit()
    conn.close()

# --- 4. UI SETUP ---
st.set_page_config(page_title="Typist Lexicon Pro", layout="wide")

# JavaScript สำหรับการ Focus ช่องพิมพ์แบบ Aggressive
st.markdown("""
    <script>
    function forceFocus() {
        const inputs = window.parent.document.querySelectorAll('input');
        inputs.forEach(input => {
            const label = input.getAttribute('aria-label');
            if (label && label.includes('Type:')) {
                if (window.parent.document.activeElement !== input) {
                    input.focus();
                }
            }
        });
    }
    setInterval(forceFocus, 500);
    </script>
""", unsafe_allow_html=True)

st.markdown("""
    <style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 24px; padding: 3rem; border: 1px solid #334155; text-align: center; }
    .word-title { font-size: 5.5rem; font-weight: 900; color: #38BDF8; margin: 0; letter-spacing: -2px; }
    .phonetic-txt { color: #94A3B8; font-family: monospace; font-size: 1.3rem; margin-bottom: 20px; }
    .trans-txt { font-size: 2.2rem; color: #F8FAFC; margin-bottom: 20px; font-weight: 600; }
    .example-quote { background: #0F172A; padding: 20px; border-radius: 12px; border-left: 5px solid #38BDF8; text-align: left; font-style: italic; color: #CBD5E1; }
    .stButton>button { border-radius: 12px; font-weight: 600; }
    </style>
""", unsafe_allow_html=True)

# --- 5. STATE MANAGEMENT ---
if 'session_words' not in st.session_state: st.session_state.session_words = []
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'phase' not in st.session_state: st.session_state.phase = "typing"
if 'quiz_idx' not in st.session_state: st.session_state.quiz_idx = 0

def start_batch(words):
    st.session_state.session_words = words
    st.session_state.idx = 0
    st.session_state.phase = "typing"
    st.session_state.quiz_idx = 0

# --- 6. MAIN APP ---
init_db()
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorites", "📊 Analytics", "🛡️ Vault"])

with tab1:
    conn = sqlite3.connect(DB_NAME)
    today = datetime.now().strftime('%Y-%m-%d')
    due_words = pd.read_sql_query("SELECT * FROM vocab WHERE next_review <= ? LIMIT ?", conn, params=(today, TARGET_BATCH_SIZE))
    
    if not st.session_state.session_words and not due_words.empty:
        start_batch(due_words.to_dict('records'))

    if st.session_state.session_words:
        if st.session_state.phase == "typing":
            curr = st.session_state.session_words[st.session_state.idx]
            
            # UI Card
            st.markdown(f"""
                <div class="main-card">
                    <p class="phonetic-txt">{curr['level']} | {curr['pos']} | {curr['pronunciation']}</p>
                    <h1 class="word-title">{curr['word']}</h1>
                    <p class="trans-txt">{curr['translation']}</p>
                    <div class="example-quote">" {curr['example']} "</div>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3 = st.columns([1,2,1])
            with c2:
                st.write("")
                user_input = st.text_input(f"Type: ({st.session_state.idx+1}/{len(st.session_state.session_words)})", 
                                          key=f"type_{curr['id']}_{st.session_state.idx}")
                
                # Favorite Star
                star_label = "⭐ Remove Favorite" if curr['is_favorite'] else "☆ Add Favorite"
                if st.button(star_label, key=f"fav_{curr['id']}"):
                    toggle_favorite(curr['id'], curr['is_favorite'])
                    st.rerun()

                if user_input.strip().lower() == curr['word'].lower():
                    st.session_state.idx += 1
                    if st.session_state.idx >= len(st.session_state.session_words):
                        st.session_state.phase = "quiz"
                    st.rerun()

        elif st.session_state.phase == "quiz":
            qz = st.session_state.session_words[st.session_state.quiz_idx]
            st.markdown(f"<h2 style='text-align:center;'>What is the meaning of <b>'{qz['word']}'</b>?</h2>", unsafe_allow_html=True)
            
            # Logic ตัวหลอก
            c = conn.cursor()
            c.execute("SELECT translation FROM vocab WHERE id != ? ORDER BY RANDOM() LIMIT 3", (qz['id'],))
            opts = [r[0] for r in c.fetchall()] + [qz['translation']]
            random.shuffle(opts)
            
            cols = st.columns(2)
            for i, o in enumerate(opts):
                if cols[i%2].button(o, key=f"opt_{i}_{qz['id']}", use_container_width=True):
                    if o == qz['translation']:
                        update_srs(qz['id'], True)
                        st.session_state.quiz_idx += 1
                        if st.session_state.quiz_idx >= len(st.session_state.session_words):
                            st.balloons()
                            st.session_state.session_words = []
                            st.success("Batch Completed! Mastery Increased.")
                            time.sleep(1.5)
                        st.rerun()
                    else:
                        update_srs(qz['id'], False)
                        st.error(f"Incorrect! Back to typing: '{qz['word']}'")
                        time.sleep(2)
                        st.session_state.phase = "typing"
                        st.session_state.idx = 0
                        st.session_state.quiz_idx = 0
                        st.rerun()
    else:
        st.info("No words due. You can unlock new words in the Vault or wait for tomorrow!")
        if st.button("Unlock 5 New Words"):
            new_words = ["Challenge", "Prosper", "Vibrant", "Obscure", "Tenacious"]
            c = conn.cursor()
            for nw in new_words:
                api = fetch_word_data(nw)
                if api:
                    c.execute("INSERT OR IGNORE INTO vocab (word, pos, pronunciation, translation, example, level, next_review) VALUES (?,?,?,?,?,?,?)",
                              (nw, api['pos'], api['pronunciation'], "รอแปล", api['example'], "B2", today))
            conn.commit()
            st.rerun()
    conn.close()

with tab2:
    st.subheader("⭐ Your Starred Words")
    conn = sqlite3.connect(DB_NAME)
    df_fav = pd.read_sql_query("SELECT word, translation, level, mastery_score FROM vocab WHERE is_favorite = 1", conn)
    conn.close()
    if not df_fav.empty:
        st.table(df_fav)
    else:
        st.write("No favorite words yet. Click the star during practice!")

with tab3:
    st.subheader("📊 Performance Analytics")
    conn = sqlite3.connect(DB_NAME)
    df_all = pd.read_sql_query("SELECT word, mastery_score FROM vocab", conn)
    conn.close()
    if not df_all.empty:
        fig = px.bar(df_all, x='word', y='mastery_score', color='mastery_score', title="Vocabulary Mastery")
        st.plotly_chart(fig, use_container_width=True)

with tab4:
    st.subheader("🛡️ Lexicon Vault")
    conn = sqlite3.connect(DB_NAME)
    df_v = pd.read_sql_query("SELECT id, word, translation, level, next_review FROM vocab", conn)
    st.dataframe(df_v, use_container_width=True)
    
    if st.button("Clear Database (Reset)"):
        c = conn.cursor()
        c.execute("DROP TABLE IF EXISTS vocab")
        conn.commit()
        st.rerun()
    conn.close()
