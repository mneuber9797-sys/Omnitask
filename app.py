import os
import html
import time
import datetime
import streamlit as st
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# --- Seiten-Konfiguration ---
st.set_page_config(page_title="OmniTasks", layout="wide")

# --- Unternehmensbereiche & Farb-Akzente ---
AREAS = [
    {
        "name": "Recht & Steuern",
        "color": "#38BDF8",
        "glow": "rgba(56, 189, 248, 0.24)",
        "bg_tint": "rgba(56, 189, 248, 0.08)",
        "icon": "⚖️",
    },
    {
        "name": "Vertrieb & Marketing",
        "color": "#FACC15",
        "glow": "rgba(250, 204, 21, 0.22)",
        "bg_tint": "rgba(250, 204, 21, 0.08)",
        "icon": "📣",
    },
    {
        "name": "Produkte",
        "color": "#A855F7",
        "glow": "rgba(168, 85, 247, 0.24)",
        "bg_tint": "rgba(168, 85, 247, 0.08)",
        "icon": "🧩",
    },
    {
        "name": "Kunden",
        "color": "#22C55E",
        "glow": "rgba(34, 197, 94, 0.22)",
        "bg_tint": "rgba(34, 197, 94, 0.08)",
        "icon": "🤝",
    },
    {
        "name": "Mitarbeiter",
        "color": "#EF4444",
        "glow": "rgba(239, 68, 68, 0.24)",
        "bg_tint": "rgba(239, 68, 68, 0.08)",
        "icon": "👥",
    },
]

AREA_BY_NAME = {a["name"]: a for a in AREAS}
AREA_NAMES = [a["name"] for a in AREAS]
ASSIGNEES = ["Leonard", "Max", "Leonard & Max"]

# --- ABC-Klassifikationslogik ---
def berechne_abc_kategorie(wichtigkeit: int, dringlichkeit: int, override: str | None = None) -> str:
    if override in ("A", "B", "C"):
        return override
    w = int(wichtigkeit)
    d = int(dringlichkeit)
    if (w in (4, 5) and d >= 3) or (w == 3 and d == 5):
        return "A"
    if w >= 3:
        return "B"
    return "C"

def formatiere_zeit(minuten: int) -> str:
    m = max(1, int(minuten))
    if m < 60:
        return f"{m} Min."
    stunden = m // 60
    rest = m % 60
    if rest == 0:
        return f"{stunden} Std."
    return f"{stunden} Std. {rest} Min."

# --- Basis-CSS (Tiefschwarzes Layout mit klaren Akzenten) ---
st.markdown(
    """
    <style>
    header[data-testid="stHeader"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"] {
        background: transparent !important;
        background-color: transparent !important;
        box-shadow: none !important;
    }

    .stApp {
        background: radial-gradient(circle at 50% -12%, #111622 0%, #06080C 52%, #040508 100%);
        color: #F1F5F9;
    }

    .block-container,
    [data-testid="stMainBlockContainer"],
    .stMainBlockContainer {
        max-width: 1280px !important;
        padding-top: 3.3rem !important;
        padding-bottom: 3.5rem !important;
        padding-left: 2.2rem !important;
        padding-right: 2.2rem !important;
    }

    hr {
        border: none !important;
        border-top: 1px solid rgba(148, 163, 184, 0.2) !important;
        margin: 1.3rem 0 !important;
    }

    .omni-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 0.85rem;
        margin-bottom: 1.2rem;
        border-bottom: 1.5px solid rgba(226, 232, 240, 0.24);
    }

    .omni-brand {
        display: inline-block;
        font-size: 2.25rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(135deg, #FFFFFF 0%, #E2E8F0 60%, #94A3B8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        line-height: 1.28;
    }

    .omni-tagline {
        font-size: 0.88rem;
        color: #94A3B8;
        margin-top: 0.12rem;
        letter-spacing: 0.03em;
    }

    .section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #F8FAFC;
        margin-bottom: 0.7rem;
        letter-spacing: -0.01em;
    }

    .top10-card {
        background: linear-gradient(165deg, #10141F 0%, #080A10 100%);
        border: 1px solid rgba(148, 163, 184, 0.2);
        border-left: 4px solid var(--accent, #38BDF8);
        border-radius: 13px;
        padding: 0.85rem 1.05rem;
        margin-bottom: 0.45rem;
        box-shadow: 0 10px 22px rgba(0, 0, 0, 0.48), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    }

    .top10-top {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 0.35rem;
    }

    .top10-rank-title {
        font-size: 1.0rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.35;
    }

    .rank-num {
        color: #94A3B8;
        font-weight: 800;
        margin-right: 0.4rem;
        font-size: 0.9rem;
    }

    .top10-meta {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 0.45rem;
        font-size: 0.79rem;
        color: #94A3B8;
    }

    .area-pill {
        display: inline-block;
        padding: 0.14rem 0.55rem;
        border-radius: 999px;
        font-weight: 700;
        font-size: 0.74rem;
        color: var(--accent, #38BDF8);
        background: var(--bg-tint, rgba(56, 189, 248, 0.1));
        border: 1px solid var(--accent, #38BDF8);
    }

    .assignee-pill {
        display: inline-block;
        padding: 0.14rem 0.55rem;
        border-radius: 7px;
        font-weight: 700;
        font-size: 0.75rem;
        color: #E2E8F0;
        background: rgba(255, 255, 255, 0.07);
        border: 1px solid rgba(255, 255, 255, 0.16);
    }

    .abc-tag-A {
        background: rgba(239, 68, 68, 0.18);
        color: #FCA5A5;
        border: 1px solid rgba(239, 68, 68, 0.45);
        padding: 0.1rem 0.45rem;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.72rem;
    }

    .abc-tag-B {
        background: rgba(250, 204, 21, 0.16);
        color: #FDE047;
        border: 1px solid rgba(250, 204, 21, 0.42);
        padding: 0.1rem 0.45rem;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.72rem;
    }

    .abc-tag-C {
        background: rgba(148, 163, 184, 0.14);
        color: #CBD5E1;
        border: 1px solid rgba(148, 163, 184, 0.35);
        padding: 0.1rem 0.45rem;
        border-radius: 6px;
        font-weight: 800;
        font-size: 0.72rem;
    }

    .area-card {
        background: linear-gradient(165deg, #101521 0%, #080A10 100%);
        border: 1px solid rgba(148, 163, 184, 0.22);
        border-top: 3.5px solid var(--accent);
        border-radius: 15px;
        padding: 1.05rem 1.2rem;
        margin-bottom: 0.45rem;
        box-shadow: 0 12px 26px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.07);
    }

    .area-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.4rem;
    }

    .area-card-title {
        font-size: 1.08rem;
        font-weight: 800;
        color: #F8FAFC;
    }

    .area-card-count {
        font-size: 0.8rem;
        font-weight: 700;
        color: var(--accent);
        background: var(--bg-tint);
        border: 1px solid var(--accent);
        padding: 0.15rem 0.58rem;
        border-radius: 999px;
    }

    .area-card-stats {
        font-size: 0.82rem;
        color: #94A3B8;
    }

    .matrix-wrapper {
        background: linear-gradient(165deg, #0D111B 0%, #07090E 100%);
        border: 1.5px solid var(--accent);
        border-radius: 18px;
        padding: 1.35rem 1.5rem;
        margin-bottom: 1.4rem;
        box-shadow: 0 18px 36px rgba(0, 0, 0, 0.58), 0 0 28px var(--glow);
    }

    .matrix-layout {
        display: flex;
        align-items: stretch;
        gap: 0.85rem;
    }

    .y-axis-label {
        writing-mode: vertical-rl;
        transform: rotate(180deg);
        text-align: center;
        font-size: 0.84rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent);
        padding: 0.3rem 0;
    }

    .matrix-grid-area {
        flex: 1;
    }

    .matrix-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 6px;
        table-layout: fixed;
    }

    .matrix-y-tick {
        width: 34px;
        text-align: center;
        font-size: 0.85rem;
        font-weight: 800;
        color: #CBD5E1;
    }

    .matrix-cell {
        height: 62px;
        border-radius: 11px;
        border: 1px solid rgba(148, 163, 184, 0.18);
        background: #0A0D15;
        vertical-align: middle;
        text-align: center;
        position: relative;
        padding: 4px;
        transition: border-color 0.15s ease;
    }

    .matrix-cell:hover {
        border-color: var(--accent);
    }

    .cell-zone-A {
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.045) 0%, #0B0F19 100%);
        border-color: rgba(255, 255, 255, 0.16);
    }

    .cell-zone-B {
        background: #090C14;
    }

    .cell-zone-C {
        background: #06080D;
        opacity: 0.88;
    }

    .zone-watermark {
        position: absolute;
        top: 4px;
        right: 7px;
        font-size: 0.65rem;
        font-weight: 700;
        color: rgba(148, 163, 184, 0.32);
        pointer-events: none;
    }

    .dots-container {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        align-items: center;
        gap: 6px;
        min-height: 28px;
    }

    .task-dot {
        display: inline-block;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: var(--accent);
        box-shadow: 0 0 10px var(--accent), 0 0 3px #FFFFFF;
        border: 1.5px solid #FFFFFF;
        cursor: pointer;
        transition: transform 0.15s ease;
    }

    .task-dot:hover {
        transform: scale(1.35);
    }

    .matrix-x-tick {
        text-align: center;
        font-size: 0.85rem;
        font-weight: 800;
        color: #CBD5E1;
        padding-top: 4px;
    }

    .x-axis-label {
        text-align: center;
        font-size: 0.84rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        color: var(--accent);
        margin-top: 0.45rem;
        padding-left: 34px;
    }

    .abc-col-header {
        background: linear-gradient(165deg, #111624 0%, #090C14 100%);
        border: 1px solid rgba(148, 163, 184, 0.24);
        border-top: 3px solid var(--accent);
        border-radius: 13px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }

    .abc-col-title {
        font-size: 1.05rem;
        font-weight: 800;
        color: #F8FAFC;
    }

    .abc-col-sub {
        font-size: 0.76rem;
        color: #94A3B8;
    }

    .movable-task-card {
        background: linear-gradient(165deg, #121726 0%, #090C14 100%);
        border: 1px solid rgba(148, 163, 184, 0.25);
        border-left: 4px solid var(--accent);
        border-radius: 14px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.35rem;
        box-shadow: 0 10px 22px rgba(0, 0, 0, 0.48), inset 0 1px 0 rgba(255, 255, 255, 0.08);
    }

    .movable-task-top {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 0.5rem;
        margin-bottom: 0.45rem;
    }

    .movable-task-title {
        font-size: 0.98rem;
        font-weight: 700;
        color: #F8FAFC;
        line-height: 1.38;
    }

    .movable-task-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.45rem;
        font-size: 0.78rem;
        color: #94A3B8;
    }

    .stButton > button {
        background: linear-gradient(180deg, #161D2E 0%, #0D111C 100%) !important;
        border: 1px solid rgba(148, 163, 184, 0.35) !important;
        color: #F1F5F9 !important;
        border-radius: 10px !important;
        padding: 0.45rem 0.75rem !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.38) !important;
        transition: border-color 0.12s ease, background 0.12s ease !important;
    }
    .stButton > button:hover {
        border-color: #E2E8F0 !important;
        background: linear-gradient(180deg, #1F2940 0%, #131929 100%) !important;
        color: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- Datenbank-Verbindung (Neon PostgreSQL) ---
def get_db_url():
    try:
        url = st.secrets["DATABASE_URL"].strip()
    except Exception:
        url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

@st.cache_resource
def get_db_pool():
    db_url = get_db_url()
    if not db_url:
        raise RuntimeError("DATABASE_URL fehlt in den Streamlit Secrets.")
    return pool.ThreadedConnectionPool(minconn=1, maxconn=6, dsn=db_url, connect_timeout=15)

def get_connection():
    p = get_db_pool()
    last_err = None
    for _ in range(3):
        conn = None
        try:
            conn = p.getconn()
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            return conn
        except Exception as e:
            last_err = e
            if conn is not None:
                try:
                    p.putconn(conn, close=True)
                except Exception:
                    pass
            time.sleep(0.4)
    raise last_err

def release_connection(conn, broken: bool = False):
    if conn is None:
        return
    try:
        get_db_pool().putconn(conn, close=broken)
    except Exception:
        try:
            conn.close()
        except Exception:
            pass

@st.cache_resource
def init_db():
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS omni_tasks (
                    id SERIAL PRIMARY KEY,
                    area TEXT NOT NULL,
                    title TEXT NOT NULL,
                    assignee TEXT NOT NULL DEFAULT 'Leonard',
                    importance INTEGER NOT NULL DEFAULT 3,
                    urgency INTEGER NOT NULL DEFAULT 3,
                    duration_minutes INTEGER NOT NULL DEFAULT 30,
                    abc_override TEXT,
                    manual_order INTEGER,
                    is_done BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS omni_subtasks (
                    id SERIAL PRIMARY KEY,
                    task_id INTEGER NOT NULL REFERENCES omni_tasks(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    assignee TEXT NOT NULL DEFAULT 'Leonard',
                    is_done BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)
    return True

try:
    init_db()
except Exception as e:
    st.error(f"Datenbank-Verbindung fehlgeschlagen: {e}")
    st.info("Hinterlege `DATABASE_URL` in Streamlit unter **Settings → Secrets**.")
    st.stop()

# --- Datenbank-Funktionen ---
def lade_alle_offenen_aufgaben():
    conn = get_connection()
    broken = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT *
                FROM omni_tasks
                WHERE is_done = FALSE
                ORDER BY id ASC;
            """)
            tasks = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT s.*
                FROM omni_subtasks s
                JOIN omni_tasks t ON t.id = s.task_id
                WHERE t.is_done = FALSE
                ORDER BY s.id ASC;
            """)
            subtasks = [dict(r) for r in cur.fetchall()]

        sub_map = {}
        for s in subtasks:
            sub_map.setdefault(s["task_id"], []).append(s)

        for t in tasks:
            t["subtasks"] = sub_map.get(t["id"], [])
            t["total_score"] = int(t["importance"]) + int(t["urgency"])
            t["abc"] = berechne_abc_kategorie(t["importance"], t["urgency"], t.get("abc_override"))

        return tasks
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def erstelle_aufgabe_mit_unteraufgaben(area, title, assignee, importance, urgency, duration_minutes, subtasks_list):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO omni_tasks (area, title, assignee, importance, urgency, duration_minutes)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (area, title.strip(), assignee, int(importance), int(urgency), int(duration_minutes)),
            )
            task_id = cur.fetchone()[0]
            for st_title in subtasks_list:
                clean_st = st_title.strip()
                if clean_st:
                    cur.execute(
                        """
                        INSERT INTO omni_subtasks (task_id, title, assignee)
                        VALUES (%s, %s, %s);
                        """,
                        (task_id, clean_st, assignee),
                    )
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def fuege_unteraufgabe_hinzu(task_id, title, assignee):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO omni_subtasks (task_id, title, assignee)
                VALUES (%s, %s, %s);
                """,
                (int(task_id), title.strip(), assignee),
            )
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def setze_unteraufgabe_status(subtask_id, is_done):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE omni_subtasks SET is_done = %s WHERE id = %s;", (bool(is_done), int(subtask_id)))
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def schliesse_aufgabe_ab(task_id):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE omni_tasks SET is_done = TRUE WHERE id = %s;", (int(task_id),))
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def verschiebe_aufgabe_spalte(task_id, ziel_spalte):
    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE omni_tasks SET abc_override = %s, manual_order = NULL WHERE id = %s;",
                (ziel_spalte, int(task_id)),
            )
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def tausche_reihenfolge_in_spalte(spalten_liste, index_a, index_b):
    if index_a < 0 or index_b < 0 or index_a >= len(spalten_liste) or index_b >= len(spalten_liste):
        return
    neu_liste = list(spalten_liste)
    neu_liste[index_a], neu_liste[index_b] = neu_liste[index_b], neu_liste[index_a]

    conn = get_connection()
    broken = False
    try:
        with conn.cursor() as cur:
            for pos, item in enumerate(neu_liste):
                cur.execute(
                    "UPDATE omni_tasks SET manual_order = %s WHERE id = %s;",
                    (pos + 1, int(item["id"])),
                )
        conn.commit()
    except Exception:
        broken = True
        raise
    finally:
        release_connection(conn, broken=broken)

def sortiere_aufgaben_standard(aufgaben_liste):
    return sorted(
        aufgaben_liste,
        key=lambda t: (
            -(int(t["importance"]) + int(t["urgency"])),
            int(t["duration_minutes"]),
            int(t["id"]),
        ),
    )

def sortiere_abc_spalte(aufgaben_liste):
    return sorted(
        aufgaben_liste,
        key=lambda t: (
            0 if t.get("manual_order") is not None else 1,
            int(t["manual_order"]) if t.get("manual_order") is not None else 0,
            -(int(t["importance"]) + int(t["urgency"])),
            int(t["duration_minutes"]),
            int(t["id"]),
        ),
    )

# --- Session State für Navigation ---
if "selected_area" not in st.session_state:
    st.session_state.selected_area = None

alle_tasks = lade_alle_offenen_aufgaben()
aktiver_bereich_name = st.session_state.selected_area
if aktiver_bereich_name and aktiver_bereich_name not in AREA_BY_NAME:
    st.session_state.selected_area = None
    aktiver_bereich_name = None

# ==============================================================================
# KOPFZEILE
# ==============================================================================
if aktiver_bereich_name is None:
    st.markdown(
        '<div class="omni-header">'
        '<div><div class="omni-brand">OmniTasks</div>'
        '<div class="omni-tagline">Eisenhower-Priorisierung · Leonard & Max</div></div>'
        f'<div style="color:#94A3B8;font-size:0.88rem;font-weight:600;">{len(alle_tasks)} offene Aufgaben gesamt</div>'
        '</div>',
        unsafe_allow_html=True,
    )
else:
    area_cfg = AREA_BY_NAME[aktiver_bereich_name]
    col_back, col_title = st.columns([1.3, 4.7])
    with col_back:
        st.markdown('<div style="height:0.35rem;"></div>', unsafe_allow_html=True)
        if st.button("← Gesamtübersicht", use_container_width=True):
            st.session_state.selected_area = None
            st.rerun()
    with col_title:
        st.markdown(
            f'<div class="omni-header" style="border-bottom-color:{area_cfg["color"]};margin-bottom:0.6rem;">'
            f'<div><div class="omni-brand" style="background:none;-webkit-text-fill-color:{area_cfg["color"]};">{area_cfg["icon"]} {html.escape(aktiver_bereich_name)}</div>'
            f'<div class="omni-tagline">Eisenhower-Matrix & ABC-Aufgabensteuerung</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ==============================================================================
# ANSICHT A: STARTBILDSCHIRM (LINKS TOP 10 · RECHTS 5 UNTERNEHMENSBEREICHE)
# ==============================================================================
if aktiver_bereich_name is None:
    col_left, col_right = st.columns([1.45, 1.0], gap="large")

    # --- LINKS: Top 10 wichtigste Aufgaben bereichsübergreifend ---
    with col_left:
        st.markdown('<div class="section-title">🔥 Top 10 wichtigste Aufgaben (bereichsübergreifend)</div>', unsafe_allow_html=True)
        top10_tasks = sortiere_aufgaben_standard(alle_tasks)[:10]

        if not top10_tasks:
            st.info("Aktuell sind keine offenen Aufgaben vorhanden. Trage unten über die Eingabemaske eure erste Aufgabe ein.")
        else:
            for idx, task in enumerate(top10_tasks, start=1):
                a_info = AREA_BY_NAME.get(task["area"], AREAS[0])
                abc = task["abc"]
                subs = task.get("subtasks", [])
                sub_txt = ""
                if subs:
                    done_subs = sum(1 for s in subs if s["is_done"])
                    sub_txt = f' · Unteraufgaben: <b>{done_subs}/{len(subs)}</b>'

                c_card, c_done = st.columns([5.2, 0.8])
                with c_card:
                    st.markdown(
                        f'<div class="top10-card" style="--accent:{a_info["color"]};--bg-tint:{a_info["bg_tint"]};">'
                        f'<div class="top10-top">'
                        f'<div class="top10-rank-title"><span class="rank-num">#{idx}</span>{html.escape(task["title"])}</div>'
                        f'<span class="abc-tag-{abc}">{abc}-Aufgabe</span>'
                        f'</div>'
                        f'<div class="top10-meta">'
                        f'<span class="area-pill">{a_info["icon"]} {html.escape(task["area"])}</span>'
                        f'<span class="assignee-pill">👤 {html.escape(task["assignee"])}</span>'
                        f'<span>Wichtigkeit: <b>{task["importance"]}</b> · Dringlichkeit: <b>{task["urgency"]}</b> (Σ {task["total_score"]})</span>'
                        f'<span>⏱️ {formatiere_zeit(task["duration_minutes"])}{sub_txt}</span>'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
                with c_done:
                    st.markdown('<div style="height:0.55rem;"></div>', unsafe_allow_html=True)
                    if st.button("✓", key=f"top10_done_{task['id']}", help="Aufgabe als erledigt abhaken", use_container_width=True):
                        schliesse_aufgabe_ab(task["id"])
                        st.rerun()

    # --- RECHTS: Anklickbare Felder für die 5 Unternehmensbereiche ---
    with col_right:
        st.markdown('<div class="section-title">🏢 Unternehmensbereiche (Eisenhower-Matrizen)</div>', unsafe_allow_html=True)
        for area in AREAS:
            area_tasks = [t for t in alle_tasks if t["area"] == area["name"]]
            cnt_a = sum(1 for t in area_tasks if t["abc"] == "A")
            cnt_b = sum(1 for t in area_tasks if t["abc"] == "B")
            cnt_c = sum(1 for t in area_tasks if t["abc"] == "C")

            st.markdown(
                f'<div class="area-card" style="--accent:{area["color"]};--bg-tint:{area["bg_tint"]};">'
                f'<div class="area-card-header">'
                f'<div class="area-card-title">{area["icon"]} {html.escape(area["name"])}</div>'
                f'<div class="area-card-count">{len(area_tasks)} offen</div>'
                f'</div>'
                f'<div class="area-card-stats">'
                f'A-Aufgaben: <b>{cnt_a}</b> · B-Aufgaben: <b>{cnt_b}</b> · C-Aufgaben: <b>{cnt_c}</b>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button(f"Matrix „{area['name']}“ öffnen →", key=f"open_area_{area['name']}", use_container_width=True):
                st.session_state.selected_area = area["name"]
                st.rerun()

# ==============================================================================
# ANSICHT B: EISENHOWER-MATRIX & ABC-TABELLE FÜR EINEN UNTERNEHMENSBEREICH
# ==============================================================================
else:
    area_cfg = AREA_BY_NAME[aktiver_bereich_name]
    accent = area_cfg["color"]
    glow = area_cfg["glow"]

    switch_cols = st.columns(5)
    for idx, a in enumerate(AREAS):
        is_curr = (a["name"] == aktiver_bereich_name)
        btn_label = f"{a['icon']} {a['name']}"
        if switch_cols[idx].button(btn_label, key=f"nav_pill_{a['name']}", disabled=is_curr, use_container_width=True):
            st.session_state.selected_area = a["name"]
            st.rerun()

    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)

    bereichs_tasks = [t for t in alle_tasks if t["area"] == aktiver_bereich_name]

    # --- 1. VISUELLES 5x5 EISENHOWER-RASTER (PUNKTE OHNE BESCHRIFTUNG) ---
    cell_tasks = {(w, d): [] for w in range(1, 6) for d in range(1, 6)}
    for t in bereichs_tasks:
        w = min(5, max(1, int(t["importance"])))
        d = min(5, max(1, int(t["urgency"])))
        cell_tasks[(w, d)].append(t)

    rows_html = []
    for w in range(5, 0, -1):
        tds = [f'<td class="matrix-y-tick">{w}</td>']
        for d in range(1, 6):
            zone = berechne_abc_kategorie(w, d)
            dots = []
            for t in cell_tasks[(w, d)]:
                tooltip = html.escape(f"{t['title']} ({t['assignee']} · {formatiere_zeit(t['duration_minutes'])})")
                dots.append(f'<span class="task-dot" title="{tooltip}"></span>')
            dots_html = "".join(dots)
            tds.append(
                f'<td class="matrix-cell cell-zone-{zone}">'
                f'<span class="zone-watermark">{zone}</span>'
                f'<div class="dots-container">{dots_html}</div>'
                f'</td>'
            )
        rows_html.append(f"<tr>{''.join(tds)}</tr>")

    x_ticks = ['<td></td>'] + [f'<td class="matrix-x-tick">{d}</td>' for d in range(1, 6)]
    rows_html.append(f"<tr>{''.join(x_ticks)}</tr>")

    matrix_html = (
        f'<div class="matrix-wrapper" style="--accent:{accent};--glow:{glow};">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.85rem;">'
        f'<span style="font-weight:800;font-size:1.05rem;color:#F8FAFC;">Eisenhower-Raster (5 × 5)</span>'
        f'<span style="font-size:0.8rem;color:#94A3B8;">Jeder Punkt steht für eine offene Aufgabe (Mauszeiger auf Punkt zeigt Details)</span>'
        f'</div>'
        f'<div class="matrix-layout">'
        f'<div class="y-axis-label">Priorität / Wichtigkeit (1 – 5) →</div>'
        f'<div class="matrix-grid-area">'
        f'<table class="matrix-table">{"".join(rows_html)}</table>'
        f'<div class="x-axis-label">Dringlichkeit (1 – 5) →</div>'
        f'</div>'
        f'</div>'
        f'</div>'
    )
    st.markdown(matrix_html, unsafe_allow_html=True)

    # --- 2. DREISPALTIGE ABC-TABELLE DARUNTER (FREI BEWEGBARE AUFGABENFELDER) ---
    a_tasks = sortiere_abc_spalte([t for t in bereichs_tasks if t["abc"] == "A"])
    b_tasks = sortiere_abc_spalte([t for t in bereichs_tasks if t["abc"] == "B"])
    c_tasks = sortiere_abc_spalte([t for t in bereichs_tasks if t["abc"] == "C"])

    col_a, col_b, col_c = st.columns(3, gap="medium")

    spalten_konfig = [
        (col_a, "A", "A-Aufgaben", "Sofort erledigen", a_tasks),
        (col_b, "B", "B-Aufgaben", "Einplanen & terminieren", b_tasks),
        (col_c, "C", "C-Aufgaben", "Nachrangig / delegieren", c_tasks),
    ]

    for col_obj, kat_code, kat_titel, kat_sub, kat_liste in spalten_konfig:
        with col_obj:
            st.markdown(
                f'<div class="abc-col-header" style="--accent:{accent};">'
                f'<div><div class="abc-col-title">{kat_titel} ({len(kat_liste)})</div>'
                f'<div class="abc-col-sub">{kat_sub}</div></div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if not kat_liste:
                st.caption("Keine Aufgaben in dieser Spalte.")

            for idx, task in enumerate(kat_liste):
                tid = task["id"]
                st.markdown(
                    f'<div class="movable-task-card" style="--accent:{accent};">'
                    f'<div class="movable-task-top">'
                    f'<div class="movable-task-title">{html.escape(task["title"])}</div>'
                    f'<span class="assignee-pill">👤 {html.escape(task["assignee"])}</span>'
                    f'</div>'
                    f'<div class="movable-task-meta">'
                    f'<span>W: <b>{task["importance"]}</b> · D: <b>{task["urgency"]}</b> (Σ {task["total_score"]})</span>'
                    f'<span>⏱️ {formatiere_zeit(task["duration_minutes"])}</span>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                subs = task.get("subtasks", [])
                if subs:
                    for sub in subs:
                        checked = st.checkbox(
                            f"{sub['title']} ({sub['assignee']})",
                            value=bool(sub["is_done"]),
                            key=f"sub_chk_{sub['id']}",
                        )
                        if checked != bool(sub["is_done"]):
                            setze_unteraufgabe_status(sub["id"], checked)
                            st.rerun()

                andere_spalten = [k for k in ("A", "B", "C") if k != kat_code]
                m1, m2, m3, m4, m5 = st.columns([1, 1, 1.15, 1.15, 1.1])

                with m1:
                    if st.button("↑", key=f"up_{tid}", disabled=(idx == 0), help="Nach oben verschieben", use_container_width=True):
                        tausche_reihenfolge_in_spalte(kat_liste, idx, idx - 1)
                        st.rerun()
                with m2:
                    if st.button("↓", key=f"dn_{tid}", disabled=(idx == len(kat_liste) - 1), help="Nach unten verschieben", use_container_width=True):
                        tausche_reihenfolge_in_spalte(kat_liste, idx, idx + 1)
                        st.rerun()
                with m3:
                    ziel_1 = andere_spalten[0]
                    if st.button(f"→ {ziel_1}", key=f"mv_{tid}_{ziel_1}", help=f"In {ziel_1}-Aufgaben verschieben", use_container_width=True):
                        verschiebe_aufgabe_spalte(tid, ziel_1)
                        st.rerun()
                with m4:
                    ziel_2 = andere_spalten[1]
                    if st.button(f"→ {ziel_2}", key=f"mv_{tid}_{ziel_2}", help=f"In {ziel_2}-Aufgaben verschieben", use_container_width=True):
                        verschiebe_aufgabe_spalte(tid, ziel_2)
                        st.rerun()
                with m5:
                    if st.button("✓", key=f"done_{tid}", help="Aufgabe erledigt", use_container_width=True):
                        schliesse_aufgabe_ab(tid)
                        st.rerun()

                st.markdown('<div style="height:0.35rem;"></div>', unsafe_allow_html=True)

# ==============================================================================
# UNTEN: EINGABEMASKE FÜR AUFGABEN & UNTERAUFGABEN (FELDER 1 BIS 5)
# ==============================================================================
st.markdown("---")
st.markdown('<div class="section-title">➕ Neue Aufgabe oder Unteraufgabe anlegen</div>', unsafe_allow_html=True)

eingabe_modus = st.radio(
    "Eintragstyp:",
    ["Neue Hauptaufgabe (optional inkl. Unteraufgaben)", "Unteraufgabe zu bestehender Aufgabe hinzufügen"],
    horizontal=True,
    label_visibility="collapsed",
)

default_area_idx = AREA_NAMES.index(aktiver_bereich_name) if aktiver_bereich_name in AREA_NAMES else 0

if eingabe_modus == "Neue Hauptaufgabe (optional inkl. Unteraufgaben)":
    with st.form("neue_aufgabe_form", clear_on_submit=True):
        r1_c1, r1_c2, r1_c3 = st.columns([1.4, 2.4, 1.2])

        # Feld 1: Unternehmensbereich
        feld_1_bereich = r1_c1.selectbox(
            "1. Unternehmensbereich",
            AREA_NAMES,
            index=default_area_idx,
        )

        # Feld 2: Aufgabe benennen
        feld_2_aufgabe = r1_c2.text_input(
            "2. Aufgabe benennen",
            placeholder="z. B. Jahresabschlussunterlagen prüfen...",
        )

        # Feld 3: Zuständigkeit (Leonard / Max)
        feld_3_zustaendig = r1_c3.selectbox(
            "3. Zuständigkeit",
            ASSIGNEES,
            index=0,
        )

        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns([1.1, 1.1, 1.2, 2.6])

        # Feld 4: Wichtigkeit (1-5) & Dringlichkeit (1-5)
        feld_4_wichtigkeit = r2_c1.selectbox(
            "4a. Wichtigkeit (1–5)",
            [5, 4, 3, 2, 1],
            index=1,
            help="5 = sehr wichtig, 1 = wenig wichtig",
        )
        feld_4_dringlichkeit = r2_c2.selectbox(
            "4b. Dringlichkeit (1–5)",
            [5, 4, 3, 2, 1],
            index=1,
            help="5 = sehr dringend, 1 = wenig dringend",
        )

        # Feld 5: Ungefährer Zeitaufwand
        feld_5_zeit = r2_c3.number_input(
            "5. Zeitaufwand (Min.)",
            min_value=5,
            max_value=1440,
            value=30,
            step=5,
        )

        # Optionale Unteraufgaben direkt mit anlegen
        unteraufgaben_raw = r2_c4.text_input(
            "Unteraufgaben (optional, mit Komma trennen)",
            placeholder="z. B. Belege sammeln, Steuerberater mailen",
        )

        submitted = st.form_submit_button("Aufgabe speichern", use_container_width=True)
        if submitted:
            if not feld_2_aufgabe.strip():
                st.warning("Bitte gib in Feld 2 einen Namen für die Aufgabe ein.")
            else:
                sub_liste = [s.strip() for s in unteraufgaben_raw.split(",") if s.strip()]
                erstelle_aufgabe_mit_unteraufgaben(
                    area=feld_1_bereich,
                    title=feld_2_aufgabe,
                    assignee=feld_3_zustaendig,
                    importance=feld_4_wichtigkeit,
                    urgency=feld_4_dringlichkeit,
                    duration_minutes=feld_5_zeit,
                    subtasks_list=sub_liste,
                )
                st.rerun()

else:
    kandidaten_tasks = (
        [t for t in alle_tasks if t["area"] == aktiver_bereich_name]
        if aktiver_bereich_name else alle_tasks
    )
    if not kandidaten_tasks:
        st.info("Es existiert noch keine Hauptaufgabe, der eine Unteraufgabe zugeordnet werden kann.")
    else:
        with st.form("neue_unteraufgabe_form", clear_on_submit=True):
            u_c1, u_c2, u_c3 = st.columns([2.2, 2.2, 1.2])
            parent_map = {
                f"[{t['area']}] {t['title']} ({t['assignee']})": t["id"]
                for t in kandidaten_tasks
            }
            gew_parent_label = u_c1.selectbox("Übergeordnete Hauptaufgabe", list(parent_map.keys()))
            sub_titel = u_c2.text_input("Unteraufgabe benennen", placeholder="z. B. Vertragsentwurf gegenlesen...")
            sub_zustaendig = u_c3.selectbox("Zuständigkeit", ASSIGNEES, index=0)

            sub_submit = st.form_submit_button("Unteraufgabe hinzufügen", use_container_width=True)
            if sub_submit:
                if not sub_titel.strip():
                    st.warning("Bitte gib einen Namen für die Unteraufgabe ein.")
                else:
                    fuege_unteraufgabe_hinzu(parent_map[gew_parent_label], sub_titel, sub_zustaendig)
                    st.rerun()