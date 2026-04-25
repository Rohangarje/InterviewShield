#!/usr/bin/env python
import subprocess
import sys

print("Installing required dependencies...")
subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'])
print("✅ All dependencies installed!")
