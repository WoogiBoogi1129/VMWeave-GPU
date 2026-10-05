"""Read losslessly archived logs without requiring campaign credentials or hardware."""
import lzma
from pathlib import Path

def read_text(path):
    path=Path(path)
    if path.exists():return path.read_text()
    return lzma.open(str(path)+'.xz','rt').read()

def exists(path):
    path=Path(path)
    return path.exists() or Path(str(path)+'.xz').exists()
