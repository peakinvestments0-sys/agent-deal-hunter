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
                  document.querySelector('.price') ||
                  document.querySelector('[class*="Price"]');
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
                 document.querySelector('.sqft .statsValue') ||
                 document.querySelector('[class*="sqFt"] .statsValue');
  if (sqftEl) {
    const sqNum = parseFloat(sqftEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(sqNum)) data.sqft = sqNum;
  }

  // 5. Beds / Baths
  const bedsEl = document.querySelector('[data-rf-test-id="abp-beds"] .statsValue') || document.querySelector('[class*="beds"] .statsValue');
  if (bedsEl) data.beds = bedsEl.innerText.trim();
  const bathsEl = document.querySelector('[data-rf-test-id="abp-baths"] .statsValue') || document.querySelector('[class*="baths"] .statsValue');
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

  // 9. Photo URL
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

  // 10. Extract Listing Agent Details
  const html = document.documentElement.innerHTML;
  
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

  return data;
}

function extractRedfinSearchResults() {
  // Find all property links on search page
  const linkElements = document.querySelectorAll('a[href*="/home/"]');
  const results = [];
  const seenUrls = new Set();

  linkElements.forEach((linkEl, idx) => {
    try {
      let href = linkEl.getAttribute('href') || "";
      if (!href || !href.includes('/home/')) return;
      
      // Clean query params
      href = href.split('?')[0];
      if (!href.startsWith('http')) {
        href = 'https://www.redfin.com' + href;
      }
      if (seenUrls.has(href)) return;
      seenUrls.add(href);

      // Find surrounding card container
      const card = linkEl.closest('[class*="Homecard"], [class*="homecard"], [class*="HomeCard"], [data-rf-test-name="mapHomeCard"], div.MapHomecardWrapper') || linkEl.parentElement;

      // Address & City Parsing from URL and card
      let addr = "";
      let city = "Melbourne";
      let county = "BREVARD";
      let zip = "";

      // Parse from URL: https://www.redfin.com/FL/Cocoa/2563-Terri-Ln-32926/home/120323468
      const urlParts = href.split('/');
      if (urlParts.length >= 6) {
        city = decodeURIComponent(urlParts[4]).replace(/-/g, ' ');
        const segment = decodeURIComponent(urlParts[5]);
        const zMatch = segment.match(/\b\d{5}\b/);
        if (zMatch) zip = zMatch[0];
        addr = segment.replace(/-\d{5}$/, '').replace(/-/g, ' ');
      }

      if (card) {
        const addrEl = card.querySelector('[class*="Address"], .street-address, [data-rf-test-name="homecard-address"]');
        if (addrEl && addrEl.innerText && addrEl.innerText.trim().length > 3) {
          addr = addrEl.innerText.trim();
        }
      }

      // Price: Check specific price elements first, then card text regex
      let price = 0;
      if (card) {
        const priceEl = card.querySelector('.bp-Homecard__Price--value, [data-rf-test-name="homecard-price"], .homecardV2Price, [class*="Price--value"], [class*="price"]');
        if (priceEl && priceEl.innerText) {
          const pNum = parseFloat(priceEl.innerText.replace(/[^0-9.]/g, ''));
          if (!isNaN(pNum) && pNum > 1000) price = pNum;
        }
        if (price === 0 && card.innerText) {
          const pMatch = card.innerText.match(/\$([0-9]{1,3}(?:,[0-9]{3})+)/);
          if (pMatch && pMatch[1]) {
            const pNum = parseFloat(pMatch[1].replace(/,/g, ''));
            if (!isNaN(pNum) && pNum > 1000) price = pNum;
          }
        }
      }

      // Stats: Beds, Baths, Sqft
      let beds = "";
      let baths = "";
      let sqft = 1200;

      if (card) {
        const bedsEl = card.querySelector('.bp-Homecard__Stats--beds, [class*="beds"], [data-rf-test-name="homecard-beds"]');
        if (bedsEl && bedsEl.innerText) beds = bedsEl.innerText.replace(/[^0-9.]/g, '');

        const bathsEl = card.querySelector('.bp-Homecard__Stats--baths, [class*="baths"], [data-rf-test-name="homecard-baths"]');
        if (bathsEl && bathsEl.innerText) baths = bathsEl.innerText.replace(/[^0-9.]/g, '');

        const sqftEl = card.querySelector('.bp-Homecard__Stats--sqft, [class*="sqft"], [data-rf-test-name="homecard-sqft"]');
        if (sqftEl && sqftEl.innerText) {
          const sNum = parseInt(sqftEl.innerText.replace(/[^0-9]/g, ''), 10);
          if (!isNaN(sNum) && sNum > 200 && sNum < 50000) sqft = sNum;
        }

        // Fallbacks from card text
        if (!beds && card.innerText) {
          const bMatch = card.innerText.match(/(\d+)\s*(?:beds?|bd)/i);
          if (bMatch) beds = bMatch[1];
        }
        if (!baths && card.innerText) {
          const baMatch = card.innerText.match(/([\d\.]+)\s*(?:baths?|ba)/i);
          if (baMatch) baths = baMatch[1];
        }
        if (sqft === 1200 && card.innerText) {
          const sqMatch = card.innerText.match(/([0-9,]+)\s*(?:sq\s*ft|sqft)/i);
          if (sqMatch) {
            const sNum = parseInt(sqMatch[1].replace(/,/g, ''), 10);
            if (!isNaN(sNum) && sNum > 200 && sNum < 50000) sqft = sNum;
          }
        }
      }

      // Photo URL
      let photoUrl = "";
      if (card) {
        const imgEl = card.querySelector('img.bp-Homecard__Photo--image, img[class*="Photo"], img[data-rf-test-name="homecard-photo"], img');
        if (imgEl) {
          const rawSrc = imgEl.src || imgEl.getAttribute('data-src') || imgEl.dataset?.src || "";
          const srcset = imgEl.srcset || imgEl.getAttribute('srcset') || "";
          
          if (rawSrc && !rawSrc.startsWith('data:') && !rawSrc.includes('redfin_logo')) {
            photoUrl = rawSrc;
          } else if (srcset) {
            const parts = srcset.split(',');
            if (parts.length > 0) {
              const bestPart = parts[parts.length - 1].trim().split(' ')[0];
              if (bestPart && !bestPart.startsWith('data:')) {
                photoUrl = bestPart;
              }
            }
          } else if (imgEl.getAttribute('data-src')) {
            photoUrl = imgEl.getAttribute('data-src');
          }
        }
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

      const est = price > 0 ? Math.round(price * 1.25) : 275000;

      results.push({
        id: `rf_card_${Date.now()}_${idx}`,
        address: addr.trim(),
        city: city.trim(),
        county: county,
        zip: zip,
        list_price: price,
        redfin_estimate: est,
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
      console.error("Error parsing link", e);
    }
  });

  return results;
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
