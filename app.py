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

ROOT = Path(__file__).resolve().parent
PAGE = Template((ROOT / "page.html").read_text(encoding="utf-8"))
CSS = (ROOT / "styles.css").read_bytes()

GUIDES = {
    "windows": (
        "Включить Экранный диктор в Windows",
        "windows виндовс компьютер экранн диктор narrator скринридер",
        (
            "Одновременно нажмите клавиши Windows, Ctrl и Enter. Клавиша Windows обычно находится в нижнем ряду рядом с Alt.",
            "Дождитесь, пока Экранный диктор начнёт говорить. Для перехода к следующей ссылке нажмите Tab, для предыдущей — Shift и Tab. Enter открывает выбранную ссылку.",
            "Если сочетание не сработало, попробуйте Windows, Ctrl и N. Откроются настройки Экранного диктора. Если компьютер пока молчит, продолжайте читать эту инструкцию со второго устройства и попросите помочь включить переключатель в настройках.",
        ),
        "https://support.microsoft.com/en-us/accessibility/windows/narrator/chapter-1-introducing-narrator",
    ),
    "iphone": (
        "Включить VoiceOver на iPhone",
        "iphone айфон ios айос эппл apple телефон voiceover войсовер скринридер",
        (
            "Если Siri уже настроена, вызовите её и скажите: «Включи VoiceOver».",
            "Другой способ — открыть «Настройки», затем «Универсальный доступ», выбрать VoiceOver и включить его.",
            "Смахните одним пальцем вправо для следующего элемента или влево для предыдущего. Дважды коснитесь экрана одним пальцем, чтобы открыть выбранный элемент.",
        ),
        "https://support.apple.com/ru-ru/guide/iphone/iph3e2e415f/ios",
    ),
    "android": (
        "Включить TalkBack на Android",
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
        <h1>Помощь с экранным доступом</h1>
        <p>Найдите, как включить экранный доступ и выполнить первые действия без мыши.</p>
        <h2>Выберите устройство</h2>
        """ + guide_links(GUIDES, static=static)
    if not static:
        content += SEARCH.format(query="")
    return page("Инструкции по скринридерам", content, base="./" if static else "/")


def guide_page(key, base="/"):
    title, _, steps, source = GUIDES[key]
    items = "".join(f"<li>{escape(step)}</li>" for step in steps)
    return page(title, f"""
        <h1>{escape(title)}</h1>
        <ol class="steps">{items}</ol>
        <p><a href="{escape(source)}">Инструкция производителя</a></p>
        <p><a href="{base}">Все инструкции по устройствам</a></p>
        """, base=base)


def build_static():
    directory = ROOT / "guides"
    directory.mkdir(exist_ok=True)
    for key in GUIDES:
        (directory / f"{key}.html").write_bytes(guide_page(key, base="../"))
    (ROOT / "index.html").write_bytes(homepage(static=True))


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
