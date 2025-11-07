import subprocess, json, time, threading, queue, sys

proc = subprocess.Popen(
    ['docker', 'mcp', 'gateway', 'run'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

stdout_queue = queue.Queue()


def reader(stream, name):
    for line in stream:
        stdout_queue.put((name, line))


threading.Thread(target=reader, args=(proc.stdout, 'stdout'), daemon=True).start()
threading.Thread(target=reader, args=(proc.stderr, 'stderr'), daemon=True).start()

# Wait a bit for the server to be ready
time.sleep(8)

init_msg = json.dumps(
    {
        'jsonrpc': '2.0',
        'id': 0,
        'method': 'initialize',
        'params': {
            'protocolVersion': '0.1.0',
            'capabilities': {},
        },
    }
) + '\n'
proc.stdin.write(init_msg)
proc.stdin.flush()

response = None
start = time.time()
while time.time() - start < 20:
    try:
        name, line = stdout_queue.get(timeout=1)
        line_stripped = line.strip()
        print(f'[{name}] {line_stripped}')
        if '"jsonrpc"' in line and '"id":0' in line:
            response = line_stripped
            break
    except queue.Empty:
        pass

if proc.stdin:
    proc.stdin.close()
proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

print('RESPONSE:', response)
