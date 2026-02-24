import asyncio
import os
import boto3
from pyrogram import Client, filters
from pyrogram.types import Message

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TARGET_GROUP = int(os.environ.get("TARGET_GROUP"))
R2_ACCOUNT_ID = os.environ.get("R2_ACCOUNT_ID")
R2_ACCESS_KEY = os.environ.get("R2_ACCESS_KEY")
R2_SECRET_KEY = os.environ.get("R2_SECRET_KEY")
R2_BUCKET = os.environ.get("R2_BUCKET")
R2_PUBLIC_URL = os.environ.get("R2_PUBLIC_URL")

# Cliente do bot
app = Client(
    "doramixx_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Cliente R2
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
    aws_access_key_id=R2_ACCESS_KEY,
    aws_secret_access_key=R2_SECRET_KEY,
    region_name="auto"
)

async def upload_to_r2(file_path: str, file_name: str) -> str:
    print(f"Fazendo upload de {file_name} pro R2...")
    with open(file_path, "rb") as f:
        s3.upload_fileobj(f, R2_BUCKET, file_name, ExtraArgs={"ContentType": "video/mp4"})
    url = f"{R2_PUBLIC_URL}/{file_name}"
    print(f"Upload concluído: {url}")
    return url

@app.on_message(filters.video | filters.document)
async def handle_video(client: Client, message: Message):
    chat_id = message.chat.id
    caption = message.caption or ""

    # Verifica se é vídeo
    if message.document and not message.document.mime_type.startswith("video/"):
        return

    await message.reply("⏳ Processando vídeo...")

    try:
        # Baixa o vídeo sem limite de tamanho
        await message.reply("⬇️ Baixando vídeo... pode demorar um pouco")
        
        import time
        file_name = f"{int(time.time())}.mp4"
        tmp_path = f"/tmp/{file_name}"
        
        await message.download(file_name=tmp_path)
        print(f"Download concluído: {tmp_path}")

        # Upload pro R2
        await message.reply("⬆️ Enviando pro servidor...")
        video_url = await upload_to_r2(tmp_path, file_name)

        # Envia a URL pro grupo destino
        await client.send_message(
            TARGET_GROUP,
            f"VIDEO_URL:{video_url}\nCAPTION:{caption}"
        )

        # Remove arquivo temporário
        os.remove(tmp_path)

        await message.reply(f"✅ Vídeo enviado com sucesso!\n\n🔗 {video_url}")

    except Exception as e:
        print(f"Erro: {e}")
        await message.reply(f"❌ Erro: {str(e)}")

print("Bot iniciado!")
app.run()
