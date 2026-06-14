#!/usr/bin/env python3
"""
Python version detection script for Salva Runtime.

Checks if the current Python version meets the minimum requirement (3.11+).
"""
import subprocess
import sys


def get_python_version() -> tuple[int, int, int]:
    """Get Python version as tuple (major, minor, patch)"""
    return sys.version_info[:3]


def get_python_version_string() -> str:
    """Get Python version as string"""
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def check_minimum_version(min_major: int = 3, min_minor: int = 11) -> bool:
    """Check if Python version meets minimum requirement"""
    current = get_python_version()
    return current >= (min_major, min_minor, 0)


def check_venv() -> dict:
    """Check if running in a virtual environment"""
    in_venv = hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    
    venv_path = getattr(sys, 'prefix', None)
    
    return {
        "in_venv": in_venv,
        "venv_path": venv_path,
        "executable": sys.executable,
    }


def check_available_pythons() -> list[dict]:
    """Check available Python installations on the system"""
    python_versions = []
    
    # Common Python paths to check
    paths_to_check = [
        "/usr/bin/python3",
        "/usr/local/bin/python3",
        "/opt/homebrew/bin/python3",
        "/opt/homebrew/bin/python3.11",
        "/opt/homebrew/bin/python3.12",
        "/opt/homebrew/bin/python3.13",
        "/opt/homebrew/bin/python3.14",
    ]
    
    for path in paths_to_check:
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                # Extract version number
                version_line = result.stdout.strip() or result.stderr.strip()
                if "Python" in version_line:
                    version = version_line.replace("Python", "").strip()
                    try:
                        major, minor = version.split(".")[:2]
                        python_versions.append({
                            "path": path,
                            "version": version,
                            "major": int(major),
                            "minor": int(minor),
                        })
                    except (ValueError, IndexError):
                        pass
        except (subprocess.TimeoutExpired, FileNotFoundError, PermissionError):
            continue
    
    return python_versions


def main():
    """Main entry point"""
    print("=" * 60)
    print("Salva Runtime - Python Version Check")
    print("=" * 60)
    
    # Current Python version
    current = get_python_version()
    current_str = get_python_version_string()
    
    print(f"\nCurrent Python: {current_str}")
    print(f"Executable: {sys.executable}")
    
    # Virtual environment check
    venv_info = check_venv()
    if venv_info["in_venv"]:
        print("Virtual Environment: ✅ Active")
        print(f"  Path: {venv_info['venv_path']}")
    else:
        print("Virtual Environment: ⚠️  Not active")
    
    # Version check
    if check_minimum_version():
        print("\n✅ Python version OK (>= 3.11)")
    else:
        print("\n❌ Python version too old (requires >= 3.11)")
        print("\nAvailable Python installations:")
        
        available = check_available_pythons()
        if available:
            for py in sorted(available, key=lambda x: (x["major"], x["minor"]), reverse=True):
                status = "✅ meets requirement" if (py["major"], py["minor"]) >= (3, 11) else "❌ too old"
                print(f"  {py['path']} -> Python {py['version']} {status}")
        else:
            print("  No additional Python installations found")
        
        print("\nTo fix:")
        print("  1. Install Python 3.11+: https://www.python.org/downloads/")
        print("  2. Or use pyenv: brew install pyenv && pyenv install 3.11")
        print("  3. Or use conda: conda create -n salva python=3.11")
        
        return 1
    
    # Requirements check
    print("\nChecking runtime dependencies...")
    required_modules = ["fastapi", "httpx", "pydantic", "uvicorn"]
    missing = []
    
    for module in required_modules:
        try:
            __import__(module)
            print(f"  ✅ {module}")
        except ImportError:
            print(f"  ❌ {module} (missing)")
            missing.append(module)
    
    if missing:
        print(f"\n⚠️  Missing modules: {', '.join(missing)}")
        print("Install with: pip install " + " ".join(missing))
    
    print("\n" + "=" * 60)
    print("Check complete!")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())