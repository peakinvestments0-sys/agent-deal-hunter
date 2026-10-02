/**
 * Content Script for Redfin Pages (Single Listing + Bulk Search Results)
 * Scrapes property details, agent contacts, and remarks for Lauren's Trojan Horse Desk.
 */

function extractRedfinData() {
  const data = {
    address: "",
    city: "Melbourne",
    county: "BREVARD",
    zip: "",
    list_price: 0,
    redfin_estimate: 0,
    dom: 1,
    sqft: 1200,
    beds: "",
    baths: "",
    year_built: "",
    remarks: "",
    photo_url: "",
    redfin_url: window.location.href,
    agent_name: "",
    agent_phone: "",
    agent_email: "",
    brokerage: ""
  };

  // 1. Address
  const streetEl = document.querySelector('[data-rf-test-id="abp-streetLine"]') ||
                   document.querySelector('.street-address') ||
                   document.querySelector('h1.full-address');
  if (streetEl) data.address = streetEl.innerText.trim();

  const cityZipEl = document.querySelector('[data-rf-test-id="abp-cityStateZip"]') ||
                    document.querySelector('.dp-subtext') ||
                    document.querySelector('.citystatezip');
  if (cityZipEl) {
    const raw = cityZipEl.innerText.trim();
    const parts = raw.split(',');
    if (parts.length > 0) data.city = parts[0].trim();
    const zipMatch = raw.match(/\b\d{5}\b/);
    if (zipMatch) data.zip = zipMatch[0];
  }

  // 2. Listing Price
  const priceEl = document.querySelector('[data-rf-test-id="abp-price"] .statsValue') ||
                  document.querySelector('.statsValue') ||
                  document.querySelector('.price');
  if (priceEl) {
    const pNum = parseFloat(priceEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(pNum)) data.list_price = pNum;
  }

  // 3. Redfin Estimate
  const estEl = document.querySelector('[data-rf-test-id="avm-price"]') ||
                document.querySelector('.avm-price') ||
                document.querySelector('[data-rf-test-id="estimate-price"]');
  if (estEl) {
    const eNum = parseFloat(estEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(eNum)) data.redfin_estimate = eNum;
  }

  // 4. SqFt
  const sqftEl = document.querySelector('[data-rf-test-id="abp-sqFt"] .statsValue') ||
                 document.querySelector('.sqft .statsValue');
  if (sqftEl) {
    const sqNum = parseFloat(sqftEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(sqNum)) data.sqft = sqNum;
  }

  // 5. Beds / Baths
  const bedsEl = document.querySelector('[data-rf-test-id="abp-beds"] .statsValue');
  if (bedsEl) data.beds = bedsEl.innerText.trim();
  const bathsEl = document.querySelector('[data-rf-test-id="abp-baths"] .statsValue');
  if (bathsEl) data.baths = bathsEl.innerText.trim();

  // 6. Days on Market (DOM)
  const allText = document.body.innerText;
  const domMatch = allText.match(/(\d+)\s+days?\s+on\s+redfin/i) || allText.match(/(\d+)\s+days?\s+on\s+market/i);
  if (domMatch) {
    data.dom = parseInt(domMatch[1], 10);
  }

  // 7. Year Built
  const yrMatch = allText.match(/year\s+built\s*[:\n]\s*(\d{4})/i) || allText.match(/built\s+in\s+(\d{4})/i);
  if (yrMatch) data.year_built = yrMatch[1];

  // 8. Public Remarks
  const remarksEl = document.querySelector('[data-rf-test-id="listing-remarks"]') ||
                    document.querySelector('#marketing-remarks-scroll') ||
                    document.querySelector('.remarks');
  if (remarksEl) {
    data.remarks = remarksEl.innerText.trim();
  }

  // 9. Photo URL (OpenGraph Meta or first img)
  const ogImg = document.querySelector('meta[property="og:image"]');
  if (ogImg && ogImg.content) {
    data.photo_url = ogImg.content;
  }

  // Address & City Parsing Fallback
  if (data.address && data.address.includes(',')) {
    const addrParts = data.address.split(',');
    if (addrParts.length >= 2 && (!data.city || data.city === "Melbourne")) {
      data.city = addrParts[1].trim();
    }
    const zMatch = data.address.match(/\b\d{5}\b/);
    if (zMatch && !data.zip) data.zip = zMatch[0];
  }

  // Infer Florida County from City
  const cityUpper = (data.city || "").toUpperCase();
  if (cityUpper.includes("ORLANDO") || cityUpper.includes("WINTER PARK") || cityUpper.includes("APOPKA") || cityUpper.includes("OCOEE")) {
    data.county = "ORANGE";
  } else if (cityUpper.includes("MELBOURNE") || cityUpper.includes("PALM BAY") || cityUpper.includes("TITUSVILLE") || cityUpper.includes("COCOA") || cityUpper.includes("ROCKLEDGE")) {
    data.county = "BREVARD";
  } else if (cityUpper.includes("KISSIMMEE") || cityUpper.includes("ST CLOUD")) {
    data.county = "OSCEOLA";
  } else if (cityUpper.includes("SANFORD") || cityUpper.includes("LAKE MARY") || cityUpper.includes("ALTAMONTE") || cityUpper.includes("OVIEDO")) {
    data.county = "SEMINOLE";
  } else if (cityUpper.includes("TAMPA") || cityUpper.includes("BRANDON")) {
    data.county = "HILLSBOROUGH";
  } else if (cityUpper.includes("DELTONA") || cityUpper.includes("DAYTONA")) {
    data.county = "VOLUSIA";
  } else if (cityUpper.includes("LAKELAND")) {
    data.county = "POLK";
  }

  // 10. Extract Listing Agent Details directly from HTML / Embedded React state
  const html = document.documentElement.innerHTML;
  
  // JSON payload pattern in reactServerState
  const mName = html.match(/\\?"listingAgentName\\?"\s*:\s*\\?"([^\\"]+)/i);
  if (mName && mName[1]) data.agent_name = mName[1].trim();

  const mPhone = html.match(/\\?"listingAgentNumber\\?"\s*:\s*\\?"([^\\"]+)/i);
  if (mPhone && mPhone[1]) data.agent_phone = mPhone[1].trim();

  const mBPhone = html.match(/\\?"listingBrokerNumber\\?"\s*:\s*\\?"([^\\"]+)/i);
  const mBroker = html.match(/\\?"brokerName\\?"\s*:\s*\\?"([^\\"]+)/i);
  if (mBroker && mBroker[1]) data.brokerage = mBroker[1].trim();

  if (!data.agent_phone && mBPhone && mBPhone[1]) {
    data.agent_phone = mBPhone[1].trim();
  }

  // Fallback: check DOM elements
  if (!data.agent_name) {
    const listedByEl = document.querySelector('[data-rf-test-id="agentInfoItem-agentDisplay"]');
    if (listedByEl) {
      const headingEl = listedByEl.querySelector('.agent-basic-details--heading');
      if (headingEl) {
        data.agent_name = headingEl.innerText.replace(/Listed by\s*/i, '').trim();
      }
      const brokerEl = listedByEl.querySelector('.agent-basic-details--broker');
      if (brokerEl && !data.brokerage) {
        data.brokerage = brokerEl.innerText.replace(/^[•\s]+/, '').trim();
      }
    }
  }

  // Fallback: check public remarks for direct agent phone
  if (!data.agent_phone && data.remarks) {
    const remarksPhone = data.remarks.match(/(?:call|text|cell|agent|contact)[:\s]*(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})/i);
    if (remarksPhone) {
      data.agent_phone = remarksPhone[1].trim();
    }
  }

  // Strict check: if phone is Redfin corporate tour or call center number, discard it
  if (isRedfinCorporateNumber(data.agent_phone)) {
    data.agent_phone = "";
  }

  return data;
}

function extractRedfinSearchResults() {
  const cards = document.querySelectorAll('.HomeCardContainer, [data-rf-test-name="mapHomeCard"], .bp-HomeCard, .homecard, div[id^="MapHomeCard_"]');
  const results = [];
  const seenUrls = new Set();

  cards.forEach((card, idx) => {
    try {
      const linkEl = card.querySelector('a.link-and-anchor, a[href*="/home/"], a.bp-HomeCard__Address, a');
      if (!linkEl) return;
      let href = linkEl.getAttribute('href');
      if (!href || !href.includes('/home/')) return;
      if (!href.startsWith('http')) {
        href = 'https://www.redfin.com' + href;
      }
      if (seenUrls.has(href)) return;
      seenUrls.add(href);

      // Address
      let addr = linkEl.innerText.trim();
      const addrEl = card.querySelector('.bp-HomeCard__Address, .street-address, [data-rf-test-name="homecard-address"]');
      if (addrEl && addrEl.innerText) addr = addrEl.innerText.trim();

      // Price
      let price = 0;
      const priceEl = card.querySelector('.bp-HomeCard__Price--value, .homecardV2Price, .price');
      if (priceEl) {
        const pNum = parseFloat(priceEl.innerText.replace(/[^0-9.]/g, ''));
        if (!isNaN(pNum)) price = pNum;
      }

      // Stats
      let beds = "";
      let baths = "";
      let sqft = 1200;

      const bedsEl = card.querySelector('.bp-HomeCard__Stats--beds, [data-rf-test-name="homecard-beds"]');
      if (bedsEl) beds = bedsEl.innerText.replace(/[^0-9.]/g, '');

      const bathsEl = card.querySelector('.bp-HomeCard__Stats--baths, [data-rf-test-name="homecard-baths"]');
      if (bathsEl) baths = bathsEl.innerText.replace(/[^0-9.]/g, '');

      const sqftEl = card.querySelector('.bp-HomeCard__Stats--sqft, [data-rf-test-name="homecard-sqft"]');
      if (sqftEl) {
        const sNum = parseInt(sqftEl.innerText.replace(/[^0-9]/g, ''), 10);
        if (!isNaN(sNum)) sqft = sNum;
      }

      // Photo
      let photoUrl = "";
      const imgEl = card.querySelector('img.homecard-image, img.bp-HomeCard__Photo, img');
      if (imgEl) {
        photoUrl = imgEl.src || imgEl.getAttribute('data-src') || "";
      }

      // City & Zip derivation from URL
      let city = "Melbourne";
      let county = "BREVARD";
      let zip = "";

      const urlParts = href.split('/');
      if (urlParts.length >= 6) {
        city = decodeURIComponent(urlParts[4]).replace(/-/g, ' ');
        const zMatch = urlParts[5].match(/\b\d{5}\b/);
        if (zMatch) zip = zMatch[0];
      }

      const cityUpper = city.toUpperCase();
      if (cityUpper.includes("ORLANDO") || cityUpper.includes("WINTER PARK") || cityUpper.includes("APOPKA") || cityUpper.includes("OCOEE")) {
        county = "ORANGE";
      } else if (cityUpper.includes("MELBOURNE") || cityUpper.includes("PALM BAY") || cityUpper.includes("TITUSVILLE") || cityUpper.includes("COCOA") || cityUpper.includes("ROCKLEDGE")) {
        county = "BREVARD";
      } else if (cityUpper.includes("KISSIMMEE") || cityUpper.includes("ST CLOUD")) {
        county = "OSCEOLA";
      } else if (cityUpper.includes("SANFORD") || cityUpper.includes("LAKE MARY") || cityUpper.includes("OVIEDO")) {
        county = "SEMINOLE";
      } else if (cityUpper.includes("TAMPA") || cityUpper.includes("BRANDON")) {
        county = "HILLSBOROUGH";
      } else if (cityUpper.includes("DELTONA") || cityUpper.includes("DAYTONA")) {
        county = "VOLUSIA";
      } else if (cityUpper.includes("LAKELAND")) {
        county = "POLK";
      }

      results.push({
        id: `rf_card_${Date.now()}_${idx}`,
        address: addr,
        city: city,
        county: county,
        zip: zip,
        list_price: price,
        redfin_estimate: Math.round(price * 1.25),
        dom: 1,
        sqft: sqft,
        beds: beds,
        baths: baths,
        year_built: "",
        remarks: "",
        photo_url: photoUrl,
        redfin_url: href,
        agent_name: "Listing Agent",
        agent_phone: "",
        agent_email: "",
        brokerage: ""
      });
    } catch (e) {
      console.error("Error parsing card", e);
    }
  });

  return results;
}

function isRedfinCorporateNumber(phone) {
  if (!phone) return false;
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 10) return false;

  const redfinKnown = [
    "4075845076",
    "3213334170",
    "4075128121",
    "8447597732",
    "8779733346"
  ];

  if (redfinKnown.includes(digits) || digits.endsWith("5845076") || digits.endsWith("3334170") || digits.endsWith("5128121")) {
    return true;
  }

  if (/^1?(800|844|855|866|877|888)/.test(digits)) {
    return true;
  }

  return false;
}

// Listen for popup requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SCRAPE_REDFIN") {
    const isSingle = window.location.href.includes("/home/");
    if (isSingle) {
      const data = extractRedfinData();
      sendResponse({ success: true, mode: "SINGLE", data: data });
    } else {
      const results = extractRedfinSearchResults();
      sendResponse({ success: true, mode: "SEARCH_RESULTS", count: results.length, listings: results });
    }
  }
  return true;
});
