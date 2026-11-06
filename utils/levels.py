"""Level system: XP thresholds and rank definitions."""
from datetime import date

# XP required to advance from level L to level L+1
# Level 1 → 2 needs XP[0], level 2 → 3 needs XP[1], … level 30 → 31 needs XP[29]
XP_TABLE = [
    100,   # 1  → 2
    200,   # 2  → 3
    400,   # 3  → 4
    600,   # 4  → 5
    900,   # 5  → 6
    1300,  # 6  → 7
    1800,  # 7  → 8
    2400,  # 8  → 9
    3100,  # 9  → 10
    3900,  # 10 → 11
    4900,  # 11 → 12
    6100,  # 12 → 13
    7500,  # 13 → 14
    9100,  # 14 → 15
    10900, # 15 → 16
    13000, # 16 → 17
    15400, # 17 → 18
    18100, # 18 → 19
    21100, # 19 → 20
    24400, # 20 → 21
    28000, # 21 → 22
    31900, # 22 → 23
    36100, # 23 → 24
    40600, # 24 → 25
    45400, # 25 → 26
    50500, # 26 → 27
    55900, # 27 → 28
    61600, # 28 → 29
    67600, # 29 → 30
    73900, # 30 → 31
]
MAX_LEVEL = len(XP_TABLE) + 1  # 31

RANKS = {
    1:  ("Новичок",        "Beginner"),
    5:  ("Аматор",         "Amateur"),
    10: ("Спортсмен",      "Athlete"),
    15: ("Професіонал",    "Pro"),
    20: ("Еліта",          "Elite"),
    25: ("Легенда",        "Legend"),
    30: ("Монстр режиму",  "Beast Mode"),
}
DEFAULT_RANK = ("Новичок", "Beginner")


def get_rank(level: int) -> tuple:
    """Return (uk, en) rank name for the given level."""
    best = DEFAULT_RANK
    for threshold, rank in sorted(RANKS.items()):
        if level >= threshold:
            best = rank
        else:
            break
    return best


def xp_for_next_level(level: int) -> int | None:
    """XP needed to advance from current level to the next. None if at max level."""
    idx = level - 1
    if idx < len(XP_TABLE):
        return XP_TABLE[idx]
    return None


def total_xp_for_level(level: int) -> int:
    """Total XP accumulated when reaching a given level."""
    return sum(XP_TABLE[:level - 1])


def get_level_from_xp(xp: int) -> int:
    """Derive level from total XP."""
    level = 1
    for threshold in XP_TABLE:
        if xp >= threshold:
            xp -= threshold
            level += 1
        else:
            break
    return level


def get_progress_in_level(level: int, xp: int) -> tuple[int, int]:
    """Return (current_xp_in_level, xp_needed) for the progress bar."""
    prev_total = total_xp_for_level(level)
    needed = xp_for_next_level(level)
    if needed is None:
        return 0, 1
    return max(0, xp - prev_total), needed
