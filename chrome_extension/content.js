/**
 * Content Script for Redfin Pages (Single Listing + Bulk Search Results)
 * Scrapes property details, agent contacts, and remarks for Lauren's Trojan Horse Desk.
 */

function inferFloridaCounty(city, address, zip) {
  const c = (city || "").toUpperCase().trim();
  const a = (address || "").toUpperCase();

  // Pinellas
  if (/ST\s*PETE|ST\s*PETERSBURG|CLEARWATER|LARGO|PINELLAS\s*PARK|DUNEDIN|TARPON\s*SPRINGS|SAFETY\s*HARBOR|SEMINOLE|GULFPORT|PALM\s*HARBOR|OLDSMAR|MADEIRA\s*BEACH|TREASURE\s*ISLAND|BELLEAIR|KENNETH\s*CITY|INDIAN\s*ROCKS|SOUTH\s*PASADENA/i.test(c)) {
    return "PINELLAS";
  }
  // Hillsborough
  if (/TAMPA|BRANDON|RIVERVIEW|PLANT\s*CITY|VALRICO|RUSKIN|APOLLO\s*BEACH|LUTZ|TEMPLE\s*TERRACE|SEFFNER|GIBSONTON|WIMAUMA/i.test(c)) {
    return "HILLSBOROUGH";
  }
  // Pasco
  if (/NEW\s*PORT\s*RICHEY|PORT\s*RICHEY|WESLEY\s*CHAPEL|ZEPHYRHILLS|LAND\s*O\s*LAKES|HUDSON|HOLIDAY|DADE\s*CITY|TRINITY|ODESSA/i.test(c)) {
    return "PASCO";
  }
  // Orange
  if (/ORLANDO|WINTER\s*PARK|APOPKA|OCOEE|WINTER\s*GARDEN|WINDERMERE|MAITLAND|BELLE\s*ISLE|PINE\s*HILLS/i.test(c)) {
    return "ORANGE";
  }
  // Seminole
  if (/SANFORD|LAKE\s*MARY|ALTAMONTE|OVIEDO|CASSELBERRY|LONGWOOD|WINTER\s*SPRINGS/i.test(c)) {
    return "SEMINOLE";
  }
  // Brevard
  if (/MELBOURNE|PALM\s*BAY|TITUSVILLE|COCOA|ROCKLEDGE|MERRITT\s*ISLAND|SATELLITE\s*BEACH|CAPE\s*CANAVERAL|WEST\s*MELBOURNE|INDIALANTIC|MIMS|MALABAR|GRANT/i.test(c)) {
    return "BREVARD";
  }
  // Sarasota
  if (/SARASOTA|VENICE|NORTH\s*PORT|ENGLEWOOD|OSPREY|NOKOMIS/i.test(c)) {
    return "SARASOTA";
  }
  // Manatee
  if (/BRADENTON|LAKEWOOD\s*RANCH|PALMETTO|ELLENTON|PARRISH|ANNA\s*MARIA/i.test(c)) {
    return "MANATEE";
  }
  // Polk
  if (/LAKELAND|WINTER\s*HAVEN|DAVENPORT|HAINES\s*CITY|BARTOW|LAKE\s*WALES/i.test(c)) {
    return "POLK";
  }
  // Osceola
  if (/KISSIMMEE|ST\s*CLOUD|CELEBRATION|POINCIANA/i.test(c)) {
    return "OSCEOLA";
  }
  // Volusia
  if (/DAYTONA|DELTONA|DELAND|PORT\s*ORANGE|ORMOND\s*BEACH|NEW\s*SMYRNA/i.test(c)) {
    return "VOLUSIA";
  }
  // Lee
  if (/FORT\s*MYERS|CAPE\s*CORAL|LEHIGH\s*ACRES|BONITA\s*SPRINGS|ESTERO/i.test(c)) {
    return "LEE";
  }
  // Palm Beach
  if (/WEST\s*PALM\s*BEACH|BOCA\s*RATON|BOYNTON\s*BEACH|DELRAY\s*BEACH|JUPITER|WELLINGTON|LAKE\s*WORTH/i.test(c)) {
    return "PALM BEACH";
  }
  // Broward
  if (/FORT\s*LAUDERDALE|PEMBROKE\s*PINES|HOLLYWOOD|CORAL\s*SPRINGS|MIRAMAR|POMPANO\s*BEACH|DAVIE|PLANTATION/i.test(c)) {
    return "BROWARD";
  }
  // Miami-Dade
  if (/MIAMI|HIALEAH|HOMESTEAD|CORAL\s*GABLES|DORAL|KENDALL|AVENTURA/i.test(c)) {
    return "MIAMI-DADE";
  }
  // Duval
  if (/JACKSONVILLE|ATLANTIC\s*BEACH|NEPTUNE\s*BEACH/i.test(c)) {
    return "DUVAL";
  }
  // Marion
  if (/OCALA|BELLEVIEW/i.test(c)) {
    return "MARION";
  }
  // Lake
  if (/CLERMONT|LEESBURG|EUSTIS|MOUNT\s*DORA|TAVARES/i.test(c)) {
    return "LAKE";
  }

  return "FLORIDA";
}

function extractRedfinData() {
  const data = {
    address: "",
    city: "Florida",
    county: "FLORIDA",
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
                   document.querySelector('h1.full-address') ||
                   document.querySelector('[class*="street-address"]');
  if (streetEl) data.address = streetEl.innerText.trim();

  const cityZipEl = document.querySelector('[data-rf-test-id="abp-cityStateZip"]') ||
                    document.querySelector('.dp-subtext') ||
                    document.querySelector('.citystatezip') ||
                    document.querySelector('[class*="cityStateZip"]');
  if (cityZipEl) {
    const raw = cityZipEl.innerText.trim();
    const parts = raw.split(',');
    if (parts.length > 0) data.city = parts[0].trim();
    const zipMatch = raw.match(/\b\d{5}\b/);
    if (zipMatch) data.zip = zipMatch[0];
  }

  // URL fallback for address and city
  if (!data.address || !data.city || data.city === "Florida") {
    const urlParts = window.location.pathname.split('/');
    if (urlParts.length >= 4) {
      if (urlParts[2]) data.city = decodeURIComponent(urlParts[2]).replace(/-/g, ' ');
      if (urlParts[3]) {
        const seg = decodeURIComponent(urlParts[3]);
        const zMatch = seg.match(/\b\d{5}\b/);
        if (zMatch) data.zip = zMatch[0];
        data.address = seg.replace(/-\d{5}$/, '').replace(/-/g, ' ');
      }
    }
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
                document.querySelector('[data-rf-test-id="estimate-price"]') ||
                document.querySelector('[class*="avm-price"]');
  if (estEl) {
    const eNum = parseFloat(estEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(eNum)) data.redfin_estimate = eNum;
  }

  // 4. SqFt
  const sqftEl = document.querySelector('[data-rf-test-id="abp-sqFt"] .statsValue') ||
                 document.querySelector('.sqft .statsValue') ||
                 document.querySelector('[class*="sqFt"] .statsValue') ||
                 document.querySelector('[data-rf-test-name="sqFt"] .statsValue');
  if (sqftEl) {
    const sqNum = parseFloat(sqftEl.innerText.replace(/[^0-9.]/g, ''));
    if (!isNaN(sqNum)) data.sqft = sqNum;
  }

  // 5. Beds / Baths
  const bedsEl = document.querySelector('[data-rf-test-id="abp-beds"] .statsValue') || document.querySelector('[class*="beds"] .statsValue');
  if (bedsEl) data.beds = bedsEl.innerText.trim();
  const bathsEl = document.querySelector('[data-rf-test-id="abp-baths"] .statsValue') || document.querySelector('[class*="baths"] .statsValue');
  if (bathsEl) data.baths = bathsEl.innerText.trim();

  // 6. Days on Market (DOM) / timeOnRedfin
  const html = document.documentElement.innerHTML;
  const torMatch = html.match(/"timeOnRedfin":\s*\{\s*"value":\s*(\d+)/i) || html.match(/"timeOnRedfin":\s*(\d+)/i);
  if (torMatch && torMatch[1]) {
    const ms = parseInt(torMatch[1], 10);
    if (ms > 86400000) {
      data.dom = Math.max(1, Math.round(ms / (1000 * 60 * 60 * 24)));
    } else if (ms > 0) {
      data.dom = 1;
    }
  } else {
    const allText = document.body.innerText;
    const domMatch = allText.match(/(\d+)\s+days?\s+on\s+redfin/i) || allText.match(/(\d+)\s+days?\s+on\s+market/i);
    if (domMatch) {
      data.dom = parseInt(domMatch[1], 10);
    }
  }

  // 7. Year Built
  const allText = document.body.innerText;
  const yrMatch = allText.match(/year\s+built\s*[:\n]\s*(\d{4})/i) || allText.match(/built\s+in\s+(\d{4})/i);
  if (yrMatch) data.year_built = yrMatch[1];

  // 8. Public Remarks (Multi-Source Extraction)
  let remarksText = "";

  // Priority 1: JSON-LD Description
  const jsonLdScripts = document.querySelectorAll('script[type="application/ld+json"]');
  for (const s of jsonLdScripts) {
    try {
      const parsed = JSON.parse(s.innerText);
      if (parsed && parsed.description) {
        remarksText = parsed.description.trim();
        break;
      }
      if (Array.isArray(parsed)) {
        for (const item of parsed) {
          if (item && item.description) {
            remarksText = item.description.trim();
            break;
          }
        }
      }
    } catch (e) {}
  }

  // Priority 2: DOM selectors
  if (!remarksText) {
    const remarksEl = document.querySelector('[data-rf-test-id="listing-remarks"]') ||
                      document.querySelector('#marketing-remarks-scroll') ||
                      document.querySelector('.remarks') ||
                      document.querySelector('.house-info--marketing-remarks') ||
                      document.querySelector('[class*="ListingRemarks"]') ||
                      document.querySelector('.notes-content');
    if (remarksEl && remarksEl.innerText && remarksEl.innerText.trim().length > 10) {
      remarksText = remarksEl.innerText.trim();
    }
  }

  // Priority 3: Meta tags
  if (!remarksText) {
    const metaDesc = document.querySelector('meta[property="og:description"]') || document.querySelector('meta[name="description"]');
    if (metaDesc && metaDesc.content && metaDesc.content.trim().length > 15) {
      remarksText = metaDesc.content.trim();
    }
  }

  // Priority 4: React state match
  if (!remarksText) {
    const mRem = html.match(/"remarks":\s*\{\s*"value":\s*"((?:\\.|[^"\\])+)"/i) ||
                 html.match(/"publicRemarks":\s*"((?:\\.|[^"\\])+)"/i);
    if (mRem && mRem[1]) {
      remarksText = mRem[1].replace(/\\n/g, ' ').replace(/\\"/g, '"').replace(/\\\//g, '/').trim();
    }
  }

  data.remarks = remarksText;

  // 9. Photo URL
  const ogImg = document.querySelector('meta[property="og:image"]') || document.querySelector('meta[name="twitter:image"]');
  if (ogImg && ogImg.content) {
    data.photo_url = ogImg.content;
  }

  // 10. Florida County Inference
  data.county = inferFloridaCounty(data.city, data.address, data.zip);

  // 11. Extract Listing Agent Details
  const mName = html.match(/"listingAgentName":\s*"([^"\\]+)/i);
  if (mName && mName[1]) data.agent_name = mName[1].trim();

  const mPhone = html.match(/"listingAgentNumber":\s*"([^"\\]+)/i);
  if (mPhone && mPhone[1]) data.agent_phone = mPhone[1].trim();

  const mBPhone = html.match(/"listingBrokerNumber":\s*"([^"\\]+)/i);
  const mBroker = html.match(/"brokerName":\s*"([^"\\]+)/i);
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
  const linkElements = document.querySelectorAll('a[href*="/home/"]');
  const results = [];
  const seenUrls = new Set();

  linkElements.forEach((linkEl, idx) => {
    try {
      let href = linkEl.getAttribute('href') || "";
      if (!href || !href.includes('/home/')) return;
      
      href = href.split('?')[0];
      if (!href.startsWith('http')) {
        href = 'https://www.redfin.com' + href;
      }
      if (seenUrls.has(href)) return;
      seenUrls.add(href);

      const card = linkEl.closest('[class*="Homecard"], [class*="homecard"], [class*="HomeCard"], [data-rf-test-name="mapHomeCard"], div.MapHomecardWrapper') || linkEl.parentElement;

      let addr = "";
      let city = "Florida";
      let zip = "";

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

      // Check DOM on Card
      let cardDom = 1;
      if (card && card.innerText) {
        const domMatch = card.innerText.match(/(\d+)\s*(?:days?|d)\s+on\s+redfin/i) ||
                         card.innerText.match(/(\d+)\s*d\s+ago/i);
        if (domMatch) {
          cardDom = parseInt(domMatch[1], 10);
        }
      }

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
          }
        }
      }

      const county = inferFloridaCounty(city, addr, zip);
      const est = price > 0 ? Math.round(price * 1.25) : 275000;

      results.push({
        id: `rf_card_${Date.now()}_${idx}`,
        address: addr.trim(),
        city: city.trim(),
        county: county,
        zip: zip,
        list_price: price,
        redfin_estimate: est,
        dom: cardDom,
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
