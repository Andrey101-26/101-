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
        <details id="site-settings">
          <summary>Настройки</summary>
          <div class="settings-panel">
            <div role="group" aria-labelledby="voice-label">
              <p id="voice-label" class="settings-label">Голос диктора</p>
              <div id="voice-choices" class="setting-choices"></div>
            </div>
            <div role="group" aria-labelledby="theme-label">
              <p id="theme-label" class="settings-label">Цветовая тема</p>
              <div class="setting-choices">
                <button type="button" data-theme-choice="system" aria-pressed="true">Системная</button>
                <button type="button" data-theme-choice="light" aria-pressed="false">Светлая</button>
                <button type="button" data-theme-choice="dark" aria-pressed="false">Тёмная</button>
              </div>
            </div>
            <button id="settings-close" type="button">Закрыть настройки</button>
          </div>
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
  --paper: #f7f8f5;
  --panel: #fff;
  --ink: #17241e;
  --muted: #3c5147;
  --line: #758279;
  --accent: #173e31;
  --button-text: #fff;
  --focus: #004ab3;
  font: 112.5%/1.5 system-ui, "Segoe UI", sans-serif;
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #171a18;
  --panel: #222a25;
  --ink: #f4f7f4;
  --muted: #c8d9cd;
  --line: #899c90;
  --accent: #c7ecdb;
  --button-text: #16281f;
  --focus: #ffdf70;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme]) {
    color-scheme: dark;
    --paper: #171a18;
    --panel: #222a25;
    --ink: #f4f7f4;
    --muted: #c8d9cd;
    --line: #899c90;
    --accent: #c7ecdb;
    --button-text: #16281f;
    --focus: #ffdf70;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink); overflow-wrap: anywhere; }
a { color: var(--accent); text-underline-offset: .2em; }
:focus-visible, .arrow-mode :focus { outline: .18rem solid var(--focus); outline-offset: .16rem; }
header { border-bottom: 1px solid var(--line); background: var(--panel); }
header .shell { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: .4rem 1rem; padding-block: .65rem; }
.shell { width: min(100% - 2rem, 36rem); margin-inline: auto; }
.brand { display: inline-flex; align-items: center; min-height: 44px; font-weight: 800; text-decoration: none; }
#keyboard-mode { display: flex; align-items: center; flex-wrap: wrap; gap: .45rem .7rem; }
[hidden] { display: none !important; }
#keyboard-mode details { max-width: 100%; }
#keyboard-mode:has(details[open]), #keyboard-mode details[open] { flex-basis: 100%; }
#keyboard-mode summary { cursor: pointer; min-height: 44px; padding: .45rem .7rem; border: 1px solid var(--line); border-radius: .4rem; }
.settings-panel { display: grid; gap: .75rem; padding: .8rem; margin-top: .4rem; border: 1px solid var(--line); border-radius: .4rem; }
.settings-panel > button { justify-self: start; }
.settings-label { margin: 0 0 .4rem; font-weight: 700; }
.setting-choices { display: flex; flex-wrap: wrap; gap: .4rem; }
.settings-panel button { background: var(--panel); color: var(--ink); font-weight: 600; }
.settings-panel button[aria-pressed="true"] { background: var(--accent); color: var(--button-text); }
.setting-choices button[aria-pressed="true"]::before { content: "✓ "; }
#keyboard-status { flex-basis: 100%; margin: 0; }
#keyboard-status:empty { margin: 0; }
main { padding-block: clamp(1.6rem, 5vw, 3.25rem) 2rem; }
h1, h2 { line-height: 1.15; margin-block: 0 .55em; }
h1 { font-size: clamp(1.75rem, 5vw, 2.8rem); }
h2 { font-size: 1.25rem; margin-top: 1.1em; }
li + li { margin-top: .5rem; }
.guides { padding-inline-start: 1.3rem; }
.menu-link { display: grid; gap: .12rem; padding: .8rem 1rem; background: var(--panel); border: 1px solid var(--line); border-radius: .55rem; min-height: 52px; text-decoration: none; }
.menu-link:hover strong { text-decoration: underline; }
.menu-link strong { font-size: 1.15rem; }
.menu-link span { color: var(--muted); }
#menu { display: grid; gap: .6rem; margin-block: 1.2rem .8rem; }
#entry-intro:not(:target):not([data-open]) { display: none; }
#entry-intro { margin-top: 1.5rem; }
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
