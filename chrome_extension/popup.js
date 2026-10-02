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
          
          // 1. Agent Name & Phone & Brokerage
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

          // Fallback DOM for Agent
          if (!l.agent_name || l.agent_name === "Listing Agent") {
            const mListed = html.match(/Listed by <span>([^<]+)<\/span>/i) ||
                            html.match(/class=["'][^"']*agent-basic-details--heading[^"']*["']>Listed by\s*([^<]+)<\//i);
            if (mListed && mListed[1]) l.agent_name = mListed[1].trim();
          }

          // 2. Photo URL (OpenGraph / JSON / CDN)
          const ogImg = html.match(/<meta\s+property=["']og:image["']\s+content=["']([^"']+)["']/i) ||
                        html.match(/<meta\s+name=["']twitter:image["']\s+content=["']([^"']+)["']/i);
          if (ogImg && ogImg[1] && !ogImg[1].includes('redfin_logo') && !ogImg[1].includes('default')) {
            l.photo_url = ogImg[1].replace(/&amp;/g, '&');
          } else if (!l.photo_url) {
            const mPhoto = html.match(/\\?"(?:photoUrl|fullSizeUrl|primaryPhotoUrl)\\?"\s*:\s*\\?"(https:[^\\"]+)/i) ||
                           html.match(/(https:\/\/(?:ssl|photos)\.cdn-redfin\.com\/photo\/\d+\/[a-zA-Z0-9_\-\/]+\.jpg)/i);
            if (mPhoto && mPhoto[1]) {
              l.photo_url = mPhoto[1].replace(/\\/g, '');
            }
          }

          // 3. List Price
          const ogPrice = html.match(/<meta\s+property=["'](?:og|product):price:amount["']\s+content=["']([\d\.]+)["']/i);
          if (ogPrice && ogPrice[1] && parseFloat(ogPrice[1]) > 0) {
            l.list_price = parseFloat(ogPrice[1]);
          } else {
            const mPrice = html.match(/\\?"price\\?"\s*:\s*\{?\\?"value\\?"?\s*:\s*(\d+)/i) ||
                           html.match(/\\?"listingPrice\\?"\s*:\s*(\d+)/i) ||
                           html.match(/\\?"price\\?"\s*:\s*(\d{5,8})/i);
            if (mPrice && mPrice[1]) {
              l.list_price = parseFloat(mPrice[1]);
            } else {
              const mDomPrice = html.match(/data-rf-test-id=["']abp-price["'][^>]*>[\s\S]*?\$([0-9,]+)/i) ||
                                html.match(/class=["'][^"']*statsValue[^"']*["']>\$([0-9,]+)/i);
              if (mDomPrice && mDomPrice[1]) {
                const p = parseFloat(mDomPrice[1].replace(/,/g, ''));
                if (!isNaN(p) && p > 0) l.list_price = p;
              }
            }
          }

          // 4. Redfin Estimate / AVM
          const mEst = html.match(/\\?"redfinEstimate\\?"\s*:\s*\{?\\?"value\\?"?\s*:\s*(\d+)/i) ||
                       html.match(/\\?"predictedValue\\?"\s*:\s*(\d+)/i) ||
                       html.match(/\\?"avmPrice\\?"\s*:\s*(\d+)/i) ||
                       html.match(/data-rf-test-id=["']avm-price["'][^>]*>[\s\S]*?\$([0-9,]+)/i);
          if (mEst && mEst[1]) {
            l.redfin_estimate = parseFloat(mEst[1].toString().replace(/,/g, ''));
          } else if (l.list_price > 0) {
            l.redfin_estimate = Math.round(l.list_price * 1.25);
          }

          // 5. SqFt
          const mSqft = html.match(/\\?"sqFt\\?"\s*:\s*\{?\\?"value\\?"?\s*:\s*(\d+)/i) ||
                        html.match(/\\?"sqft\\?"\s*:\s*(\d+)/i) ||
                        html.match(/\\?"squareFeet\\?"\s*:\s*(\d+)/i) ||
                        html.match(/data-rf-test-id=["']abp-sqFt["'][^>]*>[\s\S]*?([0-9,]+)/i) ||
                        html.match(/([0-9,]+)\s*Sq\s*Ft/i);
          if (mSqft && mSqft[1]) {
            const parsedSq = parseInt(mSqft[1].toString().replace(/,/g, ''), 10);
            if (parsedSq > 200 && parsedSq < 50000) {
              l.sqft = parsedSq;
            }
          }

          // 6. Beds & Baths
          const mBeds = html.match(/\\?"(?:beds|numBeds)\\?"\s*:\s*(\d+)/i) || html.match(/(\d+)\s*beds?/i);
          if (mBeds && mBeds[1]) l.beds = mBeds[1];

          const mBaths = html.match(/\\?"(?:baths|numBaths)\\?"\s*:\s*([\d\.]+)/i) || html.match(/([\d\.]+)\s*baths?/i);
          if (mBaths && mBaths[1]) l.baths = mBaths[1];

          // 7. Year Built
          const mYr = html.match(/\\?"yearBuilt\\?"\s*:\s*\{?\\?"value\\?"?\s*:\s*(\d{4})/i) ||
                      html.match(/\\?"yearBuilt\\?"\s*:\s*(\d{4})/i) ||
                      html.match(/Built in (\d{4})/i);
          if (mYr && mYr[1]) l.year_built = mYr[1];

          // 8. Public Remarks
          const mRemarks = html.match(/data-rf-test-id=["']listing-remarks["'][^>]*>([\s\S]*?)<\/div>/i) ||
                           html.match(/\\?"remarks\\?"\s*:\s*\\?"([^\\"]+)/i) ||
                           html.match(/\\?"publicRemarks\\?"\s*:\s*\\?"([^\\"]+)/i);
          if (mRemarks && mRemarks[1]) {
            l.remarks = mRemarks[1].replace(/<[^>]+>/g, ' ').replace(/\\n/g, ' ').replace(/\\"/g, '"').trim();
          }

          // 9. DOM
          const mDom = html.match(/(\d+)\s+days?\s+on\s+redfin/i) || html.match(/(\d+)\s+days?\s+on\s+market/i);
          if (mDom && mDom[1]) l.dom = parseInt(mDom[1], 10);
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
