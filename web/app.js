// app.js — Controlador del Dashboard del Monitor del Mercado

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const statusDiv = document.getElementById('ollama-status');
    if (data.ollama_online && data.ollama_model_available) {
      statusDiv.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-slate-300">Ollama: <strong class="text-emerald-400">${data.ollama_model}</strong></span>
      `;
    } else if (data.ollama_online) {
      statusDiv.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-amber-400"></span>
        <span class="text-slate-300">Modelo no instalado: <strong class="text-amber-400">${escapeHtml(data.ollama_model)}</strong></span>
      `;
    } else {
      statusDiv.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-red-400"></span>
        <span class="text-slate-300">Ollama: <strong class="text-red-400">Desconectado</strong></span>
      `;
    }
  } catch (err) {
    console.warn("Error consultando estado:", err);
  }
}

let allReportsCache = [];
let currentReportsTab = 'vigentes';
let activeReportPath = null;
let currentActiveReport = null;
let centralBrainSelection = { engine: 'ollama', model: null };

function parseBrainSelection(value) {
  if (typeof value === 'string' && value.startsWith('ollama|')) {
    return { engine: 'ollama', model: value.slice('ollama|'.length) };
  }
  return { engine: value, model: null };
}

function brainSelectionValue(brain) {
  if (brain?.engine === 'ollama' && brain.model) return `ollama|${brain.model}`;
  return brain?.engine || 'ollama';
}

function updateHeaderEngineStatus() {
  const modeBadge = document.getElementById('mode-badge');
  const engineEl = document.getElementById('scan-engine');
  if (!modeBadge) return;

  const rawVal = engineEl ? engineEl.value : (centralBrainSelection ? brainSelectionValue(centralBrainSelection) : 'ollama|qwen2.5:3b');
  const selection = parseBrainSelection(rawVal);

  if (selection.engine === 'antigravity_cio') {
    modeBadge.className = 'status-chip mode-chip border border-purple-500/40 bg-purple-950/50 text-purple-200';
    modeBadge.innerHTML = 'Motor: <strong class="text-purple-300">🏛️ Antigravity CIO</strong>';
  } else if (selection.engine === 'gemini') {
    modeBadge.className = 'status-chip mode-chip border border-sky-500/40 bg-sky-950/50 text-sky-200';
    modeBadge.innerHTML = 'Motor: <strong class="text-sky-300">☁️ Google Gemini</strong>';
  } else if (selection.engine === 'ollama') {
    const modelName = selection.model || 'qwen2.5:3b';
    modeBadge.className = 'status-chip mode-chip border border-emerald-500/40 bg-emerald-950/50 text-emerald-200';
    modeBadge.innerHTML = `Motor: <strong class="text-emerald-300">🤖 ${escapeHtml(modelName)}</strong>`;
  } else {
    modeBadge.className = 'status-chip mode-chip';
    modeBadge.innerHTML = `Motor: <strong>${escapeHtml(selection.engine)}</strong>`;
  }
}

async function loadBrainModels() {
  const modelsResponse = await fetch('/api/system/models');
  if (!modelsResponse.ok) throw new Error(`HTTP ${modelsResponse.status} cargando los modelos.`);
  const modelsData = await modelsResponse.json();
  const brainResponse = await fetch('/api/system/brain');
  if (!brainResponse.ok) throw new Error(`HTTP ${brainResponse.status} cargando el cerebro central.`);
  const brain = await brainResponse.json();
  centralBrainSelection = { engine: brain.engine, model: brain.model || null };

  const select = document.getElementById('scan-engine');
  if (!select) return;
  const models = Array.isArray(modelsData.models) ? modelsData.models : [];
  const current = brainSelectionValue(centralBrainSelection);
  if (centralBrainSelection.engine === 'ollama' && centralBrainSelection.model && !models.includes(centralBrainSelection.model)) {
    models.push(centralBrainSelection.model);
  }

  const unavailableOption = new Option('🤖 Ollama · Selecciona modelo', 'ollama|');
  unavailableOption.disabled = true;
  select.replaceChildren(
    ...[...new Set(models)].sort((a, b) => a.localeCompare(b)).map(model => new Option(`🤖 Ollama · ${model}`, `ollama|${model}`)),
    new Option('☁️ Google Gemini', 'gemini'),
    new Option('🏛️ Antigravity CIO (recopilar candidatos)', 'antigravity_cio'),
    new Option('⚙️ Matemático Local (solo Trading)', 'local')
  );
  if (!models.length) select.add(unavailableOption, 0);
  const localOption = Array.from(select.options).find(option => option.value === 'local');
  if (localOption) localOption.disabled = true;
  select.value = Array.from(select.options).some(option => option.value === current)
    ? current
    : (models.length ? `ollama|${models[0]}` : 'gemini');
  if (!modelsData.available) console.warn(modelsData.error || 'Ollama no disponible.');
  updateHeaderEngineStatus();
}

async function saveBrainSelection(value) {
  const selection = parseBrainSelection(value);
  if (selection.engine === 'ollama' && !selection.model) return;
  const response = await fetch('/api/system/brain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(selection),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.error || `HTTP ${response.status} guardando el cerebro.`);
  }
  centralBrainSelection = selection;
  updateHeaderEngineStatus();
  await syncRadarConfigToServer();
}

function startBrainSyncPolling() {
  loadBrainModels().catch(error => console.warn('No se pudo cargar el cerebro central:', error));
  setInterval(async () => {
    try {
      const response = await fetch('/api/system/brain');
      if (!response.ok) return;
      const brain = await response.json();
      const value = brainSelectionValue(brain);
      const select = document.getElementById('scan-engine');
      if (select && !Array.from(select.options).some(option => option.value === value)) {
        await loadBrainModels();
      } else if (select) {
        select.value = value;
      }
      centralBrainSelection = { engine: brain.engine, model: brain.model || null };
      updateHeaderEngineStatus();
    } catch (error) {
      console.warn('No se pudo sincronizar el cerebro central:', error);
    }
  }, 8000);
}
let currentInjectPayload = null;
let radarTimerInterval = null;
let radarCountdownSeconds = 0;

function filterReportsTab(tab) {
  currentReportsTab = tab;
  const btnVig = document.getElementById('filter-vigentes-btn');
  const btnTod = document.getElementById('filter-todos-btn');

  if (tab === 'vigentes') {
    btnVig.classList.add('is-active');
    btnTod.classList.remove('is-active');
  } else {
    btnTod.classList.add('is-active');
    btnVig.classList.remove('is-active');
  }

  renderReportsListButtons();
}

function renderReportsListButtons() {
  const container = document.getElementById('reports-list');
  container.innerHTML = '';

  const listToRender = currentReportsTab === 'vigentes'
    ? allReportsCache.filter(r => r.es_vigente)
    : allReportsCache;

  if (!listToRender || listToRender.length === 0) {
    const msg = currentReportsTab === 'vigentes'
      ? 'No hay reportes vigentes de las últimas 48h. Haz clic en "Historial Completo" para ver anteriores.'
      : 'No hay reportes generados aún en el historial.';
    container.innerHTML = `<span class="text-slate-500 italic text-xs py-1">${msg}</span>`;
    return;
  }

  listToRender.forEach(r => {
    const targetKey = r.rel_path || r.name;
    const isSelected = activeReportPath && (
      activeReportPath === targetKey ||
      activeReportPath.endsWith(r.name) ||
      targetKey.endsWith(activeReportPath)
    );

    const btn = document.createElement('button');
    btn.setAttribute('data-path', targetKey);
    const isVigenteDot = r.es_vigente
      ? '<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block shadow-[0_0_6px_rgba(52,211,153,0.8)]"></span>'
      : '<span class="w-2 h-2 rounded-full bg-slate-600 inline-block"></span>';
    const isCIO = r.motor_evaluador === 'Antigravity CIO' || (r.name && r.name.includes('CIO'));
    const modeIcon = isCIO ? '🏛️' : (r.modo === 'BUSQUEDA_ESPECIFICA' ? '🎯' : '🛰️');
    const folderLabel = r.date_folder && r.date_folder !== 'General' ? `[${r.date_folder}] ` : '';
    const ageLabel = r.horas_antiguedad !== undefined ? ` (${r.horas_antiguedad}h)` : '';

    const baseClass = isSelected
      ? 'active-report'
      : '';

    btn.className = baseClass;
    btn.innerHTML = `${isVigenteDot} <span>${modeIcon} ${escapeHtml(folderLabel + r.name)}${ageLabel}</span>`;
    btn.onclick = () => loadReportContent(targetKey, btn);
    container.appendChild(btn);
  });
}

async function loadReportsList() {
  try {
    const res = await fetch('/api/reports');
    allReportsCache = await res.json();

    const vigentes = allReportsCache.filter(r => r.es_vigente);
    const countVig = document.getElementById('count-vigentes');
    const countTod = document.getElementById('count-todos');
    if (countVig) countVig.innerText = vigentes.length;
    if (countTod) countTod.innerText = allReportsCache.length;

    renderReportsListButtons();
  } catch (err) {
    console.error("Error cargando lista de reportes:", err);
  }
}

async function loadLatestReport() {
  try {
    const res = await fetch('/api/reports/latest');
    if (!res.ok) {
      document.getElementById('executive-verdict').innerText = "No se ha generado ningún reporte todavía. Haz clic en 'Escanear Mercado Ahora'.";
      const banner = document.getElementById('report-vigencia-banner');
      if (banner) banner.classList.add('hidden');
      return;
    }
    const reportData = await res.json();
    activeReportPath = reportData.rel_path || reportData.name;
    renderReport(reportData);
    updateReportBanner(reportData);
    highlightActiveButton(activeReportPath);
  } catch (err) {
    console.error("Error cargando último reporte:", err);
  }
}

async function loadReportContent(targetPath, clickedBtn = null) {
  try {
    activeReportPath = targetPath;
    highlightActiveButton(targetPath);

    const res = await fetch(`/api/reports/${encodeURIComponent(targetPath)}`);
    if (!res.ok) {
      throw new Error(`Reporte no encontrado (${res.status})`);
    }
    const reportData = await res.json();
    renderReport(reportData);
    updateReportBanner(reportData);

    // Desplazamiento suave directo hacia las Conclusiones Internas
    const box = document.getElementById('conclusions-box');
    if (box) {
      box.scrollIntoView({ behavior: 'smooth', block: 'center' });
      box.classList.add('ring-2', 'ring-amber-400', 'transition-all');
      setTimeout(() => {
        box.classList.remove('ring-2', 'ring-amber-400');
      }, 1600);
    }
  } catch (err) {
    console.error("Error cargando reporte:", err);
    alert("Error al cargar el contenido del informe: " + err.message);
  }
}

function updateReportBanner(reportData) {
  const banner = document.getElementById('report-vigencia-banner');
  const titleEl = document.getElementById('report-active-title');
  const vigBadge = document.getElementById('report-vigencia-badge');
  const modeBadge = document.getElementById('report-mode-badge');
  const folderBadge = document.getElementById('report-folder-badge');
  const ageText = document.getElementById('report-age-text');

  if (banner) {
    banner.classList.remove('hidden');
    if (titleEl) {
      titleEl.innerText = reportData.name || 'Reporte';
    }
    if (vigBadge) {
      if (reportData.es_vigente) {
        vigBadge.className = 'px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-800';
        vigBadge.innerText = '🟢 VIGENTE (Activo)';
      } else {
        vigBadge.className = 'px-2 py-0.5 rounded text-[11px] font-bold bg-slate-900 text-slate-400 border border-slate-700';
        vigBadge.innerText = '⚪ HISTÓRICO (Caducado)';
      }
    }

    if (modeBadge) {
      modeBadge.innerText = reportData.modo_escaneo === 'BUSQUEDA_ESPECIFICA'
        ? '🎯 Búsqueda Específica'
        : '🛰️ Radar Autónomo';
    }

    const engineBadge = document.getElementById('report-engine-badge');
    if (engineBadge) {
      const isCIO = reportData.motor_evaluador === 'Antigravity CIO' || (reportData.name && reportData.name.includes('CIO'));
      if (isCIO) {
        engineBadge.className = 'px-2 py-0.5 rounded text-[11px] font-bold bg-purple-950 text-purple-300 border border-purple-800';
        engineBadge.innerText = '🏛️ Antigravity CIO';
      } else {
        engineBadge.className = 'px-2 py-0.5 rounded text-[11px] font-bold bg-blue-950 text-blue-300 border border-blue-800';
        engineBadge.innerText = '🤖 Ollama Local';
      }
    }

    if (folderBadge) {
      folderBadge.innerText = `Carpeta: ${reportData.date_folder || 'Raíz'}`;
    }

    if (ageText) {
      ageText.innerText = reportData.horas_antiguedad !== undefined
        ? `Emitido hace ${reportData.horas_antiguedad} h`
        : '';
    }
  }
}

function highlightActiveButton(targetPath) {
  if (!targetPath) return;
  document.querySelectorAll('#reports-list button').forEach(b => {
    const btnPath = b.getAttribute('data-path');
    b.classList.toggle('active-report', Boolean(btnPath && (
      btnPath === targetPath || btnPath.endsWith(targetPath) || targetPath.endsWith(btnPath)
    )));
  });
}

async function deleteActiveReport() {
  if (!activeReportPath) {
    alert("No hay ningún informe seleccionado para eliminar.");
    return;
  }

  const titleEl = document.getElementById('report-active-title');
  const displayName = titleEl ? titleEl.innerText : activeReportPath;

  const confirmed = confirm(
    `¿Estás seguro de que deseas eliminar permanentemente el informe "${displayName}"?\n\nEsta acción borrará el archivo físico del disco.`
  );
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/reports/${encodeURIComponent(activeReportPath)}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || `Error ${res.status}`);
    }

    alert(`El informe "${displayName}" fue eliminado exitosamente.`);
    activeReportPath = null;
    await loadReportsList();
    await loadLatestReport();
  } catch (err) {
    console.error("Error eliminando reporte:", err);
    alert("No se pudo eliminar el informe: " + err.message);
  }
}

async function syncRadarConfigToServer() {
  const select = document.getElementById('radar-interval');
  const engineEl = document.getElementById('scan-engine');
  const autoinjectEl = document.getElementById('radar-autoinject');
  const intervalMin = select ? parseInt(select.value, 10) || 0 : 0;
  const selection = parseBrainSelection(engineEl ? engineEl.value : 'ollama|');
  const autoInject = autoinjectEl ? Boolean(autoinjectEl.checked) : false;

  try {
    await fetch('/api/cio/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        interval_minutes: intervalMin,
        engine: selection.engine,
        model: selection.model,
        auto_inject: autoInject,
      })
    });
  } catch (err) {
    console.warn("No se pudo sincronizar radar_config con el servidor:", err);
  }
}

function toggleContinuousRadar(skipSync = false) {
  const select = document.getElementById('radar-interval');
  const badge = document.getElementById('radar-countdown-badge');
  const intervalMin = parseInt(select.value, 10);

  if (!skipSync) {
    syncRadarConfigToServer();
  }

  if (radarTimerInterval) {
    clearInterval(radarTimerInterval);
    radarTimerInterval = null;
  }

  if (intervalMin <= 0) {
    if (badge) badge.classList.add('hidden');
    return;
  }

  if (badge) badge.classList.remove('hidden');
  radarCountdownSeconds = intervalMin * 60;
  updateRadarCountdownDisplay();

  radarTimerInterval = setInterval(() => {
    radarCountdownSeconds--;
    if (radarCountdownSeconds <= 0) {
      radarCountdownSeconds = intervalMin * 60;
      // Disparar escaneo radar en segundo plano sin bloquear al usuario
      triggerScan(true);
    }
    updateRadarCountdownDisplay();
  }, 1000);
}

function updateRadarCountdownDisplay() {
  const el = document.getElementById('radar-countdown-text');
  if (!el) return;
  const m = Math.floor(radarCountdownSeconds / 60);
  const s = radarCountdownSeconds % 60;
  el.innerText = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}


function renderReport(report) {
  currentActiveReport = report;
  document.getElementById('last-scan-time').innerText = `Reporte: ${report.name || 'Reciente'}`;

  // 1. Conclusiones Internas y Directiva
  const directiveBadge = document.getElementById('report-directive-badge');
  const directiveText = document.getElementById('report-directive-text');
  if (directiveBadge && directiveText) {
    if (report.directiva_personalizada) {
      directiveText.innerText = report.directiva_personalizada;
      directiveBadge.classList.remove('hidden');
    } else {
      directiveBadge.classList.add('hidden');
    }
  }

  const verdictEl = document.getElementById('executive-verdict');
  verdictEl.innerText = report.sintesis_ejecutiva || "Sin veredicto consolidado disponible.";

  const stepsEl = document.getElementById('step-deductions');
  stepsEl.innerHTML = '';
  if (report.conclusiones_internas && report.conclusiones_internas.length > 0) {
    report.conclusiones_internas.forEach((c, idx) => {
      const item = document.createElement('div');
      item.innerHTML = `<span class="text-amber-500 font-bold">Etapa ${idx + 1}:</span> ${escapeHtml(c)}`;
      stepsEl.appendChild(item);
    });
  } else {
    stepsEl.innerHTML = '<div class="text-slate-500 italic">No se registraron etapas intermedias en este reporte.</div>';
  }


  // 2. Fichas de Oportunidad
  const oppContainer = document.getElementById('opportunities-container');
  oppContainer.innerHTML = '';
  const opportunities = report.oportunidades || [];
  document.getElementById('opp-count-badge').innerText = `${opportunities.length} detectadas`;

  if (opportunities.length === 0) {
    oppContainer.innerHTML = `
      <div class="col-span-full p-6 rounded-xl border border-dashed border-slate-800 text-center text-slate-400 text-xs font-mono">
        No se detectaron oportunidades validadas en este reporte.<br>
        <span class="text-slate-500">Esto no implica que todas las noticias sean ruido ni que el análisis esté completo.</span>
      </div>
    `;
  } else {
    opportunities.forEach((card, idx) => {
      oppContainer.appendChild(createOpportunityCard(card, idx));
    });
  }

  // 3. Fichas de Peligro / Trampa
  const dangerContainer = document.getElementById('dangers-container');
  dangerContainer.innerHTML = '';
  const dangers = report.alertas_peligro || [];
  document.getElementById('danger-count-badge').innerText = `${dangers.length} activas`;

  if (dangers.length === 0) {
    dangerContainer.innerHTML = `
      <div class="col-span-full p-4 rounded-xl border border-dashed border-slate-800/80 text-center text-slate-500 text-xs font-mono">
        No se registraron trampas de euforia activa en las fuentes escaneadas.
      </div>
    `;
  } else {
    dangers.forEach((card, idx) => {
      dangerContainer.appendChild(createDangerCard(card, idx));
    });
  }

  // 4. Hoja de Ruta del Operador Novato
  const guia = report.guia_operador;
  const semBadge = document.getElementById('operator-semaphore-badge');
  const semText = document.getElementById('operator-semaphore-text');
  const mainMsg = document.getElementById('operator-main-message');
  const checkList = document.getElementById('operator-checklist');
  const riskRule = document.getElementById('operator-risk-rule');
  const psychoAdv = document.getElementById('operator-psycho-advice');

  // Elementos de la tarjeta de Horarios de Mercado
  const mktBadge = document.getElementById('operator-market-badge');
  const mktDot = document.getElementById('operator-market-dot');
  const mktStatusText = document.getElementById('operator-market-status-text');
  const schedHours = document.getElementById('operator-schedule-hours');
  const nextOpen = document.getElementById('operator-next-open');
  const botWarningText = document.getElementById('operator-bot-warning-text');

  if (guia) {
    if (semText) semText.innerText = guia.estado_semaforo;
    if (semBadge) {
      if (guia.estado_semaforo.includes('OPERAR CON')) {
        semBadge.className = 'semaphore-badge is-open';
      } else if (guia.estado_semaforo.includes('PELIGRO')) {
        semBadge.className = 'semaphore-badge is-danger';
      }
    }
    let fullInstruction = guia.mensaje_principal || '';
    if (guia.mercado_abierto === false && !fullInstruction.includes('CERRADO') && !fullInstruction.includes('ATENCIÓN HORARIO')) {
      fullInstruction += ` El mercado figura cerrado (${guia.horario_mercado || 'horario no disponible'}); el monitor no transmite ni ejecuta órdenes.`;
    } else if (guia.mercado_abierto === true && !fullInstruction.includes('ABIERTO') && !fullInstruction.includes('EN VIVO')) {
      fullInstruction += ` El mercado figura en horario de sesión (${guia.horario_mercado || 'horario oficial'}); el monitor no transmite ni ejecuta órdenes.`;
    }
    if (mainMsg) mainMsg.innerText = fullInstruction;

    // Renderizar Horarios y Estado de Mercado en Tiempo Real
    const isMktOpen = guia.mercado_abierto === true;
    if (mktStatusText) {
      mktStatusText.innerText = guia.estado_texto || (isMktOpen ? '🟢 MERCADO ABIERTO' : '🔴 MERCADO CERRADO');
    }
    if (mktDot) {
      mktDot.className = isMktOpen ? 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse' : 'w-2 h-2 rounded-full bg-red-400';
    }
    if (mktBadge) {
      mktBadge.className = isMktOpen ? 'market-badge is-open' : 'market-badge is-danger';
    }
    if (schedHours) {
      schedHours.innerText = `${guia.categoria_mercado ? guia.categoria_mercado + ' • ' : ''}${guia.horario_mercado || 'Lunes a Viernes de 10:30 AM a 17:00 PM ARG'}`;
    }
    if (nextOpen) {
      nextOpen.innerText = guia.proxima_apertura || (isMktOpen ? 'Sesión en curso' : 'Próxima apertura comercial');
      nextOpen.className = isMktOpen ? 'text-emerald-400 font-bold' : 'text-amber-400 font-bold';
    }
    if (botWarningText) {
      botWarningText.innerText = guia.recomendacion_horaria || (
        isMktOpen
          ? 'El horario de mercado se muestra solo como contexto; el monitor no transmite ni ejecuta órdenes.'
          : 'El mercado figura cerrado. El monitor no transmite ni ejecuta órdenes.'
      );
    }

    if (checkList) {
      checkList.innerHTML = '';
      if (guia.checklist_pasos && guia.checklist_pasos.length > 0) {
        guia.checklist_pasos.forEach(paso => {
          const item = document.createElement('div');
          item.className = 'p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-xs flex items-start gap-2';
          item.innerHTML = `<span class="text-cyan-400 font-bold shrink-0">✔</span> <span>${escapeHtml(paso)}</span>`;
          checkList.appendChild(item);
        });
      }
    }
    if (riskRule) riskRule.innerText = guia.regla_gestion_riesgo;
    if (psychoAdv) psychoAdv.innerText = guia.consejo_psicologico;
  } else {
    if (semText) semText.innerText = 'No incluida en el reporte';
    if (semBadge) semBadge.className = 'semaphore-badge';
    if (mainMsg) mainMsg.innerText = 'Este reporte no contiene una guía operativa; no se generaron instrucciones automáticamente.';
    if (checkList) checkList.innerHTML = '';
    if (riskRule) riskRule.innerText = '';
    if (psychoAdv) psychoAdv.innerText = '';
    if (mktStatusText) mktStatusText.innerText = 'Estado no incluido';
    if (mktDot) mktDot.className = 'w-2 h-2 rounded-full bg-slate-600';
    if (mktBadge) mktBadge.className = 'market-badge';
    if (schedHours) schedHours.innerText = 'No disponible en este reporte';
    if (nextOpen) {
      nextOpen.innerText = 'No disponible';
      nextOpen.className = 'text-slate-400';
    }
    if (botWarningText) botWarningText.innerText = 'El monitor es informativo y no transmite ni ejecuta órdenes.';
  }
}

function copyMacroInstruction() {
  const mainMsg = document.getElementById('operator-main-message');
  const btnText = document.getElementById('copy-macro-text');
  if (!mainMsg) return;

  const textToCopy = mainMsg.innerText;
  navigator.clipboard.writeText(textToCopy).then(() => {
    if (btnText) {
      const orig = btnText.innerText;
      btnText.innerText = '¡Copiado!';
      setTimeout(() => {
        btnText.innerText = orig;
      }, 2000);
    }
  }).catch(() => {
    // Fallback para navegadores antiguos
    const textarea = document.createElement('textarea');
    textarea.value = textToCopy;
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    if (btnText) {
      const orig = btnText.innerText;
      btnText.innerText = '¡Copiado!';
      setTimeout(() => {
        btnText.innerText = orig;
      }, 2000);
    }
  });
}

function renderCardQuantMetrics(card) {
  const metrics = [
    ['RSI(14)', card.rsi_14, ''],
    ['Z-Score(20)', card.z_score_20, ''],
    ['% vs 52w High', card.pct_from_52w_high, '%'],
    ['EMA200', card.ema_200, ''],
    ['ATR%', card.atr_pct, '%'],
    ['RVOL', card.rvol_20, 'x']
  ];
  return metrics
    .filter(([, value]) => value !== undefined && value !== null && value !== '')
    .map(([label, value, suffix]) => `<span class="quant-pill"><strong>${label}</strong> ${escapeHtml(value)}${suffix}</span>`)
    .join('');
}

function createOpportunityCard(card, oppIndex = 0) {
  const div = document.createElement('article');
  div.className = 'trade-ticket';
  const metrics = renderCardQuantMetrics(card);
  const ratio = card.ratio_riesgo_beneficio == null
    ? 'R/B N/D'
    : `R/B 1:${escapeHtml(card.ratio_riesgo_beneficio)}`;
  const score = card.score_asimetria == null ? 'N/D' : escapeHtml(card.score_asimetria);
  div.innerHTML = `
    <header class="ticket-header">
      <div class="ticket-identity">
        <div class="ticket-ticker">${escapeHtml(card.ticker || '—')} <span class="ticket-tag">LONG / VALOR</span></div>
        <div class="ticket-name">${escapeHtml(card.asset_name || 'Activo sin nombre')}</div>
      </div>
      <div class="ticket-score"><span>${score}/10</span><span>${ratio}</span></div>
    </header>
    <div class="ticket-levels">
      <div class="ticket-level"><small>ENTRADA</small><strong>${escapeHtml(card.nivel_entrada_sugerido || 'N/D')}</strong></div>
      <div class="ticket-level stop"><small>STOP LOSS · −2× ATR</small><strong>${escapeHtml(card.stop_loss_sugerido || 'N/D')}</strong></div>
      <div class="ticket-level target"><small>TARGET</small><strong>${escapeHtml(card.target_proyectado || 'N/D')}</strong></div>
    </div>
    ${metrics ? `<div class="ticket-metrics">${metrics}</div>` : ''}
    <div class="ticket-detail"><h4>Tesis contrarian</h4><p>${escapeHtml(card.tesis_contrarian || 'No incluida en el reporte')}</p></div>
    <div class="ticket-detail catalyst"><h4>Catalizador</h4><p>${escapeHtml(card.catalizador_detonante || 'No incluido en el reporte')}</p></div>
    <div class="ticket-detail support"><h4>Soporte secular</h4><p>${escapeHtml(card.soporte_secular || 'No incluido en el reporte')}</p></div>
    <div class="ticket-footer">
      <span>${escapeHtml(card.horizonte_temporal || 'Horizonte no informado')}</span>
      <span>${escapeHtml(card.sentimiento_mercado || 'Sesgo contrarian')}</span>
    </div>
    <button onclick="openInjectModalWithCardIndex(${oppIndex})" class="inject-button ticket-inject">
      ↗ Inyectar ${escapeHtml(card.ticker || 'activo')} a Trading Ollama
    </button>
  `;
  return div;
}

function createDangerCard(card, dangerIndex) {
  const div = document.createElement('article');
  div.className = 'trade-ticket danger-ticket';
  const metrics = renderCardQuantMetrics(card);
  const ratio = card.ratio_riesgo_beneficio == null
    ? 'R/B N/D'
    : `R/B 1:${escapeHtml(card.ratio_riesgo_beneficio)}`;
  const score = card.score_asimetria == null ? 'N/D' : escapeHtml(card.score_asimetria);
  div.innerHTML = `
    <header class="ticket-header">
      <div class="ticket-identity">
        <div class="ticket-ticker">${escapeHtml(card.ticker || '—')} <span class="ticket-tag">RIESGO / EUFORIA</span></div>
        <div class="ticket-name">${escapeHtml(card.asset_name || 'Activo sin nombre')}</div>
      </div>
      <div class="ticket-score"><span>${score}/10</span><span>${ratio}</span></div>
    </header>
    <div class="ticket-levels">
      <div class="ticket-level"><small>REFERENCIA</small><strong>${escapeHtml(card.nivel_entrada_sugerido || 'N/D')}</strong></div>
      <div class="ticket-level stop"><small>INVALIDACIÓN</small><strong>${escapeHtml(card.stop_loss_sugerido || 'N/D')}</strong></div>
      <div class="ticket-level target"><small>OBJETIVO</small><strong>${escapeHtml(card.target_proyectado || 'N/D')}</strong></div>
    </div>
    ${metrics ? `<div class="ticket-metrics">${metrics}</div>` : ''}
    <div class="ticket-detail"><h4>Señal de peligro</h4><p>${escapeHtml(card.tesis_contrarian || 'No incluida en el reporte')}</p></div>
    <div class="ticket-detail catalyst"><h4>Catalizador de euforia</h4><p>${escapeHtml(card.catalizador_detonante || 'No incluido en el reporte')}</p></div>
    <div class="ticket-detail support"><h4>Recomendación</h4><p>${escapeHtml(card.soporte_secular || 'Reducir exposición y evitar perseguir el precio.')}</p></div>
    <div class="ticket-footer"><span>${escapeHtml(card.horizonte_temporal || 'Riesgo de reversión')}</span><span>Sesgo defensivo</span></div>
    <button onclick="openInjectDangerCard(${dangerIndex})" class="inject-button ticket-inject">! Enviar alerta a Trading Ollama</button>
  `;
  return div;
}

function setCustomDirective(text) {
  const input = document.getElementById('scan-custom-directive');
  if (input) {
    input.value = text;
    input.focus();
  }
}

async function triggerScan(isAutomatic = false) {
  const btn = document.getElementById('btn-scan');
  const spinner = document.getElementById('scan-spinner');
  const btnText = document.getElementById('scan-btn-text');
  const category = document.getElementById('scan-category').value;
  const engineEl = document.getElementById('scan-engine');
  const selection = parseBrainSelection(engineEl ? engineEl.value : 'ollama|');
  const engine = selection.engine;

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btnText.innerText = engine === 'antigravity_cio'
    ? (isAutomatic ? "Radar CIO recopilando..." : "Recopilando candidatos para CIO...")
    : (isAutomatic ? "Radar continuo escaneando..." : "Escaneando mercado e IA...");

  try {
    if (engine === 'local') {
      throw new Error('El motor matemático local solo está disponible en Trading Ollama.');
    }

    if (engine === 'antigravity_cio') {
      const params = new URLSearchParams();
      if (category) params.append('category', category);
      if (customDirective) params.append('directive', customDirective);

      const res = await fetch(`/api/cio/candidates?${params.toString()}`);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.error || `Error HTTP ${res.status}`);
      }
      const candidates = await res.json();
      const tickersStr = candidates.tickers && candidates.tickers.length > 0
        ? candidates.tickers.join(', ')
        : 'Ninguno';

      if (!isAutomatic) {
        const msg = `🏛️ ¡Candidatos recopilados con éxito para Antigravity CIO!\n\n` +
          `• Eventos ingestados: ${candidates.news_count}\n` +
          `• Activos identificados: ${candidates.tickers ? candidates.tickers.length : 0} (${tickersStr})\n\n` +
          `El agente Antigravity CIO puede evaluar estos datos con las Tres Verdades Contraintuitivas y publicar el informe oficial vía POST /api/cio/publish.\n\n` +
          `💡 Pídele a Antigravity en el chat:\n"Ejecuta la auditoría CIO del Monitor del Mercado con los candidatos recolectados"`;
        alert(msg);
      } else {
        console.log("Radar CIO: candidatos recopilados para Antigravity CIO.", candidates);
      }
      return;
    }

    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: category || null,
        custom_directive: customDirective || null,
        engine,
        model: selection.model,
      })
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      throw new Error(errorData.error || `Error HTTP ${res.status}`);
    }
    const result = await res.json();
    await loadReportsList();
    await loadLatestReport();

    // Auto-transmisión desatendida a Trading Ollama si la casilla está activa
    const autoinjectEl = document.getElementById('radar-autoinject');
    if (autoinjectEl && autoinjectEl.checked) {
      await autoInjectReport(result, isAutomatic);
    }

    if (!isAutomatic) {
      alert("¡Escaneo completado con éxito! Se han actualizado las fichas y conclusiones.");
    } else {
      console.log("Radar continuo: nuevo escaneo completado y archivado.");
    }
  } catch (err) {
    if (!isAutomatic) {
      alert("Error al ejecutar escaneo: " + err.message);
    } else {
      console.warn("Radar continuo error:", err);
    }

  } finally {
    btn.disabled = false;
    spinner.classList.add('hidden');
    btnText.innerText = "Iniciar escaneo";
  }
}

function setAndInspectTicker(symbol) {
  const tickerInput = document.getElementById('ticker-input');
  if (tickerInput) {
    tickerInput.value = symbol;
    inspectTicker();
  }
}

async function inspectTicker() {
  const tickerInput = document.getElementById('ticker-input');
  const resultDiv = document.getElementById('ticker-result');
  const symbol = tickerInput.value.trim().toUpperCase();

  if (!symbol) {
    resultDiv.innerHTML = '<span class="text-yellow-400">Por favor ingresa un símbolo (ej. CL=F).</span>';
    return;
  }

  resultDiv.innerHTML = '<span class="text-slate-400 animate-pulse">Consultando yfinance...</span>';

  try {
    const res = await fetch(`/api/ticker?symbol=${encodeURIComponent(symbol)}`);
    if (!res.ok) throw new Error("Ticker no encontrado");
    const data = await res.json();

    const changePositive = data.change_pct_24h >= 0;
    const metrics = [
      ['RSI(14)', data.rsi_14, '', data.rsi_14 < 30 ? 'emerald' : (data.rsi_14 > 70 ? 'rose' : '')],
      ['Z-Score(20)', data.z_score_20 === undefined || data.z_score_20 === null
        ? data.z_score_20
        : `${data.z_score_20 > 0 ? '+' : ''}${data.z_score_20}`, '', 'cyan'],
      ['% vs 52w High', data.pct_from_52w_high, '%', ''],
      ['EMA200', data.ema_200, '', ''],
      ['ATR%', data.atr_pct, '%', ''],
      ['RVOL', data.rvol_20, 'x', '']
    ];
    const metricPills = metrics
      .filter(([, value]) => value !== undefined && value !== null && value !== '')
      .map(([label, value, suffix, tone]) => `<span class="metric-pill ${tone}">${label} <strong>${escapeHtml(value)}${suffix}</strong></span>`)
      .join('');
    const schedule = data.schedule ? `
      <div class="quote-schedule">
        <span>${escapeHtml(data.schedule.estado_texto)} · ${escapeHtml(data.schedule.categoria)} (${escapeHtml(data.schedule.horario_argentina)})</span>
        <strong>${escapeHtml(data.schedule.proxima_apertura)}</strong>
      </div>` : '';

    resultDiv.innerHTML = `
      <div class="quote-main">
        <div><div class="quote-ticker">${escapeHtml(data.ticker)}</div>
          <div class="quote-change ${changePositive ? 'emerald' : 'rose'}">${changePositive ? '+' : ''}${escapeHtml(data.change_pct_24h)}% · 24H</div>
        </div>
        <div class="quote-price">${escapeHtml(data.current_price)} <small>${escapeHtml(data.currency)}</small></div>
      </div>
      <div class="quote-range">Rango 52 semanas · Máximo ${escapeHtml(data.pct_from_52w_high ?? 'N/D')}% · Mínimo +${escapeHtml(data.pct_from_52w_low ?? 'N/D')}%</div>
      ${metricPills ? `<div class="quant-metrics">${metricPills}</div>` : ''}
      ${schedule}
    `;
  } catch (err) {
    resultDiv.innerHTML = `<span class="text-red-400">No se encontraron datos para "${symbol}".</span>`;
  }
}

function escapeHtml(text) {
  if (text === null || text === undefined) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// --- Puente de Inyección a Trading Ollama (Puerto 18767) ---

const NON_OPERABLE_TICKERS = new Set(["GENERAL", "DX-Y.NYB", "DXY", "NULL", "NONE", "N/A"]);

function isOperableTicker(ticker) {
  if (!ticker || typeof ticker !== "string") return false;
  const cleaned = ticker.trim().toUpperCase();
  if (!cleaned || NON_OPERABLE_TICKERS.has(cleaned)) return false;
  return /^[A-Za-z0-9_=./^\-]+$/.test(cleaned);
}

function buildQuantitativeDirectiveText(card, fallbackText = "") {
  if (!card) return fallbackText;
  const quantMetrics = [];
  if (card.rsi_14 !== undefined && card.rsi_14 !== null) {
    quantMetrics.push(`RSI: ${card.rsi_14}`);
  } else {
    quantMetrics.push(`RSI: N/D`);
  }
  if (card.z_score_20 !== undefined && card.z_score_20 !== null) {
    quantMetrics.push(`Z-Score: ${card.z_score_20 > 0 ? '+' : ''}${card.z_score_20}`);
  } else {
    quantMetrics.push(`Z-Score: N/D`);
  }
  if (card.pct_from_52w_high !== undefined && card.pct_from_52w_high !== null) {
    quantMetrics.push(`% vs 52w High: ${card.pct_from_52w_high}%`);
  } else {
    quantMetrics.push(`% vs 52w High: N/D`);
  }
  if (card.ema_200 !== undefined && card.ema_200 !== null) {
    quantMetrics.push(`EMA200: ${card.ema_200}`);
  }
  if (card.atr_pct !== undefined && card.atr_pct !== null) {
    quantMetrics.push(`ATR%: ${card.atr_pct}%`);
  }
  if (card.rvol_20 !== undefined && card.rvol_20 !== null) {
    quantMetrics.push(`RVOL: ${card.rvol_20}x`);
  }

  const parts = [`[${quantMetrics.join(" | ")}]`];
  if (card.tesis_contrarian) {
    parts.push(`Tesis Contrarian: ${card.tesis_contrarian}`);
  } else if (fallbackText) {
    parts.push(`Tesis Contrarian: ${fallbackText}`);
  }
  if (card.nivel_entrada_sugerido) parts.push(`Entrada: ${card.nivel_entrada_sugerido}`);
  if (card.stop_loss_sugerido) parts.push(`SL: ${card.stop_loss_sugerido}`);
  if (card.target_proyectado) parts.push(`TP: ${card.target_proyectado}`);
  if (card.ratio_riesgo_beneficio) parts.push(`R/B: 1:${card.ratio_riesgo_beneficio}`);
  if (card.horizonte_temporal) parts.push(`Horizonte: ${card.horizonte_temporal}`);
  return parts.join(" | ");
}

function openInjectModal(card = null) {
  const modal = document.getElementById('inject-modal');
  if (!modal) return;

  // Si no se pasó una tarjeta específica, buscar en el reporte activo
  if (!card && currentActiveReport) {
    if (currentActiveReport.oportunidades && currentActiveReport.oportunidades.length > 0) {
      card = currentActiveReport.oportunidades.find(c => isOperableTicker(c.ticker)) || currentActiveReport.oportunidades[0];
    } else if (currentActiveReport.alertas_peligro && currentActiveReport.alertas_peligro.length > 0) {
      card = currentActiveReport.alertas_peligro.find(c => isOperableTicker(c.ticker)) || currentActiveReport.alertas_peligro[0];
    }
  }

  let asset = "GENERAL";
  let type = "Oportunidad";
  let confidence = 85;
  let text = "";
  let marketStatus = "Verificando...";
  let isMarketOpen = false;

  if (card) {
    asset = card.ticker || "GENERAL";
    type = card.tipo === 'Trampa de Mercado / Peligro' ? 'Peligro' : 'Oportunidad';
    confidence = Math.min(100, Math.max(0, Math.round((card.score_asimetria || 8) * 10)));
    text = buildQuantitativeDirectiveText(card);

    if (card.horario_mercado) {
      isMarketOpen = card.mercado_abierto;
      marketStatus = isMarketOpen 
        ? `🟢 ABIERTO (${card.horario_mercado})`
        : `🔴 CERRADO (${card.horario_mercado} - Próxima apertura: ${card.proxima_apertura || 'oficial'})`;
    }
  } else if (currentActiveReport) {
    const guia = currentActiveReport.guia_operador;
    if (guia) {
      type = guia.estado_semaforo === 'ALERTA DE PELIGRO' ? 'Peligro' : 'Neutral';
      text = guia.mensaje_principal || "Semáforo: ESPERAR / NO OPERAR. Sin asimetrías claras hoy.";
      if (guia.ticker_referencia) asset = guia.ticker_referencia;
      isMarketOpen = guia.mercado_abierto;
      marketStatus = isMarketOpen 
        ? `🟢 ABIERTO (${guia.horario_mercado || ''})`
        : `🔴 CERRADO (${guia.horario_mercado || ''} - Próxima: ${guia.proxima_apertura || 'apertura'})`;
      confidence = 90;
    } else {
      text = "Semáforo: ESPERAR / NO OPERAR. Disciplina de capital: mantener liquidez.";
    }
  }

  if (!text) {
    text = `Oportunidad identificada en ${asset}. Evaluar entrada según soporte técnico y gestión de riesgo.`;
  }

  // Cargar elementos en el Modal
  const assetEl = document.getElementById('modal-inject-asset');
  const typeEl = document.getElementById('modal-inject-type');
  const confEl = document.getElementById('modal-inject-conf');
  const mktEl = document.getElementById('modal-inject-market-status');
  const textEl = document.getElementById('modal-inject-text');
  const feedbackEl = document.getElementById('modal-inject-feedback');
  const confirmBtn = document.getElementById('btn-modal-confirm-inject');
  const confirmText = document.getElementById('modal-confirm-text');

  if (assetEl) assetEl.innerText = asset;
  if (typeEl) {
    typeEl.innerText = type;
    typeEl.className = type === 'Peligro' ? 'text-red-400 font-bold text-sm' : 'text-cyan-400 font-bold text-sm';
  }
  if (confEl) confEl.innerText = `${confidence}%`;
  if (mktEl) {
    mktEl.innerText = marketStatus;
    mktEl.className = isMarketOpen ? 'font-bold text-emerald-400' : 'font-bold text-red-400';
  }
  if (textEl) textEl.value = text;
  if (feedbackEl) {
    feedbackEl.className = 'hidden text-xs p-3 rounded-lg font-mono';
    feedbackEl.innerHTML = '';
  }
  if (confirmBtn) confirmBtn.disabled = false;
  if (confirmText) confirmText.innerText = 'Confirmar e Inyectar';

  currentInjectPayload = {
    asset: asset,
    text: text,
    confidence: confidence,
    type: type,
    source: "Monitor del Mercado",
    timestamp: new Date().toISOString()
  };

  modal.classList.remove('hidden');
}

function openInjectModalWithCardIndex(idx) {
  if (currentActiveReport && currentActiveReport.oportunidades && currentActiveReport.oportunidades[idx]) {
    openInjectModal(currentActiveReport.oportunidades[idx]);
  } else if (currentActiveReport && currentActiveReport.alertas_peligro && currentActiveReport.alertas_peligro[idx]) {
    openInjectModal(currentActiveReport.alertas_peligro[idx]);
  } else {
    openInjectModal();
  }
}

function openInjectDangerCard(idx) {
  if (currentActiveReport && currentActiveReport.alertas_peligro && currentActiveReport.alertas_peligro[idx]) {
    openInjectModal(currentActiveReport.alertas_peligro[idx]);
  }
}

function closeInjectModal() {
  const modal = document.getElementById('inject-modal');
  if (modal) modal.classList.add('hidden');
}

async function confirmInjection() {
  const textEl = document.getElementById('modal-inject-text');
  const feedbackEl = document.getElementById('modal-inject-feedback');
  const confirmBtn = document.getElementById('btn-modal-confirm-inject');
  const confirmText = document.getElementById('modal-confirm-text');

  if (!currentInjectPayload) return;
  if (textEl) currentInjectPayload.text = textEl.value.trim();

  if (confirmBtn) confirmBtn.disabled = true;
  if (confirmText) confirmText.innerText = 'Transmitiendo a puerto 18767...';

  try {
    const res = await fetch('/api/inject_to_trading_bot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentInjectPayload)
    });

    const resData = await res.json().catch(() => ({}));

    if (res.ok) {
      if (feedbackEl) {
        feedbackEl.className = 'text-xs p-3 rounded-lg font-mono bg-emerald-950/80 border border-emerald-500/60 text-emerald-200 block';
        feedbackEl.innerHTML = `
          <div class="font-bold flex items-center gap-1.5 text-emerald-300 mb-1">
            <span>✅</span> ¡Directiva inyectada exitosamente a Trading Ollama!
          </div>
          <div>El bot recibió la tesis para <strong>${escapeHtml(currentInjectPayload.asset)}</strong> en su endpoint. Verifica su bitácora en vivo para ver la recepción.</div>
        `;
      }
      if (confirmText) confirmText.innerText = '¡Inyectado con Éxito!';
      setTimeout(() => {
        closeInjectModal();
      }, 2500);
    } else {
      throw new Error(resData.error || `Error HTTP ${res.status}`);
    }
  } catch (err) {
    console.error("Error inyectando tesis a Trading Ollama:", err);
    if (feedbackEl) {
      feedbackEl.className = 'text-xs p-3 rounded-lg font-mono bg-amber-950/80 border border-amber-500/60 text-amber-200 block';
      feedbackEl.innerHTML = `
        <div class="font-bold flex items-center gap-1.5 text-amber-300 mb-1">
          <span>⚠️</span> No se pudo contactar con Trading Ollama
        </div>
        <div class="leading-relaxed mt-1">${escapeHtml(err.message)}</div>
        <div class="text-[11px] text-slate-400 mt-1">Asegúrate de que tu bot de trading esté ejecutándose en http://127.0.0.1:18767.</div>
      `;
    }
    if (confirmBtn) confirmBtn.disabled = false;
    if (confirmText) confirmText.innerText = 'Reintentar Inyección';
  }
}

async function autoInjectReport(report, isAutomatic = false) {
  if (!report) return;

  const statusEl = document.getElementById('radar-autoinject-status');
  const validOpps = (report.oportunidades || []).filter(opp => opp && isOperableTicker(opp.ticker));
  const validDangers = (report.alertas_peligro || []).filter(d => d && isOperableTicker(d.ticker));

  let selectedCard = null;
  let type = "Oportunidad";

  if (validOpps.length > 0) {
    selectedCard = validOpps[0];
    type = selectedCard.tipo === 'Trampa de Mercado / Peligro' ? 'Peligro' : 'Oportunidad';
  } else if (validDangers.length > 0) {
    selectedCard = validDangers[0];
    type = "Peligro";
  } else {
    if (statusEl) {
      statusEl.className = "text-[10px] text-slate-400 font-mono px-2 py-0.5 rounded bg-slate-900 border border-slate-700 flex items-center gap-1.5";
      statusEl.innerText = "Sin activo operable válido (se excluyen GENERAL y DX-Y.NYB): no se envió directiva.";
      statusEl.classList.remove('hidden');
    }
    return;
  }

  const asset = selectedCard.ticker.trim().toUpperCase();
  if (!isOperableTicker(asset)) {
    return;
  }

  const confidence = Math.min(100, Math.max(0, Math.round((selectedCard.score_asimetria || 8) * 10)));
  const fallbackMsg = (report.guia_operador && report.guia_operador.mensaje_principal) || selectedCard.tesis_contrarian || "";
  const text = buildQuantitativeDirectiveText(selectedCard, fallbackMsg);

  const payload = {
    asset: asset,
    text: text,
    confidence: confidence,
    type: type,
    source: isAutomatic ? "Monitor del Mercado (Auto)" : "Monitor del Mercado",
    timestamp: new Date().toISOString()
  };

  try {
    const res = await fetch('/api/inject_to_trading_bot', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (res.ok) {
      console.log(`📡 [AUTO-INYECCIÓN] Directiva transmitida exitosamente a Trading Ollama para ${asset}.`);
      if (statusEl) {
        statusEl.className = "text-[10px] text-emerald-400 font-mono px-2 py-0.5 rounded bg-emerald-950/90 border border-emerald-800/80 flex items-center gap-1.5 animate-pulse";
        statusEl.innerHTML = `<span>📡</span> Transmitido a Trading Ollama: <strong>${escapeHtml(asset)}</strong>`;
        statusEl.classList.remove('hidden');
        setTimeout(() => {
          if (statusEl) statusEl.classList.add('hidden');
        }, 8000);
      }
    } else {
      console.warn("Auto-inyección falló (puerto 18767 desconectado):", res.status);
      if (statusEl) {
        statusEl.className = "text-[10px] text-amber-400 font-mono px-2 py-0.5 rounded bg-amber-950/90 border border-amber-800/80 flex items-center gap-1.5";
        statusEl.innerHTML = `<span>⚠️</span> Puerto 18767 desconectado`;
        statusEl.classList.remove('hidden');
        setTimeout(() => {
          if (statusEl) statusEl.classList.add('hidden');
        }, 8000);
      }
    }
  } catch (err) {
    console.warn("Error en auto-inyección a Trading Ollama:", err);
  }
}

async function loadRadarConfigFromServer() {
  try {
    const res = await fetch('/api/cio/config');
    if (!res.ok) return;
    const cfg = await res.json();
    const select = document.getElementById('radar-interval');
    const engineEl = document.getElementById('scan-engine');
    const autoinjectEl = document.getElementById('radar-autoinject');
    if (select && cfg.interval_minutes !== undefined) {
        select.value = String(cfg.interval_minutes);
        toggleContinuousRadar(true);
    }
      if (autoinjectEl && cfg.auto_inject !== undefined) {
        autoinjectEl.checked = Boolean(cfg.auto_inject);
      }
  } catch (err) {
    console.warn("No se pudo cargar radar_config inicial:", err);
  }
}

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
  fetchStatus();
  loadRadarConfigFromServer();
  loadReportsList();
  loadLatestReport();
  updateHeaderEngineStatus();

  const engineEl = document.getElementById('scan-engine');
  const autoinjectEl = document.getElementById('radar-autoinject');
  if (engineEl) engineEl.addEventListener('change', () => {
    updateHeaderEngineStatus();
    saveBrainSelection(engineEl.value).catch(error => {
      console.error('No se pudo guardar el cerebro central:', error);
      alert(`No se pudo sincronizar el cerebro con Trading Ollama: ${error.message}`);
    });
  });
  if (autoinjectEl) autoinjectEl.addEventListener('change', () => syncRadarConfigToServer());
  startBrainSyncPolling();
});
