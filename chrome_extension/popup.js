let currentData = null;

document.addEventListener("DOMContentLoaded", async () => {
  const loadingBox = document.getElementById("loadingBox");
  const contentBox = document.getElementById("contentBox");
  const alertBox = document.getElementById("alertBox");
  const btnPush = document.getElementById("btnPush");

  // Query active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url || !tab.url.includes("redfin.com")) {
    loadingBox.innerHTML = `
      <div style="color: #f87171; font-weight: 600;">⚠️ Not on a Redfin page</div>
      <p style="font-size: 10px; color: #94a3b8; margin-top: 4px;">Open a Redfin listing page and click this extension again.</p>
    `;
    return;
  }

  // Request scraped data from content script
  try {
    chrome.tabs.sendMessage(tab.id, { action: "SCRAPE_REDFIN" }, (response) => {
      if (chrome.runtime.lastError || !response || !response.data) {
        // Fallback: inject content script if not ready
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"]
        }, () => {
          setTimeout(() => {
            chrome.tabs.sendMessage(tab.id, { action: "SCRAPE_REDFIN" }, (resp2) => {
              if (resp2 && resp2.data) {
                renderData(resp2.data);
              } else {
                showError("Could not read property details from this page.");
              }
            });
          }, 300);
        });
        return;
      }
      renderData(response.data);
    });
  } catch (err) {
    showError("Error connecting to page: " + err.message);
  }

  function renderData(data) {
    currentData = data;
    loadingBox.style.display = "none";
    contentBox.style.display = "block";

    document.getElementById("dispAddress").innerText = data.address || "Unknown Address";
    document.getElementById("dispCity").innerText = `${data.city || "Florida"}, ${data.zip || ""} • ${data.dom || 1} DOM`;
    document.getElementById("dispPrice").innerText = data.list_price ? `$${data.list_price.toLocaleString()}` : "$0";
    
    const est = data.redfin_estimate || (data.list_price * 1.25);
    document.getElementById("dispEstimate").innerText = est ? `$${Math.round(est).toLocaleString()}` : "$0";
    document.getElementById("dispSqft").innerText = data.sqft ? `${data.sqft.toLocaleString()} sqft` : "1,200 sqft";

    // Quick baseline MAO: ARV - ($40/sqft + $10k) - 9% fees - 15% margin
    const sqft = data.sqft || 1200;
    const rehab = (sqft * 40) + 10000;
    const fees = est * 0.09;
    const profit = est * 0.15;
    const mao = Math.max(0, est - rehab - fees - profit);
    document.getElementById("dispMao").innerText = `$${Math.round(mao).toLocaleString()}`;

    // Fill agent inputs
    document.getElementById("inputAgentName").value = data.agent_name || "";
    document.getElementById("inputAgentPhone").value = data.agent_phone || "";
    document.getElementById("inputAgentEmail").value = data.agent_email || "";
  }

  btnPush.addEventListener("click", async () => {
    if (!currentData) return;

    btnPush.disabled = true;
    btnPush.innerText = "Pushing to Desk...";

    // Capture edits from inputs
    currentData.agent_name = document.getElementById("inputAgentName").value.trim() || currentData.agent_name || "Listing Agent";
    currentData.agent_phone = document.getElementById("inputAgentPhone").value.trim() || currentData.agent_phone || "";
    currentData.agent_email = document.getElementById("inputAgentEmail").value.trim() || currentData.agent_email || "";

    try {
      const res = await fetch("http://localhost:8001/api/fixers/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentData)
      });
      const d = await res.json();
      if (d.status === "success") {
        alertBox.className = "alert alert-success";
        alertBox.innerHTML = `✓ Pushed to Lauren's Desk!<br><span style="font-size:10px; font-weight:normal;">Target Offer: $${Math.round(d.fixer.underwriting.offer_price).toLocaleString()}</span>`;
        alertBox.style.display = "block";
        btnPush.innerText = "✓ Added to Lauren's Desk";
      } else {
        showError(d.message || "Failed to push to Deal Hunter.");
        btnPush.disabled = false;
        btnPush.innerText = "🚀 Push to Lauren's Desk";
      }
    } catch (err) {
      showError("Cannot reach Deal Hunter server at localhost:8001. Is the app running?");
      btnPush.disabled = false;
      btnPush.innerText = "🚀 Push to Lauren's Desk";
    }
  });

  function showError(msg) {
    loadingBox.style.display = "none";
    alertBox.className = "alert alert-error";
    alertBox.innerText = msg;
    alertBox.style.display = "block";
  }
});
