require('dotenv').config();
const { Telegraf, Markup } = require('telegraf');
const { runCodexCommand } = require('./src/codex-interface');
const mcpBridge = require('./src/mcp-bridge');
const path = require('path');
const fs = require('fs');

const BOT_TOKEN = process.env.BOT_TOKEN;
const MY_ID = parseInt(process.env.MY_ID);

if (!BOT_TOKEN || isNaN(MY_ID)) {
    console.error('Error: BOT_TOKEN or MY_ID is not set in .env');
    process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);


mcpBridge.start();


const userState = {
    pendingTask: null,
    pendingConfirmation: null,
    pendingMessageSend: null,
    pendingRecipientText: null,
    pendingChatChoice: null
};

function extractMessageBody(text) {
    const match = text.match(/\bdeb\s+yoz\s*[:«"']?\s*(.+)$/i);
    return match ? match[1].trim().replace(/[»"']+$/, '') : null;
}

// Middleware to restrict access
bot.use(async (ctx, next) => {
    if (ctx.from.id !== MY_ID) {
        return ctx.reply('Sizga bu botdan foydalanishga ruxsat yo‘q.');
    }
    // Never run Codex tasks or expose their output in group chats.
    if (ctx.chat?.type !== 'private') return;
    return next();
});

bot.start((ctx) => {
    ctx.reply('Salom! Men Codex agentingizman. Topshiriq yuboring, Codex bajaradi.');
});

bot.help((ctx) => {
    ctx.reply(
        'Buyruqlar:\n' +
        '/start - Botni ishga tushirish\n' +
        '/help - Yordam\n' +
        '/status - Codex va Telethon holatini tekshirish\n' +
        '/cancel - Joriy topshiriqni bekor qilish\n' +
        '/search <nomi> - Telegram chatlarini qidirish\n' +
        '/read <id> - Chatdan xabarlarni o‘qish\n' +
        '/send <id> <matn> - Xabar yuborish (tasdiqlash bilan)'
    );
});

bot.command('status', async (ctx) => {
    let status = '';
    
    try {
        const { execFileSync } = require('child_process');
        const codexJs = process.env.CODEX_ENTRY || path.join(process.env.APPDATA || '', 'npm', 'node_modules', '@openai', 'codex', 'bin', 'codex.js');
        const version = execFileSync(process.execPath, [codexJs, '--version'], { encoding: 'utf8' }).trim();
        status += `✅ Codex ishlayapti: ${version}\n`;
    } catch (e) {
        status += `❌ Codex xatosi: ${e.message}\n`;
    }

    
    try {
        const teleStatus = await mcpBridge.sendRequest('status');
        if (teleStatus.authorized) {
            status += `✅ Telethon (Personal Telegram) ulandi.`;
        } else {
            status += `⚠️ Telethon login qilinmagan. 'python python/telethon_mcp.py --login' ni ishlating.`;
        }
    } catch (e) {
        status += `❌ Telethon xatosi: ${e.message}`;
    }

    ctx.reply(status);
});

bot.command('search', async (ctx) => {
    const query = ctx.message.text.split(' ').slice(1).join(' ');
    if (!query) return ctx.reply('Qidiruv uchun matn yozing. Masalan: /search Abdurahmon');
    
    try {
        const results = await mcpBridge.sendRequest('search_chats', { query });
        if (results.length === 0) return ctx.reply('Hech narsa topilmadi.');
        
        let msg = 'Topilgan chatlar:\n';
        results.forEach(c => {
            msg += `${c.name} (ID: ${c.id})\n`;
        });
        ctx.reply(msg);
    } catch (e) {
        ctx.reply(`Xato: ${e.message}`);
    }
});

bot.command('read', async (ctx) => {
    const chatId = ctx.message.text.split(' ')[1];
    if (!chatId) return ctx.reply('Chat ID sini yozing. Masalan: /read 12345678');
    
    try {
        const messages = await mcpBridge.sendRequest('get_messages', { chat_id: parseInt(chatId) });
        let msg = 'Oxirgi xabarlar:\n';
        messages.reverse().forEach(m => {
            msg += `ID ${m.sender_id}: ${m.text}\n---\n`;
        });
        ctx.reply(msg);
    } catch (e) {
        ctx.reply(`Xato: ${e.message}`);
    }
});

bot.command('send', async (ctx) => {
    const parts = ctx.message.text.split(' ');
    const chatId = parts[1];
    const text = parts.slice(2).join(' ');
    
    if (!chatId || !text) return ctx.reply('Xabar yuborish: /send <id> <matn>');
    
    userState.pendingMessageSend = { chatId, text };
    ctx.reply(
        `Xabarni yuboraymi?\nKimga: ${chatId}\nMatn: ${text}`,
        Markup.keyboard(['Ha, yubor', 'Yo‘q, bekor qil']).oneTime().resize()
    );
});

bot.command('cancel', (ctx) => {
    userState.pendingTask = null;
    userState.pendingConfirmation = null;
    userState.pendingMessageSend = null;
    userState.pendingRecipientText = null;
    userState.pendingChatChoice = null;
    ctx.reply('Amal bekor qilindi.', Markup.removeKeyboard());
});


bot.on('text', async (ctx) => {
    const text = ctx.message.text;

    // Natural language: "Abdulaziz lic topib unga xabar yoz".
    if (userState.pendingChatChoice) {
        const choice = Number.parseInt(text.trim(), 10);
        const matches = userState.pendingChatChoice;
        userState.pendingChatChoice = null;
        if (!Number.isInteger(choice) || choice < 1 || choice > matches.length) {
            return ctx.reply('Tanlov bekor qilindi. Qayta qidirish uchun chat nomini yozing.');
        }
        userState.pendingRecipientText = matches[choice - 1];
        return ctx.reply(`${matches[choice - 1].name} tanlandi. Qanday xabar yozay?`);
    }

    if (userState.pendingRecipientText) {
        const recipient = userState.pendingRecipientText;
        userState.pendingRecipientText = null;
        if (/^(bekor|cancel)$/i.test(text.trim())) return ctx.reply('Amal bekor qilindi.');
        const message = extractMessageBody(text) || text;
        userState.pendingMessageSend = { chatId: String(recipient.id), text: message };
        return ctx.reply(
            `Xabarni yuboraymi?\nKimga: ${recipient.name} (ID: ${recipient.id})\nMatn: ${message}`,
            Markup.keyboard(['Ha, yubor', 'Yo‘q, bekor qil']).oneTime().resize()
        );
    }

    
    if (userState.pendingMessageSend) {
        if (text === 'Ha, yubor') {
            const { chatId, text: msgText } = userState.pendingMessageSend;
            userState.pendingMessageSend = null;
            try {
                await mcpBridge.sendRequest('send_message', { chat_id: chatId, text: msgText, confirm: true });
                ctx.reply('✅ Xabar yuborildi!', Markup.removeKeyboard());
            } catch (e) {
                ctx.reply(`❌ Xato: ${e.message}`, Markup.removeKeyboard());
            }
        } else {
            userState.pendingMessageSend = null;
            ctx.reply('Amal bekor qilindi.', Markup.removeKeyboard());
        }
        return;
    }

    // Accept "Kenayimni topib unga: ... deb yoz" as a Telegram send request.
    // Without this form, it falls through to Codex and can trigger approvals.
    const naturalSend = text.match(/^(.+?)\s+(?:topib|qidirib\s+top(?:ib)?)\s+.+?\b(?:deb\s+yoz|xabar\s+yoz|unga\s+yoz|yozib\s*yubor)\s*[:—-]?\s*(.+)?\s*$/i);
    const directMention = text.match(/(@[\w]{3,})\s+(?:(?:shunga|unga)\s+)?(?:xabar\s+)?yoz\b/i);
    if (naturalSend || directMention) {
        const query = (naturalSend ? naturalSend[1] : directMention[1])
            .replace(/\s+(?:(?:chat|profil)(?:ni|ini|ga|dan)?|lichka(?:siga|ga)?)\s*$/i, '')
            .trim();
        if (!query) return ctx.reply('Qaysi chatni qidiray? Masalan: Abdulaziz lic topib unga xabar yoz.');
        try {
            const results = await mcpBridge.sendRequest('search_chats', { query });
            if (!results.length) return ctx.reply(`“${query}” nomi bilan chat topilmadi.`);
            if (results.length > 1) {
                const shownResults = results.slice(0, 10);
                userState.pendingChatChoice = shownResults;
                const options = shownResults.map((c, i) => `${i + 1}. ${c.name} (ID: ${c.id})`).join('\n');
                return ctx.reply(`Bir nechta chat topildi. Keraklisining raqamini yuboring:\n${options}`);
            }
            const recipient = results[0];
            const message = extractMessageBody(text) || naturalSend?.[2]?.trim() || null;
            if (!message) {
                userState.pendingRecipientText = recipient;
                return ctx.reply(`${recipient.name} (ID: ${recipient.id}) chatini topdim. Qanday xabar yozay?`);
            }
            userState.pendingMessageSend = { chatId: String(recipient.id), text: message };
            return ctx.reply(
                `Xabarni yuboraymi?\nKimga: ${recipient.name} (ID: ${recipient.id})\nMatn: ${message}`,
                Markup.keyboard(['Ha, yubor', 'Yo‘q, bekor qil']).oneTime().resize()
            );
        } catch (error) {
            return ctx.reply(`Telegram chatlarini qidirishda xato: ${error.message}`);
        }
    }

    
    if (userState.pendingConfirmation) {
        if (text === 'Ha' || text === 'Yes') {
            const task = userState.pendingConfirmation.task;
            userState.pendingConfirmation = null;
            executeTask(ctx, task);
        } else {
            userState.pendingConfirmation = null;
            ctx.reply('Amal bekor qilindi.', Markup.removeKeyboard());
        }
        return;
    }

    // Safety check: Detect dangerous keywords
    const dangerousKeywords = ['delete', 'remove', 'rm', 'format', 'destroy', 'o‘chirish'];
    const isDangerous = dangerousKeywords.some(kw => text.toLowerCase().includes(kw));

    if (isDangerous) {
        userState.pendingConfirmation = { task: text };
        return ctx.reply(
            `⚠️ Diqqat! Bu topshiriq xavfli bo‘lishi mumkin: "${text}"\nDavom ettirishni xohlaysizmi?`,
            Markup.keyboard(['Ha', 'Yo‘q']).oneTime().resize()
        );
    }

    executeTask(ctx, text);
});

async function executeTask(ctx, task) {
    const statusMsg = await ctx.reply('⏳ Topshiriq bajarilmoqda...');
    
    try {
        const response = await runCodexCommand(task);

        await ctx.telegram.editMessageText(
            ctx.chat.id,
            statusMsg.message_id,
            null,
            `✅ Natija:\n\n${response || 'Topshiriq bajarildi, lekin matnli natija qaytmadi.'}`
        );
    } catch (error) {
        console.error(error);
        await ctx.telegram.editMessageText(
            ctx.chat.id,
            statusMsg.message_id,
            null,
            `❌ Xato yuz berdi:\n${error.message}`
        );
    }
}

bot.launch().then(() => {
    console.log('Bot muvaffaqiyatli ishga tushdi!');
});


process.once('SIGINT', () => {
    bot.stop('SIGINT');
    mcpBridge.stop();
});
process.once('SIGTERM', () => {
    bot.stop('SIGTERM');
    mcpBridge.stop();
});
