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
        <details>
          <summary>Голос и оформление</summary>
          <label for="voice-choice">Голос</label>
          <select id="voice-choice"><option value="">Системный голос</option></select>
          <label for="theme-choice">Оформление</label>
          <select id="theme-choice">
            <option value="system">Как в системе</option>
            <option value="light">Светлое</option>
            <option value="dark">Тёмное</option>
          </select>
        </details>
        <button id="keyboard-toggle" type="button" aria-pressed="false" aria-describedby="keyboard-help">Озвучить меню</button>
        <p id="keyboard-help" class="sr-only">Стрелки вверх и вниз выбирают пункт. Enter открывает. Escape останавливает речь.</p>
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
  color-scheme: light;
  --paper: #f8f6f0;
  --panel: #fffdf8;
  --ink: #121212;
  --accent: #26221d;
  --button-text: #fff;
  --focus: #0a3788;
  font: 125%/1.55 system-ui, "Segoe UI", sans-serif;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #151515;
  --panel: #212121;
  --ink: #f5f5f5;
  --accent: #fff;
  --button-text: #151515;
  --focus: #ffdf70;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    color-scheme: dark;
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
header { border-bottom: 1px solid var(--accent); }
header .shell { display: flex; align-items: baseline; justify-content: space-between; flex-wrap: wrap; gap: .25rem 1rem; padding-block: .45rem; }
.shell { width: min(100% - 2rem, 36rem); margin-inline: auto; }
.brand { display: inline-flex; align-items: center; min-height: 44px; font-weight: 800; }
#keyboard-mode { display: flex; align-items: baseline; flex-wrap: wrap; gap: .3rem .7rem; }
[hidden] { display: none !important; }
#keyboard-mode details { max-width: 100%; }
#keyboard-mode summary { cursor: pointer; min-height: 44px; padding-block: .35rem; }
#keyboard-mode label { margin-top: .45rem; }
#keyboard-status { flex-basis: 100%; margin: 0; }
#keyboard-status:empty { margin: 0; }
main { padding-block: 2.2rem 2rem; }
h1, h2 { line-height: 1.15; margin-block: 0 .55em; }
h1 { font-size: clamp(1.75rem, 5vw, 2.8rem); }
h2 { font-size: 1.25rem; margin-top: 1.1em; }
li + li { margin-top: .5rem; }
.guides { padding-inline-start: 1.3rem; }
.menu-link { display: block; padding: .6rem .8rem; background: var(--panel); border: 1px solid var(--accent); border-radius: .4rem; font-weight: 700; min-height: 52px; }
#menu { display: grid; gap: .65rem; margin-block: 1.15rem; }
.back-link { display: inline-flex; align-items: center; min-height: 44px; }
.key-hint { margin-block: .8rem; }
.entry-options { display: flex; flex-wrap: wrap; gap: .65rem; padding-block: .35rem; }
.guides a, .entry-options a { display: flex; align-items: center; min-height: 44px; padding: .5rem .7rem; background: var(--panel); border: 1px solid var(--accent); border-radius: .4rem; font-weight: 700; }
audio { width: min(100%, 20rem); }
.steps { padding-inline-start: 1.5rem; }
label { display: block; margin-bottom: .35rem; font-weight: 700; }
.search-row { display: flex; flex-wrap: wrap; gap: .5rem; }
button, input, select { font: inherit; min-height: 44px; border: 1px solid var(--accent); border-radius: .4rem; padding: .45rem .7rem; max-width: 100%; }
input { color: var(--ink); background: var(--panel); flex: 1 1 14rem; min-width: 0; }
select { color: var(--ink); background: var(--panel); }
button { color: var(--button-text); background: var(--accent); cursor: pointer; font-weight: 700; }
#file-form { display: grid; gap: .55rem; justify-items: start; }
#file-status:empty { margin: 0; }
.skip { position: absolute; top: .5rem; left: .5rem; padding: .5rem; background: var(--panel); transform: translateY(calc(-100% - 1rem)); }
.skip:focus { transform: none; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); }
@media (forced-colors: active) {
  :focus-visible, .arrow-mode :focus { outline-color: Highlight; }
  .guides a, .entry-options a, .menu-link, button, input, select { border-color: ButtonText; }
}
"""
