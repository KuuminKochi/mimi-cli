#!/usr/bin/env python3
import sys
import os

# Add the project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

try:
    from mimi_lib.app import MimiApp
except ImportError as e:
    print(f"Error: Could not import Mimi. Ensure dependencies are installed.\n{e}")
    sys.exit(1)

if __name__ == "__main__":
    app = MimiApp()
    app.run()
