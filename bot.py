import os
import logging
import datetime
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client, Client

# تنظیم لاگ‌ها جهت عیب‌یابی در Render
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# وب‌سرور برای زنده نگه داشتن Render
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

# اتصال به دیتابیس
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# دستور start/
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    logger.info(f"Command /start received from user: {user.id} - {user.first_name}")
    
    try:
        supabase.table("users").upsert({
            "user_id": user.id,
            "full_name": user.full_name or user.first_name,
            "username": user.username or ""
        }).execute()
    except Exception as e:
        logger.error(f"Error updating user in Supabase: {e}")

    keyboard = [
        [InlineKeyboardButton("🏋️‍♂️ ثبت تمرین امروز", callback_data="log_workout")],
        [InlineKeyboardButton("🏆 جدول رده‌بندی (رنکینگ)", callback_data="leaderboard")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"سلام {user.first_name} عزیز! به بات باشگاه خوش آمدی.\n"
        "امروز تمرین کردی یا میخوای عقب بمونی؟!",
        reply_markup=reply_markup
    )

# دکمه‌ها
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    today = str(datetime.date.today())

    if query.data == "log_workout":
        try:
            res = supabase.table("users").select("last_workout_date, points").eq("user_id", user_id).execute()
            user_data = res.data[0] if res.data else None

            if user_data and user_data.get("last_workout_date") == today:
                await query.edit_message_text("شما امروز قبلاً تمرینت رو ثبت کردی! دمات گرم 🔥")
            else:
                current_points = user_data.get("points") if user_data and user_data.get("points") else 0
                new_points = current_points + 10
                
                supabase.table("users").update({
                    "last_workout_date": today,
                    "points": new_points
                }).eq("user_id", user_id).execute()
                
                supabase.table("workout_logs").insert({"user_id": user_id}).execute()
                await query.edit_message_text(f"ماشالله قهرمان! ۱۰ امتیاز گرفتی. مجموع امتیازات: {new_points} 🪙")
        except Exception as e:
            logger.error(f"Error in log_workout: {e}")
            await query.edit_message_text("خطایی در ثبت تمرین رخ داد.")

    elif query.data == "leaderboard":
        try:
            res = supabase.table("users").select("full_name, points").order("points", desc=True).limit(10).execute()
            text = "🏆 **جدول برترین‌های باشگاه:**\n\n"
            for idx, row in enumerate(res.data, 1):
                pts = row.get('points') or 0
                text += f"{idx}. {row['full_name']} — {pts} امتیاز\n"
            await query.edit_message_text(text, parse_mode="Markdown")
        except Exception as e:
            logger.error(f"Error in leaderboard: {e}")
            await query.edit_message_text("خطایی در دریافت جدول رده‌بندی رخ داد.")

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    logger.info("Bot is starting polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
