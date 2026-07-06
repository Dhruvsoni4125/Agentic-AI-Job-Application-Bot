# app/bot/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📄 Upload/Update Resume"))
    builder.row(KeyboardButton(text="🔑 Configure Session Cookies"), KeyboardButton(text="🔍 Search Jobs"))
    builder.row(KeyboardButton(text="⚡ Optimize Resume (ATS)"), KeyboardButton(text="📋 Application History"))
    return builder.as_markup(resize_keyboard=True)

def get_platform_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="LinkedIn", callback_data="platform:linkedin")
    builder.button(text="Naukri", callback_data="platform:naukri")
    builder.adjust(2)
    return builder.as_markup()

def get_yes_no_keyboard(prefix: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes", callback_data=f"{prefix}:yes")
    builder.button(text="❌ No", callback_data=f"{prefix}:no")
    builder.adjust(2)
    return builder.as_markup()

def get_template_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Classic / ATS-safe", callback_data="template:classic")
    builder.button(text="Modern / Clean", callback_data="template:modern")
    builder.button(text="Creative / Bold", callback_data="template:creative")
    builder.adjust(1)
    return builder.as_markup()

def get_keyword_approval_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👍 Approve & Optimize", callback_data="keywords:approve")
    builder.button(text="✍️ Custom Keywords", callback_data="keywords:custom")
    builder.button(text="❌ Cancel", callback_data="keywords:cancel")
    builder.adjust(2, 1)
    return builder.as_markup()

def get_apply_confirmation_keyboard(job_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🚀 Auto-Apply Now", callback_data=f"apply:{job_id}:yes")
    builder.button(text="⏭️ Skip Job", callback_data=f"apply:{job_id}:no")
    builder.adjust(2)
    return builder.as_markup()
