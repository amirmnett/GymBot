import os
import logging
import datetime
import threading
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, ConversationHandler, filters
)
from supabase import create_client, Client

# تنظیم لاگ‌ها
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ۱. وب‌سرور Flask
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Gym Bot is running alive!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# ۲. متغیرها و اتصال به دیتابیس
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip()

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# وضعیت‌های ConversationHandler
WAITING_DAYS, WAITING_PLAN, WAITING_WEIGHT = range(3)

# کیبورد اصلی پایین صفحه
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🏋️‍♂️ ثبت تمرین امروز"), KeyboardButton("🏆 جدول رده‌بندی")],
        [KeyboardButton("📝 ثبت/ویرایش برنامه هفتگی"), KeyboardButton("📋 مشاهده برنامه من")],
        [KeyboardButton("⚖️ ثبت وزن جدید")]
    ],
    resize_keyboard=True
)

# دستور start/
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    try:
        supabase.table("users").upsert({
            "user_id": user.id,
            "full_name": user.full_name or user.first_name,
            "username": user.username or ""
        }).execute()
    except Exception as e:
        logger.error(f"Error in start upsert: {e}")

    await update.message.reply_text(
        f"سلام {user.first_name} عزیز! به بات باشگاه خوش آمدی. 🔥\n"
        "از کیبورد زیر برای مدیریت تمریناتت استفاده کن:",
        reply_markup=MAIN_KEYBOARD
    )

# --- فرآیند ثبت برنامه هفتگی ---
async def start_plan_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "چند روز در هفته تمرین می‌کنی؟ (لطفاً یک عدد بین ۱ تا ۷ بفرست):"
    )
    return WAITING_DAYS

async def set_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or not (1 <= int(text) <= 7):
        await update.message.reply_text("لطفاً فقط یک عدد معتبر بین ۱ تا ۷ وارد کن:")
        return WAITING_DAYS

    context.user_data["workout_days"] = int(text)
    await update.message.reply_text(
        f"عالیه! برنامه {text} روز در هفته.\n\n"
        "حالا برنامه تمرینیت رو برام بفرست. (می‌تونی حرکات هر روز رو کامل تایپ کنی یا کپی کنی اینجا):"
    )
    return WAITING_PLAN

async def set_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    plan_text = update.message.text
    user_id = update.effective_user.id
    days = context.user_data.get("workout_days", 3)

    try:
        supabase.table("users").update({
            "workout_days": days,
            "workout_plan": plan_text
        }).eq("user_id", user_id).execute()

        await update.message.reply_text(
            "✅ برنامه‌ت با موفقیت ثبت شد! هر زمان خواستی می‌تونی از منو مشاهدش کنی.",
            reply_markup=MAIN_KEYBOARD
        )
    except Exception as e:
        logger.error(f"Error setting plan: {e}")
        await update.message.reply_text(" خطایی در ثبت برنامه رخ داد دوباره تلاش کن.", reply_markup=MAIN_KEYBOARD)

    return ConversationHandler.END

# --- فرآیند ثبت وزن ---
async def start_weight_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("وزن فعلیت رو به کیلوگرم بفرست (مثلاً: 75.5):")
    return WAITING_WEIGHT

async def set_weight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    user_id = update.effective_user.id
    try:
        weight = float(text)
        supabase.table("users").update({"weight": weight}).eq("user_id", user_id).execute()
        await update.message.reply_text(f"⚖️ وزن {weight} کیلوگرم با موفقیت ثبت شد!", reply_markup=MAIN_KEYBOARD)
    except ValueError:
        await update.message.reply_text("لطفاً وزن رو به صورت عدد معتبر بفرست.")
        return WAITING_WEIGHT
    except Exception as e:
        logger.error(f"Error setting weight: {e}")
        await update.message.reply_text("خطا در ثبت وزن.", reply_markup=MAIN_KEYBOARD)

    return ConversationHandler.END

# لغو عملیات
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.", reply_markup=MAIN_KEYBOARD)
    return ConversationHandler.END

# --- سایر دستورات منوی اصلی ---
async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    today = str(datetime.date.today())

    if text == "🏋️‍♂️ ثبت تمرین امروز":
        try:
            res = supabase.table("users").select("last_workout_date, points").eq("user_id", user_id).execute()
            user_data = res.data[0] if res.data else {}

            if user_data.get("last_workout_date") == today:
                await update.message.reply_text("امروز قبلاً تمرینت رو ثبت کردی قهرمان! 🔥")
            else:
                current_points = user_data.get("points") or 0
                new_points = current_points + 10

                supabase.table("users").update({
                    "last_workout_date": today,
                    "points": new_points
                }).eq("user_id", user_id).execute()

                supabase.table("workout_logs").insert({"user_id": user_id}).execute()
                await update.message.reply_text(f"ماشالله! ۱۰ امتیاز گرفتی. مجموع امتیازات: {new_points} 🪙")
        except Exception as e:
            logger.error(f"Error log workout: {e}")
            await update.message.reply_text("خطایی در ثبت تمرین رخ داد.")

    elif text == "🏆 جدول رده‌بندی":
        try:
            res = supabase.table("users").select("full_name, points").order("points", desc=True).limit(10).execute()
            msg = "🏆 **جدول برترین‌های باشگاه:**\n\n"
            for idx, row in enumerate(res.data, 1):
                pts = row.get('points') or 0
                msg += f"{idx}. {row['full_name']} — {pts} امتیاز\n"
            await update.message.reply_text(msg, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error leaderboard: {e}")
            await update.message.reply_text("خطایی در دریافت رنکینگ رخ داد.")

    elif text == "📋 مشاهده برنامه من":
        try:
            res = supabase.table("users").select("workout_days, workout_plan").eq("user_id", user_id).execute()
            user_data = res.data[0] if res.data else {}
            plan = user_data.get("workout_plan")
            days = user_data.get("workout_days")

            if plan:
                await update.message.reply_text(f"📋 **برنامه تمرینی ({days} روز در هفته):**\n\n{plan}")
            else:
                await update.message.reply_text("شما هنوز برنامه‌ای ثبت نکرده‌اید! از دکمه '📝 ثبت/ویرایش برنامه هفتگی' استفاده کنید.")
        except Exception as e:
            logger.error(f"Error view plan: {e}")
            await update.message.reply_text("خطا در دریافت برنامه.")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()

    # گفتگوی ثبت برنامه
    plan_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📝 ثبت/ویرایش برنامه هفتگی$"), start_plan_setup)],
        states={
            WAITING_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_days)],
            WAITING_PLAN: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_plan)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # گفتگوی ثبت وزن
    weight_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚖️ ثبت وزن جدید$"), start_weight_setup)],
        states={
            WAITING_WEIGHT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_weight)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(plan_handler)
    app.add_handler(weight_handler)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_main_menu))

    logger.info("Bot started successfully...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
