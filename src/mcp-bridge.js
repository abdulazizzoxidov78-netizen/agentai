const { spawn } = require('child_process');
const path = require('path');
const EventEmitter = require('events');
const { StringDecoder } = require('string_decoder');

class McpBridge extends EventEmitter {
    constructor() {
        super();
        this.pythonProcess = null;
        this.requestId = 0;
        this.pendingRequests = new Map();
        this.stdoutBuffer = '';
        this.stdoutDecoder = new StringDecoder('utf8');
    }

    start() {
        if (this.pythonProcess) return;
        const pythonPath = process.env.PYTHON_PATH || 'python';
        const scriptPath = path.join(__dirname, '..', 'python', 'telethon_mcp.py');
        
        this.pythonProcess = spawn(pythonPath, [scriptPath], {
            stdio: ['pipe', 'pipe', 'inherit'],
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', PYTHONUTF8: '1' }
        });

        this.pythonProcess.stdout.on('data', (data) => {
            this.stdoutBuffer += this.stdoutDecoder.write(data);
            const lines = this.stdoutBuffer.split('\n');
            this.stdoutBuffer = lines.pop();
            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const response = JSON.parse(line);
                    if (response.id && this.pendingRequests.has(response.id)) {
                        const { resolve, reject } = this.pendingRequests.get(response.id);
                        if (response.error) reject(new Error(response.error));
                        else resolve(response.result);
                        this.pendingRequests.delete(response.id);
                    } else if (response.event === 'incoming_private_message') {
                        this.emit('incoming_private_message', response);
                    } else if (response.event === 'error' || response.error) {
                        console.error('MCP Error:', response.error);
                    }
                } catch (e) {
                    console.log('MCP non-JSON stdout:', line);
                }
            }
        });

        this.pythonProcess.on('close', (code) => {
            console.log(`MCP process closed with code ${code}`);
            this.pythonProcess = null;
            this.stdoutBuffer = '';
            this.stdoutDecoder = new StringDecoder('utf8');
            for (const { reject } of this.pendingRequests.values()) {
                reject(new Error(`Telethon jarayoni yopildi (kod: ${code})`));
            }
            this.pendingRequests.clear();
        });
        this.pythonProcess.on('error', (error) => {
            console.error('Python ishga tushmadi:', error.message);
        });
    }

    async sendRequest(method, params = {}) {
        if (!this.pythonProcess) {
            throw new Error('MCP bridge not started');
        }

        const id = ++this.requestId;
        return new Promise((resolve, reject) => {
            this.pendingRequests.set(id, { resolve, reject });
            this.pythonProcess.stdin.write(JSON.stringify({ id, method, params }) + '\n', (error) => {
                if (error) {
                    this.pendingRequests.delete(id);
                    reject(error);
                }
            });
        });
    }

    stop() {
        if (this.pythonProcess) {
            const child = this.pythonProcess;
            child.stdin.end();

            const forceStop = setTimeout(() => {
                if (this.pythonProcess === child) child.kill();
            }, 2000);
            forceStop.unref();
            child.once('close', () => clearTimeout(forceStop));
        }
    }
}

module.exports = new McpBridge();
