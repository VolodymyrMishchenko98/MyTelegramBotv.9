"""Streak system: update, calculate, and reward consecutive workout days."""
from datetime import datetime, timedelta

STREAK_THRESHOLD_DAYS = 1   # gap of <= 1 day preserves the streak
STREAK_BONUS_COINS = {
    3:  10,
    5:  20,
    7:  30,
    10: 40,
    14: 50,
    21: 75,
    30: 100,
}
STREAK_BONUS_XP = {
    3:  10,
    5:  25,
    7:  50,
    10: 80,
    14: 120,
    21: 200,
    30: 350,
}


def _valid_workout_dates(workout_dates: list[str]) -> set:
    """Normalize valid YYYY-MM-DD values and collapse duplicate workout rows."""
    result = set()
    for value in workout_dates:
        try:
            result.add(datetime.strptime(str(value), "%Y-%m-%d").date())
        except (TypeError, ValueError):
            continue
    return result


def calculate_streak(last_workout_date: str | None, workout_dates: list[str]) -> int:
    """Calculate the active streak from unique calendar dates.

    ``last_workout_date`` remains in the public signature for compatibility;
    the complete date history is the source of truth for the calculation.
    A streak remains active when the latest workout was today or yesterday.
    """
    dates = _valid_workout_dates(workout_dates)
    if not dates:
        return 0

    today = datetime.now().date()
    latest = max(dates)
    if latest < today - timedelta(days=STREAK_THRESHOLD_DAYS):
        return 0

    streak = 0
    day = latest
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def calculate_best_streak(workout_dates: list[str]) -> int:
    """Return the longest consecutive run of unique workout dates."""
    dates = sorted(_valid_workout_dates(workout_dates))
    if not dates:
        return 0

    best = current = 1
    for previous, current_date in zip(dates, dates[1:]):
        if (current_date - previous).days == 1:
            current += 1
            best = max(best, current)
        else:
            current = 1
    return best


def get_streak_bonus(streak_days: int) -> tuple[int, int]:
    """Return (bonus_coins, bonus_xp) for the given streak, if any milestone is reached."""
    best_coins = 0
    best_xp = 0
    for threshold, coins in STREAK_BONUS_COINS.items():
        if streak_days >= threshold:
            best_coins = coins
    for threshold, xp in STREAK_BONUS_XP.items():
        if streak_days >= threshold:
            best_xp = xp
    return best_coins, best_xp


def update_streak(user_id: int, workout_date: str, earned_xp: int = 0) -> dict:
    """Update user streak in DB after a workout.
    Returns a dict with keys: streak_days, bonus_coins, bonus_xp, leveled_up, new_level.
    """
    from db_improved import get_db, fetch_one

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "SELECT streak_days, last_workout_date FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cur.fetchone()
    prev_streak = row[0] if row and row[0] is not None else 0
    prev_date = row[1] if row else None
    db.close()

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Determine if this extends or resets the streak
    if prev_date == workout_date:
        # Already logged today — streak unchanged
        return dict(streak_days=prev_streak, bonus_coins=0, bonus_xp=0, leveled_up=False, new_level=prev_streak)

    if prev_date:
        gap = (datetime.strptime(workout_date, "%Y-%m-%d") -
               datetime.strptime(prev_date, "%Y-%m-%d")).days
        if gap > STREAK_THRESHOLD_DAYS:
            new_streak = 1
        else:
            new_streak = prev_streak + 1
    else:
        new_streak = 1

    bonus_coins, bonus_xp = get_streak_bonus(new_streak)

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE users SET streak_days=?, last_workout_date=? WHERE user_id=?",
        (new_streak, workout_date, user_id)
    )
    db.commit()
    db.close()

    return dict(
        streak_days=new_streak,
        bonus_coins=bonus_coins,
        bonus_xp=bonus_xp,
        leveled_up=False,
        new_level=new_streak,
    )
