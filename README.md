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

## High-Throughput Benchmark Mode

For large experiments, use benchmark mode to produce aggregate strength metrics
(win rate, accuracy, survival, Elo-like rating, composite strength index):

```bash
python src/headless_runner.py --games 200 --players 10 --attack-all --benchmark --workers 6 --seed 42 --no-per-game
```

Useful options:

- `--workers`: number of worker processes for parallel game execution.
- `--benchmark`: enable robust aggregate reporting.
- `--no-per-game`: skip per-game JSON logs for higher throughput.
- `--output-prefix`: custom prefix for aggregate benchmark output files.

Benchmark mode writes:

- JSON report: `results/<prefix>_<timestamp>.json`
- CSV leaderboard: `results/<prefix>_<timestamp>.csv`

## Human Difficulty Search (Knowledge Graph + Evolution)

Search for hard human-opponent profiles experimentally:

```bash
python src/difficulty_lab.py --generations 8 --population 16 --games-per-eval 2 --seed 42
```

This writes:

- Profile pack: `results/human_opponents.json`
- Search report: `results/difficulty_search_<timestamp>.json`

You can point PvE profile loading to a custom profile pack with:

```powershell
$env:BATTLESHIP_PROFILE_FILE = "results/human_opponents.json"
python src/main.py
```
