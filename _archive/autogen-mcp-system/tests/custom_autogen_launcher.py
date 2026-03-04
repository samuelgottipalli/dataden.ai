# run_autogen_studio_fixed.py
# Custom AutoGen Studio launcher with extended timeouts for cloud models

import uvicorn
import sys
import os

def start_autogen_studio_with_timeouts():
    """
    Start AutoGen Studio with custom timeout settings
    optimized for cloud-based Ollama models
    """
    
    print("="*60)
    print("STARTING AUTOGEN STUDIO (Custom Configuration)")
    print("="*60)
    print("Optimized for: gpt-oss:120b-cloud")
    print("Timeouts: Extended for cloud inference")
    print("="*60)
    
    # Import AutoGen Studio app
    try:
        from autogenstudio.web.app import app
    except ImportError:
        print("ERROR: AutoGen Studio not installed")
        print("Install with: pip install autogen-studio")
        sys.exit(1)
    
    # Configure uvicorn with extended timeouts
    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=8081,
        
        # HTTP timeouts
        timeout_keep_alive=300,      # Keep connections alive for 5 minutes
        timeout_notify=180,           # Notify before timeout at 3 minutes
        
        # WebSocket settings (critical for agent conversations)
        ws_ping_interval=30,          # Ping every 30 seconds to keep alive
        ws_ping_timeout=180,          # WebSocket timeout: 3 minutes
        ws_max_size=16777216,         # 16MB max message size
        
        # General settings
        log_level="info",
        access_log=True,
        
        # Disable auto-reload for stability
        reload=False,
    )
    
    print("\nConfiguration:")
    print(f"  - Host: {config.host}:{config.port}")
    print(f"  - HTTP Keep-Alive: {config.timeout_keep_alive}s")
    # print(f"  - WebSocket Timeout: {ws_ping_timeout}s")
    # print(f"  - WebSocket Ping: Every {ws_ping_interval}s")
    print("\nServer URL: http://127.0.0.1:8081")
    print("\nPress Ctrl+C to stop")
    print("="*60)
    print()
    
    # Start server
    server = uvicorn.Server(config)
    server.run()

if __name__ == "__main__":
    try:
        start_autogen_studio_with_timeouts()
    except KeyboardInterrupt:
        print("\n\nShutting down AutoGen Studio...")
        print("Goodbye!")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
