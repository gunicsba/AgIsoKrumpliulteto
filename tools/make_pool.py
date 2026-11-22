"""Builds the potato planter VT object pool and the C++ header with its object ids.

    python tools/make_pool.py

Writes:
    pool/krumpliulteto.iop          the object pool (ISO 11783-6, VT version 4)
    include/krumpli_pool_ids.hpp    object ids and key codes for the ECU firmware

Layout: data masks are 480 x 480, soft keys 60 x 60 (the AgIsoVirtualTerminal defaults).
Texts are Hungarian, ISO 8859-2 (font type 2). Python 3.10+, standard library only.
"""

import pathlib
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]

# --- Colours ---------------------------------------------------------------------------------
BLACK, WHITE, GREEN, TEAL, MAROON, PURPLE, OLIVE, SILVER = range(8)
GREY, BLUE, LIME, CYAN, RED, MAGENTA, YELLOW, NAVY = range(8, 16)


def rgb(r, g, b):
    """Colour of the 6x6x6 cube in the standard palette, each component 0..5 (0x00, 0x33 .. 0xFF)."""
    return 16 + r * 36 + g * 6 + b


DARK_GREEN = rgb(0, 2, 0)
POTATO = rgb(4, 3, 1)
POTATO_DARK = rgb(3, 2, 0)
PANEL = rgb(5, 5, 5)
BACKGROUND = rgb(4, 4, 4)
LABEL = rgb(1, 1, 1)
ALARM_RED = rgb(4, 0, 0)
KEY_BG = rgb(4, 4, 3)

# --- Font sizes ------------------------------------------------------------------------------
F6x8, F8x8, F8x12, F12x16, F16x16, F16x24, F24x32, F32x32, F32x48, F48x64 = range(10)
LATIN2 = 2  # ISO 8859-2, Hungarian ő and ű

# --- Justification (VT 4): horizontal | vertical ---------------------------------------------
LEFT, CENTER, RIGHT = 0, 1, 2
TOP, MIDDLE, BOTTOM = 0, 4, 8

NONE = 0xFFFF


def u8(v):
    return struct.pack("<B", v)


def u16(v):
    return struct.pack("<H", v)


def i16(v):
    return struct.pack("<h", v)


def u32(v):
    return struct.pack("<I", v)


def i32(v):
    return struct.pack("<i", v)


def f32(v):
    return struct.pack("<f", v)


def children(items):
    """List of (object id, x, y)."""
    return b"".join(u16(i) + i16(x) + i16(y) for i, x, y in items)


class Pool:
    def __init__(self):
        self.objects = {}
        self.order = []
        self.references = []
        self.names = {}
        self.fonts = {}
        self.lines = {}
        self.fills = {}
        self.next_auto = 30000

    def add(self, object_id, body, refs=(), name=None):
        if object_id in self.objects:
            raise ValueError(f"duplicate object id {object_id}")
        self.objects[object_id] = u16(object_id) + body
        self.order.append(object_id)
        self.references += [(object_id, r) for r in refs if r != NONE]
        if name:
            self.names[name] = object_id
        return object_id

    def auto(self):
        self.next_auto += 1
        return self.next_auto

    # Attributes are shared: one object per distinct look.
    def font(self, colour, size, style=0):
        key = (colour, size, style)
        if key not in self.fonts:
            self.fonts[key] = self.add(self.auto(), u8(23) + u8(colour) + u8(size) + u8(LATIN2) + u8(style) + u8(0))
        return self.fonts[key]

    def line(self, colour, width=1, art=0xFFFF):
        key = (colour, width, art)
        if key not in self.lines:
            self.lines[key] = self.add(self.auto(), u8(24) + u8(colour) + u8(width) + u16(art) + u8(0))
        return self.lines[key]

    def fill(self, colour):
        if colour not in self.fills:
            self.fills[colour] = self.add(self.auto(), u8(25) + u8(2) + u8(colour) + u16(NONE) + u8(0))
        return self.fills[colour]

    # Output objects ----------------------------------------------------------------------
    def text(self, w, h, text, colour=BLACK, size=F8x12, just=LEFT | MIDDLE, bg=WHITE, transparent=True, object_id=None, name=None, wrap=False):
        data = text.encode("iso-8859-2")
        font = self.font(colour, size)
        return self.add(object_id or self.auto(),
                        u8(11) + u16(w) + u16(h) + u8(bg) + u16(font) + u8((1 if transparent else 0) | (2 if wrap else 0)) + u16(NONE) +
                        u8(just) + u16(len(data)) + data + u8(0), refs=[font], name=name)

    def number(self, object_id, w, h, value, scale, decimals, colour=BLACK, size=F16x24, just=RIGHT | MIDDLE, offset=0, name=None,
               var=NONE):
        font = self.font(colour, size)
        return self.add(object_id, u8(12) + u16(w) + u16(h) + u8(WHITE) + u16(font) + u8(1) + u16(var) + u32(value) +
                        i32(offset) + f32(scale) + u8(decimals) + u8(0) + u8(just) + u8(0), refs=[font, var], name=name)

    def number_variable(self, object_id, value, name=None):
        return self.add(object_id, u8(21) + u32(value), name=name)

    def input_number(self, object_id, w, h, value, minimum, maximum, scale, decimals, size=F16x24, name=None):
        font = self.font(BLACK, size)
        return self.add(object_id, u8(9) + u16(w) + u16(h) + u8(WHITE) + u16(font) + u8(0) + u16(NONE) + u32(value) +
                        u32(minimum) + u32(maximum) + i32(0) + f32(scale) + u8(decimals) + u8(0) + u8(RIGHT | MIDDLE) +
                        u8(1) + u8(0), refs=[font], name=name)

    def rect(self, w, h, fill_colour, line_colour=None, line_width=1, object_id=None, name=None):
        line = self.line(line_colour if line_colour is not None else fill_colour, line_width)
        fill = self.fill(fill_colour)
        return self.add(object_id or self.auto(), u8(14) + u16(line) + u16(w) + u16(h) + u8(0) + u16(fill) + u8(0),
                        refs=[line, fill], name=name)

    def hline(self, w, colour, width=1):
        line = self.line(colour, width)
        return self.add(self.auto(), u8(13) + u16(line) + u16(w) + u16(1) + u8(0) + u8(0), refs=[line])

    def ellipse(self, w, h, fill_colour, line_colour, line_width=1, object_id=None, name=None):
        line = self.line(line_colour, line_width)
        fill = self.fill(fill_colour)
        return self.add(object_id or self.auto(), u8(15) + u16(line) + u16(w) + u16(h) + u8(0) + u8(0) + u8(0) + u16(fill) + u8(0),
                        refs=[line, fill], name=name)

    def polygon(self, w, h, points, fill_colour, line_colour, line_width=1):
        line = self.line(line_colour, line_width)
        fill = self.fill(fill_colour)
        body = (u8(16) + u16(w) + u16(h) + u16(line) + u16(fill) + u8(0) + u8(len(points)) + u8(0) +
                b"".join(u16(x) + u16(y) for x, y in points))
        return self.add(self.auto(), body, refs=[line, fill])

    def bar(self, object_id, w, h, value, colour, ticks=0, target=None, name=None, maximum=100, var=NONE):
        options = 0x01 | 0x10 | 0x20  # border, horizontal, grows to the right
        if target is not None:
            options |= 0x02
        if ticks:
            options |= 0x04
        return self.add(object_id, u8(18) + u16(w) + u16(h) + u8(colour) + u8(BLACK) + u8(options) + u8(ticks) +
                        u16(0) + u16(maximum) + u16(var) + u16(value) + u16(NONE) + u16(target or 0) + u8(0),
                        refs=[var], name=name)

    def container(self, w, h, items):
        return self.add(self.auto(), u8(3) + u16(w) + u16(h) + u8(0) + u8(len(items)) + u8(0) + children(items),
                        refs=[i for i, _, _ in items])

    # Masks -------------------------------------------------------------------------------
    def data_mask(self, object_id, soft_key_mask, items, bg=BACKGROUND, name=None):
        return self.add(object_id, u8(1) + u8(bg) + u16(soft_key_mask) + u8(len(items)) + u8(0) + children(items),
                        refs=[soft_key_mask] + [i for i, _, _ in items], name=name)

    def alarm_mask(self, object_id, soft_key_mask, items, priority=0, acoustic=0, bg=ALARM_RED, name=None):
        return self.add(object_id, u8(2) + u8(bg) + u16(soft_key_mask) + u8(priority) + u8(acoustic) + u8(len(items)) + u8(0) +
                        children(items), refs=[soft_key_mask] + [i for i, _, _ in items], name=name)

    def soft_key_mask(self, object_id, keys, name=None):
        return self.add(object_id, u8(4) + u8(BACKGROUND) + u8(len(keys)) + u8(0) + b"".join(u16(k) for k in keys),
                        refs=keys, name=name)

    def key(self, object_id, key_code, items, bg=KEY_BG, name=None):
        return self.add(object_id, u8(5) + u8(bg) + u8(key_code) + u8(len(items)) + u8(0) + children(items),
                        refs=[i for i, _, _ in items], name=name)

    def working_set(self, active_mask, items):
        body = (u8(0) + u8(PANEL) + u8(1) + u16(active_mask) + u8(len(items)) + u8(0) + u8(1) + children(items) + b"hu")
        self.add(0, body, refs=[active_mask] + [i for i, _, _ in items])
        self.order.remove(0)
        self.order.insert(0, 0)  # the working set goes first

    def build(self):
        missing = sorted({r for _, r in self.references if r not in self.objects})
        if missing:
            raise ValueError(f"referenced objects missing: {missing}")
        return b"".join(self.objects[i] for i in self.order)


# --- Object ids -----------------------------------------------------------------------------
# Masks
DM_MAIN, DM_SETTINGS, DM_SERVICE = 1000, 1001, 1002
AM_JAM, AM_LAG, AM_NO_SPEED, AM_MOTOR = 1100, 1101, 1102, 1103
SKM_MAIN, SKM_SETTINGS, SKM_SERVICE, SKM_ALARM = 2000, 2001, 2002, 2100

# Keys and their key codes (the code the ECU gets in the Soft Key Activation message)
KEYS = {
    "KEY_SPACING_UP": (5000, 1),
    "KEY_SPACING_DOWN": (5001, 2),
    "KEY_RESET_COUNTERS": (5003, 4),
    "KEY_SETTINGS": (5004, 5),
    "KEY_SERVICE": (5005, 6),
    "KEY_HOME": (5006, 7),
    "KEY_CALIBRATE": (5007, 8),
    "KEY_ALARM_ACK": (5008, 9),
}

# Values the ECU changes at runtime (Change Numeric Value / Change String Value / Change Attribute)
IN_TARGET_SPACING = 6000          # mm, shown as cm with 1 decimal
OUT_ACTUAL_SPACING = 6001         # mm
OUT_SEEDS_PER_HA = 6002           # tő/ha
OUT_SPEED = 6003                  # 0.01 km/h
OUT_SPEED_SOURCE = 6004           # string, 6 chars: "MSS", "GROUND", "WHEEL", "NINCS"
OUT_WORK_SWITCH_TEXT = 6005       # string, 5 chars: "LENT" / "FENT"
OBJ_WORK_SWITCH_LED = 6006        # ellipse, change its fill attribute
OUT_STATUS_TEXT = 6007            # string, 9 chars: "DOLGOZIK" / "ÁLL" / "RIASZTÁS"
OBJ_STATUS_BOX = 6008             # rectangle, change its fill attribute
OUT_MOTOR_PWM_BAR = 6009          # shows VAR_MOTOR_PWM
OUT_MOTOR_PWM = 6010              # shows VAR_MOTOR_PWM
OUT_POSITION_ERROR_BAR = 6011     # 0..100, 50 = no error
OUT_POSITION_ERROR = 6012         # 0.01 cup, offset so that 0 cup = 10000
OUT_AREA_DAY = 6013               # 0.01 ha
OUT_AREA_TOTAL = 6014             # 0.1 ha
OUT_SEEDS_DAY = 6015              # pieces
OUT_SEEDS_TOTAL = 6016            # pieces
OUT_MOTOR_STATE = 6017            # string, 8 chars
OUT_MOTOR_CURRENT = 6018          # 0.1 A
VAR_MOTOR_PWM = 6019              # number variable, 0.01 % (0..10000): PWM bar and number together

# Settings
IN_ROW_SPACING = 6100             # cm
IN_ROW_COUNT = 6101
IN_SPACING_STEP = 6102            # mm, shown as cm
IN_START_ADVANCE = 6103           # mm, shown as cm
IN_SPEED_DEADBAND = 6104          # 0.1 km/h
IN_PULSES_PER_CUP = 6105
IN_CUPS_PER_REV = 6106
IN_GEAR_RATIO = 6107              # 0.01

# Service
IN_KP_POS = 6200                  # 0.01
IN_PI_KP = 6201                   # 0.01
IN_PI_KI = 6202                   # 0.01
IN_MAX_LAG = 6203                 # 0.1 cup
IN_CURRENT_LIMIT = 6204           # 0.1 A
IN_SOFT_START = 6205              # ms
IN_CAL_CUPS = 6206                # cups to turn for calibration
OUT_CAL_PULSES = 6207             # pulses counted

FILL_GREEN = "FILL_GREEN"
FILL_RED = "FILL_RED"
FILL_GREY = "FILL_GREY"


def key_label(pool, key_name, big, small, big_size=F24x32, colour=BLACK):
    object_id, code = KEYS[key_name]
    items = []
    if big:
        items.append((pool.text(60, 36, big, colour, big_size, CENTER | MIDDLE), 0, 2))
    items.append((pool.text(60, 18, small, BLACK, F6x8 if len(small) > 7 else F8x12, CENTER | MIDDLE), 0, 40))
    pool.key(object_id, code, items, name=key_name)


def potato_icon(pool, w, h):
    """A potato: brown ellipse with darker eyes."""
    body = pool.ellipse(w, h, POTATO, POTATO_DARK, 2)
    eye = pool.ellipse(max(4, w // 10), max(3, h // 10), POTATO_DARK, POTATO_DARK)
    return [(body, 0, 0), (eye, w * 3 // 10, h * 3 // 10), (eye, w * 6 // 10, h // 2), (eye, w * 4 // 10, h * 7 // 10)]


def panel(pool, w, h, title):
    """White panel with a title; returns the items relative to the panel corner."""
    return [(pool.rect(w, h, PANEL, GREY), 0, 0),
            (pool.text(w - 16, 16, title, LABEL, F8x12), 8, 4)]


def offset(items, dx, dy):
    return [(i, x + dx, y + dy) for i, x, y in items]


def header(pool, title):
    return [(pool.rect(480, 44, DARK_GREEN), 0, 0),
            *offset(potato_icon(pool, 40, 28), 8, 8),
            (pool.text(300, 44, title, WHITE, F16x24, LEFT | MIDDLE), 58, 0)]


def setting_row(pool, label, unit, input_id, value, minimum, maximum, scale, decimals, y):
    return [(pool.text(240, 32, label, BLACK, F12x16), 16, y),
            (pool.input_number(input_id, 120, 32, value, minimum, maximum, scale, decimals, F16x24), 256, y),
            (pool.text(80, 32, unit, LABEL, F12x16), 384, y)]


def build():
    p = Pool()

    p.number_variable(VAR_MOTOR_PWM, 4235, name="VAR_MOTOR_PWM")

    # Attributes the ECU switches between with Change Attribute
    p.names[FILL_GREEN] = p.fill(rgb(0, 4, 0))
    p.names[FILL_RED] = p.fill(RED)
    p.names[FILL_GREY] = p.fill(GREY)

    # --- Soft keys --------------------------------------------------------------------------
    key_label(p, "KEY_SPACING_UP", "+", "TŐTÁV")
    key_label(p, "KEY_SPACING_DOWN", "-", "TŐTÁV")
    key_label(p, "KEY_RESET_COUNTERS", "0", "NULLÁZ")
    key_label(p, "KEY_SETTINGS", "...", "BEÁLLÍT", F16x24)
    key_label(p, "KEY_SERVICE", "S", "SZERVIZ")
    key_label(p, "KEY_HOME", "<", "VISSZA")
    key_label(p, "KEY_CALIBRATE", "C", "KALIBR.")
    key_label(p, "KEY_ALARM_ACK", "OK", "NYUGTA", F24x32, DARK_GREEN)

    k = {name: object_id for name, (object_id, _) in KEYS.items()}
    p.soft_key_mask(SKM_MAIN, [k["KEY_SPACING_UP"], k["KEY_SPACING_DOWN"], k["KEY_RESET_COUNTERS"],
                               NONE, NONE, k["KEY_SETTINGS"]], name="SKM_MAIN")
    p.soft_key_mask(SKM_SETTINGS, [k["KEY_HOME"], NONE, NONE, NONE, NONE, k["KEY_SERVICE"]], name="SKM_SETTINGS")
    p.soft_key_mask(SKM_SERVICE, [k["KEY_HOME"], NONE, k["KEY_CALIBRATE"]], name="SKM_SERVICE")
    p.soft_key_mask(SKM_ALARM, [k["KEY_ALARM_ACK"]], name="SKM_ALARM")

    # --- Main working screen ---------------------------------------------------------------
    status_box = p.rect(130, 30, rgb(0, 4, 0), WHITE, 2, OBJ_STATUS_BOX, "OBJ_STATUS_BOX")
    status = p.text(130, 30, "DOLGOZIK", WHITE, F12x16, CENTER | MIDDLE, object_id=OUT_STATUS_TEXT, name="OUT_STATUS_TEXT")

    spacing = panel(p, 464, 132, "Tőtáv") + [
        (p.text(140, 16, "cél", LABEL, F8x12), 12, 24),
        (p.input_number(IN_TARGET_SPACING, 150, 56, 300, 100, 800, 0.1, 1, F32x48, name="IN_TARGET_SPACING"), 8, 42),
        (p.text(40, 56, "cm", BLACK, F16x24, LEFT | BOTTOM), 164, 40),
        (p.text(120, 16, "tényleges", LABEL, F8x12), 236, 28),
        (p.number(OUT_ACTUAL_SPACING, 110, 32, 304, 0.1, 1, BLACK, F16x24, name="OUT_ACTUAL_SPACING"), 236, 44),
        (p.text(48, 32, "cm", LABEL, F12x16, LEFT | BOTTOM), 350, 44),
        (p.text(120, 16, "tő / ha", LABEL, F8x12), 236, 82),
        (p.number(OUT_SEEDS_PER_HA, 110, 32, 44444, 1, 0, BLACK, F16x24, name="OUT_SEEDS_PER_HA"), 236, 98),
        (p.text(80, 16, "sortáv 75 cm", LABEL, F6x8, LEFT | BOTTOM), 350, 112),
    ]
    spacing.append((p.rect(1, 96, GREY), 220, 26))

    speed = panel(p, 228, 92, "Sebesség") + [
        (p.number(OUT_SPEED, 100, 40, 650, 0.01, 1, BLACK, F24x32, name="OUT_SPEED"), 4, 26),
        (p.text(60, 40, "km/h", LABEL, F12x16, LEFT | BOTTOM), 108, 24),
        (p.rect(76, 20, NAVY), 144, 4),
        (p.text(76, 20, "MSS", WHITE, F8x12, CENTER | MIDDLE, object_id=OUT_SPEED_SOURCE, name="OUT_SPEED_SOURCE"), 144, 4),
        (p.text(200, 16, "forrás: Machine Selected Speed", LABEL, F6x8), 8, 72),
    ]

    work = panel(p, 228, 92, "Munkakapcsoló") + [
        (p.ellipse(36, 36, rgb(0, 4, 0), BLACK, 2, OBJ_WORK_SWITCH_LED, "OBJ_WORK_SWITCH_LED"), 14, 32),
        (p.text(120, 40, "LENT", BLACK, F24x32, LEFT | MIDDLE, object_id=OUT_WORK_SWITCH_TEXT, name="OUT_WORK_SWITCH_TEXT"), 62, 30),
        (p.text(212, 16, "gép leengedve", LABEL, F6x8), 62, 72),
    ]

    motor = panel(p, 464, 76, "Motor") + [
        (p.text(90, 20, "OK", DARK_GREEN, F12x16, LEFT | MIDDLE, object_id=OUT_MOTOR_STATE, name="OUT_MOTOR_STATE"), 60, 2),
        (p.text(80, 20, "PWM", LABEL, F8x12), 8, 26),
        (p.bar(OUT_MOTOR_PWM_BAR, 110, 18, 0, rgb(0, 3, 5), ticks=5, maximum=10000, var=VAR_MOTOR_PWM,
               name="OUT_MOTOR_PWM_BAR"), 8, 46),
        (p.number(OUT_MOTOR_PWM, 56, 18, 0, 0.01, 2, BLACK, F8x12, var=VAR_MOTOR_PWM, name="OUT_MOTOR_PWM"), 120, 46),
        (p.text(16, 18, "%", LABEL, F8x12), 178, 46),
        (p.rect(1, 50, GREY), 198, 22),
        (p.text(60, 20, "áram", LABEL, F8x12), 208, 26),
        (p.number(OUT_MOTOR_CURRENT, 52, 24, 124, 0.1, 1, BLACK, F12x16, name="OUT_MOTOR_CURRENT"), 204, 42),
        (p.text(16, 24, "A", LABEL, F12x16, LEFT | BOTTOM), 258, 42),
        (p.rect(1, 50, GREY), 280, 22),
        (p.text(140, 20, "pozícióhiba", LABEL, F8x12), 290, 26),
        (p.bar(OUT_POSITION_ERROR_BAR, 90, 18, 54, rgb(5, 3, 0), target=50, name="OUT_POSITION_ERROR_BAR"), 290, 46),
        (p.number(OUT_POSITION_ERROR, 44, 18, 10008, 0.01, 2, BLACK, F8x12, offset=-10000, name="OUT_POSITION_ERROR"), 382, 46),
        (p.text(30, 18, "cs.", LABEL, F8x12), 430, 46),
    ]

    def counter(label, unit, number_id, name, value, scale, decimals, y):
        return [(p.text(110, 18, label, LABEL, F8x12), 8, y),
                (p.number(number_id, 120, 18, value, scale, decimals, BLACK, F12x16, name=name), 100, y),
                (p.text(40, 18, unit, LABEL, F8x12), 226, y)]

    counters = panel(p, 464, 80, "Számlálók") + [
        (p.text(100, 16, "napi", LABEL, F8x12, RIGHT | MIDDLE), 128, 4),
        (p.text(100, 16, "összes", LABEL, F8x12, RIGHT | MIDDLE), 324, 4),
        (p.text(80, 18, "Terület", BLACK, F8x12), 8, 26),
        (p.number(OUT_AREA_DAY, 130, 20, 342, 0.01, 2, BLACK, F12x16, name="OUT_AREA_DAY"), 98, 24),
        (p.text(30, 20, "ha", LABEL, F8x12, LEFT | BOTTOM), 232, 24),
        (p.number(OUT_AREA_TOTAL, 130, 20, 1286, 0.1, 1, BLACK, F12x16, name="OUT_AREA_TOTAL"), 294, 24),
        (p.text(30, 20, "ha", LABEL, F8x12, LEFT | BOTTOM), 428, 24),
        (p.text(80, 18, "Gumó", BLACK, F8x12), 8, 52),
        (p.number(OUT_SEEDS_DAY, 130, 20, 152340, 1, 0, BLACK, F12x16, name="OUT_SEEDS_DAY"), 98, 50),
        (p.text(30, 20, "db", LABEL, F8x12, LEFT | BOTTOM), 232, 50),
        (p.number(OUT_SEEDS_TOTAL, 130, 20, 5712800, 1, 0, BLACK, F12x16, name="OUT_SEEDS_TOTAL"), 294, 50),
        (p.text(30, 20, "db", LABEL, F8x12, LEFT | BOTTOM), 428, 50),
    ]

    p.data_mask(DM_MAIN, SKM_MAIN, header(p, "KRUMPLIÜLTETŐ") + [
        (status_box, 342, 7), (status, 342, 7),
        *offset(spacing, 8, 50),
        *offset(speed, 8, 188),
        *offset(work, 244, 188),
        *offset(motor, 8, 286),
        *offset(counters, 8, 368),
        (p.text(464, 24, "TESZT VERZIÓ", GREY, F6x8, RIGHT | BOTTOM), 8, 452),
    ], name="DM_MAIN")

    # --- Settings ------------------------------------------------------------------------------
    rows = [
        ("Sortáv", "cm", IN_ROW_SPACING, 75, 30, 200, 1, 0),
        ("Sorok száma", "sor", IN_ROW_COUNT, 4, 1, 24, 1, 0),
        ("Tőtáv lépés (+/-)", "cm", IN_SPACING_STEP, 10, 1, 100, 0.1, 1),
        ("Indulási előretolás", "cm", IN_START_ADVANCE, 0, 0, 500, 0.1, 1),
        ("Sebesség-holtsáv", "km/h", IN_SPEED_DEADBAND, 3, 0, 50, 0.1, 1),
    ]
    calibration = [
        ("Impulzus / csésze", "imp", IN_PULSES_PER_CUP, 128, 1, 65000, 1, 0),
        ("Csésze / fordulat", "db", IN_CUPS_PER_REV, 18, 1, 200, 1, 0),
        ("Áttétel", ": 1", IN_GEAR_RATIO, 2500, 100, 20000, 0.01, 2),
    ]
    settings = header(p, "BEÁLLÍTÁSOK")
    settings += [(p.text(448, 20, "Gép", DARK_GREEN, F12x16), 16, 52), (p.hline(448, DARK_GREEN, 2), 16, 74)]
    for index, row in enumerate(rows):
        settings += setting_row(p, *row, y=82 + index * 38)
    settings += [(p.text(448, 20, "Hajtás / jeladó", DARK_GREEN, F12x16), 16, 278), (p.hline(448, DARK_GREEN, 2), 16, 300)]
    for index, row in enumerate(calibration):
        settings += setting_row(p, *row, y=308 + index * 38)
    p.data_mask(DM_SETTINGS, SKM_SETTINGS, settings, bg=PANEL, name="DM_SETTINGS")

    # --- Service: controller and calibration --------------------------------------------------
    service = header(p, "SZERVIZ")
    service += [(p.text(448, 20, "Szabályzó", DARK_GREEN, F12x16), 16, 52), (p.hline(448, DARK_GREEN, 2), 16, 74)]
    controller = [
        ("Kp pozíció", "1/s", IN_KP_POS, 150, 0, 5000, 0.01, 2),
        ("PI Kp", "", IN_PI_KP, 80, 0, 5000, 0.01, 2),
        ("PI Ki", "1/s", IN_PI_KI, 250, 0, 5000, 0.01, 2),
        ("Max. lemaradás", "csésze", IN_MAX_LAG, 15, 1, 100, 0.1, 1),
        ("Áramkorlát", "A", IN_CURRENT_LIMIT, 250, 10, 1000, 0.1, 1),
        ("Lágyindítás", "ms", IN_SOFT_START, 500, 0, 5000, 1, 0),
    ]
    for index, row in enumerate(controller):
        service += setting_row(p, *row, y=82 + index * 38)
    service += [
        (p.text(448, 20, "Forgatásos kalibráció", DARK_GREEN, F12x16), 16, 316), (p.hline(448, DARK_GREEN, 2), 16, 338),
        *setting_row(p, "Forgatandó csésze", "db", IN_CAL_CUPS, 50, 1, 500, 1, 0, y=346),
        (p.text(240, 32, "Számolt impulzus", BLACK, F12x16), 16, 384),
        (p.number(OUT_CAL_PULSES, 120, 32, 6400, 1, 0, BLACK, F16x24, name="OUT_CAL_PULSES"), 256, 384),
        (p.text(80, 32, "imp", LABEL, F12x16), 384, 384),
        (p.text(448, 36, "Álló gépnél, felemelt munkakapcsolóval. Indítás: KALIBR. gomb.", LABEL, F6x8, LEFT | TOP, wrap=True), 16, 426),
    ]
    p.data_mask(DM_SERVICE, SKM_SERVICE, service, bg=PANEL, name="DM_SERVICE")

    # --- Alarms ------------------------------------------------------------------------------
    triangle = p.polygon(120, 104, [(60, 0), (120, 104), (0, 104)], YELLOW, BLACK, 3)
    bang = p.text(120, 80, "!", BLACK, F48x64, CENTER | BOTTOM)

    def alarm(object_id, name, title, lines, priority=0):
        p.alarm_mask(object_id, SKM_ALARM, [
            (triangle, 180, 40), (bang, 180, 60),
            (p.text(448, 48, title, WHITE, F24x32, CENTER | MIDDLE), 16, 170),
            (p.rect(448, 160, PANEL, BLACK, 2), 16, 236),
            (p.text(424, 144, lines, BLACK, F12x16, LEFT | TOP, wrap=True), 28, 248),
            (p.text(448, 24, "A motor áll. Nyugtázás: OK", WHITE, F8x12, CENTER | MIDDLE), 16, 420),
        ], priority=priority, name=name)

    alarm(AM_JAM, "AM_JAM", "ELAKADÁS",
          "Nagy PWM mellett nem jön impulzus a jeladóról.\r\n\r\nEllenőrizd a csészesort és a hajtást!")
    alarm(AM_LAG, "AM_LAG", "NAGY LEMARADÁS",
          "A pozícióhiba tartósan elérte a max. lemaradást.\r\n\r\nA többlet eldobva. Csökkentsd a sebességet!", priority=1)
    alarm(AM_NO_SPEED, "AM_NO_SPEED", "NINCS SEBESSÉGJEL",
          "Sem MSS, sem Ground, sem Wheel sebesség nem érkezik a buszon.\r\n\r\nEllenőrizd a traktor ISOBUS csatlakozását!")
    alarm(AM_MOTOR, "AM_MOTOR", "MOTOR HIBA",
          "Túláram vagy motormeghajtó hiba.\r\n\r\nEllenőrizd a motort és a vezetékeket!")

    # --- Working set: designator shown in the VT's working set list -------------------------
    p.working_set(DM_MAIN, [*offset(potato_icon(p, 44, 32), 8, 6),
                            (p.text(60, 16, "KRUMPLI", DARK_GREEN, F8x12, CENTER | MIDDLE), 0, 42)])
    return p


def write_header(p, path):
    def section(title, names):
        lines = [f"\t// {title}"]
        for n in names:
            lines.append(f"\tconstexpr std::uint16_t {n} = {p.names[n]};")
        return lines

    var_names = [n for n in p.names if n.startswith(("IN_", "OUT_", "OBJ_", "VAR_"))]
    var_names.sort(key=lambda n: p.names[n])
    out = [
        "// Generated by tools/make_pool.py, do not edit.",
        "#pragma once",
        "",
        "#include <cstdint>",
        "",
        "namespace krumpli_pool",
        "{",
        *section("Masks", ["DM_MAIN", "DM_SETTINGS", "DM_SERVICE", "AM_JAM", "AM_LAG", "AM_NO_SPEED", "AM_MOTOR"]),
        *section("Soft key masks", ["SKM_MAIN", "SKM_SETTINGS", "SKM_SERVICE", "SKM_ALARM"]),
        *section("Soft keys (object ids)", list(KEYS)),
        "\t// Soft key codes (Soft Key Activation message)",
        *[f"\tconstexpr std::uint8_t {n}_CODE = {code};" for n, (_, code) in KEYS.items()],
        *section("Fill attributes for Change Attribute on the status box and the work switch LED", [FILL_GREEN, FILL_RED, FILL_GREY]),
        *section("Runtime values", var_names),
        "} // namespace krumpli_pool",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8", newline="\n")


def main():
    p = build()
    data = p.build()
    iop = ROOT / "pool" / "krumpliulteto.iop"
    iop.parent.mkdir(parents=True, exist_ok=True)
    iop.write_bytes(data)
    write_header(p, ROOT / "include" / "krumpli_pool_ids.hpp")
    print(f"Wrote {iop} ({len(data)} bytes, {len(p.objects)} objects)")


if __name__ == "__main__":
    main()
