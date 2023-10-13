from pathlib import Path
import os
import sys

def wa():
    print(str(os.path.dirname(os.path.realpath(sys.executable))))

wa()