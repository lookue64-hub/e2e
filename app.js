'use strict';

// Универсальная функция статуса
function status(msg, type='') {
  const s = document.getElementById('status');
  if (!s) return;
  s.textContent = msg;
  s.className = `status show ${type}`;
  if (!msg) s.className = 'status';
}

async function derive(password, salt) {
  const enc = new TextEncoder();
  const mat = await crypto.subtle.importKey('raw', enc.encode(password), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({name: 'PBKDF2', salt, iterations: 400000, hash: 'SHA-256'}, mat, 512);
  const bytes = new Uint8Array(bits);
  return {
    aes: await crypto.subtle.importKey('raw', bytes.slice(0, 32), 'AES-GCM', false, ['encrypt', 'decrypt']),
    hmac: await crypto.subtle.importKey('raw', bytes.slice(32, 64), {name: 'HMAC', hash: 'SHA-256'}, false, ['sign', 'verify'])
  };
}

function b64(buf) { return btoa(String.fromCharCode(...new Uint8Array(buf))); }
function ub64(str) { const bin = atob(str); const u8 = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u8[i] = bin.charCodeAt(i); return u8; }

function clearAll() {
  const msgEl = document.getElementById('message');
  const statusEl = document.getElementById('status');
  if (msgEl) msgEl.value = '';
  if (statusEl) statusEl.className = 'status';
}

async function pasteFromClipboard() {
  try {
    if (!navigator.clipboard) throw new Error('No clipboard');
    const text = await navigator.clipboard.readText();
    const el = document.getElementById('message');
    if (el) el.value = text;
    status('📋 Текст вставлен из буфера', 'success');
  } catch (e) {
    status('❌ Не удалось прочитать буфер обмена', 'error');
  }
}

async function encrypt() {
  const textEl = document.getElementById('message');
  const pwdEl = document.getElementById('password');
  const text = textEl ? textEl.value.trim() : '';
  const pwd = pwdEl ? pwdEl.value.trim() : '';
  if (!text || !pwd) { status('Введите пароль и сообщение', 'error'); return; }
  try {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const {aes, hmac} = await derive(pwd, salt);
    const enc = new TextEncoder();
    const ct = await crypto.subtle.encrypt({name: 'AES-GCM', iv}, aes, enc.encode(text));
    const mac = await crypto.subtle.sign('HMAC', hmac, ct);
    const all = new Uint8Array(salt.length + iv.length + ct.byteLength + 32);
    all.set(salt, 0); all.set(iv, 16); all.set(new Uint8Array(ct), 28); all.set(new Uint8Array(mac), 28 + ct.byteLength);
    const out = b64(all.buffer);
    if (textEl) textEl.value = out;
    try {
      await navigator.clipboard.writeText(out);
      status('✅ Зашифровано и скопировано в буфер!', 'success');
    } catch (_) {
      status('✅ Зашифровано (скопируйте вручную)', 'success');
    }
  } catch (e) {
    status('Ошибка шифрования', 'error');
  }
}

async function decrypt() {
  const dataEl = document.getElementById('message');
  const pwdEl = document.getElementById('password');
  const dataB64 = dataEl ? dataEl.value.trim() : '';
  const pwd = pwdEl ? pwdEl.value.trim() : '';
  if (!dataB64 || !pwd) { status('Введите пароль и шифротекст', 'error'); return; }
  try {
    const data = ub64(dataB64);
    const salt = data.slice(0, 16), iv = data.slice(16, 28), mac = data.slice(data.length - 32), ct = data.slice(28, data.length - 32);
    const {aes, hmac} = await derive(pwd, salt);
    const ok = await crypto.subtle.verify('HMAC', hmac, mac, ct);
    if (!ok) throw new Error('HMAC');
    const plain = await crypto.subtle.decrypt({name: 'AES-GCM', iv}, aes, ct);
    if (dataEl) dataEl.value = new TextDecoder().decode(plain);
    status('✅ Расшифровано!', 'success');
  } catch (e) {
    status('❌ Неверный пароль или данные', 'error');
  }
}

// Функция для определения iOS-устройства
function isIOS() {
  try {
    return /iP(ad|hone|od)/.test(navigator.platform) || (navigator.userAgent.includes('Mac') && 'ontouchend' in document);
  } catch (e) { return false; }
}

// Выделение всего текста в textarea (работает специально для iOS)
function selectAllIos() {
  const ta = document.getElementById('message');
  if (!ta) return;
  ta.focus();
  try { ta.setSelectionRange(0, ta.value.length); } catch (err) { /* ignore */ }
  setTimeout(() => { try { ta.select(); } catch (e) { /* no-op */ } }, 50);
  status('Выделено всё', 'success');
}

function setupUi() {
  const btnEncrypt = document.getElementById('btn-encrypt');
  const btnDecrypt = document.getElementById('btn-decrypt');
  const btnPaste = document.getElementById('btn-paste');
  const btnSelect = document.getElementById('btn-select');
  const btnClear = document.getElementById('btn-clear');

  if (btnEncrypt) btnEncrypt.addEventListener('click', encrypt);
  if (btnDecrypt) btnDecrypt.addEventListener('click', decrypt);
  if (btnPaste) btnPaste.addEventListener('click', pasteFromClipboard);
  if (btnSelect) btnSelect.addEventListener('click', selectAllIos);
  if (btnClear) btnClear.addEventListener('click', clearAll);

  const isIOSDevice = isIOS();
  if (btnSelect && btnPaste) {
    if (isIOSDevice) {
      btnSelect.style.display = 'inline-flex';
      btnPaste.style.display = 'none';
    } else {
      btnSelect.style.display = 'none';
      btnPaste.style.display = 'inline-flex';
    }
  }

  // Автовставка ограничена: вставляем при загрузке только если это похоже на base64 шифротекст
  try {
    if (navigator.clipboard) {
      navigator.clipboard.readText().then(text => {
        if (text && /^[A-Za-z0-9+/=]+$/.test(text.trim()) && text.trim().length > 20) {
          const el = document.getElementById('message');
          if (el && !el.value) el.value = text.trim();
          status('📥 Вставлен шифротекст из буфера', 'success');
        }
      }).catch(()=>{/* no-op */});
    }
  } catch (e) { /* no-op */ }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', setupUi);
} else {
  setupUi();
}

