/**
 * Content Script for Redfin Listing Pages
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
  } else if (data.list_price > 0) {
    data.redfin_estimate = data.list_price * 1.25; // baseline heuristic
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
  } else if (cityUpper.includes("KISSIMMEE") || cityUpper.includes("ST CLOUD") || cityUpper.includes("SAINT CLOUD")) {
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

  // 10. Listing Agent, Brokerage & Direct Contact Phone
  // Target the specific "Listed by" section to avoid picking up Redfin buyer agent / tour numbers
  const listedByIdx = allText.search(/Listed\s+by\s+/i);
  if (listedByIdx !== -1) {
    const agentChunk = allText.slice(listedByIdx, listedByIdx + 350);

    // Grab agent name and brokerage
    const lineMatch = agentChunk.match(/Listed\s+by\s+([^•·\n\r]+)(?:[•·\-]\s*([^\n\r]+))?/i);
    if (lineMatch) {
      data.agent_name = lineMatch[1].trim();
      if (lineMatch[2]) {
        data.brokerage = lineMatch[2].replace(/(?:Contact|Phone|Lic|Listing updated).*$/i, '').trim();
      }
    }

    // Grab direct contact phone specifically from this agent section
    const phoneInChunk = agentChunk.match(/(?:Contact|Phone|Cell|Direct|Call|Tel)?[:\s]*(\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})/i);
    if (phoneInChunk) {
      data.agent_phone = phoneInChunk[1].trim();
    }
  }

  // Fallback for brokerage if not found in "Listed by"
  if (!data.brokerage) {
    const brokerMatch = allText.match(/(?:Brokerage|Provided\s+by|Broker|Brokered\s+by)\s*[:\n]?\s*([A-Za-z0-9\s,\.\-]{3,40})/i);
    if (brokerMatch) {
      data.brokerage = brokerMatch[1].trim();
    }
  }

  // Fallback: check if the listing agent put their direct cell inside the public remarks
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

function isRedfinCorporateNumber(phone) {
  if (!phone) return false;
  const digits = phone.replace(/\D/g, "");
  if (digits.length < 10) return false;

  // Known Redfin corporate, tour lead capture, and SMS automated switchboard numbers
  const redfinKnown = [
    "4075845076", // Redfin Orlando tour line
    "3213334170", // Redfin Brevard tour line
    "4075128121", // Redfin automated texting switchboard
    "8447597732", // Redfin 844 support
    "8779733346"  // Redfin corporate toll free
  ];

  if (redfinKnown.includes(digits) || digits.endsWith("5845076") || digits.endsWith("3334170") || digits.endsWith("5128121")) {
    return true;
  }

  // Also check standard toll free prefixes (800, 844, 855, 866, 877, 888) which are never direct cell phones
  if (/^1?(800|844|855|866|877|888)/.test(digits)) {
    return true;
  }

  return false;
}

// Listen for popup requests
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "SCRAPE_REDFIN") {
    const data = extractRedfinData();
    sendResponse({ success: true, data: data });
  }
  return true;
});
