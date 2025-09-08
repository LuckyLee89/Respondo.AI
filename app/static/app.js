// ===================== ESTADO GERAL ======================
let currentReplyLang = localStorage.getItem('replyLang') || 'pt';
let replyPT = '';
let replyEN = '';
let loading = false;
let lastResult = null;

const REQUEST_TIMEOUT_MS = 25000; // timeout de rede

// ===================== ELEMENTOS =========================
const form = document.getElementById('emailForm');
const fileInput = document.getElementById('email_file');
const dropzone = document.getElementById('dropzone');
const filePill = document.getElementById('filePill');
const emailText = document.getElementById('email_text');

const result = document.getElementById('result');
const resultEmpty = document.getElementById('resultEmpty');
const badge = document.getElementById('badge');
const prob = document.getElementById('prob');
const reply = document.getElementById('reply');
const explain = document.getElementById('explain');
const preview = document.getElementById('preview');

const submitBtn = document.getElementById('submitBtn');
const submitText = document.getElementById('submitText');
const iconSend = document.getElementById('iconSend');
const iconSpinner = document.getElementById('iconSpinner');
const clearBtn = document.getElementById('clearBtn');
const copyBtn = document.getElementById('copyBtn');
const copyState = document.getElementById('copyState');

const btnLangPT = document.getElementById('btnLangPT');
const btnLangEN = document.getElementById('btnLangEN');

// ===== Branding (logo & nome) =====
const brandLogo = document.getElementById('brandLogo');
const brandLogoEdit = document.getElementById('brandLogoEdit');
const brandLogoFile = document.getElementById('brandLogoFile');
const resetBrandBtn = document.getElementById('resetBrandBtn');
const brandNameEl = document.getElementById('brandName');
const editBrandNameBtn = document.getElementById('editBrandNameBtn');

// Elementos da Modal
const logoPreviewModal = document.getElementById('logoPreviewModal');
const logoPreviewImg = document.getElementById('logoPreviewImg');
const logoConsent = document.getElementById('logoConsent');
const logoApplyBtn = document.getElementById('logoApplyBtn');
const logoCancelBtn = document.getElementById('logoCancelBtn');
const preferredLangInput = document.getElementById('preferred_lang');
let userChoseLang = false;

let pendingLogoDataURL = null;

// ===================== BRANDING ==========================
async function loadBranding() {
  try {
    const res = await fetch('/config');
    const data = await res.json();
    if (data?.ok) {
      if (data.company_name && !localStorage.getItem('brandName')) {
        brandNameEl.textContent = data.company_name;
        document.title = `${data.company_name} — Classificador & Respostas de Email`;
      }
      if (data.logo_url && !localStorage.getItem('brandLogoDataURL')) {
        brandLogo.src = data.logo_url;
      }
    }
  } catch (e) {
    console.warn('Sem /config, usando defaults.');
  }
  const savedLogo = localStorage.getItem('brandLogoDataURL');
  if (savedLogo) brandLogo.src = savedLogo;
  const savedName = localStorage.getItem('brandName');
  if (savedName) {
    brandNameEl.textContent = savedName;
    document.title = `${savedName} — Classificador & Respostas de Email`;
  }
}
loadBranding();

brandLogoEdit.addEventListener('click', () => brandLogoFile.click());
brandLogo.addEventListener('click', () => brandLogoFile.click());

brandLogoFile.addEventListener('change', () => {
  const file = brandLogoFile.files?.[0];
  if (!file) return;

  const maxBytes = 5 * 1024 * 1024; // 5MB
  if (file.size > maxBytes) {
    alert('Imagem muito grande. Use até 5MB.');
    brandLogoFile.value = '';
    return;
  }
  if (!['image/png', 'image/jpeg', 'image/svg+xml'].includes(file.type)) {
    alert('Formato não suportado. Use PNG, JPG ou SVG.');
    brandLogoFile.value = '';
    return;
  }

  const reader = new FileReader();
  reader.onload = () => {
    pendingLogoDataURL = reader.result;
    logoPreviewImg.src = pendingLogoDataURL;
    logoConsent.checked = false;
    logoApplyBtn.disabled = true;
    logoPreviewModal.classList.remove('hidden');
    logoPreviewModal.classList.add('flex');
  };
  reader.readAsDataURL(file);
});

logoConsent.addEventListener('change', () => {
  logoApplyBtn.disabled = !logoConsent.checked;
});

logoApplyBtn.addEventListener('click', () => {
  if (!pendingLogoDataURL || !logoConsent.checked) return;
  brandLogo.src = pendingLogoDataURL;
  try {
    localStorage.setItem('brandLogoDataURL', pendingLogoDataURL);
  } catch {}
  pendingLogoDataURL = null;
  logoPreviewModal.classList.add('hidden');
  logoPreviewModal.classList.remove('flex');
  brandLogoFile.value = '';
});

logoCancelBtn.addEventListener('click', () => {
  pendingLogoDataURL = null;
  logoPreviewModal.classList.add('hidden');
  logoPreviewModal.classList.remove('flex');
  brandLogoFile.value = '';
});

resetBrandBtn.addEventListener('click', async () => {
  localStorage.removeItem('brandLogoDataURL');
  try {
    const res = await fetch('/config');
    const data = await res.json();
    brandLogo.src =
      data?.ok && data.logo_url ? data.logo_url : '/static/logo.png';
  } catch {
    brandLogo.src = '/static/logo.png';
  }
});

editBrandNameBtn.addEventListener('click', () => {
  const current = brandNameEl.textContent.trim();
  const val = prompt('Nome da empresa:', current || 'Minha Empresa');
  if (val === null) return;
  const name = val.trim();
  if (!name) return;
  brandNameEl.textContent = name;
  document.title = `${name} — Classificador & Respostas de Email`;
  localStorage.setItem('brandName', name);
});

// ===================== HELPERS ============================
function setLoading(is) {
  loading = is;
  submitBtn.disabled = is;
  if (is) {
    submitText.textContent = 'Processando...';
    iconSend.classList.add('hidden');
    iconSpinner.classList.remove('hidden');
  } else {
    submitText.textContent = 'Processar Email';
    iconSpinner.classList.add('hidden');
    iconSend.classList.remove('hidden');
  }
}

function showFilePill(file) {
  if (!file) {
    filePill.classList.add('hidden');
    filePill.innerHTML = '';
    return;
  }
  const sizeKB = Math.round(file.size / 102.4) / 10; // 1 casa
  filePill.className = 'mt-3 flex justify-center';
  filePill.innerHTML = `
    <span class="pill">
      <svg class="w-4 h-4 text-gray-500" viewBox="0 0 24 24" fill="currentColor"><path d="M6 2a2 2 0 00-2 2v16a2 2 0 002 2h9l5-5V4a2 2 0 00-2-2H6zm8 15h5.5L14 22.5V17z"/></svg>
      ${file.name} • ${sizeKB} KB
    </span>`;
  filePill.classList.remove('hidden');
}

function updateLangButtons() {
  if (currentReplyLang === 'pt') {
    btnLangPT.classList.add('bg-gray-100');
    btnLangEN.classList.remove('bg-gray-100');
  } else {
    btnLangEN.classList.add('bg-gray-100');
    btnLangPT.classList.remove('bg-gray-100');
  }
  if (preferredLangInput) preferredLangInput.value = currentReplyLang;
}

function setBadge(category) {
  badge.innerHTML = '';
  const span = document.createElement('span');
  span.className =
    'badge ' + (category === 'Produtivo' ? 'badge-prod' : 'badge-improd');
  span.textContent = category;
  badge.appendChild(span);
}

function ensureHasValidInput() {
  const hasFile = fileInput.files && fileInput.files.length > 0;
  const txt = (emailText.value || '').trim();
  const hasTextMin = txt.length >= 10;
  return hasFile || hasTextMin;
}

async function postWithTimeout(url, body, timeoutMs) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort('timeout'), timeoutMs);
  try {
    const res = await fetch(url, { method: 'POST', body, signal: ctrl.signal });
    return res;
  } finally {
    clearTimeout(id);
  }
}

// ===================== DRAG & DROP ========================
['dragenter', 'dragover'].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.add('ring-2', 'ring-indigo-300');
  }),
);
['dragleave', 'drop'].forEach(evt =>
  dropzone.addEventListener(evt, e => {
    e.preventDefault();
    e.stopPropagation();
    dropzone.classList.remove('ring-2', 'ring-indigo-300');
  }),
);
dropzone.addEventListener('click', () => fileInput.click());
dropzone.addEventListener('drop', e => {
  const f = e.dataTransfer.files?.[0];
  if (!f) return;
  if (!/\.(pdf|txt)$/i.test(f.name)) {
    alert('Envie .pdf ou .txt');
    return;
  }
  const dt = new DataTransfer();
  dt.items.add(f);
  fileInput.files = dt.files;
  showFilePill(f);
});
fileInput.addEventListener('change', () => showFilePill(fileInput.files?.[0]));

// ===================== IDIOMAS ============================
btnLangPT.addEventListener('click', () => {
  currentReplyLang = 'pt';
  userChoseLang = true;
  localStorage.setItem('replyLang', 'pt');
  if (!replyPT) {
    alert('Não há versão em PT desta resposta.');
    return;
  }
  reply.value = replyPT;
  updateLangButtons();
});
btnLangEN.addEventListener('click', () => {
  currentReplyLang = 'en';
  userChoseLang = true;
  localStorage.setItem('replyLang', 'en');
  if (!replyEN) {
    alert(
      'Sem versão em inglês para este resultado (mostrando PT, se disponível).',
    );
    if (replyPT) {
      currentReplyLang = 'pt';
      localStorage.setItem('replyLang', 'pt');
      reply.value = replyPT;
      updateLangButtons();
    }
    return;
  }
  reply.value = replyEN;
  updateLangButtons();
});
updateLangButtons();

// ===================== COPIAR / LIMPAR ====================
copyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(reply.value || '');
    copyState.classList.remove('hidden');
    setTimeout(() => copyState.classList.add('hidden'), 2000);
  } catch {
    alert('Não foi possível copiar.');
  }
});
clearBtn.addEventListener('click', () => {
  form.reset();
  showFilePill(null);
  result.classList.add('hidden');
  resultEmpty.classList.remove('hidden');
  userChoseLang = false;
  // limpa replies pra não “vazar” da submissão anterior
  replyPT = '';
  replyEN = '';
  reply.value = '';
  lastResult = null;
});

// ===================== SUBMIT =============================
form.addEventListener('submit', async e => {
  e.preventDefault();
  if (loading) return;
  if (!ensureHasValidInput()) {
    alert('Envie .pdf/.txt ou cole um texto com pelo menos 10 caracteres.');
    return;
  }
  preferredLangInput.value = userChoseLang ? currentReplyLang || 'pt' : 'auto';

  // limpa estado visual antes de enviar (evita confusão com dados antigos)
  prob.textContent = '—';
  badge.innerHTML = '';
  explain.innerHTML = '';
  preview.innerText = '';
  reply.value = '';
  replyPT = '';
  replyEN = '';
  lastResult = null;

  setLoading(true);
  try {
    const fd = new FormData(form);
    // timeout no fetch para evitar requests pendurados
    const res = await postWithTimeout('/classify', fd, REQUEST_TIMEOUT_MS);
    let data;
    try {
      data = await res.json();
    } catch {
      throw new Error('Resposta inválida do servidor.');
    }

    if (!res.ok || !data.ok) {
      alert((data && data.error) || 'Erro ao processar.');
      return;
    }

    lastResult = data;

    // Mostra o cartão de resultado
    resultEmpty.classList.add('hidden');
    result.classList.remove('hidden');

    // Confiança + badge de categoria
    prob.textContent = (data.probability ?? 0).toFixed(3);
    setBadge(data.category);

    // Pill de subintenção ao lado do chip
    const intent = (data.explanation && data.explanation.intent) || 'OTHER';
    const intentMap = {
      STATUS: 'Status',
      ATTACHMENT: 'Anexo',
      ACCESS: 'Acesso',
      ERROR: 'Erro',
      CLOSURE: 'Encerramento',
      THANKS: 'Agradecimento',
      GREETINGS: 'Saudação',
      SUPPORT: 'Suporte',
      NON_MESSAGE: 'Documento',
      OTHER: 'Geral',
    };
    const intentClassMap = {
      STATUS: 'pill pill-status ml-2',
      ATTACHMENT: 'pill pill-attachment ml-2',
      ACCESS: 'pill pill-access ml-2',
      ERROR: 'pill pill-error ml-2',
      CLOSURE: 'pill pill-closure ml-2',
      THANKS: 'pill pill-thanks ml-2',
      GREETINGS: 'pill pill-greetings ml-2',
      SUPPORT: 'pill pill-support ml-2',
      NON_MESSAGE: 'pill pill-nonmessage ml-2',
      OTHER: 'pill pill-other ml-2',
    };

    const intentPill = document.createElement('span');
    intentPill.className = intentClassMap[intent] || 'pill pill-other ml-2';
    intentPill.textContent = intentMap[intent] || 'Geral';
    badge.appendChild(intentPill);

    // Replies
    replyPT = data.reply_pt || '';
    replyEN = data.reply_en || '';

    // idioma padrão: respeita preferido salvo, senão o que veio do backend
    const preferred = localStorage.getItem('replyLang');
    const defaultLang = (
      preferred ||
      data.reply_lang_default ||
      'pt'
    ).toLowerCase();

    if (defaultLang === 'en' && replyEN) {
      currentReplyLang = 'en';
      reply.value = replyEN;
    } else {
      currentReplyLang = 'pt';
      reply.value = replyPT || replyEN || '';
    }
    localStorage.setItem('replyLang', currentReplyLang);
    updateLangButtons();

    // Explicação
    const feats = data.explanation?.top_features || [];
    const langDetected = (data.explanation?.language || 'pt').toUpperCase();
    const intentLabel = intentMap[intent] || 'Geral';
    explain.innerHTML = `
      <div><strong>Idioma detectado:</strong> ${langDetected}</div>
      <div class="mt-1"><strong>Subintenção:</strong> ${intentLabel}</div>
      <div class="mt-2"><strong>Principais sinais:</strong> <code>${
        feats.length ? feats.join(', ') : 'Nenhum termo de destaque'
      }</code></div>
    `;

    // Prévia
    preview.innerText = data.text_preview || '';
  } catch (err) {
    console.error(err);
    if (err?.name === 'AbortError') {
      alert('Tempo excedido ao processar. Tente novamente.');
    } else {
      alert('Falha na comunicação com o servidor.');
    }
  } finally {
    setLoading(false);
  }
});
