import aiohttp
import asyncio
import urllib.parse
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

# States
START, NUMBER, COUNT = range(3)

# Empty APIs List - Buyer needs to purchase APIs
APIS = [
    # 🛒 APIs not included in this code
    # 📞 Purchase APIs from: @LuffyBots
    # 💬 Contact owner for premium APIs
]

# Keyboard Layouts
main_keyboard = [[KeyboardButton("🔎 Enter Number")]]
count_keyboard = [["5", "10", "20"], ["50", "100", "500"]]

# Inline Keyboard for API Purchase
purchase_keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("🛒 Buy APIs - @LuffyBots", url="https://t.me/LuffyBots")]
])

async def send_request(session, api, phone_number):
    try:
        # Update phone number in payload and headers
        updated_payload = api["payload"].copy()
        updated_headers = api["headers"].copy()
        
        for key in updated_payload:
            if "mobile" in key.lower() or "phone" in key.lower() or "number" in key.lower() or key == "mob":
                updated_payload[key] = phone_number
        
        for key in updated_headers:
            if "mobile" in key.lower() or "phone" in key.lower() or "number" in key.lower():
                updated_headers[key] = phone_number

        if api["method"] == "POST":
            if updated_headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
                payload_str = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in updated_payload.items())
                updated_headers["Content-Length"] = str(len(payload_str.encode('utf-8')))
                response = await session.post(api["endpoint"], data=payload_str, headers=updated_headers, timeout=10, ssl=False)
            else:
                response = await session.post(api["endpoint"], json=updated_payload, headers=updated_headers, timeout=10, ssl=False)
        else:
            return None
        
        return response.status
    except Exception as e:
        return None

async def start_bombing(update: Update, phone_number: str, count: int):
    if not APIS:
        await update.message.reply_text(
            "❌ **APIs NOT INCLUDED!**\n\n"
            "📞 This bot framework is ready but APIs are not included.\n"
            "🛒 You need to purchase working APIs separately.\n\n"
            "💬 **Contact Owner for APIs:** @LuffyBots\n"
            "💰 Premium APIs with high success rate available",
            reply_markup=purchase_keyboard
        )
        await update.message.reply_text(
            "🔙 Returning to main menu...",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
        return
    
    await update.message.reply_text(f"🚀 Starting bombing on {phone_number}...")
    
    successful_requests = 0
    total_messages_sent = 0
    
    for round_num in range(count):
        async with aiohttp.ClientSession() as session:
            tasks = [send_request(session, api, phone_number) for api in APIS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for api_num, result in enumerate(results):
                total_messages_sent += 1
                if result in [200, 201]:
                    successful_requests += 1
                    await update.message.reply_text(f"✅ {total_messages_sent} send OTP - LuffyBots")
                else:
                    await update.message.reply_text(f"❌ {total_messages_sent} failed - LuffyBots")
        
        if round_num < count - 1:
            await asyncio.sleep(0.5)
    
    await update.message.reply_text(
        f"🎉 Bombing completed!\n"
        f"✅ Successful: {successful_requests}\n"
        f"📊 Total messages sent: {total_messages_sent}\n"
        f"🎯 Rounds completed: {count}\n"
        f"🔥 Powered by LuffyBots",
        reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    )

# Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 Welcome To ANISH EXPLOITS Bomber 🔥\n\n"
        "⚠️ **IMPORTANT:** APIs are not included in this code!\n"
        "🛒 You need to purchase working APIs separately.\n\n"
        "📞 **Contact for APIs:** @LuffyBots",
        reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    )
    return NUMBER

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text == "🔎 Enter Number":
        await update.message.reply_text(
            "📞 Send Your 10 Digit Number\n\n"
            "💡 **Note:** After entering number, you'll need to purchase APIs from @LuffyBots to make this bot work."
        )
        return NUMBER
    return NUMBER

async def process_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    number = update.message.text
    if not number.isdigit() or len(number) != 10:
        await update.message.reply_text("❌ Invalid number! Send 10-digit number:")
        return NUMBER
    
    context.user_data['number'] = number
    
    # Show API purchase message before count selection
    await update.message.reply_text(
        "🛒 **API REQUIREMENT**\n\n"
        "❌ This bot cannot work without APIs!\n"
        "📞 You need to purchase working APIs first.\n\n"
        "💬 **Contact for APIs:** @LuffyBots\n"
        "💰 Premium APIs with guaranteed delivery",
        reply_markup=purchase_keyboard
    )
    
    await update.message.reply_text(
        "📊 Select bombing count (You'll need APIs to proceed):",
        reply_markup=ReplyKeyboardMarkup(count_keyboard, resize_keyboard=True)
    )
    return COUNT

async def process_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    count = int(update.message.text)
    number = context.user_data['number']
    
    if not APIS:
        await update.message.reply_text(
            "❌ **APIS NOT CONFIGURED!**\n\n"
            "🚫 This bot framework is ready but cannot function without APIs.\n\n"
            "🛒 **Purchase APIs from:** @LuffyBots\n"
            "📞 Contact for premium OTP bombing APIs\n"
            "💬 Working APIs with high success rate\n\n"
            "⚡ After purchasing, you'll get:\n"
            "✅ 10+ Working APIs\n"
            "✅ Call + SMS Bomber\n"
            "✅ High Success Rate\n"
            "✅ Regular Updates",
            reply_markup=purchase_keyboard
        )
        await update.message.reply_text(
            "🔙 Returning to main menu...",
            reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
        )
        return START
    
    await update.message.reply_text(
        f"💣 Starting bombing on {number}\n"
        f"🎯 Total rounds: {count}",
        reply_markup=ReplyKeyboardMarkup([[]], resize_keyboard=True)
    )
    
    await start_bombing(update, number, count)
    return START

async def purchase_apis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🛒 **API Purchase Information**\n\n"
        "📞 **Contact:** @LuffyBots\n\n"
        "💰 **Pricing:**\n"
        "• Basic Package: ₹XXX\n"
        "• Premium Package: ₹XXX\n"
        "• Enterprise Package: ₹XXX\n\n"
        "⚡ **Features:**\n"
        "✅ 10+ Working APIs\n"
        "✅ Call + SMS Bomber\n"
        "✅ High Success Rate\n"
        "✅ Regular Updates\n"
        "✅ Technical Support"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Operation cancelled!\n\n"
        "🛒 Need APIs? Contact @LuffyBots",
        reply_markup=ReplyKeyboardMarkup(main_keyboard, resize_keyboard=True)
    )
    return START

def main():
    # Bot Token
    TOKEN = "8386048836:AAHwJuBXUudmwYqiybtYFgPJX1YYIA3D0AI"
    
    application = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            START: [
                MessageHandler(filters.Text(["🔎 Enter Number"]), handle_number),
            ],
            NUMBER: [
                MessageHandler(filters.Text(["🔎 Enter Number"]), handle_number),
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_number)
            ],
            COUNT: [
                MessageHandler(filters.Text(["5", "10", "20", "50", "100", "500"]), process_count)
            ]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(purchase_apis, pattern="^purchase$"))
    
    print("🤖 LuffyBots Bot is running...")
    print("🛒 APIs NOT INCLUDED - Contact @LuffyBots for APIs")
    application.run_polling()

if __name__ == "__main__":
    main()
