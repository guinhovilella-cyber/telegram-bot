import asyncio
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
SERIES_ID = os.environ.get("SERIES_ID")  # ID da série na tabela telegram_series

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

async def insert_episode(video_url: str, caption: str):
    async with httpx.AsyncClient() as client:
        # Pega a contagem atual de episódios DA SÉRIE
        res = await client.get(
            f"{SUPABASE_URL}/rest/v1/telegram_episodes?series_id=eq.{SERIES_ID}&select=id",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
        )
        
        episodes = res.json()
        count = len(episodes) if isinstance(episodes, list) else 0
        next_order = count + 1
        
        print(f"Episódios existentes: {count}, próximo order: {next_order}")

        # Insere o episódio
        insert_res = await client.post(
            f"{SUPABASE_URL}/rest/v1/telegram_episodes",
            headers={
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}",
                "Content-Type": "application/json",
                "Prefer": "return=representation"
            },
            json={
                "series_id": SERIES_ID,
                "file_id": video_url,
                "caption": caption,
                "episode_order": next_order
            }
        )
        print(f"Episódio salvo no Supabase: {video_url} (order: {next_order})")
@app.on_message(filters.photo)
async def handle_photo(client: Client, message: Message):
    """Captura foto e atualiza capa da série"""
    try:
        file_name = f"{int(time.time())}.jpg"
        tmp_path = f"/tmp/{file_name}"
        await message.download(file_name=tmp_path)

        with open(tmp_path, "rb") as f:
            s3.upload_fileobj(f, R2_BUCKET, file_name, ExtraArgs={"ContentType": "image/jpeg"})

        cover_url = f"{R2_PUBLIC_URL}/{file_name}"
        os.remove(tmp_path)

        async with httpx.AsyncClient() as http:
            await http.patch(
                f"{SUPABASE_URL}/rest/v1/telegram_series?id=eq.{SERIES_ID}",
                headers={
                    "apikey": SUPABASE_KEY,
                    "Authorization": f"Bearer {SUPABASE_KEY}",
                    "Content-Type": "application/json"
                },
                json={"cover_url": cover_url}
            )

        await message.reply(f"✅ Capa atualizada!")

    except Exception as e:
        await message.reply(f"❌ Erro: {str(e)}")
@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    chat_id = message.chat.id
    caption = message.caption or ""

    if message.document and not message.document.mime_type.startswith("video/"):
        return

    await message.reply("⏳ Processando vídeo...")

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

        await insert_episode(video_url, caption)
        await message.reply(f"✅ Vídeo salvo com sucesso!\n\n🔗 {video_url}")

    except Exception as e:
        print(f"Erro: {e}")
        await message.reply(f"❌ Erro: {str(e)}")

print("Bot iniciado!")
app.run()
