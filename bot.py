import os
import logging
import datetime
import asyncio
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, CallbackQueryHandler, filters
)
from supabase import create_client, Client

# تنظیمات لاگینگ
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------------------------------
# ۱. وب‌سرور Flask برای زنده نگه‌داشتن در Render
# ----------------------------------------------------
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "⚡ Gym Assistant Bot is Running Smoothly!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ----------------------------------------------------
# ۲. متغیرهای محیطی و اتصال به Supabase
# ----------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# وضعیت‌های ConversationHandler
(
    OB_AGE, OB_HEIGHT, OB_WEIGHT, OB_ARM, OB_CHEST, OB_WAIST, OB_GOAL,
    PLAN_DAYS_COUNT, PLAN_DAY_NAME, PLAN_EX_COUNT, PLAN_EX_NAME, PLAN_EX_SETS_REPS, PLAN_EX_SUPERSET, PLAN_EX_SUPERSET_WITH,
    BODY_WEIGHT, BODY_ARM, BODY_CHEST, BODY_WAIST,
    POST_PHOTO, POST_CAPTION,
    GYM_LOG_WEIGHT_REPS, POST_COMMENT_TEXT
) = range(22)

# ----------------------------------------------------
# ۳. کیبوردهای اصلی
# ----------------------------------------------------
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🏋️‍♂️ شروع تمرین امروز"), KeyboardButton("🌐 شبکه اجتماعی ورزشکاران")],
        [KeyboardButton("📝 ثبت/بازنویسی برنامه"), KeyboardButton("📋 مشاهده برنامه من")],
        [KeyboardButton("👤 پروفایل من"), KeyboardButton("📊 ثبت سایز و وزن جدید")],
        [KeyboardButton("🏆 جدول رده‌بندی")]
    ],
    resize_keyboard=True
)

CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("❌ انصراف / بازگشت به منوی اصلی")]],
    resize_keyboard=True
)

BACK_OR_CANCEL_KEYBOARD = ReplyKeyboardMarkup(
    [[KeyboardButton("🔙 مرحله قبلی"), KeyboardButton("❌ انصراف")]],
    resize_keyboard=True
)

# ----------------------------------------------------
# ۴. آنبوردینگ و ثبت‌نام اولیه
# ----------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        res = supabase.table("users").select("*").eq("user_id", user.id).execute()
        if not res.data or not res.data[0].get("onboarding_completed"):
            supabase.table("users").upsert({
                "user_id": user.id,
                "full_name": user.full_name or user.first_name,
                "username": user.username or ""
            }).execute()
            await update.message.reply_text(
                f"سلام **{user.first_name}** عزیز! به **آکادمی ورزشی هوشمند** خوش آمدی. 🔥\n\n"
                "جهت تنظیم پروفایل و محاسبه دقیق مشخصات، لطفاً به سوالات زیر پاسخ بده.\n"
                "📌 **سوال ۱ از ۷:** چند سالت است؟ (مثال: `25`)",
                parse_mode="Markdown",
                reply_markup=CANCEL_KEYBOARD
            )
            return OB_AGE
        else:
            await update.message.reply_text(
                f"خوش برگشتی قهرمان! 💪\nاز منوی زیر بخش مورد نظرت رو انتخاب کن:",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("❌ خطا در اتصال به پایگاه داده. لطفاً دوباره تلاش کنید.")
        return ConversationHandler.END

async def ob_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    try:
        context.user_data["age"] = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً سن را فقط به صورت عدد وارد کن (مثلاً: 25):", reply_markup=CANCEL_KEYBOARD)
        return OB_AGE
    await update.message.reply_text("📏 **سوال ۲ از ۷:** قدت چند سانتی‌متر است؟ (مثال: `180`)", parse_mode="Markdown", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return OB_HEIGHT

async def ob_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("📌 **سوال ۱ از ۷:** چند سالت است؟", reply_markup=CANCEL_KEYBOARD)
        return OB_AGE
    try:
        context.user_data["height"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً قد را به عدد وارد کن (مثلاً: 180):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_HEIGHT
    await update.message.reply_text("⚖️ **سوال ۳ از ۷:** وزنت چند کیلوگرم است؟ (مثال: `78.5`)", parse_mode="Markdown", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return OB_WEIGHT

async def ob_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("📏 **سوال ۲ از ۷:** قدت چند سانتی‌متر است؟", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_HEIGHT
    try:
        context.user_data["weight"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ لطفاً وزن را به عدد وارد کن:", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_WEIGHT
    await update.message.reply_text("💪 **سوال ۴ از ۷:** دور بازو (سانتی‌متر) - اگر نمی‌دانی عدد `0` بفرست:", parse_mode="Markdown", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return OB_ARM

async def ob_arm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("⚖️ **سوال ۳ از ۷:** وزنت چند کیلوگرم است؟", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_WEIGHT
    try:
        context.user_data["arm"] = float(update.message.text.strip())
    except ValueError:
        context.user_data["arm"] = 0.0
    await update.message.reply_text("🩺 **سوال ۵ از ۷:** دور سینه (سانتی‌متر) - یا عدد `0`:", parse_mode="Markdown", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return OB_CHEST

async def ob_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("💪 **سوال ۴ از ۷:** دور بازو (سانتی‌متر):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_ARM
    try:
        context.user_data["chest"] = float(update.message.text.strip())
    except ValueError:
        context.user_data["chest"] = 0.0
    await update.message.reply_text("📐 **سوال ۶ از ۷:** دور کمر (سانتی‌متر) - یا عدد `0`:", parse_mode="Markdown", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return OB_WAIST

async def ob_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("🩺 **سوال ۵ از ۷:** دور سینه (سانتی‌متر):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_CHEST
    try:
        context.user_data["waist"] = float(update.message.text.strip())
    except ValueError:
        context.user_data["waist"] = 0.0
    kb = ReplyKeyboardMarkup([["عضله‌سازی 🏋️‍♂️", "کاهش وزن 🏃‍♂️"], ["آمادگی جسمانی ⚡"], ["🔙 مرحله قبلی", "❌ انصراف"]], resize_keyboard=True)
    await update.message.reply_text("🎯 **سوال ۷ از ۷:** هدف اصلی ورزشی‌ات چیست؟", parse_mode="Markdown", reply_markup=kb)
    return OB_GOAL

async def ob_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("📐 **سوال ۶ از ۷:** دور کمر (سانتی‌متر):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return OB_WAIST
    goal = update.message.text
    user_id = update.effective_user.id
    try:
        supabase.table("users").update({
            "age": context.user_data.get("age"),
            "height": context.user_data.get("height"),
            "weight": context.user_data.get("weight"),
            "arm_size": context.user_data.get("arm"),
            "chest_size": context.user_data.get("chest"),
            "waist_size": context.user_data.get("waist"),
            "target_goal": goal,
            "onboarding_completed": True,
            "last_body_check": str(datetime.date.today())
        }).eq("user_id", user_id).execute()

        supabase.table("body_metrics_history").insert({
            "user_id": user_id,
            "weight": context.user_data.get("weight"),
            "arm_size": context.user_data.get("arm"),
            "chest_size": context.user_data.get("chest"),
            "waist_size": context.user_data.get("waist")
        }).execute()
    except Exception as e:
        logger.error(f"Error saving onboarding data: {e}")

    await update.message.reply_text("🎉 **پروفایل ورزشی‌ات با موفقیت تکمیل شد!**\nاکنون می‌توانی برنامه ورزشی خودت رو ثبت کنی.", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# ----------------------------------------------------
# ۵. ثبت برنامه تمرینی
# ----------------------------------------------------
async def start_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🗓 چند روز در هفته برنامه تمرینی داری؟ (عددی بین ۱ تا ۷ وارد کن):", reply_markup=CANCEL_KEYBOARD)
    return PLAN_DAYS_COUNT

async def plan_days_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 7):
        await update.message.reply_text("⚠️ لطفاً یک عدد معتبر بین ۱ تا ۷ وارد کن.", reply_markup=CANCEL_KEYBOARD)
        return PLAN_DAYS_COUNT
    
    context.user_data["total_days"] = int(text)
    context.user_data["current_day_idx"] = 1

    user_id = update.effective_user.id
    try:
        supabase.table("workout_plans").delete().eq("user_id", user_id).execute()
    except Exception as e:
        logger.error(f"Error deleting old plans: {e}")

    await update.message.reply_text("📌 **عنوان روز ۱:** نام برنامه روز اول چیست؟\n(مثال: `روز اول - سینه و جلو بازو`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
    return PLAN_DAY_NAME

async def plan_day_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["❌ انصراف", "❌ انصراف / بازگشت به منوی اصلی"]: return await cancel(update, context)
    day_name = update.message.text.strip()
    user_id = update.effective_user.id
    current_day_num = context.user_data["current_day_idx"]
    
    try:
        res = supabase.table("workout_plans").insert({
            "user_id": user_id,
            "day_number": current_day_num,
            "day_name": day_name
        }).execute()
        context.user_data["current_plan_id"] = res.data[0]["id"]
    except Exception as e:
        logger.error(f"Error inserting plan day: {e}")

    await update.message.reply_text(f"🔢 روز **'{day_name}'** چند حرکت تمرینی دارد؟ (مثلاً: `5`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
    return PLAN_EX_COUNT

async def plan_ex_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["❌ انصراف", "❌ انصراف / بازگشت به منوی اصلی"]: return await cancel(update, context)
    cnt = update.message.text.strip()
    if not cnt.isdigit():
        await update.message.reply_text("⚠️ لطفاً عدد وارد کنید.", reply_markup=CANCEL_KEYBOARD)
        return PLAN_EX_COUNT
    
    context.user_data["total_ex"] = int(cnt)
    context.user_data["current_ex_idx"] = 1

    await update.message.reply_text(f"🏋️‍♂️ **حرکت ۱ از {cnt}:** نام حرکت چیست؟\n(مثال: `پرس سینه دمبل`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
    return PLAN_EX_NAME

async def plan_ex_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["❌ انصراف", "❌ انصراف / بازگشت به منوی اصلی"]: return await cancel(update, context)
    context.user_data["temp_ex_name"] = update.message.text.strip()
    await update.message.reply_text("🔄 تعداد ست و تکرار را بفرست:\n(مثال: `4 ست 12 تایی`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
    return PLAN_EX_SETS_REPS

async def plan_ex_sets_reps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["❌ انصراف", "❌ انصراف / بازگشت به منوی اصلی"]: return await cancel(update, context)
    context.user_data["temp_ex_reps"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["بله 🔗", "خیر ❌"], ["❌ انصراف"]], resize_keyboard=True)
    await update.message.reply_text("🔗 آیا این حرکت به صورت سوپرست انجام می‌شود؟", reply_markup=kb)
    return PLAN_EX_SUPERSET

async def plan_ex_superset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "❌ انصراف": return await cancel(update, context)
    if "بله" in text:
        context.user_data["temp_is_super"] = True
        await update.message.reply_text("با چه حرکتی سوپرست است؟ (نام حرکت دوم را وارد کن):", reply_markup=CANCEL_KEYBOARD)
        return PLAN_EX_SUPERSET_WITH
    else:
        context.user_data["temp_is_super"] = False
        context.user_data["temp_super_with"] = ""
        return await save_exercise_and_next(update, context)

async def plan_ex_superset_with(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text in ["❌ انصراف", "❌ انصراف / بازگشت به منوی اصلی"]: return await cancel(update, context)
    context.user_data["temp_super_with"] = update.message.text.strip()
    return await save_exercise_and_next(update, context)

async def save_exercise_and_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data.get("current_plan_id")
    try:
        supabase.table("plan_exercises").insert({
            "plan_id": plan_id,
            "exercise_name": context.user_data["temp_ex_name"],
            "sets": 4,
            "reps": context.user_data["temp_ex_reps"],
            "is_superset": context.user_data["temp_is_super"],
            "superset_with": context.user_data.get("temp_super_with", "")
        }).execute()
    except Exception as e:
        logger.error(f"Error saving exercise: {e}")

    curr_ex = context.user_data["current_ex_idx"]
    tot_ex = context.user_data["total_ex"]

    if curr_ex < tot_ex:
        context.user_data["current_ex_idx"] += 1
        await update.message.reply_text(f"✅ ثبت شد.\n\n🏋️‍♂️ **حرکت {curr_ex + 1} از {tot_ex}:** نام حرکت چیست؟", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
        return PLAN_EX_NAME
    else:
        curr_day = context.user_data["current_day_idx"]
        tot_days = context.user_data["total_days"]
        if curr_day < tot_days:
            context.user_data["current_day_idx"] += 1
            await update.message.reply_text(f"✅ تمام حرکات این روز ثبت شد!\n\n📌 **عنوان روز {curr_day + 1}:** نام روز بعدی چیست؟", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
            return PLAN_DAY_NAME
        else:
            await update.message.reply_text("🔥 **برنامه تمرینی شما با موفقیت و کامل ذخیره شد!**", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
            return ConversationHandler.END

# ----------------------------------------------------
# ۶. دستیار هوشمند تمرین (Ultimate Gym Mode)
# ----------------------------------------------------
async def start_gym_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        res = supabase.table("workout_plans").select("*").eq("user_id", user_id).order("day_number").execute()
        if not res.data:
            await update.message.reply_text("⚠️ هنوز برنامه‌ای ثبت نکرده‌ای!\nاز دکمه '📝 ثبت/بازنویسی برنامه' استفاده کن.")
            return

        keyboard = []
        for day in res.data:
            keyboard.append([InlineKeyboardButton(f"🏋️‍♂️ {day['day_name']}", callback_data=f"start_day_{day['id']}")])
        
        await update.message.reply_text("🏋️‍♂️ **امروز برنامه کدام روز را می‌خواهی اجرا کنی؟**", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        logger.error(f"Error in gym session: {e}")

async def handle_gym_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_day_"):
        plan_id = int(data.split("_")[2])
        res = supabase.table("plan_exercises").select("*").eq("plan_id", plan_id).execute()
        exercises = res.data

        if not exercises:
            await query.edit_message_text("❌ حرکتی برای این روز یافت نشد.")
            return

        context.user_data["gym_exercises"] = exercises
        context.user_data["gym_current_idx"] = 0
        context.user_data["gym_current_set"] = 1
        await show_current_gym_exercise(query, context)

    elif data == "log_gym_set":
        await query.message.reply_text(
            f"📝 **ثبت ست شماره {context.user_data.get('gym_current_set', 1)}**\n\n"
            "وزنه (کیلوگرم) و تعداد تکرار را بفرست:\n"
            "📌 **فرمت ارسال:** `وزنه تکرار` (مثال: `80 10`)",
            parse_mode="Markdown",
            reply_markup=CANCEL_KEYBOARD
        )
        return GYM_LOG_WEIGHT_REPS

    elif data == "next_gym_ex":
        context.user_data["gym_current_idx"] += 1
        context.user_data["gym_current_set"] = 1
        await show_current_gym_exercise(query, context)

    elif data == "prev_gym_ex":
        if context.user_data.get("gym_current_idx", 0) > 0:
            context.user_data["gym_current_idx"] -= 1
            context.user_data["gym_current_set"] = 1
            await show_current_gym_exercise(query, context)
        else:
            await query.answer("شما در حرکت اول هستید!", show_alert=True)

    elif data == "cancel_gym_session":
        context.user_data.pop("gym_exercises", None)
        await query.edit_message_text("🔴 تمرین لغو شد. خسته نباشی!", reply_markup=None)
        await context.bot.send_message(chat_id=query.message.chat_id, text="منوی اصلی:", reply_markup=MAIN_KEYBOARD)

    elif data.startswith("timer_"):
        seconds = int(data.split("_")[1])
        await query.answer(f"⏱️ تایمر {seconds} ثانیه‌ای فعال شد!")
        asyncio.create_task(start_rest_timer_live(query, context, seconds))

async def receive_gym_set_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    text = update.message.text.strip().split()
    if len(text) < 2:
        await update.message.reply_text("⚠️ فرمت نادرست است! دو عدد با فاصله بفرست (مثال: `80 10`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
        return GYM_LOG_WEIGHT_REPS
    
    try:
        weight = float(text[0])
        reps = int(text[1])
    except ValueError:
        await update.message.reply_text("⚠️ اعداد معتبر وارد کنید (مثال: `80 10`)", parse_mode="Markdown", reply_markup=CANCEL_KEYBOARD)
        return GYM_LOG_WEIGHT_REPS

    user_id = update.effective_user.id
    idx = context.user_data.get("gym_current_idx", 0)
    exercises = context.user_data.get("gym_exercises", [])
    current_set = context.user_data.get("gym_current_set", 1)

    if idx < len(exercises):
        ex_name = exercises[idx]["exercise_name"]
        try:
            supabase.table("workout_logs").insert({
                "user_id": user_id,
                "exercise_name": ex_name,
                "set_number": current_set,
                "weight_kg": weight,
                "reps": reps
            }).execute()
        except Exception as e:
            logger.error(f"Error logging workout set: {e}")

        context.user_data["gym_current_set"] = current_set + 1
        await update.message.reply_text(f"✅ **ست {current_set} ثبت شد:** {weight}kg × {reps} تکرار", parse_mode="Markdown")
        
        chat_id = update.effective_chat.id
        msg = await context.bot.send_message(chat_id=chat_id, text="🔄 در حال به‌روزرسانی...")
        
        class DummyQuery:
            def __init__(self, message, user):
                self.message = message
                self.from_user = user
            async def edit_message_text(self, text, parse_mode=None, reply_markup=None):
                await self.message.edit_text(text, parse_mode=parse_mode, reply_markup=reply_markup)

        dummy_q = DummyQuery(msg, update.effective_user)
        await show_current_gym_exercise(dummy_q, context)

    return ConversationHandler.END

# بهینه‌سازی تایمر استراحت (تایمر زنده روی همان پیام)
async def start_rest_timer_live(query, context, seconds):
    chat_id = query.message.chat_id
    msg = await context.bot.send_message(chat_id=chat_id, text=f"⏱️ **زمان استراحت:** {seconds} ثانیه", parse_mode="Markdown")
    
    step = 5 if seconds <= 60 else 10
    remaining = seconds
    while remaining > 0:
        await asyncio.sleep(step)
        remaining -= step
        if remaining > 0:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id, 
                    message_id=msg.message_id, 
                    text=f"⏱️ **زمان استراحت باقی‌مانده:** {remaining} ثانیه", 
                    parse_mode="Markdown"
                )
            except Exception:
                pass
    
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, 
            message_id=msg.message_id, 
            text="🔔 **وقت استراحت تمام شد! ست بعدی را با قدرت بزن! 💪**", 
            parse_mode="Markdown"
        )
    except Exception:
        pass

async def show_current_gym_exercise(query, context):
    idx = context.user_data.get("gym_current_idx", 0)
    exercises = context.user_data.get("gym_exercises", [])
    current_set = context.user_data.get("gym_current_set", 1)
    user_id = query.from_user.id
    
    if idx >= len(exercises):
        today = str(datetime.date.today())
        try:
            res = supabase.table("users").select("points").eq("user_id", user_id).execute()
            pts = res.data[0].get("points") or 0 if res.data else 0
            new_pts = pts + 15

            supabase.table("users").update({"last_workout_date": today, "points": new_pts}).eq("user_id", user_id).execute()

            await query.edit_message_text(f"🥇 **خسته نباشی قهرمان! تمرین امروز با موفقیت پایان یافت.**\n\n➕ **۱۵ امتیاز جدید گرفتی!**\n💎 مجموع امتیازات شما: **{new_pts}**", parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error completing gym session: {e}")
        return

    ex = exercises[idx]
    
    last_log_txt = "هنوز رکوردی ثبت نشده"
    try:
        last_log = supabase.table("workout_logs").select("*").eq("user_id", user_id).eq("exercise_name", ex['exercise_name']).order("created_at", desc=True).limit(1).execute().data
        if last_log:
            last_log_txt = f"`{last_log[0]['weight_kg']}kg` × `{last_log[0]['reps']}` تکرار"
    except Exception as e:
        logger.error(f"Error fetching last log: {e}")

    txt = f"🏋️‍♂️ **حرکت {idx + 1} از {len(exercises)}**\n"
    txt += "═══════════════════\n"
    txt += f"📌 **حرکت:** {ex['exercise_name']}\n"
    txt += f"🔢 **برنامه:** {ex['reps']}\n"
    txt += f"📍 **ست فعلی:** ست شماره {current_set}\n"
    txt += f"📊 **آخرین رکورد:** {last_log_txt}\n"
    
    if ex.get("is_superset"):
        txt += f"🔗 **سوپرست با:** {ex.get('superset_with')}\n"

    txt += "\n⏱️ **انتخاب زمان استراحت بین ست‌ها:**"

    nav_btns = []
    if idx > 0:
        nav_btns.append(InlineKeyboardButton("⬅️ حرکت قبلی", callback_data="prev_gym_ex"))
    nav_btns.append(InlineKeyboardButton("انجام شد (بعدی ➔)", callback_data="next_gym_ex"))

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏱️ ۶۰ ثانیه", callback_data="timer_60"),
            InlineKeyboardButton("⏱️ ۹۰ ثانیه", callback_data="timer_90"),
            InlineKeyboardButton("⏱️ ۱۲۰ ثانیه", callback_data="timer_120")
        ],
        [InlineKeyboardButton("✍️ ثبت وزنه و تکرار این ست", callback_data="log_gym_set")],
        nav_btns,
        [InlineKeyboardButton("🔴 انصراف و لغو تمرین", callback_data="cancel_gym_session")]
    ])
    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

# ----------------------------------------------------
# ۷. شبکه اجتماعی (Social Feed & Comments)
# ----------------------------------------------------
async def social_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📸 ارسال پست جدید", callback_data="social_create_post")],
        [InlineKeyboardButton("🔥 مشاهده آخرین پست‌ها (Feed)", callback_data="social_feed_0")],
        [InlineKeyboardButton("❌ بازگشت به منوی اصلی", callback_data="social_close_menu")]
    ]
    await update.message.reply_text(
        "🌐 **شبکه اجتماعی اختصاصی ورزشکاران**\n\n"
        "در این بخش می‌توانی تصاویر تمریناتت رو به اشتراک بگذاری، پست بقیه رو لایک کنی و کامنت بگذاری!",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_social_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "social_close_menu":
        await query.message.delete()
        await context.bot.send_message(chat_id=query.message.chat_id, text="بازگشت به منوی اصلی:", reply_markup=MAIN_KEYBOARD)
    elif data.startswith("social_feed_"):
        page = int(data.split("_")[2])
        await show_feed_post(update, context, page)

async def show_feed_post(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    query = update.callback_query
    try:
        posts = supabase.table("posts").select("*, users(full_name, role)").order("created_at", desc=True).limit(10).execute().data
        if not posts:
            msg = "📷 هنوز پستی ثبت نشده است. اولین نفر باشید!"
            if query: await query.edit_message_text(msg)
            else: await update.message.reply_text(msg)
            return

        if page >= len(posts): page = 0
        if page < 0: page = len(posts) - 1

        post = posts[page]
        user_info = post.get("users", {}) or {}
        author_name = user_info.get("full_name", "ورزشکار")
        
        user_id = update.effective_user.id
        liked_res = supabase.table("likes").select("*").eq("post_id", post["post_id"]).eq("user_id", user_id).execute().data
        like_icon = "❤️" if len(liked_res) > 0 else "🤍"

        comments_res = supabase.table("comments").select("*, users(full_name)").eq("post_id", post["post_id"]).order("created_at", desc=False).execute().data
        comments_txt = "\n💬 **نظرات:**\n"
        if comments_res:
            for c in comments_res[-3:]:
                c_name = (c.get("users") or {}).get("full_name", "کاربر")
                comments_txt += f"▫️ **{c_name}:** {c['text']}\n"
        else:
            comments_txt += "هنوز نظری ثبت نشده است.\n"

        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("قبلی ⬅️", callback_data=f"social_feed_{page-1}"))
        if page < len(posts) - 1:
            nav_buttons.append(InlineKeyboardButton("➡️ بعدی", callback_data=f"social_feed_{page+1}"))

        keyboard = [
            [
                InlineKeyboardButton(f"{like_icon} {post['likes_count']}", callback_data=f"like_{post['post_id']}_{page}"),
                InlineKeyboardButton("💬 ثبت نظر", callback_data=f"comment_{post['post_id']}_{page}")
            ],
            nav_buttons,
            [InlineKeyboardButton("📸 ارسال پست جدید", callback_data="social_create_post")],
            [InlineKeyboardButton("❌ بازگشت به منوی اصلی", callback_data="social_close_menu")]
        ]

        caption_text = f"👤 **{author_name}**\n💬 {post.get('caption', '')}\n\n❤️ لایک‌ها: {post['likes_count']}{comments_txt}"
        chat_id = update.effective_chat.id

        if post.get("photo_file_id"):
            await context.bot.send_photo(chat_id=chat_id, photo=post["photo_file_id"], caption=caption_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await context.bot.send_message(chat_id=chat_id, text=caption_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        logger.error(f"Error in show_feed_post: {e}")

async def handle_like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data.split("_")
    post_id = int(data[1])
    page = int(data[2])
    user_id = query.from_user.id

    try:
        liked = supabase.table("likes").select("*").eq("post_id", post_id).eq("user_id", user_id).execute().data
        post = supabase.table("posts").select("likes_count").eq("post_id", post_id).execute().data[0]
        current_likes = post["likes_count"]

        if liked:
            supabase.table("likes").delete().eq("post_id", post_id).eq("user_id", user_id).execute()
            supabase.table("posts").update({"likes_count": max(0, current_likes - 1)}).eq("post_id", post_id).execute()
            await query.answer("لایک برداشت شد.")
        else:
            supabase.table("likes").insert({"post_id": post_id, "user_id": user_id}).execute()
            supabase.table("posts").update({"likes_count": current_likes + 1}).eq("post_id", post_id).execute()
            await query.answer("پست لایک شد! ❤️")

        await show_feed_post(update, context, page)
    except Exception as e:
        logger.error(f"Error in handle_like: {e}")

async def start_add_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split("_")
    context.user_data["comment_post_id"] = int(data[1])
    context.user_data["comment_post_page"] = int(data[2])

    await query.message.reply_text("✍️ نظر خود را بفرستید:", reply_markup=CANCEL_KEYBOARD)
    return POST_COMMENT_TEXT

async def receive_comment_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    comment_text = update.message.text.strip()
    post_id = context.user_data.get("comment_post_id")
    page = context.user_data.get("comment_post_page", 0)
    user_id = update.effective_user.id

    try:
        supabase.table("comments").insert({
            "post_id": post_id,
            "user_id": user_id,
            "text": comment_text
        }).execute()
        await update.message.reply_text("💬 نظر شما با موفقیت ثبت شد!", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.error(f"Error saving comment: {e}")

    class DummyQuery:
        def __init__(self, msg, user):
            self.message = msg
            self.from_user = user
        async def answer(self, text=""): pass
        async def edit_message_text(self, text, parse_mode=None, reply_markup=None): pass

    dummy = DummyQuery(update.message, update.effective_user)
    await show_feed_post(dummy, context, page)
    return ConversationHandler.END

async def start_create_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.reply_text("📷 لطفاً تصویر تمرین یا انگیزشیت رو ارسال کن:", reply_markup=CANCEL_KEYBOARD)
    return POST_PHOTO

async def receive_post_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    if not update.message.photo:
        await update.message.reply_text("⚠️ لطفاً یک تصویر ارسال کنید:", reply_markup=CANCEL_KEYBOARD)
        return POST_PHOTO
        
    photo_file = update.message.photo[-1].file_id
    context.user_data['post_photo'] = photo_file
    await update.message.reply_text("✍️ متن یا کپشن دلخواهت رو وارد کن:", reply_markup=CANCEL_KEYBOARD)
    return POST_CAPTION

async def receive_post_caption(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    caption = update.message.text
    photo_id = context.user_data.get('post_photo')
    user_id = update.effective_user.id

    try:
        supabase.table("posts").insert({
            "user_id": user_id,
            "caption": caption,
            "photo_file_id": photo_id
        }).execute()
        await update.message.reply_text("🎉 **پست شما با موفقیت منتشر شد!**", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.error(f"Error saving post: {e}")

    return ConversationHandler.END

# ----------------------------------------------------
# ۸. پروفایل و جدول برترین‌ها
# ----------------------------------------------------
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if not res.data:
            await update.message.reply_text("⚠️ پروفایلی یافت نشد.")
            return
        
        u = res.data[0]
        
        h_m = (u.get('height') or 0) / 100.0
        w = u.get('weight') or 0
        bmi_txt = "-"
        if h_m > 0 and w > 0:
            bmi = round(w / (h_m ** 2), 1)
            if bmi < 18.5: status = "کمبود وزن 🦴"
            elif 18.5 <= bmi < 25: status = "نرمال و ایده‌آل 🏋️‍♂️"
            elif 25 <= bmi < 30: status = "اضافه وزن 🏃‍♂️"
            else: status = "چاقی ⚠️"
            bmi_txt = f"`{bmi}` ({status})"

        txt = f"👤 **پروفایل ورزشی {u['full_name']}**\n"
        txt += "═══════════════════\n"
        txt += f"📏 **قد:** {u.get('height', '-')} cm\n"
        txt += f"⚖️ **وزن:** {u.get('weight', '-')} kg\n"
        txt += f"📊 **شاخص BMI:** {bmi_txt}\n"
        txt += f"💪 **دور بازو:** {u.get('arm_size', '-')} cm\n"
        txt += f"🩺 **دور سینه:** {u.get('chest_size', '-')} cm\n"
        txt += f"📐 **دور کمر:** {u.get('waist_size', '-')} cm\n"
        txt += f"🎯 **هدف:** {u.get('target_goal', '-')}\n"
        txt += f"💎 **امتیاز کل:** `{u.get('points', 0)}` امتیاز"

        history = supabase.table("body_metrics_history").select("*").eq("user_id", user_id).order("recorded_at", desc=False).limit(5).execute().data
        if history and len(history) > 1:
            txt += "\n\n📈 **روند سابقه تغییرات وزن:**\n"
            for h in history:
                rec_date = h.get('recorded_at', '')[:10]
                txt += f"▫️ `{rec_date}`: **{h.get('weight')} kg**\n"

        await update.message.reply_text(txt, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error show profile: {e}")

async def show_my_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    try:
        plans = supabase.table("workout_plans").select("*").eq("user_id", user_id).order("day_number").execute()
        if not plans.data:
            await update.message.reply_text("⚠️ هنوز برنامه‌ای ثبت نکرده‌ای!")
            return

        msg = "📋 **برنامه تمرینی اختصاصی شما:**\n\n"
        for p in plans.data:
            msg += f"🗓 **{p['day_name']}**\n"
            exs = supabase.table("plan_exercises").select("*").eq("plan_id", p['id']).execute()
            for idx, e in enumerate(exs.data, 1):
                msg += f"  {idx}. **{e['exercise_name']}** — `{e['reps']}`"
                if e.get("is_superset"):
                    msg += f" (🔗 سوپرست با {e.get('superset_with')})"
                msg += "\n"
            msg += "\n"

        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error show plan: {e}")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        res = supabase.table("users").select("full_name, points").order("points", desc=True).limit(10).execute()
        msg = "🏆 **جدول برترین‌های باشگاه:**\n\n"
        medals = ["🥇", "🥈", "🥉"]
        for idx, row in enumerate(res.data, 1):
            pts = row.get('points') or 0
            m = medals[idx-1] if idx <= 3 else f"`{idx}.`"
            msg += f"{m} **{row['full_name']}** — `{pts}` امتیاز\n"
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error leaderboard: {e}")

# ----------------------------------------------------
# ۹. به‌روزرسانی پارامترهای بدنی
# ----------------------------------------------------
async def start_body_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚖️ وزن جدیدت (کیلوگرم) را بفرست:", reply_markup=CANCEL_KEYBOARD)
    return BODY_WEIGHT

async def body_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف / بازگشت به منوی اصلی": return await cancel(update, context)
    try:
        context.user_data["bw"] = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ عدد معتبر بفرست:", reply_markup=CANCEL_KEYBOARD)
        return BODY_WEIGHT
    await update.message.reply_text("💪 دور بازوی جدید (cm):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return BODY_ARM

async def body_arm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("⚖️ وزن جدیدت را بفرست:", reply_markup=CANCEL_KEYBOARD)
        return BODY_WEIGHT
    try:
        context.user_data["ba"] = float(update.message.text.strip())
    except ValueError:
        context.user_data["ba"] = 0.0
    await update.message.reply_text("🩺 دور سینه‌ی جدید (cm):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return BODY_CHEST

async def body_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("💪 دور بازوی جدید (cm):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return BODY_ARM
    try:
        context.user_data["bc"] = float(update.message.text.strip())
    except ValueError:
        context.user_data["bc"] = 0.0
    await update.message.reply_text("📐 دور کمر جدید (cm):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
    return BODY_WAIST

async def body_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "❌ انصراف": return await cancel(update, context)
    if update.message.text == "🔙 مرحله قبلی":
        await update.message.reply_text("🩺 دور سینه‌ی جدید (cm):", reply_markup=BACK_OR_CANCEL_KEYBOARD)
        return BODY_CHEST
        
    user_id = update.effective_user.id
    bw = context.user_data.get("bw", 0.0)
    ba = context.user_data.get("ba", 0.0)
    bc = context.user_data.get("bc", 0.0)
    try:
        bw_size = float(update.message.text.strip())
    except ValueError:
        bw_size = 0.0

    try:
        supabase.table("users").update({
            "weight": bw, "arm_size": ba, "chest_size": bc, "waist_size": bw_size,
            "last_body_check": str(datetime.date.today())
        }).eq("user_id", user_id).execute()

        supabase.table("body_metrics_history").insert({
            "user_id": user_id, "weight": bw, "arm_size": ba, "chest_size": bc, "waist_size": bw_size
        }).execute()
    except Exception as e:
        logger.error(f"Error saving body update: {e}")

    await update.message.reply_text("📊 **اندازه‌های جدید با موفقیت به روزرسانی شدند!**", parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ عملیات لغو شد. به منوی اصلی بازگشتید.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# ----------------------------------------------------
# ۱۰. یادآور عدم فعالیت کاربران
# ----------------------------------------------------
async def inactivity_reminder_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        three_days_ago = str(datetime.date.today() - datetime.timedelta(days=3))
        res = supabase.table("users").select("user_id, full_name").lt("last_workout_date", three_days_ago).execute()
        if res.data:
            for u in res.data:
                try:
                    await context.bot.send_message(
                        chat_id=u["user_id"],
                        text=f"سلام {u['full_name']} عزیز! 🏋️‍♂️\n"
                             "۳ روز است که هیچ تمرینی ثبت نکرده‌ای! بی‌خیال اهدافت نشو؛ همین امروز شروع کن 🔥"
                    )
                except Exception as ex:
                    logger.error(f"Could not send reminder to {u['user_id']}: {ex}")
    except Exception as e:
        logger.error(f"Error in inactivity reminder: {e}")

# ----------------------------------------------------
# ۱۱. اجرای برنامه
# ----------------------------------------------------
def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(inactivity_reminder_job, interval=86400, first=10)

    # Conversation Handlers
    onboarding_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            OB_AGE: [MessageHandler(filters.TEXT, ob_age)],
            OB_HEIGHT: [MessageHandler(filters.TEXT, ob_height)],
            OB_WEIGHT: [MessageHandler(filters.TEXT, ob_weight)],
            OB_ARM: [MessageHandler(filters.TEXT, ob_arm)],
            OB_CHEST: [MessageHandler(filters.TEXT, ob_chest)],
            OB_WAIST: [MessageHandler(filters.TEXT, ob_waist)],
            OB_GOAL: [MessageHandler(filters.TEXT, ob_goal)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    plan_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ثبت/بازنویسی برنامه"), start_plan)],
        states={
            PLAN_DAYS_COUNT: [MessageHandler(filters.TEXT, plan_days_count)],
            PLAN_DAY_NAME: [MessageHandler(filters.TEXT, plan_day_name)],
            PLAN_EX_COUNT: [MessageHandler(filters.TEXT, plan_ex_count)],
            PLAN_EX_NAME: [MessageHandler(filters.TEXT, plan_ex_name)],
            PLAN_EX_SETS_REPS: [MessageHandler(filters.TEXT, plan_ex_sets_reps)],
            PLAN_EX_SUPERSET: [MessageHandler(filters.TEXT, plan_ex_superset)],
            PLAN_EX_SUPERSET_WITH: [MessageHandler(filters.TEXT, plan_ex_superset_with)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    body_update_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 ثبت سایز و وزن جدید$"), start_body_update)],
        states={
            BODY_WEIGHT: [MessageHandler(filters.TEXT, body_weight)],
            BODY_ARM: [MessageHandler(filters.TEXT, body_arm)],
            BODY_CHEST: [MessageHandler(filters.TEXT, body_chest)],
            BODY_WAIST: [MessageHandler(filters.TEXT, body_waist)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    gym_log_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_gym_callback, pattern="^log_gym_set$")],
        states={
            GYM_LOG_WEIGHT_REPS: [MessageHandler(filters.TEXT, receive_gym_set_log)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    create_post_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_create_post, pattern="^social_create_post$")],
        states={
            POST_PHOTO: [MessageHandler(filters.PHOTO | filters.TEXT, receive_post_photo)],
            POST_CAPTION: [MessageHandler(filters.TEXT, receive_post_caption)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    add_comment_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_add_comment, pattern="^comment_")],
        states={
            POST_COMMENT_TEXT: [MessageHandler(filters.TEXT, receive_comment_text)],
        },
        fallbacks=[MessageHandler(filters.Regex("^❌ انصراف"), cancel)]
    )

    # ثبت هندلرها
    app.add_handler(onboarding_handler)
    app.add_handler(plan_handler)
    app.add_handler(body_update_handler)
    app.add_handler(gym_log_handler)
    app.add_handler(create_post_handler)
    app.add_handler(add_comment_handler)

    # Callback Query Handlers
    app.add_handler(CallbackQueryHandler(handle_gym_callback, pattern="^(start_day_|next_gym_ex|prev_gym_ex|cancel_gym_session|timer_)"))
    app.add_handler(CallbackQueryHandler(handle_social_callback, pattern="^(social_close_menu|social_feed_)"))
    app.add_handler(CallbackQueryHandler(handle_like, pattern="^like_"))

    # Message Handlers دکمه‌های اصلی
    app.add_handler(MessageHandler(filters.Regex("^🏋️‍♂️ شروع تمرین امروز"), start_gym_session))
    app.add_handler(MessageHandler(filters.Regex("^🌐 شبکه اجتماعی ورزشکاران$"), social_menu))
    app.add_handler(MessageHandler(filters.Regex("^📋 مشاهده برنامه من$"), show_my_plan))
    app.add_handler(MessageHandler(filters.Regex("^👤 پروفایل من$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^🏆 جدول رده‌بندی$"), leaderboard))

    logger.info("Bot is starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
