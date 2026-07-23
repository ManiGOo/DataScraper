let currentTaskId = null;
let pollInterval = null;
let conversationHistory = [];
let authToken = localStorage.getItem('datascraper_token') || null;

document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
});

// Auth Functions
function checkAuthStatus() {
    if (!authToken) {
        window.location.href = '/login';
        return;
    }

    fetch('/api/auth/me', {
        headers: { 'Authorization': `Bearer ${authToken}` }
    })
    .then(res => {
        if (!res.ok) throw new Error('Token expired');
        return res.json();
    })
    .then(user => {
        renderLoggedInUI(user.email);
    })
    .catch(() => {
        logoutUser();
    });
}

function renderLoggedInUI(email) {
    document.getElementById('loggedInNav').classList.remove('hidden');
    document.getElementById('userEmailBadge').innerText = email;
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.add('hidden');
}

function logoutUser() {
    authToken = null;
    localStorage.removeItem('datascraper_token');
    window.location.href = '/login';
}



// AI Helper Functions
function setQuery(queryText) {
    const queryInput = document.getElementById('queryInput');
    queryInput.value = queryText;
    queryInput.focus();
    queryInput.style.borderColor = 'var(--accent-cyan)';
    queryInput.style.boxShadow = '0 0 20px rgba(6, 182, 212, 0.4)';
    setTimeout(() => { 
        queryInput.style.borderColor = ''; 
        queryInput.style.boxShadow = ''; 
    }, 1500);

    document.querySelector('.search-card').scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function clearAiMemory() {
    conversationHistory = [];
    document.getElementById('aiResponseContainer').classList.add('hidden');
    document.getElementById('btnClearMemory').classList.add('hidden');
    document.getElementById('aiPromptInput').value = '';
}

async function generateAiQuery() {
    const promptInput = document.getElementById('aiPromptInput');
    const btnAiGenerate = document.getElementById('btnAiGenerate');
    const prompt = promptInput.value.trim();

    if (!prompt) {
        alert("Please enter a plain English description for the AI Assistant.");
        return;
    }

    const origText = btnAiGenerate.innerHTML;
    btnAiGenerate.disabled = true;
    btnAiGenerate.innerHTML = `<span>Analyzing Request...</span>`;

    try {
        const response = await fetch('/api/generate-query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                prompt: prompt,
                history: conversationHistory 
            })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to generate AI query strategies.");
        }

        const data = await response.json();
        renderAiResults(data);

        conversationHistory.push({ role: "user", content: prompt });
        conversationHistory.push({ 
            role: "assistant", 
            content: `Reasoning: ${data.reasoning}\nQueries Generated: ${JSON.stringify(data.queries)}` 
        });

        document.getElementById('btnClearMemory').classList.remove('hidden');

    } catch (err) {
        alert("AI Search Agent Error: " + err.message);
    } finally {
        btnAiGenerate.disabled = false;
        btnAiGenerate.innerHTML = origText;
    }
}

function renderAiResults(data) {
    const container = document.getElementById('aiResponseContainer');
    const reasoningText = document.getElementById('aiReasoningText');
    const queriesList = document.getElementById('aiQueriesList');

    reasoningText.innerText = data.reasoning || "Analyzed user intent and formulated query parameters.";

    const queries = data.queries || [];
    if (queries.length === 0) {
        queriesList.innerHTML = `<div class="text-muted">No query strategies returned.</div>`;
    } else {
        queriesList.innerHTML = queries.map((q, idx) => {
            const title = q.title || `Strategy #${idx + 1}`;
            const desc = q.description || 'Optimized GitHub query option.';
            const queryStr = q.query || '';

            return `
                <div class="query-option-card">
                    <div>
                        <div class="query-card-header">
                            <h4>${title}</h4>
                        </div>
                        <p class="query-desc">${desc}</p>
                        <div class="query-code-preview">${queryStr}</div>
                    </div>
                    <button type="button" class="btn-use-query" onclick="setQuery('${escapeQuotes(queryStr)}')">
                        <span>🚀 Use This Query</span>
                    </button>
                </div>
            `;
        }).join('');
    }

    container.classList.remove('hidden');
    container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function escapeQuotes(str) {
    if (!str) return '';
    return str.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

async function startScraping() {
    const query = document.getElementById('queryInput').value.trim();
    const maxResults = parseInt(document.getElementById('maxResults').value);

    if (!query) {
        alert("Please enter a valid GitHub search query.");
        return;
    }

    const btnScrape = document.getElementById('btnScrape');
    const progressSection = document.getElementById('progressSection');
    const resultsSection = document.getElementById('resultsSection');
    const terminalLog = document.getElementById('terminalLog');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');
    const spinner = document.getElementById('spinner');
    const checkIcon = document.getElementById('checkIcon');
    const progressTitle = document.getElementById('progressTitle');

    btnScrape.disabled = true;
    btnScrape.style.opacity = '0.6';

    spinner.classList.remove('hidden');
    checkIcon.classList.add('hidden');
    progressTitle.innerText = "Scraping Execution Progress";

    progressSection.classList.remove('hidden');
    resultsSection.classList.add('hidden');

    progressBar.classList.remove('completed');
    progressPercent.classList.remove('completed');
    progressBar.style.width = '0%';
    progressPercent.innerText = '0%';
    terminalLog.innerHTML = `<div class="log-line text-muted">[System] Initiating scrape task for query: "${query}"...</div>`;

    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    try {
        const response = await fetch('/api/jobs/start', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ query: query, max_results: maxResults })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to start scraping task.");
        }

        const data = await response.json();
        currentTaskId = data.job_id;
        
        pollInterval = setInterval(checkStatus, 3000);

    } catch (err) {
        alert("Error starting scraper: " + err.message);
        btnScrape.disabled = false;
        btnScrape.style.opacity = '1';
        progressSection.classList.add('hidden');
    }
}

async function checkStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/jobs/status/${currentTaskId}`);
        if (!response.ok) return;

        const data = await response.json();

        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const terminalLog = document.getElementById('terminalLog');

        let pct = 0;
        if (data.total_expected > 0) {
            pct = Math.floor((data.progress / data.total_expected) * 100);
        }

        progressBar.style.width = `${pct}%`;
        progressPercent.innerText = `${pct}%`;

        terminalLog.innerHTML = `<div class="log-line">> Status: ${data.status} | Fetched: ${data.progress} / ${data.total_expected}</div>`;
        terminalLog.scrollTop = terminalLog.scrollHeight;

        if (data.status === 'COMPLETED') {
            clearInterval(pollInterval);
            finishScraping(data);
        } else if (data.status === 'FAILED') {
            clearInterval(pollInterval);
            alert("Scraping failed: " + data.error_message);
            resetUI();
        }
    } catch (err) {
        console.error("Polling error:", err);
    }
}

let globalResults = [];
let currentPage = 1;
const pageSize = 50;

function renderTablePage() {
    const tableBody = document.getElementById('tableBody');
    const paginationControls = document.getElementById('paginationControls');
    const pageIndicator = document.getElementById('pageIndicator');
    const btnPrevPage = document.getElementById('btnPrevPage');
    const btnNextPage = document.getElementById('btnNextPage');

    if (globalResults.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No profile results found for query. Try modifying your search parameters or preset tags.</td></tr>`;
        paginationControls.classList.add('hidden');
        return;
    }

    const totalPages = Math.ceil(globalResults.length / pageSize);
    if (totalPages > 1) {
        paginationControls.classList.remove('hidden');
    } else {
        paginationControls.classList.add('hidden');
    }

    pageIndicator.innerText = `Page ${currentPage} of ${totalPages}`;
    btnPrevPage.disabled = currentPage === 1;
    btnNextPage.disabled = currentPage === totalPages;

    const startIdx = (currentPage - 1) * pageSize;
    const endIdx = Math.min(startIdx + pageSize, globalResults.length);
    const pageData = globalResults.slice(startIdx, endIdx);

    tableBody.innerHTML = pageData.map((row, idx) => {
        const absoluteIdx = startIdx + idx + 1;
        const name = row.name || 'N/A';
        const emailHtml = (row.email && row.email !== 'N/A') 
            ? `<span class="badge-email">${row.email}</span>` 
            : `<span class="badge-na">N/A</span>`;

        const linkedinHtml = (row.linkedin_url && row.linkedin_url !== 'N/A') 
            ? `<a href="${row.linkedin_url}" target="_blank" class="badge-linkedin">View Profile ↗</a>` 
            : `<span class="badge-na">N/A</span>`;

        const socialHtml = (row.social_links && row.social_links !== 'N/A')
            ? `<span style="font-size: 0.85rem; color: var(--text-secondary);">${row.social_links}</span>`
            : `<span class="badge-na">N/A</span>`;

        const githubHtml = `<a href="${row.github_url}" target="_blank" class="link-github">${row.github_url}</a>`;
        const repos = row.repositories || '0';

        return `
            <tr>
                <td>${absoluteIdx}</td>
                <td><strong>${name}</strong></td>
                <td>${emailHtml}</td>
                <td>${linkedinHtml}</td>
                <td>${socialHtml}</td>
                <td>${githubHtml}</td>
                <td>${repos}</td>
            </tr>
        `;
    }).join('');
}

function prevPage() {
    if (currentPage > 1) {
        currentPage--;
        renderTablePage();
    }
}

function nextPage() {
    const totalPages = Math.ceil(globalResults.length / pageSize);
    if (currentPage < totalPages) {
        currentPage++;
        renderTablePage();
    }
}

function finishScraping(data) {
    const btnScrape = document.getElementById('btnScrape');
    const resultsSection = document.getElementById('resultsSection');
    const summaryStats = document.getElementById('summaryStats');

    const spinner = document.getElementById('spinner');
    const checkIcon = document.getElementById('checkIcon');
    const progressTitle = document.getElementById('progressTitle');
    const progressBar = document.getElementById('progressBar');
    const progressPercent = document.getElementById('progressPercent');

    spinner.classList.add('hidden');
    checkIcon.classList.remove('hidden');
    progressTitle.innerText = "Scraping Task Completed";
    
    progressBar.style.width = '100%';
    progressPercent.innerText = '✓ 100%';
    progressBar.classList.add('completed');
    progressPercent.classList.add('completed');

    btnScrape.disabled = false;
    btnScrape.style.opacity = '1';

    resultsSection.classList.remove('hidden');

    globalResults = data.results || [];
    currentPage = 1;

    const emailsCount = globalResults.filter(r => r.email && r.email !== 'N/A').length;
    const linkedinCount = globalResults.filter(r => r.linkedin_url && r.linkedin_url !== 'N/A').length;

    summaryStats.innerText = `Gathered ${globalResults.length} profile(s) | Emails: ${emailsCount} | LinkedIn: ${linkedinCount}`;

    renderTablePage();
}

function resetUI() {
    const btnScrape = document.getElementById('btnScrape');
    const spinner = document.getElementById('spinner');
    const checkIcon = document.getElementById('checkIcon');

    btnScrape.disabled = false;
    btnScrape.style.opacity = '1';
    spinner.classList.add('hidden');
    checkIcon.classList.add('hidden');
}

function downloadFile(fileFormat) {
    if (!currentTaskId) {
        alert("No active or completed scrape task found.");
        return;
    }
    window.location.href = `/api/download/${currentTaskId}/${fileFormat}`;
}
