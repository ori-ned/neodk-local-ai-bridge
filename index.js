/**
 * ESTIM BRIDGE v1.4 — SillyTavern Extension
 * Polling toutes les 500ms — version stable
 */

const ESTIM_WS_URL    = "ws://127.0.0.1:5001";
const POLL_INTERVAL   = 500;

let ws              = null;
let connected       = false;
let statusEl        = null;
let reconnectTimer  = null;
let isConnecting    = false;
let lastProcessedId = null;
let pollTimer       = null;

function connectServer() {
    if (isConnecting) return;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    isConnecting = true;
    if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }

    try { ws = new WebSocket(ESTIM_WS_URL); }
    catch(e) { isConnecting = false; scheduleReconnect(); return; }

    ws.onopen = () => {
        isConnecting = false; connected = true;
        setStatus("🟢 Connecté", "#22c55e");
        console.log("[estim-bridge] ✔ Connecté");
        safeSend(JSON.stringify({ action: "ping" }));
    };
    ws.onclose = () => {
        isConnecting = false; connected = false;
        setStatus("🔴 Déconnecté", "#ef4444");
        scheduleReconnect();
    };
    ws.onerror = () => { isConnecting = false; };
    ws.onmessage = (evt) => {
        try {
            const d = JSON.parse(evt.data);
            if (d.status === "pong") setStatus("🟢 Connecté", "#22c55e");
            if (d.status === "ok")   setStatus("⚡ Pattern actif", "#a855f7");
        } catch(e) {}
    };
}

function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = setTimeout(() => { reconnectTimer = null; connectServer(); }, 4000);
}

function safeSend(msg) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        try { ws.send(msg); return true; } catch(e) {}
    }
    return false;
}

function extractEstim(text) {
    const match = text.match(/<estim>([\s\S]*?)<\/estim>/);
    if (!match) return null;
    try { return JSON.parse(match[1].trim()); }
    catch(e) {
        try { return JSON.parse(match[1].trim().replace(/\/\/.*$/gm, "")); }
        catch(e2) { console.warn("[estim-bridge] JSON invalide:", match[1].substring(0, 80)); return null; }
    }
}

function stripEstimTags(text) {
    return text.replace(/\s*<estim>[\s\S]*?<\/estim>\s*/g, "\n").trim();
}

function sendCommand(data) {
    if (!data) return;
    if (data.action === "generate") {
        safeSend(JSON.stringify(data));
        const label = `${data.type} | ${data.intensity} | ${data.speed} | ${data.mood}`;
        console.log("[estim-bridge] ⚡ Generate:", label);
        setStatus(`⚡ ${data.type} (${data.intensity})`, "#a855f7");
    } else if (data.pattern) {
        const ok = safeSend(JSON.stringify({ action: "pattern", pattern: data }));
        if (ok) {
            const n = data.pattern?.length || 0;
            console.log(`[estim-bridge] ⚡ Pattern: "${data.note}" (${n} steps)`);
            setStatus(`⚡ ${data.note || "actif"} (${n} steps)`, "#a855f7");
        }
    }
}

function sendStop() {
    safeSend(JSON.stringify({ action: "stop" }));
    setStatus("⏹ Arrêté", "orange");
}

function pollLastMessage() {
    try {
        const ctx  = window.SillyTavern.getContext();
        const chat = ctx?.chat;
        if (!chat || chat.length === 0) return;

        for (let i = chat.length - 1; i >= 0; i--) {
            const msg = chat[i];
            if (msg.is_user || msg.is_system) continue;

            const msgId = `${i}_${(msg.mes || "").length}`;
            if (msgId === lastProcessedId) break;

            const raw = msg.mes || "";
            if (!raw.includes("<estim>")) break;

            console.log("[estim-bridge] 🎯 Pattern détecté dans message", i);
            lastProcessedId = msgId;

            const data = extractEstim(raw);
            if (data) sendCommand(data);

            msg.mes = stripEstimTags(raw);

            setTimeout(() => {
                const msgEls = document.querySelectorAll("#chat .mes .mes_text");
                if (msgEls.length > 0) {
                    const last = msgEls[msgEls.length - 1];
                    last.innerHTML = last.innerHTML
                        .replace(/\s*&lt;estim&gt;[\s\S]*?&lt;\/estim&gt;\s*/g, "")
                        .replace(/\s*<estim>[\s\S]*?<\/estim>\s*/g, "");
                }
            }, 100);
            break;
        }
    } catch(e) {}
}

function setStatus(text, color) {
    if (statusEl) { statusEl.textContent = text; statusEl.style.color = color; }
}

function addSettingsUI() {
    const html = `
    <div id="estim-bridge-settings" style="margin:10px 0;padding:10px;border:1px solid #555;border-radius:6px;">
        <h4 style="margin:0 0 8px 0;">⚡ Estim Bridge v1.4</h4>
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
            <span>Statut :</span>
            <span id="estim-status" style="font-weight:bold;">⏳ Init...</span>
        </div>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
            <button id="estim-reconnect" class="menu_button" style="padding:4px 10px;">🔄 Reconnecter</button>
            <button id="estim-stop"      class="menu_button" style="padding:4px 10px;">⏹ Stop signal</button>
            <button id="estim-test"      class="menu_button" style="padding:4px 10px;">🧪 Test ping</button>
        </div>
        <div style="margin-top:8px;font-size:0.85em;color:#aaa;">Polling ${POLL_INTERVAL}ms | ws://127.0.0.1:5001</div>
    </div>`;
    $("#extensions_settings").append(html);
    statusEl = document.getElementById("estim-status");

    document.getElementById("estim-reconnect").addEventListener("click", () => {
        if (ws) { try { ws.close(); } catch(e) {} ws = null; }
        isConnecting = false;
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        setTimeout(connectServer, 300);
    });
    document.getElementById("estim-stop").addEventListener("click", sendStop);
    document.getElementById("estim-test").addEventListener("click", () => {
        const ok = safeSend(JSON.stringify({ action: "ping" }));
        setStatus(ok ? "🔄 Ping..." : "🔴 WS fermé", ok ? "yellow" : "red");
    });
}

jQuery(async () => {
    addSettingsUI();

    await new Promise(resolve => {
        const check = () => {
            if (window.SillyTavern?.getContext) { resolve(); }
            else { setTimeout(check, 300); }
        };
        setTimeout(check, 1000);
    });

    console.log("[estim-bridge] ST prêt, démarrage v1.4");
    connectServer();
    pollTimer = setInterval(pollLastMessage, POLL_INTERVAL);
    console.log("[estim-bridge] ✔ Polling actif");
});
