#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, Qt, QTimer, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication, QVBoxLayout, QWidget

try:
    from PyQt6.QtWebChannel import QWebChannel
    from PyQt6.QtWebEngineCore import QWebEngineSettings
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
    WEBENGINE_ERROR = ""
except Exception as exc:
    QWebChannel = Any  # type: ignore[assignment]
    QWebEngineSettings = Any  # type: ignore[assignment]
    QWebEngineView = Any  # type: ignore[assignment]
    WEBENGINE_AVAILABLE = False
    WEBENGINE_ERROR = str(exc)


HERE = Path(__file__).resolve().parent
APP_DIR = HERE.parents[1]
ROOT = HERE.parents[3]
HTML_FILE = HERE / "code.html"
STATE_DIR = Path.home() / ".local" / "state" / "hanauta" / "study-tracker"
STATE_FILE = STATE_DIR / "state.json"

if str(APP_DIR) not in sys.path:
    sys.path.append(str(APP_DIR))

from pyqt.shared.runtime import python_executable
from pyqt.shared.theme import ThemePalette, blend, load_theme_palette, palette_mtime, rgba


DEFAULT_INSIGHTS: list[dict[str, str]] = [
    {
        "icon": "smart_toy",
        "accent": "primary",
        "title": "AI Enhanced Learning",
        "body": "Use Gemini or NotebookLM to condense dense material into summaries, drills, and quiz prompts before your first focus block.",
    },
    {
        "icon": "timer",
        "accent": "secondary",
        "title": "Time Management",
        "body": "Keep sessions short and intentional. A clean 25-minute block usually beats a vague hour of distracted studying.",
    },
    {
        "icon": "psychology",
        "accent": "tertiary",
        "title": "Cognitive Science",
        "body": "Practice active recall after each session. Closing the notes and explaining the idea back to yourself boosts retention fast.",
    },
    {
        "icon": "repeat",
        "accent": "primary",
        "title": "Retention Habits",
        "body": "Revisit yesterday's material before starting new content. Spaced repetition works best when it feels routine, not heroic.",
    },
]


def today_iso() -> str:
    return date.today().isoformat()


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def python_bin() -> str:
    return python_executable()


def notify(title: str, body: str) -> None:
    try:
        subprocess.Popen(
            ["notify-send", title, body],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass


def make_task(title: str, estimate_minutes: int, *, active: bool = False) -> dict[str, Any]:
    estimate = max(10, int(estimate_minutes))
    target_sessions = max(1, math.ceil(estimate / 25))
    return {
        "id": str(uuid.uuid4()),
        "title": title.strip() or "Study task",
        "estimate_minutes": estimate,
        "target_sessions": target_sessions,
        "sessions_completed": 0,
        "done": False,
        "active": active,
        "completed_at": "",
        "created_at": now_iso(),
    }


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "today_minutes": 0,
        "last_reset_date": today_iso(),
        "activity_dates": [],
        "insights": list(DEFAULT_INSIGHTS),
        "session_length_minutes": 25,
        "tasks": [
            {
                **make_task("Review N2 Vocabulary Flashcards", 25),
                "done": True,
                "active": False,
                "sessions_completed": 1,
                "completed_at": "08:30 AM",
            },
            {
                **make_task("Japanese Podcast: NHK News Easy", 60, active=True),
                "sessions_completed": 1,
            },
            make_task("Shadowing Practice: Genki Chapter 12", 15),
        ],
        "active_session": None,
    }


def normalize_state(payload: dict[str, Any] | None) -> dict[str, Any]:
    state = default_state()
    if isinstance(payload, dict):
        state.update(payload)
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
    normalized_tasks: list[dict[str, Any]] = []
    for raw_task in tasks:
        if not isinstance(raw_task, dict):
            continue
        base = make_task(str(raw_task.get("title", "Study task")), int(raw_task.get("estimate_minutes", 25) or 25))
        base.update(raw_task)
        base["done"] = bool(base.get("done", False))
        base["active"] = bool(base.get("active", False))
        base["sessions_completed"] = max(0, int(base.get("sessions_completed", 0) or 0))
        base["target_sessions"] = max(1, int(base.get("target_sessions", 1) or 1))
        normalized_tasks.append(base)
    if not normalized_tasks:
        normalized_tasks = default_state()["tasks"]
    state["tasks"] = normalized_tasks
    active_session = state.get("active_session")
    if not isinstance(active_session, dict):
        state["active_session"] = None
    else:
        state["active_session"] = {
            "task_id": str(active_session.get("task_id", "")),
            "elapsed_seconds": max(0, int(active_session.get("elapsed_seconds", 0) or 0)),
            "target_seconds": max(60, int(active_session.get("target_seconds", 25 * 60) or 25 * 60)),
            "running": bool(active_session.get("running", False)),
            "started_at": str(active_session.get("started_at", now_iso())),
        }
    insights = state.get("insights", [])
    if not isinstance(insights, list) or not insights:
        state["insights"] = list(DEFAULT_INSIGHTS)
    state["today_minutes"] = max(0, int(state.get("today_minutes", 0) or 0))
    last_reset = str(state.get("last_reset_date", today_iso()) or today_iso())
    state["last_reset_date"] = last_reset
    activity_dates = state.get("activity_dates", [])
    if not isinstance(activity_dates, list):
        activity_dates = []
    state["activity_dates"] = sorted({str(item) for item in activity_dates if str(item).strip()})
    _normalize_daily_rollover(state)
    _ensure_single_active_task(state)
    return state


def load_state() -> dict[str, Any]:
    try:
        payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        payload = default_state()
    return normalize_state(payload)


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _normalize_daily_rollover(state: dict[str, Any]) -> None:
    current = today_iso()
    if str(state.get("last_reset_date", "")) != current:
        state["today_minutes"] = 0
        state["last_reset_date"] = current


def _ensure_single_active_task(state: dict[str, Any]) -> None:
    active_seen = False
    for task in state.get("tasks", []):
        if task.get("done"):
            task["active"] = False
            continue
        if task.get("active") and not active_seen:
            active_seen = True
        else:
            task["active"] = False
    if active_seen:
        return
    for task in state.get("tasks", []):
        if not task.get("done"):
            task["active"] = True
            return


def compute_streak_days(state: dict[str, Any]) -> int:
    values = sorted({str(item) for item in state.get("activity_dates", []) if str(item).strip()}, reverse=True)
    if not values:
        return 0
    streak = 0
    cursor = date.today()
    value_set = set(values)
    while cursor.isoformat() in value_set:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def active_task(state: dict[str, Any]) -> dict[str, Any] | None:
    tasks = state.get("tasks", [])
    if not isinstance(tasks, list):
        return None
    for task in tasks:
        if isinstance(task, dict) and task.get("active") and not task.get("done"):
            return task
    for task in tasks:
        if isinstance(task, dict) and not task.get("done"):
            return task
    return None


def task_by_id(state: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    for task in state.get("tasks", []):
        if isinstance(task, dict) and str(task.get("id", "")) == task_id:
            return task
    return None


def build_summary_payload(state: dict[str, Any]) -> dict[str, Any]:
    current_task = active_task(state)
    session = state.get("active_session")
    session_payload: dict[str, Any] | None = None
    if isinstance(session, dict):
        session_payload = {
            "task_id": str(session.get("task_id", "")),
            "elapsed_seconds": max(0, int(session.get("elapsed_seconds", 0) or 0)),
            "target_seconds": max(60, int(session.get("target_seconds", 25 * 60) or 25 * 60)),
            "running": bool(session.get("running", False)),
        }
    return {
        "streak_days": compute_streak_days(state),
        "today_minutes": max(0, int(state.get("today_minutes", 0) or 0)),
        "agenda_date": datetime.now().strftime("%A, %b %d"),
        "session_length_minutes": max(1, int(state.get("session_length_minutes", 25) or 25)),
        "insights": state.get("insights", []),
        "tasks": state.get("tasks", []),
        "current_task": current_task,
        "active_session": session_payload,
    }


def theme_payload(theme: ThemePalette) -> dict[str, str]:
    surface_low = blend(theme.surface, theme.surface_container, 0.42)
    surface_lowest = blend(theme.surface, theme.surface_container, 0.18)
    surface_highest = blend(theme.surface_container_high, theme.surface_variant, 0.18)
    return {
        "primary": theme.primary,
        "onPrimary": theme.on_primary,
        "secondary": theme.secondary,
        "tertiary": theme.tertiary,
        "background": theme.background,
        "surface": theme.surface,
        "surfaceLow": surface_low,
        "surfaceLowest": surface_lowest,
        "surfaceHigh": theme.surface_container_high,
        "surfaceHighest": surface_highest,
        "outline": rgba(theme.outline, 0.68),
        "outlineSoft": rgba(theme.outline, 0.18),
        "text": theme.on_surface,
        "textMuted": rgba(theme.on_surface_variant, 0.74),
        "textSoft": rgba(theme.on_surface_variant, 0.44),
        "ambientPrimary": rgba(theme.primary, 0.09),
        "ambientSecondary": rgba(theme.secondary, 0.08),
        "railShadow": rgba(theme.primary, 0.08),
    }


def build_runtime_script() -> str:
    return r"""
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
(function () {
  const $ = (id) => document.getElementById(id);
  const escapeHtml = (value) => String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  let studyState = null;
  let studyTheme = null;
  let insightIndex = 0;
  let bridge = null;

  function formatMinutes(minutes) {
    const total = Math.max(0, Number(minutes || 0));
    if (total < 60) return `${total}m Today`;
    const hours = Math.floor(total / 60);
    const rem = total % 60;
    return rem ? `${hours}h ${rem}m Today` : `${hours}h Today`;
  }

  function formatSessionRemaining(session) {
    if (!session) return "";
    const remain = Math.max(0, Number(session.target_seconds || 0) - Number(session.elapsed_seconds || 0));
    const minutes = Math.floor(remain / 60);
    const seconds = remain % 60;
    return `${minutes}m ${String(seconds).padStart(2, "0")}s left`;
  }

  function currentTask() {
    return studyState?.current_task || null;
  }

  function renderObjective() {
    const task = currentTask();
    const session = studyState?.active_session || null;
    const headline = $("objectiveHeadline");
    const subject = $("objectiveSubject");
    const progressText = $("objectiveProgressText");
    const progressBar = $("objectiveProgressBar");
    if (!headline || !subject || !progressText || !progressBar) return;

    if (!task) {
      headline.innerHTML = `Choose your next <br><span class="text-primary" id="objectiveSubject">study target</span>`;
      progressText.textContent = "0 / 0";
      progressBar.style.width = "0%";
      return;
    }

    const completed = Math.max(0, Number(task.sessions_completed || 0));
    const target = Math.max(1, Number(task.target_sessions || 1));
    const remaining = Math.max(0, target - completed);
    const actionText = remaining > 0 ? `Finish ${remaining} Pomodoro${remaining === 1 ? "" : "s"} of` : "Keep momentum with";
    headline.innerHTML = `${escapeHtml(actionText)} <br><span class="text-primary" id="objectiveSubject">${escapeHtml(task.title)}</span>`;
    progressText.textContent = `${completed} / ${target}`;
    progressBar.style.width = `${Math.max(6, (completed / target) * 100)}%`;
    if (completed <= 0) {
      progressBar.style.width = "8%";
    }
    if (task.done) {
      progressBar.style.width = "100%";
    }
    if (session && String(session.task_id || "") === String(task.id || "")) {
      progressText.textContent = `${completed} / ${target} • ${formatSessionRemaining(session)}`;
    }
  }

  function insightCard(item) {
    const accent = item.accent || "primary";
    return `
      <div class="min-w-[280px] flex-shrink-0 snap-center glass-panel bg-[#0c0d18]/60 p-5 rounded-2xl border border-primary/10 hover:border-primary/30 transition-all group">
        <div class="flex items-center gap-3 mb-3">
          <div class="w-8 h-8 rounded-lg bg-${accent}/10 flex items-center justify-center text-${accent} group-hover:scale-110 transition-transform">
            <span class="material-symbols-outlined text-lg">${escapeHtml(item.icon || "lightbulb")}</span>
          </div>
          <span class="text-xs font-bold font-headline text-${accent}/80">${escapeHtml(item.title || "Study Insight")}</span>
        </div>
        <p class="text-sm leading-relaxed text-on-surface/80 font-body">${escapeHtml(item.body || "")}</p>
      </div>
    `;
  }

  function renderInsights() {
    const track = $("insightsTrack");
    const dots = $("insightDots");
    if (!track || !dots) return;
    const insights = Array.isArray(studyState?.insights) ? studyState.insights : [];
    if (!insights.length) {
      track.innerHTML = "";
      dots.innerHTML = "";
      return;
    }
    insightIndex = Math.max(0, Math.min(insightIndex, insights.length - 1));
    track.innerHTML = insights.map(insightCard).join("");
    dots.innerHTML = insights.map((_, index) => {
      const active = index === insightIndex;
      return `<div class="w-1.5 h-1.5 rounded-full ${active ? "bg-primary shadow-[0_0_8px_rgba(212,187,255,0.6)]" : "bg-surface-container-highest"}"></div>`;
    }).join("");
    const card = track.children[insightIndex];
    if (card) {
      card.scrollIntoView({behavior: "smooth", inline: "center", block: "nearest"});
    }
  }

  function taskRow(task) {
    const done = Boolean(task.done);
    const active = Boolean(task.active) && !done;
    const completed = Math.max(0, Number(task.sessions_completed || 0));
    const target = Math.max(1, Number(task.target_sessions || 1));
    const statusText = done
      ? `Completed ${escapeHtml(task.completed_at || "today")}`
      : active
        ? `In Progress • ${completed}/${target} sessions complete`
        : `Estimated: ${escapeHtml(task.estimate_minutes || 25)} mins • ${completed}/${target} sessions`;
    const icon = done
      ? `<span class="material-symbols-outlined text-xs text-on-primary" style="font-variation-settings: 'FILL' 1;">check</span>`
      : "";
    const badgeClass = done
      ? "border-primary bg-primary/20"
      : active
        ? "border-primary"
        : "border-outline-variant";
    const rowClass = done
      ? "p-4 rounded-lg bg-surface-container-low/30 hover:bg-surface-container-low/50 group"
      : active
        ? "p-6 rounded-lg bg-surface-container-high shadow-lg border-l-4 border-primary"
        : "p-4 rounded-lg bg-surface-container-low/30 hover:bg-surface-container-low/50 group";
    const titleClass = done
      ? "text-on-surface/50 line-through font-medium"
      : active
        ? "text-on-surface font-semibold text-lg"
        : "text-on-surface-variant font-medium group-hover:text-on-surface transition-colors";
    const detailClass = done
      ? "text-xs font-label text-on-surface-variant opacity-40"
      : active
        ? "text-xs font-label text-primary font-bold"
        : "text-xs font-label text-on-surface-variant/60";
    const controls = done ? `
      <button class="text-xs px-3 py-2 rounded-full bg-surface-container-high text-on-surface-variant" data-action="reactivate" data-task-id="${escapeHtml(task.id)}">Reopen</button>
    ` : `
      <button class="text-xs px-3 py-2 rounded-full bg-surface-container-high text-primary" data-action="focus" data-task-id="${escapeHtml(task.id)}">${active ? "Focused" : "Focus"}</button>
      <button class="text-xs px-3 py-2 rounded-full bg-primary/15 text-primary" data-action="toggle" data-task-id="${escapeHtml(task.id)}">${completed >= target ? "Finish" : "Mark Done"}</button>
    `;
    return `
      <div class="flex items-center gap-6 ${rowClass}" data-task-row="${escapeHtml(task.id)}">
        <button class="w-6 h-6 rounded-full border-2 ${badgeClass} flex items-center justify-center shrink-0" data-action="${done ? "reactivate" : "toggle"}" data-task-id="${escapeHtml(task.id)}">${icon}</button>
        <div class="flex-1 min-w-0">
          <p class="${titleClass}">${escapeHtml(task.title)}</p>
          <span class="${detailClass}">${statusText}</span>
        </div>
        <div class="flex items-center gap-2">${controls}</div>
      </div>
    `;
  }

  function renderAgenda() {
    const dateNode = $("agendaDate");
    const listNode = $("agendaList");
    if (dateNode) dateNode.textContent = studyState?.agenda_date || "";
    if (!listNode) return;
    const tasks = Array.isArray(studyState?.tasks) ? studyState.tasks : [];
    listNode.innerHTML = tasks.map(taskRow).join("");
    listNode.querySelectorAll("[data-action]").forEach((node) => {
      node.addEventListener("click", (event) => {
        event.preventDefault();
        event.stopPropagation();
        if (!bridge) return;
        const taskId = node.getAttribute("data-task-id") || "";
        const action = node.getAttribute("data-action") || "";
        if (action === "toggle") bridge.toggleTask(taskId);
        if (action === "focus") bridge.focusTask(taskId);
        if (action === "reactivate") bridge.reopenTask(taskId);
      });
    });
  }

  function renderChips() {
    if ($("streakChipText")) $("streakChipText").textContent = `${studyState?.streak_days || 0} Day Streak`;
    if ($("todayChipText")) $("todayChipText").textContent = formatMinutes(studyState?.today_minutes || 0);
  }

  function renderFab() {
    const label = $("studyFabLabel");
    const hint = $("studyFabHint");
    const icon = $("studyFabIcon");
    const session = studyState?.active_session || null;
    const task = currentTask();
    if (!label || !hint || !icon) return;
    if (session && session.running) {
      label.textContent = "Pause Session";
      hint.textContent = formatSessionRemaining(session);
      icon.textContent = "pause";
    } else if (session) {
      label.textContent = "Resume Session";
      hint.textContent = "Your focus block is waiting";
      icon.textContent = "play_arrow";
    } else if (task) {
      label.textContent = "Start Study Session";
      hint.textContent = `Focused on ${task.title}`;
      icon.textContent = "play_arrow";
    } else {
      label.textContent = "Add a Study Task";
      hint.textContent = "Build a small plan first";
      icon.textContent = "add";
    }
  }

  function render() {
    if (!studyState) return;
    renderChips();
    renderObjective();
    renderInsights();
    renderAgenda();
    renderFab();
  }

  function wireActions() {
    $("studyFabButton")?.addEventListener("click", () => {
      if (bridge) bridge.startOrPauseSession();
    });
    $("addTaskButton")?.addEventListener("click", () => {
      if (!bridge) return;
      const title = window.prompt("What do you want to study next?");
      if (!title || !title.trim()) return;
      const estimate = window.prompt("Estimated minutes?", "25");
      bridge.addTask(title.trim(), Number.parseInt(estimate || "25", 10) || 25);
    });
    $("insightPrevButton")?.addEventListener("click", () => {
      const items = Array.isArray(studyState?.insights) ? studyState.insights : [];
      if (!items.length) return;
      insightIndex = (insightIndex - 1 + items.length) % items.length;
      renderInsights();
    });
    $("insightNextButton")?.addEventListener("click", () => {
      const items = Array.isArray(studyState?.insights) ? studyState.insights : [];
      if (!items.length) return;
      insightIndex = (insightIndex + 1) % items.length;
      renderInsights();
    });
  }

  window.setStudyState = function (payloadJson) {
    studyState = JSON.parse(payloadJson);
    render();
  };

  window.applyStudyTheme = function (payloadJson) {
    studyTheme = JSON.parse(payloadJson);
    const root = document.documentElement;
    Object.entries(studyTheme).forEach(([key, value]) => {
      root.style.setProperty(`--study-${key}`, String(value));
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    const extraStyle = document.createElement("style");
    extraStyle.textContent = `
      body {
        background: radial-gradient(circle at top right, var(--study-surfaceLow, #1a1b26) 0%, var(--study-background, #12131d) 100%);
        color: var(--study-text, #e2e1f1);
      }
      aside {
        background: var(--study-surfaceLow, #1a1b26) !important;
        box-shadow: 40px 0 60px -15px var(--study-railShadow, rgba(212,187,255,0.05)) !important;
      }
      header {
        background: color-mix(in srgb, var(--study-background, #12131d) 80%, transparent) !important;
      }
      .glass-panel {
        background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 70%, transparent) !important;
      }
      .bg-surface-container-low { background: var(--study-surfaceLow, #1a1b26) !important; }
      .bg-surface-container-high { background: var(--study-surfaceHigh, #282935) !important; }
      .bg-surface-container-highest { background: var(--study-surfaceHighest, #333440) !important; }
      .bg-surface-container-low\\/30 { background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 30%, transparent) !important; }
      .hover\\:bg-surface-container-low\\/50:hover { background: color-mix(in srgb, var(--study-surfaceLow, #1a1b26) 50%, transparent) !important; }
      .text-primary, .hover\\:text-primary:hover { color: var(--study-primary, #d4bbff) !important; }
      .text-secondary { color: var(--study-secondary, #ffb2bc) !important; }
      .text-tertiary { color: var(--study-tertiary, #aec6ff) !important; }
      .text-on-surface, .group-hover\\:text-on-surface:hover { color: var(--study-text, #e2e1f1) !important; }
      .text-on-surface-variant, .text-\\[\\#4a4550\\] { color: var(--study-textMuted, #ccc3d2) !important; }
      .text-on-surface-variant\\/60 { color: var(--study-textMuted, #ccc3d2) !important; opacity: 0.7 !important; }
      .text-on-surface-variant\\/20 { color: var(--study-textSoft, #777) !important; opacity: 0.5 !important; }
      .border-primary { border-color: var(--study-primary, #d4bbff) !important; }
      .border-outline-variant { border-color: var(--study-outline, #4a4550) !important; }
      .bg-primary, .hover\\:bg-primary:hover { background: var(--study-primary, #d4bbff) !important; }
      .bg-primary\\/20 { background: color-mix(in srgb, var(--study-primary, #d4bbff) 20%, transparent) !important; }
      .bg-primary\\/15 { background: color-mix(in srgb, var(--study-primary, #d4bbff) 15%, transparent) !important; }
      .bg-primary\\/10 { background: color-mix(in srgb, var(--study-primary, #d4bbff) 10%, transparent) !important; }
      .bg-secondary\\/10 { background: color-mix(in srgb, var(--study-secondary, #ffb2bc) 10%, transparent) !important; }
      .bg-tertiary\\/10 { background: color-mix(in srgb, var(--study-tertiary, #aec6ff) 10%, transparent) !important; }
      .text-on-primary { color: var(--study-onPrimary, #3d1b72) !important; }
    `;
    document.head.appendChild(extraStyle);

    wireActions();
    new QWebChannel(qt.webChannelTransport, function (channel) {
      bridge = channel.objects.studyBridge;
      if (bridge) bridge.requestBootstrap();
    });
  });
})();
</script>
"""


def build_html(theme: ThemePalette) -> str:
    base_html = HTML_FILE.read_text(encoding="utf-8")
    injected = build_runtime_script()
    return base_html.replace("</body></html>", f"{injected}\n</body></html>")


class StudyBridge(QObject):
    bootstrapRequested = pyqtSignal()
    addTaskRequested = pyqtSignal(str, int)
    toggleTaskRequested = pyqtSignal(str)
    focusTaskRequested = pyqtSignal(str)
    reopenTaskRequested = pyqtSignal(str)
    sessionToggleRequested = pyqtSignal()

    @pyqtSlot()
    def requestBootstrap(self) -> None:
        self.bootstrapRequested.emit()

    @pyqtSlot(str, int)
    def addTask(self, title: str, estimate_minutes: int) -> None:
        self.addTaskRequested.emit(title, estimate_minutes)

    @pyqtSlot(str)
    def toggleTask(self, task_id: str) -> None:
        self.toggleTaskRequested.emit(task_id)

    @pyqtSlot(str)
    def focusTask(self, task_id: str) -> None:
        self.focusTaskRequested.emit(task_id)

    @pyqtSlot(str)
    def reopenTask(self, task_id: str) -> None:
        self.reopenTaskRequested.emit(task_id)

    @pyqtSlot()
    def startOrPauseSession(self) -> None:
        self.sessionToggleRequested.emit()


class StudyTrackerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        if not WEBENGINE_AVAILABLE:
            raise RuntimeError(f"QtWebEngine is unavailable: {WEBENGINE_ERROR}")
        self.theme = load_theme_palette()
        self._theme_mtime = palette_mtime()
        self.state = load_state()
        self._page_ready = False

        self.setWindowTitle("Hanauta Study Track")
        self.resize(1440, 980)
        self.setMinimumSize(1080, 760)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.view = QWebEngineView(self)
        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True)
        layout.addWidget(self.view)

        self.channel = QWebChannel(self.view.page())
        self.bridge = StudyBridge()
        self.channel.registerObject("studyBridge", self.bridge)
        self.view.page().setWebChannel(self.channel)
        self.view.loadFinished.connect(self._handle_load_finished)

        self.bridge.bootstrapRequested.connect(self.push_state)
        self.bridge.addTaskRequested.connect(self.add_task)
        self.bridge.toggleTaskRequested.connect(self.toggle_task)
        self.bridge.focusTaskRequested.connect(self.focus_task)
        self.bridge.reopenTaskRequested.connect(self.reopen_task)
        self.bridge.sessionToggleRequested.connect(self.start_or_pause_session)

        self.session_timer = QTimer(self)
        self.session_timer.timeout.connect(self._tick_session)
        self.session_timer.start(1000)

        self.theme_timer = QTimer(self)
        self.theme_timer.timeout.connect(self._reload_theme_if_needed)
        self.theme_timer.start(3000)

        self._load_page()

    def _load_page(self) -> None:
        html = build_html(self.theme)
        self.view.setHtml(html, QUrl.fromLocalFile(str(HERE) + "/"))

    def _handle_load_finished(self, ok: bool) -> None:
        self._page_ready = ok
        if ok:
            self.push_theme()
            self.push_state()

    def _run_js(self, script: str) -> None:
        if not self._page_ready:
            return
        self.view.page().runJavaScript(script)

    def _save(self) -> None:
        save_state(self.state)

    def push_state(self) -> None:
        payload = json.dumps(build_summary_payload(self.state))
        self._run_js(f"window.setStudyState({json.dumps(payload)});")

    def push_theme(self) -> None:
        payload = json.dumps(theme_payload(self.theme))
        self._run_js(f"window.applyStudyTheme({json.dumps(payload)});")

    def _reload_theme_if_needed(self) -> None:
        current = palette_mtime()
        if current == self._theme_mtime:
            return
        self._theme_mtime = current
        self.theme = load_theme_palette()
        self.push_theme()

    def add_task(self, title: str, estimate_minutes: int) -> None:
        task = make_task(title, estimate_minutes)
        if not any(not item.get("done") for item in self.state.get("tasks", [])):
            task["active"] = True
        self.state.setdefault("tasks", []).append(task)
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()

    def toggle_task(self, task_id: str) -> None:
        task = task_by_id(self.state, task_id)
        if task is None:
            return
        done = not bool(task.get("done", False))
        task["done"] = done
        task["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0") if done else ""
        if done:
            task["active"] = False
            session = self.state.get("active_session")
            if isinstance(session, dict) and str(session.get("task_id", "")) == task_id:
                self.state["active_session"] = None
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()

    def focus_task(self, task_id: str) -> None:
        for task in self.state.get("tasks", []):
            task["active"] = str(task.get("id", "")) == task_id and not bool(task.get("done", False))
        _ensure_single_active_task(self.state)
        session = self.state.get("active_session")
        if isinstance(session, dict):
            session["task_id"] = task_id
        self._save()
        self.push_state()

    def reopen_task(self, task_id: str) -> None:
        task = task_by_id(self.state, task_id)
        if task is None:
            return
        task["done"] = False
        task["completed_at"] = ""
        for item in self.state.get("tasks", []):
            item["active"] = str(item.get("id", "")) == task_id
        _ensure_single_active_task(self.state)
        self._save()
        self.push_state()

    def start_or_pause_session(self) -> None:
        task = active_task(self.state)
        if task is None:
            return
        session = self.state.get("active_session")
        target_seconds = max(60, int(self.state.get("session_length_minutes", 25) or 25) * 60)
        if not isinstance(session, dict):
            self.state["active_session"] = {
                "task_id": str(task.get("id", "")),
                "elapsed_seconds": 0,
                "target_seconds": target_seconds,
                "running": True,
                "started_at": now_iso(),
            }
            notify("Study session started", f"Focus on {task.get('title', 'your task')}.")
        else:
            if str(session.get("task_id", "")) != str(task.get("id", "")):
                session["task_id"] = str(task.get("id", ""))
                session["elapsed_seconds"] = 0
                session["target_seconds"] = target_seconds
            session["running"] = not bool(session.get("running", False))
            if session["running"]:
                session["started_at"] = now_iso()
        self._save()
        self.push_state()

    def _tick_session(self) -> None:
        session = self.state.get("active_session")
        if not isinstance(session, dict) or not bool(session.get("running", False)):
            return
        session["elapsed_seconds"] = max(0, int(session.get("elapsed_seconds", 0) or 0) + 1)
        if int(session.get("elapsed_seconds", 0) or 0) >= int(session.get("target_seconds", 0) or 0):
            self._complete_session()
            return
        self.push_state()

    def _complete_session(self) -> None:
        session = self.state.get("active_session")
        if not isinstance(session, dict):
            return
        task = task_by_id(self.state, str(session.get("task_id", "")))
        added_minutes = max(1, int(session.get("target_seconds", 0) or 0) // 60)
        self.state["today_minutes"] = max(0, int(self.state.get("today_minutes", 0) or 0) + added_minutes)
        self.state.setdefault("activity_dates", [])
        self.state["activity_dates"] = sorted({*self.state["activity_dates"], today_iso()})
        if task is not None:
            task["sessions_completed"] = max(0, int(task.get("sessions_completed", 0) or 0) + 1)
            if int(task.get("sessions_completed", 0) or 0) >= int(task.get("target_sessions", 1) or 1):
                task["done"] = True
                task["active"] = False
                task["completed_at"] = datetime.now().strftime("%I:%M %p").lstrip("0")
        self.state["active_session"] = None
        _ensure_single_active_task(self.state)
        self._save()
        if task is not None:
            notify("Study session complete", f"You finished a focus block for {task.get('title', 'your task')}.")
        else:
            notify("Study session complete", "A focus block has been completed.")
        self.push_state()


def main() -> int:
    if not WEBENGINE_AVAILABLE:
        message = (
            "PyQt6 QtWebEngine is not installed in the current environment. "
            "Install the PyQt6 WebEngine package to run Hanauta Study Track."
        )
        print(message, file=sys.stderr)
        notify("Hanauta Study Track", message)
        return 1
    app = QApplication(sys.argv)
    app.setApplicationName("Hanauta Study Track")
    window = StudyTrackerWindow()
    screen = QGuiApplication.primaryScreen()
    if screen is not None:
        geometry = screen.availableGeometry()
        window.move(
            geometry.x() + max(0, (geometry.width() - window.width()) // 2),
            geometry.y() + max(0, (geometry.height() - window.height()) // 2),
        )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
