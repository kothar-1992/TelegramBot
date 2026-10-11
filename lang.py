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
    "catalog_header": "🗂 <b>Categories</b>\n\n"
    "👇 Tap a category — each button shows how many products it holds.",
    "catalog_empty": "🛍 <b>Catalogue</b>\n\nThere are no products yet.",
    "cat_header": "{emoji} <b>{name}</b>\n"
    "{count} available · page {page}/{pages}\n\n"
    "👇 Tap a product to see the details.",
    "cat_empty": "{emoji} <b>{name}</b>\n\nThere are no products here yet.",
    "n_items": "{count} items",
    "n_items_one": "1 item",
    "price_tbd_short": "💬 on request",
    "sold_out_short": "sold out",
    "back_to_cat": "⬅️ {name}",
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
    "prod_no_category_warn": "⚠️ This product is in <b>no category</b>, so customers will never "
    "see it in the shop. Add the category name to the caption exactly as written: <code>{names}</code>.",
    # /status
    "status_title": "🔧 <b>Shop status</b>",
    "status_products": "📦 Products: <b>{live}</b> live · <b>{total}</b> total",
    "status_cats": "🗂 Categories: <b>{cats}</b>",
    "status_orphans": "🚫 <b>{count}</b> products belong to no category and are invisible to customers",
    "status_traffic": "👥 Users: <b>{users}</b> · 🧾 Orders: <b>{orders}</b>",
    "status_save_ok": "💾 Last saved to Telegram: <b>{when}</b>",
    "status_save_never": "⚠️ The catalogue has never been saved — a deploy will erase it",
    "status_save_dirty": "⚠️ Unsaved changes since the last snapshot",
    "status_save_off": "⚠️ Backups are OFF — set BACKUP_ENABLED=true on Render",
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
    "addproduct_prompt_into": "🛍 <b>Adding to {category}</b>\n\n"
    "<b>Step 1</b> — send the product photo.\n\n"
    "<b>Step 2</b> — send a caption with the photo:\n\n"
    "<code>Name | Price | Stock | Warranty | Tutorial</code>\n\n"
    "The category is already set, so leave it out of the caption.",
    "addproduct_bad_caption": "⚠️ Bad caption — use <code>Name | Price</code> to start.",
    "addcat_prompt": "🗂 <b>New category</b>\n\n"
    "Send the name. An emoji in front is optional:\n\n"
    "<code>/addcat CapCut</code>      → {emoji} CapCut\n"
    "<code>/addcat \U0001f3ac CapCut</code>   → \U0001f3ac CapCut\n\n"
    "The emoji is what colours the buttons customers see.",
    "addcat_need_name": "{emoji} Got it — now send just the <b>name</b> for this category.",
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
    "demo_done": "✅ <b>Demo products added</b>\n\n"
    "🗂 Categories: <b>{cats}</b> · 🛍 Products: <b>{products}</b>\n"
    "💰 Your balance: <b>{balance}</b>\n\n"
    "{note}:\n{summary}\n\n"
    "🛍 Browse them under <b>🛍 Products</b>.\n"
    "🧹 Remove them all with <code>/demo clear</code>",
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
    "adm_cat_header": "{emoji} <b>{name}</b>\n"
    "🆔 id: {id} · 🛍 {total} products · {active} live",
    "adm_cat_empty": "{emoji} <b>{name}</b>  (id: {id})\n\n"
    "No products here yet — add the first one below.",
    "admin_prod_new": "➕ Add product",
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
    # common
    "back": "⬅️ နောက်ပြန်",
    "main_menu": "🏠 ပင်မစာမျက်နှာ",
    "cancel": "🚫 ပယ်ဖျက်",
    "close": "✖️ ပိတ်",
    "prev": "◀️",
    "next": "▶️",
    "page": "📄 {page}/{pages}",
    "yes": "✅ အတည်ပြု",
    "no": "❌ ပယ်ဖျက်",
    "not_found": "⚠️ မတွေ့ပါဘူး။",
    "try_again": "⚠️ တစ်ခုခု မှားသွားပါတယ်။ ထပ်စမ်းကြည့်ပါ။",
    # main menu
    "welcome": "👋 {shop} ကို ကြိုဆိုပါတယ်",
    "balance_line": "💰 သင့်လက်ကျန်ငွေ — {balance}",
    "menu_products": "🛍 ပစ္စည်းများ",
    "menu_balance": "💰 လက်ကျန်ငွေ",
    "menu_orders": "🧾 အော်ဒါမှတ်တမ်း",
    "menu_support": "💬 Live Chat",
    "menu_help": "📖 အသုံးပြုနည်း",
    "menu_admin": "🛠 Admin Panel",
    "menu_language": "🌐 ဘာသာစကား",
    "menu_topup": "💸 ငွေဖြည့်",
    "lang_hint": "⌨️ အောက်က <b>🏠 Menu</b> ခလုတ်ကို နှိပ်လိုက်ရင် အချိန်မရွေး ဒီမှာ ပြန်ရောက်ပါမယ်။",
    # language
    "lang_pick": "🌐 <b>ဘာသာစကား ရွေးပါ</b>\n\nအောက်က ခလုတ်ကို နှိပ်ပါ — နောက်မှ ဘယ်တော့မဆို ပြောင်းလို့ရပါတယ်။",
    "lang_changed": "✅ ဘာသာစကားကို <b>{name}</b> အဖြစ် ပြောင်းပြီးပါပြီ။",
    "lang_admin_set": "✅ Default ဘာသာစကားကို <b>{name}</b> အဖြစ် သတ်မှတ်ပြီးပါပြီ။",
    "lang_current": "🌐 လက်ရှိ ဘာသာစကား — <b>{name}</b>",
    # catalogue
    "catalog_header": "🗂 <b>အမျိုးအစားများ</b>\n\n"
    "👇 အမျိုးအစား တစ်ခုကို နှိပ်ပါ — ခလုတ်တွေမှာ ပစ္စည်း ဘယ်နှစ်ခုရှိလဲ ပြပါမယ်။",
    "catalog_empty": "🛍 <b>ပစ္စည်းများ</b>\n\nအခုတော့ ပစ္စည်း ဘာမှ မရှိသေးပါဘူး။",
    "cat_header": "{emoji} <b>{name}</b>\n"
    "ပစ္စည်း {count} ခု · စာမျက်နှာ {page}/{pages}\n\n"
    "👇 အသေးစိတ် ကြည့်ချင်ရင် ပစ္စည်းကို နှိပ်ပါ။",
    "cat_empty": "{emoji} <b>{name}</b>\n\nဒီအမျိုးအစားထဲမှာ ပစ္စည်း မရှိသေးပါဘူး။",
    "n_items": "{count} ခု",
    "n_items_one": "၁ ခု",
    "price_tbd_short": "💬 စျေးမသတ်မှတ်ရသေး",
    "sold_out_short": "ကုန်ခမ်း",
    "back_to_cat": "⬅️ {name}",
    # product
    "product_stock": "📦 လက်ကျန် — {stock}",
    "product_stock_inf": "📦 လက်ကျန် — ကန့်သတ်ချက် မရှိ",
    "product_warranty": "🛡 အာမခံချက် — {warranty}",
    "product_tutorial": "🔗 {url}",
    "buy": "🛒 ဝယ်မယ်",
    "buy_or": "🛒 အခုပဲ ဝယ်မယ်",
    "ask_price": "📞 စျေးနှုန်း မေးမယ်",
    "ask_price_title": "စျေးနှုန်း မေးမြန်းရန်",
    "price_tbd": "💬 စျေးနှုန်း မသတ်မှတ်ရသေးပါ",
    "sold_out_title": "🔴 ကုန်ခမ်းနေပါပြီ",
    # quantity / confirm
    "qty_header": "🔽 <b>{name}</b>\n",
    "qty_unit": "💵 တစ်ခုစာ စျေးနှုန်း — <b>{price}</b>",
    "qty_selected": "🔢 အရေအတွက် — <b>{qty}</b>",
    "qty_total": "💵 စုစုပေါင်း — <b>{total}</b>",
    "qty_step": "🔢 {qty}",
    "buy_total": "🚚 ဝယ်မယ် · {total}",
    "confirm_title": "📋 <b>အော်ဒါ အတည်ပြုချက်</b>\n",
    "confirm_product": "📦 {name}",
    "confirm_qty": "🔢 အရေအတွက် — <b>{qty}</b>",
    "confirm_total": "💵 စုစုပေါင်း — <b>{total}</b>",
    "confirm_wallet": "💳 လက်ကျန်ငွေ — <b>{balance}</b>",
    "confirm_short": "⚠️ လိုနေသေးတာ — <b>{short}</b>",
    "confirm_yes": "✅ အော်ဒါ အတည်ပြုမယ်",
    "topup_short": "💳 {amount} ဖြည့်မယ်",
    # top-up
    "topup_title": "💸 <b>လက်ကျန်ငွေ ဖြည့်ရန်</b>\n\n",
    "topup_step1": "<b>အဆင့် ၁</b> — ဖြည့်ချင်တဲ့ ပမာဏကို အောက်က စာရိုက်ကွက်မှာ ရိုက်ပါ (ဥပမာ — 50000)။",
    "topup_step2": "<b>အဆင့် ၂</b> — ငွေလွှဲပြီးရင် ငွေလွှဲပြေစာ (receipt) ကို <b>ပုံ</b> အနေနဲ့ ပို့ပါ။",
    "topup_your_id": "👤 သင့် ID — <code>{user_id}</code> ({handle})",
    "topup_amount_ok": "✅ <b>{amount}</b> အတွက် စောင့်နေပါပြီ။\n\n<b>အဆင့် ၂</b> — ငွေလွှဲပြေစာ ပုံကို ပို့ပါ။",
    "topup_amount_bad": "⚠️ နံပါတ် ရိုက်ပေးပါ (ဥပမာ — 50000)။",
    "topup_need_start": "📸 «💰 ငွေဖြည့်» ကို အရင်နှိပ်ပြီးမှ ငွေလွှဲပြေစာ ပုံ ပို့ပါ။",
    "methods_title": "🎯 <b>အတိအကျ ငွေဖြည့်ခြင်း</b>\n\n🧾 ဒီအော်ဒါအတွက် <b>{amount}</b> အတိအကျ လွှဲပေးပါ။",
    "methods_pick": "👇 ဘယ်နည်းလမ်းနဲ့ လွှဲမလဲ ရွေးပါ",
    "methods_empty": "ℹ️ ငွေလွှဲနည်းလမ်း မရှိသေးပါဘူး — Admin က <code>/addpay</code> နဲ့ ထည့်နိုင်ပါတယ်။",
    "details_title": "🎯 <b>အတိအကျ ငွေဖြည့်ခြင်း</b>",
    "details_pay": "{emoji} <b>{name} ဆီသို့ လွှဲပေးပါ</b>\n",
    "details_number": "🏦 အကောင့်နံပါတ် — <code>{number}</code>",
    "details_name": "👤 အကောင့်အမည် — <b>{name}</b>",
    "details_note": "📝 {note}",
    "details_receipt": "💬 လွှဲပြီးရင် ငွေလွှဲပြေစာ (receipt) ပုံ ပို့ပေးပါ",
    "details_ref": "🔖 Reference — <code>{code}</code>",
    "copy_number": "📋 အကောင့်နံပါတ် ကူး",
    "copy_name": "📋 အမည် ကူး",
    "copy_ref": "🔢 Reference ကူး",
    "copied_number": "🔢 အကောင့်နံပါတ်\n{number}",
    "copied_name": "👤 အမည်\n{name}",
    "copied_ref": "🔖 Reference\n{code}",
    # review
    "review_title": "🕐 <b>ငွေဖြည့်တင်းမှု စစ်ဆေးနေဆဲ</b>",
    "review_ref": "🔖 Reference — <code>#{id}</code>{extra}",
    "review_amount": "💵 ပမာဏ — <b>{amount}</b>",
    "review_balance": "💰 လက်ကျန်ငွေ — <b>{balance}</b>",
    "status": "📌 အခြေအနေ — {status}",
    "review_waiting": "⏳ Admin က စစ်ဆေးနေပါတယ် — <b>{minutes} မိနစ်</b>အတွင်း စောင့်ပေးပါ။\n"
    "အချိန်ကျော်သွားရင် အလိုအလျောက် ပယ်ဖျက်ပါမယ်။",
    "review_status_btn": "🔄 အခြေအနေ ကြည့်မယ်",
    "review_cancel_btn": "🚫 ပယ်ဖျက်မယ်",
    "review_pending": "🟡 စစ်ဆေးနေဆဲ",
    "review_approved": "🟢 အတည်ပြုပြီး",
    "review_rejected": "🔴 ပယ်ဖျက်ပြီး",
    "review_expired": "⏰ အချိန်ကျော် ပယ်ဖျက်ပြီး",
    "review_already": "ℹ️ ဒီတောင်းဆိုမှုကို ဖြေဆိုပြီးသားပါ။",
    "review_still_pending": "🟡 စစ်ဆေးနေဆဲ — မိနစ် {minutes} လောက် ကျန်ပါသေးတယ်",
    "review_cancelled": "🚫 ပယ်ဖျက်လိုက်ပါပြီ။",
    "approve_title": "✅ <b>ငွေဖြည့်တင်းမှု အတည်ပြုပြီးပါပြီ</b>\n\n🔖 Reference — <code>#{id}</code>",
    "approve_amount": "💵 ထည့်ပေးလိုက်တာ — {amount}",
    "approve_balance": "💰 <b>လက်ကျန်ငွေ — {balance}</b>\n\n🛍 အခု ပစ္စည်းတွေ ဝယ်လို့ရပါပြီ။",
    "reject_title": "❌ <b>ငွေဖြည့်တင်းမှု ပယ်ဖျက်လိုက်ပါပြီ</b>\n\n🔖 Reference — <code>#{id}</code>\nပို့ထားတဲ့ ပြေစာ မမှန်လို့ပါ။",
    "expire_title": "⏰ <b>ငွေဖြည့်တင်းမှု အချိန်ကုန်သွားပါပြီ</b>\n\n"
    "{minutes} မိနစ်အတွင်း ဘယ်သူမှ မစစ်ပေးနိုင်လို့ ပယ်ဖျက်လိုက်ပါတယ်။\n"
    "💰 လက်ကျန်ငွေ မပြောင်းလဲပါဘူး — ထပ်ပို့ပေးပါ။",
    # balance
    "balance_title": "💰 <b>လက်ကျန်ငွေ</b>\n\n",
    "balance_name": "👤 အမည် — {name}",
    "balance_id": "🆔 ID — <code>{user_id}</code>",
    "balance_handle": "🕐 @{handle}",
    "balance_amount": "💵 ရရှိနိုင်တဲ့ ငွေ — <b>{balance}</b>",
    # orders
    "orders_title": "🧾 <b>အော်ဒါမှတ်တမ်း</b>\n",
    "orders_empty": "🧾 <b>အော်ဒါမှတ်တမ်း</b>\n\nအော်ဒါ မရှိသေးပါဘူး။",
    "orders_item": "<code>#{id}</code> — {product}\n   x{qty} · {total} · {status}",
    "orders_buy": "🛍 ပစ္စည်းများ",
    "status_pending": "🟡 စစ်ဆေးနေဆဲ",
    "status_approved": "🟢 အတည်ပြုပြီး",
    "status_delivered": "🔵 ပေးပြီး",
    "status_rejected": "🔴 ပယ်ဖျက်ပြီး",
    "order_done": "✅ <b>အော်ဒါ #{id}</b>\n{name}\n🧮 {qty} · {total}\n💰 လက်ကျန်ငွေ — {balance}\n\nAdmin က အမြန် ပေးပို့ပေးပါမယ်။",
    "order_approved": "✅ <b>အော်ဒါ အတည်ပြုပြီးပါပြီ</b>\n\n🔖 <code>#{id}</code> — {product}\n🧮 x{qty} · {total}\n"
    "👤 {handle} အတွက်\n\nAdmin က ပေးပို့ပေးပါမယ်။ လက်ခံရရှိပြီးရင် အောက်က ခလုတ်ကို နှိပ်ပေးပါ။",
    "order_received": "✅ <b>လက်ခံရရှိပါပြီ</b>\n\nကျေးဇူးတင်ပါတယ်! 🙏 Admin ကို အကြောင်းကြားလိုက်ပါပြီ။",
    "order_no_product": "—",
    # support
    "support_title": "💬 <b>Live Chat</b>\n\n{handle} ကို စာပို့လိုက်ရင် စောစေပြန်ဆက်ပေးပါမယ်။",
    "support_body": "@{handle} ကို စာပို့ပေးပါ — မကြာခင် ပြန်ဆက်ပေးပါမယ်။",
    "support_no_handle": "💬 <b>Live Chat</b>\n\n",
    "support_no_body": "ကူညီပေးဖို့ Admin ကို ဆက်သွယ်ပါ။",
    # help
    "help_title": "📖 <b>အသုံးပြုနည်း</b>\n\n",
    "help_1": "1️⃣ <b>🛍 ပစ္စည်းများ</b> — အမျိုးအစား ရွေးပြီး ကြည့်လို့ရပါတယ်။",
    "help_2": "2️⃣ <b>🛒 ဝယ်မယ်</b> — အရေအတွက် ရွေးပြီး အတည်ပြုလိုက်ရင် လက်ကျန်ငွေကနေ ချပေးပါမယ်။",
    "help_3": "3️⃣ <b>💰 ငွေဖြည့်</b> — ငွေလွှဲပြေစာ ပုံ ပို့လိုက်ရင် Admin က အတည်ပြုပေးပါမယ်။",
    "help_4": "4️⃣ <b>⬅️ နောက်ပြန် / 🏠 ပင်မစာမျက်နှာ</b> — သွားလာလှည့်လည်ဖို့ပါ။",
    "help_5": "5️⃣ <b>🌐 ဘာသာစကား</b> — English / မြန်မာ ကူးပြောင်းလို့ရပါတယ်။",
    # errors
    "err_admin_only": "🔒 ဒီ command က Admin အတွက်ပါပဲ။",
    "err_unknown_cmd": "⚠️ မသိတဲ့ command ပါ။ /menu ကို စမ်းကြည့်ပါ။",
    "err_no_order": "⚠️ အော်ဒါ မတွေ့ပါဘူး။",
    "err_already_done": "ℹ️ ဒီတောင်းဆိုမှုကို ဖြေဆိုပြီးသားပါ။",
    "err_sold_out": "⚠️ ဒီပစ္စည်း ကုန်ခမ်းနေပါပြီ။",
    "err_price_tbd": "📞 ဒီပစ္စည်းက စျေးနှုန်း မသတ်မှတ်ရသေးလို့ အော်ဒါ မယူလို့ရပါဘူး။",
    "err_low_balance": "💰 လက်ကျန်ငွေ မလုံလောက်ပါဘူး။ {amount} လိုပါတယ်။",
    "err_too_big": "⚠️ တစ်ခါတည်း အော်ဒါ {limit} ခုပဲ ယူလို့ရပါတယ်။",
    "err_no_tutorial": "ဒီပစ္စည်းအတွက် Tutorial မရှိပါဘူး။",
    # uploads
    "upload_reject": "🚫 <b>ဖိုင် လက်မခံပါဘူး</b>\n\n"
    "ငွေလွှဲပြေစာ (receipt) ကို <b>ပုံ (Photo)</b> အနေနဲ့ပဲ ပို့ပါ။\n"
    "📎 Document/ဖိုင် အနေနဲ့ ပို့ရင် လုံးဝ ငြင်းပစ်ပါမယ်။",
    "upload_reject_tip": "📸 ပုံ ပို့ချင်ရင် 🎨 icon ကို နှိပ်ပြီး screenshot ရိုက်ပါ။",
    "upload_too_big": "⚠️ ပုံ ကြီးလွန်းပါတယ်။ {limit} MB အောက် ပုံနဲ့ ထပ်ပို့ပါ။",
    "upload_fake": "⚠️ ဒါက ပုံ မဟုတ်ပါဘူး။ ပုံအစစ်ကိုပဲ လက်ခံပါတယ်။",
    # admin
    "admin_title": "🛠 <b>Admin Panel</b>\n\nဆိုင်ရဲ့ အရောင်းအဝယ်ကို ဒီကနေ စီမံနိုင်ပါတယ်။",
    "admin_cat_new": "➕ အမျိုးအစား အသစ်",
    "admin_cat_list": "🗂 အမျိုးအစားများ",
    "admin_prod_list": "🛍 ပစ္စည်းများ",
    "admin_orders": "📥 အော်ဒါများ",
    "admin_users": "👥 အသုံးပြုသူများ",
    "admin_banner": "🖼 ကြိုဆိုစာ Banner",
    "admin_stats": "📊 စာရင်းအင်း",
    "admin_lang": "🌐 Default ဘာသာစကား",
    "admin_pending": "📥 <b>အော်ဒါများ</b>\n\nစောင့်နေတဲ့ အော်ဒါ မရှိပါဘူး။",
    "admin_pending_item": "🔔 <b>အော်ဒါ အသစ်</b>\n\n<code>#{id}</code> — {product}\n🧮 x{qty} · <b>{total}</b>\n"
    "👤 {name} ({handle})\n🆔 <code>{user_id}</code>",
    "admin_topup_item": "💸 <b>ငွေလွှဲပြေစာ (receipt)</b>\n\n🔖 <code>#{id}</code>\n👤 {name}\n🆔 <code>{user_id}</code>\n"
    "💵 ပမာဏ — <b>{amount}</b>{note}\n\n⏳ <b>{minutes} မိနစ်</b>အတွင်း စစ်ပါ — မစစ်ရင် အလိုအလျောက် ပယ်ဖျက်ပါမယ်။",
    "admin_yes": "✅ အတည်ပြု",
    "admin_no": "❌ ပယ်ဖျက်",
    "admin_delivered": "🔵 ပေးပြီးလို့ မှတ်မယ်",
    "admin_done": "🔵 <b>အော်ဒါ #{id}</b> — ပေးပြီးပါပြီ။",
    "admin_user_card": "👤 <b>{name}</b>\n🆔 <code>{user_id}</code>\n🕐 @{handle}\n"
    "💰 လက်ကျန်ငွေ — <b>{balance}</b>\n🧾 အော်ဒါ {orders} ခု",
    "admin_users_title": "👥 <b>အသုံးပြုသူများ</b>\n",
    "admin_zero": "💵 Balance ကို 0 လုပ်မယ်",
    "stats_title": "📊 <b>စာရင်းအင်း</b>\n\n",
    "stats_users": "👥 အသုံးပြုသူ — <b>{users}</b>",
    "stats_cats": "🗂 အမျိုးအစား — <b>{cats}</b>",
    "stats_products": "🛍 ပစ္စည်း — <b>{active}</b> ({hidden} ခု ဖျောက်ထား)",
    "stats_orders": "🧾 အော်ဒါ — <b>{orders}</b>",
    "stats_revenue": "💵 ဝင်ငွေ — <b>{revenue}</b>",
    "prod_saved": "✅ <b>ပစ္စည်း သိမ်းပြီးပါပြီ</b>\n\n<code>#{id}</code> — {name}\n💵 {price}\n"
    "📦 လက်ကျန် — {stock}\n🗂 {category}",
    "prod_no_category": "အမျိုးအစား မရှိ",
    "prod_no_category_warn": "⚠️ ဒီပစ္စည်းမှာ <b>အမျိုးအစား မရှိဘူး</b> — ဝယ်သူတွေကို ဆိုင်ထဲမှာ ဘယ်တော့မှ မပြပါဘူး။ "
    "Caption ထဲမှာ အမျိုးအစား အမည်ကို အတိအကျ ရေးထည့်ပါ — <code>{names}</code>။",
    # /status
    "status_title": "🔧 <b>ဆိုင် အခြေအနေ</b>",
    "status_products": "📦 ပစ္စည်း — <b>{live}</b> ခု ရောင်းနေ · စုစုပေါင်း <b>{total}</b> ခု",
    "status_cats": "🗂 အမျိုးအစား — <b>{cats}</b>",
    "status_orphans": "🚫 အမျိုးအစား မရှိတဲ့ ပစ္စည်း <b>{count}</b> ခု ရှိနေပြီး ဝယ်သူတွေ မမြင်နိုင်ပါဘူး",
    "status_traffic": "👥 အသုံးပြုသူ — <b>{users}</b> · 🧾 အော်ဒါ — <b>{orders}</b>",
    "status_save_ok": "💾 Telegram ထဲ နောက်ဆုံး သိမ်းခဲ့တာ — <b>{when}</b>",
    "status_save_never": "⚠️ ဒေတာကို အခါမှ မသိမ်းဖူးဘူး — deploy လုပ်ရင် ပျောက်သွားမယ်",
    "status_save_dirty": "⚠️ နောက်ဆုံး သိမ်းခဲ့တာကတည်းက ပြောင်းလဲမှုတွေ မသိမ်းရသေးဘူး",
    "status_save_off": "⚠️ Backup ပိတ်ထားပါတယ် — Render မှာ BACKUP_ENABLED=true ထည့်ပါ",
    "prod_toggle": "{state} <b>{name}</b>",
    "prod_on": "🟢 ရောင်းနေ",
    "prod_off": "🔴 ဖျောက်ထား",
    "prod_deleted": "🗑 ဖျက်ပြီးပါပြီ။",
    "prod_none": "🛍 ပစ္စည်း မရှိသေးပါဘူး။ /addproduct နဲ့ ထည့်ပါ။",
    "cat_deleted": "🗑 အမျိုးအစား <code>{id}</code> ကို ဖျက်ပြီးပါပြီ။",
    "cat_none": "🗂 အမျိုးအစား မရှိသေးပါဘူး — <code>/addcat</code> နဲ့ ထည့်ပါ။",
    "addproduct_prompt": "🛍 <b>ပစ္စည်း အသစ် ထည့်ခြင်း</b>\n\n"
    "<b>အဆင့် ၁</b> — ပစ္စည်းပုံကို ပို့ပါ။\n\n"
    "<b>အဆင့် ၂</b> — ပုံနဲ့အတူ Caption ထည့်ပို့ပါ —\n\n"
    "<code>အမည် | စျေးနှုန်း | အမျိုးအစား | လက်ကျန် | အာမခံ | Tutorial</code>\n"
    "<code>USDT TRC20 | 65000 | Crypto | 10 | 30 မိနစ် | https://t.me/x</code>\n\n"
    "လိုအပ်တဲ့ field တွေပဲ ရေးပါ — ကျန်တာတွေ ချန်လို့ရပါတယ်။\n"
    "ပထမလိုင်းအောက်က စာအားလုံးကိုတော့ description အနေနဲ့ သိမ်းပေးပါမယ်။",
    "addproduct_caption_prompt": "📝 <b>အဆင့် ၂</b> — ပုံနဲ့အတူ Caption ထည့်ပို့ပါ —\n\n"
    "<code>အမည် | စျေးနှုန်း | အမျိုးအစား | လက်ကျန် | အာမခံ | Tutorial</code>",
    "addproduct_prompt_into": "🛍 <b>{category} ထဲ ထည့်နေပါတယ်</b>\n\n"
    "<b>အဆင့် ၁</b> — ပစ္စည်းပုံကို ပို့ပါ။\n\n"
    "<b>အဆင့် ၂</b> — ပုံနဲ့အတူ Caption ထည့်ပို့ပါ —\n\n"
    "<code>အမည် | စျေးနှုန်း | လက်ကျန် | အာမခံ | Tutorial</code>\n\n"
    "အမျိုးအစားကတော့ သတ်မှတ်ပြီးသားမို့ Caption ထဲ မထည့်ရဘူး။",
    "addproduct_bad_caption": "⚠️ Caption မမှန်ပါဘူး — <code>အမည် | စျေးနှုန်း</code> နဲ့ စပါ။",
    "addcat_prompt": "🗂 <b>အမျိုးအစား အသစ်</b>\n\n"
    "အမည်ကို ရိုက်ပို့ပါ — ရှေ့မှာ emoji ထည့်လည်း ထည့်လို့ရပါတယ် —\n\n"
    "<code>/addcat CapCut</code>      → {emoji} CapCut\n"
    "<code>/addcat \U0001f3ac CapCut</code>   → \U0001f3ac CapCut\n\n"
    "အဲဒီ emoji ကပဲ ဝယ်သူတွေ မြင်ရမယ့် ခလုတ်တွေရဲ့ အရောင်အသွင်ပါ။",
    "addcat_need_name": "{emoji} ရပါပြီ — ဒီအမျိုးအစားရဲ့ <b>အမည်</b>ကိုပဲ ပို့ပါ။",
    "addcat_saved": "✅ အမျိုးအစား ထည့်ပြီးပါပြီ — <code>{id}</code> · {emoji} {name}",
    "delcat_usage": "⚠️ <code>/delcat &lt;id&gt;</code> နဲ့ သုံးပါ။",
    "delproduct_usage": "⚠️ <code>/delproduct &lt;id&gt;</code> နဲ့ သုံးပါ။",
    "give_usage": "⚠️ <code>/give &lt;user_id&gt; &lt;amount&gt;</code> နဲ့ သုံးပါ။",
    "give_done": "✅ <code>{user_id}</code> ရဲ့ လက်ကျန်ငွေ — {balance}",
    "balance_usage": "⚠️ <code>/balance &lt;user_id&gt;</code> နဲ့ သုံးပါ။",
    "id_reply": "🆔 သင့် Telegram ID — <code>{user_id}</code>\n👤 {name}\n🔑 Admin — {admin}",
    "id_yes": "ဟုတ်ကဲ့",
    "id_no": "မဟုတ်ဘူး",
    "broadcast_prompt": "📢 ပို့ချင်တဲ့ မက်ဆေ့ကို ရိုက်ပါ။",
    "broadcast_done": "📢 ပို့ပြီးပါပြီ — ရောက်တာ {ok} · မရောက်တာ {failed}",
    "broadcast_empty": "⚠️ ပို့ချင်တဲ့ မက်ဆေ့ကို ရိုက်ပါ။",
    "setbanner_prompt": "🖼 ကြိုဆိုစာ banner ပုံကို ပို့ပါ။",
    "setbanner_saved": "🖼 ကြိုဆိုစာ banner သိမ်းပြီးပါပြီ။",
    "setbanner_cleared": "🖼 ကြိုဆိုစာ banner ဖျက်ပြီးပါပြီ။",
    "setname_usage": "⚠️ <code>/setname &lt;အမည်&gt;</code> နဲ့ သုံးပါ။",
    "setname_done": "✅ ဆိုင်အမည် — {name}",
    "demo_done": "✅ <b>Demo ပစ္စည်းတွေ ထည့်ပြီးပါပြီ</b>\n\n"
    "🗂 အမျိုးအစား <b>{cats}</b> · 🛍 ပစ္စည်း <b>{products}</b>\n"
    "💰 သင့်လက်ကျန်ငွေ — <b>{balance}</b>\n\n"
    "{note} —\n{summary}\n\n"
    "🛍 <b>🛍 ပစ္စည်းများ</b> အောက်မှာ ကြည့်လို့ရပါတယ်။\n"
    "🧹 အားလုံး ဖျက်ချင်ရင် <code>/demo clear</code>",
    "demo_exists": "ℹ️ Demo data ရှိနေပြီသားပါ — အရင် <code>/demo clear</code> နဲ့ ဖျက်ပါ။",
    "demo_cleared": "🗑 Demo ပစ္စည်း <b>{count}</b> ခု ဖျက်ပြီးပါပြီ။",
    "demo_nothing": "ℹ️ Demo data မရှိပါဘူး။ အရင် <code>/demo</code> နဲ့ စပါ။",
    "paymethods_title": "💳 <b>ငွေလွှဲနည်းလမ်းများ</b>\n",
    "paymethods_none": "💳 ငွေလွှဲနည်းလမ်း မရှိသေးပါဘူး။",
    "paymethods_item": "{flag} <code>{id}</code> · {emoji} {name}{number}{holder}",
    "addpay_usage": "⚠️ <code>/addpay &lt;emoji&gt; &lt;name&gt; | &lt;အကောင့်နံပါတ်&gt; | &lt;အမည်&gt;</code> နဲ့ သုံးပါ။",
    "addpay_done": "✅ ထည့်ပြီးပါပြီ — <code>{id}</code> · {emoji} {name}",
    "delpay_usage": "⚠️ <code>/delpay &lt;id&gt;</code> နဲ့ သုံးပါ။",
    "admin_only_cmd": "🔒 Admin အတွက်ပါ။",
    "lang_set_user": "✅ ဘာသာစကား <b>{name}</b> အဖြစ် ပြောင်းပြီးပါပြီ။",
    # misc
    "tutorial_msg": "📂 <b>{name}</b>\n🔗 {url}",
    "share_msg": "🛍 {name}",
    "archived": "—",
    # admin extras
    "cat_list_title": "🗂 <b>အမျိုးအစားများ</b>\n",
    "cat_list_item": "<code>{id}</code> · {emoji} {name} — {count} ခု",
    "adm_cat_header": "{emoji} <b>{name}</b>\n"
    "🆔 id — {id} · 🛍 ပစ္စည်း {total} ခု · {active} ခု ရောင်းနေ",
    "adm_cat_empty": "{emoji} <b>{name}</b>  (id — {id})\n\n"
    "ဒီထဲမှာ ပစ္စည်း မရှိသေးပါဘူး — အောက်က ခလုတ်နဲ့ ပစ္စည်း အသစ် ထည့်ပါ။",
    "admin_prod_new": "➕ ပစ္စည်း ထည့်မယ်",
    "prod_list_title": "🛍 <b>ပစ္စည်းများ</b>\n",
    "prod_admin_price": "💵 စျေးနှုန်း — <b>{price}</b>",
    "prod_admin_stock": "📦 လက်ကျန် — {stock}",
    "prod_admin_cat": "🗂 {category}",
    "prod_hide_btn": "🔴 ဖျောက်",
    "prod_show_btn": "🟢 ပြပြန်",
    "prod_del_btn": "🗑 ဖျက်",
    "prod_toggled": "{state} — {name}",
    "toggle_usage": "⚠️ <code>/toggle &lt;id&gt;</code> နဲ့ သုံးပါ။",
    "cat_del_btn": "🗑 ဖျက်",
    "paymethods_edit": "ပြင်ရန် — <code>/addpay &lt;emoji&gt; &lt;name&gt; | &lt;အကောင့်နံပါတ်&gt; | &lt;အမည်&gt;</code>",
    "paymethods_del": "ဖျက်ရန် — <code>/delpay &lt;id&gt;</code>",
    "err_user_not_found": "⚠️ အဲဒီ user ကို မတွေ့ပါဘူး။",
    "broadcast_sending": "📢 ပို့နေပါတယ်...",
    "give_notify": "💰 လက်ကျန်ငွေ အသစ် — {balance}",
    "order_refund": "❌ <b>အော်ဒါ ပယ်ဖျက်လိုက်ပါပြီ</b>\n\n🔖 <code>#{id}</code>\n\n"
    "💰 ပြန်အမ်းငွေ — {total}\n💵 လက်ကျန်ငွေ — {balance}",
    "deliver_btn": "✅ လက်ခံရရှိပြီ",
    "deliver_thanks": "✅ ကျေးဇူးတင်ပါတယ်! 🙏",
    "deliver_notify": "✅ <code>{user_id}</code> က အော်ဒါ <b>#{order_id}</b> လက်ခံရရှိပြီးပါပြီ။",
    "banner_set_hint": "🖼 ကြိုဆိုစာ banner သိမ်းပြီးပါပြီ — /setbanner နဲ့ ဖျက်နိုင်ပါတယ်။",
    "banner_sent": "📷 ပုံပို့ပါ။",
    "banner_cleared_alert": "🖼 Banner ဖျက်ပြီးပါပြီ",
    "add_note": "➕ ထည့်",
    "add_note_sub": "➖ နှုတ်",
    "zero_notify": "💵 လက်ကျန်ငွေ ပြန်ချိုးလိုက်ပါပြီ — ကျန်ရှိ <b>{balance}</b>",
    "quick_add_notify": "{verb}\n\nလက်ကျန်ငွေ — <b>{balance}</b>",
    "tutorial_none": "📂 ဒီပစ္စည်းအတွက် Tutorial မရှိပါဘူး။",
    "tutorial_open": "📂 Tutorial ဖွင့်ပေးပါမယ်",
    # ops
    "backup_caption": "💾 <b>အလိုအလျောက် Backup</b>\n"
    "🕐 {when}\n"
    "👥 အသုံးပြုသူ — {users}\n"
    "🧾 အော်ဒါ — {orders}",
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
