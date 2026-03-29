import sys
from pathlib import Path
p = Path(sys.argv[1])
lines = p.read_text(encoding='utf-8').splitlines()
for i, line in enumerate(lines, start=1):
    print(f"{i:04d}: {line.rstrip()}")
