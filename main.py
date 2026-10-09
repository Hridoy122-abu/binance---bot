import hashlib
import hmac
import time
import requests
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ========================================================
# ⚠️ আপনার তথ্যসমূহ:
# ========================================================
BINANCE_API_KEY = "NTnPMUWMphNUXnPGIePGYkcvRAzni4X8y4s8Hl1IIHUezQZAJqX8nx7fDAjlZcRx"
BINANCE_SECRET_KEY = "QGXPng0X7M9SHCM046iiGVIxGvJiL18M0wTe8JI2O9S7YwsR9VcEqBCUhxKpOft7"
TELEGRAM_BOT_TOKEN = "8707863162:AAGmwhMJBaFY3KPnMoCQQ6qj6zbdo0071B8"
CHAT_ID = "6495407575"

external_bought_usdt = 0.0
external_spent_bdt = 0.0
processed_orders = set()

def get_binance_usdt_balance():
    """Spot, Funding এবং P2P Ads-এ আটকে থাকা সব USDT ব্যালেন্স মোট হিসাব করবে"""
    total_balance = 0.0
    
    # Spot ও Funding ওয়ালেট
    try:
        endpoint = "https://api.binance.com/api/v3/account"
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        url = f"{endpoint}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        if "balances" in data:
            for item in data["balances"]:
                if item.get("asset") == "USDT":
                    total_balance += float(item.get("free", 0)) + float(item.get("locked", 0))
    except Exception as e:
        print(f"Error spot/funding balance: {e}")

    # P2P Ads
    try:
        endpoint_p2p = "https://api.binance.com/sapi/v1/c2c/ads/listUserAds"
        timestamp = int(time.time() * 1000)
        query_string = f"timestamp={timestamp}"
        signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
        
        url = f"{endpoint_p2p}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
        
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        if "data" in data and isinstance(data["data"], list):
            for ad in data["data"]:
                if ad.get("asset") == "USDT":
                    total_balance += float(ad.get("surplusAmount", 0))
    except Exception as e:
        print(f"Error P2P Ads balance: {e}")

    return total_balance

def fetch_p2p_orders(trade_type=None):
    endpoint = "https://api.binance.com/sapi/v1/c2c/orderMatch/listUserOrderHistory"
    end_time = int(time.time() * 1000)
    start_time = end_time - (30 * 24 * 60 * 60 * 1000)
    
    query_string = f"startTimestamp={start_time}&endTimestamp={end_time}&timestamp={end_time}"
    if trade_type:
        query_string += f"&tradeType={trade_type}"
    
    signature = hmac.new(BINANCE_SECRET_KEY.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()
    
    url = f"{endpoint}?{query_string}&signature={signature}"
    headers = {"X-MBX-APIKEY": BINANCE_API_KEY}
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        return res.json().get("data", [])
    except Exception as e:
        print(f"Error fetching P2P orders: {e}")
        return []

async def add_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global external_bought_usdt, external_spent_bdt
    try:
        raw_usdt = float(context.args[0])
        total_bdt = float(context.args[1])
        
        fee_usdt = raw_usdt * (0.20 / 100)
        net_usdt = raw_usdt - fee_usdt
        
        external_bought_usdt += net_usdt
        external_spent_bdt += total_bdt
        
        live_binance_usdt = get_binance_usdt_balance()
        total_available = live_binance_usdt + external_bought_usdt
        
        msg = (
            f"✅ **নতুন ডিপোজিট রেকর্ড করা হয়েছে!**\n\n"
            f"📥 Raw Deposited USDT: {raw_usdt:.2f} USDT\n"
            f"🔻 Fee Deducted (0.20%): {fee_usdt:.4f} USDT\n"
            f"➕ Net Added USDT: {net_usdt:.4f} USDT\n"
            f"💵 Total Spent BDT: {total_bdt:.2f} BDT\n"
            f"-----------------------------\n"
            f"🏦 Binance Live Wallet USDT: {live_binance_usdt:.2f} USDT\n"
            f"💼 Total Effective Stock USDT: {total_available:.2f} USDT"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
    except (IndexError, ValueError):
        await update.message.reply_text(
            "⚠️ ভুল ফরম্যাট! সঠিকভাবে লিখুন:\n`/add_buy <USDT> <মোট BDT>`\n\nউদাহরণ: `/add_buy 100 12000`",
            parse_mode="Markdown"
        )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    live_binance_usdt = get_binance_usdt_balance()
    total_usdt = live_binance_usdt + external_bought_usdt
    
    msg = (
        f"📊 **লাইভ বাইনান্স ওয়ালেট ও ইনভেন্টরি স্টেটাস:**\n\n"
        f"🏦 **Binance Live Wallet USDT:** {live_binance_usdt:.2f} USDT\n"
        f"📥 Extra Tracked USDT: {external_bought_usdt:.2f} USDT\n"
        f"💼 **Total Combined USDT:** {total_usdt:.2f} USDT\n"
        f"💰 Total Tracked Cost: {external_spent_bdt:.2f} BDT"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def wallet_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ ওয়ালেট নাম্বার দিন।\n\nউদাহরণ: `/wallet 01712345678`", parse_mode="Markdown")
        return

    wallet_query = context.args[0].strip()
    orders = fetch_p2p_orders()
    
    total_orders = 0
    completed_orders = 0
    total_bdt_in = 0.0
    total_usdt_traded = 0.0
    
    for order in orders:
        pay_method = str(order.get("payMethodName", ""))
        counterparty = str(order.get("counterPartNickName", ""))
        order_num = str(order.get("orderNumber", ""))
        
        if wallet_query.lower() in pay_method.lower() or wallet_query.lower() in counterparty.lower() or wallet_query in order_num:
            total_orders += 1
            if order.get("orderStatus") == "COMPLETED":
                completed_orders += 1
                total_bdt_in += float(order.get("totalPrice", 0))
                total_usdt_traded += float(order.get("amount", 0))

    if total_orders == 0:
        await update.message.reply_text(f"🔍 ওয়ালেট/আইডি: `{wallet_query}` দিয়ে কোনো লেনদেন পাওয়া যায়নি।", parse_mode="Markdown")
        return

    msg = (
        f"📱 **ওয়ালেট লেনদেন স্টেটাস**\n"
        f"🏷️ **Target:** `{wallet_query}`\n"
        f"-----------------------------\n"
        f"📦 মোট অর্ডার: {total_orders} টি\n"
        f"✅ সফল অর্ডার: {completed_orders} টি\n"
        f"💵 মোট প্রাপ্ত টাকা: {total_bdt_in:.2f} BDT\n"
        f"🪙 ট্রেডকৃত USDT: {total_usdt_traded:.2f} USDT"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def check_orders_task(app: Application):
    bot = app.bot
    initial_orders = fetch_p2p_orders(trade_type="SELL")
    for order in initial_orders:
        processed_orders.add(order.get("orderNumber"))
        
    while True:
        orders = fetch_p2p_orders(trade_type="SELL")
        for order in orders:
            order_id = order.get("orderNumber")
            if order_id not in processed_orders and order.get("orderStatus") == "COMPLETED":
                amount = float(order.get("amount", 0))
                sell_rate = float(order.get("price", 0))
                base_revenue = float(order.get("totalPrice", 0))
                
                buyer_fee = base_revenue * 0.015
                total_received = base_revenue + buyer_fee
                
                msg = (
                    f"✅ **নতুন P2P সেল কমপ্লিট!**\n\n"
                    f"🆔 Order ID: `{order_id}`\n"
                    f"💵 Sold Amount: {amount} USDT\n"
                    f"🏷️ Sell Rate: {sell_rate:.2f} BDT\n\n"
                    f"💵 Base Amount: {base_revenue:.2f} BDT\n"
                    f"➕ Buyer Fee (1.5%): {buyer_fee:.2f} BDT\n"
                    f"💳 **Total Received:** {total_received:.2f} BDT"
                )
                await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="Markdown")
                processed_orders.add(order_id)
                
        await asyncio.sleep(15)

async def post_init(app: Application):
    asyncio.create_task(check_orders_task(app))

def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("add_buy", add_buy))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("wallet", wallet_summary))
    print("Render Binance Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
