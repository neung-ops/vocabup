import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import random
import os
import requests
from deep_translator import GoogleTranslator
import plotly.express as px
import streamlit.components.v1 as components

# --- 1. CONFIG ---
DB_NAME = "lexicon_v5.db"
CSV_FILE = "my_vocab.csv"
TARGET_BATCH_SIZE = 5  # ปรับเป็น 10 ตามที่คุณต้องการแล้ว

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
            for _, row in df.iterrows():
                c.execute("INSERT OR IGNORE INTO vocab (word, level, next_review) VALUES (?,?,?)",
                          (str(row['word']).strip().capitalize(), str(row['level']).strip(), datetime.now().strftime('%Y-%m-%d')))
        except: pass
    conn.commit()
    conn.close()

def fetch_word_details(word_id, word):
    try:
        dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        pos, pron, ex = "n/a", "/.../", f"Practice using '{word}'."
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
    except: return False

def update_srs(word_id, success):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT interval, easiness, mastery_score FROM vocab WHERE id = ?", (word_id,))
    res = c.fetchone()
    if res:
        interval, easiness, mastery = res
        if success:
            interval = 1 if interval == 0 else (3 if interval == 1 else int(interval * easiness))
            easiness = min(3.0, easiness + 0.1)
            mastery = min(100, mastery + 5)
        else:
            interval, easiness, mastery = 0, max(1.3, easiness - 0.2), max(0, mastery - 10)
        next_review = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
        c.execute("UPDATE vocab SET interval=?, easiness=?, next_review=?, mastery_score=? WHERE id=?", 
                  (interval, easiness, next_review, mastery, word_id))
    conn.commit()
    conn.close()

# --- 2. UI SETUP ---
st.set_page_config(page_title="VocabUp Pro", layout="wide")

st.markdown("""<style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 24px; padding: 2.5rem; border: 2px solid #38BDF8; text-align: center; margin-bottom: 20px; }
    .word-title { font-size: 5rem; font-weight: 900; color: #FFFFFF; margin: 0; }
    .pronunciation { font-size: 1.5rem; color: #38BDF8; font-family: monospace; margin-bottom: 10px; }
    .translation { font-size: 2.5rem; color: #F8FAFC; font-weight: bold; margin: 15px 0; }
    .example-box { background: #0F172A; padding: 20px; border-radius: 12px; border-left: 6px solid #38BDF8; text-align: left; }
    .stTextInput input { font-size: 1.5rem !important; text-align: center !important; color: #FFFFFF !important; }
    #MainMenu, footer, header {visibility: hidden;}
</style>""", unsafe_allow_html=True)

# Auto-focus Script
components.html("""<script>
    setInterval(() => {
        const input = window.parent.document.querySelector('input[type="text"]');
        if (input && document.activeElement !== input) input.focus();
    }, 500);
</script>""", height=0)

if 'session_words' not in st.session_state: st.session_state.session_words = []
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'phase' not in st.session_state: st.session_state.phase = "typing"
if 'quiz_idx' not in st.session_state: st.session_state.quiz_idx = 0

init_db()
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorite", "📊 Stats", "🛡️ Admin"])

with tab1:
    conn = sqlite3.connect(DB_NAME)
    
    # Load Batch
    if not st.session_state.session_words:
        query = "SELECT * FROM vocab WHERE next_review <= ? ORDER BY level ASC, RANDOM() LIMIT ?"
        df_due = pd.read_sql_query(query, conn, params=(datetime.now().strftime('%Y-%m-%d'), TARGET_BATCH_SIZE))
        if not df_due.empty:
            st.session_state.session_words = df_due.to_dict('records')
            st.session_state.idx = 0
            st.session_state.quiz_idx = 0
            st.session_state.phase = "typing"

    if st.session_state.session_words:
        # Phase 1: Typing
        if st.session_state.phase == "typing" and st.session_state.idx < len(st.session_state.session_words):
            curr = st.session_state.session_words[st.session_state.idx]
            
            if not curr['translation']:
                fetch_word_details(curr['id'], curr['word'])
                c = conn.cursor(); c.execute("SELECT * FROM vocab WHERE id=?", (curr['id'],)); curr = dict(zip([col[0] for col in c.description], c.fetchone()))
                st.session_state.session_words[st.session_state.idx] = curr

            st.markdown(f"""<div class="main-card">
                <div style="color: #94A3B8; font-weight: bold;">{curr['level']} | {curr['pos']}</div>
                <div class="pronunciation">{curr['pronunciation']}</div>
                <h1 class="word-title">{curr['word']}</h1>
                <div class="translation">{curr['translation']}</div>
                <div class="example-box">
                    <div style="color:#CBD5E1; font-style:italic;">"{curr['example']}"</div>
                    <div style="color:#38BDF8; margin-top: 5px;">{curr['example_th']}</div>
                </div>
            </div>""", unsafe_allow_html=True)
            
            col_fav, _ = st.columns([1, 4])
            fav_text = "🌟 Unfavorite" if curr['is_favorite'] else "⭐ Favorite"
            if col_fav.button(fav_text, key=f"fav_{curr['id']}"):
                conn.cursor().execute("UPDATE vocab SET is_favorite=? WHERE id=?", (1-curr['is_favorite'], curr['id'])); conn.commit(); st.rerun()

            u_input = st.text_input(f"Typing: {st.session_state.idx+1}/{len(st.session_state.session_words)}", key=f"in_{curr['id']}")
            if u_input.strip().lower() == curr['word'].strip().lower():
                st.session_state.idx += 1
                if st.session_state.idx >= len(st.session_state.session_words):
                    st.session_state.phase = "quiz"
                st.rerun()

        # Phase 2: Quiz (Multiple Choice)
        elif st.session_state.phase == "quiz" and st.session_state.quiz_idx < len(st.session_state.session_words):
            qz = st.session_state.session_words[st.session_state.quiz_idx]
            st.markdown(f"<div class='main-card'><h2 style='color:#38BDF8;'>Quiz: {st.session_state.quiz_idx+1}/{len(st.session_state.session_words)}</h2><h1 class='word-title'>{qz['word']}</h1><p>แปลว่าอะไร?</p></div>", unsafe_allow_html=True)
            
            # Get options
            c = conn.cursor()
            c.execute("SELECT translation FROM vocab WHERE id != ? AND translation IS NOT NULL ORDER BY RANDOM() LIMIT 3", (qz['id'],))
            wrong_opts = [r[0] for r in c.fetchall()]
            options = list(set(wrong_opts + [qz['translation']]))
            random.shuffle(options)
            
            cols = st.columns(2)
            for i, opt in enumerate(options):
                if cols[i%2].button(opt, key=f"opt_{i}_{qz['id']}", use_container_width=True):
                    if opt == qz['translation']:
                        update_srs(qz['id'], True)
                        st.session_state.quiz_idx += 1
                        if st.session_state.quiz_idx >= len(st.session_state.session_words):
                            st.balloons()
                            st.session_state.session_words = []
                            st.rerun()
                        st.rerun()
                    else:
                        st.error(f"ผิด! '{qz['word']}' แปลว่า '{qz['translation']}'")
                        update_srs(qz['id'], False)
                        time.sleep(1.5)
                        # ผิดปุ๊บ กลับไปเริ่ม Typing ใหม่ทั้ง Batch เพื่อความแม่น
                        st.session_state.phase, st.session_state.idx, st.session_state.quiz_idx = "typing", 0, 0
                        st.rerun()
    else:
        st.info("No words left for today! Try adding more or Reset DB.")
    conn.close()

# --- TAB 2, 3, 4 (เหมือนเดิมแต่ครบถ้วน) ---
with tab2:
    st.subheader("⭐ My Favorites")
    conn = sqlite3.connect(DB_NAME)
    fav_df = pd.read_sql_query("SELECT id, word, pronunciation, translation FROM vocab WHERE is_favorite=1", conn)
    for _, r in fav_df.iterrows():
        c1, c2 = st.columns([5, 1])
        c1.write(f"**{r['word']}** {r['pronunciation']} - {r['translation']}")
        if c2.button("🗑️", key=f"fdel_{r['id']}"):
            conn.cursor().execute("UPDATE vocab SET is_favorite=0 WHERE id=?", (r['id'],)); conn.commit(); st.rerun()
    conn.close()

with tab3:
    st.subheader("📊 Statistics")
    conn = sqlite3.connect(DB_NAME)
    df_s = pd.read_sql_query("SELECT level, mastery_score FROM vocab WHERE mastery_score > 0", conn)
    if not df_s.empty:
        fig = px.bar(df_s.groupby("level").mean().reset_index(), x="level", y="mastery_score", color="level", range_y=[0,100])
        st.plotly_chart(fig, use_container_width=True)
    conn.close()

with tab4:
    if st.button("🚨 Reset Database"):
        if os.path.exists(DB_NAME): os.remove(DB_NAME)
        st.rerun()
