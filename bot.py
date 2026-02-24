import os
import time
import boto3
import httpx
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_BUCKET = os.environ.get("R2_BUCKET")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

app = Client(
    "doramixx_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto"
)

async def get_or_create_series(series_name: str) -> str:
    """Busca série pelo nome ou cria uma nova"""
    async with httpx.AsyncClient() as client:
        # Busca série existente
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/telegram_series?name=ilike.{series_name}&select=id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        series = res.json()

        if series and len(series) > 0:
            print(f"Série encontrada: {series[0]['id']}")
            return series[0]['id']

        # Cria nova série
        chat_id = f"manual-{int(time.time())}"
        res = await client.post(
            f"{SUPABASE_URL}/rest/v1/telegram_series",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            json={"name": series_name, "chat_id": chat_id}
        )
        new_series = res.json()
        series_id = new_series[0]['id']
        print(f"Nova série criada: {series_name} ({series_id})")
        return series_id

async def insert_episode(series_id: str, video_url: str, caption: str):
    """Insere episódio na série"""
    async with httpx.AsyncClient() as client:
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/telegram_episodes?series_id=eq.{series_id}&select=id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        count = len(res.json()) if isinstance(res.json(), list) else 0
        next_order = count + 1

        await client.post(
            f"{SUPABASE_URL}/rest/v1/telegram_episodes",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            json={
                "series_id": series_id,
                "file_id": video_url,
                "caption": caption if caption else f"Episódio {next_order}",
                "episode_order": next_order
            }
        )
        print(f"Episódio {next_order} salvo: {video_url}")

async def update_cover(series_id: str, cover_url: str):
    """Atualiza capa da série"""
    async with httpx.AsyncClient() as client:
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/telegram_series?id=eq.{series_id}",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json"
            },
            json={"cover_url": cover_url}
        )

@app.on_message(filters.photo)
async def handle_photo(client: Client, message: Message):
    """
    Foto com legenda = capa da série
    Formato da legenda: Nome da Série
    """
    caption = message.caption or ""
    series_name = caption.strip()

    if not series_name:
        await message.reply("❌ Envie a foto com o nome da série como legenda!\nEx: Na Palma de Suas Mãos")
        return

    try:
        file_name = f"{int(time.time())}.jpg"
        tmp_path = f"/tmp/{file_name}"
        await message.download(file_name=tmp_path)

        with open(tmp_path, "rb") as f:
            s3.upload_fileobj(f, R2_BUCKET, file_name, ExtraArgs={"ContentType": "image/jpeg"})

        cover_url = f"{R2_PUBLIC_URL}/{file_name}"
        os.remove(tmp_path)

        series_id = await get_or_create_series(series_name)
        await update_cover(series_id, cover_url)

        await message.reply(f"✅ Capa da série '{series_name}' atualizada!")

    except Exception as e:
        print(f"Erro foto: {e}")
        await message.reply(f"❌ Erro: {str(e)}")

@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    """
    Vídeo com legenda = episódio da série
    Formato da legenda: Nome da Série | EP1 (opcional)
    Ex: Na Palma de Suas Mãos | EP1
    Ex: Na Palma de Suas Mãos
    """
    caption = message.caption or ""

    if message.document and not message.document.mime_type.startswith("video/"):
        return

    if not caption.strip():
        await message.reply(
            "❌ Envie o vídeo com o nome da série como legenda!\n\n"
            "Formato: Nome da Série | EP1\n"
            "Ex: Na Palma de Suas Mãos | EP1\n\n"
            "O '| EP1' é opcional."
        )
        return

    # Separa nome da série do episódio
    if "|" in caption:
        parts = caption.split("|", 1)
        series_name = parts[0].strip()
        ep_caption = parts[1].strip()
    else:
        series_name = caption.strip()
        ep_caption = ""

    await message.reply(f"⏳ Processando '{series_name}'...")

    try:
        await message.reply("⬇️ Baixando vídeo...")
        file_name = f"{int(time.time())}.mp4"
        tmp_path = f"/tmp/{file_name}"
        await message.download(file_name=tmp_path)

        await message.reply("⬆️ Enviando pro servidor...")
        with open(tmp_path, "rb") as f:
            s3.upload_fileobj(f, R2_BUCKET, file_name, ExtraArgs={"ContentType": "video/mp4"})

        video_url = f"{R2_PUBLIC_URL}/{file_name}"
        os.remove(tmp_path)

        series_id = await get_or_create_series(series_name)
        await insert_episode(series_id, video_url, ep_caption)

        await message.reply(
            f"✅ Episódio salvo!\n\n"
            f"📺 Série: {series_name}\n"
            f"🎬 Episódio: {ep_caption or 'automático'}\n"
            f"🔗 {video_url}"
        )

    except Exception as e:
        print(f"Erro vídeo: {e}")
        await message.reply(f"❌ Erro: {str(e)}")

print("Bot iniciado! Aguardando vídeos...")
app.run()
