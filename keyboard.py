"""Optional keyboard and speech controls for browsers running PyScript."""

import asyncio
import importlib
import re
import sys
from collections import Counter
from pathlib import Path
from textwrap import wrap

from js import document, window
from pyodide.ffi import create_proxy

PANEL = document.getElementById("keyboard-mode")
TOGGLE = document.getElementById("keyboard-toggle")
STATUS = document.getElementById("keyboard-status")
VOICE_CHOICES = document.getElementById("voice-choices")
SETTINGS = document.getElementById("site-settings")
SETTINGS_SUMMARY = SETTINGS.querySelector("summary")
PROMPT = document.querySelector("[data-dialogue-prompt]")
ENTRY = document.getElementById("entry-intro")
ENTRY_AUDIO = ENTRY.querySelector("audio") if ENTRY else None
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


def extract_summary(text):
    parts = list(dict.fromkeys(
        " ".join(part.split())
        for part in re.split(r"(?<=[.!?…])\s+|[\r\n]+", text.strip())
        if re.search(r"\w", part)
    ))
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
        cue = any(word in unique for word in (
            "главное", "важно", "нужно", "итог", "итоги", "цель", "результат",
            "important", "must", "summary", "conclusion",
        ))
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
file_generation = 0
file_name = ""
package_loads = {}
STOP_DOCUMENT = document.getElementById("stop-document")
DOCUMENT_STATUS = document.getElementById("document-reading-status")
document_chunks = None
reading_generation = 0


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
    global document_chunks, reading_generation
    if document_chunks is not None:
        document_chunks = None
        reading_generation += 1
        STOP_DOCUMENT.disabled = True
        DOCUMENT_STATUS.textContent = "Чтение остановлено."
    if SPEAKER and UTTERANCE:
        SPEAKER.cancel()


def make_utterance(text):
    message = UTTERANCE.new(text)
    selected = voices.get(selected_voice)
    message.lang = selected.lang if selected else "ru-RU"
    if selected:
        message.voice = selected
    message.addEventListener("error", report_speech_error)
    return message


def speak(text):
    if not SPEAKER or not UTTERANCE:
        return
    stop_speech()
    clips = document.querySelectorAll("audio")
    if not text or any(not clips.item(i).paused for i in range(clips.length)):
        return
    SPEAKER.speak(make_utterance(text))


def read_next_part(event=None):
    global document_chunks
    if document_chunks is None or (event and event.target.golosReading != reading_generation):
        return
    text = next(document_chunks, "")
    if not text:
        document_chunks = None
        STOP_DOCUMENT.disabled = True
        DOCUMENT_STATUS.textContent = "Чтение завершено."
        return
    message = make_utterance(text)
    message.golosReading = reading_generation
    message.addEventListener("end", on_read_next_part)
    message.addEventListener("error", on_document_error)
    SPEAKER.speak(message)


def document_reading_error(event):
    if document_chunks is not None and event.target.golosReading == reading_generation:
        stop_speech()
        DOCUMENT_STATUS.textContent = "Не удалось продолжить озвучивание. Полный текст доступен ниже."


def speak_document(text):
    global document_chunks
    if not SPEAKER or not UTTERANCE or not text:
        return
    stop_speech()
    document_chunks = iter(wrap(" ".join(text.split()), width=170, break_on_hyphens=False))
    STOP_DOCUMENT.disabled = False
    DOCUMENT_STATUS.textContent = "Читаю документ целиком."
    read_next_part()


def stop_document_reading(event):
    stop_speech()
    document.querySelector("[data-read-full]").focus()


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
    if not enabled or document_chunks is not None or not target.matches(CONTROLS + ", h2[tabindex]"):
        return
    label = target.getAttribute("data-say") or target.getAttribute("aria-label")
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
    if event.defaultPrevented:
        return
    if event.key == "F2" and event.ctrlKey and event.shiftKey and not (event.altKey or event.metaKey):
        event.preventDefault()
        if not event.repeat:
            if SETTINGS.open:
                close_settings()
            else:
                SETTINGS.open = True
                SETTINGS_SUMMARY.focus()
        return
    if any((event.altKey, event.ctrlKey, event.metaKey, event.shiftKey)):
        return
    active = document.activeElement
    in_settings = SETTINGS.open and SETTINGS.contains(active)
    if event.key == "Escape":
        if in_settings:
            event.preventDefault()
            close_settings()
        stop_speech()
        if ENTRY_AUDIO and not ENTRY_AUDIO.paused:
            ENTRY_AUDIO.pause()
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
    button = event.currentTarget
    target = document.getElementById(button.getAttribute("data-read"))
    text = target.textContent.strip()
    if button.hasAttribute("data-read-full"):
        speak_document(text)
    else:
        speak(text)


def speak_entry(*_):
    speak(document.getElementById("entry-transcript").textContent.strip())


def open_entry(event):
    event.preventDefault()
    ENTRY.setAttribute("data-open", "")
    document.getElementById("entry-intro-heading").focus()
    if ENTRY_AUDIO:
        ENTRY_AUDIO.currentTime = 0
        ENTRY_AUDIO.play().catch(on_entry_audio_failure)
    else:
        speak_entry()


async def install_package(module, wheel):
    try:
        importlib.import_module(module)
    except ImportError:
        from pyodide.http import pyfetch

        response = await pyfetch(f"vendor/{wheel}")
        if not response.ok:
            raise OSError("Could not load bundled Python module")
        path = Path("/tmp") / wheel
        path.write_bytes(await response.bytes())
        sys.path.insert(0, str(path))
        importlib.import_module(module)


async def process_file(filename, data, generation):
    dependency = FILE_PACKAGES.get(file_suffix(filename))
    if dependency:
        module, package = dependency
        try:
            if package not in package_loads:
                package_loads[package] = asyncio.ensure_future(install_package(module, package))
            await package_loads[package]
        except Exception:
            package_loads.pop(package, None)
            if generation == file_generation:
                file_status.textContent = "Не удалось загрузить модуль чтения. Проверьте интернет и попробуйте снова."
            return
    if generation != file_generation:
        return
    try:
        text = read_document(filename, data)
        summary = extract_summary(text)
        if not summary:
            raise ValueError("Не удалось выделить главное из этого текста.")
    except ValueError as error:
        file_status.textContent = str(error)
        return
    except Exception:
        file_status.textContent = "Не удалось прочитать этот документ. Попробуйте сохранить его в другом формате."
        return
    file_status.textContent = ""
    document.getElementById("file-summary").textContent = summary
    document.getElementById("file-full-text").textContent = text
    document.querySelector("#file-result details").open = False
    document.getElementById("file-result").hidden = False
    document.getElementById("summary-heading").focus()


def file_result(event):
    data = window.Uint8Array.new(file_reader.result).to_bytes()
    asyncio.ensure_future(process_file(file_name, data, file_generation))


def file_error(event):
    file_status.textContent = "Не удалось прочитать файл. Попробуйте снова."


def clear_file_result(event=None):
    global file_generation
    file_generation += 1
    if file_reader.readyState == 1:
        file_reader.abort()
    document.getElementById("file-result").hidden = True
    document.getElementById("file-summary").textContent = ""
    document.getElementById("file-full-text").textContent = ""
    file_status.textContent = ""
    stop_speech()
    DOCUMENT_STATUS.textContent = ""


def read_file(event):
    global file_name
    event.preventDefault()
    clear_file_result()
    selected = document.getElementById("text-file").files.item(0)
    if not selected:
        file_status.textContent = "Выберите документ."
    elif file_suffix(selected.name) == ".doc":
        file_status.textContent = "Сохраните документ Word в формате DOCX и выберите его снова."
    elif file_suffix(selected.name) not in SUPPORTED:
        file_status.textContent = "Выберите DOCX, PDF, ODT, RTF, TXT, Markdown или CSV."
    elif selected.size > MAX_FILE_BYTES:
        file_status.textContent = "Выберите файл до 8 МБ."
    else:
        file_name = selected.name
        file_status.textContent = "Читаю документ…"
        file_reader.readAsArrayBuffer(selected)


def filter_instructions(event):
    event.preventDefault()
    if event.type == "reset":
        instruction_query.value = ""
    words = query_words(instruction_query.value)
    results = 0
    for index in range(instruction_groups.length):
        group = instruction_groups.item(index)
        items = group.querySelectorAll("[data-instruction]")
        visible = 0
        for item_index in range(items.length):
            item = items.item(item_index)
            match = matches_query(words, item.getAttribute("data-instruction"))
            item.hidden = not match
            visible += int(match)
        group.hidden = not visible
        results += visible
    instruction_status.textContent = (
        f"Найдено инструкций: {results}." if results else "Ничего не найдено. Попробуйте более короткий запрос."
    )


def prepare_help(event):
    event.preventDefault()
    name = document.getElementById("document-name").value.strip()
    subject = f"документ «{name}»" if name else "документ"
    help_text.value = (
        f"Здравствуйте! Можно получить {subject} в доступном формате? "
        "Подойдёт DOCX или TXT, в котором текст можно выделить и прочитать скринридером. Спасибо!"
    )
    help_status.textContent = "Сообщение готово."
    help_text.focus()


def help_copied(*_):
    help_status.textContent = "Сообщение скопировано."


def select_help(*_):
    help_text.focus()
    help_text.select()
    help_status.textContent = "Текст выделен. Нажмите Ctrl+C или Command+C."


def copy_help(event):
    clipboard = getattr(window.navigator, "clipboard", None)
    if clipboard:
        clipboard.writeText(help_text.value).then(on_help_copied).catch(on_help_fallback)
    else:
        select_help()


def normalize_number(value):
    number = re.sub(r"[\s().\-–—]", "", value.strip())
    return number if re.fullmatch(r"\+?[0-9]{3,15}", number) else ""


def clear_dial_link(event=None):
    dial_link.hidden = True
    dial_link.removeAttribute("href")
    dial_status.textContent = ""


def prepare_dial_link(event):
    event.preventDefault()
    clear_dial_link()
    number = normalize_number(dial_input.value)
    if not number:
        dial_status.textContent = "Проверьте номер. Введите от 3 до 15 цифр и, если нужно, плюс в начале."
        dial_input.focus()
        return
    dial_link.href = "tel:" + number
    dial_link.textContent = "Позвонить: " + number
    spoken = " ".join(digit if digit != "+" else "плюс" for digit in number)
    dial_link.setAttribute("data-say", "Позвонить. " + spoken)
    dial_link.hidden = False
    dial_link.focus()


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
if ENTRY:
    on_entry_audio_failure = create_proxy(speak_entry)
    document.getElementById("entry-listen").addEventListener("click", create_proxy(open_entry))
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
    if STOP_DOCUMENT:
        on_read_next_part = create_proxy(read_next_part)
        on_document_error = create_proxy(document_reading_error)
        STOP_DOCUMENT.addEventListener("click", create_proxy(stop_document_reading))
        STOP_DOCUMENT.hidden = False
refresh_voices()
preferred_theme = stored(THEME_KEY, persistent=True)
apply_theme(preferred_theme if preferred_theme in ("light", "dark") else "system")

file_form = document.getElementById("file-form")
if file_form:
    from document_text import FILE_PACKAGES, MAX_FILE_BYTES, SUPPORTED, file_suffix, read_document

    file_status = document.getElementById("file-status")
    file_reader = window.FileReader.new()
    file_reader.addEventListener("load", create_proxy(file_result))
    file_reader.addEventListener("error", create_proxy(file_error))
    file_form.addEventListener("submit", create_proxy(read_file))
    document.getElementById("text-file").addEventListener("change", create_proxy(clear_file_result))
    document.getElementById("file-fallback").hidden = True
    file_form.hidden = False

instruction_form = document.getElementById("instruction-filter")
if instruction_form:
    from instruction_search import matches_query, query_words

    instruction_query = document.getElementById("instruction-query")
    instruction_status = document.getElementById("instruction-status")
    instruction_groups = document.querySelectorAll("[data-instruction-group]")
    on_search = create_proxy(filter_instructions)
    instruction_form.addEventListener("submit", on_search)
    instruction_form.addEventListener("reset", on_search)
    instruction_form.hidden = False

help_form = document.getElementById("help-form")
if help_form:
    help_text = document.getElementById("help-text")
    help_status = document.getElementById("help-status")
    help_button = document.getElementById("copy-help")
    on_help_copied = create_proxy(help_copied)
    on_help_fallback = create_proxy(select_help)
    help_form.addEventListener("submit", create_proxy(prepare_help))
    help_button.addEventListener("click", create_proxy(copy_help))
    help_form.hidden = False
    help_button.hidden = False

dial_form = document.getElementById("dial-form")
if dial_form:
    dial_input = document.getElementById("phone-number")
    dial_status = document.getElementById("dial-status")
    dial_link = document.getElementById("dial-link")
    dial_form.addEventListener("submit", create_proxy(prepare_dial_link))
    dial_input.addEventListener("input", create_proxy(clear_dial_link))
    dial_form.hidden = False
update_mode()
PANEL.hidden = False
