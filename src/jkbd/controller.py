import logging
import select
import time
from typing import Any, Sequence, TypeVar, cast

import evdev
from evdev import InputEvent, UInput

logger = logging.getLogger(__name__)


def B(b: str):
    return cast(int, getattr(evdev.ecodes, b))


try:

    def _find_device(self, fd):
        return None

    evdev.UInput._find_device = _find_device
except Exception:
    pass

A = TypeVar("A")


def to_map(b: dict[A, Sequence[int]]) -> dict[int, A]:
    out = {}
    for btn, seq in b.items():
        for s in seq:
            out[s] = btn
    return out


BUTTON_MAP: dict[int, str] = to_map(
    {
        "a": [B("BTN_A")],
        "b": [B("BTN_B")],
        "x": [B("BTN_X")],
        "y": [B("BTN_Y")],
        "lb": [B("BTN_TL")],
        "rb": [B("BTN_TR")],
    }
)
AXIS_LIMIT = 0.25

KEYBOARD_CAPABILITIES = {
    B("EV_KEY"): [
        B("KEY_ESC"),
        B("KEY_TAB"),
        B("KEY_SPACE"),
        B("KEY_LEFTSHIFT"),
        B("KEY_UP"),
        B("KEY_LEFT"),
        B("KEY_RIGHT"),
        B("KEY_DOWN"),
        B("KEY_ENTER"),
    ],
}
KEYBOARD_MAP = {
    "up": ["KEY_UP"],
    "down": ["KEY_DOWN"],
    "left": ["KEY_LEFT"],
    "right": ["KEY_RIGHT"],
    "a": ["KEY_ENTER"],
    "x": ["KEY_SPACE"],
    "b": ["KEY_ESC"],
    "lb": ["KEY_LEFTSHIFT", "KEY_TAB"],
    "rb": ["KEY_TAB"],
}

REPEAT_INITIAL = 0.5
REPEAT_INTERVAL = 0.2
KEY_DELAY = 0.08
CONTROLLER_REFRESH_INTERVAL = 2
REFRESH_INTERVAL = 0.05


class KeyboardHandler:
    def __init__(self) -> None:
        self.dev = UInput(events=KEYBOARD_CAPABILITIES)
        self.state = {}

    def update(self, cid, dev, evs: Sequence[InputEvent]):
        if not cid in self.state:
            self.state[cid] = {}

        ranges = {
            a: (
                (i.min + i.max) / 2 - (i.max - i.min) * AXIS_LIMIT,
                (i.min + i.max) / 2 + (i.max - i.min) * AXIS_LIMIT,
            )
            for a, i in dev.capabilities().get(B("EV_ABS"), [])  # type: ignore
        }

        # Debounce changed events
        curr = time.perf_counter()
        changed = []
        for ev in evs:
            if ev.type == B("EV_ABS"):
                code = ev.code
                act1 = act2 = val1 = val2 = None
                if code == B("ABS_X") or code == B("ABS_HAT0X"):
                    act1 = "right"
                    act2 = "left"
                    if ev.value > ranges[ev.code][1]:
                        val1 = True
                        val2 = False
                    elif ev.value < ranges[ev.code][0]:
                        val1 = False
                        val2 = True
                    else:
                        val1 = False
                        val2 = False
                elif code == B("ABS_Y") or code == B("ABS_HAT0Y"):
                    act1 = "down"
                    act2 = "up"
                    if ev.value > ranges[ev.code][1]:
                        val1 = True
                        val2 = False
                    elif ev.value < ranges[ev.code][0]:
                        val1 = False
                        val2 = True
                    else:
                        val1 = False
                        val2 = False

                if act1 and act2:
                    for code, val in ((act1, val1), (act2, val2)):
                        if (
                            code not in self.state[cid]
                            or bool(self.state[cid][code]) != val
                        ):
                            changed.append((code, val))
                            self.state[cid][code] = (
                                curr + REPEAT_INITIAL if val else None
                            )
            if ev.type == B("EV_KEY"):
                code_raw = ev.code
                if code_raw not in BUTTON_MAP:
                    continue
                code = BUTTON_MAP[code_raw]
                val = ev.value
                if code not in self.state[cid] or bool(self.state[cid][code]) != val:
                    changed.append((code, val))
                    self.state[cid][code] = curr + REPEAT_INITIAL if val else None

        # Ignore guide combos
        if self.state[cid].get("mode", None):
            return

        # Allow holds
        for btn, val in list(self.state[cid].items()):
            if not val:
                continue
            if val < curr:
                changed.append((btn, True))
                self.state[cid][btn] = curr + REPEAT_INTERVAL

        # Process changed events
        for code, val in changed:
            if not val:
                continue

            if code not in KEYBOARD_MAP:
                logger.warning(f"No mapping found for code '{code}'. Skipping.")
                continue

            logger.info(f"Key '{code}' pressed. Emitting {KEYBOARD_MAP[code]}.")
            for kid in KEYBOARD_MAP[code]:
                self.dev.write(B("EV_KEY"), B(kid), 1)
            self.dev.syn()

            time.sleep(KEY_DELAY)
            for kid in reversed(KEYBOARD_MAP[code]):
                self.dev.write(B("EV_KEY"), B(kid), 0)
            self.dev.syn()

    def close(self):
        self.dev.close()


def find_controllers(existing: Sequence[str]) -> Sequence[evdev.InputDevice]:
    out = []
    for fn in evdev.list_devices():
        if fn in existing:
            continue
        d = evdev.InputDevice(fn)
        c = cast(dict[int, Sequence[int]], d.capabilities())
        if B("EV_KEY") in c and B("BTN_A") in c[B("EV_KEY")]:
            out.append(d)

    return out


def can_read(fd: int):
    return select.select([fd], [], [], 0)[0]


def controller_loop():
    kbd = KeyboardHandler()
    try:
        cnts = list(find_controllers([]))
        logger.info(f"Starting loop with controllers: {[d.path for d in cnts]}")
        last_update = time.perf_counter()

        while True:
            select.select([c.fd for c in cnts], [], [], REFRESH_INTERVAL)
            for c in cnts:
                if can_read(c.fd):
                    evs = list(c.read())
                else:
                    evs = []
                kbd.update(c.path, c, evs)

            curr = time.perf_counter()
            if curr > last_update + CONTROLLER_REFRESH_INTERVAL:
                new_devs = find_controllers([c.path for c in cnts])
                if new_devs:
                    logger.info(f"Found new controllers: {[d.path for d in new_devs]}")
                    cnts.extend(new_devs)
                last_update = curr
    finally:
        kbd.close()
