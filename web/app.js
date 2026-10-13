// app.js — Controlador del Dashboard del Monitor del Mercado

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const statusDiv = document.getElementById('ollama-status');
    if (data.ollama_online) {
      statusDiv.innerHTML = `
        <span class="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
        <span class="text-slate-300">Ollama: <strong class="text-emerald-400">${data.ollama_model}</strong></span>
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
let radarTimerInterval = null;
let radarCountdownSeconds = 0;

function filterReportsTab(tab) {
  currentReportsTab = tab;
  const btnVig = document.getElementById('filter-vigentes-btn');
  const btnTod = document.getElementById('filter-todos-btn');

  if (tab === 'vigentes') {
    btnVig.className = 'px-2.5 py-1 rounded bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold transition-all cursor-pointer';
    btnTod.className = 'px-2.5 py-1 rounded bg-slate-900 text-slate-400 border border-slate-800 transition-all cursor-pointer';
  } else {
    btnTod.className = 'px-2.5 py-1 rounded bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold transition-all cursor-pointer';
    btnVig.className = 'px-2.5 py-1 rounded bg-slate-900 text-slate-400 border border-slate-800 transition-all cursor-pointer';
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
    const modeIcon = r.modo === 'BUSQUEDA_ESPECIFICA' ? '🎯' : '🛰️';
    const folderLabel = r.date_folder && r.date_folder !== 'General' ? `[${r.date_folder}] ` : '';
    const ageLabel = r.horas_antiguedad !== undefined ? ` (${r.horas_antiguedad}h)` : '';

    const baseClass = isSelected
      ? 'px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold transition-all cursor-pointer flex items-center gap-1.5 text-xs shadow-[0_0_10px_rgba(6,182,212,0.3)]'
      : 'px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors cursor-pointer flex items-center gap-1.5 text-xs';

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
    if (btnPath && (btnPath === targetPath || btnPath.endsWith(targetPath) || targetPath.endsWith(btnPath))) {
      b.className = 'px-3 py-1.5 rounded-lg bg-cyan-950 text-cyan-300 border border-cyan-500 font-bold transition-all cursor-pointer flex items-center gap-1.5 text-xs shadow-[0_0_10px_rgba(6,182,212,0.3)]';
    } else {
      b.className = 'px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors cursor-pointer flex items-center gap-1.5 text-xs';
    }
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

function toggleContinuousRadar() {
  const select = document.getElementById('radar-interval');
  const badge = document.getElementById('radar-countdown-badge');
  const intervalMin = parseInt(select.value, 10);

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
        No se detectaron capitulaciones con ratio R/B ≥ 1:3 en este ciclo.<br>
        <span class="text-emerald-400">Disciplina de capital activa: 100% clasificado como ruido sin asimetría.</span>
      </div>
    `;
  } else {
    opportunities.forEach(card => {
      oppContainer.appendChild(createOpportunityCard(card));
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
    dangers.forEach(card => {
      dangerContainer.appendChild(createDangerCard(card));
    });
  }

  // 4. Hoja de Ruta del Operador Novato
  const guia = report.guia_operador || synthesizeGuideForNovice(report);
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
        semBadge.className = 'text-xs px-3 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 font-mono font-bold flex items-center gap-1.5';
      } else if (guia.estado_semaforo.includes('PELIGRO')) {
        semBadge.className = 'text-xs px-3 py-1 rounded-full bg-red-950 text-red-300 border border-red-800 font-mono font-bold flex items-center gap-1.5';
      }
    }
    let fullInstruction = guia.mensaje_principal || '';
    if (guia.mercado_abierto === false && !fullInstruction.includes('CERRADO') && !fullInstruction.includes('ATENCIÓN HORARIO')) {
      fullInstruction += ` ⚠️ ATENCIÓN HORARIO (MERCADO CERRADO): El mercado físico de ${guia.ticker_referencia || 'este activo'} opera de ${guia.horario_mercado || 'Wall Street 10:30 a 17:00 ARG'} y está CERRADO ahora. No dispares órdenes a tu bot con cotizaciones congeladas para evitar el error de 'datos obsoletos' y el riesgo de Gap de apertura. Ejecuta a partir de la apertura: ${guia.proxima_apertura}.`;
    } else if (guia.mercado_abierto === true && !fullInstruction.includes('ABIERTO') && !fullInstruction.includes('EN VIVO')) {
      fullInstruction += ` 🟢 MERCADO EN VIVO: El mercado está ABIERTO (${guia.horario_mercado || 'Horario oficial'}). El bot dispone de cotizaciones frescas y liquidez real para operar.`;
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
      mktBadge.className = isMktOpen
        ? 'px-2.5 py-1 rounded text-xs font-mono font-bold flex items-center gap-1.5 bg-emerald-950 text-emerald-300 border border-emerald-700'
        : 'px-2.5 py-1 rounded text-xs font-mono font-bold flex items-center gap-1.5 bg-red-950 text-red-300 border border-red-800';
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
          ? 'El mercado físico está recibiendo velas en vivo. Tu bot de trading puede operar con cotizaciones frescas.'
          : 'El mercado físico está cerrado ahora. No dispares órdenes a tu bot con datos congelados (antigüedad > 2700s) para evitar rechazos o gaps.'
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

function synthesizeGuideForNovice(report) {
  const opps = report.oportunidades || [];
  const dangers = report.alertas_peligro || [];

  if (opps.length > 0) {
    const opp0 = opps[0];
    return {
      estado_semaforo: "OPERAR CON CAUTELA",
      mensaje_principal: `Existe una oportunidad asimétrica favorable en ${opp0.ticker}. La multitud está asustada y vendiendo, permitiéndote entrar a precio de descuento con una relación beneficio/riesgo de 1 a ${opp0.ratio_riesgo_beneficio}.`,
      checklist_pasos: [
        `1. LOCALIZA EL ACTIVO: Abre tu plataforma de inversión y busca el ticker '${opp0.ticker}' (${opp0.asset_name || ''}).`,
        `2. ORDEN DE COMPRA: Configura una orden límite en ${opp0.nivel_entrada_sugerido}. No compres apurado a mercado.`,
        `3. STOP LOSS OBLIGATORIO: Coloca tu orden de venta defensiva en ${opp0.stop_loss_sugerido || 'zona defensiva'} para limitar tu riesgo.`,
        `4. TOMA DE GANANCIAS (TAKE PROFIT): Fija tu objetivo de salida en ${opp0.target_proyectado || 'zona de target'} y retira beneficios sin codicia.`,
        `5. PACIENCIA: Plazo estimado de ${opp0.horizonte_temporal || '3-6 meses'}. Dale tiempo a la tesis para desarrollarse.`
      ],
      regla_gestion_riesgo: "REGLA DEL 1%: Nunca arriesgues más del 1% o 2% del total de tu cuenta en esta operación (máx 10-20 USD por cada 1.000 USD de capital).",
      consejo_psicologico: "No te asustes por los titulares pesimistas. El pánico de los medios es el causante del descuento. Tu ventaja como inversor contrarian es comprar cuando hay sangre y vender cuando hay fiesta."
    };
  } else if (dangers.length > 0) {
    const danger0 = dangers[0];
    return {
      estado_semaforo: "ALERTA DE PELIGRO",
      mensaje_principal: `El activo ${danger0.ticker} está en zona de sobrecalentamiento y euforia mediática peligrosa. Abstente de comprar.`,
      checklist_pasos: [
        `1. ALTO TOTAL: No compres '${danger0.ticker}' bajo ninguna circunstancia.`,
        "2. NO TE DEJES LLEVAR POR EL FOMO: Aunque en redes digan que subirá al infinito, el precio ya está inflado.",
        "3. SI YA TIENES ESTE ACTIVO: Considera asegurar beneficios o colocar un Stop Loss ceñido.",
        "4. CONSERVA TU LIQUIDEZ: Tu dinero está más seguro en efectivo esperando una verdadera oportunidad."
      ],
      regla_gestion_riesgo: "PRESERVACIÓN DE CAPITAL: El primer objetivo de un operador novato no es hacerse rico rápido, sino evitar perder el dinero en las trampas de euforia.",
      consejo_psicologico: "Sentirás ganas de comprar porque 'todo el mundo habla de ello'. Esa es la trampa psicológica más antigua del mercado. Recuerda: compra en el pánico, huye de la euforia."
    };
  } else {
    return {
      estado_semaforo: "ESPERAR / NO OPERAR",
      mensaje_principal: "El mercado no ofrece ninguna oportunidad asimétrica clara hoy. Todo el flujo analizado es ruido mediático transitorio. La decisión más inteligente y rentable hoy es NO OPERAR.",
      checklist_pasos: [
        "1. QUÉDATE QUIETO: Hoy no toques ningún botón de compra ni de venta.",
        "2. CONSERVA EL 100% DE TU DINERO EN EFECTIVO: El 95% de las noticias de hoy fueron descartadas como ruido publicitario o chismes sin fundamento.",
        "3. EVITA EL ERROR N° 1 DEL NOVATO: El error más común es operar todos los días por aburrimiento o impaciencia. Los traders profesionales pasan el 80% de su tiempo observando y esperando.",
        "4. ESPERA AL PRÓXIMO ESCANEO: Mantén el radar activo y espera a que el mercado ofrezca una verdadera capitulación con ventaja matemática."
      ],
      regla_gestion_riesgo: "PACIENCIA Y DISCIPLINA: No perder dinero en días de ruido es exactamente igual a ganar dinero. El efectivo es una posición ganadora.",
      consejo_psicologico: "No sientas que estás perdiendo el tiempo por no hacer una operación hoy. La disciplina de esperar a que el precio y el pánico jueguen a tu favor es lo que separa a los perdedores de los inversores exitosos."
    };
  }
}



function createOpportunityCard(card) {
  const div = document.createElement('div');
  div.className = 'glass-card rounded-xl p-5 border-emerald-500/30 flex flex-col justify-between space-y-4 hover:border-emerald-500/60 transition-all';
  
  div.innerHTML = `
    <div>
      <div class="flex items-start justify-between gap-2 mb-2">
        <div>
          <span class="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-950/80 border border-emerald-800/60 font-mono">
            R/B 1 a ${card.ratio_riesgo_beneficio}
          </span>
          <h3 class="text-base font-bold text-white mt-1.5">${escapeHtml(card.ticker)}</h3>
          <p class="text-xs text-slate-400">${escapeHtml(card.asset_name)}</p>
        </div>
        <div class="text-right font-mono">
          <div class="text-xs font-bold text-emerald-400">${card.score_asimetria}/10 Score</div>
          <div class="text-[11px] text-slate-400">${escapeHtml(card.horizonte_temporal)}</div>
        </div>
      </div>

      <div class="bg-slate-950/70 p-3 rounded-lg border border-slate-800/80 space-y-1.5 my-3 text-xs font-mono">
        <div class="flex justify-between">
          <span class="text-slate-400">Entrada sugerida:</span>
          <span class="text-white font-bold">${escapeHtml(card.nivel_entrada_sugerido)}</span>
        </div>
        ${card.stop_loss_sugerido ? `
        <div class="flex justify-between">
          <span class="text-slate-400">Stop invalidación:</span>
          <span class="text-red-400 font-bold">${escapeHtml(card.stop_loss_sugerido)}</span>
        </div>` : ''}
        ${card.target_proyectado ? `
        <div class="flex justify-between">
          <span class="text-slate-400">Target proyectado:</span>
          <span class="text-emerald-400 font-bold">${escapeHtml(card.target_proyectado)}</span>
        </div>` : ''}
        ${card.horario_mercado ? `
        <div class="flex justify-between pt-1 border-t border-slate-800/80">
          <span class="text-slate-400">Horario:</span>
          <span class="${card.mercado_abierto ? 'text-emerald-400 font-bold' : 'text-red-400 font-bold'}">
            ${card.mercado_abierto ? '🟢 ABIERTO' : '🔴 CERRADO'}
            <span class="text-slate-400 text-[10px] font-normal">(${escapeHtml(card.horario_mercado)})</span>
          </span>
        </div>` : ''}
      </div>

      <div class="space-y-2 text-xs">
        <div>
          <h4 class="font-bold text-amber-400 flex items-center gap-1.5">
            <span>💡</span> Tesis Contrarian:
          </h4>
          <p class="text-slate-300 pl-4 border-l-2 border-amber-500/40 italic mt-1 leading-relaxed">
            "${escapeHtml(card.tesis_contrarian)}"
          </p>
        </div>

        <div>
          <h4 class="font-bold text-cyan-400 flex items-center gap-1.5">
            <span>⚡</span> Catalizador:
          </h4>
          <p class="text-slate-300 pl-4 border-l-2 border-cyan-500/40 mt-1 leading-relaxed">
            ${escapeHtml(card.catalizador_detonante)}
          </p>
        </div>

        <div>
          <h4 class="font-bold text-slate-300 flex items-center gap-1.5">
            <span>🏛️</span> Soporte Secular:
          </h4>
          <p class="text-slate-400 pl-4 border-l-2 border-slate-700 mt-1 leading-relaxed">
            ${escapeHtml(card.soporte_secular)}
          </p>
        </div>
      </div>
    </div>

    <div class="pt-3 border-t border-slate-800 text-[11px] text-slate-400 flex items-center justify-between">
      <span class="px-2 py-0.5 rounded bg-slate-900 border border-slate-800">${escapeHtml(card.sentimiento_mercado)}</span>
      <span class="text-emerald-400 font-mono">Alta Asimetría</span>
    </div>
  `;
  return div;
}

function createDangerCard(card) {
  const div = document.createElement('div');
  div.className = 'glass-card rounded-xl p-5 border-red-500/30 flex flex-col justify-between space-y-3';
  div.innerHTML = `
    <div>
      <div class="flex items-start justify-between gap-2 mb-2">
        <div>
          <span class="text-xs font-bold text-red-400 px-2 py-0.5 rounded bg-red-950/80 border border-red-800/60 font-mono">
            ⚠️ TRAMPA DE MERCADO
          </span>
          <h3 class="text-base font-bold text-white mt-1">${escapeHtml(card.ticker)} (${escapeHtml(card.asset_name)})</h3>
        </div>
        <span class="text-xs font-mono text-red-400">Score ${card.score_asimetria}/10</span>
      </div>

      <p class="text-xs text-red-200/90 leading-relaxed bg-red-950/20 p-3 rounded-lg border border-red-900/40 my-2">
        <strong>Peligro:</strong> ${escapeHtml(card.tesis_contrarian)}
      </p>

      <div class="text-xs text-slate-400 space-y-1">
        <div><strong>Catalizador de Hype:</strong> ${escapeHtml(card.catalizador_detonante)}</div>
        <div><strong>Recomendación:</strong> ${escapeHtml(card.nivel_entrada_sugerido)}</div>
      </div>
    </div>
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
  const customDirective = document.getElementById('scan-custom-directive')
    ? document.getElementById('scan-custom-directive').value.trim()
    : '';

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btnText.innerText = isAutomatic ? "Radar continuo escaneando..." : "Escaneando mercado e IA...";

  try {
    const res = await fetch('/api/scan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        category: category || null,
        custom_directive: customDirective || null
      })
    });
    const result = await res.json();
    await loadReportsList();
    await loadLatestReport();
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
    btnText.innerText = "🚀 Escanear Mercado Ahora";
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

    const changeClass = data.change_pct_24h >= 0 ? 'text-emerald-400' : 'text-red-400';
    let rsiBadge = '';
    if (data.rsi_14 !== null) {
      const rsiColor = data.rsi_14 < 30 ? 'text-emerald-400 bg-emerald-950/80 border-emerald-800' : (data.rsi_14 > 70 ? 'text-red-400 bg-red-950/80 border-red-800' : 'text-slate-300 bg-slate-900 border-slate-700');
      rsiBadge = `<span class="px-1.5 py-0.5 rounded border text-[11px] ${rsiColor}">RSI(14): ${data.rsi_14}</span>`;
    }

    let schedLine = '';
    if (data.schedule) {
      const isOp = data.schedule.mercado_abierto;
      const statusColor = isOp ? 'text-emerald-400 bg-emerald-950/80 border-emerald-800' : 'text-red-400 bg-red-950/80 border-red-800';
      schedLine = `
        <div class="flex flex-wrap items-center justify-between gap-1 pt-1.5 border-t border-slate-800/80 text-[11px]">
          <div class="flex items-center gap-1.5">
            <span class="px-1.5 py-0.5 rounded border font-bold ${statusColor}">${data.schedule.estado_texto}</span>
            <span class="text-slate-400">${data.schedule.categoria} (${data.schedule.horario_argentina})</span>
          </div>
          <span class="${isOp ? 'text-emerald-400' : 'text-amber-400'} font-bold">${data.schedule.proxima_apertura}</span>
        </div>
      `;
    }

    resultDiv.innerHTML = `
      <div class="w-full space-y-1">
        <div class="flex justify-between items-center">
          <strong class="text-white text-sm">${data.ticker}</strong>
          <span class="font-bold text-white">${data.current_price} ${data.currency} <span class="${changeClass}">(${data.change_pct_24h > 0 ? '+' : ''}${data.change_pct_24h}%)</span></span>
        </div>
        <div class="flex justify-between text-[11px] text-slate-400">
          <span>Máx 52s: ${data.pct_from_52w_high}% | Mín: +${data.pct_from_52w_low}%</span>
          ${rsiBadge}
        </div>
        ${schedLine}
      </div>
    `;
  } catch (err) {
    resultDiv.innerHTML = `<span class="text-red-400">No se encontraron datos para "${symbol}".</span>`;
  }
}

function escapeHtml(text) {
  if (!text) return '';
  return String(text)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
  fetchStatus();
  loadReportsList();
  loadLatestReport();
});
