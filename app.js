'use strict';

const byId = (id) => document.getElementById(id);
const root = document.documentElement;
const theme = byId('theme');
const textSize = byId('text-size');

function readPreference(key) {
  try { return localStorage.getItem(key); } catch { return null; }
}

function savePreference(key, value) {
  try { localStorage.setItem(key, value); } catch { /* Apply for this visit. */ }
}

function applyTheme(dark) {
  root.dataset.theme = dark ? 'dark' : 'light';
  theme.setAttribute('aria-pressed', String(dark));
}

function applySize(size) {
  textSize.value = size;
  root.style.fontSize = (125 * Number(size) / 100) + '%';
}

const savedTheme = readPreference('giz.theme');
applyTheme(savedTheme ? savedTheme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches);
const savedSize = readPreference('giz.size');
applySize(['100', '125', '150'].includes(savedSize) ? savedSize : '100');
theme.addEventListener('click', () => {
  applyTheme(root.dataset.theme !== 'dark');
  savePreference('giz.theme', root.dataset.theme);
});
textSize.addEventListener('change', () => {
  applySize(textSize.value);
  savePreference('giz.size', textSize.value);
});

const query = byId('catalog-query');
const category = byId('category');
const entries = [...byId('catalog').children];
const normalize = (value) => value.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim();
let searchTimer;

function filterCatalog() {
  const words = normalize(query.value).split(/\s+/).filter(Boolean);
  let count = 0;
  for (const article of entries) {
    const title = normalize(article.querySelector('h3').textContent);
    const matches = words.every((word) => title.includes(word))
      && (!category.value || article.dataset.category === category.value);
    article.hidden = !matches;
    if (matches) count++;
  }
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    byId('search-status').textContent = count ? 'Найдено материалов: ' + count + '.' : 'Совпадений нет. Попробуйте другое название или выберите все категории.';
  }, 250);
}

query.addEventListener('input', filterCatalog);
category.addEventListener('change', filterCatalog);
byId('hub-search').addEventListener('submit', (event) => {
  event.preventDefault();
  query.value = byId('hub-query').value;
  category.value = '';
  filterCatalog();
  const section = byId('instructions');
  location.hash = section.id;
  section.focus();
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let activeRecognition;

for (const button of document.querySelectorAll('[data-dictate]')) {
  const field = byId(button.dataset.dictate);
  const status = byId(button.getAttribute('aria-describedby'));
  const label = button.textContent;
  if (!SpeechRecognition) {
    button.hidden = true;
    status.textContent = 'Голосовой ввод недоступен в этом браузере. Можно ввести текст с клавиатуры.';
    continue;
  }

  button.addEventListener('click', () => {
    if (activeRecognition) {
      if (activeRecognition.button === button) activeRecognition.recognition.stop();
      else status.textContent = 'Сначала завершите текущий голосовой ввод.';
      return;
    }
    const recognition = new SpeechRecognition();
    recognition.lang = 'ru-RU';
    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      const value = field.tagName === 'TEXTAREA' && field.value.trim() ? field.value.trimEnd() + ' ' + transcript : transcript;
      field.value = field.maxLength > 0 ? value.slice(0, field.maxLength) : value;
      status.textContent = 'Текст записан. Его можно отредактировать.';
    };
    recognition.onerror = () => {
      status.textContent = 'Не удалось распознать речь. Проверьте доступ к микрофону или введите текст.';
    };
    recognition.onend = () => {
      activeRecognition = null;
      button.textContent = label;
      if (status.textContent === 'Слушаю…') status.textContent = 'Голосовой ввод завершён.';
    };
    try {
      recognition.start();
      activeRecognition = { button, recognition };
      button.textContent = 'Остановить голосовой ввод';
      status.textContent = 'Слушаю…';
    } catch {
      status.textContent = 'Не удалось включить микрофон. Можно ввести текст.';
    }
  });
}

const audioStatus = byId('audio-status');
if ('speechSynthesis' in window && 'SpeechSynthesisUtterance' in window) {
  let activeAudio;

  function stopAudio() {
    if (!activeAudio) return;
    activeAudio.button.textContent = 'Озвучить урок';
    activeAudio.button.setAttribute('aria-label', 'Озвучить урок. ' + activeAudio.title);
    activeAudio = null;
    window.speechSynthesis.cancel();
    audioStatus.textContent = 'Озвучивание остановлено.';
  }

  for (const details of document.querySelectorAll('.lessons details')) {
    const title = details.querySelector('summary').textContent;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = 'Озвучить урок';
    button.setAttribute('aria-label', 'Озвучить урок. ' + title);
    details.querySelector('.audio').append(button);
    details.addEventListener('toggle', () => {
      if (!details.open && activeAudio?.button === button) stopAudio();
    });
    button.addEventListener('click', () => {
      const isPlaying = activeAudio?.button === button;
      stopAudio();
      if (isPlaying) return;
      const steps = [...details.querySelectorAll('li')].map((step, index) => (index + 1) + '. ' + step.textContent);
      const speech = new SpeechSynthesisUtterance([title, ...steps].join('. '));
      speech.lang = 'ru-RU';
      activeAudio = { button, title, speech };
      button.textContent = 'Остановить озвучивание';
      button.setAttribute('aria-label', 'Остановить озвучивание. ' + title);
      audioStatus.textContent = '';
      function finishAudio(message) {
        if (activeAudio?.speech !== speech) return;
        activeAudio = null;
        button.textContent = 'Озвучить урок';
        button.setAttribute('aria-label', 'Озвучить урок. ' + title);
        audioStatus.textContent = message;
      }
      speech.onend = () => finishAudio('Озвучивание завершено.');
      speech.onerror = () => finishAudio('Озвучивание недоступно. Текст урока можно прочитать в этом разделе.');
      window.speechSynthesis.speak(speech);
    });
  }
} else {
  audioStatus.textContent = 'Озвучивание недоступно в этом браузере. Текст уроков доступен ниже.';
}

const question = byId('question');
const photoInput = byId('photo');
const helpStatus = byId('help-status');
byId('send-help').disabled = false;
byId('help-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const photo = photoInput.files[0];
  if (!question.value.trim() && !photo) {
    question.focus();
    helpStatus.textContent = 'Введите вопрос или выберите фото.';
  } else if (photo && (!['image/jpeg', 'image/png', 'image/webp'].includes(photo.type) || photo.size > 5_000_000)) {
    photoInput.focus();
    helpStatus.textContent = 'Выберите JPEG, PNG или WebP размером до 5 МБ.';
  } else {
    helpStatus.textContent = 'Запрос готов для демонстрации. Данные остались на этой странице.';
  }
});
