#!/usr/bin/env python3
"""
Web Dashboard Startup Script for AI Job Agent
"""
import os
import sys
import uvicorn
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

def main():
    """Run the web dashboard"""
    # Set environment variables if not already set
    if not os.getenv("PYTHONPATH"):
        os.environ["PYTHONPATH"] = str(src_path)
    
    # Import and run the FastAPI app
    from web.app import app
    from config import config
    
    # Get web configuration
    web_config = config.web_config
    host = web_config.get("host", "0.0.0.0")
    port = web_config.get("port", 8000)
    debug = web_config.get("debug", True)
    
    print(f"🚀 Starting AI Job Agent Web Dashboard...")
    print(f"📍 Server: http://{host}:{port}")
    print(f"🔧 Debug mode: {debug}")
    print(f"📁 Working directory: {Path.cwd()}")
    
    # Run the server
    uvicorn.run(
        "web.app:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if debug else "warning"
    )

if __name__ == "__main__":
    main()
