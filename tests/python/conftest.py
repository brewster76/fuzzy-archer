import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BIN = os.path.join(ROOT, 'bin')
if BIN not in sys.path:
    sys.path.insert(0, BIN)

# WeeWX sources for integration tests: set WEEWX_SRC to the "src" directory of a WeeWX 5.5.x checkout.
WEEWX_SRC = os.environ.get('WEEWX_SRC')
if WEEWX_SRC and WEEWX_SRC not in sys.path:
    sys.path.insert(0, WEEWX_SRC)
