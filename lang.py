"""Internationalisation.

English is the primary language; Burmese is the alternative.  Every
user-facing string lives in the catalogue below — nothing is hard-coded in the
handlers.  The active language is held in a `ContextVar` that is set at the top
of every update entry point, so any function can call `t()` without threading a
language argument through the call stack.
"""

from __future__ import annotations

import contextvars
from typing import Any

DEFAULT_LANG = "en"

LANGUAGES: dict[str, dict[str, str]] = {
    "en": {"flag": "🇬🇧", "name": "English", "native": "English"},
    "my": {"flag": "🇲🇲", "name": "Burmese", "native": "မြန်မာ"},
}

_current: contextvars.ContextVar[str] = contextvars.ContextVar("telegram_lang", default=DEFAULT_LANG)


# --------------------------------------------------------------------------- #
# catalogue
# --------------------------------------------------------------------------- #
EN: dict[str, str] = {
    # common
    "back": "⬅️ Back",
    "main_menu": "🏠 Main Menu",
    "cancel": "🚫 Cancel",
    "close": "✖️ Close",
    "prev": "◀️",
    "next": "▶️",
    "page": "📄 {page}/{pages}",
    "yes": "✅ Confirm",
    "no": "❌ Cancel",
    "not_found": "⚠️ Not found.",
    "try_again": "⚠️ Something went wrong. Please try again.",
    # main menu
    "welcome": "👋 Welcome to {shop}",
    "balance_line": "💰 Your balance: {balance}",
    "menu_products": "🛍 Products",
    "menu_balance": "💰 Balance",
    "menu_orders": "🧾 Order History",
    "menu_support": "💬 Live Chat",
    "menu_help": "📖 Help",
    "menu_admin": "🛠 Admin Panel",
    "menu_language": "🌐 Language",
    "menu_topup": "💸 Top up",
    "lang_hint": "⌨️ Tap <b>🏠 Menu</b> below to return here at any time.",
    # language
    "lang_pick": "🌐 <b>Choose your language</b>\n\nTap the button below — you can change it any time.",
    "lang_changed": "✅ Language set to <b>{name}</b>.",
    "lang_admin_set": "✅ Default language set to <b>{name}</b>.",
    "lang_current": "🌐 Current language: <b>{name}</b>",
    # catalogue
    "catalog_header": "🗂 <b>Categories</b> — {categories} · 🛍 {products}\n\n"
    "Pick a category to browse.",
    "catalog_empty": "🛍 <b>Catalogue</b>\n\nThere are no products yet.",
    "cat_footer": "{emoji} <b>{name}</b> — {count} items · page {page}/{pages}",
    # product
    "product_stock": "📦 Stock: {stock}",
    "product_stock_inf": "📦 Stock: unlimited",
    "product_warranty": "🛡 Warranty: {warranty}",
    "product_tutorial": "🔗 {url}",
    "buy": "🛒 Buy",
    "buy_or": "🛒 Buy now",
    "ask_price": "📞 Ask for price",
    "ask_price_title": "Ask for a price",
    "price_tbd": "💬 Price on request",
    "sold_out_title": "🔴 Sold out",
    # quantity / confirm
    "qty_header": "🔽 <b>{name}</b>\n",
    "qty_unit": "💵 Price each: <b>{price}</b>",
    "qty_selected": "🔢 Quantity: <b>{qty}</b>",
    "qty_total": "💵 Total: <b>{total}</b>",
    "qty_step": "🔢 {qty}",
    "buy_total": "🚚 Buy · {total}",
    "confirm_title": "📋 <b>Confirm your order</b>\n",
    "confirm_product": "📦 {name}",
    "confirm_qty": "🔢 Quantity — <b>{qty}</b>",
    "confirm_total": "💵 Total — <b>{total}</b>",
    "confirm_wallet": "💳 Wallet — <b>{balance}</b>",
    "confirm_short": "⚠️ Short — <b>{short}</b>",
    "confirm_yes": "✅ Confirm order",
    "topup_short": "💳 Top up {amount}",
    # top-up
    "topup_title": "💸 <b>Top up balance</b>\n\n",
    "topup_step1": "<b>Step 1</b> — Type the amount in the box below (e.g. 50000).",
    "topup_step2": "<b>Step 2</b> — Pay and send your receipt screenshot as a <b>photo</b>.",
    "topup_your_id": "👤 Your ID: <code>{user_id}</code> ({handle})",
    "topup_amount_ok": "✅ <b>{amount}</b> queued.\n\n<b>Step 2</b> — send the receipt photo.",
    "topup_amount_bad": "⚠️ Please type a number, e.g. 50000.",
    "topup_need_start": '📸 Send a receipt after tapping “💰 Top up”.',
    "methods_title": "🎯 <b>Exact top-up</b>\n\n🧾 Pay exactly <b>{amount}</b> for this order.",
    "methods_pick": "👇 Choose how you want to pay",
    "methods_empty": "ℹ️ No payment methods yet — the admin can add some with <code>/addpay</code>.",
    "details_title": "🎯 <b>Exact top-up</b>",
    "details_pay": "{emoji} <b>Pay to {name}</b>\n",
    "details_number": "🏦 Account — <code>{number}</code>",
    "details_name": "👤 Name — <b>{name}</b>",
    "details_note": "📝 {note}",
    "details_receipt": "💬 Send the receipt after paying",
    "details_ref": "🔖 Reference — <code>{code}</code>",
    "copy_number": "📋 Copy account",
    "copy_name": "📋 Copy name",
    "copy_ref": "🔢 Copy reference",
    "copied_number": "🔢 Account\n{number}",
    "copied_name": "👤 Name\n{name}",
    "copied_ref": "🔖 Reference\n{code}",
    # review
    "review_title": "🕐 <b>Top-up pending review</b>",
    "review_ref": "🔖 Reference — <code>#{id}</code>{extra}",
    "review_amount": "💵 Amount — <b>{amount}</b>",
    "review_balance": "💰 Balance — <b>{balance}</b>",
    "status": "📌 Status — {status}",
    "review_waiting": "⏳ The admin is reviewing — please wait up to <b>{minutes} minutes</b>.\n"
    "It is rejected automatically if nobody answers in time.",
    "review_status_btn": "🔄 Check status",
    "review_cancel_btn": "🚫 Cancel",
    "review_pending": "🟡 Pending",
    "review_approved": "🟢 Approved",
    "review_rejected": "🔴 Rejected",
    "review_expired": "⏰ Expired and rejected",
    "review_already": "ℹ️ This request was already answered.",
    "review_still_pending": "🟡 Pending — about {minutes} minutes left",
    "review_cancelled": "🚫 Cancelled.",
    "approve_title": "✅ <b>Top-up approved</b>\n\n🔖 Reference — <code>#{id}</code>",
    "approve_amount": "💵 Credited: {amount}",
    "approve_balance": "💰 <b>Balance: {balance}</b>\n\n🛍 You can buy products now.",
    "reject_title": "❌ <b>Top-up rejected</b>\n\n🔖 Reference — <code>#{id}</code>\nThe receipt was not valid.",
    "expire_title": "⏰ <b>Top-up window expired</b>\n\n"
    "Nobody reviewed it within {minutes} minutes, so it was rejected.\n"
    "💰 Your balance was not changed — send it again.",
    # balance
    "balance_title": "💰 <b>Balance</b>\n\n",
    "balance_name": "👤 Name: {name}",
    "balance_id": "🆔 ID: <code>{user_id}</code>",
    "balance_handle": "🕐 @{handle}",
    "balance_amount": "💵 Available: <b>{balance}</b>",
    # orders
    "orders_title": "🧾 <b>Order history</b>\n",
    "orders_empty": "🧾 <b>Order history</b>\n\nNo orders yet.",
    "orders_item": "<code>#{id}</code> — {product}\n   x{qty} · {total} · {status}",
    "orders_buy": "🛍 Products",
    "status_pending": "🟡 Pending",
    "status_approved": "🟢 Approved",
    "status_delivered": "🔵 Delivered",
    "status_rejected": "🔴 Rejected",
    "order_done": "✅ <b>Order #{id}</b>\n{name}\n🧮 {qty} · {total}\n💰 Balance: {balance}\n\nThe admin will deliver shortly.",
    "order_approved": "✅ <b>Order approved</b>\n\n🔖 <code>#{id}</code> — {product}\n🧮 x{qty} · {total}\n"
    "👤 For {handle}\n\nThe admin will deliver it. Tap below once you receive it.",
    "order_received": "✅ <b>Received</b>\n\nThanks! 🙏 The admin has been notified.",
    "order_no_product": "—",
    # support
    "support_title": "💬 <b>Live chat</b>\n\nMessage {handle} and we will get back to you.",
    "support_body": "Message @{handle} and we will get back to you soon.",
    "support_no_handle": "💬 <b>Live chat</b>\n\nContact the admin for help.",
    "support_no_body": "Contact the admin for help.",
    # help
    "help_title": "📖 <b>How to use</b>\n\n",
    "help_1": "1️⃣ <b>🛍 Products</b> — pick a category and browse.",
    "help_2": "2️⃣ <b>🛒 Buy</b> — choose a quantity, then confirm to pay from your balance.",
    "help_3": "3️⃣ <b>💰 Top up</b> — send the receipt photo, the admin approves it.",
    "help_4": "4️⃣ <b>⬅️ Back / 🏠 Main Menu</b> — move around.",
    "help_5": "5️⃣ <b>🌐 Language</b> — switch between English and Burmese.",
    # errors
    "err_admin_only": "🔒 Only an admin can use this command.",
    "err_unknown_cmd": "⚠️ Unknown command. Try /menu.",
    "err_no_order": "⚠️ Order not found.",
    "err_already_done": "ℹ️ This request was already answered.",
    "err_sold_out": "⚠️ This product is sold out.",
    "err_price_tbd": "📞 This product has no fixed price, so it cannot be ordered.",
    "err_low_balance": "💰 Not enough balance. You need {amount}.",
    "err_too_big": "⚠️ Only {limit} orders at a time.",
    "err_no_tutorial": "This product has no tutorial.",
    # uploads
    "upload_reject": "🚫 <b>Files are not accepted</b>\n\n"
    "For a transfer receipt send a <b>screenshot as a Photo</b>.\n"
    "📎 Documents and other files are refused outright and never reach the server.",
    "upload_reject_tip": "📸 To attach an image, tap the 🎨 palette icon and take a screenshot.",
    "upload_too_big": "⚠️ Image too large. Send one under {limit} MB.",
    "upload_fake": "⚠️ That file is not an image. Only real images are accepted.",
    # admin
    "admin_title": "🛠 <b>Admin panel</b>\n\nManage your catalogue from here.",
    "admin_cat_new": "➕ New category",
    "admin_cat_list": "🗂 Categories",
    "admin_prod_list": "🛍 Products",
    "admin_orders": "📥 Orders",
    "admin_users": "👥 Users",
    "admin_banner": "🖼 Welcome banner",
    "admin_stats": "📊 Statistics",
    "admin_lang": "🌐 Default language",
    "admin_pending": "📥 <b>Orders</b>\n\nNothing pending.",
    "admin_pending_item": "🔔 <b>New order</b>\n\n<code>#{id}</code> — {product}\n🧮 x{qty} · <b>{total}</b>\n"
    "👤 {name} ({handle})\n🆔 <code>{user_id}</code>",
    "admin_topup_item": "💸 <b>Top-up receipt</b>\n\n🔖 <code>#{id}</code>\n👤 {name}\n🆔 <code>{user_id}</code>\n"
    "💵 Amount: <b>{amount}</b>{note}\n\n⏳ Review within <b>{minutes} min</b> or it auto-rejects.",
    "admin_yes": "✅ Approve",
    "admin_no": "❌ Reject",
    "admin_delivered": "🔵 Mark delivered",
    "admin_done": "🔵 <b>Order #{id}</b> — delivered.",
    "admin_user_card": "👤 <b>{name}</b>\n🆔 <code>{user_id}</code>\n🕐 @{handle}\n"
    "💰 Balance: <b>{balance}</b>\n🧾 {orders} orders",
    "admin_users_title": "👥 <b>Users</b>\n",
    "admin_zero": "💵 Set balance to 0",
    "stats_title": "📊 <b>Statistics</b>\n\n",
    "stats_users": "👥 Users: <b>{users}</b>",
    "stats_cats": "🗂 Categories: <b>{cats}</b>",
    "stats_products": "🛍 Products: <b>{active}</b> ({hidden} hidden)",
    "stats_orders": "🧾 Orders: <b>{orders}</b>",
    "stats_revenue": "💵 Revenue: <b>{revenue}</b>",
    "prod_saved": "✅ <b>Product saved</b>\n\n<code>#{id}</code> — {name}\n💵 {price}\n"
    "📦 Stock: {stock}\n🗂 {category}",
    "prod_no_category": "uncategorised",
    "prod_toggle": "{state} <b>{name}</b>",
    "prod_on": "🟢 live",
    "prod_off": "🔴 hidden",
    "prod_deleted": "🗑 Deleted.",
    "prod_none": "🛍 No products yet. Use /addproduct to add one.",
    "cat_deleted": "🗑 Category <code>{id}</code> deleted.",
    "cat_none": "🗂 No categories yet — use <code>/addcat</code>.",
    "addproduct_prompt": "🛍 <b>Add a product</b>\n\n"
    "<b>Step 1</b> — send the product photo.\n\n"
    "<b>Step 2</b> — send a caption with the photo:\n\n"
    "<code>Name | Price | Category | Stock | Warranty | Tutorial</code>\n"
    "<code>USDT TRC20 | 65000 | Crypto | 10 | 30 min | https://t.me/x</code>\n\n"
    "Only the fields you need — the rest may be left off.\n"
    "Everything after the first line is saved as the description.",
    "addproduct_caption_prompt": "📝 <b>Step 2</b> — send the caption with the photo.\n\n"
    "<code>Name | Price | Category | Stock | Warranty | Tutorial</code>",
    "addproduct_bad_caption": "⚠️ Bad caption — use <code>Name | Price</code> to start.",
    "addcat_prompt": "🗂 Type the category name.",
    "addcat_saved": "✅ Category saved — <code>{id}</code> · {emoji} {name}",
    "delcat_usage": "⚠️ Use <code>/delcat &lt;id&gt;</code>.",
    "delproduct_usage": "⚠️ Use <code>/delproduct &lt;id&gt;</code>.",
    "give_usage": "⚠️ Use <code>/give &lt;user_id&gt; &lt;amount&gt;</code>.",
    "give_done": "✅ <code>{user_id}</code> balance is now {balance}.",
    "balance_usage": "⚠️ Use <code>/balance &lt;user_id&gt;</code>.",
    "id_reply": "🆔 Your Telegram ID: <code>{user_id}</code>\n👤 {name}\n🔑 Admin: {admin}",
    "id_yes": "yes",
    "id_no": "no",
    "broadcast_prompt": "📢 Type the broadcast message.",
    "broadcast_done": "📢 Sent — {ok} delivered · {failed} failed",
    "broadcast_empty": "⚠️ Type a message to broadcast.",
    "setbanner_prompt": "🖼 Send the welcome banner image.",
    "setbanner_saved": "🖼 Welcome banner saved.",
    "setbanner_cleared": "🖼 Welcome banner removed.",
    "setname_usage": "⚠️ Use <code>/setname &lt;name&gt;</code>.",
    "setname_done": "✅ Shop name: {name}",
    "demo_done": "✅ <b>Demo catalogue ready</b>\n\n🗂 Categories: <b>{cats}</b>\n"
    "🛍 Products: <b>{products}</b>\n💰 Your balance: <b>{balance}</b>\n\n"
    "Tap <b>🛍 Products</b> to look around.\n🧹 Remove it with <code>/demo clear</code>",
    "demo_exists": "ℹ️ Demo data already exists — run <code>/demo clear</code> first.",
    "demo_cleared": "🗑 Removed <b>{count}</b> demo products.",
    "demo_nothing": "ℹ️ No demo data. Run <code>/demo</code> first.",
    "paymethods_title": "💳 <b>Payment methods</b>\n",
    "paymethods_none": "💳 No payment methods yet.",
    "paymethods_item": "{flag} <code>{id}</code> · {emoji} {name}{number}{holder}",
    "addpay_usage": "⚠️ Use <code>/addpay &lt;emoji&gt; &lt;name&gt; | &lt;account&gt; | &lt;name&gt;</code>.",
    "addpay_done": "✅ Saved — <code>{id}</code> · {emoji} {name}",
    "delpay_usage": "⚠️ Use <code>/delpay &lt;id&gt;</code>.",
    "admin_only_cmd": "🔒 Admin only.",
    "lang_set_user": "✅ Language set to <b>{name}</b>.",
    # misc
    "tutorial_msg": "📂 <b>{name}</b>\n🔗 {url}",
    "share_msg": "🛍 {name}",
    "archived": "—",
    # admin extras
    "cat_list_title": "🗂 <b>Categories</b>\n",
    "cat_list_item": "<code>{id}</code> · {emoji} {name} — {count}",
    "prod_list_title": "🛍 <b>Products</b>\n",
    "prod_admin_price": "💵 Price: <b>{price}</b>",
    "prod_admin_stock": "📦 Stock: {stock}",
    "prod_admin_cat": "🗂 {category}",
    "prod_hide_btn": "🔴 Hide",
    "prod_show_btn": "🟢 Show",
    "prod_del_btn": "🗑 Delete",
    "prod_toggled": "{state} — {name}",
    "toggle_usage": "⚠️ Use <code>/toggle &lt;id&gt;</code>.",
    "cat_del_btn": "🗑 Delete",
    "paymethods_edit": "Edit — <code>/addpay &lt;emoji&gt; &lt;name&gt; | &lt;account&gt; | &lt;name&gt;</code>",
    "paymethods_del": "Delete — <code>/delpay &lt;id&gt;</code>",
    "err_user_not_found": "⚠️ That user was not found.",
    "broadcast_sending": "📢 Sending…",
    "give_notify": "💰 New balance: {balance}",
    "order_refund": "❌ <b>Order rejected</b>\n\n🔖 <code>#{id}</code>\n\n"
    "💰 Refunded: {total}\n💵 Balance: {balance}",
    "deliver_btn": "✅ I received it",
    "deliver_thanks": "✅ Thanks! 🙏",
    "deliver_notify": "✅ <code>{user_id}</code> received order <b>#{order_id}</b>.",
    "banner_set_hint": "🖼 Welcome banner saved — remove it with /setbanner.",
    "banner_sent": "📷 Send the photo.",
    "banner_cleared_alert": "🖼 Banner removed",
    "add_note": "➕ Add",
    "add_note_sub": "➖ Subtract",
    "zero_notify": "💵 Balance reset — remaining: <b>{balance}</b>",
    "quick_add_notify": "{verb}\n\nRemaining balance: <b>{balance}</b>",
    "tutorial_none": "📂 No tutorial for this product.",
    "tutorial_open": "📂 Opening the tutorial",
    # ops
    "backup_caption": "💾 <b>Automatic backup</b>\n"
    "🕐 {when}\n"
    "👥 Users: {users}\n"
    "🧾 Orders: {orders}",
}

MY: dict[str, str] = {
    "back": "⬅️ Back",
    "main_menu": "🏠 Main Menu",
    "cancel": "🚫 ပယ်ဖျက်",
    "close": "✖️ ပိတ်",
    "prev": "◀️",
    "next": "▶️",
    "page": "📄 {page}/{pages}",
    "yes": "✅ အတည်ပြု",
    "no": "❌ ပယ်ဖျက်",
    "not_found": "⚠️ မတွေ့ပါ။",
    "try_again": "⚠️ အမှားဖြစ်ပါတယ်။ ထပ်ကြိုးစားပါ။",
    "welcome": "👋 {shop} မှ ကြိုဆိုပါသည်",
    "balance_line": "💰 သင့်လက်ကောင်း: {balance}",
    "menu_products": "🛍 ထုတ်ကုန်များ",
    "menu_balance": "💰 သိန်းငွေ",
    "menu_orders": "🧾 အော်ဒါမှုမှတ်တမ်း",
    "menu_support": "💬 Live Chat",
    "menu_help": "📖 အကြံပြုချက်",
    "menu_admin": "🛠 Admin Panel",
    "menu_language": "🌐 ဘာသာစကား",
    "menu_topup": "💸 သိန်းငွေဖြည့်မယ်",
    "lang_hint": "⌨️ ပြန်လည်သွားရန် အောက်ရှိ <b>🏠 Menu</b> ကို နှိပါပါ။",
    "lang_pick": "🌐 <b>ဘာသာစကား ရွေးပါ</b>\n\nအောက်က ခလုပ်ကို နှိပါပါ — အချိန်မရှိဘဲ ပြောင်းနိုင်ပါတယ်။",
    "lang_changed": "✅ ဘာသာစကား <b>{name}</b> သို့ ပြောင်းပြီးပါပြီ။",
    "lang_admin_set": "✅ Default ဘာသာစကား <b>{name}</b> သို့ သတ်မှတ်ပြီးပါပြီ။",
    "lang_current": "🌐 လက်ရှိဘာသာစကား: <b>{name}</b>",
    "catalog_header": "🗂 <b>Category စာရင်း</b> — {categories} ခု · 🛍 {products} ခု\n\n"
    "အောက်က အမျိုးအစားကို ရွေးပါ။",
    "catalog_empty": "🛍 <b>ထုတ်ကုန်စာရင်း</b>\n\nယခုအချိန်တွင် ထုတ်ကုန်များ မရှိသေးပါ။",
    "cat_footer": "{emoji} <b>{name}</b> — စာရင်း {count} ခု · စာမျက်နှာ {page}/{pages}",
    "product_stock": "📦 ကုန်ပမာနှင့်: {stock}",
    "product_stock_inf": "📦 ကုန်ပမာနှင့်: အကန့်မဲ့",
    "product_warranty": "🛡 အာမခံ: {warranty}",
    "product_tutorial": "🔗 {url}",
    "buy": "🛒 ဝယ်မည်",
    "buy_or": "🛒 သို့မဟုတ် ဝယ်မည်",
    "ask_price": "📞 စျေးနှင့်မေးမြန်းမည်",
    "ask_price_title": "စျေးနှင့်မေးမြန်းရန်",
    "price_tbd": "💬 စျေးနှင့်မသတ်မှတ်",
    "sold_out_title": "🔴 ကုန်မရှိပါ",
    "qty_header": "🔽 <b>{name}</b>\n",
    "qty_unit": "💵 စျေးကြေးတစ်ခုလျှင်: <b>{price}</b>",
    "qty_selected": "🔢 ရွေးပြီးသော ပမာနှင့်: <b>{qty}</b>",
    "qty_total": "💵 စုစုပေါင်း: <b>{total}</b>",
    "qty_step": "🔢 {qty}",
    "buy_total": "🚚 ဝယ်မည် · {total}",
    "confirm_title": "📋 <b>အတည်ပြုရန် — အော်ဒါ</b>\n",
    "confirm_product": "📦 {name}",
    "confirm_qty": "🔢 ပမာနှင့် — <b>{qty}</b>",
    "confirm_total": "💵 စုစုပေါင်း — <b>{total}</b>",
    "confirm_wallet": "💳 လက်ကောင်း — <b>{balance}</b>",
    "confirm_short": "⚠️ လိုအပ်သော — <b>{short}</b>",
    "confirm_yes": "✅ အတည်ပြုဝယ်မည်",
    "topup_short": "💳 သိန်းငွေဖြည့်မည် · {amount}",
    "topup_title": "💸 <b>သိန်းငွေဖြည့်မည်</b>\n\n",
    "topup_step1": "<b>အဆင့် (၁)</b> — ဖြည့်ချင်သော ပမာနှင့်ကိန်းကို အောက်က input box တွင် ရိုက်ထည့်ပါ။ (ဥပမာ — 50000)",
    "topup_step2": "<b>အဆင့် (၂)</b> — ငွေလွှဲပြေးပြီးလျှင် receipt ကို <b>ပုံ</b> အဖြစ် ပို့ပါ။",
    "topup_your_id": "👤 သင့် ID: <code>{user_id}</code> ({handle})",
    "topup_amount_ok": "✅ <b>{amount}</b> သိမ်းဆည်းမှု။\n\n<b>အဆင့် (၂)</b> — receipt ပုံ ပို့ပါ။",
    "topup_amount_bad": "⚠️ နံပါတ်ပြထဲ ရိုက်ထည့်ပါ။ (ဥပမာ — 50000)",
    "topup_need_start": "📸 “💰 သိန်းငွေဖြည့်မည်” ကို နှိပါပြီးမှ receipt ပုံ ပို့ပါ။",
    "methods_title": "🎯 <b>အတိအကျ သိန်းငွေဖြည့်မည်</b>\n\n🧾 Order အတိုင်း <b>{amount}</b> ကို ပေးချေးမယ်။",
    "methods_pick": "👇 ပေးချေးမည့် နည်းလမ်းကို ရွေးပါ",
    "methods_empty": "ℹ️ ပေးချေးမည့်နည်းလမ်း မရှိသေးပါ — admin က <code>/addpay</code> ထည့်ပါ။",
    "details_title": "🎯 <b>အတိအကျ သိန်းငွေဖြည့်မည်</b>",
    "details_pay": "{emoji} <b>{name} အလှန်လှဲ့နေရန်</b>\n",
    "details_number": "🏦 ဘဏ်/အကောင့် — <code>{number}</code>",
    "details_name": "👤 အမည် — <b>{name}</b>",
    "details_note": "📝 {note}",
    "details_receipt": "💬 ပေးချေးပြီးလျှင် receipt ပုံ ပို့ပါ",
    "details_ref": "🔢 အမှတ်အသား — <code>{code}</code>",
    "copy_number": "📋 နံပါတ်ကိုကူးယူ",
    "copy_name": "📋 အမည်ကိုကူးယူ",
    "copy_ref": "🔢 အမှတ်အသားကိုကူးယူ",
    "copied_number": "🔢 နံပါတ်\n{number}",
    "copied_name": "👤 အမည်\n{name}",
    "copied_ref": "🔖 အမှတ်အသား\n{code}",
    "review_title": "🕐 <b>ငွေလွှဲ စောင့်ဆိုင်းငံ့</b>",
    "review_ref": "🔖 အမှတ်အသား — <code>#{id}</code>{extra}",
    "review_amount": "💵 ပမာနှင့် — <b>{amount}</b>",
    "review_balance": "💰 လက်ကောင်း — <b>{balance}</b>",
    "status": "📌 အခြေအနေ — {status}",
    "review_waiting": "⏳ Admin က စစ်ဆေးနေပါသည် — <b>{minutes} မိနစ်ခန့်</b> စောင့်ပါ။\n"
    "အချိန်ကုန်လျှင် အလိုအလျောက် ပယ်ဖျက်ပါမည်။",
    "review_status_btn": "🔄 အခြေအနေ စစ်မည်",
    "review_cancel_btn": "🚫 ပယ်ဖျက်မည်",
    "review_pending": "🟡 စောင့်ဆိုင်းငံ့",
    "review_approved": "🟢 အတည်ပြုပြီး",
    "review_rejected": "🔴 ပယ်ဖျက်ပြီး",
    "review_expired": "⏰ အချိန်ကုန်သွားပြီး ပယ်ဖျက်ပြီး",
    "review_already": "ℹ️ ဤတင်ဆက်မှုကို ရင်းနှီးမှ ဖြေပြီးသားပါ။",
    "review_still_pending": "🟡 စောင့်ဆိုင်းငံ့ — မိနစ် {minutes} ခန့် ကျန်ပါသေးသည်",
    "review_cancelled": "🚫 ပယ်ဖျက်ပြီးပါပြီ။",
    "approve_title": "✅ <b>သိန်းငွေ အတည်ပြုပြီးပါပြီ</b>\n\n🔖 အမှတ်အသား — <code>#{id}</code>",
    "approve_amount": "💵 ထည့်သွင်းသော: {amount}",
    "approve_balance": "💰 <b>လက်ကောင်း ကျန်ရှိ: {balance}</b>\n\n🛍 ထုတ်ကုန်များ ဝယ်ယူနိုင်ပါပြီ။",
    "reject_title": "❌ <b>သိန်းငွေဖြည့်မှု ပယ်ဖျက်ပြီး</b>\n\n🔖 အမှတ်အသား — <code>#{id}</code>\nReceipt ကို ပြန်စစ်ဆေးပေးပါ။",
    "expire_title": "⏰ <b>သိန်းငွေဖြည့်မှု အချိန်ကုန်သွားပါပြီ</b>\n\n"
    "{minutes} မိနစ်အတွင်း Admin က မစစ်ဆေးနိုင်ခဲ့သဖြင့် ပယ်ဖျက်ပြီးပါပြီ။\n"
    "💰 လက်ကောင်း မထည့်ထားပါ — ထပ်ပို့လိုပါက ပြန်လုပ်ဆင်းပါ။",
    "balance_title": "💰 <b>လက်ကောင်းအင်ဒုတ်</b>\n\n",
    "balance_name": "👤 အမည်: {name}",
    "balance_id": "🆔 ID: <code>{user_id}</code>",
    "balance_handle": "🕐 @{handle}",
    "balance_amount": "💵 ကျန်လက်ကောင်း: <b>{balance}</b>",
    "orders_title": "🧾 <b>အော်ဒါမှုမှတ်တမ်း</b>\n",
    "orders_empty": "🧾 <b>အော်ဒါမှုမှတ်တမ်း</b>\n\nအော်ဒါ မရှိသေးပါ။",
    "orders_item": "<code>#{id}</code> — {product}\n   x{qty} · {total} · {status}",
    "orders_buy": "🛍 ထုတ်ကုန်များ",
    "status_pending": "🟡 ဆိုင်းငံ့",
    "status_approved": "🟢 အတည်ပြုပြီး",
    "status_delivered": "🔵 ပေးပြီး",
    "status_rejected": "🔴 ပယ်ဖျက်ပြီး",
    "order_done": "✅ <b>အော်ဒါ #{id}</b>\n{name}\n🧮 {qty} · {total}\n💰 လက်ကောင်း: {balance}\n\nAdmin က စစ်ဆေးပြီး ပေးပို့ပေးပါမည်။",
    "order_approved": "✅ <b>အော်ဒါ အတည်ပြုပြီး</b>\n\n🔖 <code>#{id}</code> — {product}\n🧮 x{qty} · {total}\n"
    "👤 သင့်အတွက် ({handle})\n\nAdmin က ပေးပို့ပေးပါမည်။ ရရှိပြီးရင် အောက်က ခလုပ်ပေးပါ။",
    "order_received": "✅ <b>လက်ခံရရှိပြီး</b>\n\nကျေးဇူးတင်ပါသည်! 🙏 Admin ကို အကြောင်းကြားပါပါတယ်။",
    "order_no_product": "—",
    "support_title": "💬 <b>Live Chat</b>\n\n",
    "support_body": "အကောင်းပြုမှုအတွက် @{handle} ကို ရိုက်ဆက်ပေးပါ။",
    "support_no_handle": "💬 <b>Live Chat</b>\n\n",
    "support_no_body": "အကောင်းပြုမှုအတွက် Admin ကို ဆက်သွယ်ပါ။",
    "help_title": "📖 <b>အသုံးပြုနည်း</b>\n\n",
    "help_1": "1️⃣ <b>🛍 ထုတ်ကုန်များ</b> — အမျိုးအစားရွေးပြီး ကြည့်ပါ။",
    "help_2": "2️⃣ <b>🛒 ဝယ်မည်</b> — ပမာနှင့်ရွေးပြီး အတည်ပြုပါ။",
    "help_3": "3️⃣ <b>💰 သိန်းငွေဖြည့်မည်</b> — receipt ပုံပို့ပြီး admin အတည်ပြုပေးပါ။",
    "help_4": "4️⃣ <b>⬅️ Back / 🏠 Main Menu</b> — နောက်သို့ပြန်ပါ။",
    "help_5": "5️⃣ <b>🌐 ဘာသာစကား</b> — English / မြန်မာ ပြောင်းနိုင်ပါတယ်။",
    "err_admin_only": "🔒 ဤ command ကို admin သာ သုံးနိုင်ပါတယ်။",
    "err_unknown_cmd": "⚠️ မသိမှန်တဲ့ command ဖြစ်ပါတယ်။ `/menu` နှိပါပါ။",
    "err_no_order": "⚠️ အော်ဒါ မတွေ့ရဘူး။",
    "err_already_done": "ℹ️ ဤတင်ဆက်မှုကို ရင်းနှီးမှ ဖြေပြီးသားပါ။",
    "err_sold_out": "⚠️ ဤထုတ်ကုန် ကုန်ပမာနှင့်မရှိတော့ပါ။",
    "err_price_tbd": "📞 ဤထုတ်ကုန်က စျေးနှင့်မသတ်မှတ်ဖြစ်လို့ အော်ဒါလုပ်လို့ မရပါ။",
    "err_low_balance": "💰 လက်ကောင်း မလုံလောက်ပါ။ လိုအပ်သော: {amount}",
    "err_too_big": "⚠️ တစ်ခါလျှင် {limit} အထက် မရပါ။",
    "err_no_tutorial": "ဤထုတ်ကုန်အတွက် tutorial မရှိပါ။",
    "upload_reject": "🚫 <b>ဖိုင်ပို့ခြင်း မခွင့်ပါ။</b>\n\n"
    "ငွေလွှဲလက်ခံရန် screenshot ပုံကို <b>Photo</b> အဖြစ်ပဲ ပို့ပါ။\n"
    "📎 ဖိုင်/Document အဖြစ်ပို့လျှင် လုံးဝ လက်ခံမည်မဟုတ်ပါ။",
    "upload_reject_tip": "📸 ပုံဖွင့်ရန် အလင်းရောင် 🎨 ကို နှိပ်ပြီး screenshot ရယူပါ။",
    "upload_too_big": "⚠️ ပုံအရွယ်အစား ကြီးလွန်းပါသည်။ {limit} MB အောက် ပုံဖြင့် ထပ်ပို့ပါ။",
    "upload_fake": "⚠️ ဖိုင်သည် ပုံမဟုတ်ပါ။ ကျွန်တော်က ပုံမှန်များကိုသာ လက်ခံပါမယ်။",
    "admin_title": "🛠 <b>Admin Panel</b>\n\nဆိုင်ကိုယ်တိုင်းကို ဒီနေရာကနေ စီမံပါ။",
    "admin_cat_new": "➕ Category ထည့်မယ်",
    "admin_cat_list": "🗂 Category စာရင်း",
    "admin_prod_list": "🛍 ထုတ်ကုန်စာရင်း",
    "admin_orders": "📥 အော်ဒါများ",
    "admin_users": "👥 အသုံးပြုသူများ",
    "admin_banner": "🖼 Welcome Banner",
    "admin_stats": "📊 အချက်အလက်များ",
    "admin_lang": "🌐 Default ဘာသာစကား",
    "admin_pending": "📥 <b>အော်ဒါများ</b>\n\nဆိုင်းငံ့ အော်ဒါ မရှိပါ။",
    "admin_pending_item": "🔔 <b>အော်ဒါအသစ်</b>\n\n<code>#{id}</code> — {product}\n🧮 x{qty} · <b>{total}</b>\n"
    "👤 ဝယ်သူ: {name} ({handle})\n🆔 <code>{user_id}</code>",
    "admin_topup_item": "💸 <b>သိန်းငွေဖြည့်တင်မှု (receipt)</b>\n\n🔖 <code>#{id}</code>\n"
    "👤 အမည်: {name}\n🆔 <code>{user_id}</code>\n💵 ပမာနှင့်: <b>{amount}</b>{note}\n\n"
    "⏳ <b>{minutes} မိနစ်</b> အတွင်း စစ်ဆေးပါ — မလုပ်ရင် အလိုအလျောက် ပယ်ဖျက်ပါမည်။",
    "admin_yes": "✅ အတည်ပြု",
    "admin_no": "❌ ပယ်ဖျက်",
    "admin_delivered": "🔵 ပေးပြီးသွင်းမည်",
    "admin_done": "🔵 <b>အော်ဒါ #{id}</b> — ပေးပြီးပါပြီ။",
    "admin_user_card": "👤 <b>{name}</b>\n🆔 <code>{user_id}</code>\n🕐 @{handle}\n"
    "💰 လက်ကောင်း: <b>{balance}</b>\n🧾 အော်ဒါ {orders} ခု",
    "admin_users_title": "👥 <b>အသုံးပြုသူများ</b>\n",
    "admin_zero": "💵 Balance သတ်မှတ်",
    "stats_title": "📊 <b>အချက်အလက်များ</b>\n\n",
    "stats_users": "👥 အသုံးပြုသူ: <b>{users}</b>",
    "stats_cats": "🗂 Category: <b>{cats}</b>",
    "stats_products": "🛍 ထုတ်ကုန်: <b>{active}</b> ({hidden} ပိတ်)",
    "stats_orders": "🧾 အော်ဒါ: <b>{orders}</b>",
    "stats_revenue": "💵 ရောင်းရလိုက်သော: <b>{revenue}</b>",
    "prod_saved": "✅ <b>ထုတ်ကုန် ထည့်ပြီးပါပြီ</b>\n\n<code>#{id}</code> — {name}\n💵 {price}\n"
    "📦 ကုန်ပမာနှင့်: {stock}\n🗂 {category}",
    "prod_no_category": "Category မသတ်မှတ်",
    "prod_toggle": "{state} <b>{name}</b>",
    "prod_on": "🟢 တင်းကြီး",
    "prod_off": "🔴 ပိတ်",
    "prod_deleted": "🗑 ဖျက်ပြီးပါပြီ။",
    "prod_none": "🛍 ထုတ်ကုန် မရှိသေးပါ။ `/addproduct` သုံးပါ။",
    "cat_deleted": "🗑 Category <code>{id}</code> ဖျက်ပြီးပါပြီ။",
    "cat_none": "🗂 Category မရှိသေးပါ။ `/addcat` သုံးပါ။",
    "addproduct_prompt": "🛍 <b>ထုတ်ကုန်ထည့်ရန်</b>\n\n"
    "အဆင့် (၁) — ထုတ်ကုန်ပုံ ပို့ပါ။\n\n"
    "အဆင့် (၂) — ပုံနဲ့အတူ Caption ပို့ပါ —\n\n"
    "<code>အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့် | အာမခံ | Tutorial</code>\n"
    "<code>USDT TRC20 | 65000 | Crypto | 10 | 30 မိနစ် | https://t.me/x</code>\n\n"
    "လိုအပ်တဲ့ field တွေပဲ ထည့်ပါ — ကျန်တာ ချန်လို့ရပါတယ်။\n"
    "ပထမဆုံးလိုင်းအောက်ကို description အဖြစ် သိမ်းပါမည်။",
    "addproduct_caption_prompt": "📝 အဆင့် (၂) — ပုံနဲ့အတူ Caption ပို့ပါ —\n\n"
    "<code>အမည် | စျေးကြေး | Category | ကုန်ပမာနှင့် | အာမခံ | Tutorial</code>",
    "addproduct_bad_caption": "⚠️ Caption ပုံစံ မမှန်ပါ — `<အမည်> | <စျေးကြေး>` အတိုင်း စမ်းပါ။",
    "addcat_prompt": "🗂 Category အမည် ရိုက်ထည့်ပါ။",
    "addcat_saved": "✅ Category ထည့်ပြီးပါပြီ — <code>{id}</code> · {emoji} {name}",
    "delcat_usage": "⚠️ `/delcat <id>` သုံးပါ။",
    "delproduct_usage": "⚠️ `/delproduct <id>` သုံးပါ။",
    "give_usage": "⚠️ `/give <user_id> <amount>` သုံးပါ။",
    "give_done": "✅ <code>{user_id}</code> လက်ကောင်း: {balance}",
    "balance_usage": "⚠️ `/balance <user_id>` သုံးပါ။",
    "id_reply": "🆔 သင့် Telegram ID: <code>{user_id}</code>\n👤 အမည်: {name}\n🔑 Admin: {admin}",
    "id_yes": "ဟုတ်ကဲ့",
    "id_no": "မဟုတ်",
    "broadcast_prompt": "📢 ပို့ရန် မက်ဆော်စာ ရိုက်ထည့်ပါ။",
    "broadcast_done": "📢 ပို့ပြီးပါပြီ — အောင်မြင် {ok} · မအောင်မြင် {failed}",
    "broadcast_empty": "⚠️ မက်ဆော်စာ ရိုက်ထည့်ပါ။",
    "setbanner_prompt": "🖼 Welcome banner ပုံ ပို့ပါ။",
    "setbanner_saved": "🖼 Welcome banner သိမ်းပြီးပါပြီ။",
    "setbanner_cleared": "🖼 Welcome banner ဖျက်ပြီးပါပြီ။",
    "setname_usage": "⚠️ `/setname <အမည်>` သုံးပါ။",
    "setname_done": "✅ ဆိုင်အမည်: {name}",
    "demo_done": "✅ <b>Demo catalogue ထည့်ပြီးပါပြီ</b>\n\n🗂 Category: <b>{cats}</b>\n"
    "🛍 ထုတ်ကုန်: <b>{products}</b>\n💰 သင့်လက်ကောင်း: <b>{balance}</b>\n\n"
    "<b>🛍 ထုတ်ကုန်များ</b> ကို နှိပါပြီး စမ်းကြည့်ပါ။\n🧹 ဖျက်ချင်ရင် <code>/demo clear</code>",
    "demo_exists": "ℹ️ Demo data ရှိနေပါပြီ။ အရင် <code>/demo clear</code> နဲ့ ဖျက်ပါ။",
    "demo_cleared": "🗑 Demo ထုတ်ကုန် <b>{count}</b> ခု ဖျက်ပြီးပါပြီ။",
    "demo_nothing": "ℹ️ Demo data မရှိပါ။ အရင်က <code>/demo</code> ရိုက်ဖို့ မလိုပါ။",
    "paymethods_title": "💳 <b>ပေးချေးမည့် နည်းလမ်းများ</b>\n",
    "paymethods_none": "💳 ပေးချေးမည့်နည်းလမ်း မရှိပါ။",
    "paymethods_item": "{flag} <code>{id}</code> · {emoji} {name}{number}{holder}",
    "addpay_usage": "⚠️ `/addpay <emoji> <name> | <နံပါတ်> | <အမည်>` သုံးပါ။",
    "addpay_done": "✅ ထည့်ပြီးပါပြီ — <code>{id}</code> · {emoji} {name}",
    "delpay_usage": "⚠️ `/delpay <id>` သုံးပါ။",
    "admin_only_cmd": "🔒 Admin သာ။",
    "lang_set_user": "✅ ဘာသာစကား <b>{name}</b> သို့ ပြောင်းပြီးပါပြီ။",
    "tutorial_msg": "📂 <b>{name}</b>\n🔗 {url}",
    "share_msg": "🛍 {name}",
    "archived": "—",
    # admin extras
    "cat_list_title": "🗂 <b>Category စာရင်း</b>\n",
    "cat_list_item": "<code>{id}</code> · {emoji} {name} — {count} ခု",
    "prod_list_title": "🛍 <b>ထုတ်ကုန်စာရင်း</b>\n",
    "prod_admin_price": "💵 စျေးကြေး: <b>{price}</b>",
    "prod_admin_stock": "📦 ကုန်ပမာနှင့်: {stock}",
    "prod_admin_cat": "🗂 {category}",
    "prod_hide_btn": "🔴 ပိတ်ပါ",
    "prod_show_btn": "🟢 ပြန်ဖွင့်ပါ",
    "prod_del_btn": "🗑 ဖျက်ပါ",
    "prod_toggled": "{state} — {name}",
    "toggle_usage": "⚠️ `/toggle <id>` သုံးပါ။",
    "cat_del_btn": "🗑 ဖျက်ပါ",
    "paymethods_edit": "ပြင်ရန် — `/addpay <emoji> <name> | <နံပါတ်> | <အမည်>`",
    "paymethods_del": "ဖျက်ရန် — `/delpay <id>`",
    "err_user_not_found": "⚠️ အဲဒီ user ကို မတွေ့ပါ။",
    "broadcast_sending": "📢 ပို့နေပါသည်...",
    "give_notify": "💰 လက်ကောင်းအသစ်: {balance}",
    "order_refund": "❌ <b>အော်ဒါ ပယ်ဖျက်ပြီး</b>\n\n<code>#{id}</code>\n\n"
    "💰 ငွေပြန်အမည်: {total}\n💵 ကျန်လက်ကောင်း: {balance}",
    "deliver_btn": "✅ လက်ခံရရှိပြီး",
    "deliver_thanks": "✅ ကျေးဇူးတင်ပါသည်! 🙏",
    "deliver_notify": "✅ <code>{user_id}</code> က အော်ဒါ <b>#{order_id}</b> ကို လက်ခံရရှိပြီးပါပြီ။",
    "banner_set_hint": "🖼 Welcome banner သိမ်းပြီးပါပြီ — `/setbanner` နဲ့ ဖျက်နိုင်ပါတယ်။",
    "banner_sent": "📷 ပုံပို့ပါ။",
    "banner_cleared_alert": "🖼 Banner ဖျက်ပြီးပါပြီ",
    "add_note": "➕ ထည့်မယ်",
    "add_note_sub": "➖ နှုတ်မယ်",
    "zero_notify": "💵 လက်ကောင်းသတ်မှတ်ဖြစ်ပြီး — ကျန်လက်ကောင်း: <b>{balance}</b>",
    "quick_add_notify": "{verb}\n\nကျန်လက်ကောင်း: <b>{balance}</b>",
    "tutorial_none": "ဤထုတ်ကုန်အတွက် tutorial မရှိပါ။",
    "tutorial_open": "📂 Tutorial ဖွင့်ပါမယ်",
    # ops
    "backup_caption": "💾 <b>အလိုအလ် သိမ်းဆည်းမှု</b>\n"
    "🕐 {when}\n"
    "👥 အသုံးပြုသူ: {users}\n"
    "🧾 အော်ဒါ: {orders}",
}

CATALOG: dict[str, dict[str, str]] = {"en": EN, "my": MY}


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #
def available() -> list[str]:
    return list(LANGUAGES)


def is_supported(code: str | None) -> bool:
    return bool(code) and code in LANGUAGES


def get() -> str:
    """The language for the update currently being handled."""
    return _current.get()


def set_lang(code: str) -> str:
    """Activate a language for the rest of this update."""
    resolved = code if is_supported(code) else DEFAULT_LANG
    _current.set(resolved)
    return resolved


def reset() -> None:
    _current.set(DEFAULT_LANG)


def native_name(code: str) -> str:
    return LANGUAGES.get(code, LANGUAGES[DEFAULT_LANG])["native"]


def flag(code: str) -> str:
    return LANGUAGES.get(code, LANGUAGES[DEFAULT_LANG])["flag"]


def t(key: str, default: str | None = None, **values: Any) -> str:
    """Translate `key`, falling back to English then to `default`/the key itself."""
    catalogue = CATALOG.get(get(), EN)
    template = catalogue.get(key) or EN.get(key)
    if template is None:
        return default if default is not None else key
    try:
        return template.format(**values) if values else template
    except (KeyError, IndexError):
        return template


def detect(text: str | None, code: str | None = None) -> str:
    """Guess a language from a Telegram language code or free text."""
    if code:
        primary = code.split("-")[0].lower()
        if is_supported(primary):
            return primary
    if not text:
        return DEFAULT_LANG
    lowered = text.lower()
    myanmar = sum(1 for ch in lowered if "က" <= ch <= "အ" or "၀" <= ch <= "၉")
    return "my" if myanmar >= 3 else DEFAULT_LANG


def missing_keys() -> set[str]:
    """Keys present in English but missing from another catalogue."""
    return {key for key in EN if key not in MY}