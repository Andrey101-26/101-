"""Run with python app.py. The site uses only Python's standard library."""

import argparse
import os
import re
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from string import Template
from urllib.parse import parse_qs, urlsplit

from presentation import PAGE_TEMPLATE, SITE_STYLES

ROOT = Path(__file__).resolve().parent
PAGE = Template(PAGE_TEMPLATE)
CSS = SITE_STYLES.encode("utf-8")
KEYBOARD_PY = (ROOT / "keyboard.py").read_bytes()
AUDIO_DIR = ROOT / "audio"
LABEL_SOURCE = (
    '<a href="https://support.bemyeyes.com/hc/en-us/articles/360005528557-Getting-started-with-Be-My-Eyes">'
    "Как установить и использовать Be My Eyes</a>"
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
    "Привет, это «Голос и звук». Здесь есть практические инструкции и короткие выпуски. Чтобы сайт произносил названия выбранных пунктов, включите режим «Стрелки и озвучивание». Используйте стрелки вверх и вниз, а чтобы открыть пункт, нажмите Enter. Можно продолжить и в тишине.",
)


def find_recording(key):
    for suffix in ("mp3", "m4a", "wav"):
        path = AUDIO_DIR / f"{key}.{suffix}"
        if path.is_file():
            return path, False
    demo = AUDIO_DIR / f"demo-{key}.wav"
    return (demo, True) if demo.is_file() else (None, False)

GUIDES = {
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


def page(title, content, base="/"):
    return PAGE.substitute(title=escape(title), content=content.strip(), base=base).encode("utf-8")


def homepage(static=False):
    content = """
        <h1>Инструкции на каждый день</h1>
        <nav class="entry-options" aria-label="Как начать">
          <a href="#materials" data-quiet>Продолжить в тишине</a>
          <a href="intro.html">Вступление</a>
          <a href="#devices">Настройка скринридера</a>
          <a href="#clips">Короткие выпуски</a>
        </nav>
        <section aria-labelledby="materials">
          <h2 id="materials" tabindex="-1">Практические советы</h2>
          <h3>Как прочитать мелкую надпись на упаковке</h3>
          <p>{label_tip}</p>
          <p>{label_source}</p>
        </section>
        <section aria-labelledby="devices">
          <h2 id="devices" tabindex="-1">Настройка скринридера по желанию</h2>
          <p class="entry-options"><a href="#materials">Продолжить без настройки диктора</a></p>
        """.format(
        label_tip=escape(CLIPS["etiketka"][1]),
        label_source=LABEL_SOURCE,
    ) + guide_links(GUIDES, static=static)
    if not static:
        content += SEARCH.format(query="")
    items = "".join(
        f'<li><a href="clips/{key}.html">{escape(title)}</a></li>'
        for key, (title, _) in CLIPS.items()
    )
    content += f"""
        </section>
        <section aria-labelledby="clips">
          <h2 id="clips" tabindex="-1">Короткие выпуски</h2>
          <ol class="guides">{items}</ol>
        </section>
        """
    return page("Инструкции на каждый день", content, base="./" if static else "/")


def guide_page(key, base="/"):
    title, _, steps, source = GUIDES[key]
    items = "".join(f"<li>{escape(step)}</li>" for step in steps)
    return page(title, f"""
        <h1>{escape(title)}</h1>
        <ol class="steps">{items}</ol>
        <p><a href="{escape(source)}">Инструкция производителя</a></p>
        <p><a href="{base}#devices">Все инструкции по устройствам</a></p>
        """, base=base)


def clip_page(key, base):
    title, transcript = WELCOME if key == "intro" else CLIPS[key]
    recording, demo = find_recording(key)
    player = "<p>Пока доступен текст выпуска.</p>"
    if recording:
        src = f"{base}audio/{recording.name}"
        note = "<p>Пробная запись синтетическим голосом.</p>" if demo else ""
        player = note + f'<audio controls preload="none" src="{src}" aria-label="{escape(title)}"></audio>'
        player += f'<p><a href="{src}" download>Скачать запись</a></p>'

    navigation = [f'<a href="{base}#clips">Все выпуски</a>']
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
        <p>{escape(transcript)}</p>{source}
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
    write_page(output / "intro.html", clip_page("intro", base="./"))
    (output / "styles.css").write_bytes(CSS)
    (output / "keyboard.py").write_bytes(KEYBOARD_PY)

    audio_dir = output / "audio"
    audio_dir.mkdir(exist_ok=True)
    for key in ("intro", *CLIPS):
        recording, _ = find_recording(key)
        if recording:
            (audio_dir / recording.name).write_bytes(recording.read_bytes())


def search_guides(query):
    words = re.findall(r"[^\W_]+", query.casefold().replace("ё", "е"))
    filler = {"как", "в", "на", "и", "мне", "мой", "моем", "для"}
    words = [
        word for word in words
        if word not in filler and not word.startswith(("включ", "отключ", "запус", "запущ"))
    ]
    matches = []
    for key, (_, keywords, _, _) in GUIDES.items():
        terms = keywords.split()
        if not words or all(
            any(term.startswith(word) or (len(term) >= 5 and word.startswith(term)) for term in terms)
            for word in words
        ):
            matches.append(key)
    return matches


class Site(BaseHTTPRequestHandler):
    def do_GET(self):
        request = urlsplit(self.path)
        status = HTTPStatus.OK
        content_type = "text/html; charset=utf-8"

        if request.path == "/":
            body = homepage()
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
                results = '<p>Инструкция по этому запросу не найдена.</p><p><a href="/">Все инструкции по устройствам</a></p>'
            body = page("Результаты поиска", f"<h1>Результаты поиска</h1>{results}" + SEARCH.format(query=escape(query)))
        elif request.path.startswith("/guide/") and request.path[7:] in GUIDES:
            body = guide_page(request.path[7:])
        elif request.path == "/styles.css":
            body = CSS
            content_type = "text/css; charset=utf-8"
        elif request.path == "/keyboard.py":
            body = KEYBOARD_PY
            content_type = "text/plain; charset=utf-8"
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
