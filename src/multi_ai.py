try:
    import pygame
except ImportError:
    pygame = None
import sys
import random
import time
import math
import logging
from engine import Board, Ship, CellStatus
from ai import (HuntAndTargetAI, RandomAI, CheckerboardAI, SpiralAI, EdgePreferAI, 
                SequentialAI, HeatmapAI, QLearningAI, StatisticalAI, ParityAI,
                RandomPlacementAI, EdgePlacementAI, DistributedPlacementAI, OverlapPlacementAI)
from analytics import GameAnalytics

logger = logging.getLogger(__name__)

# Constants
WIDTH, HEIGHT = 1200, 800
GRID_SIZE = 10
CELL_SIZE = 30
PADDING = 20

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)

font = None


def _ensure_render_context():
    if pygame is None:
        raise RuntimeError("Pygame is required for rendered MultiAIGame mode")

    if not pygame.get_init():
        pygame.init()

    surf = pygame.display.get_surface()
    if surf is None:
        surf = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption("Battleship++ Experiment: Multi-AI Mode")
    return surf

class MultiAIGame:
    def __init__(self, num_ais=4, attack_all=False, seed=None, render=True, run_metadata=None, auto_save_results=True):
        self.num_ais = num_ais
        self.attack_all = attack_all # True: 1 attack to every other player, False: 1 attack to 1 random opponent
        self.seed = seed
        self.render = render
        self.run_metadata = dict(run_metadata or {})
        self.auto_save_results = bool(auto_save_results)
        if self.seed is not None:
            random.seed(self.seed)
        self.players = []
        
        # Layout calculation
        self.cols = 4 if num_ais > 8 else (3 if num_ais > 4 else 2)
        if num_ais > 12: self.cols = 5
        if num_ais > 20: self.cols = 6

        placement_options = [RandomPlacementAI, EdgePlacementAI, DistributedPlacementAI, OverlapPlacementAI]

        for i in range(num_ais):
            board = Board(GRID_SIZE, GRID_SIZE)
            # Mix the AIs for variety
            ai_options = [
                HuntAndTargetAI, 
                StatisticalAI, 
                ParityAI, 
                HeatmapAI, 
                QLearningAI, 
                SpiralAI, 
                EdgePreferAI, 
                CheckerboardAI, 
                RandomAI, 
                SequentialAI
            ]
            ai_class = ai_options[i % len(ai_options)]
            
            # Mix the placement strategies
            p_strategy = placement_options[i % len(placement_options)]
            p_ai = p_strategy(board)
            p_ai.place_ships([("Carrier", 5), ("Battleship", 4), ("Cruiser", 3), ("Submarine", 3), ("Destroyer", 2)])

            self.players.append({
                "id": i,
                "name": f"AI {i+1}",
                "board": board,
                "ai_logic": ai_class,
                "placement_logic": p_strategy, 
                "ai_handlers": {}, # target_id: AI instance
                "alive": True
            })
            
        # analytics collector
        try:
            analytics_meta = {
                "ai_roster": [p["ai_logic"].__name__ for p in self.players],
                "placement_roster": [p["placement_logic"].__name__ for p in self.players],
                "grid_size": GRID_SIZE,
            }
            analytics_meta.update(self.run_metadata)

            self.analytics = GameAnalytics(
                mode="MultiAI",
                num_players=num_ais,
                attack_all=self.attack_all,
                seed=self.seed,
                run_metadata=analytics_meta,
            )
            # Store AI class names AND placement names for better cross-experiment reporting
            self.analytics.player_ai_types = {
                i: f"{p['ai_logic'].__name__}+{p['placement_logic'].__name__}" 
                for i, p in enumerate(self.players)
            }
        except Exception:
            logger.exception("Failed to initialize GameAnalytics; analytics disabled")
            self.analytics = None

        self.current_turn_idx = 0
        self.game_over = False
        self.winner = None
        self.log = []

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

    def _finalize_analytics(self):
        if not self.analytics:
            return
        if self.analytics.end_time is not None:
            return

        try:
            self.analytics.finalize(self.winner or "No one")
            if self.auto_save_results:
                jpath, _csv_path = self.analytics.save()
                self.log.append(f"Results saved: {jpath}")
        except Exception:
            logger.exception("Failed to finalize/save analytics results")

    def get_opponents(self, current_id):
        return [p for p in self.players if p["id"] != current_id and p["alive"]]

    def perform_ai_turn(self):
        if self.game_over: return

        current_player = self.players[self.current_turn_idx]
        if not current_player["alive"]:
            self.next_turn()
            return

        # mark analytics turn
        if self.analytics:
            self.analytics.next_turn()

        opponents = self.get_opponents(current_player["id"])
        if not opponents:
            self.game_over = True
            # Find the last standing survivor
            survivors = [p for p in self.players if p["alive"]]
            self.winner = survivors[0]["name"] if survivors else "No one"
            self._finalize_analytics()
            return

        targets_to_attack = opponents if self.attack_all else [random.choice(opponents)]

        for target in targets_to_attack:
            # Get or create AI logic for this specific target
            if target["id"] not in current_player["ai_handlers"]:
                # Instantiate AI logic helper
                current_player["ai_handlers"][target["id"]] = current_player["ai_logic"](target["board"])
            
            ai_handler = current_player["ai_handlers"][target["id"]]
            tx, ty = ai_handler.get_shot_coordinates()
            status, is_sunk = target["board"].receive_shot(tx, ty)

            # analytics record for this shot
            if self.analytics:
                try:
                    self.analytics.record_shot(current_player["id"], target["id"], tx, ty, status == CellStatus.HIT, is_sunk, turn=self.analytics.turns)
                except Exception:
                    logger.exception("Failed to record shot to analytics")

            if isinstance(ai_handler, HuntAndTargetAI) and status == CellStatus.HIT:
                ai_handler.report_hit(tx, ty, is_sunk)

            # Generic observation hook (learning/update) for any AI that implements it
            try:
                if hasattr(ai_handler, 'observe_shot_result'):
                    ai_handler.observe_shot_result(tx, ty, status, is_sunk)
            except Exception:
                logger.exception("AI handler observe_shot_result failed")

            if target["board"].all_ships_sunk:
                target["alive"] = False
                if self.analytics:
                    self.analytics.record_defeat(target["id"])
                self.log.append(f"{target['name']} DEFEATED by {current_player['name']}!")
                # Double check if game over
                remaining = self.get_opponents(current_player["id"])
                if not remaining:
                    self.game_over = True
                    self.winner = current_player["name"]
                    self._finalize_analytics()
                    return

        self.next_turn()

    def next_turn(self):
        self.current_turn_idx = (self.current_turn_idx + 1) % self.num_ais
        # Check if anyone is even alive
        if not any(p["alive"] for p in self.players): 
            self.game_over = True
            self.winner = self.winner or "No one"
            self._finalize_analytics()
            return
        # Skip dead players
        tries = 0
        while not self.players[self.current_turn_idx]["alive"] and tries < self.num_ais:
            self.current_turn_idx = (self.current_turn_idx + 1) % self.num_ais
            tries += 1

    def draw(self):
        if not self.render:
            return

        surf = _ensure_render_context()
        if surf is None:
            return

        global font
        if font is None:
            font = pygame.font.SysFont("Arial", 18)

        w, h = surf.get_size()
        surf.fill((30, 30, 45)) # Dark navy background for multi-AI

        # compute responsive cell size to fit all boards
        cols = self.cols
        rows = math.ceil(self.num_ais / cols)

        padding_x = 20
        padding_y = 60
        header_h = 80
        sidebar_w = 200 if w > 800 else 0 # Hide sidebar if window too small

        available_w = max(400, w - sidebar_w - padding_x * 2)
        available_h = max(200, h - header_h - padding_y)

        # Space out boards
        gap = 10 if self.num_ais > 8 else 20
        grid_container_w = available_w // cols
        grid_container_h = available_h // rows
        
        # Calculate cell size based on board container size
        cs_box_w = (grid_container_w - gap) // GRID_SIZE
        cs_box_h = (grid_container_h - gap - 30) // GRID_SIZE # extra space for label
        cs = max(5, min(cs_box_w, cs_box_h, 30))

        grid_w = GRID_SIZE * cs
        grid_h = GRID_SIZE * cs

        for i, p in enumerate(self.players):
            row = i // cols
            col = i % cols

            # Centering board in its box
            box_x = padding_x + col * grid_container_w
            box_y = header_h + row * grid_container_h
            
            offset_x = box_x + (grid_container_w - grid_w) // 2
            offset_y = box_y + (grid_container_h - grid_h) // 2 + 10

            # Label (Better contrast)
            color = WHITE if p["alive"] else (100, 100, 100)
            title_text = f"{p['name']} ({p['ai_logic'].__name__})"
            text_surf = font.render(title_text, True, color)
            surf.blit(text_surf, (offset_x, offset_y - 28))

            # Board container styling
            border_rect = (offset_x - 3, offset_y - 3, grid_w + 6, grid_h + 6)
            is_active = i == self.current_turn_idx and not self.game_over
            
            if is_active:
                # Pulsing border effect (just use bright green for now)
                pygame.draw.rect(surf, (0, 255, 100), border_rect, 2, border_radius=4)
            else:
                pygame.draw.rect(surf, (60, 60, 80), border_rect, 1, border_radius=4)

            # Draw board background
            pygame.draw.rect(surf, (15, 15, 25), (offset_x, offset_y, grid_w, grid_h))

            for y in range(GRID_SIZE):
                for x in range(GRID_SIZE):
                    rect = pygame.Rect(offset_x + x * cs, offset_y + y * cs, cs, cs)
                    pygame.draw.rect(surf, (40, 40, 60), rect, 1)

                    status = p["board"].grid[y][x]
                    if status == CellStatus.SHIP:
                        if p["alive"]:
                            pygame.draw.rect(surf, (80, 80, 100), rect.inflate(-max(2, cs//5), -max(2, cs//5)))
                    elif status == CellStatus.HIT:
                        pygame.draw.rect(surf, RED, rect.inflate(-max(2, cs//5), -max(2, cs//5)))
                    elif status == CellStatus.MISS:
                        pygame.draw.circle(surf, BLUE, rect.center, max(1, cs // 4))

            if not p["alive"]:
                # Draw "X" overlay for eliminated players
                line_col = (150, 0, 0, 180)
                pygame.draw.line(surf, RED, (offset_x, offset_y), (offset_x + grid_w, offset_y + grid_h), 2)
                pygame.draw.line(surf, RED, (offset_x + grid_w, offset_y), (offset_x, offset_y + grid_h), 2)

        # Header Title
        title_font = pygame.font.SysFont("Arial", 36, bold=True)
        header_text = title_font.render("MULTI-AI EXPERIMENT ARENA", True, GREEN)
        surf.blit(header_text, (w // 2 - header_text.get_width() // 2, 20))

        # Side Log/Info Panel
        if sidebar_w > 0:
            log_panel = pygame.Rect(w - sidebar_w, 0, sidebar_w, h)
            pygame.draw.rect(surf, (20, 20, 30), log_panel)
            pygame.draw.line(surf, (60, 60, 80), (w - sidebar_w, 0), (w - sidebar_w, h), 2)
            
            log_title = font.render("EVENT LOG", True, GRAY)
            surf.blit(log_title, (w - sidebar_w + 20, 20))
            
            log_y = 60
            for entry in self.log[-15:]: # Show more logs
                prefix = ">> " if "Sunk" in entry or "Wins" in entry else " - "
                col = (255, 200, 100) if "Sunk" in entry else WHITE
                if "Wins" in entry: col = GREEN
                
                log_text = font.render(prefix + entry, True, col)
                surf.blit(log_text, (w - sidebar_w + 10, log_y))
                log_y += 24

        if self.game_over:
            # Game over toast
            msg_box = pygame.Rect(w//2 - 200, h//2 - 50, 400, 100)
            pygame.draw.rect(surf, (255, 255, 255), msg_box, border_radius=10)
            pygame.draw.rect(surf, GREEN, msg_box, 3, border_radius=10)
            winner_disp = title_font.render(f"WINNER: {self.winner}", True, BLACK)
            surf.blit(winner_disp, (w // 2 - winner_disp.get_width() // 2, h // 2 - 30))
            sub = font.render("Experiment Concluded. Press ESC.", True, (100, 100, 100))
            surf.blit(sub, (w // 2 - sub.get_width() // 2, h // 2 + 10))

        pygame.display.flip()

    def run(self):
        if not self.render:
            while not self.game_over:
                self.perform_ai_turn()
            return

        if pygame is None:
            raise RuntimeError("Pygame is required when render=True")

        _ensure_render_context()
        clock = pygame.time.Clock()
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return # Return to launcher
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return # Return to launcher
                if event.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

            if not self.game_over:
                self.perform_ai_turn()
                time.sleep(0.02) # Faster simulation

            self.draw()
            clock.tick(60)
            if self.game_over:
                time.sleep(0.1) # Small pause before allowing exit

if __name__ == "__main__":
    # Example: 4 AI players, attacking 1 random opponent per turn
    game = MultiAIGame(num_ais=6, attack_all=True)
    game.run()
