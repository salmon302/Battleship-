# Battleship++ Configuration
# Move constants here for easy adjustment

GRID_SIZE = 10
SHIP_TYPES = [
    ("Carrier", 5),
    ("Battleship", 4),
    ("Cruiser", 3),
    ("Submarine", 3),
    ("Destroyer", 2)
]

# UI Constants
WIDTH, HEIGHT = 1000, 600
CELL_SIZE = 40
PLAYER_OFFSET = (50, 100)
AI_OFFSET = (550, 100)

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
