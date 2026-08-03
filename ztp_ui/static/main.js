import { fetchStatus, runProvisioning, scanNetwork, stopProcess } from "./api.js";
import {
    renderControlsPanel,
    renderDevicePanel,
    renderLogsPanel,
    renderMlPanel,
    renderStatusPanel,
} from "./components.js";

const panels = {
    devices: document.getElementById("devicePanel"),
    ml: document.getElementById("mlPanel"),
    status: document.getElementById("statusPanel"),
    logs: document.getElementById("logsPanel"),
    controls: document.getElementById("controlsPanel"),
};

let isBusy = false;

function setBusy(value) {
    isBusy = value;
}

async function refreshDashboard() {
    if (isBusy) return;
    try {
        const data = await fetchStatus();
        renderDevicePanel(panels.devices, data);
        renderMlPanel(panels.ml, data);
        renderStatusPanel(panels.status, data);
        renderLogsPanel(panels.logs, data);
    } catch (error) {
        console.error(error);
    }
}

async function runAction(action) {
    try {
        setBusy(true);
        await action();
        await refreshDashboard();
    } catch (error) {
        console.error(error);
    } finally {
        setBusy(false);
    }
}

renderControlsPanel(panels.controls, {
    onRun: () => runAction(runProvisioning),
    onScan: () => runAction(scanNetwork),
    onStop: () => runAction(stopProcess),
});

refreshDashboard();
setInterval(refreshDashboard, 1500);
