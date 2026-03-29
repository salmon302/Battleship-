# Battleship++

A simplistic Battleship implementation in Python with Pygame for theoretical game experiments.

## Project Structure
- `src/`: Core game logic, AI algorithms, and UI.
- `tests/`: Unit tests.

## Running the Game
```bash
python src/main.py
```
 
## Setup & Installation

Install dependencies into a virtual environment:

```bash
pip install -r requirements.txt
```

## Running Tests

Tests import the project modules from `src/`. From the repository root either:

POSIX:
```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

PowerShell:
```powershell
$env:PYTHONPATH='src'; python -m unittest discover -s tests -v
```

If tests still fail to import, set `PYTHONPATH` to the absolute `src/` path.

## Headless Batch Simulation

Run multiple AI-vs-AI games without opening a window:

```bash
python src/headless_runner.py --games 10 --players 8 --attack-all
```

Use `--seed` for deterministic/reproducible runs:

```bash
python src/headless_runner.py --games 10 --players 8 --attack-all --seed 42
```
