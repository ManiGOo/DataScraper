let currentCampaignId = null;
let pollInterval = null;
let currentLeadsData = [];

function setPreset(region) {
    document.getElementById('targetRegion').value = region;
}

async function startSdrCampaign() {
    const region = document.getElementById('targetRegion').value.trim();
    const sector = document.getElementById('targetSector').value;
    const maxProspects = parseInt(document.getElementById('maxProspects').value);

    if (!region) {
        alert("Please specify a target region.");
        return;
    }

    const btnLaunch = document.getElementById('btnLaunch');
    const progressSection = document.getElementById('progressSection');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const terminalLog = document.getElementById('terminalLog');

    btnLaunch.disabled = true;
    btnLaunch.style.opacity = '0.6';
    progressSection.classList.remove('hidden');
    progressBar.style.width = '5%';
    progressPercent.innerText = '5%';
    terminalLog.innerHTML = `<div>> Launching AI Lead Scanner for ${region}...</div>`;

    try {
        const response = await fetch('/api/sdr/campaigns/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_region: region,
                target_sector: sector,
                max_results: maxProspects
            })
        });

        if (!response.ok) {
            throw new Error("Failed to initialize AI campaign.");
        }

        const data = await response.json();
        currentCampaignId = data.campaign_id;
        
        pollInterval = setInterval(checkCampaignStatus, 2000);
    } catch (err) {
        alert("Error: " + err.message);
        btnLaunch.disabled = false;
        btnLaunch.style.opacity = '1';
    }
}

async function checkCampaignStatus() {
    if (!currentCampaignId) return;

    try {
        const response = await fetch(`/api/sdr/campaigns/status/${currentCampaignId}`);
        if (!response.ok) return;

        const data = await response.json();
        currentLeadsData = data.leads || [];

        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const terminalLog = document.getElementById('terminalLog');
        const progressTitle = document.getElementById('progressTitle');

        let pct = 0;
        if (data.total_expected > 0) {
            pct = Math.min(100, Math.floor((data.progress / data.total_expected) * 100));
        }

        progressBar.style.width = `${pct}%`;
        progressPercent.innerText = `${pct}%`;

        terminalLog.innerHTML = `<div>> Status: ${data.status} | Qualified: ${data.progress} / ${data.total_expected} prospects</div>`;

        if (data.status === 'RUNNING') {
            progressTitle.innerText = "Crawling & AI Scoring eQMS Prospects...";
            renderLeadsList(currentLeadsData);
        } else if (data.status === 'COMPLETED') {
            clearInterval(pollInterval);
            progressTitle.innerText = "Scan Completed & Qualified";
            progressBar.style.width = '100%';
            progressPercent.innerText = '100%';
            resetUI();
            renderLeadsList(currentLeadsData);
        } else if (data.status === 'FAILED') {
            clearInterval(pollInterval);
            alert("Scan failed: " + data.error_message);
            resetUI();
        }
    } catch (err) {
        console.error("Polling error:", err);
    }
}

function resetUI() {
    const btnLaunch = document.getElementById('btnLaunch');
    btnLaunch.disabled = false;
    btnLaunch.style.opacity = '1';
}

function renderLeadsList(leads) {
    const leadsList = document.getElementById('leadsList');
    const summarySubtitle = document.getElementById('summarySubtitle');

    if (!leads || leads.length === 0) {
        leadsList.innerHTML = `
            <div class="card" style="text-align:center; padding:3rem; color:var(--text-muted);">
                <p>Scanning FDA registrations and web text for target prospects...</p>
            </div>
        `;
        return;
    }

    summarySubtitle.innerText = `Found ${leads.length} qualified Life Science prospects. Sorted by QMS Fit Score.`;

    leadsList.innerHTML = leads.map(lead => {
        const fitScore = lead.qms_fit_score || 70;
        const scoreClass = fitScore >= 80 ? 'score-high' : 'score-med';
        const drivers = lead.compliance_drivers || [];

        const contactsHtml = (lead.contacts || []).map(contact => `
            <div class="contact-card">
                <div class="contact-info">
                    <h4>${contact.name}</h4>
                    <p>${contact.title}</p>
                    <div class="email-row">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                        ${contact.email}
                        <span style="font-size:0.675rem; background:rgba(16, 185, 129, 0.2); color:#34d399; padding:0.1rem 0.4rem; border-radius:4px;">${contact.verification_status}</span>
                    </div>
                </div>
                <button class="btn-view-seq" onclick="openSequenceModal(${lead.id}, ${contact.id})">
                    View AI Email Sequence →
                </button>
            </div>
        `).join('');

        return `
            <div class="lead-card">
                <div class="lead-top">
                    <div>
                        <div class="company-name">
                            ${lead.name}
                            <a href="${lead.website_url}" target="_blank" style="font-size:0.8rem; color:var(--text-secondary); text-decoration:none;">↗</a>
                        </div>
                        <div class="lead-meta">
                            <span class="meta-item">📍 ${lead.region}</span>
                            <span class="meta-item">🏷️ ${lead.industry_subsector}</span>
                            <span class="meta-item">👥 ${lead.employee_range}</span>
                            <span class="meta-item" style="color:var(--accent-fuchsia);">🔍 ${lead.source}</span>
                        </div>
                    </div>
                    <div class="score-pill ${scoreClass}">
                        QMS FIT: ${fitScore}/100
                    </div>
                </div>

                <div class="driver-tags">
                    ${drivers.map(d => `<span class="driver-badge">${d}</span>`).join('')}
                </div>

                <div class="summary-box">
                    ${lead.summary}
                </div>

                <div style="font-size:0.8rem; font-weight:600; color:var(--text-secondary); margin-bottom:0.5rem; uppercase;">Decision Maker Contacts:</div>
                <div class="contacts-grid">
                    ${contactsHtml}
                </div>
            </div>
        `;
    }).join('');
}

function openSequenceModal(leadId, contactId) {
    const lead = currentLeadsData.find(l => l.id === leadId);
    if (!lead) return;
    const contact = (lead.contacts || []).find(c => c.id === contactId);
    if (!contact) return;

    document.getElementById('modalContactName').innerText = `${contact.name} - ${lead.name}`;
    document.getElementById('modalContactTitle').innerText = `${contact.title} | ${contact.email}`;

    const seqs = contact.sequences || [];
    const seqContent = document.getElementById('modalSequenceContent');

    if (seqs.length === 0) {
        seqContent.innerHTML = `<p style="color:var(--text-muted);">No sequence generated.</p>`;
    } else {
        seqContent.innerHTML = seqs.map(s => `
            <div class="seq-step">
                <div class="seq-step-title">Step ${s.step_number} Email Sequence</div>
                <div class="seq-subject">Subject: ${s.subject}</div>
                <div class="seq-body">${s.body_text}</div>
            </div>
        `).join('');
    }

    document.getElementById('sequenceModal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('sequenceModal').classList.add('hidden');
}

function exportData(format) {
    if (!currentCampaignId) {
        alert("Please run an AI SDR campaign first.");
        return;
    }
    window.location.href = `/api/sdr/export/${currentCampaignId}/${format}`;
}
