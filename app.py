import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import random

from srs_engine import (
    load_data, save_data, update_word,
    get_due_words, get_weak_words, get_stats, get_word_state
)
from gemini_client import generate_word_question, generate_review_question

# ─────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="VocabUp 🧠",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─────────────────────────────────────────────
# Custom CSS
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;700;800&family=Noto+Sans+Thai:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans Thai', 'Syne', sans-serif;
}

/* Dark background */
.stApp {
    background: #0d0f14;
    color: #e8e8f0;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #13151c;
    border-right: 1px solid #1e2130;
}

/* Cards */
.card {
    background: #13151c;
    border: 1px solid #1e2130;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 16px;
}

.card-accent {
    background: linear-gradient(135deg, #1a1d2e 0%, #13151c 100%);
    border: 1px solid #2a3060;
    border-radius: 16px;
    padding: 28px;
    margin-bottom: 16px;
}

/* Big word display */
.big-word {
    font-family: 'Syne', sans-serif;
    font-size: 3.5rem;
    font-weight: 800;
    color: #7c9eff;
    letter-spacing: -1px;
    line-height: 1.1;
}

.word-thai {
    font-size: 1.4rem;
    color: #a0a8c0;
    font-weight: 300;
    margin-top: 4px;
}

/* Sentence */
.sentence-box {
    background: #0a0c12;
    border-left: 3px solid #7c9eff;
    border-radius: 0 12px 12px 0;
    padding: 18px 22px;
    font-size: 1.15rem;
    color: #c8cfe8;
    margin: 16px 0;
    line-height: 1.7;
}

.sentence-thai {
    color: #6b7494;
    font-size: 0.95rem;
    margin-top: 6px;
}

/* Quiz options */
.option-btn {
    width: 100%;
    text-align: left;
    background: #1a1d2e;
    border: 1px solid #2a2f45;
    border-radius: 12px;
    padding: 16px 20px;
    color: #c8cfe8;
    font-size: 1rem;
    cursor: pointer;
    transition: all 0.2s;
    margin-bottom: 10px;
}

/* Status badges */
.badge-new     { background:#1e3a5f; color:#60a5fa; padding:4px 12px; border-radius:20px; font-size:0.8rem; }
.badge-learn   { background:#3d2e00; color:#fbbf24; padding:4px 12px; border-radius:20px; font-size:0.8rem; }
.badge-known   { background:#0d3d2e; color:#34d399; padding:4px 12px; border-radius:20px; font-size:0.8rem; }
.badge-review  { background:#3d1a2e; color:#f472b6; padding:4px 12px; border-radius:20px; font-size:0.8rem; }

/* Stat number */
.stat-number {
    font-family: 'Syne', sans-serif;
    font-size: 2.8rem;
    font-weight: 800;
    color: #7c9eff;
    line-height: 1;
}
.stat-label {
    font-size: 0.85rem;
    color: #6b7494;
    margin-top: 4px;
}

/* Result correct/wrong */
.result-correct {
    background: linear-gradient(135deg, #0d3d2e, #0f2d20);
    border: 1px solid #34d399;
    border-radius: 12px;
    padding: 20px;
    color: #34d399;
    font-size: 1.1rem;
    margin: 12px 0;
}
.result-wrong {
    background: linear-gradient(135deg, #3d1a1a, #2d0f0f);
    border: 1px solid #f87171;
    border-radius: 12px;
    padding: 20px;
    color: #f87171;
    font-size: 1.1rem;
    margin: 12px 0;
}

/* Review banner */
.review-banner {
    background: linear-gradient(90deg, #3d1a2e, #1a1d2e);
    border: 1px solid #f472b6;
    border-radius: 12px;
    padding: 14px 20px;
    color: #f9a8d4;
    font-size: 0.95rem;
    margin-bottom: 16px;
}

/* Hide streamlit default elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Session state init
# ─────────────────────────────────────────────
if "data" not in st.session_state:
    st.session_state.data = load_data()
if "question" not in st.session_state:
    st.session_state.question = None
if "answered" not in st.session_state:
    st.session_state.answered = False
if "selected" not in st.session_state:
    st.session_state.selected = None
if "is_review" not in st.session_state:
    st.session_state.is_review = False
if "seen_words" not in st.session_state:
    st.session_state.seen_words = []

# ─────────────────────────────────────────────
# Sidebar navigation
# ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🧠 VocabUp")
    st.markdown("---")
    page = st.radio(
        "เมนู",
        ["🎮 เล่นเลย", "📊 Dashboard"],
        label_visibility="collapsed"
    )
    st.markdown("---")

    # Quick stats in sidebar
    stats = get_stats(st.session_state.data)
    st.markdown(f"""
    <div style='text-align:center; padding: 8px 0;'>
        <div style='font-size:2rem; font-weight:800; color:#7c9eff; font-family:Syne,sans-serif;'>{stats["streak"]} 🔥</div>
        <div style='font-size:0.8rem; color:#6b7494;'>วันติดต่อกัน</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown("")

    due_words = get_due_words(st.session_state.data)
    if due_words:
        st.markdown(f"<div class='badge-review'>📬 มีคำรอ review {len(due_words)} คำ</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(f"<div style='color:#6b7494; font-size:0.8rem;'>คำทั้งหมด: <b style='color:#c8cfe8'>{stats['total']}</b></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#6b7494; font-size:0.8rem;'>🟢 จำได้แล้ว: <b style='color:#34d399'>{stats['known']}</b></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#6b7494; font-size:0.8rem;'>🟡 กำลังเรียน: <b style='color:#fbbf24'>{stats['learning']}</b></div>", unsafe_allow_html=True)
    st.markdown(f"<div style='color:#6b7494; font-size:0.8rem;'>🔵 ใหม่: <b style='color:#60a5fa'>{stats['new']}</b></div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# Helper: load next question
# ─────────────────────────────────────────────
def load_next_question():
    st.session_state.answered = False
    st.session_state.selected = None
    data = st.session_state.data

    # Check if there are due words to review first
    due = get_due_words(data)
    if due and random.random() < 0.4:   # 40% chance to review due word
        word_state = due[0]
        st.session_state.is_review = True
        with st.spinner("⏳ กำลังโหลดคำ review..."):
            q = generate_review_question(word_state["word"], word_state.get("word_th", ""))
        st.session_state.question = q
    else:
        st.session_state.is_review = False
        with st.spinner("⏳ กำลังสร้างคำศัพท์ใหม่..."):
            q = generate_word_question(exclude_words=st.session_state.seen_words)
        st.session_state.question = q
        if q:
            st.session_state.seen_words.append(q["word"])
            if len(st.session_state.seen_words) > 30:
                st.session_state.seen_words = st.session_state.seen_words[-30:]

# ─────────────────────────────────────────────
# PAGE: เล่นเลย
# ─────────────────────────────────────────────
if page == "🎮 เล่นเลย":
    st.markdown("# 🎮 Word in Context")
    st.markdown("<p style='color:#6b7494;'>เห็นคำในประโยคจริง แล้วเลือกคำที่ถูกต้อง</p>", unsafe_allow_html=True)

    # Auto-load first question
    if st.session_state.question is None:
        load_next_question()
        st.rerun()

    q = st.session_state.question

    if q:
        # Review banner
        if st.session_state.is_review:
            st.markdown("""
            <div class='review-banner'>
                🔄 <b>Review Mode</b> — คำนี้คุณเคยตอบผิดมาก่อน ลองอีกครั้ง!
            </div>
            """, unsafe_allow_html=True)

        # Word display
        st.markdown(f"""
        <div class='card-accent'>
            <div class='big-word'>{q['word']}</div>
            <div class='word-thai'>{q['word_th']}</div>
        </div>
        """, unsafe_allow_html=True)

        # Sentence with blank
        if not st.session_state.answered:
            st.markdown(f"""
            <div class='sentence-box'>
                📝 {q['blank_sentence']}
                <div class='sentence-thai'>{q['sentence_th']}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("#### เลือกคำที่เหมาะสมที่สุด:")

            # Shuffle options once per question
            if "shuffled_options" not in st.session_state or st.session_state.get("last_word") != q["word"]:
                opts = q["options"].copy()
                random.shuffle(opts)
                st.session_state.shuffled_options = opts
                st.session_state.last_word = q["word"]

            cols = st.columns(2)
            for i, opt in enumerate(st.session_state.shuffled_options):
                with cols[i % 2]:
                    if st.button(
                        f"**{opt['word']}**  \n{opt['word_th']}",
                        key=f"opt_{i}",
                        use_container_width=True
                    ):
                        st.session_state.selected = opt
                        st.session_state.answered = True
                        correct = opt["is_correct"]
                        st.session_state.data = update_word(
                            st.session_state.data,
                            q["word"],
                            q["word_th"],
                            correct
                        )
                        st.rerun()

        # After answer
        else:
            selected = st.session_state.selected
            correct_opt = next(o for o in q["options"] if o["is_correct"])
            is_correct = selected["is_correct"]

            # Show full sentence
            st.markdown(f"""
            <div class='sentence-box'>
                📖 {q['sentence']}
                <div class='sentence-thai'>{q['sentence_th']}</div>
            </div>
            """, unsafe_allow_html=True)

            if is_correct:
                st.markdown(f"""
                <div class='result-correct'>
                    ✅ <b>ถูกต้อง!</b> — <b>{selected['word']}</b> ({selected['word_th']}) คือคำที่ใช้ได้ในบริบทนี้
                </div>
                """, unsafe_allow_html=True)
            else:
                state = get_word_state(st.session_state.data, q["word"])
                st.markdown(f"""
                <div class='result-wrong'>
                    ❌ <b>ผิด</b> — คุณเลือก <b>{selected['word']}</b> ({selected['word_th']})<br>
                    คำที่ถูกคือ <b>{correct_opt['word']}</b> ({correct_opt['word_th']})<br>
                    <small style='opacity:0.7'>🔄 คำนี้จะวนกลับมาให้ review พรุ่งนี้</small>
                </div>
                """, unsafe_allow_html=True)

            # Word status after answer
            state = get_word_state(st.session_state.data, q["word"])
            status_map = {
                "new": "<span class='badge-new'>🔵 ใหม่</span>",
                "learning": "<span class='badge-learn'>🟡 กำลังเรียน</span>",
                "known": "<span class='badge-known'>🟢 จำได้แล้ว</span>"
            }
            st.markdown(f"สถานะคำนี้: {status_map.get(state['status'], '')}", unsafe_allow_html=True)

            st.markdown("")
            if st.button("➡️ คำต่อไป", type="primary", use_container_width=True):
                st.session_state.question = None
                st.rerun()

# ─────────────────────────────────────────────
# PAGE: Dashboard
# ─────────────────────────────────────────────
elif page == "📊 Dashboard":
    st.markdown("# 📊 Dashboard")
    stats = get_stats(st.session_state.data)

    # Top stats row
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class='card' style='text-align:center'>
            <div class='stat-number'>{stats['total']}</div>
            <div class='stat-label'>คำทั้งหมด</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class='card' style='text-align:center; border-color:#34d399'>
            <div class='stat-number' style='color:#34d399'>{stats['known']}</div>
            <div class='stat-label'>จำได้แล้ว 🟢</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class='card' style='text-align:center; border-color:#fbbf24'>
            <div class='stat-number' style='color:#fbbf24'>{stats['learning']}</div>
            <div class='stat-label'>กำลังเรียน 🟡</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class='card' style='text-align:center; border-color:#f472b6'>
            <div class='stat-number' style='color:#f472b6'>{stats['streak']} 🔥</div>
            <div class='stat-label'>Streak รายวัน</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # Daily activity chart
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown("### 📈 กิจกรรม 14 วันที่ผ่านมา")
        daily = stats["daily"]
        if any(d["seen"] > 0 for d in daily):
            df = pd.DataFrame(daily)
            df["date_short"] = pd.to_datetime(df["date"]).dt.strftime("%d/%m")

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df["date_short"], y=df["seen"],
                name="คำที่เห็น", marker_color="#2a3060"
            ))
            fig.add_trace(go.Bar(
                x=df["date_short"], y=df["correct"],
                name="ตอบถูก", marker_color="#7c9eff"
            ))
            fig.update_layout(
                barmode="overlay",
                plot_bgcolor="#0d0f14",
                paper_bgcolor="#13151c",
                font_color="#a0a8c0",
                legend=dict(bgcolor="#13151c"),
                margin=dict(l=0, r=0, t=10, b=0),
                height=250,
                xaxis=dict(gridcolor="#1e2130"),
                yaxis=dict(gridcolor="#1e2130"),
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.markdown("<div class='card' style='color:#6b7494; text-align:center; padding:40px'>ยังไม่มีข้อมูล เริ่มเล่นก่อนเลย! 🎮</div>", unsafe_allow_html=True)

    with col_right:
        st.markdown("### 🔴 คำที่ยังบกพร่อง")
        weak = get_weak_words(st.session_state.data)
        if weak:
            for w in weak:
                wrong_pct = round(w["total_wrong"] / w["total_seen"] * 100) if w["total_seen"] > 0 else 0
                st.markdown(f"""
                <div style='background:#1a1d2e; border-radius:10px; padding:10px 14px; margin-bottom:8px; border-left:3px solid #f87171'>
                    <b style='color:#c8cfe8'>{w['word']}</b>
                    <span style='color:#6b7494; font-size:0.85rem'> — {w.get('word_th','')}</span><br>
                    <small style='color:#f87171'>ผิด {w['total_wrong']} ครั้ง ({wrong_pct}%)</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("<div class='card' style='color:#6b7494; text-align:center; padding:30px'>ยังไม่มีคำที่ผิดบ่อย 🎉</div>", unsafe_allow_html=True)

    # Word list
    st.markdown("### 📚 คำทั้งหมดที่เรียนแล้ว")
    all_words = list(st.session_state.data["words"].values())
    if all_words:
        df_words = pd.DataFrame(all_words)[["word", "word_th", "status", "repetitions", "total_seen", "total_wrong", "next_review"]]
        df_words.columns = ["คำ", "ความหมาย", "สถานะ", "ตอบถูกติดต่อกัน", "เห็นทั้งหมด", "ผิดทั้งหมด", "Review ครั้งต่อไป"]
        status_th = {"new": "🔵 ใหม่", "learning": "🟡 กำลังเรียน", "known": "🟢 จำได้แล้ว"}
        df_words["สถานะ"] = df_words["สถานะ"].map(status_th)
        st.dataframe(df_words, use_container_width=True, hide_index=True)
    else:
        st.markdown("<div class='card' style='color:#6b7494; text-align:center; padding:40px'>ยังไม่มีคำในคลัง ไปเล่นก่อนเลย! 🎮</div>", unsafe_allow_html=True)
