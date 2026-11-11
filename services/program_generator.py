"""Deterministic, conservative training-plan generation from user preferences."""
from __future__ import annotations

from typing import Any


GOALS = {"general", "strength", "endurance", "mobility", "sport"}
LOCATIONS = {"home", "gym", "outdoors"}
FREQUENCIES = {"2-3", "4", "5"}
DURATIONS = {"15-20", "30", "45", "60"}
LEVELS = {"beginner", "intermediate", "advanced"}
EQUIPMENT = {"none", "dumbbells", "pullup_bar", "machines", "other"}
MAX_NOTES_LENGTH = 500

_WEEKDAYS = {
    "2-3": ("monday", "wednesday", "friday"),
    "4": ("monday", "wednesday", "friday", "sunday"),
    "5": ("monday", "tuesday", "thursday", "friday", "sunday"),
}

_GOAL_SESSIONS = {
    "general": ("full_a", "cardio", "full_b", "mobility", "full_c"),
    "strength": ("strength_a", "strength_b", "strength_a", "strength_b", "strength_a"),
    "endurance": ("endurance_a", "endurance_b", "endurance_a", "endurance_b", "endurance_a"),
    "mobility": ("mobility_a", "mobility_b", "mobility_a", "mobility_b", "mobility_a"),
    "sport": ("sport_a", "sport_b", "sport_a", "sport_b", "sport_a"),
}

_SESSION_EXERCISES = {
    "full_a": ("squat", "push", "pull", "glute_bridge", "dead_bug"),
    "full_b": ("step_back", "push", "pull", "bird_dog", "brisk_walk"),
    "full_c": ("squat", "push", "pull", "glute_bridge", "march"),
    "strength_a": ("squat", "push", "pull", "glute_bridge", "dead_bug"),
    "strength_b": ("step_back", "push", "pull", "glute_bridge", "bird_dog"),
    "endurance_a": ("brisk_walk", "march", "squat", "bird_dog", "cat_cow"),
    "endurance_b": ("brisk_walk", "march", "step_back", "dead_bug", "hip_mobility"),
    "mobility_a": ("cat_cow", "hip_mobility", "shoulder_mobility", "glute_bridge", "brisk_walk"),
    "mobility_b": ("cat_cow", "hip_mobility", "shoulder_mobility", "bird_dog", "march"),
    "sport_a": ("brisk_walk", "squat", "push", "pull", "dead_bug"),
    "sport_b": ("march", "step_back", "glute_bridge", "bird_dog", "hip_mobility"),
    "cardio": ("brisk_walk", "march", "squat", "dead_bug", "hip_mobility"),
    "mobility": ("cat_cow", "hip_mobility", "shoulder_mobility", "bird_dog", "brisk_walk"),
}

_SESSION_TITLES = {
    "full_a": "program_session_full_a",
    "full_b": "program_session_full_b",
    "full_c": "program_session_full_c",
    "strength_a": "program_session_strength_a",
    "strength_b": "program_session_strength_b",
    "endurance_a": "program_session_endurance_a",
    "endurance_b": "program_session_endurance_b",
    "mobility_a": "program_session_mobility_a",
    "mobility_b": "program_session_mobility_b",
    "sport_a": "program_session_sport_a",
    "sport_b": "program_session_sport_b",
    "cardio": "program_session_cardio",
    "mobility": "program_session_mobility",
}

_EXERCISE_TITLES = {
    "squat": "program_exercise_squat",
    "push": "program_exercise_push",
    "pull": "program_exercise_pull",
    "glute_bridge": "program_exercise_glute_bridge",
    "dead_bug": "program_exercise_dead_bug",
    "bird_dog": "program_exercise_bird_dog",
    "step_back": "program_exercise_step_back",
    "brisk_walk": "program_exercise_brisk_walk",
    "march": "program_exercise_march",
    "cat_cow": "program_exercise_cat_cow",
    "hip_mobility": "program_exercise_hip_mobility",
    "shoulder_mobility": "program_exercise_shoulder_mobility",
}

_EXTRA_EQUIPMENT_TERMS = {
    "dumbbells": {"гантелі", "гантели", "dumbbells", "dumbbell"},
    "pullup_bar": {"турнік", "турник", "pull-up bar", "pullup bar"},
    "machines": {"тренажери", "тренажёры", "machines", "gym machines"},
    "bands": {
        "гумові стрічки",
        "резинки",
        "еспандер",
        "resistance bands",
        "resistance band",
        "bands",
    },
}


def validate_preferences(preferences: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize answers before generation or persistence."""
    if not isinstance(preferences, dict):
        raise ValueError("Preferences must be an object")

    normalized = dict(preferences)
    for field, choices in (
        ("goal", GOALS),
        ("location", LOCATIONS),
        ("frequency", FREQUENCIES),
        ("duration", DURATIONS),
        ("level", LEVELS),
    ):
        value = normalized.get(field)
        if not isinstance(value, str) or value not in choices:
            raise ValueError(f"Invalid {field}")

    equipment = normalized.get("equipment")
    if not isinstance(equipment, list) or not equipment:
        raise ValueError("Select at least one equipment option")
    if any(not isinstance(item, str) or item not in EQUIPMENT for item in equipment):
        raise ValueError("Invalid equipment")
    if "none" in equipment and len(equipment) > 1:
        raise ValueError("No-equipment option cannot be combined")
    normalized["equipment"] = sorted(set(equipment))

    notes = normalized.get("notes", "")
    if not isinstance(notes, str) or len(notes.strip()) > MAX_NOTES_LENGTH:
        raise ValueError("Invalid additional notes")
    normalized["notes"] = notes.strip()
    other_equipment = normalized.get("other_equipment", "")
    if not isinstance(other_equipment, str) or len(other_equipment.strip()) > 120:
        raise ValueError("Invalid additional equipment")
    normalized["other_equipment"] = other_equipment.strip()
    return normalized


def _include_extra_equipment(preferences: dict[str, Any]) -> set[str]:
    available = set(preferences["equipment"])
    if "other" not in available:
        return available
    details = preferences.get("other_equipment", "").casefold()
    tokens = {
        token.strip()
        for token in details.replace(";", ",").replace("\n", ",").split(",")
        if token.strip()
    }
    for equipment, terms in _EXTRA_EQUIPMENT_TERMS.items():
        if tokens.intersection(terms):
            available.add(equipment)
    return available


def _exercise_id(
    exercise: str,
    equipment: set[str],
    level: str,
    location: str,
) -> str:
    if exercise == "brisk_walk":
        if location == "gym" and "machines" in equipment:
            return "program_stationary_bike"
        if location == "home":
            return "program_exercise_march"
    if exercise == "squat":
        if "machines" in equipment:
            return "program_machine_leg_press"
        if "dumbbells" in equipment:
            return "program_dumbbell_squat"
        return "program_exercise_squat"
    if exercise == "push":
        if "machines" in equipment:
            return "program_machine_chest_press"
        if "bands" in equipment:
            return "program_band_press"
        if "dumbbells" in equipment:
            return "program_dumbbell_press"
        return "program_wall_pushup" if level == "beginner" else "program_incline_pushup"
    if exercise == "pull":
        if "machines" in equipment:
            return "program_machine_row"
        if "bands" in equipment:
            return "program_band_row"
        if "dumbbells" in equipment:
            return "program_dumbbell_row"
        if "pullup_bar" in equipment:
            return "program_supported_hang"
        return "program_prone_w_raise"
    return _EXERCISE_TITLES[exercise]


def generate_program(
    preferences: dict[str, Any],
    *,
    age: int | None = None,
) -> dict[str, Any]:
    """Build a moderate weekly plan without max lifts or failure training."""
    answers = validate_preferences(preferences)
    equipment = _include_extra_equipment(answers)
    days = _WEEKDAYS[answers["frequency"]]
    duration = {"15-20": 20, "30": 30, "45": 45, "60": 60}[answers["duration"]]
    sessions_per_week = len(days)

    if answers["level"] == "beginner" or (age is not None and age < 18):
        sets, repetitions, rest = 2, "8–10", 75
    elif answers["level"] == "intermediate":
        sets, repetitions, rest = 3, "8–12", 75
    else:
        sets, repetitions, rest = 3, "10–12", 90

    exercise_count = 3 if duration == 20 else 4 if duration == 30 else 5
    title_sequence = _GOAL_SESSIONS[answers["goal"]]
    sessions = []
    for index, day in enumerate(days):
        is_light_recovery_session = (
            answers["frequency"] == "5" and index in (1, 3)
        )
        sequence_index = index // 2 if answers["frequency"] == "5" else index
        session_id = (
            "mobility"
            if is_light_recovery_session
            else title_sequence[sequence_index]
        )
        selected = _SESSION_EXERCISES[session_id][:exercise_count]
        exercises = []
        for exercise in selected:
            item = _exercise_id(
                exercise,
                equipment,
                answers["level"],
                answers["location"],
            )
            is_timed = item in {
                "brisk_walk", "march", "program_exercise_march",
                "program_stationary_bike",
                "cat_cow", "hip_mobility",
                "shoulder_mobility", "program_supported_hang",
            }
            exercise_data: dict[str, Any] = {
                "key": item,
                "prescription_key": (
                    "program_prescription_minutes" if is_timed
                    else "program_prescription_reps"
                ),
                "sets": sets,
                "reps": repetitions,
                "minutes": 2 if duration == 20 else 3,
            }
            if item in {"brisk_walk", "march"}:
                exercise_data["minutes"] = 5 if duration == 20 else 8
            exercises.append(exercise_data)

        sessions.append({
            "day_key": f"program_day_{day}",
            "title_key": _SESSION_TITLES[session_id],
            "objective_key": (
                "program_objective_mobility"
                if is_light_recovery_session
                else f"program_objective_{answers['goal']}"
            ),
            "warmup_key": "program_warmup_detail",
            "cooldown_key": "program_cooldown_detail",
            "exercises": exercises,
            "rest_seconds": rest,
            "duration_minutes": duration,
        })

    return {
        "version": 1,
        "goal": answers["goal"],
        "sessions_per_week": sessions_per_week,
        "duration_minutes": duration,
        "level": answers["level"],
        "minor_guidance": age is not None and age < 18,
        "sessions": sessions,
        "progression_keys": [
            "program_progression_week_1",
            "program_progression_week_2",
            "program_progression_week_3",
            "program_progression_week_4",
        ],
        "safety_key": "program_safety_minor" if age is not None and age < 18
        else "program_safety_general",
    }
