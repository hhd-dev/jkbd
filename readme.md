# JKBD: Joystick to Keyboard
Simple script which runs as a service and converts gamepads into using a lizard
mode that is suitable for graphical and CLI linux installers.

Handles holding to auto-repeating buttons, multiple controllers, controller
disconnections, reconnections, and is compatible all Linux controllers (some 
controllers might not support mouse mode).

This script will ignore Valve controllers.

## CLI Keys
| Key          | Action     |
| ------------ | ---------- |
| Left Stick   | Arrow Keys |
| DPAD         | Arrow Keys |
| A            | Enter      |
| B            | Escape     |
| X            | Space      |
| Left Bumper  | Shift-Tab  |
| Right Bumper | Tab        |

## Mouse Keys
| Key           | Action      |
| ------------- | ----------- |
| Right Stick   | Mouse       |
| Left Trigger  | Right Click |
| Right Trigger | Left Click  |