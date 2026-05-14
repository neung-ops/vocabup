import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_FILE = Path("data/progress.json")

def load_data():
    DATA_FILE.parent.mkdir(exist_ok=True)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"words": {}, "daily_log": {}, "streak": {"last_date": None, "count": 0}}

def save_data(data):
    DATA_FILE.parent.mkdir(exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_streak(data):
    today = str(date.today())
    streak = data.get("streak", {"last_date": None, "count": 0})
    if streak["last_date"] == today:
        return data
    yesterday = str(date.today() - timedelta(days=1))
    if streak["last_date"] == yesterday:
        streak["count"] += 1
    elif streak["last_date"] != today:
        streak["count"] = 1
    streak["last_date"] = today
    data["streak"] = streak
    return data

def log_daily(data, correct: bool):
    today = str(date.today())
    if today not in data["daily_log"]:
        data["daily_log"][today] = {"seen": 0, "correct": 0}
    data["daily_log"][today]["seen"] += 1
    if correct:
        data["daily_log"][today]["correct"] += 1
    return data

def get_word_state(data, word: str):
    return data["words"].get(word, {
        "word": word,
        "interval": 0,
        "repetitions": 0,
        "ef": 2.5,           # easiness factor (SM-2)
        "next_review": str(date.today()),
        "total_seen": 0,
        "total_wrong": 0,
        "status": "new"      # new / learning / known
    })

def update_word(data, word: str, word_th: str, correct: bool):
    """SM-2 algorithm update"""
    state = get_word_state(data, word)
    state["word"] = word
    state["word_th"] = word_th
    state["total_seen"] += 1

    q = 4 if correct else 1   # quality: 4=correct, 1=wrong

    if correct:
        if state["repetitions"] == 0:
            state["interval"] = 1
        elif state["repetitions"] == 1:
            state["interval"] = 4
        else:
            state["interval"] = round(state["interval"] * state["ef"])
        state["repetitions"] += 1
    else:
        state["total_wrong"] += 1
        state["repetitions"] = 0
        state["interval"] = 1   # reset — วนกลับมาพรุ่งนี้

    # Update EF (min 1.3)
    state["ef"] = max(1.3, state["ef"] + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))

    # Set next review date
    next_date = date.today() + timedelta(days=state["interval"])
    state["next_review"] = str(next_date)

    # Update status
    if state["repetitions"] >= 3 and state["total_wrong"] == 0:
        state["status"] = "known"
    elif state["repetitions"] >= 1:
        state["status"] = "learning"
    else:
        state["status"] = "new"

    data["words"][word] = state
    data = log_daily(data, correct)
    data = update_streak(data)
    save_data(data)
    return data

def get_due_words(data):
    today = str(date.today())
    due = []
    for word, state in data["words"].items():
        if state["next_review"] <= today:
            due.append(state)
    return sorted(due, key=lambda x: x["next_review"])

def get_weak_words(data, top_n=10):
    words = list(data["words"].values())
    words = [w for w in words if w.get("total_wrong", 0) > 0]
    return sorted(words, key=lambda x: x["total_wrong"], reverse=True)[:top_n]

def get_stats(data):
    words = list(data["words"].values())
    total = len(words)
    known = sum(1 for w in words if w["status"] == "known")
    learning = sum(1 for w in words if w["status"] == "learning")
    new_w = sum(1 for w in words if w["status"] == "new")
    streak = data.get("streak", {}).get("count", 0)

    # Daily log last 14 days
    daily = []
    for i in range(13, -1, -1):
        d = str(date.today() - timedelta(days=i))
        entry = data["daily_log"].get(d, {"seen": 0, "correct": 0})
        daily.append({"date": d, **entry})

    return {
        "total": total,
        "known": known,
        "learning": learning,
        "new": new_w,
        "streak": streak,
        "daily": daily,
    }
