import os
import logging
import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ---------------- Logging ---------------- #
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)

# ---------------- Config ---------------- #
load_dotenv()
TOKEN = os.getenv("TOKEN")  # must be set in Wasmer ENV
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://python-bot.wasmer.app/webhook")

# ---------------- FastAPI App ---------------- #
app = FastAPI()
telegram_app: Application | None = None


# ---------------- Bot Handlers ---------------- #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Hello! I am alive and running on Wasmer with webhook.")


async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"You said: {update.message.text}")


# ---------------- Lifespan Events ---------------- #
@app.on_event("startup")
async def on_startup():
    global telegram_app
    logging.info("🤖 Starting bot in webhook mode…")

    telegram_app = Application.builder().token(TOKEN).build()

    # Add handlers
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Set webhook
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{TOKEN}/setWebhook",
            params={"url": WEBHOOK_URL},
        )
        if resp.status_code == 200:
            logging.info(f"✅ Webhook set: {WEBHOOK_URL}")
        else:
            logging.error(f"❌ Failed to set webhook: {resp.text}")

    logging.info("✅ Application started")


@app.on_event("shutdown")
async def on_shutdown():
    logging.info("🛑 Application shutdown")


# ---------------- Routes ---------------- #
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, telegram_app.bot)
    await telegram_app.process_update(update)
    return {"ok": True}


# Healthcheck endpoints (fixes ExitCode::27 on Wasmer)
@app.api_route("/health", methods=["GET", "HEAD", "POST"])
async def health():
    return {"status": "ok", "message": "healthy ✅"}


@app.api_route("/", methods=["GET", "HEAD", "POST"])
async def home():
    return {"status": "ok", "message": "Telegram bot webhook is running!"}