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
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');
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
    statusText.innerText = "Scraping In Progress";
    statusDot.classList.add('active');

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
        const response = await fetch('/api/scrape', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({ query: query, max_results: maxResults })
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || "Failed to start scraping task.");
        }

        const data = await response.json();
        currentTaskId = data.task_id;
        
        pollInterval = setInterval(checkStatus, 1000);

    } catch (err) {
        alert("Error starting scraper: " + err.message);
        btnScrape.disabled = false;
        btnScrape.style.opacity = '1';
        statusText.innerText = "System Ready";
        statusDot.classList.remove('active');
        progressSection.classList.add('hidden');
    }
}

async function checkStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/status/${currentTaskId}`);
        if (!response.ok) return;

        const data = await response.json();

        const progressBar = document.getElementById('progressBar');
        const progressPercent = document.getElementById('progressPercent');
        const terminalLog = document.getElementById('terminalLog');

        progressBar.style.width = `${data.progress}%`;
        progressPercent.innerText = `${data.progress}%`;

        if (data.logs && data.logs.length > 0) {
            terminalLog.innerHTML = data.logs.map(log => `<div class="log-line">> ${log}</div>`).join('');
            terminalLog.scrollTop = terminalLog.scrollHeight;
        }

        if (data.status === 'completed') {
            clearInterval(pollInterval);
            finishScraping(data);
        } else if (data.status === 'failed') {
            clearInterval(pollInterval);
            alert("Scraping task failed: " + (data.error || "Unknown error"));
            resetUI();
        }
    } catch (err) {
        console.error("Polling error:", err);
    }
}

function finishScraping(data) {
    const btnScrape = document.getElementById('btnScrape');
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');
    const resultsSection = document.getElementById('resultsSection');
    const tableBody = document.getElementById('tableBody');
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
    statusText.innerText = "Task Completed";
    statusDot.classList.remove('active');

    resultsSection.classList.remove('hidden');

    const results = data.results || [];
    const emailsCount = results.filter(r => r.Email && r.Email !== 'N/A').length;
    const linkedinCount = results.filter(r => r["LinkedIn URL"] && r["LinkedIn URL"] !== 'N/A').length;

    summaryStats.innerText = `Gathered ${results.length} profile(s) | Emails: ${emailsCount} | LinkedIn: ${linkedinCount}`;

    if (results.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-secondary); padding: 2rem;">No profile results found for query. Try modifying your search parameters or preset tags.</td></tr>`;
        return;
    }

    tableBody.innerHTML = results.map((row, idx) => {
        const name = row.Name || 'N/A';
        const emailHtml = (row.Email && row.Email !== 'N/A') 
            ? `<span class="badge-email">${row.Email}</span>` 
            : `<span class="badge-na">N/A</span>`;

        const linkedinHtml = (row["LinkedIn URL"] && row["LinkedIn URL"] !== 'N/A') 
            ? `<a href="${row["LinkedIn URL"]}" target="_blank" class="badge-linkedin">View Profile ↗</a>` 
            : `<span class="badge-na">N/A</span>`;

        const githubHtml = `<a href="${row["GitHub URL"]}" target="_blank" class="link-github">${row["GitHub URL"]}</a>`;
        const repos = row.Repositories || '0';

        return `
            <tr>
                <td>${idx + 1}</td>
                <td><strong>${name}</strong></td>
                <td>${emailHtml}</td>
                <td>${linkedinHtml}</td>
                <td>${githubHtml}</td>
                <td>${repos}</td>
            </tr>
        `;
    }).join('');
}

function resetUI() {
    const btnScrape = document.getElementById('btnScrape');
    const statusText = document.getElementById('statusText');
    const statusDot = document.querySelector('.status-dot');
    const spinner = document.getElementById('spinner');
    const checkIcon = document.getElementById('checkIcon');

    btnScrape.disabled = false;
    btnScrape.style.opacity = '1';
    statusText.innerText = "System Ready";
    statusDot.classList.remove('active');
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
