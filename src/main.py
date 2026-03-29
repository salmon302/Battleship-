import pygame
import sys
import random
from typing import List
from engine import Board, Ship, CellStatus
from ai import create_pve_ai
from analytics import GameAnalytics

# Constants
WIDTH, HEIGHT = 1000, 600
GRID_SIZE = 10
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

pygame.init()
screen = pygame.display.get_surface()
if screen is None:
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Battleship++ Experiment")
font = pygame.font.SysFont("Arial", 24)

class BattleshipGame:
    def __init__(self, ai_type: str = "HuntAndTarget"):
        global screen
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.player_board = Board(GRID_SIZE, GRID_SIZE)
        self.ai_board = Board(GRID_SIZE, GRID_SIZE)
        self.ai = create_pve_ai(ai_type, self.player_board)
        self.ai_type = ai_type
        self.setup_random_ships(self.player_board)
        self.setup_random_ships(self.ai_board)
        # Analytics
        try:
            self.analytics = GameAnalytics(mode="PvE", num_players=2, attack_all=False)
        except Exception:
            self.analytics = None
        self.last_results = None
        self.game_over = False
        self.winner = None

    def setup_random_ships(self, board: Board):
        ship_types = [("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)]
        for name, size in ship_types:
            placed = False
            while not placed:
                ship = Ship(name, size)
                x = random.randint(0, board.width - 1)
                y = random.randint(0, board.height - 1)
                horizontal = random.choice([True, False])
                placed = board.place_ship(ship, x, y, horizontal)

    def draw_grid(self, surf, offset_x, offset_y, board: Board, show_ships=True, cell_size: int = None):
        cs = cell_size or CELL_SIZE
        for y in range(board.height):
            for x in range(board.width):
                rect = pygame.Rect(offset_x + x * cs, offset_y + y * cs, cs, cs)
                pygame.draw.rect(surf, BLACK, rect, 1)
                
                status = board.grid[y][x]
                if status == CellStatus.SHIP and show_ships:
                    pygame.draw.rect(surf, GRAY, rect.inflate(-max(2, cs//10), -max(2, cs//10)))
                elif status == CellStatus.HIT:
                    pygame.draw.rect(surf, RED, rect.inflate(-max(2, cs//10), -max(2, cs//10)))
                elif status == CellStatus.MISS:
                    pygame.draw.circle(surf, BLUE, rect.center, max(2, cs // 4))

    def handle_click(self, pos, ai_offset, cell_size):
        if self.game_over:
            return

        # mark a new turn
        if self.analytics:
            self.analytics.next_turn()

        mx, my = pos
        ax, ay = ai_offset
        grid_x = (mx - ax) // cell_size
        grid_y = (my - ay) // cell_size

        if self.ai_board.is_valid_coordinate(grid_x, grid_y) and self.ai_board.grid[grid_y][grid_x] in [CellStatus.EMPTY, CellStatus.SHIP]:
            # Player turn
            status, is_sunk = self.ai_board.receive_shot(grid_x, grid_y)
            if self.analytics:
                self.analytics.record_shot(0, 1, grid_x, grid_y, status == CellStatus.HIT, is_sunk, turn=self.analytics.turns)
            if self.ai_board.all_ships_sunk:
                self.game_over = True
                self.winner = "Player"
                if self.analytics:
                    self.analytics.finalize(self.winner)
                    self.last_results = self.analytics.save()
                return

            # AI turn
            ax_shot, ay_shot = self.ai.get_shot_coordinates()
            ai_status, ai_sunk = self.player_board.receive_shot(ax_shot, ay_shot)
            if ai_status == CellStatus.HIT and hasattr(self.ai, "report_hit"):
                self.ai.report_hit(ax_shot, ay_shot, ai_sunk)
            if hasattr(self.ai, "observe_shot_result"):
                self.ai.observe_shot_result(ax_shot, ay_shot, ai_status, ai_sunk)
            if self.analytics:
                self.analytics.record_shot(1, 0, ax_shot, ay_shot, ai_status == CellStatus.HIT, ai_sunk, turn=self.analytics.turns)

            if self.player_board.all_ships_sunk:
                self.game_over = True
                self.winner = "AI"
                if self.analytics:
                    self.analytics.finalize(self.winner)
                    self.last_results = self.analytics.save()
    def run(self):
        clock = pygame.time.Clock()
        while True:
            surf = pygame.display.get_surface()
            if surf is None:
                surf = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)

            w, h = surf.get_size()

            # compute responsive cell size so two grids fit side-by-side
            margin = 40
            spacing = 40
            available_width = max(200, w - 2 * margin - spacing)
            cs_by_width = available_width // (2 * GRID_SIZE)
            available_height = max(200, h - 3 * margin)
            cs_by_height = available_height // GRID_SIZE
            cs = max(12, min(cs_by_width, cs_by_height, CELL_SIZE))

            # offsets
            player_offset_x = margin
            player_offset_y = margin + 60
            ai_offset_x = player_offset_x + GRID_SIZE * cs + spacing
            ai_offset_y = player_offset_y

            surf.fill(WHITE)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return # Return to launcher
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return # Return to launcher
                if event.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos, (ai_offset_x, ai_offset_y), cs)

            # UI labels
            surf.blit(font.render("Your Fleet", True, BLACK), (player_offset_x, 20))
            surf.blit(font.render("AI Radar", True, BLACK), (ai_offset_x, 20))

            self.draw_grid(surf, player_offset_x, player_offset_y, self.player_board, show_ships=True, cell_size=cs)
            self.draw_grid(surf, ai_offset_x, ai_offset_y, self.ai_board, show_ships=False, cell_size=cs)

            if self.game_over:
                winner_text = font.render(f"GAME OVER - {self.winner} Wins!", True, RED)
                surf.blit(winner_text, (w // 2 - winner_text.get_width() // 2, 10))
                if self.last_results:
                    # show saved results paths
                    jpath, cpath = self.last_results
                    info = font.render(f"Results: {jpath}", True, BLACK)
                    surf.blit(info, (w // 2 - info.get_width() // 2, 50))

            pygame.display.flip()
            clock.tick(60)

if __name__ == "__main__":
    game = BattleshipGame()
    game.run()

class PvETournament:
    def __init__(self, ai_types: List[str] = None):
        self.ai_types = ai_types or ["Random", "HuntAndTarget", "Statistical", "Heatmap", "QLearning"]
        self.results = []
        self.current_ai_idx = 0
        self.player_score = 0
        self.ai_scores = {ai: 0 for ai in self.ai_types}
        self.game_over = False
        self.tournament_complete = False

    def next_round(self):
        if self.current_ai_idx >= len(self.ai_types):
            self.tournament_complete = True
            return None
        
        ai_name = self.ai_types[self.current_ai_idx]
        game = BattleshipGame(ai_type=ai_name)
        return game

    def run(self):
        clock = pygame.time.Clock()
        while not self.tournament_complete:
            game = self.next_round()
            if not game: break
            
            # Run the single game
            game.run()
            
            # Record result
            if game.winner == "Player":
                self.player_score += 1
            else:
                self.ai_scores[self.ai_types[self.current_ai_idx]] += 1
            
            self.results.append({
                "opponent": self.ai_types[self.current_ai_idx],
                "winner": game.winner
            })
            
            self.current_ai_idx += 1
            
            # Show summary screen between rounds
            if not self.show_summary_screen():
                break

    def show_summary_screen(self):
        """Shows a summary screen between tournament rounds."""
        waiting = True
        clock = pygame.time.Clock()
        while waiting:
            surf = pygame.display.get_surface()
            if surf is None: break
            w, h = surf.get_size()
            surf.fill(WHITE)

            title = font.render(f"Tournament Standings ({self.current_ai_idx}/{len(self.ai_types)})", True, BLACK)
            surf.blit(title, (w // 2 - title.get_width() // 2, 50))

            y_offset = 120
            p_text = font.render(f"PLAYER Score: {self.player_score}", True, BLUE)
            surf.blit(p_text, (w // 2 - p_text.get_width() // 2, y_offset))
            y_offset += 40

            for ai, score in self.ai_scores.items():
                ai_text = font.render(f"{ai} Score: {score}", True, BLACK)
                surf.blit(ai_text, (w // 2 - ai_text.get_width() // 2, y_offset))
                y_offset += 30

            msg = "Press SPACE to continue to next round or ESC to quit"
            if self.current_ai_idx >= len(self.ai_types):
                msg = "Tournament Complete! Press any key to return to menu"
            
            instr = font.render(msg, True, RED)
            surf.blit(instr, (w // 2 - instr.get_width() // 2, h - 100))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
                    if event.key == pygame.K_SPACE or self.current_ai_idx >= len(self.ai_types):
                        waiting = False

            pygame.display.flip()
            clock.tick(60)
        return True
