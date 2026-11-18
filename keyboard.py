"""Optional keyboard and speech controls for browsers running PyScript."""

import re
from collections import Counter

from js import document, window
from pyodide.ffi import create_proxy

PANEL = document.getElementById("keyboard-mode")
TOGGLE = document.getElementById("keyboard-toggle")
STATUS = document.getElementById("keyboard-status")
VOICE = document.getElementById("voice-choice")
THEME = document.getElementById("theme-choice")
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
file_reader = None


def refresh_voices(event=None):
    if not SPEAKER or not UTTERANCE:
        VOICE.disabled = True
        return
    available = SPEAKER.getVoices()
    all_voices = [available[index] for index in range(available.length)]
    russian = [voice for voice in all_voices if voice.lang.lower().startswith("ru")]
    voices.clear()
    voices.update((voice.voiceURI, voice) for voice in russian or all_voices)
    VOICE.replaceChildren()
    default = document.createElement("option")
    default.value = ""
    default.textContent = "Системный голос"
    VOICE.append(default)
    for key, voice in voices.items():
        option = document.createElement("option")
        option.value = key
        option.textContent = voice.name
        VOICE.append(option)
    preferred = stored(VOICE_KEY, persistent=True)
    VOICE.value = preferred if preferred in voices else ""


def choose_voice(event):
    save(VOICE_KEY, VOICE.value, persistent=True)
    if enabled:
        speak("Удобно так?")


def apply_theme(value):
    if value in ("light", "dark"):
        document.documentElement.setAttribute("data-theme", value)
    else:
        document.documentElement.removeAttribute("data-theme")


def choose_theme(event):
    apply_theme(THEME.value)
    save(THEME_KEY, THEME.value, persistent=True)


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
    selected = voices.get(VOICE.value)
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
        speak(PROMPT.textContent.strip() if PROMPT else "Слушаю.")
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
    labels = getattr(target, "labels", None)
    if not label and labels and labels.length:
        label = labels.item(0).textContent
    text = (label or target.textContent).strip()
    if question_pending and target.closest("main"):
        question_pending = False
        text = PROMPT.textContent.strip() + " " + text
    speak(text)


def move_focus(event):
    if event.defaultPrevented or any(
        (event.altKey, event.ctrlKey, event.metaKey, event.shiftKey)
    ):
        return
    if event.key == "Escape":
        stop_speech()
        return
    if not enabled or event.key not in ("ArrowDown", "ArrowUp") or event.target.closest(NATIVE_ARROWS):
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
VOICE.addEventListener("change", create_proxy(choose_voice))
THEME.addEventListener("change", create_proxy(choose_theme))
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
THEME.value = preferred_theme if preferred_theme in ("light", "dark") else "system"
apply_theme(THEME.value)

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
