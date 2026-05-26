# launcher.py - COMPLETE WORKING VERSION
import threading
import uvicorn
import sys
import os
import socket
import webbrowser
import time
import subprocess

def find_free_port():
    """Find a free port to use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def get_base_path():
    """Get the base path for templates and static files"""
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return sys._MEIPASS
    else:
        # Running as script
        return os.path.dirname(os.path.abspath(__file__))

def install_missing_packages():
    """Install missing packages if needed"""
    packages = ['fastapi', 'uvicorn', 'jinja2', 'reportlab']
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            print(f"Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def run_server(port):
    """Run the FastAPI server"""
    # Install missing packages first
    install_missing_packages()
    
    # Set the base path for templates
    base_path = get_base_path()
    os.environ['BASE_PATH'] = base_path
    
    # Add current directory to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import app here
    try:
        from main import app
    except Exception as e:
        print(f"Error importing main: {e}")
        # Try alternative import
        import importlib.util
        spec = importlib.util.spec_from_file_location("main", os.path.join(get_base_path(), "main.py"))
        main_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(main_module)
        app = main_module.app
    
    config = uvicorn.Config(
        app, 
        host="127.0.0.1", 
        port=port,
        log_level="info",
        access_log=True
    )
    server = uvicorn.Server(config)
    server.run()

def open_browser(port):
    """Open the default browser after a short delay"""
    time.sleep(3)
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
    print("\nIf browser doesn't open automatically, go to:")
    print(f"http://127.0.0.1:{port}")
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