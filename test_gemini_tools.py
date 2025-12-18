"""Quick test to verify tool conversion works."""
import sys
import os

# Load .env file
from dotenv import load_dotenv
load_dotenv()

# Force reload of the module
if 'agents.gemini3_flash_brightdata_genius' in sys.modules:
    del sys.modules['agents.gemini3_flash_brightdata_genius']

# Now import
from agents.gemini3_flash_brightdata_genius import (
    ChatGemini3Flash,
    get_all_tools,
    get_gemini3_flash_model
)

def test_tool_conversion():
    print("Testing tool conversion...")

    # Get all tools
    tools = get_all_tools()
    print(f"Got {len(tools)} tools")

    for t in tools:
        print(f"  - {t.name}: {t.description[:50] if t.description else 'No description'}...")

    # Create model
    model = get_gemini3_flash_model(thinking_level="NONE")
    print(f"\nModel created: {model.model_name}")

    # Try to convert tools
    print("\nConverting tools to Gemini format...")
    try:
        gemini_tools = model._convert_tools_to_gemini_format(tools)
        print(f"SUCCESS! Converted {len(gemini_tools)} tool groups")
        if gemini_tools:
            tool_obj = gemini_tools[0]
            print(f"Function declarations: {len(tool_obj.function_declarations)}")
            for fd in tool_obj.function_declarations:
                print(f"  - {fd.name}: {len(fd.parameters.properties) if fd.parameters else 0} params")
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_tool_conversion()
