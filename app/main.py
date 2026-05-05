import asyncio
import hashlib
import hmac
import logging

from fastapi import FastAPI, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import PlainTextResponse

from app.config import FACEBOOK_APP_SECRET, FACEBOOK_VERIFY_TOKEN, HUMAN_HANDOFF_KEYWORD
from app.claude_client import get_ai_response, should_handoff_to_human
from app.database import init_db, get_conversation, save_message, set_needs_human
from app.messenger import send_message, send_typing_on, send_typing_off

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="Messenger AI Chatbot")


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("Baza de date initializata.")


# ---------- Webhook verification ----------

@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == FACEBOOK_VERIFY_TOKEN:
        logger.info("Webhook verificat cu succes.")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Token invalid")


# ---------- Receive messages ----------

@app.post("/webhook")
async def receive_webhook(request: Request, background_tasks: BackgroundTasks):
    # Verifica semnatura Facebook
    signature = request.headers.get("X-Hub-Signature-256", "")
    body = await request.body()

    if FACEBOOK_APP_SECRET:
        expected = "sha256=" + hmac.new(
            FACEBOOK_APP_SECRET.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(status_code=403, detail="Semnatura invalida")

    import json
    data = json.loads(body)

    if data.get("object") != "page":
        return {"status": "ignored"}

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            sender_id = event.get("sender", {}).get("id")
            message = event.get("message", {})
            text = message.get("text")

            if not sender_id or not text:
                continue

            background_tasks.add_task(handle_message, sender_id, text)

    return {"status": "ok"}


# ---------- Core message handler ----------

async def handle_message(sender_id: str, text: str):
    try:
        conv = get_conversation(sender_id)

        # Daca asteapta un om, nu mai raspunde automat
        if conv["needs_human"]:
            logger.info(f"[{sender_id}] Conversatie preluata de om, bot inactiv.")
            return

        # Verifica daca clientul cere un om
        if should_handoff_to_human(text, HUMAN_HANDOFF_KEYWORD):
            set_needs_human(sender_id, True)
            await send_message(
                sender_id,
                "Inteleg, transfer conversatia catre un coleg care te va contacta in cel mai scurt timp. Multumim pentru rabdare!"
            )
            logger.info(f"[{sender_id}] Escaladare catre om.")
            return

        # Salveaza mesajul clientului
        save_message(sender_id, "user", text)

        # Genereaza raspuns
        await send_typing_on(sender_id)
        conv = get_conversation(sender_id)
        response_parts = await asyncio.to_thread(get_ai_response, conv["messages"])
        await send_typing_off(sender_id)

        # Trimite fiecare parte ca mesaj separat, cu typing intre ele
        full_response = " ".join(response_parts)
        save_message(sender_id, "assistant", full_response)

        for i, part in enumerate(response_parts):
            await send_message(sender_id, part)
            if i < len(response_parts) - 1:
                await asyncio.sleep(1.2)
                await send_typing_on(sender_id)
                await asyncio.sleep(1.5)
                await send_typing_off(sender_id)

        logger.info(f"[{sender_id}] {len(response_parts)} mesaje trimise.")

    except Exception as e:
        logger.error(f"[{sender_id}] Eroare: {e}", exc_info=True)
        await send_message(sender_id, "Momentan intampinam o problema tehnica. Revenim imediat!")


# ---------- Admin endpoints ----------

@app.get("/conversations")
async def list_conversations():
    from app.database import get_all_conversations
    return get_all_conversations()


@app.post("/conversations/{sender_id}/resolve")
async def resolve_conversation(sender_id: str):
    set_needs_human(sender_id, False)
    return {"status": "resolved", "sender_id": sender_id}


@app.get("/health")
async def health():
    return {"status": "ok"}
