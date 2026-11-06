from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    waiting_height = State()
    waiting_gender = State()
    waiting_age = State()
    waiting_goal = State()
    waiting_weekly_goal = State()
    waiting_weight = State()


class WorkoutFlow(StatesGroup):
    waiting_workout_text = State()
    waiting_calories_query = State()


class WeightFlow(StatesGroup):
    waiting_weight_input = State()


class ProfileEdit(StatesGroup):
    waiting_new_value = State()
