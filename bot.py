#!/usr/bin/env python3
"""
📱 Phone Service Tracker Bot
ဖုန်းပြုပြင်ရေး Job မှတ်တမ်း Telegram Bot
"""

import logging
import sqlite3
import os
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters, ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN   = os.environ.get('BOT_TOKEN', '')
DB_PATH = os.environ.get('DB_PATH', 'service.db')

# ── Conversation States ──
CUST_NAME, CUST_PHONE, DEVICE, ISSUE, PRICE, NOTES_STEP = range(6)
SEARCH_INPUT  = 6
UPDATE_JOB_ID = 7
EDIT_PRICE_ID, EDIT_PRICE_VAL = 8, 9

# ── Status Labels ──
STATUS_LABEL = {
    'pending':       '⏳ Pending',
    'inprogress':    '🔧 In Progress',
    'waiting_parts': '📦 Parts စောင့်ဆဲ',
    'done':          '✅ Done',
    'delivered':     '📤 Delivered',
    'cancelled':     '❌ Cancelled',
}

STATUS_EMOJI = {
    'pending': '⏳', 'inprogress': '🔧',
    'waiting_parts': '📦', 'done': '✅',
    'delivered': '📤', 'cancelled': '❌',
}


# ══════════════════════════════════════════
# DATABASE
# ══════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS jobs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        job_code    TEXT UNIQUE,
        cust_name   TEXT,
        cust_phone  TEXT,
        device      TEXT,
        issue       TEXT,
        price       REAL DEFAULT 0,
        notes       TEXT DEFAULT '',
        status      TEXT DEFAULT 'pending',
        created_at  TEXT,
        updated_at  TEXT,
        chat_id     INTEGER
    )''')
    conn.commit()
    conn.close()

def db():
    return sqlite3.connect(DB_PATH)

def next_code():
    conn = db()
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM jobs')
    n = c.fetchone()[0] + 1
    conn.close()
    return f'SVC-{n:04d}'

def fmt_dt(s):
    try:
        return datetime.fromisoformat(s).strftime('%d/%m %H:%M')
    except:
        return s or '—'

def fmt_money(n):
    try:
        return f'{float(n):,.0f} ကျပ်'
    except:
        return '—'


# ══════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════

def job_card(j, compact=False):
    """Format a job row as a readable message."""
    _, code, name, phone, device, issue, price, notes, status, created, updated, _ = j
    stat = STATUS_LABEL.get(status, status)

    if compact:
        return (
            f"{STATUS_EMOJI.get(status,'•')} *{code}*  {name}  {device}\n"
            f"   📞{phone}  💰{fmt_money(price)}  {fmt_dt(created)}"
        )

    return (
        f"🔖 *{code}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👤 {name}\n"
        f"📞 {phone}\n"
        f"📱 {device}\n"
        f"🔧 {issue}\n"
        f"💰 {fmt_money(price)}\n"
        f"📝 {notes or '—'}\n"
        f"📊 {stat}\n"
        f"📅 {fmt_dt(created)}  🔄 {fmt_dt(updated)}"
    )

def status_keyboard(code, current):
    """Build inline keyboard based on current status."""
    rows = []
    if current == 'pending':
        rows.append([InlineKeyboardButton("🔧 Start Repair",   callback_data=f"ss:{code}:inprogress")])
        rows.append([InlineKeyboardButton("📦 Wait for Parts", callback_data=f"ss:{code}:waiting_parts")])
    if current == 'inprogress':
        rows.append([InlineKeyboardButton("📦 Wait for Parts", callback_data=f"ss:{code}:waiting_parts")])
        rows.append([InlineKeyboardButton("✅ Mark Done",       callback_data=f"ss:{code}:done")])
    if current == 'waiting_parts':
        rows.append([InlineKeyboardButton("🔧 Resume Repair",  callback_data=f"ss:{code}:inprogress")])
        rows.append([InlineKeyboardButton("✅ Mark Done",       callback_data=f"ss:{code}:done")])
    if current == 'done':
        rows.append([InlineKeyboardButton("📤 Mark Delivered", callback_data=f"ss:{code}:delivered")])
    if current not in ('cancelled', 'delivered'):
        rows.append([InlineKeyboardButton("❌ Cancel Job",     callback_data=f"ss:{code}:cancelled")])
    rows.append([InlineKeyboardButton("🔍 View Full",          callback_data=f"view:{code}")])
    return InlineKeyboardMarkup(rows) if rows else None

def get_jobs(statuses, chat_id, limit=30):
    conn = db()
    c = conn.cursor()
    ph = ','.join('?' * len(statuses))
    c.execute(
        f'SELECT * FROM jobs WHERE status IN ({ph}) AND chat_id=? ORDER BY created_at DESC LIMIT ?',
        (*statuses, chat_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows


# ══════════════════════════════════════════
# /start  /help
# ══════════════════════════════════════════

HELP_TEXT = (
    "🛠 *Phone Service Tracker*\n"
    "━━━━━━━━━━━━━━━━━━━━\n\n"
    "📌 *Job Management*\n"
    "➕ /newjob — Job အသစ်ထည့်\n"
    "✏️ /update — Status ပြောင်း\n"
    "💰 /editprice — ငွေကြေး ပြင်\n"
    "❌ /cancel\\_job `SVC-0001` — ပယ်ဖျက်\n\n"
    "📋 *Job Lists*\n"
    "📋 /jobs — Active Jobs အားလုံး\n"
    "⏳ /pending — Pending\n"
    "🔧 /inprogress — လုပ်ဆောင်ဆဲ\n"
    "📦 /waiting — Parts စောင့်ဆဲ\n"
    "✅ /done — ပြီးဆုံးသော\n"
    "📤 /delivered — Delivered\n\n"
    "🔍 *Search & Reports*\n"
    "🔍 /search — Customer ရှာ\n"
    "📊 /summary — ဒီနေ့ Summary\n"
    "📈 /monthly — လပတ်စာရင်း\n"
)

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


# ══════════════════════════════════════════
# NEW JOB CONVERSATION
# ══════════════════════════════════════════

async def newjob(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "➕ *Job အသစ်ထည့်မည်*\n━━━━━━━━━━━━━━━\n\n"
        "👤 *Customer နာမည်* ထည့်ပါ:\n"
        "_(ပယ်ဖျက်ရန် /cancel)_",
        parse_mode='Markdown'
    )
    return CUST_NAME

async def got_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['name'] = update.message.text.strip()
    await update.message.reply_text("📞 *ဖုန်းနံပါတ်* ထည့်ပါ:", parse_mode='Markdown')
    return CUST_PHONE

async def got_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['phone'] = update.message.text.strip()
    await update.message.reply_text(
        "📱 *Device Model* ထည့်ပါ:\n_(e.g. iPhone 15 Pro, Samsung S24)_",
        parse_mode='Markdown'
    )
    return DEVICE

async def got_device(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['device'] = update.message.text.strip()
    await update.message.reply_text(
        "🔧 *ပြဿနာ / လုပ်ဆောင်ရမည်* ဖော်ပြပါ:\n"
        "_(e.g. Screen ကွဲ, Battery ချွတ်, Charging မဝင်)_",
        parse_mode='Markdown'
    )
    return ISSUE

async def got_issue(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data['issue'] = update.message.text.strip()
    await update.message.reply_text(
        "💰 *ခန့်မှန်းငွေကြေး* (ကျပ်) ထည့်ပါ:\n_(မသိသေးပါက `0` ရိုက်ပါ)_",
        parse_mode='Markdown'
    )
    return PRICE

async def got_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        ctx.user_data['price'] = float(update.message.text.replace(',', '').strip())
    except:
        ctx.user_data['price'] = 0.0
    await update.message.reply_text(
        "📝 *မှတ်ချက်* ထည့်ပါ:\n_(မရှိပါက `-` ရိုက်ပါ)_",
        parse_mode='Markdown'
    )
    return NOTES_STEP

async def got_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    notes = update.message.text.strip()
    if notes == '-':
        notes = ''
    ctx.user_data['notes'] = notes

    d    = ctx.user_data
    code = next_code()
    now  = datetime.now().isoformat()

    conn = db()
    c    = conn.cursor()
    c.execute(
        'INSERT INTO jobs (job_code,cust_name,cust_phone,device,issue,price,notes,status,created_at,updated_at,chat_id) '
        'VALUES (?,?,?,?,?,?,?,?,?,?,?)',
        (code, d['name'], d['phone'], d['device'], d['issue'], d['price'], notes,
         'pending', now, now, update.effective_chat.id)
    )
    conn.commit()
    conn.close()

    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔧 Start Repair",   callback_data=f"ss:{code}:inprogress"),
        InlineKeyboardButton("📦 Wait Parts",     callback_data=f"ss:{code}:waiting_parts"),
    ]])

    await update.message.reply_text(
        f"✅ *Job မှတ်ပုံတင်ပြီးပြီ!*\n\n"
        f"🔖 Code: *{code}*\n"
        f"👤 {d['name']}  📞 {d['phone']}\n"
        f"📱 {d['device']}\n"
        f"🔧 {d['issue']}\n"
        f"💰 {fmt_money(d['price'])}\n"
        f"📊 ⏳ Pending",
        parse_mode='Markdown',
        reply_markup=kb
    )
    ctx.user_data.clear()
    return ConversationHandler.END

async def cancel_conv(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ ပယ်ဖျက်ပြီးပြီ")
    return ConversationHandler.END


# ══════════════════════════════════════════
# JOB LIST COMMANDS
# ══════════════════════════════════════════

async def show_jobs(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['pending', 'inprogress', 'waiting_parts', 'done', 'delivered'],
                    update.effective_chat.id)
    if not jobs:
        await update.message.reply_text("📭 Job မရှိသေးပါ\n➕ /newjob")
        return
    lines = [f"📋 *Active Jobs ({len(jobs)})*\n━━━━━━━━━━━━━━━"]
    for j in jobs:
        lines.append(job_card(j, compact=True))
    text = '\n\n'.join(lines)
    if len(text) > 4000:
        text = text[:4000] + '\n...'
    await update.message.reply_text(text, parse_mode='Markdown')

async def show_pending(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['pending'], update.effective_chat.id)
    if not jobs:
        await update.message.reply_text("✅ Pending Job မရှိပါ")
        return
    await update.message.reply_text(f"⏳ *Pending Jobs — {len(jobs)} ခု*", parse_mode='Markdown')
    for j in jobs[:10]:
        await update.message.reply_text(
            job_card(j), parse_mode='Markdown',
            reply_markup=status_keyboard(j[1], j[8])
        )

async def show_inprogress(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['inprogress', 'waiting_parts'], update.effective_chat.id)
    if not jobs:
        await update.message.reply_text("📭 In Progress Job မရှိပါ")
        return
    await update.message.reply_text(f"🔧 *In Progress — {len(jobs)} ခု*", parse_mode='Markdown')
    for j in jobs[:10]:
        await update.message.reply_text(
            job_card(j), parse_mode='Markdown',
            reply_markup=status_keyboard(j[1], j[8])
        )

async def show_waiting(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['waiting_parts'], update.effective_chat.id)
    if not jobs:
        await update.message.reply_text("📭 Parts စောင့်ဆဲ Job မရှိပါ")
        return
    lines = [f"📦 *Parts စောင့်ဆဲ — {len(jobs)} ခု*\n━━━━━━━━━━━━━━━"]
    for j in jobs:
        lines.append(job_card(j, compact=True))
    await update.message.reply_text('\n\n'.join(lines), parse_mode='Markdown')

async def show_done(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['done', 'delivered'], update.effective_chat.id, limit=15)
    if not jobs:
        await update.message.reply_text("📭 Completed Job မရှိသေးပါ")
        return
    lines = [f"✅ *Completed Jobs — {len(jobs)} ခု*\n━━━━━━━━━━━━━━━"]
    for j in jobs:
        lines.append(job_card(j, compact=True))
    await update.message.reply_text('\n\n'.join(lines), parse_mode='Markdown')

async def show_delivered(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs(['delivered'], update.effective_chat.id, limit=15)
    if not jobs:
        await update.message.reply_text("📭 Delivered Job မရှိသေးပါ")
        return
    lines = [f"📤 *Delivered — {len(jobs)} ခု*\n━━━━━━━━━━━━━━━"]
    for j in jobs:
        lines.append(job_card(j, compact=True))
    await update.message.reply_text('\n\n'.join(lines), parse_mode='Markdown')


# ══════════════════════════════════════════
# SEARCH
# ══════════════════════════════════════════

async def search_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 Customer နာမည်၊ ဖုန်းနံပါတ် သို့မဟုတ် Job Code ရိုက်ပါ:"
    )
    return SEARCH_INPUT

async def search_exec(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q    = update.message.text.strip()
    conn = db()
    c    = conn.cursor()
    c.execute(
        'SELECT * FROM jobs WHERE (cust_name LIKE ? OR cust_phone LIKE ? OR job_code LIKE ?) '
        'AND chat_id=? ORDER BY created_at DESC LIMIT 10',
        (f'%{q}%', f'%{q}%', f'%{q}%', update.effective_chat.id)
    )
    jobs = c.fetchall()
    conn.close()

    if not jobs:
        await update.message.reply_text(f"🔍 *'{q}'* — မတွေ့ပါ", parse_mode='Markdown')
        return ConversationHandler.END

    await update.message.reply_text(f"🔍 *{len(jobs)} ခု တွေ့ပြီ*", parse_mode='Markdown')
    for j in jobs[:5]:
        await update.message.reply_text(
            job_card(j), parse_mode='Markdown',
            reply_markup=status_keyboard(j[1], j[8])
        )
    return ConversationHandler.END


# ══════════════════════════════════════════
# UPDATE STATUS (command)
# ══════════════════════════════════════════

async def update_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✏️ *Job Code* ရိုက်ပါ:\n_(e.g. SVC-0001)_",
        parse_mode='Markdown'
    )
    return UPDATE_JOB_ID

async def update_got_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    conn = db()
    c    = conn.cursor()
    c.execute('SELECT * FROM jobs WHERE job_code=? AND chat_id=?',
              (code, update.effective_chat.id))
    job = c.fetchone()
    conn.close()
    if not job:
        await update.message.reply_text(f"❌ *{code}* မတွေ့ပါ", parse_mode='Markdown')
        return ConversationHandler.END
    await update.message.reply_text(
        job_card(job), parse_mode='Markdown',
        reply_markup=status_keyboard(code, job[8])
    )
    return ConversationHandler.END


# ══════════════════════════════════════════
# EDIT PRICE
# ══════════════════════════════════════════

async def editprice_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💰 *ငွေကြေးပြင်မည်*\nJob Code ရိုက်ပါ:",
        parse_mode='Markdown'
    )
    return EDIT_PRICE_ID

async def editprice_got_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip().upper()
    conn = db()
    c    = conn.cursor()
    c.execute('SELECT * FROM jobs WHERE job_code=? AND chat_id=?',
              (code, update.effective_chat.id))
    job = c.fetchone()
    conn.close()
    if not job:
        await update.message.reply_text(f"❌ {code} မတွေ့ပါ")
        return ConversationHandler.END
    ctx.user_data['price_code'] = code
    await update.message.reply_text(
        f"📱 *{code}* — {job[2]}\n💰 ယခု: {fmt_money(job[6])}\n\nငွေပမာဏ အသစ် ရိုက်ပါ (ကျပ်):",
        parse_mode='Markdown'
    )
    return EDIT_PRICE_VAL

async def editprice_got_val(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.replace(',', '').strip())
    except:
        await update.message.reply_text("❌ ဂဏန်း မှားနေသည်")
        return ConversationHandler.END
    code = ctx.user_data.pop('price_code', '')
    conn = db()
    c    = conn.cursor()
    c.execute('UPDATE jobs SET price=?, updated_at=? WHERE job_code=? AND chat_id=?',
              (price, datetime.now().isoformat(), code, update.effective_chat.id))
    conn.commit()
    conn.close()
    await update.message.reply_text(
        f"✅ *{code}* ငွေကြေး *{fmt_money(price)}* သိမ်းပြီးပြီ",
        parse_mode='Markdown'
    )
    return ConversationHandler.END


# ══════════════════════════════════════════
# CANCEL JOB (direct command)
# ══════════════════════════════════════════

async def cancel_job_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Usage: `/cancel_job SVC-0001`", parse_mode='Markdown'
        )
        return
    code = ctx.args[0].upper()
    conn = db()
    c    = conn.cursor()
    c.execute('UPDATE jobs SET status=?, updated_at=? WHERE job_code=? AND chat_id=?',
              ('cancelled', datetime.now().isoformat(), code, update.effective_chat.id))
    ok = c.rowcount
    conn.commit()
    conn.close()
    if ok:
        await update.message.reply_text(f"❌ *{code}* ပယ်ဖျက်ပြီးပြီ", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ {code} မတွေ့ပါ")


# ══════════════════════════════════════════
# INLINE BUTTON HANDLER
# ══════════════════════════════════════════

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Set Status
    if data.startswith('ss:'):
        _, code, new_st = data.split(':')
        now  = datetime.now().isoformat()
        conn = db()
        c    = conn.cursor()
        c.execute('UPDATE jobs SET status=?, updated_at=? WHERE job_code=?', (new_st, now, code))
        conn.commit()
        c.execute('SELECT * FROM jobs WHERE job_code=?', (code,))
        job = c.fetchone()
        conn.close()
        stat = STATUS_LABEL.get(new_st, new_st)
        try:
            await q.edit_message_text(
                job_card(job) + f"\n\n🔄 → *{stat}*",
                parse_mode='Markdown',
                reply_markup=status_keyboard(code, new_st)
            )
        except Exception:
            pass

    # View full
    elif data.startswith('view:'):
        code = data.split(':', 1)[1]
        conn = db()
        c    = conn.cursor()
        c.execute('SELECT * FROM jobs WHERE job_code=?', (code,))
        job  = c.fetchone()
        conn.close()
        if job:
            try:
                await q.edit_message_text(
                    job_card(job), parse_mode='Markdown',
                    reply_markup=status_keyboard(code, job[8])
                )
            except Exception:
                pass


# ══════════════════════════════════════════
# SUMMARY & REPORTS
# ══════════════════════════════════════════

async def summary(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    today_s  = date.today().isoformat()
    chat_id  = update.effective_chat.id
    conn     = db()
    c        = conn.cursor()

    def q1(sql, *args):
        c.execute(sql, args)
        return c.fetchone()[0] or 0

    new_today  = q1("SELECT COUNT(*) FROM jobs WHERE DATE(created_at)=? AND chat_id=?",  today_s, chat_id)
    done_today = q1("SELECT COUNT(*) FROM jobs WHERE DATE(updated_at)=? AND status IN ('done','delivered') AND chat_id=?", today_s, chat_id)
    revenue    = q1("SELECT SUM(price)  FROM jobs WHERE DATE(updated_at)=? AND status IN ('done','delivered') AND chat_id=?", today_s, chat_id)
    pending    = q1("SELECT COUNT(*) FROM jobs WHERE status='pending'       AND chat_id=?", chat_id)
    inprog     = q1("SELECT COUNT(*) FROM jobs WHERE status='inprogress'    AND chat_id=?", chat_id)
    waiting    = q1("SELECT COUNT(*) FROM jobs WHERE status='waiting_parts' AND chat_id=?", chat_id)
    total      = q1("SELECT COUNT(*) FROM jobs WHERE chat_id=?", chat_id)
    conn.close()

    await update.message.reply_text(
        f"📊 *ဒီနေ့ Summary*\n"
        f"📅 {date.today().strftime('%d/%m/%Y')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆕 ယနေ့ Job အသစ်:    *{new_today}*\n"
        f"✅ ယနေ့ ပြီးဆုံး:      *{done_today}*\n"
        f"💰 ယနေ့ ဝင်ငွေ:       *{fmt_money(revenue)}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏳ Pending:          *{pending}*\n"
        f"🔧 In Progress:      *{inprog}*\n"
        f"📦 Parts စောင့်ဆဲ:   *{waiting}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📁 Total Jobs (all): *{total}*",
        parse_mode='Markdown'
    )

async def monthly(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    now     = date.today()
    month_s = f"{now.year}-{now.month:02d}"
    conn    = db()
    c       = conn.cursor()

    def q1(sql, *args):
        c.execute(sql, args)
        return c.fetchone()[0] or 0

    new_m    = q1("SELECT COUNT(*) FROM jobs WHERE strftime('%Y-%m',created_at)=? AND chat_id=?", month_s, chat_id)
    done_m   = q1("SELECT COUNT(*) FROM jobs WHERE strftime('%Y-%m',updated_at)=? AND status IN ('done','delivered') AND chat_id=?", month_s, chat_id)
    rev_m    = q1("SELECT SUM(price) FROM jobs WHERE strftime('%Y-%m',updated_at)=? AND status IN ('done','delivered') AND chat_id=?", month_s, chat_id)
    cancel_m = q1("SELECT COUNT(*) FROM jobs WHERE strftime('%Y-%m',updated_at)=? AND status='cancelled' AND chat_id=?", month_s, chat_id)
    conn.close()

    await update.message.reply_text(
        f"📈 *{now.strftime('%B %Y')} Monthly Report*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🆕 Job အသစ်:        *{new_m}*\n"
        f"✅ ပြီးဆုံး:           *{done_m}*\n"
        f"❌ ပယ်ဖျက်:          *{cancel_m}*\n"
        f"💰 လပတ်ဝင်ငွေ:      *{fmt_money(rev_m)}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 Completion Rate: *{round(done_m/new_m*100) if new_m else 0}%*",
        parse_mode='Markdown'
    )


# ══════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════

def main():
    if not TOKEN:
        raise ValueError("BOT_TOKEN environment variable မသတ်မှတ်ရသေး!")
    init_db()

    app = Application.builder().token(TOKEN).build()

    # Conversations
    newjob_conv = ConversationHandler(
        entry_points=[CommandHandler('newjob', newjob)],
        states={
            CUST_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            CUST_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_phone)],
            DEVICE:     [MessageHandler(filters.TEXT & ~filters.COMMAND, got_device)],
            ISSUE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_issue)],
            PRICE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, got_price)],
            NOTES_STEP: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_notes)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conv)],
    )

    search_conv = ConversationHandler(
        entry_points=[CommandHandler('search', search_start)],
        states={SEARCH_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, search_exec)]},
        fallbacks=[CommandHandler('cancel', cancel_conv)],
    )

    update_conv = ConversationHandler(
        entry_points=[CommandHandler('update', update_cmd)],
        states={UPDATE_JOB_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, update_got_id)]},
        fallbacks=[CommandHandler('cancel', cancel_conv)],
    )

    editprice_conv = ConversationHandler(
        entry_points=[CommandHandler('editprice', editprice_start)],
        states={
            EDIT_PRICE_ID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, editprice_got_id)],
            EDIT_PRICE_VAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, editprice_got_val)],
        },
        fallbacks=[CommandHandler('cancel', cancel_conv)],
    )

    # Register handlers
    app.add_handler(CommandHandler('start',      start))
    app.add_handler(CommandHandler('help',       help_cmd))
    app.add_handler(CommandHandler('jobs',       show_jobs))
    app.add_handler(CommandHandler('pending',    show_pending))
    app.add_handler(CommandHandler('inprogress', show_inprogress))
    app.add_handler(CommandHandler('waiting',    show_waiting))
    app.add_handler(CommandHandler('done',       show_done))
    app.add_handler(CommandHandler('delivered',  show_delivered))
    app.add_handler(CommandHandler('summary',    summary))
    app.add_handler(CommandHandler('monthly',    monthly))
    app.add_handler(CommandHandler('cancel_job', cancel_job_cmd))
    app.add_handler(newjob_conv)
    app.add_handler(search_conv)
    app.add_handler(update_conv)
    app.add_handler(editprice_conv)
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("✅ Bot started — polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
