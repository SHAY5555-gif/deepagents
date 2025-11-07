"""
MCP Server Configuration for Deep Agents
This file contains the configuration for enabled MCP servers
Based on the original Claude Dev MCP settings.
"""
import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_enabled_mcp_tools():
    """
    Get tools from all enabled MCP servers from the original configuration.
    
    Enabled servers:
    1. windows-cli
    2. github.com/mendableai/firecrawl-mcp-server  
    3. chrome-devtools-local
    """
    
    # MCP servers configuration - converted from the JSON settings
    mcp_config = {
        # Windows CLI server (stdio)
        "windows-cli": {
            "command": "npx",
            "args": [
                "-y",
                "@simonb97/server-win-cli",
                "--config",
                "C:/Users/yesha/.win-cli-mcp/config.json"
            ],
            "transport": "stdio"
        },
        
        # Firecrawl server (stdio with API key)
        "firecrawl-mcp-server": {
            "command": "npx", 
            "args": [
                "-y",
                "firecrawl-mcp"
            ],
            "env": {
                "FIRECRAWL_API_KEY": "fc-0bed08c54ba34a349ef512c32d1a8328"
            },
            "transport": "stdio"
        },
        
        # Chrome DevTools Local server (stdio)
        "chrome-devtools-local": {
            "command": "npx",
            "args": [
                "-y", 
                "@shay-avitan/chrome-devtools-mcp-local@latest"
            ],
            "transport": "stdio"
        }
    }
    
    try:
        print("Connecting to enabled MCP servers...")
        mcp_client = MultiServerMCPClient(mcp_config)
        tools = await mcp_client.get_tools()
        
        print(f"Successfully connected to {len(mcp_config)} MCP servers:")
        for server_name in mcp_config.keys():
            print(f"  - {server_name}")
        print(f"Total tools available: {len(tools)}")
        
        return tools, mcp_client
        
    except Exception as e:
        print(f"Error connecting to MCP servers: {e}")
        # Fallback: return empty tools if connection fails
        return [], None


# Auto-approve configurations (for reference)
AUTO_APPROVE_WINDOWS_CLI = [
    "execute_command",
    "get_command_history", 
    "ssh_execute",
    "ssh_disconnect",
    "create_ssh_connection",
    "read_ssh_connections",
    "update_ssh_connection",
    "delete_ssh_connection",
    "get_current_directory"
]

AUTO_APPROVE_FIRECRAWL = [
    "firecrawl_scrape",
    "firecrawl_map", 
    "firecrawl_search",
    "firecrawl_crawl",
    "firecrawl_check_crawl_status",
    "firecrawl_extract"
]

AUTO_APPROVE_CHROME_DEVTOOLS = [
    "list_console_messages",
    "emulate_cpu",
    "emulate_network", 
    "click",
    "drag",
    "fill",
    "fill_form",
    "hover",
    "upload_file",
    "get_network_request",
    "list_network_requests",
    "close_page",
    "handle_dialog",
    "list_pages",
    "navigate_page",
    "navigate_page_history",
    "new_page",
    "new_page_default", 
    "resize_page",
    "select_page",
    "performance_analyze_insight",
    "performance_start_trace",
    "performance_stop_trace",
    "take_screenshot",
    "evaluate_script",
    "take_snapshot",
    "wait_for",
    "press_key"
]


if __name__ == "__main__":
    # Test the MCP connection
    async def test_mcp():
        tools, client = await get_enabled_mcp_tools()
        if tools:
            print(f"\\nAvailable MCP tools:")
            for tool in tools[:5]:  # Show first 5 tools
                print(f"  - {tool.name}: {tool.description}")
            if len(tools) > 5:
                print(f"  ... and {len(tools) - 5} more tools")
    
    asyncio.run(test_mcp())