#!/usr/bin/env python3
"""
RALPH Installation Script

Sets up a virtual environment and installs all required dependencies.
"""

import subprocess
import sys
from pathlib import Path
import os

def print_header(text):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")

def run_command(cmd, description, cwd=None):
    """Run a command and handle errors"""
    print(f"→ {description}...")
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        if result.stdout.strip():
            print(f"  {result.stdout.strip()}")
        print(f"  ✓ Done")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Failed: {e}")
        if e.stderr:
            print(f"  Error: {e.stderr}")
        return False

def main():
    print_header("RALPH v0.1 Installation")
    
    # Get script directory
    script_dir = Path(__file__).parent
    venv_dir = script_dir / ".venv"
    
    print(f"Installation directory: {script_dir}")
    print(f"Virtual environment: {venv_dir}")
    
    # Step 1: Check Python version
    print_header("Step 1: Checking Python Version")
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
        print("✗ Python 3.8 or higher is required")
        sys.exit(1)
    print("✓ Python version OK")
    
    # Step 2: Create virtual environment
    print_header("Step 2: Creating Virtual Environment")
    
    if venv_dir.exists():
        print(f"Virtual environment already exists at {venv_dir}")
        response = input("Remove and recreate? [y/N]: ").strip().lower()
        if response == 'y':
            import shutil
            print("→ Removing existing venv...")
            shutil.rmtree(venv_dir)
            print("  ✓ Done")
        else:
            print("  Keeping existing venv")
    
    if not venv_dir.exists():
        if not run_command(
            f"{sys.executable} -m venv .venv",
            "Creating virtual environment",
            cwd=script_dir
        ):
            print("\n✗ Failed to create virtual environment")
            sys.exit(1)
    
    # Determine activation script and pip path
    if sys.platform == "win32":
        activate_script = venv_dir / "Scripts" / "activate"
        pip_path = venv_dir / "Scripts" / "pip"
        python_path = venv_dir / "Scripts" / "python"
    else:
        activate_script = venv_dir / "bin" / "activate"
        pip_path = venv_dir / "bin" / "pip"
        python_path = venv_dir / "bin" / "python"
    
    # Step 3: Upgrade pip
    print_header("Step 3: Upgrading pip")
    if not run_command(
        f"{python_path} -m pip install --upgrade pip",
        "Upgrading pip",
        cwd=script_dir
    ):
        print("⚠️  Warning: pip upgrade failed, continuing anyway...")
    
    # Step 4: Install dependencies
    print_header("Step 4: Installing Dependencies")
    
    dependencies = [
        "requests>=2.28.0",
    ]
    
    print("Required packages:")
    for dep in dependencies:
        print(f"  - {dep}")
    print()
    
    for dep in dependencies:
        if not run_command(
            f"{pip_path} install {dep}",
            f"Installing {dep}",
            cwd=script_dir
        ):
            print(f"\n✗ Failed to install {dep}")
            sys.exit(1)
    
    # Step 5: Verify installation
    print_header("Step 5: Verifying Installation")
    
    # Test import
    test_cmd = f"{python_path} -c 'import requests; import ralph; print(\"✓ All imports successful\")'"
    if run_command(test_cmd, "Testing imports", cwd=script_dir):
        print("\n✓ Installation verified successfully")
    else:
        print("\n⚠️  Warning: Import test failed, but dependencies are installed")
    
    # Final instructions
    print_header("Installation Complete!")
    
    print("To activate the virtual environment:")
    if sys.platform == "win32":
        print(f"  .venv\\Scripts\\activate")
    else:
        print(f"  source .venv/bin/activate")
    
    print("\nTo run RALPH:")
    print(f"  {python_path} run_ralph.py --goal 'Your task here'")
    
    print("\nOr activate the venv first, then:")
    print(f"  python3 run_ralph.py --goal 'Your task here'")
    
    print("\nQuick verification:")
    print(f"  {python_path} quick_check.py")
    
    print("\nFor more information, see:")
    print("  README.md")
    print("  docs/QUICKSTART.md")
    print("  docs/INDEX.md")
    
    print("\n" + "="*60)
    print("  Ready to use RALPH! 🚀")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Installation cancelled by user\n")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n✗ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
