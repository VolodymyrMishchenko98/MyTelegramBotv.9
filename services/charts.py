"""
Robust matplotlib chart generation.

Fixes for Windows / non-UTF-8 terminals:
* Register a DejaVu-based fallback font so Cyrillic / CJK text can render.
* Shut up matplotlib's deprecation warnings.
* Always return a valid ``io.BytesIO`` — never ``None`` or raise.
* Work entirely with the object-oriented API (no stateful ``plt.xticks`` calls).
"""
from __future__ import annotations

import io
import logging
import warnings
from datetime import datetime, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")                          # non-interactive — must be before pyplot
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.font_manager as _fm
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

log = logging.getLogger("services.charts")

# ── Font registration ─────────────────────────────────────────────────────────

def _register_fallback_font() -> None:
    """Ensure at least one readable font is the matplotlib default."""
    # DejaVu Sans ships with every matplotlib install and covers
    # Latin + Cyrillic + Greek without any extra files.
    for name in ("DejaVu Sans", "DejaVu Sans Mono", "Arial"):
        found = _fm.findfont(_fm.FontProperties(family=name), fallback_to_default=False)
        if found:
            plt.rcParams["font.family"]    = "sans-serif"
            plt.rcParams["font.sans-serif"] = [name]
            log.debug("Using matplotlib font: %s (%s)", name, found)
            return


_register_fallback_font()

# ── Palette ──────────────────────────────────────────────────────────────────

BG      = "#1A1D23"
PANEL   = "#21252E"
ACCENT1 = "#00E5FF"
ACCENT2 = "#FF6D3F"
TEXT    = "#E8E9EB"
GRID    = "#2E3340"
GREEN   = "#39D98A"
RED     = "#FF6B6B"


# ── helpers ──────────────────────────────────────────────────────────────────

def _fig():
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(PANEL)
    for sp in ax.spines.values():
        sp.set_edgecolor(GRID)
    ax.xaxis.label.set_color(TEXT)
    ax.yaxis.label.set_color(TEXT)
    ax.title.set_color(TEXT)
    ax.tick_params(colors=TEXT, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.6, alpha=0.8)
    return fig, ax


def _save(fig) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    buf.seek(0)
    plt.close(fig)
    return buf


def _empty_chart(msg: str) -> io.BytesIO:
    fig, ax = _fig()
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            fontsize=11, color=TEXT, transform=ax.transAxes)
    ax.set_xticks([])
    ax.set_yticks([])
    return _save(fig)


def _last_n_days(n: int):
    end   = datetime.now()
    start = end - timedelta(days=n - 1)
    return start, end


def _xticks(ax, ticks: list, labels: list | None = None,
            max_ticks: int = 8) -> None:
    """Apply x-axis tick labels.

    Parameters
    ----------
    ax:        matplotlib Axes
    ticks:     x-axis positions (datetime objects or ints)
    labels:    labels to write at each tick.  If *None*, the ticks themselves
               are formatted (``str(d)`` for ints, ``d.strftime("%d %b")``
               for datetimes).
    max_ticks: maximum number of tick labels to show (avoids overlap).
    """
    n = len(ticks)
    if n == 0:
        return
    step = max(1, n // max_ticks)
    idx  = list(range(0, n, step))
    ax.set_xticks([ticks[i] for i in idx])
    if labels is not None:
        tick_labels = [labels[i] for i in idx]
    elif isinstance(ticks[0], datetime):
        tick_labels = [ticks[i].strftime("%d %b") for i in idx]
    else:
        tick_labels = [str(ticks[i]) for i in idx]
    ax.set_xticklabels(tick_labels, rotation=30, ha="right",
                       fontsize=8, color=TEXT)
    ax.xaxis.label.set_fontsize(9)


# ── public API ────────────────────────────────────────────────────────────────

def weight_chart(user_id: int, db_fetch_all, days: int = 30) -> io.BytesIO:
    rows = db_fetch_all(
        "SELECT date, weight FROM weights "
        "WHERE user_id=? AND date >= ? ORDER BY date",
        (user_id, (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")),
    )
    if not rows:
        return _empty_chart("Немає даних про вагу / No weight data")

    dates, weights = zip(*rows)
    x = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
    fig, ax = _fig()
    colour = RED if weights[-1] < weights[0] else GREEN
    ax.plot(x, weights, color=colour, linewidth=2, marker="o", markersize=5)
    ax.fill_between(x, weights, alpha=0.12, color=colour)
    for xi, yi in zip(x, weights):
        ax.annotate(f"{yi:.1f}", (xi, yi),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7.5, color=TEXT)
    ax.set_title("Weight / Вага", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("кг", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    _xticks(ax, x)
    return _save(fig)


def workout_chart(user_id: int, db_fetch_all, days: int = 14) -> io.BytesIO:
    start, _ = _last_n_days(days)
    rows = db_fetch_all(
        "SELECT date, COUNT(*) "
        "FROM workouts WHERE user_id=? AND date >= ? GROUP BY date ORDER BY date",
        (user_id, start.strftime("%Y-%m-%d")),
    )
    if not rows:
        return _empty_chart("Немає даних / No workout data")

    dates, counts = zip(*rows)
    x = [datetime.strptime(d, "%Y-%m-%d") for d in dates]
    fig, ax = _fig()
    bars = ax.bar(x, counts, color=ACCENT1, width=0.6, alpha=0.82, zorder=2)
    ax.set_title("Тренування / Workouts", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("сесій", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    _xticks(ax, x)
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.1,
                str(int(h)), ha="center", va="bottom", fontsize=8, color=TEXT)
    return _save(fig)


def streak_chart(user_id: int, db_fetch_all, days: int = 30) -> io.BytesIO:
    start, _ = _last_n_days(days)
    rows = db_fetch_all(
        "SELECT date FROM workouts WHERE user_id=? AND date >= ? ORDER BY date",
        (user_id, start.strftime("%Y-%m-%d")),
    )
    active = {r[0] for r in rows}
    labels, vals = [], []
    cur = 0
    for i in range(days):
        day = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        if day in active:
            cur += 1
        else:
            if i > 0 and (start + timedelta(days=i - 1)).strftime("%Y-%m-%d") in active:
                cur = 0
        labels.append(day[5:])   # MM-DD
        vals.append(cur)

    fig, ax = _fig()
    x = list(range(days))
    colours = [
        GREEN if v >= 7 else (ACCENT1 if v >= 3 else GRID)
        for v in vals
    ]
    bars = ax.bar(x, vals, color=colours, width=0.7, alpha=0.88, zorder=2)
    ax.axhline(0, color=GRID, linewidth=0.8, zorder=1)
    ax.set_title("Серія / Streak", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("днів", fontsize=9)
    _xticks(ax, x, labels=labels)
    for bar in bars:
        h = bar.get_height()
        if h > 0:
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.15,
                    str(int(h)), ha="center", va="bottom", fontsize=7, color=TEXT)
    return _save(fig)


def volume_chart(user_id: int, db_fetch_all, days: int = 14) -> io.BytesIO:
    start, _ = _last_n_days(days)
    rows = db_fetch_all(
        "SELECT date, text FROM workouts "
        "WHERE user_id=? AND date >= ? ORDER BY date",
        (user_id, start.strftime("%Y-%m-%d")),
    )
    if not rows:
        return _empty_chart("Немає даних / No data")

    volumes: dict[str, int] = defaultdict(int)
    for d, text in rows:
        for n in __import__("re").findall(r"(\d+)", text):
            volumes[d] += int(n)

    sdates = sorted(volumes)
    x = [datetime.strptime(d, "%Y-%m-%d") for d in sdates]
    y = [volumes[d] for d in sdates]
    if not y:
        return _empty_chart("Немає даних / No data")

    fig, ax = _fig()
    ax.plot(x, y, color=ACCENT2, linewidth=2.2, marker="s", markersize=5, zorder=3)
    ax.fill_between(x, y, alpha=0.1, color=ACCENT2)
    ax.set_title("Обсяг / Volume", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("підйомів", fontsize=9)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
    _xticks(ax, x)
    for xi, yi in zip(x, y):
        ax.annotate(str(yi), (xi, yi),
                    textcoords="offset points", xytext=(0, 8),
                    ha="center", fontsize=7.5, color=TEXT)
    return _save(fig)
