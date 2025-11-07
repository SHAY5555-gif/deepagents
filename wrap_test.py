import subprocess, time

proc = subprocess.Popen(
    ['python.exe', 'C:\\Users\\yesha\\.codex\\mcp_docker_wrapper.py'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)

# Wait for server to start
for _ in range(20):
    line = proc.stderr.readline()
    if not line:
        break
    print('[stderr]', line.strip())
    if 'Start stdio server' in line:
        break

init_msg = '{"jsonrpc":"2.0","id":0,"method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{}}}'
proc.stdin.write(init_msg + '\r\n')
proc.stdin.flush()

for _ in range(10):
    line = proc.stdout.readline()
    if not line:
        break
    print('[stdout]', line.strip())

proc.terminate()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()
