/* ═══════════════════════════════════════════════════════════
   SANKET // RISKSYS  —  SVG Chart Rendering
   ═══════════════════════════════════════════════════════════ */

const Charts = (() => {
  /* ── Sparkline (mini trend line) ────────────────────── */
  function renderSparkline(containerId, data, color = '#10b981') {
    const el = document.getElementById(containerId);
    if (!el) return;
    const w = el.clientWidth || 240;
    const h = 28;
    const max = Math.max(...data);
    const min = Math.min(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
      const x = (i / (data.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x},${y}`;
    });

    const areaPoints = `0,${h} ${points.join(' ')} ${w},${h}`;

    el.innerHTML = `
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="${color}" stop-opacity=".18"/>
            <stop offset="100%" stop-color="${color}" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <polygon points="${areaPoints}" fill="url(#sparkGrad)"/>
        <polyline points="${points.join(' ')}" fill="none" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>`;
  }

  /* ── Trajectory Divergence Line Chart ───────────────── */
  function renderTrajectoryChart(containerId, labelsContainerId, chartData) {
    const el = document.getElementById(containerId);
    const labelsEl = document.getElementById(labelsContainerId);
    if (!el) return;

    const w = el.clientWidth || 500;
    const h = 180;
    const padL = 32;
    const padR = 16;
    const padT = 20;
    const padB = 12;
    const chartW = w - padL - padR;
    const chartH = h - padT - padB;

    const { labels, target, contractorReport, sanketTelemetry, anomalyPoint, discrepancyGap } = chartData;
    const n = target.length;

    const maxVal = Math.max(100, ...target, ...contractorReport, ...sanketTelemetry);
    const yMax = Math.ceil(maxVal / 25) * 25;

    function xPos(i) { return padL + (n > 1 ? (i / (n - 1)) * chartW : chartW / 2); }
    function yPos(v) { return padT + chartH - (v / yMax) * chartH; }

    function polyline(data, color, width, dash = false) {
      const pts = data.map((v, i) => v !== null ? `${xPos(i)},${yPos(v)}` : null).filter(Boolean).join(' ');
      if (!pts) return '';
      return `<polyline points="${pts}" fill="none" stroke="${color}" stroke-width="${width}"
        stroke-linecap="round" stroke-linejoin="round"
        ${dash ? 'stroke-dasharray="6 6"' : ''}/>`;
    }

    // Grid lines
    let gridLines = '';
    for (let pct = 0; pct <= yMax; pct += Math.max(25, Math.ceil(yMax / 4 / 25) * 25)) {
      const y = yPos(pct);
      gridLines += `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="#f1f5f9" stroke-width="1"/>`;
      gridLines += `<text x="${padL - 6}" y="${y + 3}" fill="#94a3b8" font-size="8" text-anchor="end" font-weight="600" font-family="'JetBrains Mono', monospace">${pct}%</text>`;
    }

    // Shaded area between contractor and sanket (discrepancy zone)
    let areaPath = '';
    let firstTop = contractorReport.findIndex(v => v !== null);
    if (firstTop !== -1) {
      areaPath = `M ${xPos(firstTop)},${yPos(contractorReport[firstTop])}`;
      for (let i = firstTop + 1; i < n; i++) {
        if (contractorReport[i] !== null) areaPath += ` L ${xPos(i)},${yPos(contractorReport[i])}`;
      }
      for (let i = n - 1; i >= 0; i--) {
        if (sanketTelemetry[i] !== null) areaPath += ` L ${xPos(i)},${yPos(sanketTelemetry[i])}`;
      }
      areaPath += ' Z';
    }

    let annotations = '';

    if (anomalyPoint) {
      const aIdx = anomalyPoint.index;
      const anomalyX = xPos(aIdx);
      const anomalyY = yPos(sanketTelemetry[aIdx]);
      const anomalyLines = anomalyPoint.label.split('\\n');
      annotations += `
        <!-- Anomaly marker -->
        <line x1="${anomalyX}" y1="${anomalyY - 20}" x2="${anomalyX}" y2="${anomalyY}" stroke="#ef4444" stroke-width="1.5" stroke-dasharray="3 2"/>
        <rect x="${anomalyX - 80}" y="${anomalyY - 52}" width="160" height="30" rx="4" fill="#0f172a" opacity=".95" box-shadow="0 4px 6px rgba(0,0,0,0.1)"/>
        <text x="${anomalyX}" y="${anomalyY - 38}" fill="#f87171" font-size="8" text-anchor="middle" font-weight="800" font-family="'JetBrains Mono', monospace">${anomalyLines[0]}</text>
        <text x="${anomalyX}" y="${anomalyY - 27}" fill="#94a3b8" font-size="7" text-anchor="middle" font-family="'JetBrains Mono', monospace">${anomalyLines[1] || ''}</text>
      `;
    }

    if (discrepancyGap) {
      const dIdx = discrepancyGap.index;
      const gapTopY = yPos(contractorReport[dIdx]);
      const gapBotY = yPos(sanketTelemetry[dIdx]);
      const gapX = xPos(dIdx);
      annotations += `
        <!-- Discrepancy gap line -->
        <line x1="${gapX + 8}" y1="${gapTopY}" x2="${gapX + 8}" y2="${gapBotY}" stroke="#ef4444" stroke-width="2" stroke-dasharray="4 3"/>
        <rect x="${gapX + 14}" y="${(gapTopY + gapBotY) / 2 - 10}" width="120" height="18" rx="4" fill="#fef2f2" stroke="#fca5a5" stroke-width="1"/>
        <text x="${gapX + 74}" y="${(gapTopY + gapBotY) / 2 + 3}" fill="#ef4444" font-size="8" font-weight="800" text-anchor="middle" font-family="'JetBrains Mono', monospace">${discrepancyGap.label}</text>
      `;
    }

    const svg = `
      <svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" style="overflow:visible">
        <!-- Grid -->
        ${gridLines}

        <!-- Discrepancy shaded area -->
        <path d="${areaPath}" fill="url(#discrepancyGrad)" opacity="0.8"/>
        <defs>
          <linearGradient id="discrepancyGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#ef4444" stop-opacity="0.15"/>
            <stop offset="100%" stop-color="#ef4444" stop-opacity="0.02"/>
          </linearGradient>
        </defs>

        <!-- Lines -->
        ${polyline(target, '#cbd5e1', 2, true)}
        ${polyline(contractorReport, '#8b5cf6', 2.5)}
        ${polyline(sanketTelemetry, '#0f172a', 3.5)}

        <!-- Data dots (sanket line) -->
        ${sanketTelemetry.map((v, i) => `
          <circle cx="${xPos(i)}" cy="${yPos(v)}" r="3.5" fill="#0f172a" stroke="#fff" stroke-width="2"/>
          <circle cx="${xPos(i)}" cy="${yPos(v)}" r="14" fill="transparent" class="hover-target" style="cursor:crosshair;"
            data-month="${labels[i]}" 
            data-target="${(target[i] || 0).toFixed(1)}" 
            data-contractor="${(contractorReport[i] || 0).toFixed(1)}" 
            data-sanket="${(v || 0).toFixed(1)}" />
        `).join('')}

        ${annotations}
      </svg>`;

    el.innerHTML = svg;

    const tooltip = document.getElementById('chartTooltip');
    if (tooltip) {
      el.querySelectorAll('.hover-target').forEach(targetEl => {
        targetEl.addEventListener('mouseenter', (e) => {
          tooltip.style.display = 'block';
          tooltip.innerHTML = `
            <div style="font-weight:bold; margin-bottom:6px; color:#f8fafc;">${e.target.dataset.month}</div>
            <div style="color:#a1a1aa;">Target: <span style="float:right;margin-left:12px">${e.target.dataset.target}%</span></div>
            <div style="color:#d4d4d8;">Reported: <span style="float:right;margin-left:12px">${e.target.dataset.contractor}%</span></div>
            <div style="color:#ffffff; font-weight:bold;">Sanket: <span style="float:right;margin-left:12px">${e.target.dataset.sanket}%</span></div>
          `;
        });
        targetEl.addEventListener('mousemove', (e) => {
          tooltip.style.left = (e.pageX + 15) + 'px';
          tooltip.style.top = (e.pageY - 15) + 'px';
        });
        targetEl.addEventListener('mouseleave', () => {
          tooltip.style.display = 'none';
        });
      });
    }

    // X-axis labels
    if (labelsEl) {
      labelsEl.innerHTML = labels.map(l =>
        `<span>${l}</span>`
      ).join('');
    }
  }

  return { renderSparkline, renderTrajectoryChart };
})();
