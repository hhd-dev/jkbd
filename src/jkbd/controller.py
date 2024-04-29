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
        "rt": [B("BTN_TR2")],
        "lt": [B("BTN_TL2")],
    }
)
AXIS_LIMIT = 0.3

DEVICE_CAPABILITIES = {
    B("EV_KEY"): [
        B("KEY_ESC"),
        B("KEY_TAB"),
        B("KEY_SPACE"),
        B("KEY_LEFTSHIFT"),
        B("KEY_UP"),
        B("KEY_LEFT"),
        B("KEY_RIGHT"),
        B("BTN_LEFT"),
        B("BTN_RIGHT"),
        B("KEY_DOWN"),
        B("KEY_ENTER"),
    ],
    B("EV_REL"): [
        B("REL_X"),
        B("REL_Y"),
    ],
}
KEYBOARD_MAP = {
    "up": ["KEY_UP"],
    "down": ["KEY_DOWN"],
    "left": ["KEY_LEFT"],
    "right": ["KEY_RIGHT"],
    "lt": ["BTN_RIGHT"],
    "rt": ["BTN_LEFT"],
    "a": ["KEY_ENTER"],
    "x": ["KEY_SPACE"],
    "b": ["KEY_ESC"],
    "lb": ["KEY_LEFTSHIFT", "KEY_TAB"],
    "rb": ["KEY_TAB"],
}
MOUSE_MAP = {
    "mouse_x": B("REL_X"),
    "mouse_y": B("REL_Y"),
}

REPEAT_INITIAL = 0.5
REPEAT_INTERVAL = 0.2
KEY_DELAY = 0.08
CONTROLLER_REFRESH_INTERVAL = 2
REFRESH_INTERVAL = 0.01  # 100hz
MOUSE_DEADZONE = 0.2
MOUSE_MULTIPLIER = 1000
MOUSE_THRES = 4
MIN_REFRESH_DELAY = 0.001

class KeyboardHandler:
    def __init__(self) -> None:
        self.dev = UInput(events=DEVICE_CAPABILITIES)
        self.state = {}
        self.last = {}
        self.accum = {}
        self.mouse = {}

    def update(self, cid, dev, evs: Sequence[InputEvent]):
        if not cid in self.accum:
            self.state[cid] = {}
        if not cid in self.accum:
            self.accum[cid] = {}
        if not cid in self.mouse:
            self.mouse[cid] = {}

        ranges = {
            a: (
                (i.min + i.max) / 2 - (i.max - i.min) * AXIS_LIMIT,
                (i.min + i.max) / 2 + (i.max - i.min) * AXIS_LIMIT,
            )
            for a, i in dev.capabilities().get(B("EV_ABS"), [])  # type: ignore
        }
        limits = {
            a: (i.min, i.max)
            for a, i in dev.capabilities().get(B("EV_ABS"), [])  # type: ignore
        }
        dinput = any(
            d[0] == B("ABS_GAS") for d in dev.capabilities().get(B("EV_ABS"), [])
        )

        def norm(k, v):
            return 2 * (v - limits[k][0]) / (limits[k][1] - limits[k][0]) - 1

        if dinput:
            mouse_vals = {
                B("ABS_Z"): "mouse_x",
                B("ABS_RZ"): "mouse_y",
            }
            trig_vals = {
                B("ABS_BRAKE"): "rt",
                B("ABS_GAS"): "lt",
            }
        else:
            mouse_vals = {
                B("ABS_RX"): "mouse_x",
                B("ABS_RY"): "mouse_y",
            }
            trig_vals = {
                B("ABS_Z"): "lt",
                B("ABS_RZ"): "rt",
            }

        # Debounce changed events
        curr = time.perf_counter()
        changed = []
        for ev in evs:
            if ev.type == B("EV_ABS"):
                code_raw = ev.code
                if code_raw in trig_vals:
                    code = trig_vals[code_raw]
                    val = ev.value > ranges[ev.code][1]
                    if (
                        code not in self.state[cid]
                        or bool(self.state[cid][code]) != val
                    ):
                        changed.append((code, val))
                        self.state[cid][code] = curr + REPEAT_INITIAL if val else None
                    continue
                if code_raw in mouse_vals:
                    code = mouse_vals[code_raw]
                    val = norm(code_raw, ev.value)
                    self.mouse[cid][code] = val
                    continue

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

        # Process Mouse
        if not cid in self.last:
            self.last[cid] = curr
        last = self.last[cid]
        wrote = False
        for code, raw_code in MOUSE_MAP.items():
            if code not in self.mouse[cid]:
                continue
            val = self.mouse[cid][code]
            if code not in self.accum[cid]:
                self.accum[cid][code] = 0
            if abs(val) < MOUSE_DEADZONE:
                self.accum[cid][code] = 0
                continue
            self.accum[cid][code] += MOUSE_MULTIPLIER * val * (curr - last)
            if abs(self.accum[cid][code]) > MOUSE_THRES:
                self.dev.write(
                    B("EV_REL"),
                    raw_code,
                    int(self.accum[cid][code]),
                )
                self.accum[cid][code] %= 1
                wrote = True
        if wrote:
            self.dev.syn()

        # Update perf counter
        self.last[cid] = curr

    def close(self):
        self.dev.close()


def find_controllers(
    existing: Sequence[str],
) -> tuple[list[evdev.InputDevice], list[str]]:
    out = []
    devs = evdev.list_devices()
    for fn in devs:
        if fn in existing:
            continue
        d = evdev.InputDevice(fn)

        if d.info.vendor == 0x28DE:
            # Skip steam deck
            continue

        c = cast(dict[int, Sequence[int]], d.capabilities())
        if B("EV_KEY") in c and B("BTN_A") in c[B("EV_KEY")]:
            out.append(d)

    return list(out), list(devs)


def can_read(fd: int):
    return select.select([fd], [], [], 0)[0]


def controller_loop():
    kbd = KeyboardHandler()
    try:
        cnts, checked = find_controllers([])
        logger.info(f"Starting loop with controllers: {[d.path for d in cnts]}")
        last_update = time.perf_counter()

        while True:
            select.select([c.fd for c in cnts], [], [], REFRESH_INTERVAL)
            for c in cnts:
                evs = []
                if can_read(c.fd):
                    evs.extend(c.read())

                kbd.update(c.path, c, evs)

            curr = time.perf_counter()
            if curr > last_update + CONTROLLER_REFRESH_INTERVAL:
                new_devs, checked = find_controllers(checked)
                if new_devs:
                    logger.info(f"Found new controllers: {[d.path for d in new_devs]}")
                    cnts.extend(new_devs)
                last_update = curr

            # Prevent burning out       
            time.sleep(MIN_REFRESH_DELAY)
    finally:
        kbd.close()
