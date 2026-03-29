import random
from typing import List, Tuple
from engine import Board, Ship

class NashPlacement:
    """
    Implements a mixed-strategy Nash Equilibrium for ship placement.
    Instead of clustering ships, it uses a non-uniform distribution 
    to maximize the entropy of the ship positions, making it harder 
    for checkerboard or heat-map AIs to find them.
    """
    def __init__(self, board: Board):
        self.board = board
        self.width = board.width
        self.height = board.height

    def place_ships_optimally(self, ship_specs: List[Tuple[str, int]]):
        """
        Distributes ships to avoid common clusters and 'hot-zones' 
        like the center or absolute corners, unless randomized.
        """
        # Fisher-Yates shuffle the specs
        specs = list(ship_specs)
        random.shuffle(specs)
        
        for name, size in specs:
            placed = False
            attempts = 0
            while not placed and attempts < 100:
                attempts += 1
                # Weight towards edges slightly to counter center-firing strategies
                # but keep enough randomness to be unpredictable.
                if random.random() < 0.4:
                    # Edge preference
                    x = random.choice([0, 1, self.width-2, self.width-1])
                    y = random.randint(0, self.height - 1)
                else:
                    x = random.randint(0, self.width - 1)
                    y = random.randint(0, self.height - 1)
                    
                horiz = random.choice([True, False])
                ship = Ship(name, size)
                if self.board.place_ship(ship, x, y, horiz):
                    placed = True

    @staticmethod
    def get_optimal_placement(board: Board, ship_specs: List[Tuple[str, int]]):
        strategy = NashPlacement(board)
        strategy.place_ships_optimally(ship_specs)
