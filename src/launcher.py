import pygame
import sys
import os
from multi_ai import MultiAIGame
from main import BattleshipGame, PvETournament
from scoreboard import Scoreboard

# Constants
WIDTH, HEIGHT = 900, 750
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
BLUE = (50, 50, 200)
GREEN = (50, 200, 50)
ORANGE = (255, 165, 0)

pygame.init()
pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("Battleship++ Experiment Launcher")
font_title = pygame.font.SysFont("Arial", 48)
font_label = pygame.font.SysFont("Arial", 24)
font_small = pygame.font.SysFont("Arial", 18)


def get_surface():
    s = pygame.display.get_surface()
    if s is None:
        s = pygame.display.set_mode((WIDTH, HEIGHT), pygame.RESIZABLE)
    return s

class Menu:
    def __init__(self):
        self.num_ais = 4
        self.attack_all = False
        self.mode = "PvE"  # OR "AIvAI" OR "PvE_Tournament"
        self.ai_type = "HuntAndTarget"  # Options: HuntAndTarget, Statistical, MonteCarlo

    def draw_button(self, surf, text, rect, color, active=False, hover=False):
        # Draw shadow
        shadow_rect = rect.copy()
        shadow_rect.x += 2
        shadow_rect.y += 2
        pygame.draw.rect(surf, (50, 50, 50), shadow_rect, border_radius=8)

        # Draw main button
        draw_color = color
        if active:
            draw_color = (130, 130, 255) if color == BLUE else (130, 255, 130) if color == GREEN else (255, 200, 130)
        elif hover:
            # Lighten color slightly on hover
            draw_color = tuple(min(255, c + 25) for c in color)

        pygame.draw.rect(surf, draw_color, rect, border_radius=8)
        border_col = (50, 50, 50) if not active else (0, 0, 150)
        pygame.draw.rect(surf, border_col, rect, 2, border_radius=8)
        
        txt_color = WHITE if active or color in (BLUE, GREEN, ORANGE) else BLACK
        txt = font_label.render(text, True, txt_color)
        surf.blit(txt, (rect.x + (rect.width - txt.get_width())//2, rect.y + (rect.height - txt.get_height())//2))

    def run(self):
        clock = pygame.time.Clock()
        scoreboard = Scoreboard()
        while True:
            surf = get_surface()
            width, height = surf.get_size()
            mouse_pos = pygame.mouse.get_pos()
            surf.fill(WHITE)

            # Title
            title = font_title.render("Battleship++ Experiment", True, BLACK)
            surf.blit(title, (width // 2 - title.get_width() // 2, int(height * 0.05)))

            # Modes positions (3 columns now)
            third = width // 3
            pve_rect = pygame.Rect(third // 2 - 100, int(height * 0.15), 200, 50)
            pve_tourney_rect = pygame.Rect(width // 2 - 100, int(height * 0.15), 200, 50)
            aivai_rect = pygame.Rect(width - third // 2 - 100, int(height * 0.15), 200, 50)

            # Mode buttons
            self.draw_button(surf, "Player vs AI", pve_rect, BLUE if self.mode == "PvE" else GRAY, self.mode == "PvE", pve_rect.collidepoint(mouse_pos))
            self.draw_button(surf, "PvE Tournament", pve_tourney_rect, ORANGE if self.mode == "PvE_Tournament" else GRAY, self.mode == "PvE_Tournament", pve_tourney_rect.collidepoint(mouse_pos))
            self.draw_button(surf, "AI vs AI (Multi)", aivai_rect, GREEN if self.mode == "AIvAI" else GRAY, self.mode == "AIvAI", aivai_rect.collidepoint(mouse_pos))

            # Selection for AI difficulty in PvE
            if self.mode == "PvE":
                label = font_label.render("AI Strategy Selection:", True, BLACK)
                surf.blit(label, (width // 2 - label.get_width()//2, int(height * 0.28)))
                
                center_x = width // 2
                hunt_rect = pygame.Rect(center_x - 90, int(height * 0.33), 180, 40)
                stat_rect = pygame.Rect(center_x - 90, int(height * 0.40), 180, 40)
                mc_rect = pygame.Rect(center_x - 90, int(height * 0.47), 180, 40)
                hm_rect = pygame.Rect(center_x - 90, int(height * 0.54), 180, 40)
                hh_rect = pygame.Rect(center_x - 90, int(height * 0.61), 180, 40)

                self.draw_button(surf, "Hunt & Target", hunt_rect, BLUE if self.ai_type == "HuntAndTarget" else GRAY, self.ai_type == "HuntAndTarget", hunt_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "Statistical (PDM)", stat_rect, BLUE if self.ai_type == "Statistical" else GRAY, self.ai_type == "Statistical", stat_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "Monte Carlo", mc_rect, BLUE if self.ai_type == "MonteCarlo" else GRAY, self.ai_type == "MonteCarlo", mc_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "Human KG (Med)", hm_rect, BLUE if self.ai_type == "HumanMedium" else GRAY, self.ai_type == "HumanMedium", hm_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "Human KG (Hard)", hh_rect, BLUE if self.ai_type == "HumanHard" else GRAY, self.ai_type == "HumanHard", hh_rect.collidepoint(mouse_pos))

            # PvE Tournament explanation
            if self.mode == "PvE_Tournament":
                label = font_label.render("Tournament Sequence:", True, BLACK)
                surf.blit(label, (width // 2 - label.get_width()//2, int(height * 0.28)))
                
                sequence = ["Random", "Hunt & Target", "Statistical (PDM)", "Heatmap", "Q-Learning"]
                y_off = 0.33
                for s in sequence:
                    s_txt = font_small.render(f"• {s}", True, BLACK)
                    surf.blit(s_txt, (width // 2 - 80, int(height * y_off)))
                    y_off += 0.04
                
                info = font_small.render("Win against each AI to finish the tournament!", True, (100, 100, 100))
                surf.blit(info, (width // 2 - info.get_width() // 2, int(height * 0.55)))

            # AI vs AI settings (Only shows if AIvAI is selected)
            if self.mode == "AIvAI":
                label = font_label.render(f"Number of AIs: {self.num_ais}", True, BLACK)
                surf.blit(label, (center_x - 150, int(height * 0.28)))
                minus_rect = pygame.Rect(center_x + 60, int(height * 0.28), 40, 40)
                plus_rect = pygame.Rect(center_x + 110, int(height * 0.28), 40, 40)
                self.draw_button(surf, "-", minus_rect, GRAY, hover=minus_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "+", plus_rect, GRAY, hover=plus_rect.collidepoint(mouse_pos))

                label2 = font_label.render("Attack Pattern Mode:", True, BLACK)
                surf.blit(label2, (center_x - 150, int(height * 0.38)))
                attack_one_rect = pygame.Rect(center_x - 50, int(height * 0.38), 150, 40)
                attack_all_rect = pygame.Rect(center_x + 110, int(height * 0.38), 150, 40)
                self.draw_button(surf, "Attack One", attack_one_rect, GRAY if self.attack_all else BLUE, not self.attack_all, attack_one_rect.collidepoint(mouse_pos))
                self.draw_button(surf, "Attack All", attack_all_rect, BLUE if self.attack_all else GRAY, self.attack_all, attack_all_rect.collidepoint(mouse_pos))

            # Start Button
            launch_rect = pygame.Rect(center_x - 150, int(height * 0.52), 300, 50)
            self.draw_button(surf, "VISUAL EXPERIMENT", launch_rect, (255, 100, 100), hover=launch_rect.collidepoint(mouse_pos))

            batch_rect = pygame.Rect(center_x - 150, int(height * 0.60), 300, 50)
            self.draw_button(surf, "BATCH RUN (10 Headless)", batch_rect, (100, 100, 100), hover=batch_rect.collidepoint(mouse_pos))

            # Scoreboard View (Bottom half)
            pygame.draw.line(surf, GRAY, (50, int(height * 0.68)), (width - 50, int(height * 0.68)), 2)
            surf.blit(font_label.render("STRATEGY MATRIX: LETHALITY vs SURVIVAL", True, BLACK), (width // 2 - 220, int(height * 0.7)))
            
            stats = scoreboard.get_aggregate_stats()
            col_widths = [240, 60, 90, 90, 70]
            start_x = (width - sum(col_widths)) // 2
            header_y = int(height * 0.76)
            
            # Headers
            headers = ["AI Logic + Placement", "Wins", "Lethality", "Survival", "Games"]
            for i, h_text in enumerate(headers):
                h_surf = font_small.render(h_text, True, (100, 100, 100))
                surf.blit(h_surf, (start_x + sum(col_widths[:i]), header_y))

            for i, entry in enumerate(stats[:5]):
                row_y = header_y + 25 + i * 22
                row_color = BLACK if i > 0 else (0, 150, 0)
                disp_type = entry["type"] if len(entry["type"]) < 25 else entry["type"][:22] + "..."
                row_data = [disp_type, str(entry["wins"]), f"{entry['accuracy']:.1f}%", f"{entry['avg_survival']:.1f}T", str(entry["total_games"])]
                for j, text in enumerate(row_data):
                    d_surf = font_small.render(text, True, row_color)
                    surf.blit(d_surf, (start_x + sum(col_widths[:j]), row_y))

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()

                if event.type == pygame.VIDEORESIZE:
                    pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)

                if event.type == pygame.MOUSEBUTTONDOWN:
                    pos = event.pos

                    # Mode buttons
                    if pve_rect.collidepoint(pos):
                        self.mode = "PvE"
                    if pve_tourney_rect.collidepoint(pos):
                        self.mode = "PvE_Tournament"
                    if aivai_rect.collidepoint(pos):
                        self.mode = "AIvAI"

                    if self.mode == "PvE":
                        h_rect = pygame.Rect(center_x - 90, int(height * 0.33), 180, 40)
                        s_rect = pygame.Rect(center_x - 90, int(height * 0.40), 180, 40)
                        m_rect = pygame.Rect(center_x - 90, int(height * 0.47), 180, 40)
                        hm_rect = pygame.Rect(center_x - 90, int(height * 0.54), 180, 40)
                        hh_rect = pygame.Rect(center_x - 90, int(height * 0.61), 180, 40)
                        
                        if h_rect.collidepoint(pos):
                            self.ai_type = "HuntAndTarget"
                        if s_rect.collidepoint(pos):
                            self.ai_type = "Statistical"
                        if m_rect.collidepoint(pos):
                            self.ai_type = "MonteCarlo"
                        if hm_rect.collidepoint(pos):
                            self.ai_type = "HumanMedium"
                        if hh_rect.collidepoint(pos):
                            self.ai_type = "HumanHard"

                    if self.mode == "AIvAI":
                        # Rects must be recalculated here to avoid UnboundLocalError
                        center_x = width // 2
                        minus_rect = pygame.Rect(center_x + 60, int(height * 0.28), 40, 40)
                        plus_rect = pygame.Rect(center_x + 110, int(height * 0.28), 40, 40)
                        attack_one_rect = pygame.Rect(center_x - 50, int(height * 0.38), 150, 40)
                        attack_all_rect = pygame.Rect(center_x + 110, int(height * 0.38), 150, 40)

                        if minus_rect.collidepoint(pos):
                            self.num_ais = max(2, self.num_ais - 1)
                        if plus_rect.collidepoint(pos):
                            self.num_ais = min(20, self.num_ais + 1)
                        if attack_one_rect.collidepoint(pos):
                            self.attack_all = False
                        if attack_all_rect.collidepoint(pos):
                            self.attack_all = True

                    # Launch button
                    launch_rect = pygame.Rect(center_x - 150, int(height * 0.52), 300, 50)
                    batch_rect = pygame.Rect(center_x - 150, int(height * 0.60), 300, 50)

                    if launch_rect.collidepoint(pos):
                        if self.mode == "PvE":
                            game = BattleshipGame(ai_type=self.ai_type)
                            game.run()
                        elif self.mode == "PvE_Tournament":
                            tourney = PvETournament()
                            tourney.run()
                        scoreboard = Scoreboard()
                        pygame.display.set_mode((width, height), pygame.RESIZABLE)
                    
                    if batch_rect.collidepoint(pos):
                        from headless_runner import run_batch
                        run_batch(10, self.num_ais, self.attack_all)
                        # Refresh scoreboard
                        scoreboard = Scoreboard()
                        pygame.display.set_mode((width, height), pygame.RESIZABLE)

            pygame.display.flip()
            clock.tick(30)

if __name__ == "__main__":
    menu = Menu()
    menu.run()
