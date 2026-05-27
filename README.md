# 📱 Phone Service Tracker Bot

ဖုန်းပြုပြင်ရေး Service Job မှတ်တမ်း Telegram Bot

---

## 🚀 Deploy လုပ်နည်း (Railway)

### Step 1 — Bot Token ရယူမည် (2 မိနစ်)

1. Telegram တွင် **@BotFather** ကို ဖွင့်ပါ
2. `/newbot` ပို့ပါ
3. Bot နာမည် ထည့်ပါ (e.g. `MyShop Service Bot`)
4. Bot username ထည့်ပါ (e.g. `myshop_service_bot`) — _bot ဆုံးရမည်_
5. BotFather မှ **Token** ပေးလိမ့်မည် (e.g. `1234567890:ABCdef...`)
6. Token ကို မှတ်ထားပါ

---

### Step 2 — GitHub Upload (3 မိနစ်)

1. **https://github.com** — Sign up / Login
2. **New Repository** နှိပ်ပါ
3. Repository name: `service-bot`
4. **Create repository** နှိပ်ပါ
5. Files ၃ ခု (`bot.py`, `requirements.txt`, `Procfile`) upload လုပ်ပါ
   - "uploading an existing file" link နှိပ်ပြီး drag & drop
6. **Commit changes** နှိပ်ပါ

---

### Step 3 — Railway Deploy (5 မိနစ်)

1. **https://railway.app** သွားပါ
2. **Login with GitHub** နှိပ်ပါ
3. **New Project** → **Deploy from GitHub repo**
4. `service-bot` repo ရွေးပါ
5. Deploy ပြီးနောက် **Variables** tab သွားပါ
6. **Add Variable** နှိပ်ပြီး:
   - Key: `BOT_TOKEN`
   - Value: BotFather မှ ရသော token
7. **Deploy** ပြန်လုပ်ပါ (Redeploy button)

---

### ✅ Done! Bot လုပ်ငန်းဆောင်တာများ

Bot ကို Telegram တွင် ရှာပြီး `/start` ပို့ပါ

---

## 📋 Commands

| Command | လုပ်ဆောင်ချက် |
|---------|------------|
| `/newjob` | Job အသစ်ထည့် |
| `/jobs` | Active Jobs အားလုံး |
| `/pending` | Pending Jobs |
| `/inprogress` | လုပ်ဆောင်ဆဲ Jobs |
| `/waiting` | Parts စောင့်ဆဲ |
| `/done` | ပြီးဆုံးသော Jobs |
| `/delivered` | ထုတ်ပေးပြီး Jobs |
| `/search` | Customer / Code ရှာ |
| `/update` | Status ပြောင်း |
| `/editprice` | ငွေကြေး ပြင် |
| `/cancel_job SVC-0001` | Job ပယ်ဖျက် |
| `/summary` | ဒီနေ့ Summary |
| `/monthly` | လပတ် Report |

## 🔄 Job Status Flow

```
⏳ Pending
    ↓
🔧 In Progress ←→ 📦 Wait Parts
    ↓
✅ Done
    ↓
📤 Delivered
```

---

## 💡 Tips

- Railway Free tier: **$5 credit/month** — ၁ Bot အတွက် လုံလောက်သည်
- Data (SQLite) သည် Railway Volume တွင် သိမ်းဆည်းသည်
- Bot ကို Group Chat တွင်လည်း Add နိုင်သည်
