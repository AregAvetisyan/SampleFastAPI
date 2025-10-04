import os, logging, httpx, atexit
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# --- Logging ---
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
atexit.register(lambda: logging.info("🔥 Process is exiting"))
load_dotenv()
TOKEN, WEBHOOK_URL = os.getenv("TOKEN"), os.getenv("WEBHOOK_URL")
if not TOKEN or not WEBHOOK_URL: raise ValueError("TOKEN and WEBHOOK_URL must be set")

async def check_balance(card: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post("https://transport-api.yerevan.am/api/citizen/card-status/",
                             json={"card_number": card}, headers={"Content-Type": "application/json"})
            r.raise_for_status()
            return str(r.json()["card_status"]["Subscriptions"][0]["TripsLeft"])
    except Exception: logging.exception("Balance check failed"); return "⚠️ Քարտի վրա ակտիվ տոմս չի գտնվել"

def kb(saved: str | None) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        ([[f"💳 Օգտագործել պահված քարտը ({saved})"]] if saved else []) + [["▶️ ՍԿՍԵԼ"]],
        resize_keyboard=True
    )

async def start(update: Update, ctx) -> None:
    await update.message.reply_text("👋 Բարի գալուստ!\nՍեղմեք «ՍԿՍԵԼ» կամ ընտրեք պահված քարտը։",
                                    reply_markup=kb(ctx.user_data.get("card")))

async def ask(update: Update, ctx) -> None:
    t, saved = update.message.text, ctx.user_data.get("card")
    if t.startswith("💳") and saved:
        await update.message.reply_text(f"🔎 Ստուգում եմ քարտի {saved} մնացորդը…")
        await update.message.reply_text(f"💳 Քարտ՝ {saved}\nՄնացորդ՝ {await check_balance(saved)}",
                                        reply_markup=kb(saved))
    elif "ՍԿՍԵԼ" in t: await update.message.reply_text("Մուտքագրեք ձեր 16-անիշ քարտի համարը։", reply_markup=ReplyKeyboardRemove())

async def handle_card(update: Update, ctx) -> None:
    card = update.message.text.strip()
    if not (card.isdigit() and len(card) == 16): await update.message.reply_text("❌ Մուտքագրեք վավեր 16-անիշ քարտի համար։"); return
    ctx.user_data["card"] = card
    await update.message.reply_text("🔎 Ստուգում եմ, խնդրում եմ սպասել…")
    await update.message.reply_text(f"💳 Քարտ՝ {card}\nՄնացորդ՝ {await check_balance(card)}", reply_markup=kb(card))

bot_app = Application.builder().token(TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(MessageHandler(filters.Regex("ՍԿՍԵԼ|Օգտագործել պահված քարտը"), ask))
bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card))

@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.info("🤖 Starting bot in webhook mode…")
    await bot_app.initialize()
    await bot_app.start()
    await bot_app.bot.set_webhook(WEBHOOK_URL)
    try:
        yield
    finally:
        logging.info("🛑 Stopping bot…")
        await bot_app.bot.delete_webhook()
        await bot_app.stop()
        await bot_app.shutdown()

app = FastAPI(lifespan=lifespan)

@app.post("/webhook")
async def webhook(r: Request):
    await bot_app.update_queue.put(Update.de_json(await r.json(), bot_app.bot))
    return {"ok": True}

@app.get("/")
async def root(): return {"message": "Bot is running 🚀"}

if __name__ == "__main__" and not os.getenv("WASMER"):
    import uvicorn; uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)