"""Test the XAI model directly to see what's happening"""
from langchain_xai import ChatXAI
import os


# Test the model directly
model = ChatXAI(
    model="grok-4-1-fast-reasoning-latest",
    max_tokens=100,
    temperature=1.0,
)

print("="*80)
print("TESTING XAI MODEL DIRECTLY")
print("="*80)
print(f"Model name configured: {model.model_name}")

# Make a test call
print("\n" + "="*80)
print("MAKING TEST CALL TO XAI API")
print("="*80)

response = model.invoke("Say hello")
print(f"Response content: {response.content}")

# Check response metadata
print("\n" + "="*80)
print("RESPONSE METADATA:")
print("="*80)
if hasattr(response, 'response_metadata'):
    for key, value in response.response_metadata.items():
        print(f"  {key}: {value}")
    
    if 'model' in response.response_metadata:
        actual_model = response.response_metadata['model']
        print(f"\n{'='*80}")
        print(f"ACTUAL MODEL USED BY API: {actual_model}")
        print(f"{'='*80}")
        
        if actual_model == "grok-4-1-fast-reasoning-latest":
            print("[SUCCESS] API is using the updated model!")
        elif actual_model == "grok-4-fast-reasoning-latest":
            print("[INFO] API returned old model name - this might be an alias")
        else:
            print(f"[INFO] API returned: {actual_model}")

print("="*80)
