import os, asyncio, logging, httpx, contextlib
from typing import Optional
from fastapi import FastAPI
from contextlib import asynccontextmanager
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

# --- Config & Logging --- #
logging.basicConfig(format="%(asctime)s [%(levelname)s] %(message)s", level=logging.INFO)
TOKEN, PROXY = os.getenv("TOKEN"), os.getenv("PROXY", "")
logger = logging.getLogger("bot")

# --- Helpers --- #
async def check_balance(card: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.post(
                "https://transport-api.yerevan.am/api/citizen/card-status/",
                json={"card_number": card}, headers={"Content-Type": "application/json"}
            ); r.raise_for_status()
            return str(r.json()["card_status"]["Subscriptions"][0]["TripsLeft"])
    except Exception:
        logger.exception("Balance check failed")
        return "⚠️ Քարտի վրա ակտիվ տոմս չի գտնվել"

def keyboard(saved: Optional[str]) -> ReplyKeyboardMarkup:
    btns = [[f"💳 Օգտագործել պահված քարտը ({saved})"]] if saved else []
    btns.append(["▶️ ՍԿՍԵԼ"])
    return ReplyKeyboardMarkup(btns, resize_keyboard=True)

# --- Telegram Handlers --- #
async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(
        "👋 Բարի գալուստ!\nՍեղմեք «ՍԿՍԵԼ» նոր քարտ մուտքագրելու համար կամ ընտրեք պահված քարտը՝ մնացորդը ստանալու համար։",
        reply_markup=keyboard(c.user_data.get("card"))
    )

async def ask_card(u: Update, c: ContextTypes.DEFAULT_TYPE):
    txt, saved = u.message.text, c.user_data.get("card")
    if txt.startswith("💳") and saved:
        await u.message.reply_text(f"🔎 Ստուգում եմ քարտի {saved} մնացորդը…")
        res = await check_balance(saved)
        await u.message.reply_text(f"💳 Քարտ՝ {saved}\nՄնացորդ՝ {res}", reply_markup=keyboard(saved))
    elif txt.endswith("ՍԿՍԵԼ"):
        await u.message.reply_text("Մուտքագրեք ձեր 16-անիշ քարտի համարը։", reply_markup=ReplyKeyboardRemove())

async def handle_card(u: Update, c: ContextTypes.DEFAULT_TYPE):
    card = u.message.text.strip()
    if not (card.isdigit() and len(card) == 16):
        return await u.message.reply_text("❌ Մուտքագրեք վավեր 16-անիշ քարտի համար։")
    c.user_data["card"] = card
    await u.message.reply_text("🔎 Ստուգում եմ, խնդրում եմ սպասել…")
    res = await check_balance(card)
    await u.message.reply_text(f"💳 Քարտ՝ {card}\nՄնացորդ՝ {res}", reply_markup=keyboard(card))

async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("ՍԿՍԵԼ|Օգտագործել պահված քարտը"), ask_card))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_card))
    logger.info("🤖 Telegram bot started…")
    await app.run_polling()

# --- FastAPI with Lifespan --- #
@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(run_bot())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError): await task

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root(): return {"message": "Bot is running on Wasmer 🚀"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)