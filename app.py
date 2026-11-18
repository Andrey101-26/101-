"""Run with python app.py. The site uses only Python's standard library."""

import argparse
import json
import os
import re
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import parse_qs, urlsplit

from document_text import FILE_PACKAGES
from instruction_search import matches_query, query_words
from presentation import PAGE_TEMPLATE, SITE_STYLES

ROOT = Path(__file__).resolve().parent
PAGE = Template(PAGE_TEMPLATE)
CSS = SITE_STYLES.encode("utf-8")
KEYBOARD_PY = (ROOT / "keyboard.py").read_bytes()
BROWSER_MODULES = {
    name: (ROOT / name).read_bytes()
    for name in ("document_text.py", "instruction_search.py")
}
AUDIO_DIR = ROOT / "audio"
VENDOR_DIR = ROOT / "vendor"
VENDOR_WHEELS = {wheel for _, wheel in FILE_PACKAGES.values()}
LABEL_SOURCE = (
    '<a href="https://support.bemyeyes.com/hc/en-us/articles/360005528557-Getting-started-with-Be-My-Eyes">'
    "Как установить и использовать Be My Eyes</a>"
)
EMERGENCY_SOURCE = "https://60.mchs.gov.ru/deyatelnost/press-centr/novosti/5827639"
EMERGENCY_NUMBERS = (
    ("112", "Единый номер экстренных служб", "Один, один, два"),
    ("101", "Пожарная охрана", "Один, ноль, один"),
    ("102", "Полиция", "Один, ноль, два"),
    ("103", "Скорая помощь", "Один, ноль, три"),
    ("104", "Аварийная газовая служба", "Один, ноль, четыре"),
)

CLIPS = {
    "etiketka": (
        "Прочитать мелкую надпись",
        "Нужно прочитать мелкую надпись на упаковке? В приложении Be My Eyes откройте раздел Be My AI и сфотографируйте надпись. Если в ответе пропущена строка, попросите прочитать именно её или сделайте снимок ближе.",
    ),
    "windows-tab": (
        "Перейти к нужной ссылке без мыши",
        "На компьютере нажмите клавишу Tab, чтобы перейти к следующей ссылке или кнопке. Чтобы вернуться, нажмите Shift и Tab одновременно. Когда услышите название нужной ссылки, нажмите Enter.",
    ),
    "iphone-gesture": (
        "Открыть выбранный пункт с VoiceOver",
        "Если на айфоне включён VoiceOver, смахните одним пальцем вправо, чтобы перейти к следующему элементу. Когда услышите название нужного пункта, дважды коснитесь экрана одним пальцем. Откроется выбранный пункт.",
    ),
}
WELCOME = (
    "Вступление",
    "Здравствуйте. Клавиша Tab переводит между пунктами. Если хотите слышать названия, включите «Озвучить меню» и выбирайте стрелками вверх и вниз. Enter открывает выбранный пункт. Escape останавливает речь.",
)
GUIDE_SUMMARIES = {
    "windows": "Нажмите Windows, Ctrl и Enter одновременно. Дождитесь голоса.",
    "iphone": "Попросите Siri включить VoiceOver. Для выбора смахните вправо. Для открытия дважды коснитесь экрана.",
    "android": "Если быстрый доступ к TalkBack настроен, удерживайте обе кнопки громкости. Если не получилось, откройте специальные возможности.",
    "zoom": "Увеличьте масштаб сочетанием Ctrl и плюс. На Mac используйте Command и плюс.",
    "label": "Сфотографируйте надпись в Be My AI. Если приложение пропустило строку, попросите прочитать именно её.",
}


def find_recording(key):
    for suffix in ("mp3", "m4a", "wav"):
        path = AUDIO_DIR / f"{key}.{suffix}"
        if path.is_file():
            return path, False
    demo = AUDIO_DIR / f"demo-{key}.wav"
    return (demo, True) if demo.is_file() else (None, False)

GUIDES = {
    "zoom": (
        "Увеличить текст на сайте",
        "мелк маленьк текст шрифт увелич масштаб крупн браузер не вижу zoom",
        (
            "На Windows или Linux нажмите Ctrl и плюс несколько раз. На Mac нажмите Command и плюс.",
            "Чтобы уменьшить масштаб, нажмите Ctrl и минус. На Mac — Command и минус.",
            "Чтобы вернуться к обычному размеру, нажмите Ctrl и ноль. На Mac — Command и ноль.",
        ),
        "https://support.google.com/chrome/answer/96810?hl=ru",
    ),
    "label": (
        "Прочитать надпись на упаковке",
        "прочитать мелк надпис упаковк этикетк фотограф текст камер",
        (
            "Откройте приложение Be My Eyes, затем раздел Be My AI.",
            "Сфотографируйте упаковку. Дождитесь текстового описания.",
            "Если нужная строка пропущена, задайте уточняющий вопрос или сделайте снимок ближе. В приложении также можно попросить волонтёра посмотреть на упаковку через камеру.",
        ),
        "https://support.bemyeyes.com/hc/en-us/articles/360005528557-Getting-started-with-Be-My-Eyes",
    ),
    "windows": (
        "Как включить Экранный диктор в Windows",
        "windows виндовс компьютер экранн диктор narrator скринридер",
        (
            "Одновременно нажмите клавиши Windows, Ctrl и Enter. Клавиша Windows обычно находится в нижнем ряду рядом с Alt.",
            "Дождитесь, пока Экранный диктор начнёт говорить. Для перехода к следующей ссылке нажмите Tab, для предыдущей — Shift и Tab. Enter открывает выбранную ссылку.",
            "Если сочетание не сработало, попробуйте Windows, Ctrl и N. Откроются настройки Экранного диктора. Если компьютер пока молчит, продолжайте читать эту инструкцию со второго устройства и попросите помочь включить переключатель в настройках.",
        ),
        "https://support.microsoft.com/en-us/accessibility/windows/narrator/chapter-1-introducing-narrator",
    ),
    "iphone": (
        "Как включить VoiceOver на iPhone",
        "iphone айфон ios айос эппл apple телефон voiceover войсовер скринридер",
        (
            "Если Siri уже настроена, вызовите её и скажите: «Включи VoiceOver».",
            "Другой способ — открыть «Настройки», затем «Универсальный доступ», выбрать VoiceOver и включить его.",
            "Смахните одним пальцем вправо для следующего элемента или влево для предыдущего. Дважды коснитесь экрана одним пальцем, чтобы открыть выбранный элемент.",
        ),
        "https://support.apple.com/ru-ru/guide/iphone/iph3e2e415f/ios",
    ),
    "android": (
        "Как включить TalkBack на Android",
        "android андроид телефон talkback толкбэк талкбэк скринридер",
        (
            "Если быстрый доступ к TalkBack настроен, нажмите обе кнопки громкости одновременно и удерживайте несколько секунд. Дождитесь голосового сообщения.",
            "При первой настройке телефона тоже можно попробовать обе кнопки громкости. Если быстрый доступ не срабатывает, найдите TalkBack в разделе «Специальные возможности» настроек телефона.",
            "После включения смахивайте одним пальцем вправо или влево. Два касания одним пальцем открывают выбранный элемент.",
        ),
        "https://support.google.com/accessibility/answer/6007100?hl=ru",
    ),
}

SEARCH = """
<form role="search" aria-label="Поиск инструкций" action="/search" method="get">
  <label for="query">Поиск по устройству или названию скринридера</label>
  <div class="search-row">
    <input id="query" name="q" type="search" maxlength="120" value="{query}" aria-describedby="example">
    <button type="submit">Найти</button>
  </div>
  <p id="example">Например, «Windows», «Экранный диктор» или «iPhone».</p>
</form>
"""


def guide_links(keys, static=False):
    route = "guides/{key}.html" if static else "/guide/{key}"
    items = "".join(
        f'<li><a href="{route.format(key=key)}">{escape(GUIDES[key][0])}</a></li>'
        for key in keys
    )
    return f'<ul class="guides">{items}</ul>'


def page(title, content, base="/", browser_module=None):
    config = ""
    if browser_module:
        files = json.dumps({"files": {f"./{browser_module}": f"./{browser_module}"}})
        config = f' config="{escape(files, quote=True)}"'
    return PAGE.substitute(
        title=escape(title), content=content.strip(), base=base, keyboard_config=config
    ).encode("utf-8")


def homepage(static=False):
    title, transcript = WELCOME
    base = "./" if static else "/"
    player = recording_player("intro", title, base) or (
        '<button type="button" data-read="entry-transcript" hidden>Повторить озвучку</button>'
    )
    return page("Начало", f"""
        <h1 data-dialogue-prompt="Прослушать вступление?">Прослушать вступление?</h1>
        <nav id="menu" aria-label="Вступительная инструкция">
          <a class="menu-link" id="entry-listen" href="#entry-intro"><strong>Прослушать вступление</strong></a>
          <a class="menu-link" href="menu.html"><strong>Пропустить вступление</strong></a>
        </nav>
        <section id="entry-intro" aria-labelledby="entry-intro-heading" tabindex="-1">
          <h2 id="entry-intro-heading" tabindex="-1">Как пользоваться сайтом</h2>
          <p id="entry-transcript">{escape(transcript)}</p>
          {player}
          <p><a class="back-link" href="menu.html">Перейти к меню</a></p>
        </section>
        """, base=base)


def menu_page(static=False):
    return page("Главное меню", """
        <h1 data-dialogue-prompt="Что пожелаете?">Что хотите сделать?</h1>
        <nav id="menu" aria-label="Главное меню" tabindex="-1">
          <a id="materials" class="menu-link" href="instructions.html" aria-labelledby="instructions-label" aria-describedby="instructions-description">
            <strong id="instructions-label">Найти инструкцию</strong>
            <span id="instructions-description">Увеличить текст, прочитать надпись или настроить диктора.</span>
          </a>
          <a class="menu-link" href="file.html" aria-labelledby="file-label" aria-describedby="file-description">
            <strong id="file-label">Прочитать документ</strong>
            <span id="file-description">Откройте Word, PDF или другой файл и прослушайте главное.</span>
          </a>
          <a class="menu-link" href="help.html" aria-labelledby="help-label" aria-describedby="help-description">
            <strong id="help-label">Попросить о помощи</strong>
            <span id="help-description">Найдите волонтёра или составьте запрос на доступный документ.</span>
          </a>
          <a class="menu-link" href="phone.html#dial" aria-labelledby="dial-label" aria-describedby="dial-description">
            <strong id="dial-label">Набрать номер</strong>
            <span id="dial-description">Введите номер с клавиатуры и откройте его в приложении для звонков.</span>
          </a>
        </nav>
        <p class="entry-options">
          <a class="back-link" href="#menu" data-quiet>Продолжить в тишине</a>
          <a class="back-link" href="intro.html">Вступление</a>
        </p>
        """, base="./" if static else "/")


def instructions_page(static=False):
    route = "guides/{key}.html" if static else "/guide/{key}"

    def item(title, url, keywords):
        return f'<li data-instruction="{escape(keywords)}"><a href="{url}">{escape(title)}</a></li>'

    def guide_item(key):
        title, keywords, _, _ = GUIDES[key]
        return item(title, route.format(key=key), keywords + " " + title)

    daily = guide_item("zoom") + guide_item("label")
    devices = "".join(guide_item(key) for key in ("windows", "iphone", "android"))
    return page("Инструкции", f"""
        <h1 data-dialogue-prompt="Что подсказать?">Инструкции</h1>
        <form id="instruction-filter" role="search" aria-label="Найти инструкцию" hidden>
          <label for="instruction-query">Что нужно сделать?</label>
          <div class="search-row">
            <input type="search" id="instruction-query" maxlength="120" placeholder="Например, мелкий текст">
            <button type="submit">Найти</button>
            <button type="reset">Показать всё</button>
          </div>
        </form>
        <p id="instruction-status" role="status"></p>
        <section aria-labelledby="daily-tasks" data-instruction-group>
          <h2 id="daily-tasks">На каждый день</h2>
          <ul class="guides">{daily}</ul>
        </section>
        <section aria-labelledby="devices" data-instruction-group>
          <h2 id="devices" tabindex="-1">Настроить экранный диктор</h2>
          <ul class="guides">{devices}</ul>
        </section>
        <p><a class="back-link" href="menu.html">Вернуться к меню</a></p>
        """, base="./" if static else "/", browser_module="instruction_search.py")


def file_page(static=False):
    return page("Главное из файла", """
        <h1 data-dialogue-prompt="Что прочитать?">Главное из документа</h1>
        <p id="file-fallback">Подготовка чтения файлов в браузере…</p>
        <form id="file-form" hidden>
          <label for="text-file">Выберите документ</label>
          <input id="text-file" type="file" accept=".docx,.pdf,.odt,.rtf,.txt,.md,.csv" aria-describedby="file-help" required>
          <p id="file-help">DOCX (Word), PDF, ODT, RTF, TXT, Markdown и CSV. До 8 МБ. Файл остаётся в браузере.</p>
          <button type="submit">Выделить главное</button>
        </form>
        <p id="file-status" role="status"></p>
        <section id="file-result" aria-labelledby="summary-heading" hidden>
          <h2 id="summary-heading" tabindex="-1">Вот главное</h2>
          <p id="file-summary"></p>
          <button type="button" data-read="file-summary" hidden>Озвучить главное</button>
          <details>
            <summary>Прочитать документ целиком</summary>
            <button type="button" data-read="file-full-text" data-read-full hidden>Озвучить весь текст</button>
            <button type="button" id="stop-document" hidden disabled>Остановить чтение</button>
            <p id="document-reading-status" role="status"></p>
            <div id="file-full-text" class="document-text"></div>
          </details>
        </section>
        <p><a class="back-link" href="menu.html">Вернуться к меню</a></p>
        """, base="./" if static else "/", browser_module="document_text.py")


def help_page(static=False):
    return page("Помощь", f"""
        <h1 data-dialogue-prompt="Чем помочь?">Попросить о помощи</h1>
        <p><a class="urgent-link" href="phone.html">Экстренная помощь в России</a></p>
        <section aria-labelledby="volunteer">
          <h2 id="volunteer">Если нужно, чтобы кто-то посмотрел</h2>
          <p>В приложении Be My Eyes можно позвонить волонтёру и показать надпись или предмет через камеру.</p>
          <p>{LABEL_SOURCE}</p>
        </section>
        <section aria-labelledby="request">
          <h2 id="request">Если нужен доступный документ</h2>
          <form id="help-form" hidden>
            <label for="document-name">Название документа или ссылки (необязательно)</label>
            <input id="document-name" type="text" maxlength="120">
            <button type="submit">Подготовить сообщение</button>
          </form>
          <div id="help-message">
            <label for="help-text">Текст запроса</label>
            <textarea id="help-text" rows="5" readonly>Здравствуйте! Можно получить документ в доступном формате? Подойдёт DOCX или TXT, в котором текст можно выделить и прочитать скринридером. Спасибо!</textarea>
            <button type="button" id="copy-help" hidden>Скопировать сообщение</button>
            <p id="help-status" role="status"></p>
          </div>
        </section>
        <p><a class="back-link" href="menu.html">Вернуться к меню</a></p>
        """, base="./" if static else "/")


def phone_page(static=False):
    links = "".join(
        f'<li><a href="tel:{number}" data-say="{spoken}. {service}.">{number} — {service}</a></li>'
        for number, service, spoken in EMERGENCY_NUMBERS
    )
    return page("Экстренная помощь и звонки", f"""
        <h1 data-dialogue-prompt="Куда позвонить?">Экстренная помощь в России</h1>
        <ul class="guides emergency-numbers">{links}</ul>
        <p>Ссылка передаёт номер приложению для звонков. Если оно не открылось, наберите номер на телефоне.</p>
        <p><a href="{EMERGENCY_SOURCE}">Номера экстренных служб на сайте МЧС</a></p>
        <section aria-labelledby="dial">
          <h2 id="dial" tabindex="-1">Набрать другой номер</h2>
          <form id="dial-form" hidden>
            <label for="phone-number">Номер телефона</label>
            <div class="search-row">
              <input id="phone-number" type="tel" inputmode="tel" maxlength="40"
                aria-describedby="dial-hint" autocomplete="off" required>
              <button type="submit">Проверить номер</button>
            </div>
            <p id="dial-hint">От 3 до 15 цифр. Для международного номера начните с плюса.</p>
          </form>
          <p id="dial-status" role="status"></p>
          <p><a id="dial-link" class="back-link" hidden>Позвонить</a></p>
        </section>
        <p><a class="back-link" href="menu.html">Вернуться к меню</a></p>
        """, base="./" if static else "/")


def clips_page(static=False):
    items = "".join(
        f'<li><a href="clips/{key}.html">{escape(title)}</a></li>'
        for key, (title, _) in CLIPS.items()
    )
    return page("Короткие выпуски", f"""
        <h1 data-dialogue-prompt="Что включить?">Короткие аудиосоветы</h1>
        <ol class="guides">{items}</ol>
        <p><a class="back-link" href="menu.html">Вернуться к меню</a></p>
        """, base="./" if static else "/")


def guide_page(key, base="/"):
    title, _, steps, source = GUIDES[key]
    items = "".join(f"<li>{escape(step)}</li>" for step in steps)
    return page(title, f"""
        <h1>{escape(title)}</h1>
        <h2>Коротко</h2>
        <p id="guide-summary">{escape(GUIDE_SUMMARIES[key])}</p>
        <button type="button" data-read="guide-summary" hidden>Озвучить главное</button>
        <h2>По шагам</h2>
        <ol class="steps">{items}</ol>
        <p><a href="{escape(source)}">Официальная справка</a></p>
        <p><a href="{base}instructions.html">Вернуться к инструкциям</a></p>
        """, base=base)


def recording_player(key, title, base):
    recording, demo = find_recording(key)
    if not recording:
        return ""
    src = f"{base}audio/{recording.name}"
    note = "<p>Пробная запись синтетическим голосом.</p>" if demo else ""
    return (
        note + f'<audio controls preload="none" src="{src}" aria-label="{escape(title)}"></audio>'
        f'<p><a href="{src}" download>Скачать запись</a></p>'
    )


def clip_page(key, base):
    title, transcript = WELCOME if key == "intro" else CLIPS[key]
    player = recording_player(key, title, base)
    if not player:
        player = (
            '<button type="button" data-read="clip-transcript" hidden>Прослушать вступление</button>'
            if key == "intro" else "<p>Пока доступен текст выпуска.</p>"
        )

    navigation = [f'<a href="{base}clips.html">Все выпуски</a>'] if key in CLIPS else [
        f'<a href="{base}menu.html">Перейти к меню</a>'
    ]
    if key in CLIPS:
        keys = list(CLIPS)
        index = keys.index(key)
        if index > 0:
            prev_key = keys[index - 1]
            navigation.insert(0, f'<a href="{prev_key}.html">Предыдущий выпуск: {escape(CLIPS[prev_key][0])}</a>')
        if index < len(keys) - 1:
            next_key = keys[index + 1]
            navigation.insert(0, f'<a href="{next_key}.html">Следующий выпуск: {escape(CLIPS[next_key][0])}</a>')

    source = ""
    if key == "etiketka":
        source = f"<p>{LABEL_SOURCE}</p>"
    return page(title, f"""
        <h1>{escape(title)}</h1>
        {player}
        <h2>Текст выпуска</h2>
        <p id="clip-transcript">{escape(transcript)}</p>{source}
        <nav class="entry-options" aria-label="Навигация по выпускам">{"".join(navigation)}</nav>
        """, base=base)


def build_static():
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)

    def write_page(path, content):
        marker = b"<!-- Generated by python app.py --build-static. Edit the Python source. -->\n"
        path.write_bytes(marker + content)

    directory = output / "guides"
    directory.mkdir(exist_ok=True)
    for key in GUIDES:
        write_page(directory / f"{key}.html", guide_page(key, base="../"))
    clips_dir = output / "clips"
    clips_dir.mkdir(exist_ok=True)
    for key in CLIPS:
        write_page(clips_dir / f"{key}.html", clip_page(key, base="../"))
    write_page(output / "index.html", homepage(static=True))
    write_page(output / "menu.html", menu_page(static=True))
    write_page(output / "instructions.html", instructions_page(static=True))
    write_page(output / "file.html", file_page(static=True))
    write_page(output / "help.html", help_page(static=True))
    write_page(output / "phone.html", phone_page(static=True))
    write_page(output / "clips.html", clips_page(static=True))
    write_page(output / "intro.html", clip_page("intro", base="./"))
    (output / "styles.css").write_bytes(CSS)
    (output / "keyboard.py").write_bytes(KEYBOARD_PY)
    for filename, source in BROWSER_MODULES.items():
        (output / filename).write_bytes(source)
    vendor_output = output / "vendor"
    vendor_output.mkdir(exist_ok=True)
    for wheel in VENDOR_WHEELS:
        (vendor_output / wheel).write_bytes((VENDOR_DIR / wheel).read_bytes())

    audio_dir = output / "audio"
    audio_dir.mkdir(exist_ok=True)
    for key in ("intro", *CLIPS):
        recording, _ = find_recording(key)
        if recording:
            (audio_dir / recording.name).write_bytes(recording.read_bytes())


def search_guides(query):
    words = query_words(query)
    return [key for key, (title, keywords, _, _) in GUIDES.items() if matches_query(words, keywords + " " + title)]


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlsplit(self.path)
        status = HTTPStatus.OK
        content_type = "text/html; charset=utf-8"

        if request.path == "/":
            body = homepage()
        elif request.path == "/menu.html":
            body = menu_page()
        elif request.path == "/instructions.html":
            body = instructions_page()
        elif request.path == "/file.html":
            body = file_page()
        elif request.path == "/help.html":
            body = help_page()
        elif request.path == "/phone.html":
            body = phone_page()
        elif request.path == "/clips.html":
            body = clips_page()
        elif request.path == "/intro.html":
            body = clip_page("intro", base="/")
        elif request.path.startswith("/clips/") and request.path.endswith(".html") and request.path[7:-5] in CLIPS:
            body = clip_page(request.path[7:-5], base="/")
        elif match := re.fullmatch(r"/audio/((?:demo-)?[a-z-]+)\.(mp3|m4a|wav)", request.path):
            audio_path = AUDIO_DIR / f"{match[1]}.{match[2]}"
            if audio_path.is_file():
                body = audio_path.read_bytes()
                content_type = {"mp3": "audio/mpeg", "m4a": "audio/mp4", "wav": "audio/wav"}[match[2]]
            else:
                status = HTTPStatus.NOT_FOUND
                body = page("Запись не найдена", '<h1>Запись не найдена</h1><p><a href="/#clips">Все выпуски</a></p>')
        elif request.path == "/search":
            query = parse_qs(request.query).get("q", [""])[0].strip()[:120]
            matches = search_guides(query)
            if matches:
                results = f"<p>Найдено инструкций: {len(matches)}.</p>" + guide_links(matches)
            else:
                results = '<p>Инструкция по этому запросу не найдена.</p><p><a href="/instructions.html#devices">Все инструкции по устройствам</a></p>'
            body = page("Результаты поиска", f"<h1>Результаты поиска</h1>{results}" + SEARCH.format(query=escape(query)))
        elif request.path.startswith("/guide/") and request.path[7:] in GUIDES:
            body = guide_page(request.path[7:])
        elif request.path == "/styles.css":
            body = CSS
            content_type = "text/css; charset=utf-8"
        elif request.path == "/keyboard.py":
            body = KEYBOARD_PY
            content_type = "text/plain; charset=utf-8"
        elif request.path.removeprefix("/") in BROWSER_MODULES:
            body = BROWSER_MODULES[request.path.removeprefix("/")]
            content_type = "text/plain; charset=utf-8"
        elif request.path.startswith("/vendor/") and request.path[8:] in VENDOR_WHEELS:
            body = (VENDOR_DIR / request.path[8:]).read_bytes()
            content_type = "application/zip"
        else:
            status = HTTPStatus.NOT_FOUND
            body = page("Страница не найдена", '<h1>Страница не найдена</h1><p><a href="/">Все инструкции по устройствам</a></p>')

        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve():
    address = ("127.0.0.1", int(os.environ.get("PORT", "8000")))
    with ThreadingHTTPServer(address, Site) as server:
        print(f"Голос и звук: http://{address[0]}:{address[1]}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Голос и звук")
    parser.add_argument("--build-static", action="store_true", help="Собрать страницы для GitHub Pages.")
    if parser.parse_args().build_static:
        build_static()
    else:
        serve()
