import random
import json
import os
import logging
from pathlib import Path
from typing import Tuple, List, Set, Optional
from engine import Board, Ship, CellStatus

logger = logging.getLogger(__name__)

# Persist AI learning state inside the project's `results/` folder to avoid
# polluting the repo root and to keep run artifacts together.
LEARN_FILE = Path(__file__).resolve().parent.parent / "results" / "ai_learning.json"


def _load_store():
    try:
        if not LEARN_FILE.exists():
            return {}
        with LEARN_FILE.open('r', encoding='utf8') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.exception("Failed to decode AI learning file %s; starting fresh", LEARN_FILE)
        return {}
    except Exception:
        logger.exception("Unexpected error loading AI learning file %s", LEARN_FILE)
        return {}


def _save_store(store):
    try:
        LEARN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LEARN_FILE.open('w', encoding='utf8') as f:
            json.dump(store, f)
    except Exception:
        logger.exception("Failed to save AI learning file %s", LEARN_FILE)

class BaseAI:
    def __init__(self, board: Board):
        self.board = board
        self.shots: Set[Tuple[int, int]] = set()

    def get_shot_coordinates(self) -> Tuple[int, int]:
        raise NotImplementedError
    
    def observe_shot_result(self, x: int, y: int, status: CellStatus, is_sunk: bool):
        """Optional hook for AIs to learn from shot outcomes."""
        return

    def _get_available_shots(self) -> List[Tuple[int, int]]:
        available = []
        for y in range(self.board.height):
            for x in range(self.board.width):
                if (x, y) not in self.shots:
                    available.append((x, y))
        return available

class PlacementAI:
    """Interface for AI-driven ship placement."""
    def __init__(self, board: Board):
        self.board = board

    def place_ships(self, ship_types: List[Tuple[str, int]]):
        raise NotImplementedError

class RandomPlacementAI(PlacementAI):
    """The standard random placement strategy."""
    def place_ships(self, ship_types: List[Tuple[str, int]]):
        for name, size in ship_types:
            placed = False
            while not placed:
                ship = Ship(name, size)
                x = random.randint(0, self.board.width - 1)
                y = random.randint(0, self.board.height - 1)
                horizontal = random.choice([True, False])
                placed = self.board.place_ship(ship, x, y, horizontal)

class EdgePlacementAI(PlacementAI):
    """Prefers placing ships along the edges of the board for survival."""
    def place_ships(self, ship_types: List[Tuple[str, int]]):
        for name, size in ship_types:
            placed = False
            attempts = 0
            while not placed:
                ship = Ship(name, size)
                horizontal = random.choice([True, False])
                # Bias towards edges (0 or max-1)
                if attempts < 50:
                    if random.random() < 0.8:
                        if horizontal:
                            y = random.choice([0, self.board.height - 1])
                            x = random.randint(0, self.board.width - size)
                        else:
                            x = random.choice([0, self.board.width - 1])
                            y = random.randint(0, self.board.height - size)
                    else:
                        x, y = random.randint(0, self.board.width-1), random.randint(0, self.board.height-1)
                else:
                    x, y = random.randint(0, self.board.width-1), random.randint(0, self.board.height-1)
                
                placed = self.board.place_ship(ship, x, y, horizontal)
                attempts += 1

class DistributedPlacementAI(PlacementAI):
    """Try to keep ships away from each other (no adjacent clusters)."""
    def place_ships(self, ship_types: List[Tuple[str, int]]):
        for name, size in ship_types:
            placed = False
            attempts = 0
            while not placed:
                ship = Ship(name, size)
                x = random.randint(0, self.board.width - 1)
                y = random.randint(0, self.board.height - 1)
                horizontal = random.choice([True, False])
                
                # Check if it's too close to existing ships
                too_close = False
                if attempts < 100:
                    dx, dy = (1, 0) if horizontal else (0, 1)
                    for i in range(size):
                        nx, ny = x + i*dx, y + i*dy
                        if not self.board.is_valid_coordinate(nx, ny):
                            too_close = True; break
                        # Check neighbors
                        for ox in range(-1, 2):
                            for oy in range(-1, 2):
                                if self.board.is_valid_coordinate(nx+ox, ny+oy):
                                    if self.board.grid[ny+oy][nx+ox] == CellStatus.SHIP:
                                        too_close = True; break
                        if too_close: break
                
                if not too_close:
                    placed = self.board.place_ship(ship, x, y, horizontal)
                attempts += 1

class OverlapPlacementAI(PlacementAI):
    """Prefers placing ships in high-traffic overlap areas (like the center)."""
    def place_ships(self, ship_types: List[Tuple[str, int]]):
        w, h = self.board.width, self.board.height
        for name, size in ship_types:
            placed = False
            attempts = 0
            while not placed and attempts < 200:
                x = int(random.gauss(w/2, w/4))
                y = int(random.gauss(h/2, h/4))
                x = max(0, min(w-1, x))
                y = max(0, min(h-1, y))
                
                horizontal = random.choice([True, False])
                ship = Ship(name, size)
                placed = self.board.place_ship(ship, x, y, horizontal)
                attempts += 1

class StatisticalAI(BaseAI):
    """PDM simulator."""
    def __init__(self, board: Board, ship_sizes: List[int] = None):
        super().__init__(board)
        self.ship_sizes = ship_sizes or [5, 4, 3, 3, 2]

    def get_probability_map(self) -> List[List[int]]:
        width, height = self.board.width, self.board.height
        p_map = [[0 for _ in range(width)] for _ in range(height)]
        for size in self.ship_sizes:
            # Horizontal
            for y in range(height):
                for x in range(width - size + 1):
                    valid = True
                    for i in range(size):
                        if self.board.grid[y][x+i] == CellStatus.MISS:
                            valid = False; break
                    if valid:
                        for i in range(size): p_map[y][x+i] += 1
            # Vertical
            for x in range(width):
                for y in range(height - size + 1):
                    valid = True
                    for i in range(size):
                        if self.board.grid[y+i][x] == CellStatus.MISS:
                            valid = False; break
                    if valid:
                        for i in range(size): p_map[y+i][x] += 1
        return p_map

    def get_shot_coordinates(self) -> Tuple[int, int]:
        p_map = self.get_probability_map()
        available = []
        max_prob = -1
        min_size = min(self.ship_sizes) if self.ship_sizes else 2
        for y in range(self.board.height):
            for x in range(self.board.width):
                if (x, y) not in self.shots:
                    if (x + y) % min_size == 0:
                        prob = p_map[y][x]
                        if prob > max_prob:
                            max_prob = prob; available = [(x, y)]
                        elif prob == max_prob:
                            available.append((x, y))
        if not available:
            available = self._get_available_shots()
        shot = random.choice(available)
        self.shots.add(shot)
        return shot

class RandomAI(BaseAI):
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        if not available: return (0, 0)
        shot = random.choice(available)
        self.shots.add(shot)
        return shot

class ParityAI(BaseAI):
    def __init__(self, board: Board, parity: int = 2):
        super().__init__(board)
        self.parity = parity
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        checkered = [(x, y) for (x, y) in available if (x + y) % self.parity == 0]
        shot = random.choice(checkered if checkered else available)
        self.shots.add(shot)
        return shot

class HuntAndTargetAI(BaseAI):
    def __init__(self, board: Board, parity: int = 2):
        super().__init__(board)
        self.targets: List[Tuple[int, int]] = []
        self.parity = parity
    def get_shot_coordinates(self) -> Tuple[int, int]:
        if self.targets:
            shot = self.targets.pop(0)
            self.shots.add(shot)
            return shot
        available = self._get_available_shots()
        checkered = [(x, y) for (x, y) in available if (x + y) % self.parity == 0]
        shot = random.choice(checkered if checkered else available)
        self.shots.add(shot)
        return shot
    def report_hit(self, x: int, y: int, is_sunk: bool):
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = x + dx, y + dy
            if (0 <= nx < self.board.width and 0 <= ny < self.board.height and 
                (nx, ny) not in self.shots and (nx, ny) not in self.targets):
                self.targets.append((nx, ny))

class QLearningAI(BaseAI):
    def __init__(self, board: Board, alpha: float = 0.3, epsilon: float = 0.1, persist: bool = True):
        super().__init__(board)
        self.alpha, self.epsilon, self.persist = alpha, epsilon, persist
        size_key = f"{board.width}x{board.height}"
        store = _load_store()
        q_table = store.get(size_key, {}).get('q') if isinstance(store.get(size_key), dict) else None
        if q_table and len(q_table) == board.height: self.q = q_table
        else: self.q = [[0.0 for _ in range(board.width)] for _ in range(board.height)]
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        if not available: return (0,0)
        if random.random() < self.epsilon: shot = random.choice(available)
        else: shot = max(available, key=lambda c: self.q[c[1]][c[0]])
        self.shots.add(shot)
        return shot
    def observe_shot_result(self, x: int, y: int, status: CellStatus, is_sunk: bool):
        reward = 1.0 if status == CellStatus.HIT else 0.0
        old = self.q[y][x]
        self.q[y][x] = old + self.alpha * (reward - old)
        if self.persist:
            store = _load_store()
            size_key = f"{self.board.width}x{self.board.height}"
            size_entry = store.get(size_key, {}) if isinstance(store.get(size_key), dict) else {}
            size_entry['q'] = self.q
            store[size_key] = size_entry
            _save_store(store)

class HeatmapAI(BaseAI):
    def __init__(self, board: Board, persist: bool = True):
        super().__init__(board)
        self.persist = persist
        size_key = f"{board.width}x{board.height}"
        store = _load_store()
        heatmap = store.get(size_key, {}).get('heatmap') if isinstance(store.get(size_key), dict) else None
        if heatmap and len(heatmap) == board.height: self.heatmap = heatmap
        else: self.heatmap = [[1.0 for _ in range(board.width)] for _ in range(board.height)]
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        if not available: return (0, 0)
        weights = [self.heatmap[y][x] + 1e-6 for (x, y) in available]
        total = sum(weights)
        r = random.random() * total
        upto = 0.0
        for idx, w in enumerate(weights):
            upto += w
            if r <= upto:
                self.shots.add(available[idx])
                return available[idx]
        shot = random.choice(available)
        self.shots.add(shot)
        return shot
    def observe_shot_result(self, x: int, y: int, status: CellStatus, is_sunk: bool):
        if status == CellStatus.HIT: self.heatmap[y][x] += 5.0
        else: self.heatmap[y][x] = max(0.01, self.heatmap[y][x] * 0.95)
        if self.persist:
            store = _load_store()
            size_key = f"{self.board.width}x{self.board.height}"
            size_entry = store.get(size_key, {}) if isinstance(store.get(size_key), dict) else {}
            size_entry['heatmap'] = self.heatmap
            store[size_key] = size_entry
            _save_store(store)

class SpiralAI(BaseAI):
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        cx, cy = self.board.width // 2, self.board.height // 2
        available.sort(key=lambda c: (c[0]-cx)**2 + (c[1]-cy)**2)
        shot = available[0]
        self.shots.add(shot)
        return shot

class EdgePreferAI(BaseAI):
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        w, h = self.board.width, self.board.height
        edges = [(x, y) for (x, y) in available if x == 0 or x == w-1 or y == 0 or y == h-1]
        shot = random.choice(edges if edges else available)
        self.shots.add(shot)
        return shot

def create_pve_ai(ai_type: str, board: Board):
    """Factory to create a PvE AI instance by name.

    Supports common names: 'HuntAndTarget', 'Statistical', 'MonteCarlo',
    'Random', 'Checkerboard', 'Spiral', 'EdgePrefer', 'Sequential',
    'Heatmap', 'QLearning'. The Monte Carlo implementation is imported
    lazily to avoid circular imports.
    """
    if not isinstance(ai_type, str):
        ai_type = str(ai_type)
    key = ai_type.strip().lower()

    if key in ("huntandtarget", "hunt_and_target", "hunt-and-target", "hunt"):
        return HuntAndTargetAI(board)
    if key in ("statistical", "pdm"):
        return StatisticalAI(board)
    if key in ("montecarlo", "monte-carlo", "mcs", "mc"):
        # import here to avoid circular import at module import time
        from mcs import MonteCarloAI
        return MonteCarloAI(board)
    if key in ("random", "rand"):
        return RandomAI(board)
    if key in ("checkerboard", "checker"):
        return CheckerboardAI(board)
    if key in ("spiral",):
        return SpiralAI(board)
    if key in ("edgeprefer", "edge"):
        return EdgePreferAI(board)
    if key in ("sequential",):
        return SequentialAI(board)
    if key in ("heatmap",):
        return HeatmapAI(board)
    if key in ("qlearning", "ql", "qlearn"):
        return QLearningAI(board)

    # Fallback to HuntAndTarget for unknown names
    return HuntAndTargetAI(board)

class SequentialAI(BaseAI):
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        available.sort(key=lambda c: (c[1], c[0]))
        shot = available[0]
        self.shots.add(shot)
        return shot

class CheckerboardAI(BaseAI):
    def get_shot_coordinates(self) -> Tuple[int, int]:
        available = self._get_available_shots()
        checkered = [(x, y) for (x, y) in available if (x + y) % 2 == 0]
        shot = random.choice(checkered if checkered else available)
        self.shots.add(shot)
        return shot
