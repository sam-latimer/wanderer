import pygame
import csv
import random
from typing import Dict, List, Tuple, Optional

# --- Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
HUD_WIDTH = 200
GAME_WIDTH = SCREEN_WIDTH - HUD_WIDTH
FPS = 60
MEMORY_LIMIT = 12
BUFFER_TILES = 1
PAN_SMOOTHING = 0.85
MOVE_COOLDOWN = 0.15
BACKPACK_CAPACITY = 20

# Colors
COLORS = {
    'background': (30, 30, 30),
    'trail_start': (0, 200, 255),
    'trail_end': (45, 45, 45),
    'player': (255, 255, 255),
    'tile_border': (50, 50, 50),
    'hud_bg': (20, 20, 20),
    'hud_text': (255, 255, 255),
    'hud_border': (60, 60, 60),
    'default_room': (60, 60, 60),
    'loot_indicator': (255, 255, 0)
}


# --- Utilities ---
def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b"""
    return a + (b - a) * t


def get_gradient_color(index: int, total: int,
                       start: Tuple[int, int, int] = COLORS['trail_start'],
                       end: Tuple[int, int, int] = COLORS['trail_end']) -> Tuple[int, int, int]:
    """Calculate gradient color between start and end colors"""
    if total <= 1:
        return start
    t = index / (total - 1)
    return tuple(int(end[i] + (start[i] - end[i]) * t) for i in range(3))


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """Parse color from string format"""
    if not color_str or color_str.strip() == '':
        return COLORS['default_room']

    color_str = color_str.strip().lower()

    # Handle predefined colors
    color_map = {
        'gray': (128, 128, 128),
        'yellow': (255, 255, 0),
        'gold': (255, 215, 0),
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255)
    }

    if color_str in color_map:
        return color_map[color_str]

    # Handle hex colors
    if color_str.startswith('#'):
        try:
            hex_color = color_str[1:]
            return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass

    return COLORS['default_room']


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels"""
    words = text.split(' ')
    lines = []
    current_line = ""

    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if font.size(test_line)[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


# --- Data Loading ---
class GameData:
    def __init__(self):
        self.rooms_data = []
        self.items_data = []
        self.weighted_rooms = []
        self.weighted_items = []
        self.load_data()

    def load_file(self, filename: str) -> List[Dict]:
        """Load CSV file and return as list of dictionaries"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return list(csv.DictReader(file))
        except FileNotFoundError:
            print(f"Warning: {filename} not found")
            return []

    def load_data(self):
        """Load all game data"""
        self.rooms_data = self.load_file('wanderer content - rooms.csv')
        self.items_data = self.load_file('wanderer content - items.csv')
        self.create_weighted_lists()

    def create_weighted_lists(self):
        """Create weighted lists for random selection"""
        self.weighted_rooms = []
        self.weighted_items = []

        for room in self.rooms_data:
            try:
                prob = int(room.get('probability', 0))
                self.weighted_rooms.extend([room] * prob)
            except ValueError:
                continue

        for item in self.items_data:
            try:
                prob = int(item.get('probability', 0))
                self.weighted_items.extend([item] * prob)
            except ValueError:
                continue


# --- Game Logic ---
class GameLogic:
    def __init__(self, game_data: GameData):
        self.game_data = game_data
        self.backpack = {}

    def generate_room(self) -> Dict:
        """Generate a random room based on probabilities"""
        if not self.game_data.weighted_rooms:
            return {
                'name': 'Empty Room',
                'type': 'room',
                'probability': '1',
                'max_loot': '6',
                'flavor_text': "There doesn't seem to be anything here."
            }
        return random.choice(self.game_data.weighted_rooms).copy()

    def generate_item(self, tier: int = 0) -> str:
        """Generate a random item based on tier"""
        if not self.game_data.weighted_items:
            return "Small Pebble"

        item_data = random.choice(self.game_data.weighted_items)
        tier_key = f'tier{min(tier, 2)}'

        item_name = item_data.get(tier_key, '')
        if not item_name or item_name.strip() == '':
            for fallback_tier in range(tier - 1, -1, -1):
                fallback_key = f'tier{fallback_tier}'
                item_name = item_data.get(fallback_key, '')
                if item_name and item_name.strip() != '':
                    break

            if not item_name or item_name.strip() == '':
                item_name = item_data.get('name', 'Unknown Item')

        return item_name.strip()

    def generate_room_loot(self, room_data: Dict) -> List[str]:
        """Generate loot for a room"""
        try:
            max_loot = int(room_data.get('max_loot', 6))
        except ValueError:
            max_loot = 6

        num_items = min(random.randint(1, 3), max_loot)
        loot = []

        for _ in range(num_items):
            tier_roll = random.random()
            tier = 0 if tier_roll < 0.6 else (1 if tier_roll < 0.85 else 2)
            item = self.generate_item(tier)
            loot.append(item)

        return loot

    def add_to_backpack(self, item_name: str) -> bool:
        """Add an item to the backpack if there's space"""
        total_items = sum(self.backpack.values())
        if total_items < BACKPACK_CAPACITY:
            self.backpack[item_name] = self.backpack.get(item_name, 0) + 1
            return True
        return False


# --- Game State ---
class GameState:
    def __init__(self, game_data: GameData, game_logic: GameLogic):
        self.game_data = game_data
        self.game_logic = game_logic
        self.player_pos = (0, 0)
        self.trail = []
        self.camera_offset = [0, 0]
        self.target_offset = [0, 0]
        self.move_timer = 0
        self.initialize_game()

    def initialize_game(self):
        """Initialize starting game state"""
        initial_room = self.game_logic.generate_room()
        initial_loot = self.game_logic.generate_room_loot(initial_room)
        self.trail = [{
            'pos': self.player_pos,
            'room': initial_room,
            'loot': initial_loot,
            'looted': False
        }]

    def move_player(self, target_pos: Tuple[int, int]):
        """Move player to new position"""
        existing_entry = None
        for entry in self.trail:
            if entry['pos'] == target_pos:
                existing_entry = entry
                self.trail.remove(entry)
                break

        if existing_entry is None:
            room_data = self.game_logic.generate_room()
            room_loot = self.game_logic.generate_room_loot(room_data)
            existing_entry = {
                'pos': target_pos,
                'room': room_data,
                'loot': room_loot,
                'looted': False
            }

        self.trail.insert(0, existing_entry)
        self.player_pos = target_pos

        if len(self.trail) > MEMORY_LIMIT:
            self.trail.pop()


# --- Rendering ---
class Renderer:
    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen = screen
        self.font = font

    def draw_grid(self, camera_offset: List[float], tile_size: int):
        """Draw the background grid"""
        grid_start_x = int(round(camera_offset[0] % tile_size - tile_size))
        grid_start_y = int(round(camera_offset[1] % tile_size - tile_size))

        for x in range(grid_start_x, GAME_WIDTH + tile_size, tile_size):
            for y in range(grid_start_y, SCREEN_HEIGHT + tile_size, tile_size):
                if x < GAME_WIDTH:
                    rect = pygame.Rect(x, y, min(tile_size, GAME_WIDTH - x), tile_size)
                    pygame.draw.rect(self.screen, COLORS['tile_border'], rect, 1)

    def draw_trail(self, trail: List[Dict], view_bounds: Dict, camera_offset: List[float], tile_size: int):
        """Draw the trail of visited rooms"""
        trail_without_player = trail[1:]
        for idx, tile in enumerate(reversed(trail_without_player)):
            color = get_gradient_color(idx, len(trail_without_player))
            x, y = tile['pos']
            screen_x = camera_offset[0] + (x - view_bounds['min_x']) * tile_size
            screen_y = camera_offset[1] + (y - view_bounds['min_y']) * tile_size
            if screen_x < GAME_WIDTH:
                rect = pygame.Rect(int(screen_x), int(screen_y), tile_size, tile_size)
                pygame.draw.rect(self.screen, color, rect)

    def draw_room(self, room_entry: Dict, pos: Tuple[int, int], view_bounds: Dict,
                  camera_offset: List[float], tile_size: int):
        """Draw room content"""
        x, y = pos
        screen_x = camera_offset[0] + (x - view_bounds['min_x']) * tile_size
        screen_y = camera_offset[1] + (y - view_bounds['min_y']) * tile_size

        if screen_x < GAME_WIDTH:
            room_data = room_entry['room']
            color_str = room_data.get('color', '')
            color = parse_color(color_str)

            center_x = int(screen_x + tile_size // 2)
            center_y = int(screen_y + tile_size // 2)
            radius = max(3, tile_size // 4)
            pygame.draw.circle(self.screen, color, (center_x, center_y), radius)

            room_type = room_data.get('type', 'room').upper()
            type_label = self.font.render(room_type, True, COLORS['hud_text'])
            label_rect = type_label.get_rect(center=(center_x, screen_y + tile_size - 10))
            self.screen.blit(type_label, label_rect)

            if room_entry.get('loot', []) and not room_entry.get('looted', False):
                sparkle_size = max(2, tile_size // 8)
                pygame.draw.line(self.screen, COLORS['loot_indicator'],
                                 (center_x - sparkle_size, center_y),
                                 (center_x + sparkle_size, center_y), 2)
                pygame.draw.line(self.screen, COLORS['loot_indicator'],
                                 (center_x, center_y - sparkle_size),
                                 (center_x, center_y + sparkle_size), 2)

    def draw_player(self, pos: Tuple[int, int], view_bounds: Dict,
                    camera_offset: List[float], tile_size: int):
        """Draw the player"""
        x, y = pos
        screen_x = camera_offset[0] + (x - view_bounds['min_x']) * tile_size
        screen_y = camera_offset[1] + (y - view_bounds['min_y']) * tile_size
        if screen_x < GAME_WIDTH:
            rect = pygame.Rect(int(screen_x), int(screen_y), tile_size, tile_size)
            pygame.draw.rect(self.screen, COLORS['player'], rect)

    def draw_hud(self, current_room: Dict, backpack: Dict):
        """Draw the HUD panel"""
        hud_rect = pygame.Rect(GAME_WIDTH, 0, HUD_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, COLORS['hud_bg'], hud_rect)
        pygame.draw.line(self.screen, COLORS['hud_border'],
                         (GAME_WIDTH, 0), (GAME_WIDTH, SCREEN_HEIGHT), 2)

        padding = 10
        y_offset = 10

        # Room info
        room_name = self.font.render(f"Room: {current_room['room'].get('name', 'Unknown')}",
                                     True, COLORS['hud_text'])
        self.screen.blit(room_name, (GAME_WIDTH + padding, y_offset))
        y_offset += 25

        room_type = self.font.render(f"Type: {current_room['room'].get('type', 'Unknown')}",
                                     True, COLORS['hud_text'])
        self.screen.blit(room_type, (GAME_WIDTH + padding, y_offset))
        y_offset += 25

        # Room description
        flavor_text = current_room['room'].get('flavor_text', 'No description')
        wrapped_lines = wrap_text(flavor_text, self.font, HUD_WIDTH - padding * 2)
        for line in wrapped_lines:
            text = self.font.render(line, True, COLORS['hud_text'])
            self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
            y_offset += 20
        y_offset += 10

        # Loot info
        if current_room.get('loot', []):
            if current_room.get('looted', False):
                text = self.font.render("Loot: (taken)", True, (128, 128, 128))
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 20
            else:
                text = self.font.render("Loot:", True, COLORS['hud_text'])
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 20
                for item in current_room['loot']:
                    text = self.font.render(f"  {item}", True, COLORS['loot_indicator'])
                    self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                    y_offset += 18
        y_offset += 15

        # Backpack
        text = self.font.render(f"Backpack ({sum(backpack.values())}/{BACKPACK_CAPACITY}):",
                                True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 20

        if backpack:
            for item, count in backpack.items():
                text = self.font.render(f"  {item} x{count}", True, (200, 200, 200))
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 18
        else:
            text = self.font.render("  (empty)", True, (128, 128, 128))
            self.screen.blit(text, (GAME_WIDTH + padding, y_offset))


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Wanderer v0.2")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 18)

    game_data = GameData()
    game_logic = GameLogic(game_data)
    game_state = GameState(game_data, game_logic)
    renderer = Renderer(screen, font)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        game_state.move_timer -= dt

        # Handle input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and game_state.move_timer <= 0:
                dx, dy = 0, 0
                if event.key in [pygame.K_w, pygame.K_UP, pygame.K_KP8]:
                    dy = -1
                elif event.key in [pygame.K_s, pygame.K_DOWN, pygame.K_KP2]:
                    dy = 1
                elif event.key in [pygame.K_a, pygame.K_LEFT, pygame.K_KP4]:
                    dx = -1
                elif event.key in [pygame.K_d, pygame.K_RIGHT, pygame.K_KP6]:
                    dx = 1
                elif event.key == pygame.K_l:
                    current_entry = game_state.trail[0]
                    if not current_entry.get('looted', False) and current_entry.get('loot', []):
                        for item in current_entry['loot']:
                            if game_logic.add_to_backpack(item):
                                continue
                            else:
                                break
                        current_entry['looted'] = True

                if dx != 0 or dy != 0:
                    target = (game_state.player_pos[0] + dx, game_state.player_pos[1] + dy)
                    game_state.move_player(target)
                    game_state.move_timer = MOVE_COOLDOWN

        # Calculate view bounds
        positions = [entry['pos'] for entry in game_state.trail]
        xs = [x for x, y in positions]
        ys = [y for x, y in positions]
        view_bounds = {
            'min_x': min(xs) - BUFFER_TILES,
            'max_x': max(xs) + BUFFER_TILES,
            'min_y': min(ys) - BUFFER_TILES,
            'max_y': max(ys) + BUFFER_TILES
        }

        view_width = view_bounds['max_x'] - view_bounds['min_x'] + 1
        view_height = view_bounds['max_y'] - view_bounds['min_y'] + 1

        tile_size_x = GAME_WIDTH // view_width
        tile_size_y = SCREEN_HEIGHT // view_height
        tile_size = int(min(tile_size_x, tile_size_y))

        grid_width_px = view_width * tile_size
        grid_height_px = view_height * tile_size

        # Update camera
        game_state.target_offset[0] = (GAME_WIDTH - grid_width_px) // 2
        game_state.target_offset[1] = (SCREEN_HEIGHT - grid_height_px) // 2

        game_state.camera_offset[0] += (game_state.target_offset[0] - game_state.camera_offset[0]) * (1 - PAN_SMOOTHING)
        game_state.camera_offset[1] += (game_state.target_offset[1] - game_state.camera_offset[1]) * (1 - PAN_SMOOTHING)

        # Render
        screen.fill(COLORS['background'])
        renderer.draw_grid(game_state.camera_offset, tile_size)
        renderer.draw_trail(game_state.trail, view_bounds, game_state.camera_offset, tile_size)

        for entry in game_state.trail:
            renderer.draw_room(entry, entry['pos'], view_bounds, game_state.camera_offset, tile_size)

        renderer.draw_player(game_state.player_pos, view_bounds, game_state.camera_offset, tile_size)
        renderer.draw_hud(game_state.trail[0], game_logic.backpack)

        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
