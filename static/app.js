let currentCampaignId = null;
let pollInterval = null;
let currentLeadsData = [];

// Searchable Custom Multi-Select Dropdown Functions
function toggleRegistryDropdown(event) {
    if (event) event.stopPropagation();
    const menu = document.getElementById('registryDropdownMenu');
    menu.classList.toggle('hidden');
    if (!menu.classList.contains('hidden')) {
        document.getElementById('registrySearchInput').focus();
    }
}

document.addEventListener('click', function(event) {
    const menu = document.getElementById('registryDropdownMenu');
    const btn = document.getElementById('registryDropdownBtn');
    if (menu && !menu.classList.contains('hidden')) {
        if (!menu.contains(event.target) && !btn.contains(event.target)) {
            menu.classList.add('hidden');
        }
    }
});

function filterRegistryOptions() {
    const query = document.getElementById('registrySearchInput').value.toLowerCase();
    const items = document.querySelectorAll('.dropdown-option-item');
    items.forEach(item => {
        const text = item.innerText.toLowerCase();
        if (text.includes(query)) {
            item.style.display = 'flex';
        } else {
            item.style.display = 'none';
        }
    });
}

function toggleSources(masterCb) {
    const checkboxes = document.querySelectorAll('.src-checkbox');
    if (masterCb.checked) {
        checkboxes.forEach(cb => cb.checked = false);
    }
    updateDropdownButtonText();
}

function updateSourceCheckboxes() {
    const masterCb = document.getElementById('srcALL');
    const checkedboxes = document.querySelectorAll('.src-checkbox:checked');
    if (checkedboxes.length > 0) {
        masterCb.checked = false;
    } else {
        masterCb.checked = true;
    }
    updateDropdownButtonText();
}

function updateDropdownButtonText() {
    const textSpan = document.getElementById('selectedRegistriesText');
    const masterCb = document.getElementById('srcALL');
    const checkedboxes = document.querySelectorAll('.src-checkbox:checked');

    if (masterCb.checked || checkedboxes.length === 0) {
        textSpan.innerText = "🌐 All Global Registries (Recommended)";
    } else if (checkedboxes.length === 1) {
        const labelText = checkedboxes[0].parentElement.innerText.trim();
        textSpan.innerText = labelText;
    } else {
        textSpan.innerText = `${checkedboxes.length} Registries Selected`;
    }
}

function setPreset(region) {
    document.getElementById('targetRegion').value = region;
    
    // Smart Registry Auto-Suggest
    const regLower = region.lower ? region.lower() : region.toLowerCase();
    const srcALL = document.getElementById('srcALL');
    const srcCDSCO = document.getElementById('srcCDSCO');
    const srcEUDAMED = document.getElementById('srcEUDAMED');
    const srcFDA = document.getElementById('srcFDA');
    const srcWHO = document.getElementById('srcWHO');

    if (regLower.includes('india')) {
        srcALL.checked = false;
        srcCDSCO.checked = true;
        srcEUDAMED.checked = false;
        srcFDA.checked = false;
        srcWHO.checked = false;
    } else if (regLower.includes('europe') || regLower.includes('uk') || regLower.includes('germany')) {
        srcALL.checked = false;
        srcCDSCO.checked = false;
        srcEUDAMED.checked = true;
        srcFDA.checked = false;
        srcWHO.checked = false;
    } else if (regLower.includes('north america') || regLower.includes('usa')) {
        srcALL.checked = false;
        srcCDSCO.checked = false;
        srcEUDAMED.checked = false;
        srcFDA.checked = true;
        srcWHO.checked = false;
    } else if (regLower.includes('middle east')) {
        srcALL.checked = false;
        srcCDSCO.checked = false;
        srcEUDAMED.checked = false;
        srcFDA.checked = false;
        srcWHO.checked = true;
    } else {
        srcALL.checked = true;
        document.querySelectorAll('.src-checkbox').forEach(cb => cb.checked = false);
    }
    updateDropdownButtonText();
}

async function startSdrCampaign() {
    const region = document.getElementById('targetRegion').value.trim();
    const sector = document.getElementById('targetSector').value;
    const maxProspects = parseInt(document.getElementById('maxProspects').value);

    if (!region) {
        alert("Please specify a target region.");
        return;
    }

    // Collect selected regulatory sources
    let selectedSources = [];
    if (document.getElementById('srcALL').checked) {
        selectedSources = ["ALL"];
    } else {
        document.querySelectorAll('.src-checkbox:checked').forEach(cb => selectedSources.push(cb.value));
        if (selectedSources.length === 0) selectedSources = ["ALL"];
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
    terminalLog.innerHTML = `<div>> Querying Regulatory Registries (${selectedSources.join(', ')}) for ${region}...</div>`;

    try {
        const response = await fetch('/api/sdr/campaigns/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                target_region: region,
                target_sector: sector,
                max_results: maxProspects,
                selected_sources: selectedSources
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
            progressTitle.innerText = "Mining Registries & AI Scoring Prospects...";
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
                <p>Mining selected government registries and web text for target prospects...</p>
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
