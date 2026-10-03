/**
 * Google Search Content Script for 407 Flips Agent Deal Hunter
 * Automatically detects phone numbers from Google Search AI Overviews & Knowledge Panels,
 * and renders a 1-click "Push to Lauren's Desk" floating button.
 */

(function () {
  const SERVER_URL = "http://127.0.0.1:8001";

  function extractQueryInfo() {
    const urlParams = new URLSearchParams(window.location.search);
    const q = urlParams.get("q") || "";
    // Remove search keywords to isolate agent name
    let cleanName = q.replace(/realtor|phone|number|contact|fl|florida|cell|office|brokerage|real estate/gi, "").trim();
    cleanName = cleanName.replace(/["',]/g, " ").replace(/\s+/g, " ").trim();
    return { rawQuery: q, candidateName: cleanName };
  }

  function findPhonesOnPage() {
    const bodyText = document.body ? document.body.innerText : "";
    const phoneRegex = /(?:\+?1[-.\s]?)?\(?([2-9]\d{2})\)?[-.\s]?([2-9]\d{2})[-.\s]?(\d{4})/g;
    const matches = [];
    let m;
    while ((m = phoneRegex.exec(bodyText)) !== null) {
      const full = `${m[1]}-${m[2]}-${m[3]}`;
      // Exclude generic 800/888 toll frees
      if (!matches.includes(full) && !/^(800|888|877|866|855|844|833)/.test(m[1])) {
        matches.push(full);
      }
    }
    return matches;
  }

  function createFloatingPushWidget(phone, agentName) {
    if (document.getElementById("dealHunterGoogleWidget")) return;

    const widget = document.createElement("div");
    widget.id = "dealHunterGoogleWidget";
    widget.style.cssText = `
      position: fixed;
      top: 20px;
      right: 24px;
      z-index: 999999;
      background: linear-gradient(135deg, #0f172a, #1e1b4b);
      border: 2px solid #818cf8;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.6), 0 8px 10px -6px rgba(0, 0, 0, 0.6);
      border-radius: 16px;
      padding: 14px 18px;
      color: #fff;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      font-size: 12px;
      max-width: 320px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      animation: dealHunterSlideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    `;

    widget.innerHTML = `
      <style>
        @keyframes dealHunterSlideIn {
          from { transform: translateY(-20px); opacity: 0; }
          to { transform: translateY(0); opacity: 1; }
        }
      </style>
      <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
        <div style="display: flex; align-items: center; gap: 6px; font-weight: 800; color: #fbbf24;">
          <span>🔨</span>
          <span>407 Flips Deal Hunter</span>
        </div>
        <button id="btnDealHunterClose" style="background:none;border:none;color:#94a3b8;font-size:14px;cursor:pointer;line-height:1;">✕</button>
      </div>
      <div>
        <div style="color: #94a3b8; font-size: 11px;">Detected Agent:</div>
        <div style="font-weight: 700; color: #fff; font-size: 13px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap;">
          ${agentName || 'Listing Agent'}
        </div>
      </div>
      <div>
        <div style="color: #94a3b8; font-size: 11px;">Direct Phone:</div>
        <div style="font-weight: 800; font-family: monospace; color: #34d399; font-size: 15px;">
          📱 ${phone}
        </div>
      </div>
      <button id="btnDealHunterPush" style="
        background: linear-gradient(135deg, #4f46e5, #7c3aed);
        color: white;
        border: 1px solid #a78bfa;
        border-radius: 10px;
        padding: 8px 12px;
        font-weight: 800;
        font-size: 12px;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
        transition: all 0.2s;
        margin-top: 4px;
      ">
        <span>📤 Push to Lauren's Desk</span>
      </button>
      <div id="dealHunterPushStatus" style="font-size: 11px; text-align: center; display: none;"></div>
    `;

    document.body.appendChild(widget);

    document.getElementById("btnDealHunterClose").addEventListener("click", () => {
      widget.remove();
    });

    const pushBtn = document.getElementById("btnDealHunterPush");
    const statusEl = document.getElementById("dealHunterPushStatus");

    pushBtn.addEventListener("click", async () => {
      pushBtn.disabled = true;
      pushBtn.innerText = "⏳ Pushing to Desk...";

      try {
        const res = await fetch(`${SERVER_URL}/api/fixers/push-phone`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            agent_name: agentName,
            phone: phone
          })
        });

        const data = await res.json();
        if (data.status === "success") {
          pushBtn.style.background = "#059669";
          pushBtn.style.borderColor = "#34d399";
          pushBtn.innerHTML = `<span>✓ Phone Saved to Desk!</span>`;
          statusEl.style.display = "block";
          statusEl.style.color = "#34d399";
          statusEl.innerText = `${data.message || 'Saved!'}`;
          setTimeout(() => {
            widget.remove();
          }, 3500);
        } else {
          pushBtn.disabled = false;
          pushBtn.innerHTML = `<span>📤 Push to Lauren's Desk</span>`;
          statusEl.style.display = "block";
          statusEl.style.color = "#fbbf24";
          statusEl.innerText = data.message || "Could not auto-match agent name.";
        }
      } catch (err) {
        pushBtn.disabled = false;
        pushBtn.innerHTML = `<span>📤 Push to Lauren's Desk</span>`;
        statusEl.style.display = "block";
        statusEl.style.color = "#f87171";
        statusEl.innerText = "Error: Deal Hunter server (:8001) not responding.";
      }
    });
  }

  // Check for AI overview / knowledge panel phones after page loads
  function init() {
    const { rawQuery, candidateName } = extractQueryInfo();
    if (!rawQuery) return;

    setTimeout(() => {
      const phones = findPhonesOnPage();
      if (phones.length > 0) {
        createFloatingPushWidget(phones[0], candidateName);
      }
    }, 800);
  }

  if (document.readyState === "complete" || document.readyState === "interactive") {
    init();
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
