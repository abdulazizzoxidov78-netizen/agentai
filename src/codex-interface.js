const { spawn } = require('child_process');
const fs = require('fs/promises');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
require('dotenv').config();

const PROJECT_PATH = path.resolve(process.env.PROJECT_PATH || process.cwd());
const CODEX_ENTRY = process.env.CODEX_ENTRY || path.join(
    process.env.APPDATA || '', 'npm', 'node_modules', '@openai', 'codex', 'bin', 'codex.js'
);

async function runCodexCommand(message) {
    await fs.access(CODEX_ENTRY);
    const outputPath = path.join(os.tmpdir(), `codex-telegram-${crypto.randomUUID()}.txt`);
    try {
        return await new Promise((resolve, reject) => {
            const child = spawn(process.execPath, [
                CODEX_ENTRY, 'exec', '--json', '--skip-git-repo-check',
                '--cd', PROJECT_PATH, '--output-last-message', outputPath, '-'
            ], { cwd: PROJECT_PATH, env: process.env, stdio: ['pipe', 'ignore', 'pipe'] });
            let errorOutput = '';
            child.stderr.setEncoding('utf8');
            child.stderr.on('data', (chunk) => { errorOutput += chunk; });
            child.on('error', reject);
            child.on('close', async (code) => {
                if (code !== 0) {
                    reject(new Error(`Codex tugadi (kod ${code}): ${errorOutput.slice(-3000)}`));
                    return;
                }
                try {
                    resolve((await fs.readFile(outputPath, 'utf8')).trim());
                } catch (error) {
                    reject(new Error(`Codex javobini o‘qib bo‘lmadi: ${error.message}`));
                }
            });
            child.stdin.end(message);
        });
    } finally {
        await fs.rm(outputPath, { force: true });
    }
}

module.exports = { runCodexCommand };
