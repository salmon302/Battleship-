import random
from typing import List, Tuple, Set
from engine import Board, Ship, CellStatus
from ai import BaseAI

class MonteCarloPlacement:
    """
    Given a partially hit board and a list of remaining ships,
    find the best placement for the remaining hits.
    """
    def __init__(self, board: Board, remaining_ship_sizes: List[int]):
        self.board = board
        self.remaining_sizes = remaining_ship_sizes

    def run_simulation(self, iterations: int = 1000) -> List[List[float]]:
        width, height = self.board.width, self.board.height
        hit_counts = [[0 for _ in range(width)] for _ in range(height)]
        
        # Get all current hits and misses
        current_grid = self.board.grid
        successful_sims = 0
        
        for _ in range(iterations):
            temp_board = Board(width, height)
            # Reconstruct the board with MISSES as obstacles
            for y in range(height):
                for x in range(width):
                    if current_grid[y][x] == CellStatus.MISS:
                        # Mark it as HIT temporarily to prevent placement
                        temp_board.grid[y][x] = CellStatus.HIT
            
            # Try to place ships randomly
            placed_all = True
            for size in self.remaining_sizes:
                placed = False
                for _ in range(100): # 100 attempts per ship
                    rx, ry = random.randint(0, width-1), random.randint(0, height-1)
                    horiz = random.choice([True, False])
                    s = Ship(f"T{size}", size)
                    if temp_board.place_ship(s, rx, ry, horiz):
                        placed = True
                        break
                if not placed:
                    placed_all = False
                    break
            
            if placed_all:
                successful_sims += 1
                for ship in temp_board.ships:
                    for x, y in ship.coordinates:
                        hit_counts[y][x] += 1
        
        if successful_sims == 0:
            return [[0.0 for _ in range(width)] for _ in range(height)]
            
        return [[count / successful_sims for count in row] for row in hit_counts]

class MonteCarloAI(BaseAI):
    """
    AI that uses Monte Carlo simulations to find the highest probability targets.
    """
    def __init__(self, board: Board, ship_sizes: List[int] = None, iterations: int = 500):
        super().__init__(board)
        self.ship_sizes = ship_sizes or [5, 4, 3, 3, 2]
        self.iterations = iterations
        self.mc = MonteCarloPlacement(board, self.ship_sizes)

    def get_shot_coordinates(self) -> Tuple[int, int]:
        # Run simulation to get probability map
        p_map = self.mc.run_simulation(self.iterations)
        
        width, height = self.board.width, self.board.height
        max_prob = -1.0
        best_shots = []

        for y in range(height):
            for x in range(width):
                if (x, y) not in self.shots:
                    prob = p_map[y][x]
                    if prob > max_prob:
                        max_prob = prob
                        best_shots = [(x, y)]
                    elif abs(prob - max_prob) < 1e-6:
                        best_shots.append((x, y))

        if not best_shots:
            # Fallback if no simulations succeeded or board is full
            available = [(x, y) for y in range(height) for x in range(width) if (x, y) not in self.shots]
            shot = random.choice(available) if available else (0, 0)
        else:
            shot = random.choice(best_shots)
            
        self.shots.add(shot)
        return shot
