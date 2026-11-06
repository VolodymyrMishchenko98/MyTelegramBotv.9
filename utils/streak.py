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


def calculate_streak(last_workout_date: str | None, workout_dates: list[str]) -> int:
    """Calculate the current streak based on last_workout_date and all workout dates."""
    if not workout_dates:
        return 0

    used = set(workout_dates)
    today = datetime.now().date()

    # If the last_workout_date exists and is recent, start from there
    if last_workout_date:
        try:
            last = datetime.strptime(last_workout_date, "%Y-%m-%d").date()
            start = last if (today - last).days <= STREAK_THRESHOLD_DAYS else today
        except ValueError:
            start = today
    else:
        start = today

    streak = 0
    while True:
        day = start - timedelta(days=streak)
        if day.strftime("%Y-%m-%d") in used:
            streak += 1
        else:
            break
    return streak


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
