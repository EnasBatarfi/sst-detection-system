"""
Python usercustomize.py - Alternative auto-load mechanism

This is executed after sitecustomize.py. Place in:
- Unix: ~/.local/lib/python3.X/site-packages/
- Windows: %APPDATA%\Python\Python3X\site-packages\

Or set PYTHONPATH to include this directory.
"""

import sitecustomize
