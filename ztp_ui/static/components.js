function statusBadgeClass(status) {
    const normalized = (status || "").toLowerCase();
    if (normalized === "active") return "badge active";
    if (normalized === "provisioning") return "badge provisioning";
    return "badge completed";
}

function decisionClass(decision) {
    const normalized = (decision || "").toLowerCase();
    if (normalized === "high") return "decision-high";
    if (normalized === "medium") return "decision-medium";
    return "decision-low";
}

function stateClass(state) {
    const normalized = (state || "").toLowerCase();
    if (normalized === "running") return "state-running";
    if (normalized === "completed") return "state-completed";
    return "state-idle";
}

export function renderDevicePanel(el, data) {
    const rows = (data.devices || [])
        .map(
            (device) => `
            <div class="device-row ${device.is_new ? "new" : ""}">
                <div>${device.ip}</div>
                <div><span class="${statusBadgeClass(device.status)}">${device.status}</span></div>
                <div>${device.detected_at || "-"}</div>
            </div>
        `
        )
        .join("");

    el.innerHTML = `
        <div class="panel-header">
            <h3>Device Panel</h3>
            <span>${(data.devices || []).length} connected</span>
        </div>
        <div class="device-row">
            <strong>IP Address</strong>
            <strong>Status</strong>
            <strong>Detected</strong>
        </div>
        ${rows || '<div class="device-row"><div>No devices found</div><div>-</div><div>-</div></div>'}
    `;
}

export function renderMlPanel(el, data) {
    const ml = data.ml || {};
    el.innerHTML = `
        <div class="panel-header">
            <h3>ML Decision Panel</h3>
            <span class="${decisionClass(ml.decision)}">${ml.decision || "LOW"}</span>
        </div>
        <div class="metrics">
            <div class="metric">
                <span>Network Load</span>
                <strong>${ml.network_load ?? 0}%</strong>
            </div>
            <div class="metric">
                <span>Latency</span>
                <strong>${ml.latency ?? 0}ms</strong>
            </div>
            <div class="metric">
                <span>Decision</span>
                <strong>${ml.decision || "LOW"}</strong>
            </div>
        </div>
    `;
}

export function renderStatusPanel(el, data) {
    const state = data.system_state || "Idle";
    const progress = data.progress || 0;
    el.innerHTML = `
        <div class="panel-header">
            <h3>System Status</h3>
        </div>
        <div class="status-line">
            <div class="state-dot ${stateClass(state)}"></div>
            <strong>${state}</strong>
        </div>
        <div class="progress-wrap">
            <div class="progress-bar">
                <div class="progress-value" style="width:${progress}%"></div>
            </div>
            <p>${progress}% complete</p>
        </div>
    `;
}

export function renderLogsPanel(el, data) {
    const logs = (data.logs || [])
        .slice(-120)
        .reverse()
        .map((log) => {
            const klass = `log-${(log.level || "INFO").toLowerCase()}`;
            return `
                <div class="log-row ${klass}">
                    <span>${log.time}</span>
                    <span>${log.level}</span>
                    <span>${log.message}</span>
                </div>
            `;
        })
        .join("");

    el.innerHTML = `
        <div class="panel-header">
            <h3>Logs Panel</h3>
            <span>Live stream</span>
        </div>
        <div class="logs">
            ${logs || '<div class="log-row log-info"><span>-</span><span>INFO</span><span>No logs yet</span></div>'}
        </div>
    `;
}

export function renderControlsPanel(el, handlers) {
    el.innerHTML = `
        <div class="panel-header">
            <h3>Control Panel</h3>
            <span>Automation actions</span>
        </div>
        <div class="controls">
            <button class="btn primary" id="btnRun">Start Provisioning</button>
            <button class="btn" id="btnScan">Scan Network</button>
            <button class="btn warn" id="btnStop">Stop Process</button>
        </div>
    `;
    el.querySelector("#btnRun").addEventListener("click", handlers.onRun);
    el.querySelector("#btnScan").addEventListener("click", handlers.onScan);
    el.querySelector("#btnStop").addEventListener("click", handlers.onStop);
}
