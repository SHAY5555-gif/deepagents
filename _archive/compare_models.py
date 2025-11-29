"""Compare both model names to see if they're aliases"""
from langchain_xai import ChatXAI

# Test old name
model_old = ChatXAI(model="grok-4-fast-reasoning-latest", max_tokens=50)
response_old = model_old.invoke("Say hello")
print("OLD MODEL NAME: grok-4-fast-reasoning-latest")
print(f"API returned model_name: {response_old.response_metadata.get('model_name')}")
print(f"System fingerprint: {response_old.response_metadata.get('system_fingerprint')}")

print("\n" + "="*80 + "\n")

# Test new name  
model_new = ChatXAI(model="grok-4-1-fast-reasoning-latest", max_tokens=50)
response_new = model_new.invoke("Say hello")
print("NEW MODEL NAME: grok-4-1-fast-reasoning-latest")
print(f"API returned model_name: {response_new.response_metadata.get('model_name')}")
print(f"System fingerprint: {response_new.response_metadata.get('system_fingerprint')}")

print("\n" + "="*80)
if response_old.response_metadata.get('model_name') == response_new.response_metadata.get('model_name'):
    print("[CONCLUSION] Both names point to THE SAME MODEL!")
    print("XAI automatically redirects 'grok-4-fast-reasoning-latest' to the newest version")
else:
    print("[CONCLUSION] These are DIFFERENT models")
print("="*80)
