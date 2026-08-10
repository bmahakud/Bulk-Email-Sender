// ── GLOBAL APPLICATION STATE ─────────────────────────────────────────────
let appState = {
    smtps: [],
    recipients: [],
    subjects: [
        "Your invoice #INVOICE# is ready — ProMailer Pro",
        "Payment of $#AMOUNT# received on #DATE# — Order #ORDERID#",
        "Transaction #TXNID# confirmed — Support Desk"
    ],
    senders: ["Sofia Adams", "Ava Harris", "John Smith"],
    bodyPlain: "Hello #NAME#,\n\nYour payment of $#AMOUNT# has been successfully received on #DATE#.\nInvoice: #INVOICE#\nTransaction ID: #TXNID#\n\nThanks!\nSupport Division",
    inlineImages: [],
    htmlTemplates: [],
    delay: 1.0,
    smtpRotationMode: 'auto',
    emailsPerSmtpLimit: 5,
    autoRemoveSent: true,
    status: 'idle',
    emailsSentCount: 0,
    emailsFailedCount: 0,
    currentSmtp: 'None',
    lastActiveTextarea: null
};

let syncTimer = null;
let lastLogIndex = 0; // Tracks which log lines we have already displayed

// ── LOCAL STORAGE SYNC FOR LOCAL SETTINGS ──────────────────────────────
function saveSettingsLocal() {
    localStorage.setItem('promailer_settings', JSON.stringify({
        subjects: appState.subjects,
        senders: appState.senders,
        bodyPlain: appState.bodyPlain,
        delay: appState.delay,
        smtpRotationMode: appState.smtpRotationMode,
        emailsPerSmtpLimit: appState.emailsPerSmtpLimit,
        autoRemoveSent: appState.autoRemoveSent
    }));
}

function loadSettingsLocal() {
    const saved = localStorage.getItem('promailer_settings');
    if (saved) {
        try {
            const parsed = JSON.parse(saved);
            appState.subjects = parsed.subjects || appState.subjects;
            appState.senders = parsed.senders || appState.senders;
            appState.bodyPlain = parsed.bodyPlain || appState.bodyPlain;
            appState.delay = parsed.delay !== undefined ? parsed.delay : 1.0;
            appState.smtpRotationMode = parsed.smtpRotationMode || 'auto';
            appState.emailsPerSmtpLimit = parsed.emailsPerSmtpLimit || 5;
            appState.autoRemoveSent = parsed.autoRemoveSent !== undefined ? parsed.autoRemoveSent : true;
        } catch (e) {
            console.error("Error loading local settings:", e);
        }
    }
}

// ── INITIALIZATION ───────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    loadSettingsLocal();
    initUI();

    // Initial fetch from backend APIs
    fetchDatabaseState();

    // Keep checking campaign status
    startSyncLoop();
});

// ── API COMMUNICATIONS (FETCH DATA FROM BACKEND REST API) ────────────────
async function apiCall(endpoint, method = 'GET', body = null) {
    try {
        const options = { method };
        if (body) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        const resp = await fetch(endpoint, options);
        if (!resp.ok) {
            throw new Error(`HTTP error! status: ${resp.status}`);
        }
        return await resp.json();
    } catch (e) {
        console.error(`API Call failed [${method} ${endpoint}]:`, e);
        // Fallback for visual stability if server is down during draft view
        return null;
    }
}

async function fetchDatabaseState() {
    // 1. Fetch SMTP accounts
    const smtps = await apiCall('/api/smtps');
    if (smtps) appState.smtps = smtps;

    // 2. Fetch Recipients
    const recs = await apiCall('/api/recipients');
    if (recs) appState.recipients = recs;

    renderAll();
}

async function startSyncLoop() {
    if (syncTimer) clearInterval(syncTimer);
    syncTimer = setInterval(async () => {
        const data = await apiCall('/api/campaign/status');
        if (data) {
            appState.status = data.status;
            appState.emailsSentCount = data.stats.sent;
            appState.emailsFailedCount = data.stats.failed;
            appState.currentSmtp = data.stats.current_smtp;

            // Sync engine log screen
            syncLogFeeds(data.logs);

            // Update button states
            updateControls();

            // Re-render to show rotation shifts in tables & mini slots
            renderAll();
        }
    }, 1000);
}

function syncLogFeeds(backendLogs) {
    const list = document.getElementById("log-monitor");
    if (!backendLogs || backendLogs.length === 0) return;

    // If backend cleared logs, reset our pointer
    if (backendLogs.length < lastLogIndex) {
        lastLogIndex = 0;
        list.innerHTML = "";
    }

    for (let i = lastLogIndex; i < backendLogs.length; i++) {
        const log = backendLogs[i];
        const entry = document.createElement("div");
        entry.className = `log-entry ${log.type}`;
        entry.innerText = `[${log.time}] ${log.message}`;
        list.appendChild(entry);
        list.scrollTop = list.scrollHeight;
    }

    lastLogIndex = backendLogs.length;
}

// ── UI EVENT HANDLERS & BINDING ──────────────────────────────────────────
function initUI() {
    // Tab switching routing
    const menuItems = document.querySelectorAll(".menu-item");
    menuItems.forEach(item => {
        item.addEventListener("click", () => {
            const tabName = item.getAttribute("data-tab");

            menuItems.forEach(m => m.classList.remove("active"));
            item.classList.add("active");

            document.querySelectorAll(".tab-content").forEach(tab => {
                tab.classList.remove("active");
            });
            document.getElementById(`tab-${tabName}`).classList.add("active");

            const titles = {
                dashboard: ["Analytics Dashboard", "Real-time mail distribution overview"],
                smtp: ["Outlook Senders Pool", "OAuth token registration and connection testing"],
                recipients: ["Recipients Pool", "Manage destination address lists"],
                content: ["Content Rotator", "Configure rotating subjects, content templates, and body formats"],
                limits: ["Safe Speed & Rotation Limits", "Define spam prevention safeguards"]
            };
            document.getElementById("current-tab-title").innerText = titles[tabName][0];
            document.getElementById("current-tab-subtitle").innerText = titles[tabName][1];

            // Refresh DB when tab opens
            fetchDatabaseState();
        });
    });

    // Logger Clear Action
    document.getElementById("btn-clear-logs").addEventListener("click", () => {
        document.getElementById("log-monitor").innerHTML = "";
        lastLogIndex = 0;
    });

    // Form: Add Single SMTP API redirect
    document.getElementById("form-add-smtp").addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("smtp-email").value.trim();
        const pass = document.getElementById("smtp-password").value;
        const token = document.getElementById("smtp-token").value.trim();
        const client_id = document.getElementById("smtp-client-id").value.trim();

        await apiCall('/api/smtps/add', 'POST', { email, password: pass, token, client_id });
        document.getElementById("form-add-smtp").reset();
        document.getElementById("smtp-password").value = "dummy_password";
        document.getElementById("smtp-client-id").value = "0dcc03c9-4d8d-413a-896b-308559661ed9";

        fetchDatabaseState();
    });

    // Form: Add Single Recipient API redirect
    document.getElementById("form-add-recipient").addEventListener("submit", async (e) => {
        e.preventDefault();
        const email = document.getElementById("rec-email").value.trim();
        const name = document.getElementById("rec-name").value.trim();

        await apiCall('/api/recipients/add', 'POST', { email, name });
        document.getElementById("form-add-recipient").reset();

        fetchDatabaseState();
    });

    // Textarea tracker to target template tag injection
    const textareas = ['campaign-subjects', 'campaign-senders', 'campaign-body-plain'];
    textareas.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('focus', () => { appState.lastActiveTextarea = id; });
        }
    });

    // Rotate config change
    document.getElementById("chk-default-sender").addEventListener("change", (e) => {
        document.getElementById("campaign-senders").disabled = e.target.checked;
    });

    // Subject/Body changes auto-save
    document.getElementById("campaign-subjects").value = appState.subjects.join("\n");
    document.getElementById("campaign-subjects").addEventListener("input", (e) => {
        appState.subjects = e.target.value.split("\n").filter(x => x.trim() !== "");
        saveSettingsLocal();
    });

    document.getElementById("campaign-senders").value = appState.senders.join("\n");
    document.getElementById("campaign-senders").addEventListener("input", (e) => {
        appState.senders = e.target.value.split("\n").filter(x => x.trim() !== "");
        saveSettingsLocal();
    });

    document.getElementById("campaign-body-plain").value = appState.bodyPlain;
    document.getElementById("campaign-body-plain").addEventListener("input", (e) => {
        appState.bodyPlain = e.target.value;
        saveSettingsLocal();
    });

    // Timing safeguards
    document.getElementById("limits-delay").value = appState.delay;
    document.getElementById("limits-delay").addEventListener("change", (e) => {
        appState.delay = parseFloat(e.target.value);
        saveSettingsLocal();
    });

    document.getElementById("limits-per-smtp").value = appState.emailsPerSmtpLimit;
    document.getElementById("limits-per-smtp").addEventListener("change", (e) => {
        appState.emailsPerSmtpLimit = parseInt(e.target.value);
        saveSettingsLocal();
    });

    document.getElementById("chk-auto-remove").checked = appState.autoRemoveSent;
    document.getElementById("chk-auto-remove").addEventListener("change", (e) => {
        appState.autoRemoveSent = e.target.checked;
        saveSettingsLocal();
    });

    document.querySelectorAll("input[name='smtp_rotate_mode']").forEach(radio => {
        if (radio.value === appState.smtpRotationMode) radio.checked = true;
        radio.addEventListener("change", (e) => {
            appState.smtpRotationMode = e.target.value;
            saveSettingsLocal();
        });
    });

    // Clear SMTPs database api
    document.getElementById("btn-clear-smtps").addEventListener("click", async () => {
        if (confirm("Are you sure you want to delete all SMTP accounts in database?")) {
            await apiCall('/api/smtps/clear', 'POST');
            fetchDatabaseState();
        }
    });

    // Clear recipients database api
    document.getElementById("btn-clear-recipients").addEventListener("click", async () => {
        if (confirm("Are you sure you want to clear the target recipients database pool?")) {
            await apiCall('/api/recipients/clear', 'POST');
            fetchDatabaseState();
        }
    });

    // OAuth mock redirect and registration
    document.getElementById("btn-link-ms").addEventListener("click", () => {
        const simulatedUsernames = ["corporate.finance@outlook.com", "billing.ops@outlook.com", "billing.support@outlook.com", "billing@live.com"];
        const chosenEmail = simulatedUsernames[Math.floor(Math.random() * simulatedUsernames.length)];

        const code = prompt("Simulating browser OAuth2 authentication response.\n\nAuthorise link to database?\nType 'OK' to add:", "OK");
        if (code && code.toUpperCase() === "OK") {
            const mockToken = "M.R3_BAY." + Math.random().toString(36).substring(2, 10).toUpperCase() + Math.random().toString(36).substring(2, 15);
            apiCall('/api/smtps/add', 'POST', {
                email: chosenEmail,
                password: "dummy_password",
                token: mockToken,
                client_id: "0dcc03c9-4d8d-413a-896b-308559661ed9"
            }).then(() => {
                fetchDatabaseState();
                alert(`Successfully authenticated Microsoft Account:\n${chosenEmail}`);
            });
        }
    });

    // Paste Bulk imports
    document.getElementById("btn-paste-smtp").addEventListener("click", () => {
        openModal("Paste SMTP Accounts", "Format (one per line): email | password | token | client_id", async (textareaValue) => {
            const lines = textareaValue.split("\n");
            for (const line of lines) {
                const parts = line.split("|");
                if (parts.length >= 4) {
                    await apiCall('/api/smtps/add', 'POST', {
                        email: parts[0].trim(),
                        password: parts[1].trim(),
                        token: parts[2].trim(),
                        client_id: parts[3].trim()
                    });
                }
            }
            fetchDatabaseState();
        });
    });

    document.getElementById("btn-paste-recipients").addEventListener("click", () => {
        openModal("Paste Recipients Pool", "Format (one per line): email   OR   email,name", async (textareaValue) => {
            const lines = textareaValue.split("\n");
            for (const line of lines) {
                if (line.includes("@")) {
                    const parts = line.split(",");
                    await apiCall('/api/recipients/add', 'POST', {
                        email: parts[0].trim(),
                        name: parts[1] ? parts[1].trim() : ""
                    });
                }
            }
            fetchDatabaseState();
        });
    });

    // File uploads API redirect
    document.getElementById("btn-upload-smtp").addEventListener("click", () => {
        document.getElementById("file-input-smtp").click();
    });
    document.getElementById("file-input-smtp").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (evt) => {
            const content = evt.target.result;
            const lines = content.split("\n");
            for (const line of lines) {
                const parts = line.split(/[|,]/);
                if (parts.length >= 4) {
                    await apiCall('/api/smtps/add', 'POST', {
                        email: parts[0].trim(),
                        password: parts[1].trim(),
                        token: parts[2].trim(),
                        client_id: parts[3].trim()
                    });
                }
            }
            fetchDatabaseState();
        };
        reader.readAsText(file);
    });

    document.getElementById("btn-upload-recipients").addEventListener("click", () => {
        document.getElementById("file-input-recipients").click();
    });
    document.getElementById("file-input-recipients").addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (evt) => {
            const content = evt.target.result;
            const lines = content.split("\n");
            for (const line of lines) {
                if (line.includes("@")) {
                    const parts = line.split(/[,,|]/);
                    await apiCall('/api/recipients/add', 'POST', {
                        email: parts[0].trim(),
                        name: parts[1] ? parts[1].trim() : ""
                    });
                }
            }
            fetchDatabaseState();
        };
        reader.readAsText(file);
    });

    // Content uploads UI mocks
    document.getElementById("btn-add-html-file").addEventListener("click", () => {
        document.getElementById("file-input-html").click();
    });
    document.getElementById("file-input-html").addEventListener("change", (e) => {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            appState.htmlTemplates.push(file.name);
        });
        renderLists();
    });

    document.getElementById("btn-add-attachments").addEventListener("click", () => {
        document.getElementById("file-input-attachments").click();
    });
    document.getElementById("file-input-attachments").addEventListener("change", (e) => {
        const files = Array.from(e.target.files);
        files.forEach(file => {
            appState.inlineImages.push(file.name);
        });
        renderLists();
    });

    // Campaign Actions Backend binding
    document.getElementById("btn-global-start").addEventListener("click", triggerCampaignStart);
    document.getElementById("btn-global-pause").addEventListener("click", triggerCampaignPause);
    document.getElementById("btn-global-stop").addEventListener("click", triggerCampaignStop);
}

// ── CRUD REMOVE ACTIONS DIRECT PATHS ─────────────────────────────────────
async function deleteSmtp(email) {
    await apiCall('/api/smtps/delete', 'POST', { email });
    fetchDatabaseState();
}

async function deleteRecipient(email) {
    await apiCall('/api/recipients/delete', 'POST', { email });
    fetchDatabaseState();
}

function insertTag(tag) {
    const id = appState.lastActiveTextarea || 'campaign-body-plain';
    const el = document.getElementById(id);
    if (el) {
        const start = el.selectionStart;
        const end = el.selectionEnd;
        const text = el.value;
        el.value = text.substring(0, start) + tag + text.substring(end);
        el.focus();
        el.selectionStart = el.selectionEnd = start + tag.length;
        const event = new Event('input', { bubbles: true });
        el.dispatchEvent(event);
    }
}

// ── MODALS DIALOGS ───────────────────────────────────────────────────────
let activeModalCallback = null;

function openModal(title, descStr, callback) {
    document.getElementById("modal-title").innerText = title;
    document.getElementById("modal-desc").innerText = descStr;
    document.getElementById("modal-textarea").value = "";
    document.getElementById("modal-paste").classList.add("active");
    activeModalCallback = callback;
}

function closeModal() {
    document.getElementById("modal-paste").classList.remove("active");
    activeModalCallback = null;
}

document.getElementById("btn-modal-submit").addEventListener("click", () => {
    const areaVal = document.getElementById("modal-textarea").value.trim();
    if (areaVal && activeModalCallback) {
        activeModalCallback(areaVal);
    }
    closeModal();
});

// ── WEB PAGE RENDERING ──────────────────────────────────────────────────
function renderAll() {
    renderStats();
    renderTables();
    renderLists();
}

function renderStats() {
    document.getElementById("stat-smtp-count").innerText = appState.smtps.length;
    document.getElementById("stat-recipients-count").innerText = appState.recipients.length;

    const pendingVal = appState.recipients.filter(x => x.status === 'pending').length;
    document.getElementById("stat-pending-info").innerText = `${pendingVal} pending in queue`;

    document.getElementById("stat-sent-count").innerText = appState.emailsSentCount;
    document.getElementById("stat-failed-count").innerText = appState.emailsFailedCount;

    const total = appState.emailsSentCount + appState.emailsFailedCount;
    const rate = total > 0 ? Math.round((appState.emailsFailedCount / total) * 100) : 0;
    document.getElementById("stat-fail-info").innerText = `${rate}% error rate`;

    // Completeness Progress trackers
    const overallTotal = appState.recipients.length;
    const completed = appState.recipients.filter(x => x.status === 'sent' || x.status === 'failed').length;
    const pct = overallTotal > 0 ? Math.round((completed / overallTotal) * 100) : 0;

    document.getElementById("progress-percentage-text").innerText = `${pct}%`;
    document.getElementById("dashboard-progress-fill").style.width = `${pct}%`;
}

function renderTables() {
    // Senders Table
    const smtpBody = document.getElementById("smtp-table-body");
    if (appState.smtps.length === 0) {
        smtpBody.innerHTML = `<tr><td colspan="6" class="empty-state">No SMTP accounts added yet. Link a Microsoft account or paste your credential pool.</td></tr>`;
    } else {
        smtpBody.innerHTML = appState.smtps.map(s => {
            const badg = s.status === 'ready' ? 'badge-ready' : (s.status === 'working' ? 'badge-working' : 'badge-error');
            const tokenSnippet = s.token ? s.token.substring(0, 15) + "..." : 'No Token';
            return `
                <tr>
                    <td><span class="table-badge ${badg}">${s.status.toUpperCase()}</span></td>
                    <td><b>${s.email}</b></td>
                    <td><code>${s.client_id}</code></td>
                    <td><code>${tokenSnippet}</code></td>
                    <td><b>${s.emails_sent || 0}</b> sent</td>
                    <td><button class="btn btn-sm btn-danger-outline" onclick="deleteSmtp('${s.email}')">Remove</button></td>
                </tr>
            `;
        }).join("");
    }

    // Recipients Table
    const recBody = document.getElementById("recipients-table-body");
    if (appState.recipients.length === 0) {
        recBody.innerHTML = `<tr><td colspan="6" class="empty-state">Recipient pool is empty. Add static entries or import a CSV mailing list.</td></tr>`;
    } else {
        recBody.innerHTML = appState.recipients.map(r => {
            const badg = r.status === 'pending' ? 'badge-neutral' : (r.status === 'sent' ? 'badge-working' : 'badge-error');
            return `
                <tr>
                    <td><b>${r.email}</b></td>
                    <td>${r.name || '<i>Anonymous</i>'}</td>
                    <td><span class="table-badge ${badg}">${r.status.toUpperCase()}</span></td>
                    <td><small class="${r.status === 'failed' ? 'color-error' : ''}">${r.error_message || r.logs || 'No issues'}</small></td>
                    <td>${r.created_at || new Date().toLocaleDateString()}</td>
                    <td><button class="btn btn-sm btn-danger-outline" onclick="deleteRecipient('${r.email}')">&times;</button></td>
                </tr>
            `;
        }).join("");
    }

    // Mini SMTP Slots sidebar
    const slotBody = document.getElementById("mini-smtp-slots");
    if (appState.smtps.length === 0) {
        slotBody.innerHTML = `<li class="empty-slot">Register SMTP accounts to view rotation slots.</li>`;
    } else {
        slotBody.innerHTML = appState.smtps.map((s) => {
            const act = (appState.status === 'running' && s.email === appState.currentSmtp) ? 'class="active-slot"' : '';
            return `<li ${act}><span>${s.email}</span><span>${s.emails_sent || 0} sent</span></li>`;
        }).join("");
    }
}

function renderLists() {
    const htmlUl = document.getElementById("html-paths-list");
    if (appState.htmlTemplates.length === 0) {
        htmlUl.innerHTML = `<li class="empty-li">No HTML templates uploaded. Defaulting to plain text template.</li>`;
    } else {
        htmlUl.innerHTML = appState.htmlTemplates.map((t, idx) => {
            return `<li><span>📄 ${t}</span><span class="btn-remove-item" onclick="removeHtmlTemplate(${idx})">&times; remove</span></li>`;
        }).join("");
    }

    const attUl = document.getElementById("attachment-paths-list");
    if (appState.inlineImages.length === 0) {
        attUl.innerHTML = `<li class="empty-li">No attachments selected.</li>`;
    } else {
        attUl.innerHTML = appState.inlineImages.map((a, idx) => {
            return `<li><span>📎 ${a}</span><span class="btn-remove-item" onclick="removeAttachment(${idx})">&times; remove</span></li>`;
        }).join("");
    }
}

function removeHtmlTemplate(idx) {
    appState.htmlTemplates.splice(idx, 1);
    renderLists();
}

function removeAttachment(idx) {
    appState.inlineImages.splice(idx, 1);
    renderLists();
}

// ── REAL BACKEND ACTIVE CAMPAIGN TRIGGERS ───────────────────────────────
async function triggerCampaignStart() {
    if (appState.smtps.length === 0) {
        alert("Please register at least one SMTP account first.");
        return;
    }
    const pendingPool = appState.recipients.filter(x => x.status === 'pending');
    if (pendingPool.length === 0) {
        alert("All active recipients have been processed. Reset lists or upload new targets.");
        return;
    }

    // Capture configurations block
    const config = {
        subjects: appState.subjects,
        senders: appState.senders,
        body_plain: appState.bodyPlain,
        default_sender: document.getElementById("chk-default-sender").checked,
        delay: appState.delay,
        smtp_mode: appState.smtpRotationMode,
        limit_per_smtp: appState.emailsPerSmtpLimit,
        auto_remove: appState.autoRemoveSent
    };

    // Clear logs front pointer
    lastLogIndex = 0;
    document.getElementById("log-monitor").innerHTML = "";

    await apiCall('/api/campaign/start', 'POST', config);
}

async function triggerCampaignPause() {
    await apiCall('/api/campaign/pause', 'POST');
}

async function triggerCampaignStop() {
    await apiCall('/api/campaign/stop', 'POST');
}

function updateControls() {
    const startBtn = document.getElementById("btn-global-start");
    const pauseBtn = document.getElementById("btn-global-pause");
    const stopBtn = document.getElementById("btn-global-stop");
    const statPill = document.getElementById("global-status-indicator");
    const statText = statPill.querySelector(".status-name");

    statPill.className = "global-status-pill " + appState.status;
    document.getElementById("active-smtp-display").innerText = appState.currentSmtp;

    if (appState.status === 'running') {
        startBtn.disabled = true;
        pauseBtn.disabled = false;
        pauseBtn.innerText = "⏸ Pause";
        stopBtn.disabled = false;
        statText.innerText = "Active Sending";
    } else if (appState.status === 'paused') {
        startBtn.disabled = true;
        pauseBtn.disabled = false;
        pauseBtn.innerText = "▶ Resume";
        stopBtn.disabled = false;
        statText.innerText = "Suspended";
    } else {
        startBtn.disabled = false;
        pauseBtn.disabled = true;
        pauseBtn.innerText = "⏸ Pause";
        stopBtn.disabled = true;
        statText.innerText = "Engine Idle";
    }
}
