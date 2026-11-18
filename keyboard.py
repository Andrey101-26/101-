"""Optional keyboard and speech controls for browsers running PyScript."""

from js import document, window
from pyodide.ffi import create_proxy

PANEL = document.getElementById("keyboard-mode")
TOGGLE = document.getElementById("keyboard-toggle")
STATUS = document.getElementById("keyboard-status")
SPEAKER = getattr(window, "speechSynthesis", None)
UTTERANCE = getattr(window, "SpeechSynthesisUtterance", None)
STORAGE_KEY = "golos-keyboard-mode"
CONTROLS = "a[href], button, input, select, textarea, summary, audio[controls]"
NATIVE_ARROWS = "input, select, textarea, audio, video, [contenteditable]"

try:
    enabled = window.sessionStorage.getItem(STORAGE_KEY) == "on"
except Exception:
    enabled = False


def speech_error(event):
    if enabled and event.error not in ("canceled", "interrupted"):
        STATUS.textContent = "Браузер не смог озвучить пункт. Навигация стрелками доступна."


def stop_speech(*_):
    if SPEAKER and UTTERANCE:
        SPEAKER.cancel()


def speak(text):
    if not SPEAKER or not UTTERANCE:
        return
    stop_speech()
    clips = document.querySelectorAll("audio")
    if not text or any(not clips.item(i).paused for i in range(clips.length)):
        return
    message = UTTERANCE.new(text)
    message.lang = "ru-RU"
    message.addEventListener("error", report_speech_error)
    SPEAKER.speak(message)


def update_mode():
    TOGGLE.setAttribute("aria-pressed", "true" if enabled else "false")
    document.documentElement.classList.toggle("arrow-mode", enabled)


def set_mode(value):
    global enabled
    enabled = value
    update_mode()
    try:
        window.sessionStorage.setItem(STORAGE_KEY, "on" if enabled else "off")
    except Exception:
        pass
    if enabled:
        STATUS.textContent = (
            "Режим включён." if SPEAKER and UTTERANCE
            else "Стрелки включены. Озвучивание в этом браузере недоступно."
        )
        speak("Режим включён.")
    else:
        stop_speech()
        STATUS.textContent = "Режим выключен."


def toggle_mode(event):
    set_mode(not enabled)


def quiet_mode(event):
    if enabled:
        set_mode(False)


def speak_focus(event):
    target = event.target
    if not enabled or not target.matches(CONTROLS + ", h2[tabindex]"):
        return
    label = target.getAttribute("aria-label")
    labels = getattr(target, "labels", None)
    if not label and labels and labels.length:
        label = labels.item(0).textContent
    speak((label or target.textContent).strip())


def move_focus(event):
    if not enabled or event.defaultPrevented or any(
        (event.altKey, event.ctrlKey, event.metaKey, event.shiftKey)
    ):
        return
    if event.key == "Escape":
        stop_speech()
        return
    if event.key not in ("ArrowDown", "ArrowUp") or event.target.closest(NATIVE_ARROWS):
        return

    forward = event.key == "ArrowDown"
    active = document.activeElement
    controls = document.querySelectorAll(CONTROLS)
    indices = range(controls.length) if forward else range(controls.length - 1, -1, -1)
    position = window.Node.DOCUMENT_POSITION_FOLLOWING if forward else window.Node.DOCUMENT_POSITION_PRECEDING
    event.preventDefault()
    for index in indices:
        control = controls.item(index)
        if control.matches(".skip, :disabled") or not control.getClientRects().length:
            continue
        if active.isSameNode(document.body) or active.compareDocumentPosition(control) & position:
            control.focus()
            break


def stop_if_enabled(event):
    if enabled:
        stop_speech()


report_speech_error = create_proxy(speech_error)
TOGGLE.addEventListener("click", create_proxy(toggle_mode))
quiet_link = document.querySelector("[data-quiet]")
if quiet_link:
    quiet_link.addEventListener("click", create_proxy(quiet_mode))
document.addEventListener("focusin", create_proxy(speak_focus))
document.addEventListener("keydown", create_proxy(move_focus))
document.addEventListener("play", create_proxy(stop_if_enabled), True)
window.addEventListener("pagehide", create_proxy(stop_if_enabled))
update_mode()
PANEL.hidden = False
