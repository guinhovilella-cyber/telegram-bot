const TelegramBot = require('node-telegram-bot-api');
const { S3Client, PutObjectCommand } = require('@aws-sdk/client-s3');
const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const TOKEN = process.env.BOT_TOKEN;
const TARGET_GROUP = process.env.TARGET_GROUP;
const R2_ACCOUNT_ID = process.env.R2_ACCOUNT_ID;
const R2_ACCESS_KEY = process.env.R2_ACCESS_KEY;
const R2_SECRET_KEY = process.env.R2_SECRET_KEY;
const R2_BUCKET = process.env.R2_BUCKET;
const R2_PUBLIC_URL = process.env.R2_PUBLIC_URL;

const bot = new TelegramBot(TOKEN, { polling: true });

const s3 = new S3Client({
  region: 'auto',
  endpoint: `https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
  credentials: {
    accessKeyId: R2_ACCESS_KEY,
    secretAccessKey: R2_SECRET_KEY,
  },
});

console.log('Bot iniciado! Aguardando vídeos...');

async function processVideo(msg, fileId, caption) {
  const chatId = msg.chat.id;

  try {
    await bot.sendMessage(chatId, '⏳ Processando vídeo...');

    // Pega o link do arquivo via Telegram API
    const file = await bot.getFile(fileId);
    const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${file.file_path}`;
    const fileName = `${Date.now()}_${path.basename(file.file_path)}`;
    const tmpPath = `/tmp/${fileName}`;

    console.log(`Baixando: ${fileUrl}`);
    await bot.sendMessage(chatId, '⬇️ Baixando vídeo...');
    await downloadFile(fileUrl, tmpPath);

    console.log(`Fazendo upload pro R2: ${fileName}`);
    await bot.sendMessage(chatId, '⬆️ Enviando pro servidor...');

    const fileBuffer = fs.readFileSync(tmpPath);
    await s3.send(new PutObjectCommand({
      Bucket: R2_BUCKET,
      Key: fileName,
      Body: fileBuffer,
      ContentType: 'video/mp4',
    }));

    const videoUrl = `${R2_PUBLIC_URL}/${fileName}`;
    console.log(`URL pública: ${videoUrl}`);

    // Envia a URL pro grupo destino como mensagem
    await bot.sendMessage(TARGET_GROUP, videoUrl, {
      caption: caption || '',
    });

    // Também envia o vídeo com a URL no caption pro webhook capturar
    await bot.sendMessage(TARGET_GROUP, `VIDEO_URL:${videoUrl}\nCAPTION:${caption || ''}`);

    fs.unlinkSync(tmpPath);

    await bot.sendMessage(chatId, `✅ Vídeo enviado com sucesso!\n\n🔗 URL: ${videoUrl}`);

  } catch (err) {
    console.error('Erro:', err);
    await bot.sendMessage(chatId, '❌ Erro: ' + err.message);
  }
}

bot.on('video', async (msg) => {
  await processVideo(msg, msg.video.file_id, msg.caption);
});

bot.on('document', async (msg) => {
  if (!msg.document.mime_type?.startsWith('video/')) return;
  await processVideo(msg, msg.document.file_id, msg.caption);
});

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    const protocol = url.startsWith('https') ? https : http;
    protocol.get(url, (response) => {
      if (response.statusCode === 302 || response.statusCode === 301) {
        file.close();
        downloadFile(response.headers.location, dest).then(resolve).catch(reject);
        return;
      }
      response.pipe(file);
      file.on('finish', () => file.close(resolve));
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}
