---
name: kernel-computer-controls
description: OS-level mouse, keyboard, screen control, and screenshots for Kernel browsers.
---

# Computer Controls

Computer controls operate at the browser VM OS level. Use them when Playwright or
CDP cannot reach the target, such as browser chrome, difficult canvas/WebGL
surfaces, drag gestures, or visual-only interactions.

Prefer `kernel browsers playwright execute` for ordinary page automation because
it is usually faster and more reliable.

## Screenshots

```bash
kernel browsers computer screenshot <session_id> --to /tmp/screenshot.png
kernel browsers computer screenshot <session_id> --to /tmp/region.png --x 0 --y 0 --width 800 --height 600
```

## Mouse

```bash
kernel browsers computer move-mouse <session_id> --x 500 --y 300
kernel browsers computer click-mouse <session_id> --x 100 --y 200
kernel browsers computer click-mouse <session_id> --x 100 --y 200 --button right --num-clicks 2
kernel browsers computer scroll <session_id> --x 300 --y 400 --delta-y 120
kernel browsers computer drag-mouse <session_id> --point 100,200 --point 200,300 --button left
```

## Keyboard

```bash
kernel browsers computer type <session_id> --text "Hello, World!"
kernel browsers computer type <session_id> --text "Slow typing" --delay 100
kernel browsers computer press-key <session_id> --key Return
kernel browsers computer press-key <session_id> --key Control_L+t
kernel browsers computer press-key <session_id> --key Control_L+Shift_L+Tab --hold-key Alt_L
```

Common key names include `Return`, `Tab`, `Escape`, `BackSpace`, `Delete`,
`Home`, `End`, `Page_Up`, `Page_Down`, `Up`, `Down`, `Left`, `Right`,
`Shift_L`, `Control_L`, and `Alt_L`.

## Navigate And Capture

```bash
SESSION=$(kernel browsers create -o json | jq -r '.session_id')

kernel browsers playwright execute "$SESSION" 'await page.goto("https://kernel.sh")'
kernel browsers computer screenshot "$SESSION" --to /tmp/kernel-homepage.png
kernel browsers delete "$SESSION" -y
```
