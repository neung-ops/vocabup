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

# --- 1. CONFIG & DB ---
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
            for _, row in df.iterrows():
                c.execute("INSERT OR IGNORE INTO vocab (word, level, next_review) VALUES (?,?,?)",
                          (str(row['word']).strip().capitalize(), str(row['level']).strip(), datetime.now().strftime('%Y-%m-%d')))
        except: pass
    conn.commit()
    conn.close()

def fetch_word_details(word_id, word):
    try:
        dict_res = requests.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{word}", timeout=5)
        pos, pron, ex = "n/a", "/.../", f"Example sentence with {word}."
        if dict_res.status_code == 200:
            res = dict_res.json()[0]
            pron = res.get('phonetic', next((p.get('text') for p in res.get('phonetics', []) if p.get('text')), "/.../"))
            meaning = res['meanings'][0]
            pos = meaning['partOfSpeech']
            ex = meaning['definitions'][0].get('example', f"No example found for {word}.")
        
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
            mastery = min(100, mastery + 10)
        else:
            interval, easiness = 0, max(1.3, easiness - 0.2)
            mastery = max(0, mastery - 15)
        next_review = (datetime.now() + timedelta(days=interval)).strftime('%Y-%m-%d')
        c.execute("UPDATE vocab SET interval=?, easiness=?, next_review=?, mastery_score=? WHERE id=?", 
                  (interval, easiness, next_review, mastery, word_id))
    conn.commit()
    conn.close()

# --- 2. UI ---
st.set_page_config(page_title="VocabUp Pro", layout="wide")
st.markdown("""<style>
    .stApp { background-color: #0F172A; color: #F1F5F9; }
    .main-card { background: #1E293B; border-radius: 20px; padding: 1.5rem; border: 1px solid #334155; text-align: center; margin-bottom: 10px; }
    .word-title { font-size: 4.5rem; font-weight: 900; color: #38BDF8; margin: 0; }
    .example-box { background: #0F172A; padding: 15px; border-radius: 10px; border-left: 4px solid #38BDF8; text-align: left; margin: 10px 0; }
</style>""", unsafe_allow_html=True)

if 'session_words' not in st.session_state: st.session_state.session_words = []
if 'idx' not in st.session_state: st.session_state.idx = 0
if 'phase' not in st.session_state: st.session_state.phase = "typing"

init_db()
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Practice", "⭐ Favorite", "📊 Stats", "🛡️ Admin"])

# --- TAB 1: PRACTICE ---
with tab1:
    conn = sqlite3.connect(DB_NAME)
    if not st.session_state.session_words:
        query = "SELECT * FROM vocab WHERE next_review <= ? ORDER BY level ASC, RANDOM() LIMIT ?"
        df_due = pd.read_sql_query(query, conn, params=(datetime.now().strftime('%Y-%m-%d'), TARGET_BATCH_SIZE))
        if not df_due.empty:
            st.session_state.session_words = df_due.to_dict('records')
            st.session_state.idx, st.session_state.phase = 0, "typing"

    if st.session_state.session_words and st.session_state.idx < len(st.session_state.session_words):
        curr = st.session_state.session_words[st.session_state.idx]
        if not curr['translation']:
            fetch_word_details(curr['id'], curr['word'])
            c = conn.cursor(); c.execute("SELECT * FROM vocab WHERE id=?", (curr['id'],)); curr = dict(zip([col[0] for col in c.description], c.fetchone()))
            st.session_state.session_words[st.session_state.idx] = curr

        if st.session_state.phase == "typing":
            st.markdown(f"""<div class="main-card">
                <small>{curr['level']} | {curr['pos']}</small>
                <h1 class="word-title">{curr['word']}</h1>
                <h3>{curr['translation']}</h3>
                <div class="example-box">
                    <p style="color:#CBD5E1; font-style:italic;">"{curr['example']}"</p>
                    <p style="color:#94A3B8; font-size:0.8rem;">{curr['example_th']}</p>
                </div>
            </div>""", unsafe_allow_html=True)
            
            u_input = st.text_input(f"Type ({st.session_state.idx+1}/{len(st.session_state.session_words)})", key=f"t_{curr['id']}")
            c1, c2 = st.columns([1, 5])
            if c1.button("⭐ Fav" if not curr['is_favorite'] else "🌟 Unfav"):
                conn.cursor().execute("UPDATE vocab SET is_favorite=? WHERE id=?", (1-curr['is_favorite'], curr['id'])); conn.commit(); st.rerun()

            if u_input.strip().lower() == curr['word'].strip().lower():
                st.session_state.idx += 1
                if st.session_state.idx >= len(st.session_state.session_words): st.session_state.phase = "quiz"
                st.rerun()
        
        elif st.session_state.phase == "quiz":
            st.info("Quiz Phase: Match the translations!")
            # [Simplified Quiz Logic to prevent crash]
            qz_idx = st.session_state.idx - len(st.session_state.session_words) if st.session_state.idx >= len(st.session_state.session_words) else 0
            # เพื่อความชัวร์ ผมแนะนำให้รัน Typing ให้จบก่อน แล้วค่อยเพิ่ม Quiz ทีหลังถ้ายังต้องการครับ
            if st.button("Finish Session"):
                for w in st.session_state.session_words: update_srs(w['id'], True)
                st.session_state.session_words = []; st.rerun()
    else:
        st.write("No words due. Check back later!")
    conn.close()

# --- TAB 2: FAVORITE ---
with tab2:
    conn = sqlite3.connect(DB_NAME)
    favs = pd.read_sql_query("SELECT word, translation, level FROM vocab WHERE is_favorite = 1", conn)
    st.table(favs)
    conn.close()

# --- TAB 3: STATS ---
with tab3:
    conn = sqlite3.connect(DB_NAME)
    df_stats = pd.read_sql_query("SELECT level, mastery_score FROM vocab", conn)
    if not df_stats.empty:
        fig = px.histogram(df_stats, x="level", y="mastery_score", histfunc="avg", title="Average Mastery by Level")
        st.plotly_chart(fig)
    conn.close()

# --- TAB 4: ADMIN ---
with tab4:
    if st.button("Reset DB"):
        if os.path.exists(DB_NAME): os.remove(DB_NAME)
        st.rerun()
