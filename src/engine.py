from enum import Enum, auto
from typing import List, Tuple, Set

class CellStatus(Enum):
    EMPTY = auto()
    SHIP = auto()
    HIT = auto()
    MISS = auto()

class Ship:
    def __init__(self, name: str, size: int):
        self.name = name
        self.size = size
        self.coordinates: List[Tuple[int, int]] = []
        self.hits: Set[Tuple[int, int]] = set()

    @property
    def is_sunk(self) -> bool:
        return len(self.hits) == self.size

class Board:
    def __init__(self, width: int = 10, height: int = 10):
        self.width = width
        self.height = height
        self.grid = [[CellStatus.EMPTY for _ in range(width)] for _ in range(height)]
        self.ships: List[Ship] = []

    def is_valid_coordinate(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def can_place_ship(self, ship: Ship, x: int, y: int, horizontal: bool) -> bool:
        dx, dy = (1, 0) if horizontal else (0, 1)
        for i in range(ship.size):
            nx, ny = x + i * dx, y + i * dy
            if not self.is_valid_coordinate(nx, ny) or self.grid[ny][nx] != CellStatus.EMPTY:
                return False
        return True

    def place_ship(self, ship: Ship, x: int, y: int, horizontal: bool) -> bool:
        if not self.can_place_ship(ship, x, y, horizontal):
            return False
        
        dx, dy = (1, 0) if horizontal else (0, 1)
        for i in range(ship.size):
            nx, ny = x + i * dx, y + i * dy
            self.grid[ny][nx] = CellStatus.SHIP
            ship.coordinates.append((nx, ny))
        self.ships.append(ship)
        return True

    def receive_shot(self, x: int, y: int) -> Tuple[CellStatus, bool]:
        """Returns (status, is_sunk)"""
        if not self.is_valid_coordinate(x, y):
            raise ValueError("Invalid coordinates")
        
        current = self.grid[y][x]
        if current == CellStatus.SHIP:
            self.grid[y][x] = CellStatus.HIT
            for ship in self.ships:
                if (x, y) in ship.coordinates:
                    ship.hits.add((x, y))
                    return CellStatus.HIT, ship.is_sunk
        elif current == CellStatus.EMPTY:
            self.grid[y][x] = CellStatus.MISS
            return CellStatus.MISS, False
        
        return current, False

    @property
    def all_ships_sunk(self) -> bool:
        return all(ship.is_sunk for ship in self.ships)
