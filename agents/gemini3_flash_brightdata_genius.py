"""
Gemini 3 Flash Deep Agent with BrightData SDK + Genius API + Sub-Agents
========================================================================

This is a FULL-FEATURED deep research agent that combines:
- Google Gemini 3 Flash (1M context, 65K output) with Thinking Mode
- BrightData SDK for enterprise-grade web scraping and search
- Genius API for song lyrics and music metadata
- General Purpose Sub-Agent delegation for complex parallel tasks
- Context reduction/trimming for long conversations
- Todo list, filesystem tools, and summarization (via create_deep_agent)

Perfect for:
- Deep web research with parallel sub-agents
- Music/lyrics research with Genius API
- Complex multi-step tasks with isolated context
- Enterprise-grade web data collection
"""
import asyncio
import json
import logging
import os
import requests
import sys
from typing import Optional, Literal

# Module-level debug - write to file at import time
try:
    import datetime as _dt
    with open("c:/projects/learn_ten_x_faster/deepagents/module_load_debug.log", "a", encoding="utf-8") as _f:
        _f.write(f"[{_dt.datetime.now()}] Module loaded from {__file__}\n")
except Exception as _e:
    pass

from langchain_core.tools import tool
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from deepagents import create_deep_agent

# Apply nest_asyncio EARLY to allow nested event loops
# This is critical for sub-agents that run in async context
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # Will use fallback in _run_async
except ValueError:
    # uvloop (used by Railway/LangGraph) can't be patched - that's OK
    # The async calls will work natively without nest_asyncio
    pass

# Configure logging
logger = logging.getLogger(__name__)

# ============================================================================
# Context Limits for Gemini 3 Flash (1M input tokens, 65K output tokens)
# ============================================================================

MAX_CONTEXT_CHARS = 3500000  # Safe limit below 1M tokens (~4 chars per token)
MAX_TOOL_OUTPUT_CHARS = 15000  # Max chars per tool output
MAX_TOTAL_MESSAGES_CHARS = 3000000  # Max total message content
MAX_OUTPUT_TOKENS = 65536  # Gemini 3 Flash max output


def truncate_content(content: str, max_chars: int = MAX_TOOL_OUTPUT_CHARS) -> str:
    """Truncate content to stay within character limits."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n\n[TRUNCATED - Content exceeded {max_chars} characters]"


# ============================================================================
# Gemini 3 Flash Model Initialization (Native Google GenAI SDK)
# ============================================================================

# Lazy import for google-genai
_genai_client = None


def get_genai_client():
    """Get or initialize Google GenAI client."""
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai package not installed. Install with: pip install google-genai"
            )

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set. "
                "Get your API key from https://aistudio.google.com/apikey"
            )

        _genai_client = genai.Client(api_key=api_key)

    return _genai_client


class ChatGemini3Flash(BaseChatModel):
    """LangChain-compatible wrapper for Gemini 3 Flash with Thinking Mode.

    Uses the native google-genai SDK for full Gemini 3 Flash support including
    thinking/reasoning capabilities and native function calling.
    """

    model_name: str = "gemini-3-flash-preview"
    temperature: float = 0.7
    max_output_tokens: int = MAX_OUTPUT_TOKENS
    thinking_level: Literal["NONE", "LOW", "MEDIUM", "HIGH"] = "NONE"
    _bound_tools: list = []  # Tools bound via bind_tools()

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        object.__setattr__(self, '_bound_tools', kwargs.get('_bound_tools', []))

    @property
    def _llm_type(self) -> str:
        return "gemini-3-flash"

    @property
    def _identifying_params(self) -> dict:
        return {
            "model_name": self.model_name,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
            "thinking_level": self.thinking_level,
        }

    def _convert_tools_to_gemini_format(self, tools: list) -> list:
        """Convert LangChain tools to Gemini FunctionDeclaration format.

        Uses function signature extraction which is more reliable than Pydantic
        schema extraction (avoids CallableSchema and other serialization issues).
        """
        from google.genai import types
        import inspect
        import typing

        def get_type_info(annotation) -> dict:
            """Get JSON schema type info from Python type annotation.

            Returns a dict with 'type' and optionally 'items' for arrays.
            """
            if annotation is None or annotation == inspect.Parameter.empty:
                return {'type': 'string'}

            # Handle basic types
            if annotation == str:
                return {'type': 'string'}
            elif annotation == int:
                return {'type': 'integer'}
            elif annotation == float:
                return {'type': 'number'}
            elif annotation == bool:
                return {'type': 'boolean'}
            elif annotation == list:
                return {'type': 'array', 'items': {'type': 'string'}}
            elif annotation == dict:
                return {'type': 'object'}

            # Handle typing module types (Optional, List, etc.)
            origin = getattr(annotation, '__origin__', None)
            if origin is not None:
                if origin == list:
                    # Get the item type from List[X]
                    args = getattr(annotation, '__args__', ())
                    if args:
                        item_info = get_type_info(args[0])
                        return {'type': 'array', 'items': item_info}
                    return {'type': 'array', 'items': {'type': 'string'}}
                elif origin == dict:
                    return {'type': 'object'}
                elif origin == typing.Union:
                    # For Optional[X], get the non-None type
                    args = getattr(annotation, '__args__', ())
                    for arg in args:
                        if arg is not type(None):
                            return get_type_info(arg)

            return {'type': 'string'}

        def get_type_string(annotation) -> str:
            """Get JSON schema type string from Python type annotation."""
            return get_type_info(annotation).get('type', 'string')

        def extract_schema_from_tool(tool) -> dict:
            """Extract parameter schema from a LangChain tool.

            Tries multiple methods in order of reliability:
            1. Pydantic args_schema if available (most complete)
            2. Function signature extraction (fallback)
            """
            properties = {}
            required = []

            # Method 1: Try to use Pydantic args_schema (preferred for complex types)
            if hasattr(tool, 'args_schema') and tool.args_schema is not None:
                try:
                    args_schema = tool.args_schema
                    # Get JSON schema from Pydantic model
                    if hasattr(args_schema, 'model_json_schema'):
                        # Pydantic v2
                        json_schema = args_schema.model_json_schema()
                    elif hasattr(args_schema, 'schema'):
                        # Pydantic v1
                        json_schema = args_schema.schema()
                    else:
                        json_schema = None

                    if json_schema and 'properties' in json_schema:
                        logger.debug(f"[GEMINI] Using Pydantic schema for {tool.name}")
                        defs = json_schema.get('$defs', json_schema.get('definitions', {}))

                        def resolve_ref(schema_obj):
                            """Resolve $ref references in JSON schema."""
                            if not isinstance(schema_obj, dict):
                                return schema_obj
                            if '$ref' in schema_obj:
                                ref = schema_obj['$ref']
                                # Handle #/$defs/ClassName or #/definitions/ClassName
                                if ref.startswith('#/$defs/'):
                                    def_name = ref[8:]
                                    return defs.get(def_name, {'type': 'object'})
                                elif ref.startswith('#/definitions/'):
                                    def_name = ref[14:]
                                    return defs.get(def_name, {'type': 'object'})
                            return schema_obj

                        # Process the JSON schema to ensure items are set for arrays
                        for prop_name, prop_info in json_schema.get('properties', {}).items():
                            prop_type = prop_info.get('type', 'string')
                            prop_entry = {
                                'type': prop_type,
                                'description': prop_info.get('description', f'Parameter: {prop_name}')
                            }

                            # Ensure items is set for array types
                            if prop_type == 'array':
                                if 'items' in prop_info:
                                    items_schema = resolve_ref(prop_info['items'])
                                    prop_entry['items'] = items_schema
                                else:
                                    # Default to string items if not specified
                                    prop_entry['items'] = {'type': 'string'}

                            properties[prop_name] = prop_entry

                        required = json_schema.get('required', [])
                        return {'type': 'object', 'properties': properties, 'required': required}
                except Exception as e:
                    logger.debug(f"[GEMINI] Could not use Pydantic schema for {tool.name}: {e}")

            # Method 2: Fall back to function signature extraction
            func = None
            if hasattr(tool, 'func'):
                func = tool.func
            elif hasattr(tool, '_run'):
                func = tool._run

            if func is None:
                return {'type': 'object', 'properties': {}, 'required': []}

            try:
                sig = inspect.signature(func)

                # Get type hints safely
                type_hints = {}
                try:
                    type_hints = typing.get_type_hints(func)
                except Exception:
                    try:
                        type_hints = getattr(func, '__annotations__', {})
                    except Exception:
                        pass

                for param_name, param in sig.parameters.items():
                    # Skip self, cls, and variadic parameters
                    if param_name in ('self', 'cls'):
                        continue
                    if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                        continue

                    # Get type info from hints (includes items for arrays)
                    type_info = {'type': 'string'}
                    if param_name in type_hints:
                        type_info = get_type_info(type_hints[param_name])
                    elif param.annotation != inspect.Parameter.empty:
                        type_info = get_type_info(param.annotation)

                    # Get description from docstring or parameter name
                    description = f'Parameter: {param_name}'

                    prop_entry = {
                        'type': type_info.get('type', 'string'),
                        'description': description
                    }

                    # Include items for array types - ALWAYS set default if missing
                    if type_info.get('type') == 'array':
                        if 'items' in type_info:
                            prop_entry['items'] = type_info['items']
                        else:
                            prop_entry['items'] = {'type': 'string'}

                    properties[param_name] = prop_entry

                    # Check if required (no default value)
                    if param.default == inspect.Parameter.empty:
                        required.append(param_name)

            except Exception as e:
                logger.debug(f"[GEMINI] Could not extract signature from {tool.name}: {e}")

            return {'type': 'object', 'properties': properties, 'required': required}

        function_declarations = []
        for tool in tools:
            try:
                # Extract schema directly from function signature (most reliable)
                schema = extract_schema_from_tool(tool)

                # Build Gemini parameters from schema
                properties = {}
                required = []

                type_map = {
                    'string': 'STRING',
                    'integer': 'INTEGER',
                    'number': 'NUMBER',
                    'boolean': 'BOOLEAN',
                    'array': 'ARRAY',
                    'object': 'OBJECT',
                }

                for prop_name, prop_info in schema.get('properties', {}).items():
                    prop_type = prop_info.get('type', 'string')
                    gemini_type = type_map.get(prop_type, 'STRING')

                    # Build schema kwargs
                    schema_kwargs = {
                        'type': gemini_type,
                        'description': prop_info.get('description', ''),
                    }

                    # For ARRAY type, Gemini requires 'items' field
                    if gemini_type == 'ARRAY':
                        # Get items type from prop_info, default to STRING
                        items_info = prop_info.get('items', {})
                        items_type = items_info.get('type', 'string') if items_info else 'string'
                        items_gemini_type = type_map.get(items_type, 'STRING')

                        # Create items schema - for complex objects, use OBJECT type
                        if items_gemini_type == 'OBJECT':
                            # If items have properties, include them
                            items_props = items_info.get('properties', {}) if items_info else {}
                            if items_props:
                                nested_properties = {}
                                for nested_name, nested_info in items_props.items():
                                    nested_type = nested_info.get('type', 'string')
                                    nested_gemini_type = type_map.get(nested_type, 'STRING')
                                    nested_properties[nested_name] = types.Schema(
                                        type=nested_gemini_type,
                                        description=nested_info.get('description', '')
                                    )
                                schema_kwargs['items'] = types.Schema(
                                    type='OBJECT',
                                    properties=nested_properties
                                )
                            else:
                                schema_kwargs['items'] = types.Schema(type='OBJECT')
                        else:
                            schema_kwargs['items'] = types.Schema(type=items_gemini_type)

                    properties[prop_name] = types.Schema(**schema_kwargs)

                required = schema.get('required', [])

                parameters = types.Schema(
                    type='OBJECT',
                    properties=properties,
                    required=required if required else None,
                )

                func_decl = types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description or '',
                    parameters=parameters,
                )
                function_declarations.append(func_decl)
                logger.info(f"[GEMINI] Converted tool: {tool.name} with {len(properties)} params")

            except Exception as e:
                logger.error(f"[GEMINI] Failed to convert tool {tool.name}: {e}")
                import traceback
                logger.debug(f"[GEMINI] Traceback: {traceback.format_exc()}")
                # Skip this tool but continue with others

        if function_declarations:
            logger.info(f"[GEMINI] Total {len(function_declarations)} tools converted to Gemini format")
            return [types.Tool(function_declarations=function_declarations)]
        return []

    def _convert_messages_to_contents(self, messages: list[BaseMessage]) -> list:
        """Convert LangChain messages to Google GenAI content format."""
        from google.genai import types

        contents = []
        system_instruction = None

        for msg in messages:
            if isinstance(msg, SystemMessage):
                # System messages become system instruction
                system_instruction = msg.content
            elif isinstance(msg, HumanMessage):
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=str(msg.content))],
                    )
                )
            elif isinstance(msg, AIMessage):
                parts = []
                # Add text content if present
                if msg.content:
                    parts.append(types.Part.from_text(text=str(msg.content)))

                # Get thought_signatures from additional_kwargs if present
                thought_signatures = msg.additional_kwargs.get('thought_signatures', {}) if hasattr(msg, 'additional_kwargs') else {}

                # Add function calls if present
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    import base64
                    for tool_call in msg.tool_calls:
                        call_id = tool_call.get('id', '')
                        sig_b64 = thought_signatures.get(call_id)

                        if sig_b64:
                            # Include thought_signature in the Part (required for Gemini 3)
                            # Create Part with function_call and thought_signature
                            sig_bytes = base64.b64decode(sig_b64)
                            func_call = types.FunctionCall(
                                name=tool_call['name'],
                                args=tool_call['args'],
                            )
                            part = types.Part(function_call=func_call, thought_signature=sig_bytes)
                            parts.append(part)
                            logger.info(f"[GEMINI] Including thought_signature for {tool_call['name']}")
                        else:
                            # Fallback without signature (may cause issues with Gemini 3)
                            parts.append(types.Part.from_function_call(
                                name=tool_call['name'],
                                args=tool_call['args'],
                            ))

                if parts:
                    contents.append(types.Content(role="model", parts=parts))
            elif isinstance(msg, ToolMessage):
                # Tool responses become function_response parts
                # Try to parse as JSON, otherwise use as string
                try:
                    import json
                    response_data = json.loads(msg.content)
                except (json.JSONDecodeError, TypeError):
                    response_data = {"result": msg.content}

                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=msg.name or "unknown_tool",
                            response=response_data,
                        )],
                    )
                )

        return contents, system_instruction

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        """Generate a response using Gemini 3 Flash with native function calling."""
        from google.genai import types
        import uuid

        # Debug: Write to file
        import datetime
        with open("c:/projects/learn_ten_x_faster/deepagents/gemini_debug.log", "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n")
            f.write(f"[{datetime.datetime.now()}] Received {len(messages)} messages\n")
            for i, msg in enumerate(messages):
                msg_type = type(msg).__name__
                content_preview = str(msg.content)[:500] if msg.content else "EMPTY"
                f.write(f"Message {i} ({msg_type}): {content_preview}...\n")

        client = get_genai_client()
        contents, system_instruction = self._convert_messages_to_contents(messages)

        # Get bound tools from kwargs or instance
        tools = kwargs.get('tools', getattr(self, '_bound_tools', []))

        # Convert tools to Gemini format
        gemini_tools = []
        if tools:
            try:
                gemini_tools = self._convert_tools_to_gemini_format(tools)
                logger.info(f"[GEMINI] Converted {len(tools)} tools to Gemini format")
                with open("c:/projects/learn_ten_x_faster/deepagents/gemini_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Tools bound: {len(tools)} - {[t.name for t in tools]}\n")
            except Exception as e:
                logger.warning(f"[GEMINI] Failed to convert tools: {e}")
                with open("c:/projects/learn_ten_x_faster/deepagents/gemini_debug.log", "a", encoding="utf-8") as f:
                    f.write(f"Tool conversion error: {e}\n")

        # Build config with thinking mode
        config_params = {
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }

        # Add thinking config for Gemini 3 Flash
        if self.thinking_level != "NONE":
            try:
                budget_map = {"LOW": 1024, "MEDIUM": 8192, "HIGH": 24576}
                budget = budget_map.get(self.thinking_level, 8192)
                thinking_config = types.ThinkingConfig(thinkingBudget=budget)
                config_params["thinking_config"] = thinking_config
            except Exception as e:
                logger.warning(f"ThinkingConfig error: {e}, skipping")

        # Add system instruction if present
        if system_instruction:
            config_params["system_instruction"] = system_instruction

        # Add stop sequences if provided
        if stop:
            config_params["stop_sequences"] = stop

        # Add tools if available
        if gemini_tools:
            config_params["tools"] = gemini_tools

        generate_content_config = types.GenerateContentConfig(**config_params)

        try:
            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=generate_content_config,
            )

            # Debug: Write response info to file
            with open("c:/projects/learn_ten_x_faster/deepagents/gemini_debug.log", "a", encoding="utf-8") as f:
                f.write(f"Got response, candidates count: {len(response.candidates) if response.candidates else 0}\n")
                if response.candidates:
                    c = response.candidates[0]
                    f.write(f"Finish reason: {getattr(c, 'finish_reason', 'N/A')}\n")
                    if c.content and c.content.parts:
                        for i, p in enumerate(c.content.parts):
                            text = getattr(p, 'text', '')
                            func_call = getattr(p, 'function_call', None)
                            if func_call:
                                f.write(f"Part {i}: FUNCTION_CALL - {func_call.name}({func_call.args})\n")
                            else:
                                f.write(f"Part {i}: len={len(text) if text else 0}, preview={text[:100] if text else 'EMPTY'}...\n")

            # Extract response - check for function calls
            response_text = ""
            tool_calls = []

            # Also capture thought_signatures for function calls (required by Gemini 3)
            thought_signatures = {}

            if response.candidates:
                for candidate in response.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            # Skip thought parts (thinking mode internal reasoning)
                            if hasattr(part, 'thought') and part.thought:
                                continue

                            # Check for function call
                            if hasattr(part, 'function_call') and part.function_call:
                                func_call = part.function_call
                                call_id = f"call_{uuid.uuid4().hex[:8]}"
                                tool_call = {
                                    "id": call_id,
                                    "name": func_call.name,
                                    "args": dict(func_call.args) if func_call.args else {},
                                }
                                tool_calls.append(tool_call)

                                # Capture thought_signature if present (required for Gemini 3)
                                if hasattr(part, 'thought_signature') and part.thought_signature:
                                    import base64
                                    thought_signatures[call_id] = base64.b64encode(part.thought_signature).decode('utf-8')
                                    logger.info(f"[GEMINI] Captured thought_signature for {func_call.name}")

                                logger.info(f"[GEMINI] Function call: {func_call.name}({func_call.args})")

                            # Extract text
                            elif hasattr(part, 'text') and part.text:
                                response_text += part.text

            # Create AIMessage with tool_calls if present
            if tool_calls:
                # LangChain expects tool_calls in a specific format
                # Include thought_signatures in additional_kwargs for later use
                message = AIMessage(
                    content=response_text or "",
                    tool_calls=[
                        {
                            "id": tc["id"],
                            "name": tc["name"],
                            "args": tc["args"],
                        }
                        for tc in tool_calls
                    ],
                    additional_kwargs={
                        "thought_signatures": thought_signatures,
                    } if thought_signatures else {},
                )
                logger.info(f"[GEMINI] Returning AIMessage with {len(tool_calls)} tool calls, {len(thought_signatures)} signatures")
            else:
                # Regular text response
                if not response_text:
                    logger.warning(f"[GEMINI] Empty response. Candidates: {response.candidates}")
                message = AIMessage(content=response_text)

            generation = ChatGeneration(message=message)
            return ChatResult(generations=[generation])

        except Exception as e:
            logger.error(f"[GEMINI] Generation error: {type(e).__name__}: {str(e)}")
            raise

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        """Async generate - wraps sync for now."""
        import concurrent.futures
        import datetime

        # Debug: Log _agenerate entry
        debug_path = "c:/projects/learn_ten_x_faster/deepagents/gemini_agenerate_debug.log"
        try:
            with open(debug_path, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.datetime.now()}] _agenerate called with {len(messages)} messages\n")
        except Exception as e:
            logger.error(f"[GEMINI] Debug log failed: {e}")

        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            result = await loop.run_in_executor(
                executor,
                lambda: self._generate(messages, stop, run_manager, **kwargs)
            )
        return result

    def bind_tools(self, tools: list, **kwargs):
        """Bind tools to the model for native Gemini function calling.

        Creates a new instance with tools bound, which will be passed to the
        Gemini API as FunctionDeclarations for native function calling.
        """
        # Create a new instance with tools bound
        new_instance = ChatGemini3Flash(
            model_name=self.model_name,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
            thinking_level=self.thinking_level,
            _bound_tools=tools,
        )
        return new_instance


def get_gemini3_flash_model(
    max_output_tokens: int = MAX_OUTPUT_TOKENS,
    temperature: float = 0.7,
    thinking_level: Literal["NONE", "LOW", "MEDIUM", "HIGH"] = "NONE",
) -> ChatGemini3Flash:
    """Initialize Gemini 3 Flash with Thinking Mode enabled.

    Args:
        max_output_tokens: Maximum tokens for model output (default: 65536)
        temperature: Temperature for generation (default: 0.7)
        thinking_level: Thinking/reasoning level - NONE, LOW, MEDIUM, HIGH (default: HIGH)

    Returns:
        ChatGemini3Flash instance configured for use with LangChain
    """
    model_name = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

    logger.info(f"Initializing Gemini 3 Flash with model: {model_name}, thinking: {thinking_level}")

    return ChatGemini3Flash(
        model_name=model_name,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        thinking_level=thinking_level,
    )


# ============================================================================
# BrightData SDK Tools
# ============================================================================

_brightdata_client = None


def get_brightdata_client():
    """Get or initialize BrightData SDK client (v1.1.3+ API)."""
    global _brightdata_client

    if _brightdata_client is None:
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            logger.warning("BRIGHTDATA_API_TOKEN not set - BrightData tools will be disabled")
            return None

        try:
            from brightdata import bdclient
        except ImportError:
            logger.warning("BrightData SDK not installed. Install with: pip install brightdata>=1.1.0")
            return None

        serp_zone = os.getenv("SERP_ZONE", "serp_api1")
        web_unlocker_zone = os.getenv("WEB_UNLOCKER_ZONE")
        logger.info(f"Initializing BrightData client with SERP zone: {serp_zone}")

        try:
            _brightdata_client = bdclient(
                api_token=api_token,
                serp_zone=serp_zone,
                web_unlocker_zone=web_unlocker_zone
            )
        except Exception as e:
            logger.warning(f"Failed to init with zones, trying without: {e}")
            _brightdata_client = bdclient(api_token=api_token)

    return _brightdata_client


def _run_sync_in_thread(func, *args, **kwargs):
    """Run a sync function in a thread to avoid uvloop conflicts.

    The BrightData SDK internally uses nest_asyncio which doesn't work with uvloop
    (used by Railway/LangGraph). By running in a separate thread, the SDK can
    create its own event loop without uvloop interference.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=120)  # 2 minute timeout


def _run_search_in_thread(search_type: str, query: str, num_results: int):
    """Run BrightData search in a thread with its own client.

    Creates a fresh BrightData client in a separate thread to avoid uvloop
    compatibility issues. Uses the sync API from brightdata SDK v1.1.3+.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        serp_zone = os.getenv("SERP_ZONE", "serp_api1")

        try:
            from brightdata import bdclient
            client = bdclient(api_token=api_token, serp_zone=serp_zone)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        try:
            # Use the sync search API from SDK v1.1.3+
            result = client.search(
                query=query,
                search_engine=search_type,
                response_format="json",
                parse=True
            )
            return result
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Search error: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


def _run_scrape_in_thread(url: str, response_format: str = "raw"):
    """Run BrightData scrape in a thread with its own client.

    Creates a fresh BrightData client in a separate thread to avoid uvloop
    compatibility issues. Uses the sync API from brightdata SDK v1.1.3+.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        web_unlocker_zone = os.getenv("WEB_UNLOCKER_ZONE")

        try:
            from brightdata import bdclient
            client = bdclient(api_token=api_token, web_unlocker_zone=web_unlocker_zone)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        try:
            # Use the sync scrape API from SDK v1.1.3+
            return client.scrape(
                url=url,
                zone=web_unlocker_zone,
                response_format=response_format
            )
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Scrape error: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


@tool
def brightdata_search_google(
    query: str,
    num_results: int = 10
) -> str:
    """Search Google using BrightData SERP API with enterprise-grade reliability.

    Use this for web searches when you need reliable, anti-bot bypassing search results.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)

    Returns:
        JSON string with search results including titles, URLs, and snippets
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching Google for: {query}")
        # Run search in a separate thread to avoid uvloop conflicts
        result = _run_search_in_thread("google", query, num_results)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute search"})

        # Format results from SDK v1.1.3+ response format
        # Response: {'status_code': 200, 'headers': {...}, 'body': '<JSON_STRING>'}
        formatted_results = []
        if isinstance(result, dict):
            # SDK v1.1.3+ returns {'status_code', 'headers', 'body'}
            body = result.get('body', result)
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    body = result  # Fall back to original

            # Extract organic results from parsed body
            organic = body.get('organic', body.get('results', body.get('data', [])))
            for i, item in enumerate(organic[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })
        elif hasattr(result, 'data') and result.data:
            # Legacy format support
            for i, item in enumerate(result.data[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })

        return json.dumps({
            'success': True,
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Google search error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_search_bing(
    query: str,
    num_results: int = 10
) -> str:
    """Search Bing using BrightData SERP API for alternative perspectives.

    Args:
        query: Search query string
        num_results: Number of results to return (default: 10)

    Returns:
        JSON string with search results including titles, URLs, and snippets
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching Bing for: {query}")
        # Run search in a separate thread to avoid uvloop conflicts
        result = _run_search_in_thread("bing", query, num_results)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute search"})

        # Format results from SDK v1.1.3+ response format
        formatted_results = []
        if isinstance(result, dict):
            # SDK v1.1.3+ returns {'status_code', 'headers', 'body'}
            body = result.get('body', result)
            if isinstance(body, str):
                try:
                    body = json.loads(body)
                except json.JSONDecodeError:
                    body = result

            organic = body.get('organic', body.get('results', body.get('data', [])))
            for i, item in enumerate(organic[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })
        elif hasattr(result, 'data') and result.data:
            for i, item in enumerate(result.data[:num_results]):
                formatted_results.append({
                    'position': i + 1,
                    'title': item.get('title', ''),
                    'url': item.get('link', item.get('url', '')),
                    'snippet': item.get('snippet', item.get('description', '')),
                })

        return json.dumps({
            'success': True,
            'query': query,
            'results': formatted_results,
            'total_results': len(formatted_results)
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Bing search error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_scrape_url(
    url: str,
    response_format: str = "raw"
) -> str:
    """Scrape a webpage and extract its content using BrightData with anti-bot bypass.

    Args:
        url: The URL to scrape
        response_format: Output format - 'raw', 'markdown', or 'json' (default: 'raw')

    Returns:
        JSON string with scraped content
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Scraping URL: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, response_format)

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute scrape"})

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        # Truncate content to prevent context overflow
        content = truncate_content(content, MAX_TOOL_OUTPUT_CHARS)

        return json.dumps({
            'success': True,
            'url': url,
            'content': content,
            'format': response_format
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Scrape error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_crawl_website(
    url: str,
    max_pages: int = 10
) -> str:
    """Crawl a website and extract content from multiple pages using BrightData.

    Note: In SDK v2.0, crawler is limited. This will scrape the main URL.

    Args:
        url: The starting URL to crawl
        max_pages: Maximum number of pages to crawl (default: 10, currently limited)

    Returns:
        JSON string with crawled content
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Crawling website: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, "raw")

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute crawl"})

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        content = truncate_content(content, MAX_TOOL_OUTPUT_CHARS)

        return json.dumps({
            'success': True,
            'url': url,
            'pages_crawled': 1,
            'content': content,
            'note': 'Crawler limited to single page in SDK v2.0'
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Crawl error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


@tool
def brightdata_extract_data(
    url: str,
    extraction_prompt: str
) -> str:
    """Extract structured data from a webpage using AI-powered extraction.

    Args:
        url: The URL to extract data from
        extraction_prompt: Natural language description of what data to extract

    Returns:
        JSON string with extracted structured data
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Extracting data from: {url}")

        # Run scrape in a separate thread to avoid uvloop conflicts
        result = _run_scrape_in_thread(url, "raw")

        if result is None:
            return json.dumps({"success": False, "url": url, "error": "Failed to execute extraction"})

        if hasattr(result, 'success') and result.success is False:
            error_msg = getattr(result, 'error', 'Unknown error')
            return json.dumps({
                'success': False,
                'url': url,
                'error': f'BrightData API error: {error_msg}'
            }, ensure_ascii=False)

        content = ""
        if hasattr(result, 'data') and result.data:
            if isinstance(result.data, list) and len(result.data) > 0:
                content = json.dumps(result.data, ensure_ascii=False, indent=2)
            else:
                content = str(result.data)
        elif hasattr(result, 'content'):
            content = result.content
        elif isinstance(result, str):
            content = result
        else:
            content = str(result)

        return json.dumps({
            'success': True,
            'url': url,
            'extraction_prompt': extraction_prompt,
            'raw_content': truncate_content(content, 5000),
            'note': 'AI extraction not available in SDK v2.0 - use raw content with your own processing'
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] Extract error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'url': url,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


def _run_linkedin_search_in_thread(query: str, search_type: str):
    """Run LinkedIn search in a thread with its own client.

    Creates a fresh BrightData client in a separate thread to avoid uvloop
    compatibility issues. Uses the sync API from brightdata SDK v1.1.3+.
    """
    import concurrent.futures

    def _run():
        # Create a fresh client in this thread
        api_token = os.getenv("BRIGHTDATA_API_TOKEN")
        if not api_token:
            return None

        try:
            from brightdata import bdclient
            client = bdclient(api_token=api_token)
        except Exception as e:
            logger.error(f"[BRIGHTDATA] Failed to create client in thread: {e}")
            return None

        try:
            # Use the sync LinkedIn search API from SDK v1.1.3+
            if search_type == "jobs":
                return client.search_linkedin(keyword=query, search_type="jobs")
            else:
                return client.search_linkedin(keyword=query, search_type="people")
        except Exception as e:
            logger.error(f"[BRIGHTDATA] LinkedIn search error: {e}")
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


@tool
def brightdata_search_linkedin(
    query: str,
    search_type: str = "profiles"
) -> str:
    """Search LinkedIn using BrightData (requires LinkedIn zone).

    Args:
        query: Search query (name, company, job title, etc.)
        search_type: Type of search - 'profiles' or 'jobs' (default: 'profiles')

    Returns:
        JSON string with LinkedIn search results
    """
    try:
        if not os.getenv("BRIGHTDATA_API_TOKEN"):
            return json.dumps({"success": False, "error": "BRIGHTDATA_API_TOKEN not set"})

        logger.info(f"[BRIGHTDATA] Searching LinkedIn for: {query} (type: {search_type})")

        # Run LinkedIn search in a separate thread to avoid uvloop conflicts
        result = _run_linkedin_search_in_thread(query, search_type)

        if result is None:
            return json.dumps({"success": False, "error": "Failed to execute LinkedIn search"})

        results_data = []
        if hasattr(result, 'data') and result.data:
            results_data = result.data
        elif isinstance(result, list):
            results_data = result
        elif isinstance(result, dict):
            results_data = result.get('data', result.get('results', [result]))

        return json.dumps({
            'success': True,
            'query': query,
            'search_type': search_type,
            'results': results_data
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[BRIGHTDATA] LinkedIn search error: {type(e).__name__}: {str(e)}")
        return json.dumps({
            'success': False,
            'error': f'{type(e).__name__}: {str(e)}'
        }, ensure_ascii=False)


# ============================================================================
# Genius API Tools (Song Lyrics Search)
# ============================================================================

def get_genius_headers():
    """Get Genius API headers with access token"""
    access_token = os.getenv("GENIUS_ACCESS_TOKEN")
    if not access_token:
        return None
    return {"Authorization": f"Bearer {access_token}"}


@tool
def genius_search_song(song_name: str, artist_name: Optional[str] = None) -> str:
    """Search for a song on Genius to find its lyrics page URL.

    This is the FIRST step in finding song lyrics. Use this to search for a song
    and get the Genius URL where the lyrics are located.

    Args:
        song_name: The name of the song to search for
        artist_name: Optional artist name to narrow down the search

    Returns:
        JSON string with search results including song title, artist, URL, and song ID
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        query = song_name
        if artist_name:
            query = f"{song_name} {artist_name}"

        response = requests.get(
            "https://api.genius.com/search",
            params={"q": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "hits" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": "No results found",
                "query": query
            }, ensure_ascii=False)

        results = []
        for hit in data["response"]["hits"][:5]:
            song = hit["result"]
            results.append({
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "url": song["url"],
                "song_id": song["id"],
                "thumbnail": song.get("song_art_image_thumbnail_url", "")
            })

        return json.dumps({
            "success": True,
            "query": query,
            "results_count": len(results),
            "results": results
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


@tool
def genius_get_song_details(song_id: int) -> str:
    """Get detailed information about a song from Genius.

    Use this AFTER genius_search_song to get more details about a specific song,
    including album, release date, and the lyrics page URL.

    Args:
        song_id: The Genius song ID (obtained from genius_search_song)

    Returns:
        JSON string with detailed song information
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        response = requests.get(
            f"https://api.genius.com/songs/{song_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "song" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": f"Song with ID {song_id} not found"
            }, ensure_ascii=False)

        song = data["response"]["song"]

        return json.dumps({
            "success": True,
            "song": {
                "id": song["id"],
                "title": song["title"],
                "artist": song["primary_artist"]["name"],
                "album": song.get("album", {}).get("name") if song.get("album") else None,
                "release_date": song.get("release_date"),
                "url": song["url"],
                "page_views": song.get("stats", {}).get("pageviews"),
                "description": song.get("description_preview", "")[:500],
                "thumbnail": song.get("song_art_image_thumbnail_url", ""),
                "full_image": song.get("song_art_image_url", "")
            }
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


@tool
def genius_get_artist(artist_id: int) -> str:
    """Get detailed information about an artist from Genius.

    Args:
        artist_id: The Genius artist ID

    Returns:
        JSON string with artist information including bio and social links
    """
    try:
        headers = get_genius_headers()
        if not headers:
            return json.dumps({
                "success": False,
                "error": "GENIUS_ACCESS_TOKEN not set"
            }, ensure_ascii=False)

        response = requests.get(
            f"https://api.genius.com/artists/{artist_id}",
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        data = response.json()

        if "response" not in data or "artist" not in data["response"]:
            return json.dumps({
                "success": False,
                "error": f"Artist with ID {artist_id} not found"
            }, ensure_ascii=False)

        artist = data["response"]["artist"]

        return json.dumps({
            "success": True,
            "artist": {
                "id": artist["id"],
                "name": artist["name"],
                "url": artist["url"],
                "image": artist.get("image_url", ""),
                "description": artist.get("description_preview", "")[:500],
                "twitter": artist.get("twitter_name"),
                "instagram": artist.get("instagram_name"),
                "facebook": artist.get("facebook_name"),
            }
        }, ensure_ascii=False, indent=2)

    except requests.exceptions.RequestException as e:
        return json.dumps({
            "success": False,
            "error": f"Network error: {str(e)}"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": f"{type(e).__name__}: {str(e)}"
        }, ensure_ascii=False)


# ============================================================================
# Combined Tool: Get Lyrics in ONE call (Search + Scrape)
# ============================================================================

def _extract_lyrics_from_html(html: str) -> dict:
    """Extract lyrics from Genius page HTML."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return {"success": False, "error": "beautifulsoup4 not installed"}

    soup = BeautifulSoup(html, 'html.parser')
    result = {"success": False, "title": None, "artist": None, "lyrics": None}

    # Extract title and artist from meta tag
    og_title = soup.find('meta', property='og:title')
    if og_title and og_title.get('content'):
        title_content = og_title['content']
        if ' by ' in title_content:
            parts = title_content.split(' by ')
            result["title"] = parts[0].strip()
            result["artist"] = parts[1].strip()

    # Extract lyrics from data-lyrics-container elements
    lyrics_containers = soup.find_all('div', attrs={'data-lyrics-container': 'true'})

    if lyrics_containers:
        lyrics_parts = []
        for container in lyrics_containers:
            for br in container.find_all('br'):
                br.replace_with('\n')
            text = container.get_text(separator='')
            lyrics_parts.append(text.strip())

        raw_lyrics = '\n\n'.join(lyrics_parts)

        # Clean up header noise (Contributors, Translations, etc.)
        import re
        for pattern in [r'\[(?:Intro|Verse|Chorus|Bridge|Pre-Chorus|Outro|Hook)', r'\n[A-Z][a-z]']:
            match = re.search(pattern, raw_lyrics, re.IGNORECASE)
            if match:
                start_pos = match.start()
                if raw_lyrics[start_pos] == '\n':
                    start_pos += 1
                raw_lyrics = raw_lyrics[start_pos:]
                break

        result["lyrics"] = raw_lyrics.strip()
        result["success"] = True

    return result


def _ai_analyze_genius_results(query: str, results: list, artist_hint: Optional[str] = None) -> dict:
    """Use AI to analyze Genius search results and pick the best match.

    Args:
        query: The original search query
        results: List of search result hits from Genius API
        artist_hint: Optional artist name hint from user

    Returns:
        The best matching result dict, or None if no good match
    """
    if not results:
        return None

    # If only one result, return it
    if len(results) == 1:
        return results[0]["result"]

    # Format results for AI analysis
    formatted_results = []
    for i, hit in enumerate(results[:5]):  # Limit to top 5
        song = hit["result"]
        formatted_results.append({
            "index": i,
            "title": song.get("title", "Unknown"),
            "artist": song.get("primary_artist", {}).get("name", "Unknown"),
            "url": song.get("url", ""),
        })

    # Create a simple prompt that works well with Gemini
    results_text = "\n".join([
        f"{r['index']}: \"{r['title']}\" by {r['artist']}"
        for r in formatted_results
    ])

    prompt = f"""User is searching for: "{query}"{f' by {artist_hint}' if artist_hint else ''}

Search results:
{results_text}

Return ONLY the index number (0-{len(formatted_results)-1}) of the best matching song. Just the number, nothing else.

Answer:"""

    try:
        # Use Gemini 3 Flash for fast analysis
        model = get_gemini3_flash_model(max_output_tokens=50, temperature=0.0, thinking_level="LOW")
        response = model.invoke(prompt)

        # Parse the response - should be just a number
        response_text = response.content.strip() if response.content else ""
        logger.info(f"[GENIUS AI] Raw response: '{response_text}'")

        # Extract number from response
        import re
        numbers = re.findall(r'\d+', response_text)
        if numbers:
            index = int(numbers[0])
            if 0 <= index < len(results):
                selected = results[index]["result"]
                logger.info(f"[GENIUS AI] Selected index {index}: {selected.get('title')} by {selected.get('primary_artist', {}).get('name')}")
                return selected

        # Fallback to first result if AI response is unclear
        logger.warning(f"[GENIUS AI] Could not parse response '{response_text}', using first result")
        return results[0]["result"]

    except Exception as e:
        logger.warning(f"[GENIUS AI] Analysis failed: {e}, using simple matching")
        # Fallback to simple matching
        if artist_hint:
            for hit in results[:5]:
                song = hit["result"]
                if artist_hint.lower() in song.get("primary_artist", {}).get("name", "").lower():
                    return song
        return results[0]["result"]


def _scrape_genius_url_sync(url: str) -> dict:
    """Scrape lyrics from a Genius URL using BrightData WebUnlocker."""
    import concurrent.futures

    def _run():
        # Get credentials for WebUnlocker
        bearer_token = os.getenv("BRIGHTDATA_API_TOKEN") or os.getenv("BRIGHTDATA_WEBUNLOCKER_BEARER")
        zone_string = os.getenv("WEB_UNLOCKER_ZONE") or os.getenv("BRIGHTDATA_WEBUNLOCKER_APP_ZONE_STRING")

        if not bearer_token:
            return {"success": False, "error": "BRIGHTDATA_API_TOKEN or BRIGHTDATA_WEBUNLOCKER_BEARER not set"}
        if not zone_string:
            return {"success": False, "error": "WEB_UNLOCKER_ZONE or BRIGHTDATA_WEBUNLOCKER_APP_ZONE_STRING not set"}

        try:
            from brightdata import WebUnlocker
            unlocker = WebUnlocker(BRIGHTDATA_WEBUNLOCKER_BEARER=bearer_token, ZONE_STRING=zone_string)
        except Exception as e:
            return {"success": False, "error": f"Failed to create WebUnlocker: {e}"}

        try:
            result = unlocker.get_source(url)

            if not result.success:
                return {"success": False, "error": f"Scrape failed: {result.error}"}

            html = result.data
            if not html or len(html) < 500:
                return {"success": False, "error": "Empty or too short response"}

            if len(html) < 5000:
                html_lower = html.lower()
                if any(x in html_lower for x in ["access denied", "you have been blocked"]):
                    return {"success": False, "error": "Request was blocked"}

            lyrics_data = _extract_lyrics_from_html(html)
            lyrics_data["url"] = url
            lyrics_data["html_size"] = len(html)
            return lyrics_data

        except Exception as e:
            return {"success": False, "error": f"Scrape error: {type(e).__name__}: {str(e)}"}

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_run)
        return future.result(timeout=120)


@tool
def genius_get_lyrics(song_name: str, artist_name: Optional[str] = None) -> str:
    """Get song lyrics in ONE call - searches Genius and uses AI to pick the best match.

    This is the RECOMMENDED tool for getting lyrics. It:
    1. Searches Genius API for the song
    2. Uses AI (Gemini 3 Flash) to analyze results and pick the BEST match
    3. Scrapes lyrics from ONLY the AI-verified result
    4. Returns everything in one response

    The AI analysis ensures:
    - Correct song is selected even with similar titles
    - Artist matching is intelligent (handles variations)
    - Only ONE URL is scraped (no wasted requests)

    Args:
        song_name: The name of the song
        artist_name: Artist name (recommended for accurate matching)

    Returns:
        JSON with title, artist, lyrics, and source URL
    """
    try:
        # Step 1: Search Genius API
        headers = get_genius_headers()
        if not headers:
            return json.dumps({"success": False, "error": "GENIUS_ACCESS_TOKEN not set"})

        query = f"{song_name} {artist_name}" if artist_name else song_name
        logger.info(f"[GENIUS] Searching for: {query}")

        response = requests.get(
            "https://api.genius.com/search",
            params={"q": query},
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        if "response" not in data or not data["response"].get("hits"):
            return json.dumps({"success": False, "error": "No results found", "query": query})

        hits = data["response"]["hits"]
        logger.info(f"[GENIUS] Found {len(hits)} results, analyzing with AI...")

        # Step 2: Use AI to analyze results and pick the best match
        best_match = _ai_analyze_genius_results(
            query=query,
            results=hits,
            artist_hint=artist_name
        )

        if not best_match:
            return json.dumps({"success": False, "error": "AI could not find a matching result", "query": query})

        song_url = best_match["url"]
        song_title = best_match["title"]
        song_artist = best_match["primary_artist"]["name"]

        logger.info(f"[GENIUS] AI selected: {song_title} by {song_artist}")
        logger.info(f"[GENIUS] Scraping URL: {song_url}")

        # Step 3: Scrape lyrics from the verified URL
        lyrics_result = _scrape_genius_url_sync(song_url)

        if not lyrics_result.get("success"):
            return json.dumps({
                "success": False,
                "error": lyrics_result.get("error", "Failed to scrape lyrics"),
                "song_found": {"title": song_title, "artist": song_artist, "url": song_url}
            })

        # Step 4: Return complete result
        return json.dumps({
            "success": True,
            "title": lyrics_result.get("title") or song_title,
            "artist": lyrics_result.get("artist") or song_artist,
            "lyrics": lyrics_result.get("lyrics"),
            "url": song_url,
            "song_id": best_match["id"]
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"[GENIUS] Error: {type(e).__name__}: {str(e)}")
        return json.dumps({"success": False, "error": f"{type(e).__name__}: {str(e)}"})


# ============================================================================
# Collect All Tools
# ============================================================================

def get_all_tools():
    """Get all available tools based on configured API keys."""
    tools = []

    # BrightData tools (if API token available)
    if os.getenv("BRIGHTDATA_API_TOKEN"):
        tools.extend([
            brightdata_search_google,
            brightdata_search_bing,
            brightdata_scrape_url,
            brightdata_crawl_website,
            brightdata_extract_data,
            brightdata_search_linkedin,
        ])
        logger.info("BrightData tools enabled")
    else:
        logger.warning("BRIGHTDATA_API_TOKEN not set - BrightData tools disabled")

    # Genius tools (if access token available)
    if os.getenv("GENIUS_ACCESS_TOKEN"):
        tools.extend([
            genius_get_lyrics,  # RECOMMENDED: One-call solution for lyrics
            genius_search_song,
            genius_get_song_details,
            genius_get_artist,
        ])
        logger.info("Genius API tools enabled (including genius_get_lyrics)")
    else:
        logger.warning("GENIUS_ACCESS_TOKEN not set - Genius tools disabled")

    return tools


# ============================================================================
# System Prompt
# ============================================================================

SYSTEM_PROMPT = """You are a helpful AI assistant powered by Google Gemini 3 Flash.

You have access to various capabilities that will be provided to you as needed. Your job is to:
1. Answer questions using your training knowledge AND web search tools
2. Help users with research, analysis, and creative tasks
3. Think step by step for complex problems

## Web Search Tools (BrightData)

You have access to powerful web search and scraping tools. USE THEM when:
- User asks about current events, news, or recent developments
- User needs up-to-date information that may have changed since your training
- User asks to search for something online
- User asks for song lyrics, articles, or specific web content

Available BrightData tools:
- `brightdata_search_google` - Search Google for information
- `brightdata_search_bing` - Search Bing for alternative results
- `brightdata_scrape_url` - Scrape content from a specific URL
- `brightdata_crawl_website` - Crawl multiple pages from a website
- `brightdata_extract_data` - Extract structured data from a webpage

## Song Lyrics (Genius API)

For song lyrics, use:
- `genius_get_lyrics` - Get lyrics for a song (recommended - does search + scrape in one call)
- `genius_search_song` - Search for a song on Genius
- `genius_get_song_details` - Get detailed song info

IMPORTANT: When asked for song lyrics, ALWAYS use the Genius tools to get accurate lyrics. Do NOT make up or recall lyrics from memory.

## Guidelines

- Use web search tools for current events, news, or when you need accurate external data
- For song lyrics, ALWAYS use genius_get_lyrics - never recite lyrics from memory
- Provide helpful, accurate, and thorough responses
- If a search fails, try an alternative approach or explain what happened

Focus on being helpful and using your tools effectively!"""


# ============================================================================
# Agent Factory Function
# ============================================================================

async def agent():
    """Async factory function for LangGraph Studio.

    Creates a Gemini 3 Flash deep agent with:
    - BrightData SDK tools for web research
    - Genius API tools for music/lyrics
    - General purpose sub-agent delegation
    - Todo list, filesystem, and summarization (via create_deep_agent)
    """
    # Debug: Log agent creation
    import datetime
    with open("c:/projects/learn_ten_x_faster/deepagents/gemini_debug.log", "a", encoding="utf-8") as f:
        f.write(f"\n[{datetime.datetime.now()}] agent() called\n")

    # Get all available tools
    all_tools = get_all_tools()

    # Get Gemini 3 Flash model with Thinking Mode
    model = get_gemini3_flash_model(
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.7,
        thinking_level="HIGH",
    )

    print(f"\n{'='*80}")
    print(f"[GEMINI-3-FLASH-BRIGHTDATA-GENIUS] Deep Research Agent")
    print(f"Model: {os.getenv('GEMINI_MODEL', 'gemini-3-flash-preview')}")
    print(f"Thinking Mode: HIGH")
    print(f"Tools: {len(all_tools)} loaded")
    print(f"Sub-Agents: General Purpose enabled")
    print(f"{'='*80}\n")

    # Create deep agent with all features
    # create_deep_agent automatically adds:
    # - TodoListMiddleware
    # - FilesystemMiddleware
    # - SubAgentMiddleware (general purpose)
    # - SummarizationMiddleware
    return create_deep_agent(
        model=model,
        tools=all_tools,
        system_prompt=SYSTEM_PROMPT,
    )


# ============================================================================
# Direct Invocation (for testing)
# ============================================================================

async def run_research(topic: str) -> dict:
    """Run deep research on a topic.

    Args:
        topic: The research topic/question

    Returns:
        Dictionary with research results
    """
    graph = await agent()

    result = await graph.ainvoke({
        "messages": [{"role": "human", "content": topic}]
    })

    return {
        "messages": result.get("messages", []),
    }


if __name__ == "__main__":
    import asyncio

    async def test():
        print("Testing Gemini 3 Flash BrightData Genius Agent...")
        result = await run_research("What is the capital of France?")
        print(result)

    asyncio.run(test())
