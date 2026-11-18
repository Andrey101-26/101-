"""Templates and styles emitted by the Python site builder."""

PAGE_TEMPLATE = r"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>$title — Голос и звук</title>
  <link rel="stylesheet" href="${base}styles.css">
  <script type="module" src="https://pyscript.net/releases/2026.7.3/core.js"></script>
</head>
<body>
  <a class="skip" href="#main">Перейти к основному содержимому</a>
  <header>
    <div class="shell">
      <a class="brand" href="$base">Голос и звук<span class="sr-only">, главная</span></a>
      <div id="keyboard-mode" hidden>
        <button id="keyboard-toggle" type="button" aria-pressed="false" aria-describedby="keyboard-help">Стрелки и озвучивание</button>
        <p id="keyboard-help">Вверх и вниз — выбрать пункт. Enter — открыть. Tab — обычная навигация. Escape — прервать озвучивание.</p>
        <p id="keyboard-status" role="status"></p>
      </div>
    </div>
  </header>
  <main class="shell" id="main" tabindex="-1">
    $content
  </main>
  <script type="py" src="${base}keyboard.py"></script>
</body>
</html>
"""

SITE_STYLES = r""":root {
  color-scheme: light dark;
  --paper: #f5f5f5;
  --panel: #fff;
  --ink: #121212;
  --accent: #181818;
  --button-text: #fff;
  --focus: #0a3788;
  font: 125%/1.55 system-ui, "Segoe UI", sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #151515;
    --panel: #212121;
    --ink: #f5f5f5;
    --accent: #fff;
    --button-text: #151515;
    --focus: #ffdf70;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); overflow-wrap: anywhere; }
a { color: var(--accent); text-underline-offset: .2em; }
:focus-visible, .arrow-mode :focus { outline: .18rem solid var(--focus); outline-offset: .16rem; }
header { background: var(--panel); border-bottom: 1px solid var(--accent); }
.shell { width: min(100% - 2rem, 37rem); margin-inline: auto; }
.brand { display: inline-flex; align-items: center; min-height: 44px; font-weight: 800; }
#keyboard-mode { padding-block: .3rem .65rem; }
#keyboard-mode p { margin: .45rem 0 0; }
#keyboard-status:empty { margin: 0; }
main { padding-block: 1.6rem 2rem; }
h1, h2 { line-height: 1.15; margin-block: 0 .55em; }
h1 { font-size: clamp(1.75rem, 5vw, 2.8rem); }
h2 { font-size: 1.25rem; margin-top: 1.1em; }
li + li { margin-top: .5rem; }
.guides { padding-inline-start: 1.3rem; }
.entry-options { display: flex; flex-wrap: wrap; gap: .65rem; padding-block: .35rem; }
.guides a, .entry-options a { display: flex; align-items: center; min-height: 44px; padding: .5rem .7rem; background: var(--panel); border: 1px solid var(--accent); border-radius: .4rem; font-weight: 700; }
audio { width: min(100%, 20rem); }
.steps { padding-inline-start: 1.5rem; }
label { display: block; margin-bottom: .35rem; font-weight: 700; }
.search-row { display: flex; flex-wrap: wrap; gap: .5rem; }
button, input { font: inherit; min-height: 44px; border: 1px solid var(--accent); border-radius: .4rem; padding: .45rem .7rem; }
input { color: var(--ink); background: var(--panel); flex: 1 1 14rem; min-width: 0; }
button { color: var(--button-text); background: var(--accent); cursor: pointer; font-weight: 700; }
.skip { position: absolute; top: .5rem; left: .5rem; padding: .5rem; background: var(--panel); transform: translateY(calc(-100% - 1rem)); }
.skip:focus { transform: none; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
@media (forced-colors: active) {
  :focus-visible, .arrow-mode :focus { outline-color: Highlight; }
  .guides a, .entry-options a, button, input { border-color: ButtonText; }
}
"""
