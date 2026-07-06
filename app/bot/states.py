# app/bot/states.py
from aiogram.fsm.state import State, StatesGroup

class Onboarding(StatesGroup):
    waiting_resume = State()
    waiting_role = State()
    waiting_experience = State()
    waiting_locations = State()

class CookieAuth(StatesGroup):
    waiting_platform = State()
    waiting_cookie = State()

class OptimizeFlow(StatesGroup):
    waiting_jd = State()
    waiting_keywords_approval = State()
    waiting_custom_keywords = State()
    waiting_template_choice = State()
    waiting_apply_confirmation = State()

