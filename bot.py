import os
import logging
import datetime
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, CallbackQueryHandler, filters
)
from supabase import create_client, Client

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# وب‌سرور Flask برای Render
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Gym Bot is running alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# خواندن متغیرها
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# حالت‌های ConversationHandler
(
    OB_AGE, OB_HEIGHT, OB_WEIGHT, OB_ARM, OB_CHEST, OB_WAIST, OB_GOAL,
    PLAN_DAYS_COUNT, PLAN_DAY_NAME, PLAN_EX_COUNT, PLAN_EX_NAME, PLAN_EX_SETS_REPS, PLAN_EX_SUPERSET, PLAN_EX_SUPERSET_WITH,
    BODY_WEIGHT, BODY_ARM, BODY_CHEST, BODY_WAIST
) = range(19)

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🏋️‍♂️ شروع تمرین امروز (باشگاه)"), KeyboardButton("🏆 جدول رده‌بندی")],
        [KeyboardButton("📝 ثبت/بازنویسی برنامه تمرینی"), KeyboardButton("📋 مشاهده برنامه من")],
        [KeyboardButton("👤 پروفایل من"), KeyboardButton("📊 ثبت سایز و وزن جدید")]
    ],
    resize_keyboard=True
)

# --- ۱. ثبت‌نام و آنبوردینگ کامل ---
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
                f"سلام {user.first_name} عزیز! به آکادمی ورزشی خوش آمدی. 🔥\n"
                "برای ساخت پروفایل ورزشی، چند سوال کوتاه می‌پرسم.\n\n"
                "۱. چند سالت است؟ (مثلاً: 25)"
            )
            return OB_AGE
        else:
            await update.message.reply_text(
                f"خوش برگشتی {user.first_name} عزیز! 💪\nاز منوی زیر استفاده کن:",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("خطا در اتصال. دوباره امتحان کنید.")
        return ConversationHandler.END

async def ob_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["age"] = int(update.message.text.strip())
    await update.message.reply_text("۲. قدت چند سانتی‌متر است؟ (مثلاً: 180)")
    return OB_HEIGHT

async def ob_height(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["height"] = float(update.message.text.strip())
    await update.message.reply_text("۳. وزنت چند کیلوگرم است؟ (مثلاً: 78.5)")
    return OB_WEIGHT

async def ob_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["weight"] = float(update.message.text.strip())
    await update.message.reply_text("۴. دور بازو (سانتی‌متر) - اگر نمی‌دانی عدد 0 را بفرست:")
    return OB_ARM

async def ob_arm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["arm"] = float(update.message.text.strip())
    await update.message.reply_text("۵. دور سینه (سانتی‌متر) - یا عدد 0:")
    return OB_CHEST

async def ob_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["chest"] = float(update.message.text.strip())
    await update.message.reply_text("۶. دور کمر (سانتی‌متر) - یا عدد 0:")
    return OB_WAIST

async def ob_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waist"] = float(update.message.text.strip())
    kb = ReplyKeyboardMarkup([["عضله‌سازی 🏋️‍♂️", "کاهش وزن 🏃‍♂️"], ["آمادگی جسمانی ⚡"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("۷. هدف اصلی ورزشی‌ات چیست؟", reply_markup=kb)
    return OB_GOAL

async def ob_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    goal = update.message.text
    user_id = update.effective_user.id
    
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

    # ثبت در تاریخچه
    supabase.table("body_metrics_history").insert({
        "user_id": user_id,
        "weight": context.user_data.get("weight"),
        "arm_size": context.user_data.get("arm"),
        "chest_size": context.user_data.get("chest"),
        "waist_size": context.user_data.get("waist")
    }).execute()

    await update.message.reply_text("🎉 پروفایل ورزشی‌ات با موفقیت ساخته شد!", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# --- ۲. ساختار هوشمند و جزئی ثبت برنامه تمرینی ---
async def start_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("چند روز در هفته برنامه تمرینی داری؟ (عدد بین ۱ تا ۷ بفرست):")
    return PLAN_DAYS_COUNT

async def plan_days_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 7):
        await update.message.reply_text("لطفاً یک عدد معتبر بین ۱ تا ۷ وارد کن.")
        return PLAN_DAYS_COUNT
    
    context.user_data["total_days"] = int(text)
    context.user_data["current_day_idx"] = 1
    context.user_data["days_data"] = []

    # پاک کردن برنامه قبلی کاربر
    user_id = update.effective_user.id
    supabase.table("workout_plans").delete().eq("user_id", user_id).execute()

    await update.message.reply_text(f"عالیه! نام روز اول تمرین چیست؟ (مثلاً: روز اول - سینه و جلو بازو):")
    return PLAN_DAY_NAME

async def plan_day_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    day_name = update.message.text.strip()
    
    # ثبت روز جدید در دیتابیس
    user_id = update.effective_user.id
    current_day_num = context.user_data["current_day_idx"]
    
    res = supabase.table("workout_plans").insert({
        "user_id": user_id,
        "day_number": current_day_num,
        "day_name": day_name
    }).execute()
    
    context.user_data["current_plan_id"] = res.data[0]["id"]
    await update.message.reply_text(f"روز '{day_name}' چند حرکت تمرینی دارد؟ (مثلاً: 5)")
    return PLAN_EX_COUNT

async def plan_ex_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cnt = update.message.text.strip()
    if not cnt.isdigit():
        await update.message.reply_text("لطفاً یک عدد بفرست.")
        return PLAN_EX_COUNT
    
    context.user_data["total_ex"] = int(cnt)
    context.user_data["current_ex_idx"] = 1

    await update.message.reply_text(f"حرکت ۱ از {cnt}: نام حرکت چیست؟ (مثلاً: پرس سینه دمبل)")
    return PLAN_EX_NAME

async def plan_ex_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["temp_ex_name"] = update.message.text.strip()
    await update.message.reply_text("تعداد ست و تکرار را بفرست (مثلاً: 4 ست 12 تایی):")
    return PLAN_EX_SETS_REPS

async def plan_ex_sets_reps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["temp_ex_reps"] = update.message.text.strip()
    kb = ReplyKeyboardMarkup([["بله 🔗", "خیر ❌"]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text("آیا این حرکت سوپرست است؟", reply_markup=kb)
    return PLAN_EX_SUPERSET

async def plan_ex_superset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "بله" in text:
        context.user_data["temp_is_super"] = True
        await update.message.reply_text("با چه حرکتی سوپرست است؟ (نام حرکت همراه را بفرست):")
        return PLAN_EX_SUPERSET_WITH
    else:
        context.user_data["temp_is_super"] = False
        context.user_data["temp_super_with"] = ""
        return await save_exercise_and_next(update, context)

async def plan_ex_superset_with(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["temp_super_with"] = update.message.text.strip()
    return await save_exercise_and_next(update, context)

async def save_exercise_and_next(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_id = context.user_data["current_plan_id"]
    
    supabase.table("plan_exercises").insert({
        "plan_id": plan_id,
        "exercise_name": context.user_data["temp_ex_name"],
        "sets": 4, # پیش‌فرض
        "reps": context.user_data["temp_ex_reps"],
        "is_superset": context.user_data["temp_is_super"],
        "superset_with": context.user_data.get("temp_super_with", "")
    }).execute()

    curr_ex = context.user_data["current_ex_idx"]
    tot_ex = context.user_data["total_ex"]

    if curr_ex < tot_ex:
        context.user_data["current_ex_idx"] += 1
        await update.message.reply_text(
            f"✅ ذخیره شد.\n\nحرکت {curr_ex + 1} از {tot_ex}: نام حرکت چیست؟",
            reply_markup=MAIN_KEYBOARD
        )
        return PLAN_EX_NAME
    else:
        curr_day = context.user_data["current_day_idx"]
        tot_days = context.user_data["total_days"]
        if curr_day < tot_days:
            context.user_data["current_day_idx"] += 1
            await update.message.reply_text(
                f"✅ تمام حرکات این روز ثبت شد!\n\nحالا نام روز {curr_day + 1} چیست؟ (مثلاً: روز دوم - پا و سرشانه):",
                reply_markup=MAIN_KEYBOARD
            )
            return PLAN_DAY_NAME
        else:
            await update.message.reply_text(
                "🔥 فوق‌العاده است! تمام روزها و حرکات برنامه‌ات با موفقیت ذخیره شدند.",
                reply_markup=MAIN_KEYBOARD
            )
            return ConversationHandler.END

# --- ۳. مد حالت باشگاه (حرفه ای تیک زدن حرکات) ---
async def start_gym_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    res = supabase.table("workout_plans").select("*").eq("user_id", user_id).order("day_number").execute()
    
    if not res.data:
        await update.message.reply_text("هنوز برنامه‌ای ثبت نکرده‌ای! ابتدا از دکمه '📝 ثبت/بازنویسی برنامه تمرینی' استفاده کن.")
        return

    keyboard = []
    for day in res.data:
        keyboard.append([InlineKeyboardButton(f"🏋️‍♂️ {day['day_name']}", callback_data=f"start_day_{day['id']}")])
    
    await update.message.reply_text("امروز برنامه کدام روز را می‌خواهی اجرا کنی؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_gym_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("start_day_"):
        plan_id = int(data.split("_")[2])
        res = supabase.table("plan_exercises").select("*").eq("plan_id", plan_id).execute()
        exercises = res.data

        if not exercises:
            await query.edit_message_text("حرکتی برای این روز یافت نشد.")
            return

        context.user_data["gym_exercises"] = exercises
        context.user_data["gym_current_idx"] = 0
        await show_current_gym_exercise(query, context)

    elif data == "next_gym_ex":
        context.user_data["gym_current_idx"] += 1
        await show_current_gym_exercise(query, context)

async def show_current_gym_exercise(query, context):
    idx = context.user_data["gym_current_idx"]
    exercises = context.user_data["gym_exercises"]
    
    if idx >= len(exercises):
        # تمرین تمام شد
        user_id = query.from_user.id
        today = str(datetime.date.today())
        
        res = supabase.table("users").select("points").eq("user_id", user_id).execute()
        pts = res.data[0].get("points") or 0 if res.data else 0
        new_pts = pts + 10

        supabase.table("users").update({"last_workout_date": today, "points": new_pts}).eq("user_id", user_id).execute()
        supabase.table("workout_logs").insert({"user_id": user_id}).execute()

        await query.edit_message_text(f"🥇 خسته نباشی قهرمان! تمرین امروز با موفقیت تمام شد.\n\n۱۰ امتیاز جدید گرفتی! مجموع امتیازات: {new_pts} 🪙")
        return

    ex = exercises[idx]
    txt = f"🏋️‍♂️ **حرکت {idx + 1} از {len(exercises)}:**\n\n"
    txt += f"📌 **{ex['exercise_name']}**\n"
    txt += f"🔢 **مقدار:** {ex['reps']}\n"
    
    if ex.get("is_superset"):
        txt += f"🔥 **سوپرست با:** {ex.get('superset_with')}\n"

    kb = InlineKeyboardMarkup([[InlineKeyboardButton("✅ انجام شد (حرکت بعدی ➔)", callback_data="next_gym_ex")]])
    await query.edit_message_text(txt, parse_mode="Markdown", reply_markup=kb)

# --- ۴. پروفایل و مشاهده برنامه ---
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not res.data:
        await update.message.reply_text("پروفایلی یافت نشد.")
        return
    
    u = res.data[0]
    txt = f"👤 **پروفایل ورزشی {u['full_name']}**\n\n"
    txt += f"📏 قد: {u.get('height', '-')} سانتی‌متر\n"
    txt += f"⚖️ وزن: {u.get('weight', '-')} کیلوگرم\n"
    txt += f"💪 دور بازو: {u.get('arm_size', '-')} cm\n"
    txt += f"🩺 دور سینه: {u.get('chest_size', '-')} cm\n"
    txt += f"📐 دور کمر: {u.get('waist_size', '-')} cm\n"
    txt += f"🎯 هدف: {u.get('target_goal', '-')}\n"
    txt += f"🪙 امتیاز کل: {u.get('points', 0)}"

    await update.message.reply_text(txt, parse_mode="Markdown")

async def show_my_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    plans = supabase.table("workout_plans").select("*").eq("user_id", user_id).order("day_number").execute()
    
    if not plans.data:
        await update.message.reply_text("هنوز برنامه‌ای ثبت نکرده‌ای!")
        return

    msg = "📋 **برنامه تمرینی شما:**\n\n"
    for p in plans.data:
        msg += f"🗓 **{p['day_name']}**\n"
        exs = supabase.table("plan_exercises").select("*").eq("plan_id", p['id']).execute()
        for idx, e in enumerate(exs.data, 1):
            msg += f"  {idx}. {e['exercise_name']} — {e['reps']}"
            if e.get("is_superset"):
                msg += f" (🔗 سوپرست با {e.get('superset_with')})"
            msg += "\n"
        msg += "\n"

    await update.message.reply_text(msg, parse_mode="Markdown")

async def leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    res = supabase.table("users").select("full_name, points").order("points", desc=True).limit(10).execute()
    msg = "🏆 **جدول برترین‌های باشگاه:**\n\n"
    for idx, row in enumerate(res.data, 1):
        pts = row.get('points') or 0
        msg += f"{idx}. {row['full_name']} — {pts} امتیاز\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

# --- ۵. ثبت سایز و وزن جدید (اندازه‌گیری دوره‌ای) ---
async def start_body_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("وزن جدیدت (کیلوگرم) را بفرست:")
    return BODY_WEIGHT

async def body_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bw"] = float(update.message.text.strip())
    await update.message.reply_text("دور بازوی جدید (cm):")
    return BODY_ARM

async def body_arm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["ba"] = float(update.message.text.strip())
    await update.message.reply_text("دور سینه‌ی جدید (cm):")
    return BODY_CHEST

async def body_chest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["bc"] = float(update.message.text.strip())
    await update.message.reply_text("دور کمر جدید (cm):")
    return BODY_WAIST

async def body_waist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bw = context.user_data["bw"]
    ba = context.user_data["ba"]
    bc = context.user_data["bc"]
    bw_size = float(update.message.text.strip())

    supabase.table("users").update({
        "weight": bw, "arm_size": ba, "chest_size": bc, "waist_size": bw_size,
        "last_body_check": str(datetime.date.today())
    }).eq("user_id", user_id).execute()

    supabase.table("body_metrics_history").insert({
        "user_id": user_id, "weight": bw, "arm_size": ba, "chest_size": bc, "waist_size": bw_size
    }).execute()

    await update.message.reply_text("📊 اندازه‌های جدید با موفقیت ثبت شدند!", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    # آنبوردینگ
    onboarding_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            OB_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_age)],
            OB_HEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_height)],
            OB_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_weight)],
            OB_ARM: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_arm)],
            OB_CHEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_chest)],
            OB_WAIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_waist)],
            OB_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ob_goal)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # ثبت برنامه تمرینی
    plan_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ثبت/بازنویسی برنامه تمرینی$"), start_plan)],
        states={
            PLAN_DAYS_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_days_count)],
            PLAN_DAY_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_day_name)],
            PLAN_EX_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_ex_count)],
            PLAN_EX_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_ex_name)],
            PLAN_EX_SETS_REPS: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_ex_sets_reps)],
            PLAN_EX_SUPERSET: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_ex_superset)],
            PLAN_EX_SUPERSET_WITH: [MessageHandler(filters.TEXT & ~filters.COMMAND, plan_ex_superset_with)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # به‌روزرسانی پارامترهای بدنی
    body_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📊 ثبت سایز و وزن جدید$"), start_body_update)],
        states={
            BODY_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_weight)],
            BODY_ARM: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_arm)],
            BODY_CHEST: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_chest)],
            BODY_WAIST: [MessageHandler(filters.TEXT & ~filters.COMMAND, body_waist)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(onboarding_handler)
    app.add_handler(plan_handler)
    app.add_handler(body_handler)
    
    app.add_handler(MessageHandler(filters.Regex("^🏋️‍♂️ شروع تمرین امروز \(باشگاه\)$"), start_gym_session))
    app.add_handler(MessageHandler(filters.Regex("^👤 پروفایل من$"), show_profile))
    app.add_handler(MessageHandler(filters.Regex("^📋 مشاهده برنامه من$"), show_my_plan))
    app.add_handler(MessageHandler(filters.Regex("^🏆 جدول رده‌بندی$"), leaderboard))
    
    app.add_handler(CallbackQueryHandler(handle_gym_callback))

    logger.info("Bot starting...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
