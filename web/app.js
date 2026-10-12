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

async function loadReportsList() {
  try {
    const res = await fetch('/api/reports');
    const reports = await res.json();
    const container = document.getElementById('reports-list');
    container.innerHTML = '';

    if (!reports || reports.length === 0) {
      container.innerHTML = '<span class="text-slate-500 italic">No hay reportes generados aún.</span>';
      return;
    }

    reports.forEach(r => {
      const btn = document.createElement('button');
      btn.className = 'px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 text-slate-300 border border-slate-700/60 transition-colors cursor-pointer';
      btn.innerText = r.name;
      btn.onclick = () => loadReportContent(r.name, btn);
      container.appendChild(btn);
    });
  } catch (err) {
    console.error("Error cargando lista de reportes:", err);
  }
}

async function loadLatestReport() {
  try {
    const res = await fetch('/api/reports/latest');
    if (!res.ok) {
      document.getElementById('executive-verdict').innerText = "No se ha generado ningún reporte todavía. Haz clic en 'Escanear Mercado Ahora'.";
      return;
    }
    const reportData = await res.json();
    renderReport(reportData);
  } catch (err) {
    console.error("Error cargando último reporte:", err);
  }
}

async function loadReportContent(filename, clickedBtn = null) {
  try {
    // Marcar botón activo
    if (clickedBtn) {
      document.querySelectorAll('#reports-list button').forEach(b => {
        b.classList.remove('bg-cyan-950', 'border-cyan-500', 'text-cyan-300');
        b.classList.add('bg-slate-900', 'text-slate-300');
      });
      clickedBtn.classList.remove('bg-slate-900', 'text-slate-300');
      clickedBtn.classList.add('bg-cyan-950', 'border-cyan-500', 'text-cyan-300');
    }

    const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`);
    const reportData = await res.json();
    renderReport(reportData);

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
  }
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

async function triggerScan() {
  const btn = document.getElementById('btn-scan');
  const spinner = document.getElementById('scan-spinner');
  const btnText = document.getElementById('scan-btn-text');
  const category = document.getElementById('scan-category').value;
  const customDirective = document.getElementById('scan-custom-directive')
    ? document.getElementById('scan-custom-directive').value.trim()
    : '';

  btn.disabled = true;
  spinner.classList.remove('hidden');
  btnText.innerText = "Escaneando mercado e IA...";

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
    alert("¡Escaneo completado con éxito! Se han actualizado las fichas y conclusiones.");

  } catch (err) {
    alert("Error al ejecutar escaneo: " + err.message);
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

    resultDiv.innerHTML = `
      <div class="w-full space-y-1">
        <div class="flex justify-between items-center">
          <strong class="text-white">${data.ticker}</strong>
          <span class="font-bold text-white">${data.current_price} ${data.currency} <span class="${changeClass}">(${data.change_pct_24h > 0 ? '+' : ''}${data.change_pct_24h}%)</span></span>
        </div>
        <div class="flex justify-between text-[11px] text-slate-400">
          <span>Máx 52s: ${data.pct_from_52w_high}% | Mín: +${data.pct_from_52w_low}%</span>
          ${rsiBadge}
        </div>
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
