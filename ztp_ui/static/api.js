const JSON_HEADERS = { "Content-Type": "application/json" };

export async function fetchStatus() {
    const response = await fetch("/status", { headers: JSON_HEADERS });
    if (!response.ok) throw new Error("Failed to fetch /status");
    return response.json();
}

export async function runProvisioning() {
    const response = await fetch("/run");
    return response.json();
}

export async function scanNetwork() {
    const response = await fetch("/scan");
    return response.json();
}

export async function stopProcess() {
    const response = await fetch("/stop");
    return response.json();
}
