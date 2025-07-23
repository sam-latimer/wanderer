import pygame
import csv
import random
from typing import Dict, List, Tuple

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
    'loot_indicator': (255, 255, 0),
    'gray': (128, 128, 128),
    'yellow': (255, 255, 0),
    'gold': (255, 215, 0),
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'purple': (128, 0, 128),
    'orange': (255, 165, 0),
    'brown': (139, 69, 19),
    'pink': (255, 192, 203),
    'cyan': (0, 255, 255),
    'magenta': (255, 0, 255),
    'white': (255, 255, 255),
    'black': (0, 0, 0)
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

    # Normalize index to be between 0 and 1
    t = index / (total - 1)

    # Interpolate RGB values
    r = int(end[0] + (start[0] - end[0]) * t)
    g = int(end[1] + (start[1] - end[1]) * t)
    b = int(end[2] + (start[2] - end[2]) * t)

    return (r, g, b)


def parse_color(color_str: str) -> Tuple[int, int, int]:
    """Parse color from string format"""
    if not color_str or color_str.strip() == '':
        return COLORS['default_room']

    color_str = color_str.strip().lower()

    # Handle predefined colors
    if color_str in COLORS:
        return COLORS[color_str]

    # Handle hex colors
    if color_str.startswith('#'):
        try:
            hex_str = color_str[1:]
            if len(hex_str) == 6:
                return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass

    # Handle RGB tuples like "255,0,0"
    if ',' in color_str:
        try:
            parts = [int(x.strip()) for x in color_str.split(',')]
            if len(parts) == 3:
                return tuple(max(0, min(255, x)) for x in parts)
        except ValueError:
            pass

    return COLORS['default_room']


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> List[str]:
    """Wrap text to fit within max_width pixels"""
    if not text:
        return []

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

    @staticmethod
    def load_file(filename: str) -> List[Dict]:
        """Load CSV file and return as list of dictionaries"""
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                data = []
                for row in reader:
                    # Clean up the row data
                    cleaned_row = {}
                    for key, value in row.items():
                        if key:  # Skip empty keys
                            cleaned_row[key.strip()] = value.strip() if value else ''
                    data.append(cleaned_row)
                return data
        except FileNotFoundError:
            print(f"Warning: {filename} not found, using fallback data")
            return []

    def load_data(self):
        """Load all game data"""
        self.rooms_data = self.load_file('wanderer content - rooms.csv')
        self.items_data = self.load_file('wanderer content - items.csv')

        # Fallback data if files not found
        if not self.rooms_data:
            self.rooms_data = [
                {
                    'type': 'room',
                    'name': 'Empty Chamber',
                    'color': 'gray',
                    'probability': '10',
                    'max_loot': '3',
                    'flavor_text': 'A bare stone chamber with dusty corners.',
                    'action1': 'search',
                    'action2': 'take loot',
                    'action3': 'leave',
                    'action4': '',
                    'action5': ''
                },
                {
                    'type': 'treasure',
                    'name': 'Treasure Room',
                    'color': 'gold',
                    'probability': '3',
                    'max_loot': '8',
                    'flavor_text': 'Golden light reflects off piles of treasure.',
                    'action1': 'take loot',
                    'action2': 'search+',
                    'action3': 'leave',
                    'action4': '',
                    'action5': ''
                }
            ]

        if not self.items_data:
            self.items_data = [
                {
                    'name': 'coin',
                    'probability': '10',
                    'tier0': 'copper coin',
                    'tier1': 'silver coin',
                    'tier2': 'gold coin'
                },
                {
                    'name': 'gem',
                    'probability': '5',
                    'tier0': 'rough stone',
                    'tier1': 'polished gem',
                    'tier2': 'precious jewel'
                }
            ]

        self.create_weighted_lists()

    def create_weighted_lists(self):
        """Create weighted lists for random selection"""
        self.weighted_rooms = []
        self.weighted_items = []

        for room in self.rooms_data:
            try:
                prob = int(room.get('probability', 0))
                if prob > 0:
                    self.weighted_rooms.extend([room] * prob)
            except (ValueError, TypeError):
                continue

        for item in self.items_data:
            try:
                prob = int(item.get('probability', 0))
                if prob > 0:
                    self.weighted_items.extend([item] * prob)
            except (ValueError, TypeError):
                continue

        # Ensure we have at least one room and item
        if not self.weighted_rooms and self.rooms_data:
            self.weighted_rooms = [self.rooms_data[0]]
        if not self.weighted_items and self.items_data:
            self.weighted_items = [self.items_data[0]]


# --- Game Logic ---
class GameLogic:
    def __init__(self, game_data: GameData):
        self.game_data = game_data
        self.backpack = {}

    def add_to_backpack(self, item_name: str) -> bool:
        """Add item to backpack if there's space"""
        if sum(self.backpack.values()) < BACKPACK_CAPACITY:
            self.backpack[item_name] = self.backpack.get(item_name, 0) + 1
            return True
        return False

    def action_take_loot(self, current_room: Dict) -> str:
        """Take loot from current room"""
        if not current_room.get('loot', []):
            return "There's nothing to take."

        if sum(self.backpack.values()) >= BACKPACK_CAPACITY:
            return "Your backpack is full!"

        item_name = current_room['loot'].pop(0)
        self.add_to_backpack(item_name)

        if not current_room['loot']:
            current_room['looted'] = True

        return f"You found {item_name}!"

    def action_search(self, current_room: Dict) -> str:
        """Search the room for additional items"""
        if random.random() < 0.3:  # 30% chance to find something
            tier = random.randint(0, 1)  # Lower tier for regular search
            item = self.generate_item(tier)
            if self.add_to_backpack(item):
                return f"You search and find {item}!"
            else:
                return f"You found {item}, but your backpack is full!"
        else:
            return "You search but find nothing of interest."

    def action_search_plus(self, current_room: Dict) -> str:
        """Enhanced search with better rewards"""
        if random.random() < 0.5:  # 50% chance to find something
            tier = random.randint(1, 2)  # Higher tier for enhanced search
            item = self.generate_item(tier)
            if self.add_to_backpack(item):
                return f"You search thoroughly and find {item}!"
            else:
                return f"You found {item}, but your backpack is full!"
        else:
            return "You search extensively but find nothing."

    def perform_action(self, action_text: str, current_room: Dict) -> str:
        """Perform an action based on the action text"""
        if not action_text or action_text.strip() == '':
            return "No action available."

        action = action_text.strip().lower()

        # Handle specific actions
        if action == "take loot":
            return self.action_take_loot(current_room)
        elif action == "search":
            return self.action_search(current_room)
        elif action == "search+":
            return self.action_search_plus(current_room)
        elif action == "leave":
            return "You decide to leave."
        elif action == "rest":
            return "You rest for a moment, feeling refreshed."
        elif action == "inspect":
            return current_room['room'].get('inspect_passed', 'You inspect the area carefully.')
        else:
            # Generic action response
            return f"You {action}."

    def generate_room(self) -> Dict:
        """Generate a random room based on probabilities"""
        if not self.game_data.weighted_rooms:
            return {
                'type': 'room',
                'name': 'Empty Room',
                'color': 'gray',
                'probability': '1',
                'max_loot': '3',
                'flavor_text': "There doesn't seem to be anything here.",
                'action1': 'search',
                'action2': 'take loot',
                'action3': 'leave',
                'action4': '',
                'action5': ''
            }

        room_template = random.choice(self.game_data.weighted_rooms)
        return room_template.copy()

    def generate_item(self, tier: int = 0) -> str:
        """Generate a random item based on tier"""
        if not self.game_data.weighted_items:
            return "Small Pebble"

        item_data = random.choice(self.game_data.weighted_items)
        tier_key = f'tier{min(tier, 2)}'

        item_name = item_data.get(tier_key, '')
        if not item_name or item_name.strip() == '':
            # Fallback to lower tiers
            for fallback_tier in range(tier - 1, -1, -1):
                fallback_key = f'tier{fallback_tier}'
                item_name = item_data.get(fallback_key, '')
                if item_name and item_name.strip() != '':
                    break

            # Final fallback
            if not item_name or item_name.strip() == '':
                item_name = item_data.get('name', 'Unknown Item')

        return item_name.strip()

    def generate_room_loot(self, room_data: Dict) -> List[str]:
        """Generate loot for a room"""
        try:
            max_loot = int(float(room_data.get('max_loot', 3)))
        except (ValueError, TypeError):
            max_loot = 3

        if max_loot <= 0:
            return []

        num_items = random.randint(1, min(max_loot, 5))
        loot = []

        for _ in range(num_items):
            tier_roll = random.random()
            if tier_roll < 0.6:
                tier = 0
            elif tier_roll < 0.85:
                tier = 1
            else:
                tier = 2

            item = self.generate_item(tier)
            loot.append(item)

        return loot


# --- Game State ---
class GameState:
    def __init__(self, game_data: GameData, game_logic: GameLogic):
        self.game_data = game_data
        self.game_logic = game_logic
        self.player_pos = (0, 0)
        self.trail = []
        self.camera_offset = [0.0, 0.0]
        self.target_offset = [0.0, 0.0]
        self.move_timer = 0.0
        self.action_message = ""
        self.message_timer = 0.0
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
        # Check if we've been to this position before
        existing_entry = None
        for i, entry in enumerate(self.trail):
            if entry['pos'] == target_pos:
                existing_entry = self.trail.pop(i)
                break

        if existing_entry is None:
            # Generate new room
            room_data = self.game_logic.generate_room()
            room_loot = self.game_logic.generate_room_loot(room_data)
            existing_entry = {
                'pos': target_pos,
                'room': room_data,
                'loot': room_loot,
                'looted': False
            }

        # Add to front of trail (current position)
        self.trail.insert(0, existing_entry)
        self.player_pos = target_pos

        # Remove oldest rooms if we exceed memory limit
        if len(self.trail) > MEMORY_LIMIT:
            self.trail.pop()


# --- Rendering ---
class Renderer:
    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen = screen
        self.font = font

    def draw_grid(self, camera_offset: List[float], tile_size: int):
        """Draw the background grid"""
        grid_start_x = int(camera_offset[0] % tile_size - tile_size)
        grid_start_y = int(camera_offset[1] % tile_size - tile_size)

        for x in range(grid_start_x, GAME_WIDTH + tile_size, tile_size):
            for y in range(grid_start_y, SCREEN_HEIGHT + tile_size, tile_size):
                if x < GAME_WIDTH:
                    rect = pygame.Rect(x, y, min(tile_size, GAME_WIDTH - x), tile_size)
                    pygame.draw.rect(self.screen, COLORS['tile_border'], rect, 2)

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

            # Draw room background
            rect = pygame.Rect(int(screen_x), int(screen_y), tile_size, tile_size)
            pygame.draw.rect(self.screen, color, rect)
            pygame.draw.rect(self.screen, COLORS['tile_border'], rect, 2)

            # Draw room type indicator
            center_x = int(screen_x + tile_size // 2)
            center_y = int(screen_y + tile_size // 2)

            room_type = room_data.get('type', 'room').upper()
            if len(room_type) > 0:
                type_label = self.font.render(room_type[0], True, COLORS['hud_text'])
                label_rect = type_label.get_rect(center=(center_x, center_y))
                self.screen.blit(type_label, label_rect)

            # Draw loot indicator
            if room_entry.get('loot', []) and not room_entry.get('looted', False):
                sparkle_size = max(3, tile_size // 6)
                pygame.draw.line(self.screen, COLORS['loot_indicator'],
                                 (center_x - sparkle_size, center_y),
                                 (center_x + sparkle_size, center_y), 2)
                pygame.draw.line(self.screen, COLORS['loot_indicator'],
                                 (center_x, center_y - sparkle_size),
                                 (center_x, center_y + sparkle_size), 2)

    def draw_trail(self, trail: List[Dict], view_bounds: Dict, camera_offset: List[float], tile_size: int):
        """Draw the trail of visited rooms with inward creeping effect"""
        trail_without_player = trail[1:]  # Skip current room

        # Draw from oldest to newest for proper layering
        for idx, tile in enumerate(reversed(trail_without_player)):
            # Calculate progress (0 = newest, 1 = oldest)
            progress = idx / max(1, len(trail_without_player) - 1)

            # Calculate color with alpha
            start_color = COLORS['trail_start']
            end_color = COLORS['trail_end']

            # Interpolate color with alpha
            color = (
                int(start_color[0] + (end_color[0] - start_color[0]) * progress),
                int(start_color[1] + (end_color[1] - start_color[1]) * progress),
                int(start_color[2] + (end_color[2] - start_color[2]) * progress),
                int(255 - 155 * progress)  # Alpha from 255 to 100
            )

            x, y = tile['pos']
            screen_x = camera_offset[0] + (x - view_bounds['min_x']) * tile_size
            screen_y = camera_offset[1] + (y - view_bounds['min_y']) * tile_size

            if screen_x < GAME_WIDTH:
                # Create a transparent surface for this trail tile
                tile_surface = pygame.Surface((tile_size, tile_size), pygame.SRCALPHA)

                # Calculate the inward creep
                # For newest tiles: thin border (outline_width = 2)
                # For oldest tiles: almost filled (outline_width = tile_size/2 - 1)
                min_width = 2
                max_width = tile_size // 2 - 1
                outline_width = int(min_width + progress * (max_width - min_width))

                # Draw the outline that creeps inward
                pygame.draw.rect(tile_surface, color, 
                                (0, 0, tile_size, tile_size), 0)  # Fill with semi-transparent color

                # Draw inner rect with transparent center
                inner_rect = (outline_width, outline_width, 
                            tile_size - 2*outline_width, tile_size - 2*outline_width)
                if inner_rect[2] > 0 and inner_rect[3] > 0:  # Make sure we don't have negative dimensions
                    pygame.draw.rect(tile_surface, (0, 0, 0, 0), inner_rect, 0)  # Transparent inner

                # Blit the trail tile to the screen
                self.screen.blit(tile_surface, (int(screen_x), int(screen_y)))

    def draw_player(self, pos: Tuple[int, int], view_bounds: Dict,
                    camera_offset: List[float], tile_size: int):
        """Draw the player"""
        x, y = pos
        screen_x = camera_offset[0] + (x - view_bounds['min_x']) * tile_size
        screen_y = camera_offset[1] + (y - view_bounds['min_y']) * tile_size

        if screen_x < GAME_WIDTH:
            center_x = int(screen_x + tile_size // 2)
            center_y = int(screen_y + tile_size // 2)
            radius = max(4, tile_size // 4)

            # Draw player as a circle
            pygame.draw.circle(self.screen, COLORS['player'], (center_x, center_y), radius)
            pygame.draw.circle(self.screen, (0, 0, 0), (center_x, center_y), radius, 2)

    def draw_hud(self, current_room: Dict, backpack: Dict, action_message: str = ""):
        """Draw the HUD panel"""
        hud_rect = pygame.Rect(GAME_WIDTH, 0, HUD_WIDTH, SCREEN_HEIGHT)
        pygame.draw.rect(self.screen, COLORS['hud_bg'], hud_rect)
        pygame.draw.line(self.screen, COLORS['hud_border'],
                         (GAME_WIDTH, 0), (GAME_WIDTH, SCREEN_HEIGHT), 2)

        padding = 10
        y_offset = 10

        # Room info
        room_name = current_room['room'].get('name', 'Unknown')
        text = self.font.render(f"Room: {room_name}", True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 25

        room_type = current_room['room'].get('type', 'Unknown')
        text = self.font.render(f"Type: {room_type}", True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 25

        # Room description
        flavor_text = current_room['room'].get('flavor_text', 'No description')
        wrapped_lines = wrap_text(flavor_text, self.font, HUD_WIDTH - padding * 2)
        for line in wrapped_lines:
            text = self.font.render(line, True, COLORS['hud_text'])
            self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
            y_offset += 18
        y_offset += 10

        # Available actions
        text = self.font.render("Actions:", True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 20

        for i in range(1, 6):
            action_key = f'action{i}'
            action_text = current_room['room'].get(action_key, '')
            if action_text and action_text.strip() != '':
                text = self.font.render(f"{i}: {action_text}", True, COLORS['hud_text'])
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 18

        y_offset += 10

        # Loot info
        if current_room.get('loot', []):
            if current_room.get('looted', False):
                text = self.font.render("Loot: (taken)", True, (128, 128, 128))
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 20
            else:
                text = self.font.render("Loot available:", True, COLORS['hud_text'])
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 20
                for item in current_room['loot'][:3]:  # Show first 3 items
                    text = self.font.render(f"  {item}", True, COLORS['loot_indicator'])
                    self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                    y_offset += 16
                if len(current_room['loot']) > 3:
                    text = self.font.render(f"  ...and {len(current_room['loot']) - 3} more",
                                            True, COLORS['loot_indicator'])
                    self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                    y_offset += 16

        y_offset += 10

        # Action message
        if action_message:
            message_rect = pygame.Rect(GAME_WIDTH + padding, y_offset, HUD_WIDTH - padding * 2, 50)
            pygame.draw.rect(self.screen, (40, 40, 40), message_rect)
            pygame.draw.rect(self.screen, COLORS['hud_border'], message_rect, 1)

            wrapped_lines = wrap_text(action_message, self.font, HUD_WIDTH - padding * 4)
            msg_y = y_offset + 8
            for line in wrapped_lines[:2]:  # Limit to 2 lines
                text = self.font.render(line, True, (255, 255, 100))
                self.screen.blit(text, (GAME_WIDTH + padding * 2, msg_y))
                msg_y += 18

            y_offset += 60

        # Backpack
        backpack_count = sum(backpack.values())
        text = self.font.render(f"Backpack ({backpack_count}/{BACKPACK_CAPACITY}):",
                                True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 20

        if backpack:
            items_shown = 0
            for item, count in backpack.items():
                if items_shown >= 10:  # Limit display
                    remaining = len(backpack) - items_shown
                    text = self.font.render(f"  ...and {remaining} more types",
                                            True, (128, 128, 128))
                    self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                    break
                text = self.font.render(f"  {item} x{count}", True, (200, 200, 200))
                self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
                y_offset += 16
                items_shown += 1
        else:
            text = self.font.render("  (empty)", True, (128, 128, 128))
            self.screen.blit(text, (GAME_WIDTH + padding, y_offset))

        # Controls help at bottom
        y_offset = SCREEN_HEIGHT - 80
        text = self.font.render("Controls:", True, COLORS['hud_text'])
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 18
        text = self.font.render("WASD: Move", True, (180, 180, 180))
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))
        y_offset += 16
        text = self.font.render("1-5: Actions", True, (180, 180, 180))
        self.screen.blit(text, (GAME_WIDTH + padding, y_offset))


def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Wanderer - Memory Trail")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 16)

    # Initialize game systems
    game_data = GameData()
    game_logic = GameLogic(game_data)
    game_state = GameState(game_data, game_logic)
    renderer = Renderer(screen, font)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        game_state.move_timer = max(0, game_state.move_timer - dt)

        # Update message timer
        if game_state.message_timer > 0:
            game_state.message_timer -= dt
            if game_state.message_timer <= 0:
                game_state.action_message = ""

        # Handle input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and game_state.move_timer <= 0:
                dx, dy = 0, 0
                if event.key in [pygame.K_w, pygame.K_UP]:
                    dy = -1
                elif event.key in [pygame.K_s, pygame.K_DOWN]:
                    dy = 1
                elif event.key in [pygame.K_a, pygame.K_LEFT]:
                    dx = -1
                elif event.key in [pygame.K_d, pygame.K_RIGHT]:
                    dx = 1
                # Handle numeric keys for actions
                elif event.key in [pygame.K_1, pygame.K_KP1]:
                    current_entry = game_state.trail[0]
                    action_text = current_entry['room'].get('action1', '')
                    if action_text:
                        game_state.action_message = game_logic.perform_action(action_text, current_entry)
                        game_state.message_timer = 3.0
                elif event.key in [pygame.K_2, pygame.K_KP2]:
                    current_entry = game_state.trail[0]
                    action_text = current_entry['room'].get('action2', '')
                    if action_text:
                        game_state.action_message = game_logic.perform_action(action_text, current_entry)
                        game_state.message_timer = 3.0
                elif event.key in [pygame.K_3, pygame.K_KP3]:
                    current_entry = game_state.trail[0]
                    action_text = current_entry['room'].get('action3', '')
                    if action_text:
                        game_state.action_message = game_logic.perform_action(action_text, current_entry)
                        game_state.message_timer = 3.0
                elif event.key in [pygame.K_4, pygame.K_KP4]:
                    current_entry = game_state.trail[0]
                    action_text = current_entry['room'].get('action4', '')
                    if action_text:
                        game_state.action_message = game_logic.perform_action(action_text, current_entry)
                        game_state.message_timer = 3.0
                elif event.key in [pygame.K_5, pygame.K_KP5]:
                    current_entry = game_state.trail[0]
                    action_text = current_entry['room'].get('action5', '')
                    if action_text:
                        game_state.action_message = game_logic.perform_action(action_text, current_entry)
                        game_state.message_timer = 3.0

                if dx != 0 or dy != 0:
                    target = (game_state.player_pos[0] + dx, game_state.player_pos[1] + dy)
                    game_state.move_player(target)
                    game_state.move_timer = MOVE_COOLDOWN
                    # Clear action message when moving
                    game_state.action_message = ""
                    game_state.message_timer = 0

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

        for entry in game_state.trail:
            renderer.draw_room(entry, entry['pos'], view_bounds, game_state.camera_offset, tile_size)

        renderer.draw_trail(game_state.trail, view_bounds, game_state.camera_offset, tile_size)
        renderer.draw_hud(game_state.trail[0], game_logic.backpack, game_state.action_message)
        renderer.draw_player(game_state.player_pos, view_bounds, game_state.camera_offset, tile_size)


        pygame.display.flip()

    pygame.quit()


if __name__ == "__main__":
    main()
