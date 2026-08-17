import os
import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from supabase import create_client, Client

# خواندن مقادیر حساس از متغیرهای محیطی Render
BOT_TOKEN = os.environ.get("BOT_TOKEN")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# اتصال به دیتابیس Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# دستور start/
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # ثبت یا آپدیت کاربر در دیتابیس
    supabase.table("users").upsert({
        "user_id": user.id,
        "full_name": user.full_name,
        "username": user.username
    }).execute()
    
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

# مدیریت دکمه‌های شیشه‌ای
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    today = str(datetime.date.today())

    if query.data == "log_workout":
        # بررسی اینکه امروز ثبت کرده یا نه
        res = supabase.table("users").select("last_workout_date, points").eq("user_id", user_id).execute()
        user_data = res.data[0] if res.data else None

        if user_data and user_data.get("last_workout_date") == today:
            await query.edit_message_text("شما امروز قبلاً تمرینت رو ثبت کردی! دمات گرم 🔥")
        else:
            new_points = (user_data.get("points") or 0) + 10 if user_data else 10
            supabase.table("users").update({
                "last_workout_date": today,
                "points": new_points
            }).eq("user_id", user_id).execute()
            
            supabase.table("workout_logs").insert({"user_id": user_id}).execute()
            await query.edit_message_text(f"ماشالله قهرمان! ۱۰ امتیاز گرفتی. مجموع امتیازات: {new_points} 🪙")

    elif query.data == "leaderboard":
        res = supabase.table("users").select("full_name, points").order("points", desc=True).limit(10).execute()
        text = "🏆 **جدول برترین‌های باشگاه:**\n\n"
        for idx, row in enumerate(res.data, 1):
            text += f"{idx}. {row['full_name']} — {row['points']} امتیاز\n"
        await query.edit_message_text(text, parse_mode="Markdown")

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

if __name__ == "__main__":
    main()
