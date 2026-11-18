"""Optional keyboard and speech controls for browsers running PyScript."""

import re
from collections import Counter

from js import document, window
from pyodide.ffi import create_proxy

PANEL = document.getElementById("keyboard-mode")
TOGGLE = document.getElementById("keyboard-toggle")
STATUS = document.getElementById("keyboard-status")
VOICE_CHOICES = document.getElementById("voice-choices")
SETTINGS = document.getElementById("site-settings")
SETTINGS_SUMMARY = SETTINGS.querySelector("summary")
PROMPT = document.querySelector("[data-dialogue-prompt]")
SPEAKER = getattr(window, "speechSynthesis", None)
UTTERANCE = getattr(window, "SpeechSynthesisUtterance", None)
STORAGE_KEY = "golos-keyboard-mode"
VOICE_KEY = "golos-voice"
THEME_KEY = "golos-theme"
CONTROLS = "a[href], button, input, select, textarea, summary, audio[controls]"
NATIVE_ARROWS = "input, select, textarea, audio, video, [contenteditable]"

STOP_WORDS = set(
    "или это все как что при для без ещё где когда чем если этот эта эти того его она они который которая которые после перед через такие между также такой такое чтобы тот есть там уже можно было быть будут".split()
)
MAX_FILE_BYTES = 256 * 1024


def decode_text(data):
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        text = data.decode("utf-16")
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("cp1251")
    if any(not (char.isprintable() or char in "\r\n\t") for char in text):
        raise ValueError("Похоже, это не текстовый файл.")
    return text


def extract_summary(text):
    parts = [
        " ".join(part.split())
        for part in re.split(r"(?<=[.!?…])\s+|[\r\n]+", text.strip())
        if re.search(r"\w", part)
    ]
    if not parts:
        return ""
    words = [
        [word for word in re.findall(r"[^\W\d_]{3,}", part.lower()) if word not in STOP_WORDS]
        for part in parts
    ]
    counts = Counter(word for sentence in words for word in set(sentence))

    def rank(index):
        unique = set(words[index])
        recurring = sum(min(counts[word] - 1, 4) for word in unique) / max(5, len(unique))
        cue = any(word in unique for word in ("главное", "важно", "нужно", "итог", "итоги", "цель", "результат"))
        return recurring + cue + 0.2 / (index + 1)

    limit = min(3, max(1, (len(parts) + 1) // 3))
    selection = sorted(sorted(range(len(parts)), key=rank, reverse=True)[:limit])
    summary = []
    for index in selection:
        part = parts[index]
        tokens = part.split()
        if len(tokens) > 28 or len(part) > 240:
            chunk = " ".join(tokens[:28])[:240]
            if len(chunk) == 240 and " " in chunk:
                chunk = chunk.rsplit(" ", 1)[0]
            part = chunk.rstrip(",;:.!?") + "…"
        summary.append(part if part[-1] in ".!?…" else part + ".")
    return " ".join(summary)


def stored(key, *, persistent=False):
    try:
        storage = window.localStorage if persistent else window.sessionStorage
        return storage.getItem(key)
    except Exception:
        return None


def save(key, value, *, persistent=False):
    try:
        storage = window.localStorage if persistent else window.sessionStorage
        storage.setItem(key, value)
    except Exception:
        pass


enabled = stored(STORAGE_KEY) == "on"
question_pending = bool(PROMPT)
voices = {}
selected_voice = stored(VOICE_KEY, persistent=True) or ""
voice_catalog = None
file_reader = None


def refresh_voices(event=None):
    global voice_catalog
    if not SPEAKER or not UTTERANCE:
        VOICE_CHOICES.textContent = "Озвучивание недоступно в этом браузере."
        return
    available = SPEAKER.getVoices()
    all_voices = [available[index] for index in range(available.length)]
    russian = [voice for voice in all_voices if voice.lang.lower().startswith("ru")]
    signature = tuple((voice.voiceURI, voice.name) for voice in russian)
    voices.clear()
    voices.update((voice.voiceURI, voice) for voice in russian)
    if signature == voice_catalog:
        return
    voice_catalog = signature
    active = document.activeElement
    focused_voice = active.getAttribute("data-voice-choice") if VOICE_CHOICES.contains(active) else None
    VOICE_CHOICES.replaceChildren()
    for key, name in (("", "Системный"), *signature):
        button = document.createElement("button")
        button.type = "button"
        button.setAttribute("data-voice-choice", key)
        button.textContent = friendly_voice_name(name)
        VOICE_CHOICES.append(button)
        if key == focused_voice:
            button.focus()
    if focused_voice is not None and focused_voice and focused_voice not in voices:
        VOICE_CHOICES.firstElementChild.focus()
    mark_choice("data-voice-choice", selected_voice if selected_voice in voices else "")


def friendly_voice_name(name):
    short = name.split(" - ", 1)[0].removeprefix("Microsoft ")
    return {"Pavel": "Павел", "Irina": "Ирина", "Daria": "Дарья"}.get(short, short)


def mark_choice(attribute, selected):
    buttons = document.querySelectorAll(f"button[{attribute}]")
    for index in range(buttons.length):
        button = buttons.item(index)
        pressed = button.getAttribute(attribute) == selected
        button.setAttribute("aria-pressed", "true" if pressed else "false")


def choose_voice(event):
    global selected_voice
    button = event.target.closest("[data-voice-choice]")
    if not button:
        return
    selected_voice = button.getAttribute("data-voice-choice")
    mark_choice("data-voice-choice", selected_voice)
    save(VOICE_KEY, selected_voice, persistent=True)
    if enabled:
        speak("Удобно так?")


def apply_theme(value):
    mark_choice("data-theme-choice", value)
    if value in ("light", "dark"):
        document.documentElement.setAttribute("data-theme", value)
    else:
        document.documentElement.removeAttribute("data-theme")


def choose_theme(event):
    value = event.currentTarget.getAttribute("data-theme-choice")
    apply_theme(value)
    save(THEME_KEY, value, persistent=True)


def close_settings(event=None):
    SETTINGS.open = False
    SETTINGS_SUMMARY.focus()


def speech_error(event):
    if event.error not in ("canceled", "interrupted"):
        STATUS.textContent = "Озвучить не удалось. Текст доступен."


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
    selected = voices.get(selected_voice)
    message.lang = selected.lang if selected else "ru-RU"
    if selected:
        message.voice = selected
    message.addEventListener("error", report_speech_error)
    SPEAKER.speak(message)


def update_mode():
    TOGGLE.setAttribute("aria-pressed", "true" if enabled else "false")
    document.documentElement.classList.toggle("arrow-mode", enabled)


def set_mode(value):
    global enabled, question_pending
    enabled = value
    update_mode()
    save(STORAGE_KEY, "on" if enabled else "off")
    if enabled:
        STATUS.textContent = (
            "Режим включён." if SPEAKER and UTTERANCE
            else "Стрелки включены. Озвучивание в этом браузере недоступно."
        )
        speak(PROMPT.getAttribute("data-dialogue-prompt") if PROMPT else "Слушаю.")
        question_pending = False
    else:
        stop_speech()
        STATUS.textContent = "Режим выключен."


def toggle_mode(event):
    set_mode(not enabled)


def quiet_mode(event):
    if enabled:
        set_mode(False)


def speak_focus(event):
    global question_pending
    target = event.target
    if not enabled or not target.matches(CONTROLS + ", h2[tabindex]"):
        return
    label = target.getAttribute("aria-label")
    labelled_by = target.getAttribute("aria-labelledby")
    if not label and labelled_by:
        label = " ".join(document.getElementById(key).textContent for key in labelled_by.split())
    labels = getattr(target, "labels", None)
    if not label and labels and labels.length:
        label = labels.item(0).textContent
    text = (label or target.textContent).strip()
    if question_pending and target.closest("main"):
        question_pending = False
        text = PROMPT.getAttribute("data-dialogue-prompt") + " " + text
    speak(text)


def move_focus(event):
    if event.defaultPrevented or any(
        (event.altKey, event.ctrlKey, event.metaKey, event.shiftKey)
    ):
        return
    active = document.activeElement
    in_settings = SETTINGS.open and SETTINGS.contains(active)
    if event.key == "Escape":
        if in_settings:
            event.preventDefault()
            close_settings()
        stop_speech()
        return
    if not (enabled or in_settings) or event.key not in ("ArrowDown", "ArrowUp") or event.target.closest(NATIVE_ARROWS):
        return

    forward = event.key == "ArrowDown"
    controls = document.querySelectorAll(CONTROLS)
    indices = range(controls.length) if forward else range(controls.length - 1, -1, -1)
    position = window.Node.DOCUMENT_POSITION_FOLLOWING if forward else window.Node.DOCUMENT_POSITION_PRECEDING
    event.preventDefault()
    for index in indices:
        control = controls.item(index)
        if control.matches(".skip, :disabled") or not control.getClientRects().length:
            continue
        if active.isSameNode(document.body) or active.compareDocumentPosition(control) & position:
            if in_settings and not SETTINGS.contains(control):
                SETTINGS.open = False
            control.focus()
            break


def read_excerpt(event):
    target = document.getElementById(event.currentTarget.getAttribute("data-read"))
    speak(target.textContent.strip())


def file_result(event):
    try:
        data = window.Uint8Array.new(file_reader.result).to_bytes()
        summary = extract_summary(decode_text(data))
        if not summary:
            raise ValueError("В файле нет текста.")
    except UnicodeError:
        file_status.textContent = "Не удалось распознать кодировку. Сохраните файл как TXT в UTF-8."
        return
    except ValueError as error:
        file_status.textContent = str(error)
        return
    file_status.textContent = ""
    document.getElementById("file-summary").textContent = summary
    document.getElementById("file-result").hidden = False
    document.getElementById("summary-heading").focus()


def file_error(event):
    file_status.textContent = "Не удалось прочитать файл. Попробуйте снова."


def clear_file_result(event=None):
    if file_reader.readyState == 1:
        file_reader.abort()
    document.getElementById("file-result").hidden = True
    document.getElementById("file-summary").textContent = ""
    file_status.textContent = ""
    stop_speech()


def read_file(event):
    event.preventDefault()
    clear_file_result()
    selected = document.getElementById("text-file").files.item(0)
    if not selected or not selected.name.lower().endswith(".txt"):
        file_status.textContent = "Выберите файл TXT."
    elif selected.size > MAX_FILE_BYTES:
        file_status.textContent = "Выберите файл до 256 КБ."
    else:
        file_reader.readAsArrayBuffer(selected)


report_speech_error = create_proxy(speech_error)
TOGGLE.addEventListener("click", create_proxy(toggle_mode))
VOICE_CHOICES.addEventListener("click", create_proxy(choose_voice))
document.getElementById("settings-close").addEventListener("click", create_proxy(close_settings))
theme_buttons = document.querySelectorAll("[data-theme-choice]")
on_theme_choice = create_proxy(choose_theme)
for index in range(theme_buttons.length):
    theme_buttons.item(index).addEventListener("click", on_theme_choice)
quiet_link = document.querySelector("[data-quiet]")
if quiet_link:
    quiet_link.addEventListener("click", create_proxy(quiet_mode))
document.addEventListener("focusin", create_proxy(speak_focus))
document.addEventListener("keydown", create_proxy(move_focus))
document.addEventListener("play", create_proxy(stop_speech), True)
window.addEventListener("pagehide", create_proxy(stop_speech))
if SPEAKER and UTTERANCE:
    SPEAKER.addEventListener("voiceschanged", create_proxy(refresh_voices))
    buttons = document.querySelectorAll("[data-read]")
    on_read_excerpt = create_proxy(read_excerpt)
    for index in range(buttons.length):
        button = buttons.item(index)
        button.addEventListener("click", on_read_excerpt)
        button.hidden = False
refresh_voices()
preferred_theme = stored(THEME_KEY, persistent=True)
apply_theme(preferred_theme if preferred_theme in ("light", "dark") else "system")

file_form = document.getElementById("file-form")
if file_form:
    file_status = document.getElementById("file-status")
    file_reader = window.FileReader.new()
    file_reader.addEventListener("load", create_proxy(file_result))
    file_reader.addEventListener("error", create_proxy(file_error))
    file_form.addEventListener("submit", create_proxy(read_file))
    document.getElementById("text-file").addEventListener("change", create_proxy(clear_file_result))
    document.getElementById("file-fallback").hidden = True
    file_form.hidden = False
update_mode()
PANEL.hidden = False
