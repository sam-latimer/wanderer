import pygame
import random
import csv
import os

# --- Constants ---
SCREEN_WIDTH, SCREEN_HEIGHT = 800, 600
HUD_WIDTH = 200  # Width of the HUD panel
GAME_WIDTH = SCREEN_WIDTH - HUD_WIDTH  # Adjusted game area width
FPS = 60
MEMORY_LIMIT = 12
BUFFER_TILES = 1
PAN_SMOOTHING = 0.85  # Higher = smoother but slower response (0-1)
MOVE_COOLDOWN = 0.15  # Cooldown between moves in seconds

# Colorss
BACKGROUND_COLOR = (30, 30, 30)
TRAIL_START_COLOR = (0, 200, 255)
TRAIL_END_COLOR = (45, 45, 45)  # Slightly lighter than background so last trail tile is visible
PLAYER_COLOR = (255, 255, 255)
TILE_BORDER_COLOR = (50, 50, 50)
HUD_BG_COLOR = (20, 20, 20)
HUD_TEXT_COLOR = (255, 255, 255)
HUD_BORDER_COLOR = (60, 60, 60)

# Default fallback color
DEFAULT_ROOM_COLOR = (60, 60, 60)

ROOMS_TSV = 'wanderer content - rooms.tsv'
ITEMS_TSV = 'wanderer content - items.tsv'



def lerp(a, b, t):
    return a + (b - a) * t


def get_gradient_color(index, total, start=TRAIL_START_COLOR, end=TRAIL_END_COLOR):
    if total <= 1:
        return start
    t = index / (total - 1)
    return tuple(int(end[i] + (start[i] - end[i]) * t) for i in range(3))


def parse_color(color_str):
    """Parse color from TSV - supports hex (#FFFFFF) or RGB (255,255,255)"""
    if not color_str or color_str.strip() == '':
        return DEFAULT_ROOM_COLOR

    color_str = color_str.strip()

    # Handle hex colors
    if color_str.startswith('#'):
        try:
            hex_color = color_str[1:]
            if len(hex_color) == 6:
                return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            pass

    # Handle RGB format like "255,128,64"
    if ',' in color_str:
        try:
            rgb = [int(x.strip()) for x in color_str.split(',')]
            if len(rgb) == 3 and all(0 <= c <= 255 for c in rgb):
                return tuple(rgb)
        except ValueError:
            pass

    return DEFAULT_ROOM_COLOR


def load_tsv_data(filename):
    """Load TSV data and return as list of dictionaries"""
    data = []
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter='\t')
            for row in reader:
                data.append(row)
    except FileNotFoundError:
        print(f"Warning: {filename} not found. Using default data.")
        return []
    return data


def load_room_data():
    """Load room data from TSV and create weighted selection list"""
    rooms_data = load_tsv_data(ROOMS_TSV)

    if not rooms_data:
        # Fallback data if file not found
        return [{
            'name'       : 'Empty Room',
            'type'       : 'room',
            'probability': '1',
            'max_loot'   : '6',
            'entry_text' : "There doesn't seem to be anything here."
        }]

    return rooms_data


def create_weighted_room_list(rooms_data):
    """Create a weighted list of rooms based on probability"""
    weighted_rooms = []
    for room in rooms_data:
        try:
            probability = int(room.get('probability', 0))
            if probability > 0:  # Only include rooms with probability > 0
                for _ in range(probability):
                    weighted_rooms.append(room)
        except ValueError:
            continue  # Skip rooms with invalid probability values

    return weighted_rooms if weighted_rooms else [rooms_data[0]]  # Fallback to first room


def load_item_data():
    """Load item data from TSV"""
    items_data = load_tsv_data(ITEMS_TSV)

    if not items_data:
        # Fallback data if file not found
        return [{
            'name'       : 'Rock',
            'probability': '16',
            'tier0'      : 'Small Pebble',
            'tier1'      : 'Stray Rock',
            'tier2'      : 'Smooth Stone'
        }]

    return items_data


def create_weighted_item_list(items_data):
    """Create a weighted list of items based on probability"""
    weighted_items = []
    for item in items_data:
        try:
            probability = int(item.get('probability', 0))
            if probability > 0:  # Only include items with probability > 0
                for _ in range(probability):
                    weighted_items.append(item)
        except ValueError:
            continue  # Skip items with invalid probability values

    return weighted_items if weighted_items else [items_data[0]]  # Fallback to first item


def generate_item(item_list, tier=0):
    """Generate a random item based on probabilities and tier"""
    if not item_list:
        return "Small Pebble"

    item_data = random.choice(item_list)
    tier_key = f'tier{min(tier, 2)}'  # Cap at tier 2

    item_name = item_data.get(tier_key, '')
    if not item_name or item_name.strip() == '':
        # Fallback to lower tiers if current tier is empty
        for fallback_tier in range(tier - 1, -1, -1):
            fallback_key = f'tier{fallback_tier}'
            item_name = item_data.get(fallback_key, '')
            if item_name and item_name.strip() != '':
                break

        # Final fallback to item name
        if not item_name or item_name.strip() == '':
            item_name = item_data.get('name', 'Unknown Item')

    return item_name.strip()


def generate_room(room_list):
    """Generate a random room based on probabilities"""
    if not room_list:
        return {
            'name'       : 'Empty Room',
            'type'       : 'room',
            'probability': '1',
            'max_loot'   : '6',
            'entry_text' : "There doesn't seem to be anything here."
        }

    return random.choice(room_list).copy()


def add_to_backpack(item_name):
    """Add an item to the player's backpack if there's space"""
    total_items = sum(backpack.values())
    if total_items < BACKPACK_CAPACITY:
        backpack[item_name] = backpack.get(item_name, 0) + 1
        print(f"Added {item_name} to backpack ({total_items + 1}/{BACKPACK_CAPACITY})")
        return True
    else:
        print(f"Backpack full! Cannot add {item_name}")
        return False


def generate_room_loot(room_data):
    """Generate loot for a room based on its max_loot value"""
    try:
        max_loot = int(room_data.get('max_loot', 6))
    except ValueError:
        max_loot = 6

    # Generate 1-3 items, but don't exceed max_loot
    num_items = min(random.randint(1, 3), max_loot)
    loot = []

    for _ in range(num_items):
        # Higher tier items are rarer - weighted towards lower tiers
        tier_roll = random.random()
        if tier_roll < 0.6:  # 60% chance
            tier = 0
        elif tier_roll < 0.85:  # 25% chance
            tier = 1
        else:  # 15% chance
            tier = 2

        item = generate_item(weighted_items, tier)
        loot.append(item)

    return loot


def move_player(target_pos):
    global player_pos, tail

    # Check if target position is already in tail
    existing_entry = None
    for entry in tail:
        if entry['pos'] == target_pos:
            existing_entry = entry
            tail.remove(entry)
            break

    # If not in tail, create new entry with random room
    if existing_entry is None:
        room_data = generate_room(weighted_rooms)
        # Generate loot for the room
        room_loot = generate_room_loot(room_data)
        existing_entry = {
            'pos'   : target_pos,
            'room'  : room_data,
            'loot'  : room_loot,
            'looted': False  # Track if player has taken loot from this room
        }

    # Add to front of trail
    tail.insert(0, existing_entry)
    player_pos = target_pos

    # Remove oldest memories if over limit
    if len(tail) > MEMORY_LIMIT:
        tail.pop()


def wrap_text(text, font, max_width):
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


def draw_hud(screen, font):
    """Draw the HUD panel on the right side"""
    # Draw HUD background
    hud_rect = pygame.Rect(GAME_WIDTH, 0, HUD_WIDTH, SCREEN_HEIGHT)
    pygame.draw.rect(screen, HUD_BG_COLOR, hud_rect)
    
    # Draw border
    pygame.draw.line(screen, HUD_BORDER_COLOR, (GAME_WIDTH, 0), (GAME_WIDTH, SCREEN_HEIGHT), 2)
    
    # Get current room info
    current_entry = tail[0]
    current_room = current_entry['room']
    
    y_offset = 10
    padding = 10
    text_width = HUD_WIDTH - padding * 2
    
    # Room name
    room_name = current_room.get('name', 'Unknown')
    text_surface = font.render(f"Room: {room_name}", True, HUD_TEXT_COLOR)
    screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
    y_offset += 25
    
    # Room type
    room_type = current_room.get('type', 'Unknown')
    text_surface = font.render(f"Type: {room_type}", True, HUD_TEXT_COLOR)
    screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
    y_offset += 25
    
    # Entry text (wrapped)
    entry_text = current_room.get('entry_text', 'No description')
    wrapped_lines = wrap_text(entry_text, font, text_width)
    for line in wrapped_lines:
        text_surface = font.render(line, True, HUD_TEXT_COLOR)
        screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
        y_offset += 20
    
    y_offset += 10
    
    # Loot status
    loot_items = current_entry.get('loot', [])
    looted = current_entry.get('looted', False)
    
    if loot_items:
        if looted:
            text_surface = font.render("Loot: (taken)", True, (128, 128, 128))
            screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
            y_offset += 20
        else:
            text_surface = font.render("Loot:", True, HUD_TEXT_COLOR)
            screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
            y_offset += 20
            
            for item in loot_items:
                text_surface = font.render(f"  {item}", True, (255, 255, 0))
                screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
                y_offset += 18
    else:
        text_surface = font.render("Loot: None", True, (128, 128, 128))
        screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
        y_offset += 20
    
    y_offset += 15
    
    # Backpack
    text_surface = font.render(f"Backpack ({sum(backpack.values())}/{BACKPACK_CAPACITY}):", True, HUD_TEXT_COLOR)
    screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
    y_offset += 20
    
    if backpack:
        for item in backpack.items():
            text_surface = font.render(f"  {item[0]} x{item[1]}", True, (200, 200, 200))
            screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))
            y_offset += 18
    else:
        text_surface = font.render("  (empty)", True, (128, 128, 128))
        screen.blit(text_surface, (GAME_WIDTH + padding, y_offset))


# --- Load Game Data ---
rooms_data = load_room_data()
weighted_rooms = create_weighted_room_list(rooms_data)

items_data = load_item_data()
weighted_items = create_weighted_item_list(items_data)

print(f"Loaded {len(rooms_data)} room types")
print(f"Created weighted room list with {len(weighted_rooms)} entries")
print(f"Loaded {len(items_data)} item types")
print(f"Created weighted item list with {len(weighted_items)} entries")

# Display room types for debugging
room_types = {}
for room in weighted_rooms:
    room_type = room.get('name', 'Unknown')
    room_types[room_type] = room_types.get(room_type, 0) + 1

print("Room distribution:")
for room_type, count in room_types.items():
    print(f"  {room_type}: {count}")

# --- Game State ---
player_pos = (0, 0)
initial_room = generate_room(weighted_rooms)
# Generate loot for the initial room too
initial_loot = generate_room_loot(initial_room)
tail = [{
    'pos'   : player_pos,
    'room'  : initial_room,
    'loot'  : initial_loot,
    'looted': False
}]

# Player inventory
backpack = {}
BACKPACK_CAPACITY = 20

camera_offset = [0, 0]  # Use floats for smoother interpolation
target_offset = [0, 0]  # do not use floats, these need to be integers later
move_timer = 0  # Timer for movement cooldown

pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Wanderer")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 18)  # Font for HUD text

running = True
while running:
    dt = clock.tick(FPS) / 1000.0
    move_timer -= dt

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            # Only handle clicks in the game area (not HUD)
            if mx < GAME_WIDTH:
                grid_x = (mx - camera_offset[0]) // tile_size
                grid_y = (my - camera_offset[1]) // tile_size
                tx = view_min_x + grid_x
                ty = view_min_y + grid_y
                target = (tx, ty)
                if abs(tx - player_pos[0]) + abs(ty - player_pos[1]) == 1:
                    move_player(target)
                    move_timer = MOVE_COOLDOWN
        elif event.type == pygame.KEYDOWN:
            if move_timer <= 0:
                dx, dy = 0, 0
                if event.key == pygame.K_w or event.key == pygame.K_UP:
                    dy = -1
                elif event.key == pygame.K_s or event.key == pygame.K_DOWN:
                    dy = 1
                elif event.key == pygame.K_a or event.key == pygame.K_LEFT:
                    dx = -1
                elif event.key == pygame.K_d or event.key == pygame.K_RIGHT:
                    dx = 1

                if dx != 0 or dy != 0:
                    target = (player_pos[0] + dx, player_pos[1] + dy)
                    move_player(target)
                    move_timer = MOVE_COOLDOWN

            # Debug: Print current room info when pressing SPACE
            if event.key == pygame.K_SPACE:
                current_entry = tail[0]
                current_room = current_entry['room']
                print(f"Current room: {current_room.get('name', 'Unknown')}")
                print(f"Type: {current_room.get('type', 'Unknown')}")
                print(f"Entry text: {current_room.get('entry_text', 'No description')}")
                print(f"Loot: {current_entry.get('loot', [])}")
                print(f"Already looted: {current_entry.get('looted', False)}")
                print(f"Backpack ({len(backpack)}/{BACKPACK_CAPACITY}): {backpack}")

            # Loot collection with L key
            if event.key == pygame.K_l:
                current_entry = tail[0]
                if not current_entry.get('looted', False) and current_entry.get('loot', []):
                    loot_items = current_entry['loot']
                    collected_items = []

                    for item in loot_items:
                        if add_to_backpack(item):
                            collected_items.append(item)
                        else:
                            break  # Stop if backpack is full

                    if collected_items:
                        current_entry['looted'] = True
                        print(f"Collected: {', '.join(collected_items)}")
                    else:
                        print("No room in backpack or no loot to collect!")
                else:
                    if current_entry.get('looted', False):
                        print("This room has already been looted.")
                    else:
                        print("No loot in this room.")

    # Calculate view bounds from tail positions
    positions = [entry['pos'] for entry in tail]
    xs = [x for x, y in positions]
    ys = [y for x, y in positions]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    view_min_x = min_x - BUFFER_TILES
    view_max_x = max_x + BUFFER_TILES
    view_min_y = min_y - BUFFER_TILES
    view_max_y = max_y + BUFFER_TILES

    view_width = int(view_max_x - view_min_x) + 1
    view_height = int(view_max_y - view_min_y) + 1

    # Use GAME_WIDTH instead of SCREEN_WIDTH for tile size calculation
    tile_size_x = GAME_WIDTH // view_width
    tile_size_y = SCREEN_HEIGHT // view_height
    tile_size = min(tile_size_x, tile_size_y)

    grid_width_px = view_width * tile_size
    grid_height_px = view_height * tile_size

    # Calculate target camera position
    target_offset[0] = (GAME_WIDTH - grid_width_px) // 2
    target_offset[1] = (SCREEN_HEIGHT - grid_height_px) // 2

    # Smooth camera movement using exponential smoothing
    camera_offset[0] += (target_offset[0] - camera_offset[0]) * (1 - PAN_SMOOTHING)
    camera_offset[1] += (target_offset[1] - camera_offset[1]) * (1 - PAN_SMOOTHING)

    # --- RENDERING ---
    screen.fill(BACKGROUND_COLOR)

    # 1. Draw full background grid (only in game area)
    grid_start_x = camera_offset[0] % tile_size - tile_size
    grid_start_y = camera_offset[1] % tile_size - tile_size

    for x in range(int(grid_start_x), GAME_WIDTH + tile_size, tile_size):
        for y in range(int(grid_start_y), SCREEN_HEIGHT + tile_size, tile_size):
            if x < GAME_WIDTH:  # Only draw grid in game area
                rect = pygame.Rect(x, y, min(tile_size, GAME_WIDTH - x), tile_size)
                pygame.draw.rect(screen, TILE_BORDER_COLOR, rect, 1)

    # 2. Draw trail gradient (excluding current player position)
    trail_without_player = tail[1:]  # Exclude current position
    for idx, entry in enumerate(reversed(trail_without_player)):
        color = get_gradient_color(idx, len(trail_without_player))
        x, y = entry['pos']
        screen_x = camera_offset[0] + (x - view_min_x) * tile_size
        screen_y = camera_offset[1] + (y - view_min_y) * tile_size
        if screen_x < GAME_WIDTH:  # Only draw if in game area
            rect = pygame.Rect(int(screen_x), int(screen_y), tile_size, tile_size)
            pygame.draw.rect(screen, color, rect)

    # 3. Draw room content (only for tiles in memory trail)
    for entry in tail:
        x, y = entry['pos']
        if view_min_x <= x <= view_max_x and view_min_y <= y <= view_max_y:
            screen_x = camera_offset[0] + (x - view_min_x) * tile_size
            screen_y = camera_offset[1] + (y - view_min_y) * tile_size

            if screen_x < GAME_WIDTH:  # Only draw if in game area
                room = entry['room']
                room_type = room.get('type', 'room')

                # Try to get color from room data, fallback to default
                color_str = room.get('color', '')
                color = parse_color(color_str)

                # Draw content as circle in center of tile
                center_x = int(screen_x + tile_size // 2)
                center_y = int(screen_y + tile_size // 2)
                radius = max(3, tile_size // 4)
                pygame.draw.circle(screen, color, (center_x, center_y), radius)
                # Draw room type text at bottom center of tile
                room_type_label = font.render(room_type.upper(), True, (180, 180, 180))
                label_rect = room_type_label.get_rect(center=(center_x, screen_y + tile_size - 10))
                screen.blit(room_type_label, label_rect)


                # Draw loot indicator if room has unlooteed items
                if entry.get('loot', []) and not entry.get('looted', False):
                    # Draw a small sparkle/star to indicate loot
                    sparkle_color = (255, 255, 0)  # Yellow
                    sparkle_size = max(2, tile_size // 8)
                    # Draw a simple plus sign as loot indicator
                    pygame.draw.line(screen, sparkle_color,
                                     (center_x - sparkle_size, center_y),
                                     (center_x + sparkle_size, center_y), 2)
                    pygame.draw.line(screen, sparkle_color,
                                     (center_x, center_y - sparkle_size),
                                     (center_x, center_y + sparkle_size), 2)

    # 4. Draw player
    px, py = tail[0]['pos']
    screen_x = camera_offset[0] + (px - view_min_x) * tile_size
    screen_y = camera_offset[1] + (py - view_min_y) * tile_size
    if screen_x < GAME_WIDTH:  # Only draw if in game area
        rect = pygame.Rect(int(screen_x), int(screen_y), tile_size, tile_size)
        pygame.draw.rect(screen, PLAYER_COLOR, rect)

    # 5. Draw HUD
    draw_hud(screen, font)

    pygame.display.flip()

pygame.quit()
