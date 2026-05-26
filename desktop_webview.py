# launcher.py - Opens in default browser automatically
import threading
import uvicorn
import sys
import os
import socket
import webbrowser
import time

def find_free_port():
    """Find a free port to use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def run_server(port):
    """Run the FastAPI server"""
    # Import app here to avoid circular imports
    from main import app
    
    config = uvicorn.Config(
        app, 
        host="127.0.0.1", 
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()

def open_browser(port):
    """Open the default browser after a short delay"""
    time.sleep(2)  # Wait for server to start
    url = f"http://127.0.0.1:{port}"
    webbrowser.open(url)
    print(f"Browser opened at {url}")

def main():
    """Main function to launch the application"""
    port = find_free_port()
    
    print("="*60)
    print("SCHOOL MANAGEMENT SYSTEM")
    print("="*60)
    print(f"Starting server on port {port}...")
    print("Opening browser...")
    print("="*60)
    
    # Start the server in background thread
    server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
    server_thread.start()
    
    # Open browser
    open_browser(port)
    
    # Keep the application running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)

if __name__ == '__main__':
    main()