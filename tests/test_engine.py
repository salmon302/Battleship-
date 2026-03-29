import unittest
from engine import Board, Ship, CellStatus

class TestBattleship(unittest.TestCase):
    def test_ship_placement(self):
        board = Board(10, 10)
        ship = Ship("Test", 3)
        self.assertTrue(board.place_ship(ship, 0, 0, True))
        self.assertEqual(board.grid[0][0], CellStatus.SHIP)
        self.assertEqual(board.grid[0][1], CellStatus.SHIP)
        self.assertEqual(board.grid[0][2], CellStatus.SHIP)

    def test_invalid_placement(self):
        board = Board(10, 10)
        ship1 = Ship("S1", 3)
        board.place_ship(ship1, 0, 0, True)
        ship2 = Ship("S2", 3)
        self.assertFalse(board.place_ship(ship2, 1, 0, False)) # Overlap

    def test_receive_shot(self):
        board = Board(10, 10)
        ship = Ship("Test", 2)
        board.place_ship(ship, 0, 0, True)
        
        status, sunk = board.receive_shot(0, 0)
        self.assertEqual(status, CellStatus.HIT)
        self.assertFalse(sunk)
        
        status, sunk = board.receive_shot(1, 0)
        self.assertEqual(status, CellStatus.HIT)
        self.assertTrue(sunk)
        self.assertTrue(board.all_ships_sunk)

if __name__ == "__main__":
    unittest.main()
