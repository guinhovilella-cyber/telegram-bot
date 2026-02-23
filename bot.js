const TelegramBot = require('node-telegram-bot-api');
const fs = require('fs');
const path = require('path');
const https = require('https');

const TOKEN = process.env.BOT_TOKEN;
const TARGET_GROUP = process.env.TARGET_GROUP; // chat_id do grupo DORAMIXX

const bot = new TelegramBot(TOKEN, { polling: true });

console.log('Bot iniciado! Aguardando vídeos...');

bot.on('video', async (msg) => {
  const chatId = msg.chat.id;
  const video = msg.video;
  const caption = msg.caption || '';

  console.log(`Vídeo recebido de ${chatId}, file_id: ${video.file_id}`);

  try {
    // Pega o link do arquivo
    const file = await bot.getFile(video.file_id);
    const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${file.file_path}`;
    const fileName = path.basename(file.file_path);

    console.log(`Baixando arquivo: ${fileName}`);

    // Baixa o arquivo temporariamente
    const tmpPath = `/tmp/${fileName}`;
    await downloadFile(fileUrl, tmpPath);

    console.log(`Arquivo baixado! Enviando pro grupo...`);

    // Envia como novo arquivo pro grupo destino
    await bot.sendVideo(TARGET_GROUP, fs.createReadStream(tmpPath), {
      caption: caption,
    });

    console.log(`Vídeo enviado pro grupo ${TARGET_GROUP} com sucesso!`);

    // Remove o arquivo temporário
    fs.unlinkSync(tmpPath);

    // Confirma pro remetente
    await bot.sendMessage(chatId, '✅ Vídeo enviado pro grupo com sucesso!');

  } catch (err) {
    console.error('Erro:', err);
    await bot.sendMessage(chatId, '❌ Erro ao processar o vídeo: ' + err.message);
  }
});

bot.on('document', async (msg) => {
  const chatId = msg.chat.id;
  const doc = msg.document;
  const caption = msg.caption || '';

  // Verifica se é um vídeo enviado como documento
  if (!doc.mime_type || !doc.mime_type.startsWith('video/')) return;

  console.log(`Documento de vídeo recebido, file_id: ${doc.file_id}`);

  try {
    const file = await bot.getFile(doc.file_id);
    const fileUrl = `https://api.telegram.org/file/bot${TOKEN}/${file.file_path}`;
    const fileName = path.basename(file.file_path);

    const tmpPath = `/tmp/${fileName}`;
    await downloadFile(fileUrl, tmpPath);

    await bot.sendVideo(TARGET_GROUP, fs.createReadStream(tmpPath), {
      caption: caption,
    });

    fs.unlinkSync(tmpPath);
    await bot.sendMessage(chatId, '✅ Vídeo enviado pro grupo com sucesso!');

  } catch (err) {
    console.error('Erro:', err);
    await bot.sendMessage(chatId, '❌ Erro: ' + err.message);
  }
});

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, (response) => {
      response.pipe(file);
      file.on('finish', () => {
        file.close(resolve);
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => {});
      reject(err);
    });
  });
}
