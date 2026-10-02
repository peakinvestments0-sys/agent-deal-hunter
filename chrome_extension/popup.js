let currentData = null;
let bulkListings = [];

document.addEventListener("DOMContentLoaded", async () => {
  const loadingBox = document.getElementById("loadingBox");
  const singleContentBox = document.getElementById("singleContentBox");
  const bulkContentBox = document.getElementById("bulkContentBox");
  const alertBox = document.getElementById("alertBox");
  const btnPushSingle = document.getElementById("btnPushSingle");
  const btnPushBulk = document.getElementById("btnPushBulk");
  const modeBadge = document.getElementById("modeBadge");

  // Query active tab
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab || !tab.url || !tab.url.includes("redfin.com")) {
    loadingBox.innerHTML = `
      <div style="color: #f87171; font-weight: 600;">⚠️ Not on a Redfin page</div>
      <p style="font-size: 10px; color: #94a3b8; margin-top: 4px;">Open a Redfin listing or search page and click this extension again.</p>
    `;
    return;
  }

  // Request scraped data from content script
  try {
    chrome.tabs.sendMessage(tab.id, { action: "SCRAPE_REDFIN" }, (response) => {
      if (chrome.runtime.lastError || !response) {
        chrome.scripting.executeScript({
          target: { tabId: tab.id },
          files: ["content.js"]
        }, () => {
          setTimeout(() => {
            chrome.tabs.sendMessage(tab.id, { action: "SCRAPE_REDFIN" }, (resp2) => {
              if (resp2 && resp2.success) {
                handleResponse(resp2);
              } else {
                showError("Could not read property or search details from this page.");
              }
            });
          }, 300);
        });
        return;
      }
      handleResponse(response);
    });
  } catch (err) {
    showError("Error connecting to page: " + err.message);
  }

  function handleResponse(resp) {
    loadingBox.style.display = "none";
    if (resp.mode === "SEARCH_RESULTS") {
      renderBulkSearch(resp.listings || []);
    } else {
      renderSingleProperty(resp.data || {});
    }
  }

  function renderSingleProperty(data) {
    currentData = data;
    modeBadge.innerText = "Single Fixer";
    singleContentBox.style.display = "block";

    document.getElementById("dispAddress").innerText = data.address || "Unknown Address";
    document.getElementById("dispCity").innerText = `${data.city || "Florida"}, ${data.zip || ""} • ${data.dom || 1} DOM`;
    document.getElementById("dispPrice").innerText = data.list_price ? `$${data.list_price.toLocaleString()}` : "$0";
    
    const est = data.redfin_estimate || (data.list_price * 1.25);
    document.getElementById("dispEstimate").innerText = est ? `$${Math.round(est).toLocaleString()}` : "$0";
    document.getElementById("dispSqft").innerText = data.sqft ? `${data.sqft.toLocaleString()} sqft` : "1,200 sqft";

    // MAO calculation
    const sqft = data.sqft || 1200;
    const rehab = (sqft * 40) + 10000;
    const fees = est * 0.09;
    const profit = est * 0.15;
    const mao = Math.max(0, est - rehab - fees - profit);
    document.getElementById("dispMao").innerText = `$${Math.round(mao).toLocaleString()}`;

    // Agent fields
    document.getElementById("inputAgentName").value = data.agent_name || "";
    document.getElementById("inputAgentPhone").value = data.agent_phone || "";
    document.getElementById("inputBrokerage").value = data.brokerage || "";
  }

  function renderBulkSearch(listings) {
    bulkListings = listings;
    modeBadge.innerText = "Bulk Scanner";
    modeBadge.style.background = "rgba(16, 185, 129, 0.2)";
    modeBadge.style.color = "#34d399";
    modeBadge.style.borderColor = "rgba(16, 185, 129, 0.4)";

    bulkContentBox.style.display = "block";
    document.getElementById("bulkCountBadge").innerText = `${listings.length} Listings`;
    document.getElementById("statBulkListings").innerText = listings.length;
    document.getElementById("btnPushBulk").innerText = `⚡ 1-Click Ingest All ${listings.length} Listings & Agents`;
  }

  // Single Push Handler
  btnPushSingle.addEventListener("click", async () => {
    if (!currentData) return;
    btnPushSingle.disabled = true;
    btnPushSingle.innerText = "Pushing to Desk...";

    currentData.agent_name = document.getElementById("inputAgentName").value.trim() || currentData.agent_name || "Listing Agent";
    currentData.agent_phone = document.getElementById("inputAgentPhone").value.trim() || currentData.agent_phone || "";
    currentData.brokerage = document.getElementById("inputBrokerage").value.trim() || currentData.brokerage || "";

    try {
      const res = await fetch("http://localhost:8001/api/fixers/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(currentData)
      });
      const d = await res.json();
      if (d.status === "success") {
        alertBox.className = "alert alert-success";
        alertBox.innerHTML = `✓ Pushed to Lauren's Desk!<br><span style="font-size:10px; font-weight:normal;">Offer Target: $${Math.round(d.fixer.underwriting.offer_price).toLocaleString()}</span>`;
        alertBox.style.display = "block";
        btnPushSingle.innerText = "✓ Added to Lauren's Desk";
      } else {
        showError(d.message || "Failed to push to Deal Hunter.");
        btnPushSingle.disabled = false;
        btnPushSingle.innerText = "🚀 Push Fixer to Lauren's Desk";
      }
    } catch (err) {
      showError("Connection failed: Make sure Agent Deal Hunter is running on localhost:8001");
      btnPushSingle.disabled = false;
      btnPushSingle.innerText = "🚀 Push Fixer to Lauren's Desk";
    }
  });

  // Bulk Push Handler with Parallel In-Browser Crawl
  btnPushBulk.addEventListener("click", async () => {
    if (!bulkListings || bulkListings.length === 0) return;

    btnPushBulk.disabled = true;
    const progressContainer = document.getElementById("progressContainer");
    const progressText = document.getElementById("progressText");
    const progressPct = document.getElementById("progressPct");
    const progressBarFill = document.getElementById("progressBarFill");

    progressContainer.style.display = "block";
    btnPushBulk.innerText = "Crawling Agent Numbers...";

    let completed = 0;
    const total = bulkListings.length;
    const enrichedListings = [];

    // Helper to scrape single listing page via browser fetch
    async function enrichListing(l) {
      if (!l.redfin_url) return l;
      try {
        const resp = await fetch(l.redfin_url);
        if (resp.ok) {
          const html = await resp.text();
          
          const mName = html.match(/\\?"listingAgentName\\?"\s*:\s*\\?"([^\\"]+)/i);
          if (mName && mName[1]) l.agent_name = mName[1].trim();

          const mPhone = html.match(/\\?"listingAgentNumber\\?"\s*:\s*\\?"([^\\"]+)/i);
          if (mPhone && mPhone[1]) l.agent_phone = mPhone[1].trim();

          const mBPhone = html.match(/\\?"listingBrokerNumber\\?"\s*:\s*\\?"([^\\"]+)/i);
          const mBroker = html.match(/\\?"brokerName\\?"\s*:\s*\\?"([^\\"]+)/i);
          if (mBroker && mBroker[1]) l.brokerage = mBroker[1].trim();

          if (!l.agent_phone && mBPhone && mBPhone[1]) {
            l.agent_phone = mBPhone[1].trim();
          }

          // Fallback DOM
          if (!l.agent_name) {
            const mListed = html.match(/Listed by <span>([^<]+)<\/span>/i);
            if (mListed) l.agent_name = mListed[1].trim();
          }
        }
      } catch (e) {
        console.warn("Failed to enrich url", l.redfin_url, e);
      }
      return l;
    }

    // Process in batches of 4 concurrent fetches
    const batchSize = 4;
    for (let i = 0; i < total; i += batchSize) {
      const batch = bulkListings.slice(i, i + batchSize);
      const batchResults = await Promise.all(batch.map(enrichListing));
      enrichedListings.push(...batchResults);
      completed += batch.length;
      
      const pct = Math.min(100, Math.round((completed / total) * 100));
      progressText.innerText = `Enriched ${completed} / ${total} agent contacts...`;
      progressPct.innerText = `${pct}%`;
      progressBarFill.style.width = `${pct}%`;
    }

    // Send payload to backend
    progressText.innerText = "Ingesting all listings to backend...";
    try {
      const res = await fetch("http://localhost:8001/api/fixers/ingest-bulk", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ listings: enrichedListings })
      });
      const d = await res.json();
      if (d.status === "success") {
        alertBox.className = "alert alert-success";
        alertBox.innerHTML = `✓ ${d.message}<br><span style="font-size:10px; font-weight:normal;">Total Fixers on Desk: ${d.total_fixers}</span>`;
        alertBox.style.display = "block";
        btnPushBulk.innerText = `✓ Added ${enrichedListings.length} Listings!`;
      } else {
        showError(d.message || "Bulk ingest failed.");
        btnPushBulk.disabled = false;
        btnPushBulk.innerText = "⚡ 1-Click Ingest All to Lauren's Desk";
      }
    } catch (err) {
      showError("Connection error: Make sure Agent Deal Hunter is running on localhost:8001");
      btnPushBulk.disabled = false;
      btnPushBulk.innerText = "⚡ 1-Click Ingest All to Lauren's Desk";
    }
  });

  function showError(msg) {
    alertBox.className = "alert alert-error";
    alertBox.innerText = msg;
    alertBox.style.display = "block";
  }
});
