/* ═══════════════════════════════════════════════════════════
   SANKET // RISKSYS  —  Application Controller
   ═══════════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
  /* ── Initialize Data & Charts ────────────────────────── */
  async function initData() {
    try {
      // Check backend health
      const health = await API.healthCheck();
      document.getElementById('connectionDot').className = 'status-dot status-green';
      document.getElementById('connectionText').innerHTML = 'System<br/>Operational';

      // Fetch live data
      const [summary, projectsRes] = await Promise.all([
        API.getDashboardSummary(),
        API.getProjects('', '', '', 5000, 0)
      ]);

      // Hydrate SANKET_DATA portfolio summary
      SANKET_DATA.hydrateFromAPI(summary, null);

      // Map all 5000 projects
      SANKET_DATA.projects = (projectsRes.projects || []).map(p => ({
        id: p.project_id,
        name: p.project_name,
        score: Math.round(p.latest_risk_tier === 'NORMAL' ? 0 : (p.latest_risk || 0) * 100),
        severity: p.latest_risk_tier || 'UNKNOWN',
        severityClass: (p.latest_risk_tier || 'unknown').toLowerCase(),
        location: `${p.state || '--'} • ${p.sector || '--'}`,
        ministry: p.ministry || '--',
        progress: p.financial_progress || 0,
        lastReported: p.latest_observation || 'Unknown',
        variance: p.schedule_deviation_months != null ? p.schedule_deviation_months : null,
        varianceLabel: 'Months',
        value: Math.round((p.baseline_cost || p.approved_cost || 0))
      }));

      // Update DOM with live data
      updateDashboardDOM();

    } catch (e) {
      console.error('[initData] Backend unavailable:', e);
      document.getElementById('connectionDot').className = 'status-dot status-amber';
      document.getElementById('connectionText').innerHTML = 'Offline<br/>Connection Error';
      
      const errorOverlay = document.getElementById('errorOverlay');
      const errorDetails = document.getElementById('errorDetails');
      if (errorOverlay && errorDetails) {
        errorOverlay.style.display = 'block';
        errorDetails.textContent = `Error: ${e.message}. Attempted to connect to backend via Express proxy.`;
      }
      return; // Stop rendering mock data
    }

    // Render charts (uses live data if available, else mock)
    Charts.renderSparkline('sparkline-total', SANKET_DATA.sparkline, '#10b981');
    Charts.renderTrajectoryChart('trajectoryChart', 'chartXLabels', SANKET_DATA.trajectoryChart);

    // Render project cards
    renderProjectCards();

    // Auto-select the first project
    const firstProject = document.querySelector('.project-row');
    if (firstProject) {
      firstProject.click();
    }
  }

  function updateDashboardDOM() {
    // Header updates
    document.getElementById('connectionDot').className = 'status-dot status-green';
    document.getElementById('connectionText').innerHTML = 'System<br/>Operational';
    document.getElementById('headerTelemetryText').innerHTML = `Live Telemetry &bull; M${SANKET_DATA.portfolio.latestMonth || '--'}`;

    const activeRisksBadge = document.getElementById('activeRisksBadge');
    if (activeRisksBadge) activeRisksBadge.innerHTML = `${SANKET_DATA.portfolio.highRiskExcursions || '--'} Active<br/>Risks`;

    const totalMonitoredValue = document.getElementById('valTotalMonitored');
    if (totalMonitoredValue) totalMonitoredValue.textContent = SANKET_DATA.portfolio.totalMonitored.toLocaleString();

    const yoyChange = document.getElementById('valYoyChange');
    if (yoyChange) yoyChange.textContent = `${SANKET_DATA.portfolio.yoyChange}% YoY ${SANKET_DATA.portfolio.yoyChange >= 0 ? '▲' : '▼'}`;

    const totalArchiveValue = document.getElementById('valTotalArchive');
    if (totalArchiveValue) totalArchiveValue.textContent = SANKET_DATA.portfolio.totalArchiveEntities ? SANKET_DATA.portfolio.totalArchiveEntities.toLocaleString() : '--';

    const activeTelemetryPct = document.getElementById('valActiveTelemetryPct');
    if (activeTelemetryPct) activeTelemetryPct.textContent = `${SANKET_DATA.portfolio.activeTelemetryPct}% Active Telemetry`;

    const addedThisQuarter = document.getElementById('valAddedThisQuarter');
    if (addedThisQuarter) addedThisQuarter.textContent = `+${SANKET_DATA.portfolio.addedThisQuarter} this quarter`;

    // Update "High Risk Excursions" (card 1)
    const excursionsValue = document.getElementById('valHighRisk');
    if (excursionsValue) excursionsValue.textContent = SANKET_DATA.portfolio.highRiskExcursions;

    const highRiskTotal = document.getElementById('valHighRiskTotal');
    if (highRiskTotal) highRiskTotal.textContent = `/ ${SANKET_DATA.portfolio.totalMonitored.toLocaleString()}`;

    const riskPct = document.getElementById('valRiskPct');
    if (riskPct) riskPct.textContent = `${SANKET_DATA.portfolio.riskPct}% Risk`;

    // Risk Segments
    const totalCount = SANKET_DATA.portfolio.totalMonitored || 1;
    const pNorm = (SANKET_DATA.portfolio.riskSegments.normal / totalCount) * 100;
    const pElev = (SANKET_DATA.portfolio.riskSegments.elevated / totalCount) * 100;
    const pDiv = (SANKET_DATA.portfolio.riskSegments.divergent / totalCount) * 100;
    
    if (document.getElementById('barSegNormal')) document.getElementById('barSegNormal').style.width = `${pNorm}%`;
    if (document.getElementById('barSegElevated')) document.getElementById('barSegElevated').style.width = `${pElev}%`;
    if (document.getElementById('barSegDivergent')) document.getElementById('barSegDivergent').style.width = `${pDiv}%`;
    if (document.getElementById('valLegendDivergent')) document.getElementById('valLegendDivergent').textContent = SANKET_DATA.portfolio.highRiskExcursions;

    // Update "Value at Immediate Risk" (card 2)
    const varValue = document.getElementById('valImmediateRisk');
    if (varValue) varValue.textContent = `₹${SANKET_DATA.portfolio.valueAtRisk.toLocaleString()}`;

    const riskPortPct = document.getElementById('valRiskPortfolioPct');
    if (riskPortPct) riskPortPct.textContent = `${SANKET_DATA.portfolio.riskPortfolioPct}% Port.`;

    // Risk Breakdown
    const breakdownList = document.getElementById('riskBreakdownList');
    const barMulti = document.getElementById('riskBarMulti');
    if (breakdownList && barMulti) {
      breakdownList.innerHTML = '';
      barMulti.innerHTML = '';
      const topSectors = SANKET_DATA.portfolio.sectorBreakdown.slice(0, 3);
      const totalTop = topSectors.reduce((acc, s) => acc + s.value, 0) || 1;
      
      topSectors.forEach(sector => {
        // e.g. "Road Transport And Highways" -> "Roads"
        const shortName = sector.name.length > 10 ? sector.name.substring(0, 10) + '...' : sector.name;
        const valueK = (sector.value / 1000).toFixed(1);
        const pct = (sector.value / totalTop) * 100;
        
        breakdownList.innerHTML += `<span class="rb-item">${shortName} ₹${valueK}k</span>`;
        barMulti.innerHTML += `<div class="rb-seg" style="width:${pct}%; background-color:${sector.color}"></div>`;
      });
    }

    // Update "Median Warning Lead"
    const leadValue = document.getElementById('valMedianLead');
    if (leadValue) leadValue.textContent = SANKET_DATA.portfolio.medianWarningLead;

    const modelCal = document.getElementById('valModelCalibration');
    if (modelCal) modelCal.textContent = `${SANKET_DATA.portfolio.modelCalibration}% Accuracy`;

    // Active Risks Badge
    const badgeRed = document.querySelector('.badge-red');
    if (badgeRed) badgeRed.textContent = `${SANKET_DATA.portfolio.highRiskExcursions} Active Risks`;
  }

  function renderProjectCards() {
    const listEl = document.querySelector('.project-list');
    if (!listEl) return;

    const searchInput = document.getElementById('projectSearchInput');
    const filterSelect = document.getElementById('projectRiskFilter');
    const sortSelect = document.getElementById('projectSortFilter');
    const query = searchInput ? searchInput.value.toLowerCase() : '';
    const riskFilter = filterSelect ? filterSelect.value : 'ALL';
    const sortFilter = sortSelect ? sortSelect.value : 'RISK_DESC';

    const isCompletedView = window.currentView === 'view-completed';

    const filteredProjects = SANKET_DATA.projects.filter(p => {
      const matchesQuery = !query || p.name.toLowerCase().includes(query) || p.location.toLowerCase().includes(query) || p.ministry.toLowerCase().includes(query);
      let matchesRisk = true;
      if (isCompletedView) {
          matchesRisk = p.progress >= 100;
      } else {
          matchesRisk = riskFilter === 'ALL' || p.severity === riskFilter;
      }
      return matchesQuery && matchesRisk;
    });

    if (filteredProjects.length === 0) {
      listEl.innerHTML = '<div style="padding:40px 20px; text-align:center; color:#64748b; font-size:13px;">No projects match your search criteria.</div>';
      return;
    }

    filteredProjects.sort((a, b) => {
      if (sortFilter === 'RISK_DESC') {
        return b.score - a.score;
      } else if (sortFilter === 'RISK_ASC') {
        return a.score - b.score;
      } else if (sortFilter === 'NEWEST') {
        return (b.lastReported || '').localeCompare(a.lastReported || '');
      } else if (sortFilter === 'OLDEST') {
        return (a.lastReported || '').localeCompare(b.lastReported || '');
      }
      return 0;
    });

    // Generate simulated sparkline based on final score and ID seed
    function generateSparklineSVG(score, idStr) {
      let seed = 0;
      for (let i = 0; i < idStr.length; i++) seed += idStr.charCodeAt(i);
      
      const points = [];
      const numPoints = 6;
      let currentVal = score;
      points.push(currentVal);
      
      // Walk backwards from the actual score to simulate history
      for (let i = 1; i < numPoints; i++) {
        const fluct = (Math.sin(seed + i) * 15);
        currentVal = Math.max(0, Math.min(100, currentVal + fluct));
        points.unshift(currentVal);
      }
      
      const w = 60;
      const h = 20;
      const dx = w / (numPoints - 1);
      let d = '';
      points.forEach((p, idx) => {
        const x = idx * dx;
        const y = h - (p / 100 * h);
        if (idx === 0) d += `M ${x},${y} `;
        else d += `L ${x},${y} `;
      });
      
      const color = '#a3a3a3'; // Minimalist gray
      return `<svg width="${w}" height="${h}" viewBox="0 -5 ${w} ${h+10}" style="overflow: visible;"><path d="${d}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" /><circle cx="${w}" cy="${h - (score / 100 * h)}" r="2.5" fill="#000000" /></svg>`;
    }

    const isInterventions = window.currentView === 'view-interventions';
    let tableHTML = '';

    if (isInterventions) {
      tableHTML = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 24px; padding: 24px; background: #f8f9fa; min-height: 100%; border-radius: 16px;">';
      filteredProjects.forEach((p, idx) => {
        // Material Colors
        const isRed = p.score > 70;
        const isYellow = p.score > 40 && p.score <= 70;
        
        const mRedText = '#d93025'; const mRedBg = '#fce8e6';
        const mYellowText = '#b06000'; const mYellowBg = '#fef7e0';
        const mGreenText = '#1e8e3e'; const mGreenBg = '#e6f4ea';
        const mGrayText = '#5f6368'; const mGrayBg = '#f1f3f4';
        const mBlue = '#1a73e8';

        const severityText = isRed ? mRedText : isYellow ? mYellowText : mGreenText;
        const severityBg = isRed ? mRedBg : isYellow ? mYellowBg : mGreenBg;
        
        let varText, varBg, varColor;
        if (p.variance > 0) { varText = 'Delay'; varColor = mRedText; varBg = mRedBg; }
        else if (p.variance < 0) { varText = 'Ahead'; varColor = mGreenText; varBg = mGreenBg; }
        else { varText = 'On Track'; varColor = mGrayText; varBg = mGrayBg; }

        const varianceStr = p.variance === 0 ? 'On Track' : `${Math.abs(p.variance)}m ${varText}`;
        
        tableHTML += `
          <div class="project-row" data-id="${p.id}" style="background: #ffffff; border: 1px solid #e0e0e0; border-radius: 16px; padding: 24px; cursor: pointer; display: flex; flex-direction: column; transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);" onmouseover="this.style.boxShadow='0 4px 12px 3px rgba(0,0,0,0.04)'; this.style.transform='translateY(-2px)';" onmouseout="this.style.boxShadow='none'; this.style.transform='translateY(0)';">
            
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
              <span style="background: ${severityBg}; color: ${severityText}; padding: 6px 14px; border-radius: 20px; font-size: 11px; font-weight: 600; letter-spacing: 0.3px;">${p.severity}</span>
              <span style="color: ${mGrayText}; font-size: 12px; font-weight: 500;">ID: ${p.id}</span>
            </div>

            <div style="font-weight: 500; color: #202124; font-size: 18px; margin-bottom: 8px; line-height: 1.3;">${p.name}</div>
            
            <div style="font-size: 13px; color: #5f6368; display: flex; align-items: center; gap: 6px; margin-bottom: 24px;">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z"/><circle cx="12" cy="10" r="3"/></svg>
              ${p.location} • ${p.ministry}
            </div>

            <div style="display: flex; gap: 32px; margin-bottom: 32px;">
              <div>
                <div style="font-size: 12px; color: #5f6368; margin-bottom: 2px; font-weight: 500;">Risk Score</div>
                <div style="font-size: 36px; font-weight: 400; color: ${severityText}; line-height: 1;">${p.score}</div>
              </div>
              <div>
                <div style="font-size: 12px; color: #5f6368; margin-bottom: 8px; font-weight: 500;">Schedule</div>
                <div style="font-size: 13px; font-weight: 600; color: ${varColor}; background: ${varBg}; display: inline-block; padding: 6px 12px; border-radius: 8px;">
                  ${varianceStr}
                </div>
              </div>
            </div>
            
            <div style="margin-top: auto; border-top: 1px solid #f1f3f4; padding-top: 20px; display: flex; justify-content: space-between; align-items: center;">
              <div>
                <div style="font-size: 11px; color: #5f6368; margin-bottom: 2px;">Project Value</div>
                <div style="font-size: 16px; font-weight: 500; color: #202124;">₹${p.value} Cr</div>
              </div>
              <button style="background: ${mBlue}; color: #ffffff; border: none; padding: 10px 24px; border-radius: 24px; font-size: 14px; font-weight: 500; cursor: pointer; transition: background 0.2s; box-shadow: 0 1px 3px rgba(0,0,0,0.12);" onmouseover="this.style.background='#174ea6'" onmouseout="this.style.background='${mBlue}'">
                View Details
              </button>
            </div>
          </div>
        `;
      });
      tableHTML += '</div>';
    } else {
      tableHTML = `
        <div style="width: 100%; overflow-x: auto;">
        <table class="project-table" style="width: 100%; min-width: 700px; border-collapse: collapse; text-align: left; font-size: 13px;">
          <thead>
            <tr style="border-bottom: 1px solid rgba(0,0,0,0.1); color: #64748b; font-size: 11px; text-transform: uppercase;">
              <th style="padding: 12px 8px;">Risk</th>
              <th style="padding: 12px 8px;">Score</th>
              <th style="padding: 12px 8px; width: 80px;">Trend (6m)</th>
              <th style="padding: 12px 8px;">Project</th>
              <th style="padding: 12px 8px;">Location</th>
              <th style="padding: 12px 8px; text-align: right;">Cost</th>
            </tr>
          </thead>
          <tbody>
      `;

      filteredProjects.forEach((p, idx) => {
        const isSelected = idx === 0 ? 'selected' : '';
        const varianceColor = p.variance == null ? '#94a3b8' : (p.variance > 0 ? '#ef4444' : (p.variance < 0 ? '#10b981' : '#94a3b8'));
        const varianceText = p.variance == null ? 'Unknown' : (p.variance === 0 ? 'On Schedule' : `${Math.abs(p.variance)} ${p.variance > 0 ? 'Months Delay' : 'Months Ahead'}`);
        
        tableHTML += `
          <tr class="project-row ${isSelected}" data-id="${p.id}" style="cursor: pointer; border-bottom: 1px solid rgba(0,0,0,0.05); transition: all 0.2s; background: white;" onmouseover="this.style.background='#f8fafc'" onmouseout="this.style.background='white'">
            <td style="padding: 16px 8px;"><span class="pc-badge badge-${p.severityClass}" style="padding: 4px 8px; font-weight: 700;">${p.severity}</span></td>
            <td style="padding: 16px 8px; font-weight: 800; font-size: 14px; color: ${p.score > 70 ? '#ef4444' : p.score > 40 ? '#f59e0b' : '#10b981'};">${p.score}<span style="font-size: 11px; font-weight: 600; color: #94a3b8;">/100</span></td>
            <td style="padding: 16px 8px;">${generateSparklineSVG(p.score, p.id)}</td>
            <td style="padding: 16px 8px;">
              <div style="font-weight: 700; color: #0f172a; margin-bottom: 6px; font-size: 13px;">${p.name}</div>
              <div style="font-size: 11px; color: ${p.progress >= 100 ? '#10b981' : '#64748b'}; font-weight: 500; display: flex; align-items: center; gap: 4px;">
                ${p.progress >= 100 ? '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> Completed' : (p.ministry !== '—' ? p.ministry : 'Ongoing')} • Last Reported: ${p.lastReported}
              </div>
            </td>
            <td style="padding: 16px 8px; color: #64748b; font-size: 12px; font-weight: 500;">${p.location}</td>
            <td style="padding: 16px 8px; text-align: right;">
              <div style="font-size: 14px; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #0f172a;">₹${p.value} Cr</div>
              <div style="font-size: 11px; font-weight: 600; font-family: 'JetBrains Mono', monospace; color: ${varianceColor}; margin-top: 6px; background: ${varianceColor}15; display: inline-block; padding: 2px 6px; border-radius: 4px;">${varianceText}</div>
            </td>
          </tr>
        `;
      });

      tableHTML += `
          </tbody>
        </table>
        </div>
      `;
    }

    listEl.innerHTML = tableHTML;

    // Add hover styles dynamically if not present
    if (!document.getElementById('projectTableStyles')) {
      const style = document.createElement('style');
      style.id = 'projectTableStyles';
      style.innerHTML = `
        .project-row:hover { background-color: rgba(0, 0, 0, 0.03); }
        .project-row.selected { background-color: rgba(56, 189, 248, 0.1); border-left: 3px solid #38bdf8; }
      `;
      document.head.appendChild(style);
    }

    // Re-bind click events
    const projectRows = document.querySelectorAll('.project-row');
    projectRows.forEach(row => {
      row.addEventListener('click', async (e) => {
        const isActionClick = e.target.closest('.action-btn');
        
        projectRows.forEach(r => r.classList.remove('selected'));
        row.classList.add('selected');

        const mainGrid = document.querySelector('.dashboard-grid');
        const navItems = document.querySelectorAll('.nav-item');
        
        if (isActionClick) {
          // Redirect to Trajectory Analysis View
          if (mainGrid) {
            mainGrid.classList.remove('view-mode-projects', 'view-mode-interventions');
            mainGrid.classList.add('view-mode-trajectory');
          }
          navItems.forEach(n => n.classList.remove('active'));
          const trajNav = document.querySelector('.nav-item[data-target="view-trajectory"]');
          if (trajNav) trajNav.classList.add('active');
        } else {
          // Redirect to DETAILED ANALYSIS (Dashboard View)
          if (mainGrid) {
            mainGrid.classList.remove('view-mode-projects', 'view-mode-interventions', 'view-mode-trajectory');
          }
          navItems.forEach(n => n.classList.remove('active'));
          const dashboardNav = document.querySelector('.nav-item[data-target="view-dashboard"]');
          if (dashboardNav) dashboardNav.classList.add('active');
        }
        
        // Show loading state in detail panel
        const projectTitleEl = document.getElementById('valProjectTitle');
        if (projectTitleEl) projectTitleEl.innerHTML = 'Loading...';
        const projectGeoEl = document.getElementById('valProjectGeo');
        if (projectGeoEl) projectGeoEl.innerHTML = '--';
        document.getElementById('valProjectScore').textContent = '--';
        const chartEl = document.getElementById('trajectoryChart');
        if (chartEl) chartEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding: 40px; font-size: 13px;">Fetching trajectory data...</div>';
        const labelsEl = document.getElementById('chartXLabels');
        if (labelsEl) labelsEl.innerHTML = '';

        // Fetch project detail and update right panel if backend is up
        try {
          const detail = await API.getProjectDetails(row.dataset.id);
          const replay = await API.getProjectReplay(row.dataset.id);
          updateDetailPanel(detail, replay);
        } catch (e) {
          console.error('Failed to load project details:', e);
          if (projectTitleEl) projectTitleEl.innerHTML = '<span style="color:#ef4444;">Error Loading Project</span>';
          if (chartEl) chartEl.innerHTML = '<div style="color:#ef4444; text-align:center; padding: 40px; font-size: 13px;">Failed to load data. Please try again.</div>';
        }
      });
    });
  }

  function updateDetailPanel(detail, replay) {
    if (!detail) return;
    window.lastDetail = detail;
    window.lastReplay = replay;

    const projectTitleEl = document.getElementById('valProjectTitle');
    if (projectTitleEl) projectTitleEl.innerHTML = `${detail.project_name || '--'}`;
    
    const projectGeoEl = document.getElementById('valProjectGeo');
    if (projectGeoEl) projectGeoEl.innerHTML = `${detail.state || '--'} &bull; ${detail.sector || '--'} &bull; ${detail.ministry || '--'}`;
    
    const projectScoreEl = document.getElementById('valProjectScore');
    if (projectScoreEl) projectScoreEl.textContent = `${Math.round((detail.latest_prediction?.raw_prob || 0) * 100)}/100`;

    // Update AI Assistant Context
    SANKET_DATA.selectedProject = {
      name: detail.project_name || '--',
      score: Math.round((detail.latest_prediction?.raw_prob || 0) * 100),
      scoreMax: 100,
      severity: detail.current_risk_tier || '--',
      discrepancy: detail.current_trajectory_metrics?.Z_peer_V_fin ? detail.current_trajectory_metrics.Z_peer_V_fin.toFixed(2) : 0,
      physicalProgress: detail.approved_cost ? Math.round((detail.current_trajectory_metrics?.C_base || 0) / detail.approved_cost * 100) : 0,
      financialDrawdown: detail.current_trajectory_metrics?.financial_progress ? detail.current_trajectory_metrics.financial_progress.toFixed(2) : 0,
      spread: detail.current_trajectory_metrics?.schedule_deviation_months || 0,
      stagnation: { days: 0, chainage: '--' },
      sensors: {},
      causalAttribution: detail.top_explanations || []
    };

    // Detailed Metadata
    const valTotalObs = document.getElementById('valTotalObs');
    if (valTotalObs) valTotalObs.textContent = detail.total_observations || '--';
    const valApprovedCost = document.getElementById('valApprovedCost');
    if (valApprovedCost) valApprovedCost.textContent = detail.approved_cost ? `₹${detail.approved_cost.toLocaleString()}` : '--';
    const valStartMonth = document.getElementById('valStartMonth');
    if (valStartMonth) valStartMonth.textContent = detail.start_month || '--';
    const valEndMonth = document.getElementById('valEndMonth');
    if (valEndMonth) valEndMonth.textContent = detail.end_month || '--';
    const valSchedDev = document.getElementById('valSchedDev');
    if (valSchedDev) {
      const dev = detail.current_trajectory_metrics?.schedule_deviation_months;
      valSchedDev.textContent = dev != null ? `${dev > 0 ? '+' : ''}${dev} Months` : '--';
      if (dev > 0) valSchedDev.style.color = '#ef4444';
      else if (dev < 0) valSchedDev.style.color = '#10b981';
      else valSchedDev.style.color = '#94a3b8';
    }

    // Format trajectory chart from replay
    const trajectoryPills = document.getElementById('trajectoryPills');
    if (trajectoryPills && detail.latest_prediction) {
      if (detail.latest_prediction.risk_tier !== 'NORMAL' || detail.latest_prediction.alert) {
        trajectoryPills.style.display = 'flex';
        document.getElementById('valTriggerPoint').textContent = `Trigger: ${detail.latest_observation || 'Model'}`;
        const lead = detail.latest_prediction.lead_time_if_event || 3;
        document.getElementById('valAdvanceLead').textContent = `${lead} Mo Predictive Lead`;
      } else {
        trajectoryPills.style.display = 'none';
      }
    }

    const tl = replay?.timeline || [];
    if (tl.length > 0) {
      // Pick up to 6 points for the chart
      const points = tl.length > 6 ? tl.filter((_, i) => i % Math.ceil(tl.length / 5) === 0 || i === tl.length - 1) : tl;

      SANKET_DATA.trajectoryChart.labels = points.map(p => `M${p.observation_number || 0}`);
      SANKET_DATA.trajectoryChart.target = points.map(p => Math.min(100, ((p.observation_number || 1) / (detail.total_observations || 1)) * 100)); // Ideal linear progress
      SANKET_DATA.trajectoryChart.contractorReport = points.map(p => p.financial_progress || 0);
      SANKET_DATA.trajectoryChart.sanketTelemetry = points.map(p => (p.financial_progress || 0) * (1 - (p.pred_prob || 0)));

      SANKET_DATA.trajectoryChart.anomalyPoint = null;
      SANKET_DATA.trajectoryChart.discrepancyGap = null;

      const chartEl = document.getElementById('trajectoryChart');
      if (chartEl) chartEl.innerHTML = ''; // clear loading
      Charts.renderTrajectoryChart('trajectoryChart', 'chartXLabels', SANKET_DATA.trajectoryChart);
    } else {
      const chartEl = document.getElementById('trajectoryChart');
      if (chartEl) chartEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding: 40px; font-size: 13px;">No timeline data available for this project.</div>';
      const labelsEl = document.getElementById('chartXLabels');
      if (labelsEl) labelsEl.innerHTML = '';
    }

    // Execution Disparity (Dual Radial Gauge)
    const trajMetrics = detail.current_trajectory_metrics || {};
    const score = Math.round(trajMetrics.trajectory_risk_score || 0);
    const execScoreLabel = document.getElementById('execScoreLabel');
    if (execScoreLabel) execScoreLabel.textContent = `Score / 100`;

    const dualGaugeContainer = document.getElementById('dualGaugeContainer');
    if (dualGaugeContainer) {
      const riskColor = score > 80 ? '#ef4444' : score > 50 ? '#f59e0b' : '#10b981';
      const finProg = Math.min(100, Math.max(0, trajMetrics.financial_progress || 0));
      const finColor = '#0ea5e9';
      
      const rOuter = 52;
      const cOuter = 2 * Math.PI * rOuter;
      const offsetOuter = cOuter - ((score / 100) * cOuter);
      
      const rInner = 38;
      const cInner = 2 * Math.PI * rInner;
      const offsetInner = cInner - ((finProg / 100) * cInner);

      dualGaugeContainer.innerHTML = `
        <div style="position: relative; width: 140px; height: 140px;">
          <svg viewBox="0 0 140 140" style="width: 100%; height: 100%; transform: rotate(-90deg);">
            <!-- Outer Ring (Risk) -->
            <circle cx="70" cy="70" r="${rOuter}" fill="none" stroke="rgba(0,0,0,0.05)" stroke-width="12" />
            <circle cx="70" cy="70" r="${rOuter}" fill="none" stroke="${riskColor}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${cOuter}" stroke-dashoffset="${offsetOuter}" style="transition: stroke-dashoffset 1s ease-out; filter: drop-shadow(0 0 6px ${riskColor}80);" />
            <!-- Inner Ring (Financial Progress) -->
            <circle cx="70" cy="70" r="${rInner}" fill="none" stroke="rgba(0,0,0,0.05)" stroke-width="12" />
            <circle cx="70" cy="70" r="${rInner}" fill="none" stroke="${finColor}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${cInner}" stroke-dashoffset="${offsetInner}" style="transition: stroke-dashoffset 1s ease-out; filter: drop-shadow(0 0 4px ${finColor}80);" />
          </svg>
          <div style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: flex; flex-direction: column; justify-content: center; align-items: center;">
            <span style="font-size: 24px; font-weight: 800; font-family: 'JetBrains Mono', monospace; color: #0f172a;">${score}</span>
            <span style="font-size: 9px; font-weight: 600; color: #64748b; letter-spacing: 1px;">RISK</span>
          </div>
        </div>
        <div style="display: flex; flex-direction: column; gap: 12px; margin-left: 20px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; background: ${riskColor}; box-shadow: 0 0 8px ${riskColor}80;"></div>
            <div>
              <div style="font-size: 10px; color: #64748b; font-weight: 600; text-transform: uppercase;">Trajectory Risk</div>
              <div style="font-size: 14px; color: #0f172a; font-weight: 800; font-family: 'JetBrains Mono', monospace;">${score}/100</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; background: ${finColor}; box-shadow: 0 0 8px ${finColor}80;"></div>
            <div>
              <div style="font-size: 10px; color: #64748b; font-weight: 600; text-transform: uppercase;">Fin. Progress</div>
              <div style="font-size: 14px; color: #0f172a; font-weight: 800; font-family: 'JetBrains Mono', monospace;">${trajMetrics.financial_progress != null ? finProg.toFixed(1) + '%' : '--'}</div>
            </div>
          </div>
        </div>
      `;
    }

    // Trajectory Kinematics
    const getKinematicMeter = (val, colorClass) => {
      if (val === null || val === undefined) {
        return `<div class="sensor-meter"><div class="meter-track"><div class="meter-fill" style="height:0%; background:transparent"></div></div><span class="meter-val" style="font-size:11px; color:#64748b;">--</span></div>`;
      }
      const v = parseFloat(val) || 0;
      const height = Math.min(100, Math.max(0, 50 + (v * 2)));
      let colorOverride = '';
      if (colorClass === 'meter-cyan' && v < 0) colorOverride = 'background: #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);';
      else if (colorClass === 'meter-green' && v < 0) colorOverride = 'background: #ef4444; box-shadow: 0 0 10px rgba(239, 68, 68, 0.4);';
      const displayVal = Math.abs(v) > 99 ? v.toFixed(1) : v.toFixed(3);
      return `<div class="sensor-meter"><div class="meter-track"><div class="meter-fill ${colorClass}" style="height:${height}%; ${colorOverride}"></div></div><span class="meter-val" style="font-size:9.5px; letter-spacing:-0.2px;">${displayVal}</span></div>`;
    };

    const kinematicsHtml = `
      ${getKinematicMeter(trajMetrics.V_fin_1m, 'meter-cyan')}
      ${getKinematicMeter(trajMetrics.V_fin_3m, 'meter-amber')}
      ${getKinematicMeter(trajMetrics.A_fin, 'meter-green')}
      ${getKinematicMeter(trajMetrics.EWMA_V_fin, 'meter-cyan')}
    `;
    const kinematicsMeters = document.getElementById('kinematicsMeters');
    if (kinematicsMeters) kinematicsMeters.innerHTML = kinematicsHtml;

    // Top Explanations
    const causalConfidence = document.getElementById('causalConfidence');
    if (causalConfidence) {
      const p = detail.latest_prediction?.pred_prob || 0;
      const confidence = Math.max(p, 1 - p) * 100;
      causalConfidence.textContent = `${confidence.toFixed(1)}% Confidence`;
    }
    const explanations = detail.top_explanations || [];
    const maxContrib = Math.max(...explanations.map(e => Math.abs(e.contribution || 0)), 0.01);
    const factorsHtml = explanations.map((exp, idx) => {
      const c = exp.contribution || 0;
      const pct = (Math.abs(c) / maxContrib) * 100;
      const color = c >= 0 ? '#ef4444' : '#10b981';
      return `
        <div style="margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; font-size: 10px; margin-bottom: 3px;">
            <span style="font-weight: 800; color: #475569; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 70%;">${(exp.feature || '').toUpperCase()}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: ${color};">${c >= 0 ? '+' : ''}${(c * 100).toFixed(1)}%</span>
          </div>
          <div style="width: 100%; height: 6px; background: #f1f5f9; border-radius: 3px; overflow: hidden;">
            <div style="width: ${pct}%; height: 100%; background: ${color}; border-radius: 3px; transition: width 0.6s ease;"></div>
          </div>
          <div style="font-size: 9px; color: #94a3b8; margin-top: 3px; line-height: 1.2;">${exp.explanation || ''}</div>
        </div>
      `;
    }).join('');
    const causalFactors = document.getElementById('causalFactors');
    if (causalFactors) causalFactors.innerHTML = factorsHtml || '<div style="color:#94a3b8; font-size:11px;">No causal factors available.</div>';
    
    // Unhide causal card if hidden
    const causalCard = document.getElementById('causalCard');
    if (causalCard && factorsHtml) {
      causalCard.style.display = 'block';
    } else if (causalCard) {
      causalCard.style.display = 'none';
    }

    // Fetch and render Timeline
    const timelineCard = document.getElementById('timelineCard');
    const projectTimeline = document.getElementById('projectTimeline');
    if (timelineCard && projectTimeline) {
      projectTimeline.innerHTML = '<div style="color:#94a3b8; font-size: 11px;">Loading timeline...</div>';
      timelineCard.style.display = 'block';
      
      API.getProjectTimeline(detail.project_id)
        .then(data => {
          if (!data || !data.timeline || data.timeline.length === 0) {
            projectTimeline.innerHTML = '<div style="color:#94a3b8; font-size: 11px;">No historical milestones available.</div>';
            return;
          }
          
          const milestones = [];
          let lastTier = null;
          data.timeline.forEach((point, idx) => {
            const isFirst = idx === 0;
            const isLast = idx === data.timeline.length - 1;
            const changedTier = point.risk_tier !== lastTier && lastTier !== null;
            
            if (isFirst || isLast || changedTier) {
              milestones.push({...point, isFirst, isLast, changedTier});
              lastTier = point.risk_tier;
            }
          });
          
          projectTimeline.innerHTML = milestones.map((m, i) => {
            const color = m.risk_tier === 'ESCALATE' ? '#ef4444' : (m.risk_tier === 'REVIEW' || m.risk_tier === 'WATCH' ? '#f59e0b' : '#10b981');
            const dateStr = m.reporting_month;
            let title = '';
            if (m.isFirst) title = 'Project Inception';
            else if (m.isLast) title = 'Current State';
            else title = `Shifted to ${m.risk_tier}`;
            
            return `
              <div style="display: flex; gap: 12px; position: relative;">
                ${i !== milestones.length - 1 ? '<div style="position: absolute; left: 5px; top: 12px; bottom: -8px; width: 2px; background: #e5e5e5;"></div>' : ''}
                <div style="width: 12px; height: 12px; border-radius: 50%; background: ${color}; margin-top: 2px; z-index: 1;"></div>
                <div style="padding-bottom: 12px;">
                  <div style="font-size: 11px; font-weight: 700; color: #000000;">${title}</div>
                  <div style="font-size: 9px; color: #525252; font-family: 'JetBrains Mono', monospace; margin-top: 3px;">${dateStr} • Month ${m.observation_number} • Cost: ₹${m.C_base || 0}Cr</div>
                </div>
              </div>
            `;
          }).join('');
        })
        .catch(err => {
          projectTimeline.innerHTML = '<div style="color:#ef4444; font-size: 11px;">Failed to load timeline.</div>';
        });
    }
  }

  initData();

  /* ── Re-render charts on resize (debounced) ─────────── */
  let resizeTimer;
  window.addEventListener('resize', () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      Charts.renderSparkline('sparkline-total', SANKET_DATA.sparkline, '#10b981');
      Charts.renderTrajectoryChart('trajectoryChart', 'chartXLabels', SANKET_DATA.trajectoryChart);
    }, 200);
  });

  /* ── Mobile sidebar toggle ─────────────────────────── */
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  const menuBtn = document.getElementById('mobileMenuBtn');

  function toggleSidebar() {
    sidebar.classList.toggle('open');
    overlay.classList.toggle('open');
  }

  menuBtn?.addEventListener('click', toggleSidebar);
  overlay?.addEventListener('click', toggleSidebar);



  /* ── Nav item active state & View Switching ──────────────────────────── */
  const mainGrid = document.querySelector('.dashboard-grid');
  const navItems = document.querySelectorAll('.nav-item');
  
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      navItems.forEach(n => n.classList.remove('active'));
      item.classList.add('active');

      const targetView = item.getAttribute('data-target');
      window.currentView = targetView;

      if (targetView && mainGrid) {
        // Remove existing view classes
        mainGrid.classList.remove('view-mode-dashboard', 'view-mode-projects', 'view-mode-trajectory', 'view-mode-interventions');

        // Add specific view class based on the target
        if (targetView === 'view-dashboard') {
          // If dashboard, just clear classes to show default 3-column view
        } else if (targetView === 'view-projects' || targetView === 'view-interventions' || targetView === 'view-completed') {
          if (targetView === 'view-interventions') {
            mainGrid.classList.add('view-mode-interventions');
            mainGrid.classList.remove('view-mode-projects');
          } else {
            mainGrid.classList.add('view-mode-projects');
            mainGrid.classList.remove('view-mode-interventions');
          }
          
          // Set Titles and Filters
          const title = document.querySelector('.projects-title');
          const riskFilter = document.getElementById('projectRiskFilter');
          const filterWrap = riskFilter ? riskFilter.parentElement : null;

          if (title) {
            if (targetView === 'view-interventions') {
              title.innerHTML = 'RISK<br/>INTERVENTIONS';
              if (riskFilter) riskFilter.value = 'ESCALATE';
              if (filterWrap) filterWrap.style.display = '';
            } else if (targetView === 'view-completed') {
              title.innerHTML = 'COMPLETED<br/>PROJECTS';
              if (filterWrap) filterWrap.style.display = 'none';
            } else {
              title.innerHTML = 'ONGOING<br/>PROJECTS';
              if (riskFilter) riskFilter.value = 'ALL';
              if (filterWrap) filterWrap.style.display = '';
            }
          }
          
          // Fetch appropriate datasets
          if (targetView === 'view-completed') {
            const listEl = document.querySelector('.project-list');
            if (listEl) listEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding:20px; font-size:13px;">Loading Historical Projects...</div>';
            
            API.getProjects('', '', '', 5000, 0, true).then(results => {
              SANKET_DATA.projects = (results.projects || []).map(p => ({
                  id: p.project_id,
                  name: p.project_name,
                  score: Math.round(p.latest_risk_tier === 'NORMAL' ? 0 : (p.latest_risk || 0) * 100),
                  severity: p.latest_risk_tier || 'UNKNOWN',
                  severityClass: (p.latest_risk_tier || 'unknown').toLowerCase(),
                  location: `${p.state || '--'} • ${p.sector || '--'}`,
                  ministry: p.ministry || '--',
                  progress: p.financial_progress || 0,
                  lastReported: p.latest_observation || 'Unknown',
                  variance: p.schedule_deviation_months != null ? p.schedule_deviation_months : null,
                  varianceLabel: 'Months',
                  value: Math.round((p.baseline_cost || p.approved_cost || 0))
              }));
              renderProjectCards();
            });
          } else {
            // Re-fetch only if we previously fetched historical projects (which changes SANKET_DATA.projects)
            // But doing it unconditionally is safer and fast because the local limit is 5000.
            if (SANKET_DATA.projects.length > SANKET_DATA.portfolio.active_project_count) {
                const listEl = document.querySelector('.project-list');
                if (listEl) listEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding:20px; font-size:13px;">Loading Ongoing Projects...</div>';
                
                API.getProjects('', '', '', 5000, 0, false).then(results => {
                  SANKET_DATA.projects = (results.projects || []).map(p => ({
                      id: p.project_id,
                      name: p.project_name,
                      score: Math.round(p.latest_risk_tier === 'NORMAL' ? 0 : (p.latest_risk || 0) * 100),
                      severity: p.latest_risk_tier || 'UNKNOWN',
                      severityClass: (p.latest_risk_tier || 'unknown').toLowerCase(),
                      location: `${p.state || '--'} • ${p.sector || '--'}`,
                      ministry: p.ministry || '--',
                      progress: p.financial_progress || 0,
                      lastReported: p.latest_observation || 'Unknown',
                      variance: p.schedule_deviation_months != null ? p.schedule_deviation_months : null,
                      varianceLabel: 'Months',
                      value: Math.round((p.baseline_cost || p.approved_cost || 0))
                  }));
                  if (riskFilter) riskFilter.dispatchEvent(new Event('change'));
                });
            } else {
                if (riskFilter) riskFilter.dispatchEvent(new Event('change'));
            }
          }
          
        } else if (targetView === 'view-trajectory') {
          mainGrid.classList.add('view-mode-trajectory');
        }
      }
    });
  });

  /* ── Search functionality ────────────────────────────── */
  const searchInput = document.getElementById('searchInput');
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener('input', (e) => {
      const term = e.target.value.trim();
      clearTimeout(debounceTimer);
      
      debounceTimer = setTimeout(async () => {
        const listEl = document.querySelector('.project-list');
        if (listEl) listEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding:20px; font-size:13px;">Searching...</div>';
        
        try {
          if (!term) {
            const projectsRes = await API.getProjects('', '', '', 5000, 0);
            SANKET_DATA.projects = (projectsRes.projects || []).map(p => ({
              id: p.project_id,
              name: p.project_name,
              score: Math.round(p.latest_risk_tier === 'NORMAL' ? 0 : (p.latest_risk || 0) * 100),
              severity: p.latest_risk_tier || 'UNKNOWN',
              severityClass: (p.latest_risk_tier || 'unknown').toLowerCase(),
              location: `${p.state || '--'} • ${p.sector || '--'}`,
              ministry: p.ministry || '--',
              progress: p.financial_progress || 0,
              lastReported: p.latest_observation || 'Unknown',
              variance: p.schedule_deviation_months != null ? p.schedule_deviation_months : null,
              varianceLabel: 'Months',
              value: Math.round((p.baseline_cost || p.approved_cost || 0))
            }));
            renderProjectCards();
            return;
          }
          
          const results = await API.getProjects(term);
          SANKET_DATA.projects = (results.projects || []).map(p => ({
            id: p.project_id,
            name: p.project_name,
            score: Math.round(p.latest_risk_tier === 'NORMAL' ? 0 : (p.latest_risk || 0) * 100),
            severity: p.latest_risk_tier || 'UNKNOWN',
            severityClass: (p.latest_risk_tier || 'unknown').toLowerCase(),
            location: `${p.state || '--'} • ${p.sector || '--'}`,
            ministry: p.ministry || '--',
            progress: p.financial_progress || 0,
            lastReported: p.latest_observation || 'Unknown',
            variance: p.schedule_deviation_months != null ? p.schedule_deviation_months : null,
            varianceLabel: 'Months',
            value: Math.round((p.baseline_cost || p.approved_cost || 0))
          }));
          
          renderProjectCards();
          
          if (SANKET_DATA.projects.length === 0 && listEl) {
            listEl.innerHTML = '<div style="color:#94a3b8; text-align:center; padding:20px; font-size:13px;">No projects found.</div>';
          } else {
            const firstProject = document.querySelector('.project-card');
            if (firstProject) firstProject.click();
          }
          
        } catch (error) {
          console.error('Search failed:', error);
          if (listEl) listEl.innerHTML = '<div style="color:#ef4444; text-align:center; padding:20px; font-size:13px;">Search error.</div>';
        }
      }, 400);
    });
  }

  /* ── Local Table Search & Filter ───────────────────────── */
  const localSearch = document.getElementById('projectSearchInput');
  const riskFilter = document.getElementById('projectRiskFilter');
  const sortFilter = document.getElementById('projectSortFilter');
  if (localSearch) localSearch.addEventListener('input', renderProjectCards);
  if (riskFilter) riskFilter.addEventListener('change', renderProjectCards);
  if (sortFilter) sortFilter.addEventListener('change', renderProjectCards);

  /* ── Export CSV Logic ───────────────────────────────── */
  const btnExport = document.getElementById('btnExportReport');
  if (btnExport) {
    btnExport.addEventListener('click', () => {
      const detail = window.lastDetail;
      const replay = window.lastReplay;
      if (!detail) return;

      let csv = 'Month,Target_CBase,Financial_Progress,Sanket_Telemetry_Risk,Schedule_Deviation\\n';
      const tl = replay?.timeline || [];
      tl.forEach(p => {
        const t = (p.C_base || 0).toFixed(2);
        const fp = (p.financial_progress || 0).toFixed(2);
        const risk = (p.pred_prob || 0).toFixed(3);
        const sd = (p.schedule_deviation_months || 0).toFixed(1);
        csv += `M${p.observation_number || 0},${t},${fp},${risk},${sd}\\n`;
      });

      const blob = new Blob([csv], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.setAttribute('hidden', '');
      a.setAttribute('href', url);
      a.setAttribute('download', `${detail.project_id || 'project'}_telemetry.csv`);
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    });
  }

  /* ── Initialize AI Assistant ────────────────────────── */
  // Assistant.init();

  /* ── Live clock in telemetry ────────────────────────── */
  function updateTelemetry() {
    const now = new Date();
    const months = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
    const day = String(now.getDate()).padStart(2, '0');
    const month = months[now.getMonth()];
    const year = now.getFullYear();
    const h = String(now.getHours()).padStart(2, '0');
    const m = String(now.getMinutes()).padStart(2, '0');
    const telEl = document.querySelector('.telemetry-text');
    if (telEl) {
      telEl.innerHTML = `Live Telemetry • ${ day } ${ month } <br />${ year }, ${ h }:${ m } Local`;
    }
  }
  updateTelemetry();
  setInterval(updateTelemetry, 30000);
});

