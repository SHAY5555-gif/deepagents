import os, subprocess, json, time

env = os.environ.copy()
# Use environment variable for API key - set PERPLEXITY_API_KEY in your environment
env['PERPLEXITY_API_KEY'] = os.getenv('PERPLEXITY_API_KEY', 'your-api-key-here')
proc = subprocess.Popen([r"C:\\Program Files\\nodejs\\npx.cmd", "-y", "@perplexity-ai/mcp-server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
print('started', proc.pid)
init = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "clientInfo": {"name": "test-client", "version": "0.0.1"},
        "protocolVersion": "1.0.0"
    }
}
msg = json.dumps(init)
wire = f"Content-Length: {len(msg)}\r\n\r\n" + msg
proc.stdin.write(wire)
proc.stdin.flush()
print('sent init')

def read_response():
    header = ''
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            return None
        header += ch
        if header.endswith('\r\n\r\n'):
            break
    length = 0
    for line in header.strip().split('\r\n'):
        if line.lower().startswith('content-length:'):
            length = int(line.split(':', 1)[1].strip())
    body = proc.stdout.read(length)
    return header, body

resp = read_response()
print('response:', resp)
proc.stdin.close()
time.sleep(1)
proc.terminate()
err = proc.stderr.read()
print('stderr:', err)
