# Telegram Shop Bot

ထုတ်ကုန်တွေ ကြည့်ရှုခြင်း၊ **⬅️ Back** / **🏠 Main Menu** navigation၊ online order လုပ်ခြင်းနဲ့
**💰 Balance** (top-up + အော်ဒါနှင့် ငွေနှုတ်) စနစ်ပါဝင်တဲ့ Telegram bot။

- **Framework** — `python-telegram-bot` (async)  •  **DB** — SQLite  •  **Language** — Python 3.11+

---

## 1. အစပြီးဆင်သင့်အချက်များ

### Bot ဖန်တီးခြင်း
1. Telegram မှာ [@BotFather](https://t.me/BotFather) ကို ဖွင့်ပါ → `/newbot`
2. အမည်ပေးပြီး **token** ရပါမည် (`123456:ABC-DEF...`)
3. `/setcommands` နဲ့ command တွေ သတ်မှတ်နိုင်ပါတယ်

> ⚠️ **အရေးကြီး** — `.env.example` ထဲက token ကို commit လုပ်ထားဖြစ်လို့ `@BotFather` → `/revoke` နဲ့
> ပြန်ရရှိပြီး အသစ်ထည့်ပါ။ Token ကို `.env` ထဲမှာသာ သိမ်းပါ (`.gitignore` ထဲကပါ)။

### သင့် Telegram ID ရယူခြင်း
[@userinfobot](https://t.me/userinfobot) သို့မဟုတ် bot ကို `/id` ပို့ပါ — ရရှိတဲ့ ကိန်းက `ADMIN_IDS` ထဲ ထည့်ပါ။

---

## 2. တပ်ဆင်ခြင်း

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # Windows — ပြီးရင် .env ထဲ ပြင်ပါ
python bot.py
```

`.env` ထဲမှာ ပြင်ဆင်ရန်:

```dotenv
BOT_TOKEN=123456:ABC-DEF...
ADMIN_IDS=987654321,123456789
SHOP_NAME=W3K Digital Pay & Services
CURRENCY=MMK
WELCOME_TEXT=👋 Welcome to {shop}
SUPPORT_USERNAME=kothar1992
DB_PATH=shop.db
PAGE_SIZE=6
PROXY=http://127.0.0.1:10808
```

### 🌐 Proxy (အလိုအလို လိုအပ်ပါတယ်)

မြန်မာ / ဘဂရဝန်လိုလို နိုင်ငံတွေမှာ `api.telegram.org` ကို **တိုက်ရိုက်ချိတ်လို့ မရပါ**။
အဲဒါကြောင့် `.env` ထဲက `PROXY` ကို VPN/proxy လိုက်ပါ။

| App | HTTP | SOCKS5 |
|---|---|---|
| v2rayN | `http://127.0.0.1:10808` | `socks5://127.0.0.1:10809` |
| Nekoray | `http://127.0.0.1:11111` | `socks5://127.0.0.1:2080` |

> ⚠️ ခေါင်းစဉ်ထဲမှာ မှန်ကန်တဲ့ **ကိုယ်တိုင် စမ်းသပ်ပါ** — SOCKS5 port မှားနေလျှင် `Malformed reply`
> လို့ error ပေါ်မည်။ Port အမှန်/မှမဟုတ် ကိုယ်တိုင်စစ်ရန်လည်းရှိပါတယ်။
> VPN **ပိတ်လိုက်ပြီး** bot ကိုပဲ အလုပ်လုပ်ချင်ရင် `PROXY=` ကို အလွတ်ထားပါ။

---

## 3. Admin — ဆိုင်ဖွဲ့ခြင်း

### Category ထည့်ခြင်း
```
/addcat 💰 USDT
/addcat 🎫 Account
/cats              ← စာရင်းကြည့်ခြင်း
```

### ထုတ်ကုန် (ပုံ + caption) ထည့်ခြင်း
1. `/addproduct` လို့ ပို့ပါ
2. ထုတ်ကုန် **ပုံ** ပို့ပါ
3. ပုံနဲ့အတူ **caption** ရိုက်ထည့်ပါ — ပုံစံမှာ —

```
အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့်
```

ဥပမာ —
```
USDT TRC20 | 65000 | USDT | 10
မိနစ်ပိုင်းအတွင်း ပေးပို့ပါမည်။
24/7 လက်ကောင်းပေးနိုင်ပါသည်။
```

- ပထမဆုံးလိုင်းက **အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့်**
- Category ကို အမည် (`USDT`) ဒါမှီ id (`1`) နဲ့လည်း ရေးနိုင်ပါတယ်
- Category / ကုန်ပမာနှင့် ကို ချန်လို့ရပါတယ်။ ကုန်ပမာနှင့် မထည့်ရင် **အကန့်မဲ့** သတ်မှတ်ပါမည်
- ပထမဆုံးလိုင်းအောက်က ကျန်ကို **description** အဖြစ် သိမ်းပါမည်

### Command စာရင်း

| Command | လုပ်ပါ |
|---|---|
| `/addproduct` | ပုံ + caption နဲ့ ထုတ်ကုန်ထည့် |
| `/products` | ထုတ်ကုန်စာရင်း |
| `/delproduct <id>` | ထုတ်ကုန်ဖျက် |
| `/toggle <id>` | ထုတ်ကုန် ဖွင့်/ပိတ် |
| `/addcat` · `/cats` · `/delcat <id>` | Category စီမံခြင်း |
| `/give <user_id> <amount>` | လက်ကောင်းထည့် (`-` ရှေ့ထည့်ရင် နှုတ်) |
| `/balance <user_id>` | လက်ကောင်းကြည့် |
| `/broadcast <မက်ဆော်စာ>` | အားလုံးကို ပို့ |
| `/setbanner` | Welcome banner ပုံ သိမ်း / ဖျက် |
| `/setname <အမည်>` | ဆိုင်အမည် ပြောင်း |
| `/pending` | ဆိုင်းငံ့ အော်ဒါများ |
| `/id` | သင့် Telegram ID |

`🛍 ထုတ်ကုန်များ` Main Menu ထဲမှာ **🛠 Admin Panel** ခလုပ်က ဖြတ်လို့လည်းရ — button အသစ်တွေနဲ့
ထုတ်ကုန်/အော်ဒါ/လက်ကောင်း စီမံခြင်း၊

---

## 4. User ဘက် အသုံးပြုပုံ

```
/start  →  Welcome card + Balance + Main Menu
  ├─ 🛍 ထုတ်ကုန်များ   → Category → ထုတ်ကုန်ကတ်များ → 🛒 ဝယ်မည် → အရေအတွက် → အတည်ပြု
  ├─ 💰 သိန်းငွေ       → ပမာနှင့်ရိုက်ထည့် → receipt ပုံပို့ → admin အတည်ပြု
  ├─ 🧾 အော်ဒါမှုမှတ်တမ်း
  ├─ 💬 Live Chat        → @{SUPPORT_USERNAME}
  └─ 📖 အကြံပြုချက်
```

- ⌨️ message box အောက်ရှိ **🏠 Menu** ခလုပ်က Main Menu ပြန်သွားပါမည် — welcome card ပုံပေါ်ကနေ ပေးပို့တာကြောင့်
  အပိုစာသား အပို message မရှိပါ။ Banner မထည့်ရင် ဒီခလုပ်က မပေါ်လာပါ (`.env` ထဲ `MENU_BUTTON` ကို `false` လုပ်လျှင် လုံးဝမပို့ပါ)
- **⬅️ Back** က navigation stack အတိုင်း နောက်သို့ပြန်ပါမည် (bot restart ပြီးလည်း အလုပ်လုပ်ပါမည် — stack ကို SQLite ထဲတွင်သိမ်း)
- Order တင်တဲ့အခါ လက်ကောင်း ချက်ချင်းနှုတ်ပါမည်။ မလုံလောက်ရင် order မဖန်တီးပါ။
- Admin က **❌ ပယ်ဖျက်** နှိပ်လျှင် ငွေ အပြန်အမည် ပြန်ဖြည့်ပါမည်

### 🖼 Welcome Banner

```
/setbanner     → ပုံပို့ (သိမ်း)      /setbanner ထပ်ချလိုက် → ဖျက်
```

ပုံထည့်ပြီးနောက် `/start` လုပ်တိုင်း card ပုံ + 🏠 Menu ခလုပ် ပေါ်လာပါမည်။
ပုံ **မရှိသေးခင်** ဆို welcome card ကို စာသားတစ်ကြောင်းနဲ့ပဲ ပေါ်ပြီး 🏠 Menu ခလုပ်က ပေါ်လာမှာမဟုတ်ပါ။

---

## 5. File ဖွဲ့စည်းပုံ

```
bot.py             အစတွင်းချရန် + handler registration + admin guard
config.py          .env ဖတ်ခြင်း / settings
db.py              SQLite schema + query အားလုံး
keyboards.py       inline keyboard အားလုံး (Back / Main Menu ပါဝင်)
views.py           စာမျက်နှာတိုင်းကို ရေးသားခြင်း
router.py          စာမျက်နှာချိန်ချင်း / Back navigation
handlers_user.py   user command, top-up, order
handlers_admin.py  catalogue + order + balance + broadcast
selftest.py        network မလို screen တိုင်းကို စစ်
simulate.py        fake bot နဲ့ ဝယ်သွယ်မှု flow အပြည့်အစုံ စမ်း
```

---

## 6. စမ်းသပ်ခြင်း

```powershell
python selftest.py         # screen အားလုံး၊ caption parser၊ balance/stock တွက်ချက်
python simulate.py         # /start → catalogue → ဝယ်ခြင်း → အတည်ပြု → ပေးပို့ပြီး → Back
python selftest_infra.py   # health endpoint၊ keep-alive၊ database snapshot
```

နှစ်ခုလုံးက network မလို ခင်းစွာ run ပါမည်။

---

## 7. 🖥 24/7 အနားထားခြင်း (Render free)

PC ပိတ်လိုက်ရင် bot လည်း ပိတ်သွားမည်။ **[Render](https://render.com)** က credit card
မလိုတော့ဘူး၊ GitHub push လုပ်လိုက်ရုံပဲဖြစ်ပါတယ်။

### Free tier ရဲ့ ပြဿနာ ၂ ခု — ဖြေနေပြီးသား

| ပြဿနာ | ဖြေနည်း |
|---|---|
| ၁။ ၁၅ မိနစ် inbound traffic မရှိရင် **အိမ်ချမှု** | `health.py` — `/health` endpoint + bot ကိုယ်တိုင် URL ကို ၉ မိနစ်တိုင်း ping |
| ၂။ deploy/restart တိုင်း **disk ပျက်** → `shop.db` ထုတ်ကုန်၊ လက်ကောင်း၊ order အားလုံး ပျောက် | `backup.py` — Telegram chat ထဲသို့ snapshot ပို့၊ boot မှာ ပြန်ယူ |

DB backup ကိုယ်ပိုင် profile description ထဲမှာ file_id ကို သိမ်းတာဖြစ်လို့ deploy တိုင်းပင်
ဆက်လက်ချိတ်ဆက်နိုင်ပါတယ် — account အသစ်၊ key အသစ် မလိုပါ။

### ဆင်နည်း

1. GitHub repo တစ်ခုတည်း → ဒီ code တင်ပါ
2. [render.com](https://render.com) သွားပါ → **New → Blueprint** → repo ရွေးပါ (ရှိပြီးသား `render.yaml` ကို သတိပြုမည်)
3. Environment variables တွေ ဖြည့်ပါ —

   | Key | တန်ဖိုး |
   |---|---|
   | `BOT_TOKEN` | @BotFather က token |
   | `ADMIN_IDS` | သင့် Telegram id |
   | `BACKUP_ADMIN_ID` | သင့် Telegram id |
   | `SELF_URL` | deploy ပြီးရင် `https://<service>.onrender.com` |
   | `PROXY` | **အလွတ်ထားပါ** — Render (US) က Telegram ကို တိုက်ရိုက်ရောက်နိုင်တာကြောင့် |

4. Deploy → logs မှာ `Bot started as @...` ပေါ်လာပါမည်

### သတိပြုရန်
- Free plan မှာ web service **၁ ခုတည်း**သာ ရှိပြီး **၄၈၅ နာရီအတွင်း** build ပြီးပါက လိုက်ထားပါ။
- `render.yaml` က auto-deploy ဖြစ်လို့ GitHub push တိုင်း **ပြန် deploy ဖြစ်ပါမည်** — backup ကြောင့် data မပျောက်ပါ။ မလိုအပ်ရင် `autoDeploy: false` ချိန်ပါ။
- ၇၅၀ instance-hours/လ free instance ပဲ ရှိပါတယ် — bot တစ်ခုတည်းဆို မလုံလောက်ပါ။

---

## 8. အမှတ်ရမှတ်များ

- ထုတ်ကုန်ပုံတိုင်းက **ကုန်ပမာနှင့် မရှိက်နိုင်ဘူး** — caption ရဲ့ နောက်ဆုံးမှာ `| 10` လို့ ထည့်ပါ။
  အော်ဒါတင်တိုင်း ကုန်ပမာနှင့် လျော့ပါမည်။ မရှိသွားရင် `🔴 ကုန်မရှိပါ` ပေါ်ပါမည်။
- Order ပယ်ဖျက်ချိန်က လက်ကောင်း ပြန်ဖြည့်ပါမည်။ ကုန်ပမာနှင့်က မ ပြန်ပေးထားပါ — လိုအပ်ရင် `/toggle` နဲ့ ပြန်ဖွင့်ပါ။
- `shop.db` နဲ့ `receipts/` ကို `.gitignore` လုပ်ထားပါတယ်။ Backup လိုရင် `shop.db` ကို copy ပါ။
- Server မှာ အနားထားမယ်ဆို systemd / `nohup` / Task Scheduler သုံးပါ။