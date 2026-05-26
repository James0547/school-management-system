# build_exe.py - SIMPLIFIED WORKING VERSION
import os
import sys
import subprocess
import shutil

def clean_build():
    """Clean previous build files"""
    folders_to_clean = ['build', 'dist', '__pycache__']
    for folder in folders_to_clean:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
                print(f"Cleaned {folder}")
            except:
                print(f"Could not clean {folder}")
    
    spec_files = [f for f in os.listdir('.') if f.endswith('.spec')]
    for spec in spec_files:
        try:
            os.remove(spec)
            print(f"Removed {spec}")
        except:
            pass

def build_exe():
    """Build the executable"""
    
    # First install required packages
    print("\nInstalling required packages...")
    packages = ['pyinstaller', 'fastapi', 'uvicorn', 'jinja2', 'reportlab']
    for package in packages:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--quiet"])
    
    # Create templates directory if it doesn't exist
    if not os.path.exists("templates"):
        os.makedirs("templates")
        print("Created templates directory")
    
    if not os.path.exists("static"):
        os.makedirs("static")
        print("Created static directory")
    
    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name=SchoolManagement",
        "--add-data=templates;templates",
        "--add-data=static;static",
        "--hidden-import=uvicorn",
        "--hidden-import=uvicorn.lifespan.off",
        "--hidden-import=uvicorn.lifespan.on",
        "--hidden-import=uvicorn.loops.auto",
        "--hidden-import=uvicorn.protocols.http.auto",
        "--hidden-import=uvicorn.protocols.websockets.auto",
        "--hidden-import=uvicorn.logging",
        "--hidden-import=reportlab",
        "--hidden-import=fastapi",
        "--hidden-import=jinja2",
        "--hidden-import=starlette",
        "--hidden-import=sqlite3",
        "--hidden-import=webbrowser",
        "--hidden-import=socket",
        "--hidden-import=threading",
        "--hidden-import=jinja2.ext",
        "--collect-all=fastapi",
        "--collect-all=starlette",
        "--collect-all=jinja2",
        "--collect-all=uvicorn",
        "launcher.py"
    ]
    
    print("\n" + "="*60)
    print("Building executable...")
    print("="*60)
    print("Command:", " ".join(cmd))
    print("="*60)
    
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        print("\n" + "="*60)
        print("✅ BUILD SUCCESSFUL!")
        print(f"Executable created at: dist/SchoolManagement.exe")
        print("="*60)
        
        # Create portable version
        portable_dir = "SchoolManagement_Portable"
        if os.path.exists(portable_dir):
            shutil.rmtree(portable_dir)
        
        os.makedirs(portable_dir, exist_ok=True)
        
        # Copy exe
        if os.path.exists("dist/SchoolManagement.exe"):
            shutil.copy2("dist/SchoolManagement.exe", portable_dir)
        
        # Copy templates
        if os.path.exists("templates"):
            shutil.copytree("templates", os.path.join(portable_dir, "templates"), dirs_exist_ok=True)
        
        # Copy static
        if os.path.exists("static"):
            shutil.copytree("static", os.path.join(portable_dir, "static"), dirs_exist_ok=True)
        
        # Create start batch file
        with open(os.path.join(portable_dir, "Start School System.bat"), "w") as f:
            f.write('@echo off\n')
            f.write('title School Management System\n')
            f.write('color 0A\n')
            f.write('echo Starting School Management System...\n')
            f.write('echo.\n')
            f.write('start "" "SchoolManagement.exe"\n')
            f.write('echo Application started! Check your browser.\n')
            f.write('echo.\n')
            f.write('pause\n')
        
        print(f"\n✅ Portable version created in: {portable_dir}/")
        print("\nTo run the portable version:")
        print(f"   1. Go to {portable_dir} folder")
        print("   2. Double-click 'Start School System.bat'")
        
    else:
        print("\n❌ BUILD FAILED!")
        print("Trying alternative build method...")
        
        # Alternative build method without --onefile
        cmd2 = [
            sys.executable, "-m", "PyInstaller",
            "--name=SchoolManagement",
            "--add-data=templates;templates",
            "--add-data=static;static",
            "launcher.py"
        ]
        result2 = subprocess.run(cmd2)
        
        if result2.returncode == 0:
            print("\n✅ BUILD SUCCESSFUL (folder mode)!")
            print(f"Executable created at: dist/SchoolManagement/SchoolManagement.exe")
        else:
            print("\n❌ BUILD FAILED! Please check errors above.")
    
    return result.returncode

if __name__ == "__main__":
    print("="*60)
    print("SCHOOL MANAGEMENT SYSTEM - EXE BUILDER")
    print("="*60)
    print("\nThis will create a standalone EXE file.")
    print("\nPress Enter to continue...")
    input()
    
    clean_build()
    exit_code = build_exe()
    
    print("\n" + "="*60)
    if exit_code == 0:
        print("BUILD COMPLETE! Press Enter to exit.")
    else:
        print("BUILD FAILED! Press Enter to exit.")
    input()
    sys.exit(exit_code)