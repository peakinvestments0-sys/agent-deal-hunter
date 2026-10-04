// AGENT DEAL HUNTER - Client Controller
let allAgents = [];
let filteredAgents = [];
let currentCounty = "ALL";
let currentTab = "ALL";
let searchQuery = "";
let selectedAgent = null;
let currentHudData = null;

let currentDesk = "BROOKE";
let allFixers = [];
let filteredFixers = [];

// Settings Caches
let pandadocSettings = {};
let smsSettings = {};
let emailSettings = {};
let botSettings = {};

function sanitizeSmsNoHyphens(text) {
  if (!text) return "";
  return text
    .replace(/(\w)-(\w)/g, "$1 $2")
    .replace(/\s*[-–—]\s*/g, " ")
    .replace(/ +/g, " ")
    .trim();
}

function resolveSpintax(text) {
  if (!text) return "";
  const pattern = /\{([^{}]+)\}/;
  let safety = 0;
  while (safety < 20) {
    safety++;
    const match = pattern.exec(text);
    if (!match) break;
    if (!match[1].includes('|')) {
      break;
    }
    const options = match[1].split('|');
    const chosen = options[Math.floor(Math.random() * options.length)];
    text = text.slice(0, match.index) + chosen + text.slice(match.index + match[0].length);
  }
  return text;
}

const BROOKE_ICEBREAKER_VARIATIONS = [
  // Angle 1: Local Renovation Buyer (carrier-safe, <160 chars)
  "{Hey|Hi} {Agent_FirstName}, Brooke here. We buy 2 to 3 fixer projects a month in {City}. Got anything beat up that will not qualify for traditional retail buyers?",
  
  // Angle 2: Pattern Interrupt / Roughest Property (carrier-safe, <160 chars)
  "{Hey|Hi} {Agent_FirstName}, quick question. What is the roughest property you have seen lately that never made it to MLS? Looking for our next flip in {City}.",
  
  // Angle 3: Pipeline Pocket Inquirer (carrier-safe, <160 chars)
  "{Hi|Hey} {Agent_FirstName}, saw your listing on {Listing_Address}. Do you have any off market fixers coming down the pipeline before they hit the MLS?"
];

function getRandomBrookeIcebreaker() {
  const idx = Math.floor(Math.random() * BROOKE_ICEBREAKER_VARIATIONS.length);
  return BROOKE_ICEBREAKER_VARIATIONS[idx];
}

const SMS_TEMPLATES = {
  icebreaker: BROOKE_ICEBREAKER_VARIATIONS[0],
  double_comm: "Hi {Agent_FirstName}, its Brooke. Our fund is looking to place capital on 2 or 3 as is properties in {City} this month. If you have any sellers needing a quick cash close or pre MLS sale, we will gladly let you keep the full commission or double end it. Got anything coming up?",
  checkin: "Hey {Agent_FirstName}, Brooke checking in for the month! Any new off market deals, fixer opportunities, or listings that fell out of contract recently in {City}? Ready to write clean cash offers with zero contingencies.",
  backup_offer: "Hey {Agent_FirstName}, Brooke here regarding {Listing_Address}. If the seller wants a firm cash backup offer with zero inspection hassle and a 10 day close, let me know where we need to be on price.",
  loi_offer: "Hey {Agent_FirstName}, I ran the numbers on {Listing_Address}.\nWith fully renovated comps around ${ARV} and roughly ${Repairs} in needed work, John is at ${Offer_Amount} cash, as is.\nTerms:\nCash offer, as is\nBuyer pays all closing costs\nNo buyers agent commission needed\nEMD: 1%\n5 day inspection period\nClose on your sellers timeline\nPlease present this to the seller and let us know. Once I hear from you, we can send over the contract to get things moving.\n\nJohnathan Roberts"
};

const EMAIL_TEMPLATES = {
  pocket_hunt: {
    subject: "Off-Market Fixers & Upcoming Listings in {City} (Cash Buyer - Commission Protected)",
    body: `<p>Hi {Agent_FirstName},</p>
<p>I noticed your active listing over at <strong>{Listing_Address}</strong>—great work in the area.</p>
<p>My partners and I are active local cash buyers deploying capital in <strong>{City}</strong> and surrounding Florida markets. We specialize in buying homes completely "as-is" with guaranteed speed:</p>
<ul>
  <li><strong>100% Cash / Proof of Funds Ready</strong></li>
  <li><strong>Zero Financing or Appraisal Contingencies</strong></li>
  <li><strong>Flexible Closings (7–14 days or seller's choice)</strong></li>
  <li><strong>As-Is Condition (No repairs, cleaning, or cleanout required)</strong></li>
</ul>
<p>We work very closely with listing agents: if you have any clients with properties not quite ready for the MLS (deferred maintenance, probate/estate, code violations, or privacy needs), we would love to review them. We are more than happy to have you represent us as the buyer so you retain both sides of the commission.</p>
<p>Do you have any upcoming listings or pocket opportunities coming down the pipeline?</p>
<p>Best regards,<br>
<strong>Johnathan Roberts</strong><br>
407 Flips co.<br>
<a href="mailto:john@407flips.com" style="color: #0284c7; text-decoration: underline;">john@407flips.com</a><br>
<a href="https://407flips.com" target="_blank" style="color: #0284c7; text-decoration: underline;">407flips.com</a><br>
(407) 815-5043</p>`
  },
  backup_offer: {
    subject: "Backup Cash Offer / Fast Close for {Listing_Address}",
    body: `<p>Hi {Agent_FirstName},</p>
<p>I’m reaching out regarding your active listing at <strong>{Listing_Address}</strong>.</p>
<p>We buy properties in as-is condition for our portfolio. If your seller is motivated for a guaranteed, clean transaction—or if you would like a rock-solid cash backup offer in place should financing or appraisal stumble on current buyers—we can submit a formal FAR/BAR As-Is contract today.</p>
<p><strong>Our standard cash terms:</strong><br>
- Escrow Deposit: $2,500 within 48 hours of execution<br>
- Inspection Period: 5 to 7 Calendar Days<br>
- Closing: 10–14 Days with our local title agency</p>
<p>Please let me know what net number the seller is targeting, and we can shoot over a formal pre-filled FAR/BAR immediately.</p>
<p>Best regards,<br>
<strong>Johnathan Roberts</strong><br>
407 Flips co.<br>
<a href="mailto:john@407flips.com" style="color: #0284c7; text-decoration: underline;">john@407flips.com</a><br>
<a href="https://407flips.com" target="_blank" style="color: #0284c7; text-decoration: underline;">407flips.com</a><br>
(407) 815-5043</p>`
  },
  loi_offer: {
    subject: "Official Cash LOI Proposal - {Listing_Address}",
    body: `<p>Hi {Agent_FirstName},</p>
<p>I have reviewed the property at <strong>{Listing_Address}</strong>, including the listing information and the condition details you provided.</p>
<p>With fully renovated comps around <strong>\${ARV}</strong> and roughly <strong>\${Repairs}</strong> in needed work, I’m at <strong>\${Offer_Amount} cash, as-is</strong>.</p>
<p>Here are the proposed terms:</p>
<ul>
  <li><strong>Cash purchase</strong></li>
  <li><strong>Property purchased as-is;</strong> seller to make no repairs</li>
  <li><strong>Buyer to pay closing costs</strong></li>
  <li><strong>Brokerage Commission:</strong> No buyers agent needed</li>
  <li><strong>Earnest money deposit:</strong> 1%</li>
  <li><strong>Inspection period:</strong> 5 days with reasonable access for inspection/walkthrough</li>
  <li><strong>Closing:</strong> Sellers preferred timeline</li>
  <li><strong>LOI expiration or acceptance deadline:</strong> 3 days</li>
  <li><strong>Special terms:</strong> None</li>
</ul>
<p>Please present this offer to the seller. If the seller is interested in moving forward, I will promptly prepare and send the purchase agreement.</p>
<p>Thanks,<br>
<strong>Johnathan Roberts</strong><br>
407 Flips co.<br>
<a href="mailto:john@407flips.com" style="color: #0284c7; text-decoration: underline;">john@407flips.com</a><br>
<a href="https://407flips.com" target="_blank" style="color: #0284c7; text-decoration: underline;">407flips.com</a></p>`
  }
};

// Initialize Application
document.addEventListener("DOMContentLoaded", () => {
  initApp();
});

async function initApp() {
  await loadCounties();
  await loadStats();
  await loadSettings();
  await loadAgents();
  await loadFixers();
  await pollDripStatus();

  // Live polling for inbound SMS replies, stats, and drip queue updates
  setInterval(async () => {
    try {
      await pollDripStatus();
      const res = await fetch("/api/stats");
      const stats = await res.json();
      const inboxBadge = document.getElementById("inboxBadge");
      if (inboxBadge) {
        if (stats.unread_replies_count > 0) {
          inboxBadge.innerText = stats.unread_replies_count;
          inboxBadge.classList.remove("hidden");
        } else {
          inboxBadge.classList.add("hidden");
        }
      }
      // If an agent drawer is open, check if there are new messages or pending autopilot
      if (window.currentOpenDrawerAgentId) {
        const aRes = await fetch(`/api/agent/${window.currentOpenDrawerAgentId}`);
        const aData = await aRes.json();
        const thread = document.getElementById("drawerChatThread");
        if (thread && aData.outreach) {
          const countEl = document.getElementById("drawerMessageCount");
          if (countEl) countEl.innerText = `${aData.outreach.length} message${aData.outreach.length === 1 ? '' : 's'}`;
          const currentCount = parseInt(thread.getAttribute("data-count") || "0", 10);
          if (aData.outreach.length !== currentCount) {
            const typingEl = document.getElementById("drawerTypingIndicator");
            if (typingEl) typingEl.remove();
            thread.setAttribute("data-count", aData.outreach.length);
            thread.innerHTML = renderChatBubbles(aData.agent, aData.outreach);
            thread.scrollTop = thread.scrollHeight;
          } else if (aData.agent && aData.agent.pending_autopilot && !document.getElementById("drawerTypingIndicator")) {
            const delaySecs = aData.agent.pending_autopilot_eta_seconds || 30;
            const typingHtml = `
              <div id="drawerTypingIndicator" class="flex items-center gap-2 p-3 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-300 text-xs shadow-sm max-w-[85%] ml-auto">
                <span class="flex h-2 w-2 relative">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                </span>
                <span class="font-bold">Johnathan is typing...</span>
                <span class="text-slate-400 font-mono text-[10px]" id="autopilotCountdown">(~${delaySecs}s human delay)</span>
              </div>
            `;
            thread.insertAdjacentHTML("beforeend", typingHtml);
            startTypingCountdown(delaySecs);
            thread.scrollTop = thread.scrollHeight;
          }
        }
      }

      // Background check for Lauren Fixers updates if Lauren desk is active
      const laurenDesk = document.getElementById("laurenDeskView");
      if (laurenDesk && !laurenDesk.classList.contains("hidden")) {
        const isEditing = document.activeElement && (document.activeElement.tagName === "TEXTAREA" || document.activeElement.tagName === "INPUT");
        if (!isEditing) {
          const fRes = await fetch("/api/fixers");
          if (fRes.ok) {
            const freshFixers = await fRes.json();
            const freshMsgCount = freshFixers.reduce((acc, f) => acc + (f.messages ? f.messages.length : 0), 0);
            const prevMsgCount = (allFixers || []).reduce((acc, f) => acc + (f.messages ? f.messages.length : 0), 0);
            const freshPhoneHash = freshFixers.map(f => `${f.id}:${f.agent_phone || ''}:${f.status || ''}`).join('|');
            const prevPhoneHash = (allFixers || []).map(f => `${f.id}:${f.agent_phone || ''}:${f.status || ''}`).join('|');

            if (freshMsgCount !== prevMsgCount || freshFixers.length !== (allFixers || []).length || freshPhoneHash !== prevPhoneHash) {
              allFixers = freshFixers;
              populateFixerFilterDropdowns();
              filterFixersList();
            }
          }
        }
      }
    } catch(e) {}
  }, 2500);

  // Instantly re-sync desk the moment you switch back from Google Search tab
  window.addEventListener('focus', () => {
    if (typeof currentDesk !== 'undefined' && currentDesk === 'LAUREN') {
      loadFixers();
    }
  });
}

async function loadCounties() {
  try {
    const res = await fetch("/api/counties");
    const counties = await res.json();
    const sel = document.getElementById("countySelect");
    sel.innerHTML = '<option value="ALL">All Florida Counties</option>';
    counties.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = `${c} County`;
      sel.appendChild(opt);
    });
  } catch (err) {
    console.error("Error loading counties:", err);
  }
}

async function loadStats() {
  try {
    const res = await fetch("/api/stats");
    const d = await res.json();
    document.getElementById("statTotalAgents").innerText = d.total_agents.toLocaleString();
    document.getElementById("statTotalListings").innerText = d.total_listings.toLocaleString();
    document.getElementById("statTotalVolume").innerText = `$${(d.total_volume / 1000000).toFixed(2)}M Volume`;
    document.getElementById("statCountiesCount").innerText = `${d.counties_count} Florida ${d.counties_count === 1 ? 'County' : 'Counties'}`;
    document.getElementById("tabCount_ALL").innerText = d.total_agents;

    // Underdog Model & Flowchart Metrics Ribbon
    const t1El = document.getElementById("statTier1Hot");
    if (t1El) t1El.innerText = (d.tier_1_hot || 0).toLocaleString();
    const goldEl = document.getElementById("statGoldDeals");
    if (goldEl) goldEl.innerText = (d.gold_deals || 0).toLocaleString();
    const t2El = document.getElementById("statTier2Pocket");
    if (t2El) t2El.innerText = (d.tier_2_pocket || 0).toLocaleString();
    const fuEl = document.getElementById("statFollowupsDue");
    if (fuEl) fuEl.innerText = ((d.follow_up_1_due || 0) + (d.follow_up_2_due || 0)).toLocaleString();
    const ccEl = document.getElementById("statColdCall");
    if (ccEl) ccEl.innerText = (d.cold_call_bucket || 0).toLocaleString();

    // Tab Counts & Badges
    const t1Badge = document.getElementById("tabCount_TIER_1");
    if (t1Badge) {
      t1Badge.innerText = d.tier_1_hot || 0;
      t1Badge.classList.toggle("hidden", !(d.tier_1_hot > 0));
    }
    const goldBadge = document.getElementById("tabCount_GOLD");
    if (goldBadge) {
      goldBadge.innerText = d.gold_deals || 0;
      goldBadge.classList.toggle("hidden", !(d.gold_deals > 0));
    }

    const unread = d.unread_replies_count || 0;
    const badge = document.getElementById("headerUnreadBadge");
    const pill = document.getElementById("inboxUnreadPill");
    if (badge) {
      if (unread > 0) {
        badge.innerText = unread;
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
    }
    if (pill) pill.innerText = `${unread} Unread`;
  } catch (err) {
    console.error("Error loading stats:", err);
  }
}

async function loadSettings() {
  try {
    const [pRes, sRes, eRes, bRes] = await Promise.all([
      fetch("/api/pandadoc/settings"),
      fetch("/api/sms/settings"),
      fetch("/api/email/settings"),
      fetch("/api/bot/settings")
    ]);
    pandadocSettings = await pRes.json();
    smsSettings = await sRes.json();
    emailSettings = await eRes.json();
    botSettings = await bRes.json();
    updateSettingsUI();
    updateGlobalGoldenCountBadge();
  } catch (err) {
    console.error("Error loading settings:", err);
  }
}

function updateSettingsUI() {
  const pMode = (pandadocSettings.mode || "production").toLowerCase();
  setPandaDocMode(pMode);
  const badge = document.getElementById("headerPandadocMode");
  if (badge) {
    badge.innerText = pMode.toUpperCase();
    badge.className = pMode === "production" 
      ? "text-[9px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold"
      : "text-[9px] uppercase px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-400 font-bold";
  }
  const contractBadge = document.getElementById("contractPandadocBadge");
  if (contractBadge) {
    contractBadge.innerText = pMode === "production" ? "PANDADOC (LIVE PROD)" : "PANDADOC (TEST SANDBOX)";
    contractBadge.className = pMode === "production"
      ? "px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold"
      : "px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold";
  }

  // Populate Bot settings modal & header badge
  const bMode = (botSettings.mode || "copilot").toLowerCase();
  setBotModeUI(bMode);
  const botBadge = document.getElementById("headerBotModeBadge");
  if (botBadge) {
    botBadge.innerText = bMode.toUpperCase();
    botBadge.className = bMode === "autopilot" 
      ? "text-[9px] uppercase px-1.5 py-0.5 rounded bg-emerald-500/30 text-emerald-300 font-mono font-bold"
      : "text-[9px] uppercase px-1.5 py-0.5 rounded bg-indigo-500/30 text-indigo-200 font-mono font-bold";
  }
  if (document.getElementById("botName")) {
    document.getElementById("botName").value = botSettings.bot_name || "Emma";
  }
  if (document.getElementById("botPartnerName")) {
    document.getElementById("botPartnerName").value = botSettings.partner_name || "John";
    document.getElementById("botCallWindow").value = botSettings.call_window_hours || 3;
    const goldRatio = Math.round((botSettings.zestimate_gold_threshold || 0.80) * 100);
    document.getElementById("botGoldThreshold").value = goldRatio;
    document.getElementById("botGoldDisplay").innerText = `≤ ${goldRatio}% of Zestimate`;
    document.getElementById("botFu1Days").value = botSettings.campaign_followup_1_days || 3;
    document.getElementById("botFu2Days").value = botSettings.campaign_followup_2_days || 7;
    document.getElementById("botColdCallDays").value = botSettings.campaign_coldcall_days || 14;

    // Human reply delay
    const delaySecs = botSettings.auto_send_delay_seconds || 30;
    const delayInput = document.getElementById("botDelayInput");
    const delayDisp = document.getElementById("botDelayDisplay");
    if (delayInput) delayInput.value = delaySecs;
    if (delayDisp) delayDisp.innerText = `${delaySecs}s (±5s natural jitter)`;

    // Gemini settings
    const gemKey = document.getElementById("botGeminiApiKey");
    const gemModel = document.getElementById("botGeminiModel");
    const gemEnabled = document.getElementById("botGeminiEnabled");
    if (gemKey) gemKey.value = botSettings.gemini_api_key || "";
    if (gemModel) gemModel.value = botSettings.gemini_model || "gemini-3.5-flash-lite";
    if (gemEnabled) gemEnabled.checked = botSettings.use_gemini_enhancer !== false;

    // Scheduler settings
    const autoCadenceChk = document.getElementById("botAutoCadenceEnabled");
    if (autoCadenceChk) {
      autoCadenceChk.checked = botSettings.auto_cadence_followup_enabled !== false;
      autoCadenceChk.onchange = async () => {
        try {
          await fetch("/api/scheduler/toggle", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enabled: autoCadenceChk.checked })
          });
          fetchSchedulerStatus();
        } catch (e) {
          console.error("Error toggling scheduler:", e);
        }
      };
    }
    fetchSchedulerStatus();
  }

  // Populate PandaDoc settings modal
  document.getElementById("pandaSandboxKey").value = pandadocSettings.sandbox_key || "";
  document.getElementById("pandaProdKey").value = pandadocSettings.production_key || "";
  document.getElementById("pandaBuyerName").value = pandadocSettings.buyer_name || "Peak Investments LLC";
  document.getElementById("pandaSignerName").value = pandadocSettings.buyer_signer_name || "Johnathan Roberts";
  const tmplInput = document.getElementById("pandaFarbarTemplateId");
  if (tmplInput) tmplInput.value = pandadocSettings.farbar_template_id || "6dCNMVqv5wBQ6gF5UoUjun";

  // Populate SMS settings modal
  document.getElementById("smsBaseUrl").value = smsSettings.base_url || "";
  document.getElementById("smsUser").value = smsSettings.username || "";
  document.getElementById("smsPass").value = smsSettings.password || "";

  // Populate Email settings modal
  document.getElementById("emailHost").value = emailSettings.smtp_server || "mail.smtp2go.com";
  document.getElementById("emailPort").value = emailSettings.smtp_port || 2525;
  document.getElementById("emailUser").value = emailSettings.smtp_user || "";
  document.getElementById("emailPass").value = emailSettings.smtp_password || "";
  document.getElementById("emailSender").value = emailSettings.sender_email || "john@407flips.com";
  document.getElementById("emailReplyTo").value = emailSettings.reply_to || "john@407flips.com";
}

function openBotSettingsModal() {
  openModal('botSettingsModal');
  fetchSchedulerStatus();
}

function setBotModeUI(mode) {
  botSettings.mode = mode;
  const btnCopilot = document.getElementById("btnBotModeCopilot");
  const btnAutopilot = document.getElementById("btnBotModeAutopilot");
  const expl = document.getElementById("botModeExplanation");

  if (mode === "autopilot") {
    btnAutopilot.className = "px-3 py-1.5 rounded-xl text-xs font-bold bg-emerald-600 text-white transition cursor-pointer shadow";
    btnCopilot.className = "px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";
    if (expl) expl.innerHTML = `<strong>⚡ Auto-Pilot Active:</strong> When incoming agent texts arrive, the bot evaluates the flowchart and dispatches after a natural 25–40s human typing pause via Android Gateway.`;
  } else {
    btnCopilot.className = "px-3 py-1.5 rounded-xl text-xs font-bold bg-indigo-600 text-white transition cursor-pointer shadow";
    btnAutopilot.className = "px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";
    if (expl) expl.innerHTML = `<strong>🛡️ Copilot Active (Recommended):</strong> The bot evaluates incoming messages according to the flowchart, tags the tier, and drafts the exact script response in your inbox with a 1-click "Approve &amp; Send" button.`;
  }
}

function togglePasswordVisibility(inputId, btn) {
  const input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    btn.innerText = "🔒";
  } else {
    input.type = "password";
    btn.innerText = "👁️";
  }
}

async function testGeminiConnectionFromModal() {
  const key = document.getElementById("botGeminiApiKey")?.value.trim();
  const model = document.getElementById("botGeminiModel")?.value || "gemini-3.5-flash-lite";
  const alertEl = document.getElementById("botSettingsAlert");
  if (!key) {
    alert("Please enter a Gemini API Key to test.");
    return;
  }
  if (alertEl) {
    alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-violet-500/20 text-violet-300 border border-violet-500/30";
    alertEl.innerText = "⏳ Testing Gemini connection...";
    alertEl.classList.remove("hidden");
  }
  try {
    const res = await fetch("/api/bot/test-gemini", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: key, model: model })
    });
    const d = await res.json();
    if (d.status === "success") {
      alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertEl.innerText = `✓ Connected! Model '${model}' verified successfully.`;
    } else {
      alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30";
      alertEl.innerText = `Gemini Error: ${d.message}`;
    }
  } catch (err) {
    alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-rose-500/20 text-rose-300 border border-rose-500/30";
    alertEl.innerText = `Network error: ${err.message}`;
  }
}

async function toggleGoldenExamplesViewer() {
  const viewer = document.getElementById("goldenExamplesViewer");
  if (!viewer) return;
  const isHidden = viewer.classList.contains("hidden");
  if (isHidden) {
    viewer.classList.remove("hidden");
    await loadGoldenExamplesList();
  } else {
    viewer.classList.add("hidden");
  }
}

async function loadGoldenExamplesList() {
  const listEl = document.getElementById("goldenExamplesList");
  const badgeEl = document.getElementById("goldenExamplesCountBadge");
  if (!listEl) return;
  try {
    const res = await fetch("/api/bot/training");
    const d = await res.json();
    if (badgeEl) badgeEl.innerText = `📚 ${d.count || 0} Golden Examples Learned`;
    if (!d.examples || d.examples.length === 0) {
      listEl.innerHTML = '<div class="text-slate-500 italic py-1">No golden examples logged yet. Edit or approve any bot suggestion to train your voice!</div>';
      return;
    }
    listEl.innerHTML = d.examples.slice(0, 10).map((ex, i) => `
      <div class="p-2 rounded-lg bg-slate-900 border border-slate-800 space-y-1">
        <div class="flex items-center justify-between text-[10px] text-slate-400">
          <span class="font-bold text-violet-300">#${i + 1} Node: ${escapeHtml(ex.node || 'RESPONSE')}</span>
          <span class="font-mono text-slate-500">${escapeHtml(ex.timestamp || '')}</span>
        </div>
        <div class="text-slate-400 text-[10px]"><strong>Agent Inbound:</strong> "${escapeHtml(ex.agent_inbound || '')}"</div>
        <div class="text-emerald-300 text-[10px]"><strong>Learned Reply:</strong> "${escapeHtml(ex.final_approved_text || '')}"</div>
      </div>
    `).join('');
  } catch (e) {
    listEl.innerHTML = `<div class="text-rose-400">Error loading examples: ${e.message}</div>`;
  }
}

// ==========================================
// GOLDEN TRAINING STUDIO & SCRIPT CRITIQUE
// ==========================================
let trainingScenarios = [];
let savedGoldenDataset = [];
let activeTrainingCategory = "ALL";
let activeTrainingDesk = "BROOKE";
let trainingSearchQuery = "";

async function updateGlobalGoldenCountBadge() {
  try {
    const res = await fetch("/api/bot/training");
    const d = await res.json();
    savedGoldenDataset = d.examples || [];
    
    const brookeCount = savedGoldenDataset.filter(e => e.agent_desk === 'BROOKE' || !e.agent_desk).length;
    const laurenCount = savedGoldenDataset.filter(e => e.agent_desk === 'LAUREN').length;
    const lanaCount = savedGoldenDataset.filter(e => e.agent_desk === 'LANA').length;

    const bHeader = document.getElementById("headerBrookeCountBadge");
    if (bHeader) bHeader.innerText = brookeCount;

    const lHeader = document.getElementById("headerLaurenCountBadge");
    if (lHeader) lHeader.innerText = laurenCount;

    const laHeader = document.getElementById("headerLanaCountBadge");
    if (laHeader) laHeader.innerText = lanaCount;

    const bModal = document.getElementById("modalBrookeCountBadge");
    if (bModal) bModal.innerText = brookeCount;

    const lModal = document.getElementById("modalLaurenCountBadge");
    if (lModal) lModal.innerText = laurenCount;

    const laModal = document.getElementById("modalLanaCountBadge");
    if (laModal) laModal.innerText = lanaCount;

    const bDesk = document.getElementById("deskBrookeCountBadge");
    if (bDesk) bDesk.innerText = "10 Stages";

    const lDesk = document.getElementById("deskLaurenCountBadge");
    if (lDesk) lDesk.innerText = "7 Stages";

    const laDesk = document.getElementById("deskLanaCountBadge");
    if (laDesk) laDesk.innerText = "8 Stages";

    const tabBadge = document.getElementById("tabDatasetCount");
    if (tabBadge) {
      tabBadge.innerText = activeTrainingDesk === 'LANA' ? lanaCount : (activeTrainingDesk === 'LAUREN' ? laurenCount : brookeCount);
    }
  } catch (err) {
    console.error("Failed to update golden badge:", err);
  }
}

function updateStudioHeader() {
  const isLauren = activeTrainingDesk === 'LAUREN';
  const isLana = activeTrainingDesk === 'LANA';
  const btnBrooke = document.getElementById("studioDeskBrooke") || document.getElementById("btnDeskBrooke");
  const btnLauren = document.getElementById("studioDeskLauren") || document.getElementById("btnDeskLauren");
  const btnLana = document.getElementById("studioDeskLana");
  const tabScenBtn = document.getElementById("btnTabScenarios");
  const tabDataBtn = document.getElementById("btnTabDataset");
  const tabCustBtn = document.getElementById("btnTabCustom");

  const brookeGoldens = savedGoldenDataset.filter(e => e.agent_desk === 'BROOKE' || !e.agent_desk).length;
  const laurenGoldens = savedGoldenDataset.filter(e => e.agent_desk === 'LAUREN').length;
  const lanaGoldens = savedGoldenDataset.filter(e => e.agent_desk === 'LANA').length;

  const bModal = document.getElementById("modalBrookeCountBadge");
  if (bModal) bModal.innerText = brookeGoldens;
  const lModal = document.getElementById("modalLaurenCountBadge");
  if (lModal) lModal.innerText = laurenGoldens;
  const laModal = document.getElementById("modalLanaCountBadge");
  if (laModal) laModal.innerText = lanaGoldens;

  const inactiveBtnCls = "flex-1 py-2 px-3 rounded-xl text-xs font-medium flex items-center justify-center gap-2 bg-slate-900/60 text-slate-400 hover:text-white border border-slate-800 cursor-pointer transition";

  if (btnBrooke) btnBrooke.className = inactiveBtnCls;
  if (btnLauren) btnLauren.className = inactiveBtnCls;
  if (btnLana) btnLana.className = inactiveBtnCls;

  if (isLana) {
    if (btnLana) {
      btnLana.className = "flex-1 py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-lg shadow-emerald-600/30 border border-emerald-400 cursor-pointer transition";
    }
    if (tabScenBtn) tabScenBtn.innerHTML = `📋 Lana Stages (8)`;
    if (tabDataBtn) tabDataBtn.innerHTML = `📚 Lana Golden Dataset (<span id="tabDatasetCount">${lanaGoldens}</span>)`;
    if (tabCustBtn) tabCustBtn.innerHTML = `➕ Add Lana Objection`;
  } else if (isLauren) {
    if (btnLauren) {
      btnLauren.className = "flex-1 py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-amber-600 to-yellow-600 text-slate-950 shadow-lg shadow-amber-600/30 border border-amber-400 cursor-pointer transition";
    }
    if (tabScenBtn) tabScenBtn.innerHTML = `📋 Lauren Stages (7)`;
    if (tabDataBtn) tabDataBtn.innerHTML = `📚 Lauren Golden Dataset (<span id="tabDatasetCount">${laurenGoldens}</span>)`;
    if (tabCustBtn) tabCustBtn.innerHTML = `➕ Add Lauren Objection`;
  } else {
    if (btnBrooke) {
      btnBrooke.className = "flex-1 py-2 px-3 rounded-xl text-xs font-bold flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-600/30 border border-indigo-400 cursor-pointer transition";
    }
    if (tabScenBtn) tabScenBtn.innerHTML = `📋 Brooke Stages (10)`;
    if (tabDataBtn) tabDataBtn.innerHTML = `📚 Brooke Golden Dataset (<span id="tabDatasetCount">${brookeGoldens}</span>)`;
    if (tabCustBtn) tabCustBtn.innerHTML = `➕ Add Brooke Objection`;
  }
}

function updateCustomScenarioDropdown() {
  const select = document.getElementById("customScenarioNode");
  if (!select) return;

  if (activeTrainingDesk === "LANA") {
    select.innerHTML = `
      <option value="LANA_OPENING_HOOK">1. Infill Builder Opening Hook</option>
      <option value="LANA_ASK_BUILDABLE">2. Buildable Lot & Zoning Verification</option>
      <option value="LANA_ASK_UTILITIES">3. Utilities Check (Water / Sewer / Septic)</option>
      <option value="LANA_DOORBELL_LOI">4. SMS Doorbell & Written LOI Push</option>
      <option value="LANA_MATH_DROP">5. Residual Land Math Drop Objection</option>
      <option value="LANA_FIRM_PRICE">6. Firm Price Pushback (60-Day Backup Cash)</option>
      <option value="LANA_BUILDER_CREDS">7. Builder Credentials & Track Record</option>
      <option value="LANA_IDENTITY">8. Identity Inquiry (Local Builder Partner)</option>
    `;
  } else if (activeTrainingDesk === "LAUREN") {
    select.innerHTML = `
      <option value="LAUREN_OPENING_HOOK">1. Smart Opening Hook (Flattery & Condition)</option>
      <option value="LAUREN_ASK_REPAIR_SCOPE">2. Repair Scope Extraction (Major Mechanicals)</option>
      <option value="LAUREN_ASK_REPAIR_COST">3. Dollar Rehab Extraction (Get Agent's Number)</option>
      <option value="LAUREN_ASK_AGENT_ARV">4. Back-End Resale ARV Extraction</option>
      <option value="LAUREN_MATH_DROP">5. Low ARV Arbitrage Math Drop (Accept Low Comp)</option>
      <option value="LAUREN_HIGH_ARV_ANCHOR">6. High ARV Anchor (Conservative Comps)</option>
      <option value="LAUREN_STANDING_LOI">7. Pushback & 30 Day Standing Written LOI</option>
      <option value="IDENTITY_ANSWERED">8. Identity Inquiry ("Who is this?")</option>
    `;
  } else {
    select.innerHTML = `
      <option value="ENTRY_HOOK_AWAITING_REPLY">1. Inbound Property Pitch</option>
      <option value="OFF_MARKET_CONDITION">2. Condition Vetting (Roof, AC, Interior)</option>
      <option value="OFF_MARKET_PHOTOS">3. Requesting Photos & Access</option>
      <option value="OFF_MARKET_PRICE">4. Inquiring Asking Price</option>
      <option value="OFF_MARKET_GOLD_TIMELINE">5. Asking Decision Timeline (Gold Deal)</option>
      <option value="OFF_MARKET_UPDATED_CREATIVE">6. Retail Price -> Creative Terms Pivot</option>
      <option value="MATT_APPOINTMENT_REQUEST">7. Underwriting Partner Handoff</option>
      <option value="APPOINTMENT_CONFIRMED">8. Confirming Call Appointment</option>
      <option value="TIER_2_NURTURE_ASK">9. Tier 2 Pocket Lead Pivot</option>
      <option value="IDENTITY_EXPLAINED">10. Identity Verification ("Who is this?")</option>
    `;
  }
}

async function openBotTrainingModal(desk = null) {
  if (desk) {
    activeTrainingDesk = desk;
  } else if (!activeTrainingDesk || activeTrainingDesk === "ALL") {
    activeTrainingDesk = "BROOKE";
  }

  openModal("botTrainingModal");
  switchTrainingTab("scenarios");
  updateStudioHeader();
  updateCustomScenarioDropdown();

  // Load scenarios and saved golden examples concurrently
  try {
    const [scenRes, trainRes] = await Promise.all([
      fetch("/api/bot/training/scenarios"),
      fetch("/api/bot/training")
    ]);
    const scenData = await scenRes.json();
    const trainData = await trainRes.json();

    trainingScenarios = scenData.scenarios || [];
    savedGoldenDataset = trainData.examples || [];

    updateGlobalGoldenCountBadge();
    updateStudioHeader();
    renderTrainingCategoryChips();
    renderTrainingStudioScenarios();
  } catch (err) {
    console.error("Error loading training studio:", err);
    const listEl = document.getElementById("scenariosCardList");
    if (listEl) {
      listEl.innerHTML = `<div class="p-4 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs">Error loading training scenarios: ${escapeHtml(err.message)}</div>`;
    }
  }
}

function switchTrainingTab(tab) {
  const tabScen = document.getElementById("tabContentScenarios");
  const tabData = document.getElementById("tabContentDataset");
  const tabCust = document.getElementById("tabContentCustom");

  const btnScen = document.getElementById("btnTabScenarios");
  const btnData = document.getElementById("btnTabDataset");
  const btnCust = document.getElementById("btnTabCustom");

  if (tabScen) tabScen.classList.toggle("hidden", tab !== "scenarios");
  if (tabData) tabData.classList.toggle("hidden", tab !== "dataset");
  if (tabCust) tabCust.classList.toggle("hidden", tab !== "custom");

  const isLana = activeTrainingDesk === "LANA";
  const isLauren = activeTrainingDesk === "LAUREN";
  const activeBtnClass = isLana
    ? "px-3.5 py-1.5 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 transition cursor-pointer"
    : isLauren
    ? "px-3.5 py-1.5 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 transition cursor-pointer"
    : "px-3.5 py-1.5 rounded-lg text-xs font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 transition cursor-pointer";
  const inactiveBtnClass = "px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";

  if (btnScen) btnScen.className = tab === "scenarios" ? activeBtnClass : inactiveBtnClass;
  if (btnData) btnData.className = tab === "dataset" ? activeBtnClass : inactiveBtnClass;
  if (btnCust) btnCust.className = tab === "custom" ? activeBtnClass : inactiveBtnClass;

  if (tab === "dataset") {
    loadSavedGoldenDataset();
  }
}

function renderTrainingCategoryChips() {
  const container = document.getElementById("scenarioCategoryChips");
  if (!container) return;

  const isLana = activeTrainingDesk === "LANA";
  const isLauren = activeTrainingDesk === "LAUREN";
  const currentDeskScenarios = trainingScenarios.filter(s => {
    if (isLana) return s.agent_desk === "LANA";
    if (isLauren) return s.agent_desk === "LAUREN";
    return s.agent_desk === "BROOKE" || !s.agent_desk;
  });

  const categories = ["ALL", ...new Set(currentDeskScenarios.map(s => s.category).filter(Boolean))];

  const categoryChips = categories.map(cat => {
    const isAct = cat === activeTrainingCategory;
    const activeColor = isLana
      ? "bg-emerald-500/30 text-emerald-200 border border-emerald-500/50 shadow-sm"
      : isLauren
      ? "bg-amber-500/30 text-amber-200 border border-amber-500/50 shadow-sm"
      : "bg-indigo-500/30 text-indigo-200 border border-indigo-500/50 shadow-sm";
    const cls = isAct
      ? `px-2.5 py-1 rounded-lg text-[11px] font-bold ${activeColor} cursor-pointer`
      : "px-2.5 py-1 rounded-lg text-[11px] font-medium bg-slate-900 text-slate-400 border border-slate-800 hover:text-white cursor-pointer transition";
    return `<button type="button" onclick="setScenarioCategoryFilter('${escapeHtml(cat)}')" class="${cls}">${cat === 'ALL' ? 'All ' + (isLana ? 'Infill Land' : (isLauren ? 'Trojan Horse' : 'Flowchart')) + ' Stages (' + currentDeskScenarios.length + ')' : escapeHtml(cat)}</button>`;
  }).join('');

  container.innerHTML = `
    <div class="flex flex-wrap items-center justify-between gap-2 w-full">
      <div class="flex items-center gap-2">
        <span class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          ${isLana ? '📐 Lana Stages:' : (isLauren ? '🔨 Lauren Stages:' : '🌿 Brooke Stages:')}
        </span>
      </div>
      <div class="flex flex-wrap items-center gap-1.5">${categoryChips}</div>
    </div>
  `;
}

function setStudioDeskFilter(desk) {
  activeTrainingDesk = desk || "BROOKE";
  activeTrainingCategory = "ALL";
  updateStudioHeader();
  renderTrainingCategoryChips();
  renderTrainingStudioScenarios();
  updateCustomScenarioDropdown();
  const tabData = document.getElementById("tabContentDataset");
  if (tabData && !tabData.classList.contains("hidden")) {
    loadSavedGoldenDataset();
  }
}

function setScenarioCategoryFilter(cat) {
  activeTrainingCategory = cat;
  renderTrainingCategoryChips();
  renderTrainingStudioScenarios();
}

function filterTrainingScenarios(val) {
  trainingSearchQuery = (val || "").trim().toLowerCase();
  renderTrainingStudioScenarios();
}

function renderTrainingStudioScenarios() {
  const container = document.getElementById("scenariosCardList");
  if (!container) return;

  let filtered = trainingScenarios;
  if (activeTrainingDesk === "BROOKE") {
    filtered = filtered.filter(s => s.agent_desk === "BROOKE" || !s.agent_desk);
  } else if (activeTrainingDesk === "LAUREN") {
    filtered = filtered.filter(s => s.agent_desk === "LAUREN");
  } else if (activeTrainingDesk === "LANA") {
    filtered = filtered.filter(s => s.agent_desk === "LANA");
  }
  if (activeTrainingCategory !== "ALL") {
    filtered = filtered.filter(s => s.category === activeTrainingCategory);
  }
  if (trainingSearchQuery) {
    filtered = filtered.filter(s => 
      (s.title || "").toLowerCase().includes(trainingSearchQuery) ||
      (s.node || "").toLowerCase().includes(trainingSearchQuery) ||
      (s.category || "").toLowerCase().includes(trainingSearchQuery) ||
      (s.description || "").toLowerCase().includes(trainingSearchQuery) ||
      (s.sample_inbound || "").toLowerCase().includes(trainingSearchQuery)
    );
  }

  if (filtered.length === 0) {
    container.innerHTML = `
      <div class="text-center py-10 bg-slate-950/40 rounded-2xl border border-slate-800 text-slate-500 text-xs">
        No deal stages match your search query "${escapeHtml(trainingSearchQuery)}".
      </div>
    `;
    return;
  }

  container.innerHTML = filtered.map((s, idx) => {
    // Find if there is an existing golden reply for this node
    const matchingGolden = savedGoldenDataset.find(g => g.node === s.node);
    const existingReply = matchingGolden ? matchingGolden.final_approved_text : "";
    const existingInbound = matchingGolden && matchingGolden.agent_inbound ? matchingGolden.agent_inbound : s.sample_inbound;

    const isLana = s.agent_desk === "LANA";
    const isLauren = s.agent_desk === "LAUREN";
    const deskBadge = isLana
      ? `<span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold">📐 Lana</span>`
      : isLauren
      ? `<span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 font-bold">🔨 Lauren</span>`
      : `<span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-bold">🌿 Brooke</span>`;
    const ruleBadge = (isLauren || isLana)
      ? `<span class="text-[9px] font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-300 border border-rose-500/20 font-medium">Rule: Zero hyphens between words</span>`
      : '';

    return `
      <div class="bg-slate-950/80 border border-slate-800 hover:border-slate-700/80 rounded-2xl p-4 sm:p-5 space-y-3.5 transition shadow-sm" id="card_${s.node}">
        
        <!-- Card Top Bar -->
        <div class="flex flex-wrap items-start justify-between gap-2">
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <span class="w-6 h-6 rounded-lg bg-amber-500/20 text-amber-300 font-mono text-xs font-bold flex items-center justify-center">
                ${idx + 1}
              </span>
              ${deskBadge}
              <h4 class="text-sm font-bold text-white">${escapeHtml(s.title)}</h4>
              <span class="text-[10px] uppercase font-mono px-2 py-0.5 rounded-full bg-slate-800 text-amber-300/80 border border-slate-700 font-bold">${escapeHtml(s.category)}</span>
              ${ruleBadge}
            </div>
            <p class="text-xs text-slate-400 mt-1 pl-8">${escapeHtml(s.description)}</p>
          </div>
          <div class="flex items-center gap-2">
            <span class="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/70 text-indigo-300 border border-indigo-500/30 font-semibold">${escapeHtml(s.node)}</span>
            ${matchingGolden ? '<span class="text-[9px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">✓ Active Golden Memory</span>' : ''}
          </div>
        </div>

        <!-- Simulated Inbound Agent Text -->
        <div class="bg-slate-900/90 rounded-xl p-3 border border-slate-800 space-y-1">
          <div class="flex items-center justify-between text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
            <span>📥 Simulated Agent Message (Trigger)</span>
            <span class="text-slate-500 font-normal">Editable for testing edge-cases</span>
          </div>
          <input type="text" id="inbound_${s.node}" value="${escapeHtml(existingInbound)}" class="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-amber-500/80 font-sans">
        </div>

        <!-- Baseline Default Script (Reference) -->
        <div class="bg-slate-900/40 rounded-xl p-3 border border-slate-800 space-y-1.5">
          <div class="flex items-center justify-between text-[10px] text-slate-400 font-semibold uppercase tracking-wider">
            <span class="flex items-center gap-1.5 text-slate-300 font-bold">
              <span>⚙️ Standard Flowchart Script (Reference)</span>
            </span>
            <button type="button" onclick="copyBaselineToCritique('${s.node}')" class="text-amber-400 hover:text-amber-300 hover:underline flex items-center gap-1 cursor-pointer font-bold text-[11px]" title="Copy this standard script into your critique box below to edit it">
              <span>📋 Copy to Critique Box Below</span>
            </button>
          </div>
          <div id="baseline_${s.node}" class="text-xs text-slate-300 italic leading-relaxed bg-[#060c18] p-2.5 rounded-lg border border-slate-800/80">
            "${escapeHtml(s.default_script || s.default_suggestion || 'No baseline script set.')}"
          </div>
        </div>

        <!-- Critique & Golden Response Textarea -->
        <div class="space-y-1.5">
          <div class="flex items-center justify-between text-[10px] font-semibold uppercase tracking-wider">
            <label class="text-amber-300 flex items-center gap-1.5 font-bold">
              <span>✍️ Your Golden Critique / Authentic Voice (Editable)</span>
            </label>
            <span class="text-emerald-400 font-normal">Type here &bull; Saved to train Gemini</span>
          </div>
          <textarea id="critique_${s.node}" rows="2" placeholder="Write exactly how you want Johnathan/your team to say this..." class="w-full bg-[#0b1220] border-2 border-amber-500/40 focus:border-amber-400 rounded-xl p-3 text-xs text-amber-200 placeholder-slate-500 focus:outline-none font-sans leading-relaxed shadow-inner">${escapeHtml(existingReply || s.default_script || s.default_suggestion || '')}</textarea>
        </div>

        <!-- Live AI Test Result Preview Container -->
        <div id="test_container_${s.node}" class="hidden p-3 rounded-xl bg-gradient-to-r from-violet-950/30 to-indigo-950/30 border border-violet-500/30 text-xs space-y-2">
          <div class="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-violet-300">
            <div class="flex items-center gap-1.5">
              <span class="animate-pulse">✨</span>
              <span>Gemini AI Phrasing Result:</span>
            </div>
            <button type="button" onclick="adoptAIVariant('${s.node}')" class="px-2 py-0.5 rounded bg-violet-600/30 hover:bg-violet-600/50 text-violet-200 border border-violet-400/40 text-[10px] font-semibold transition cursor-pointer">
              ⭐ Adopt AI Phrasing
            </button>
          </div>
          <div id="test_output_${s.node}" class="text-slate-100 font-medium leading-relaxed italic bg-slate-950/70 p-3 rounded-lg border border-slate-800"></div>
        </div>

        <!-- Action Bar -->
        <div class="flex items-center justify-between pt-1">
          <div id="status_badge_${s.node}" class="text-xs"></div>
          <div class="flex items-center gap-2">
            <button type="button" onclick="testScenarioAI('${s.node}')" id="btn_test_${s.node}" class="px-3.5 py-2 rounded-xl bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 border border-violet-500/30 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm">
              <span>✨ Test AI Phrasing</span>
            </button>
            <button type="button" onclick="saveScenarioCritique('${s.node}')" id="btn_save_${s.node}" class="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-md shadow-amber-600/20 cursor-pointer">
              <span>💾 Save Golden Reply</span>
            </button>
          </div>
        </div>

      </div>
    `;
  }).join('');
}

function copyBaselineToCritique(node) {
  const scen = trainingScenarios.find(s => s.node === node);
  if (!scen) return;
  const textarea = document.getElementById(`critique_${node}`);
  if (textarea) {
    textarea.value = scen.default_script || scen.default_suggestion || "";
    textarea.focus();
  }
}

function adoptAIVariant(node) {
  const outputEl = document.getElementById(`test_output_${node}`);
  const textarea = document.getElementById(`critique_${node}`);
  if (outputEl && textarea && outputEl.innerText.trim()) {
    textarea.value = outputEl.innerText.trim();
    textarea.focus();
    const statusEl = document.getElementById(`status_badge_${node}`);
    if (statusEl) {
      statusEl.innerHTML = `<span class="text-emerald-400 text-[11px] font-semibold">✓ AI wording copied to critique! Click 'Save Golden Reply' to lock it in.</span>`;
      setTimeout(() => { if (statusEl) statusEl.innerHTML = ""; }, 4000);
    }
  }
}

async function testScenarioAI(node) {
  const inbound = document.getElementById(`inbound_${node}`)?.value.trim() || "";
  const critique = document.getElementById(`critique_${node}`)?.value.trim() || "";
  const scen = trainingScenarios.find(s => s.node === node);
  const baseline = scen ? (scen.default_script || scen.default_suggestion || "") : "";

  const container = document.getElementById(`test_container_${node}`);
  const output = document.getElementById(`test_output_${node}`);
  const btn = document.getElementById(`btn_test_${node}`);

  if (container) container.classList.remove("hidden");
  if (output) output.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span> Gemini is crafting an authentic variation using your golden training memory...`;
  if (btn) btn.disabled = true;

  try {
    const res = await fetch("/api/bot/training/test-generation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node: node,
        inbound_message: inbound,
        template_reply: critique || baseline
      })
    });
    const d = await res.json();
    if (d.status === "success" && output) {
      output.innerText = d.generated_reply || critique || baseline;
    } else if (output) {
      output.innerText = `Could not generate reply: ${d.message || "Unknown error"}`;
    }
  } catch (err) {
    if (output) output.innerText = `Network error: ${err.message}`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function saveScenarioCritique(node) {
  const inbound = document.getElementById(`inbound_${node}`)?.value.trim() || "";
  const critique = document.getElementById(`critique_${node}`)?.value.trim();
  const scen = trainingScenarios.find(s => s.node === node);
  const baseline = scen ? (scen.default_script || scen.default_suggestion || "") : "";

  if (!critique) {
    alert("Please write your ideal phrasing in the critique box before saving.");
    return;
  }

  const btn = document.getElementById(`btn_save_${node}`);
  const statusEl = document.getElementById(`status_badge_${node}`);
  if (btn) btn.disabled = true;

  try {
    const res = await fetch("/api/bot/training/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node: node,
        agent_inbound: inbound,
        final_approved_text: critique,
        suggested_text: baseline,
        tags: [scen ? scen.category : "Real Estate", node],
        agent_desk: (scen && scen.agent_desk) ? scen.agent_desk : activeTrainingDesk
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      if (statusEl) {
        statusEl.innerHTML = `<span class="text-emerald-400 font-bold flex items-center gap-1">✓ Saved to Gemini Memory! (${d.count} total)</span>`;
        setTimeout(() => { if (statusEl) statusEl.innerHTML = ""; }, 4000);
      }
      await updateGlobalGoldenCountBadge();
    } else {
      if (statusEl) statusEl.innerHTML = `<span class="text-rose-400 font-semibold">Error saving critique</span>`;
    }
  } catch (err) {
    if (statusEl) statusEl.innerHTML = `<span class="text-rose-400 font-semibold">${err.message}</span>`;
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadSavedGoldenDataset() {
  const listEl = document.getElementById("goldenDatasetList");
  if (!listEl) return;
  listEl.innerHTML = `<div class="text-center py-6 text-slate-500 text-xs"><span class="inline-block animate-spin mr-2">⏳</span> Loading saved golden replies...</div>`;

  try {
    const res = await fetch("/api/bot/training");
    const d = await res.json();
    savedGoldenDataset = d.examples || [];
    updateGlobalGoldenCountBadge();

    const isLana = activeTrainingDesk === "LANA";
    const isLauren = activeTrainingDesk === "LAUREN";
    const deskDataset = savedGoldenDataset.filter(ex => {
      if (isLana) return ex.agent_desk === "LANA";
      if (isLauren) return ex.agent_desk === "LAUREN";
      return ex.agent_desk === "BROOKE" || !ex.agent_desk;
    });

    if (deskDataset.length === 0) {
      listEl.innerHTML = `
        <div class="text-center py-10 bg-slate-950/40 rounded-2xl border border-slate-800 text-slate-500 text-xs">
          No golden examples saved for ${isLana ? "Lana" : (isLauren ? "Lauren" : "Brooke")} yet. Use Tab 1 to critique common scenarios!
        </div>
      `;
      return;
    }

    listEl.innerHTML = deskDataset.map((ex, i) => `
      <div class="bg-slate-950/80 border border-slate-800 rounded-xl p-3.5 space-y-2 text-xs" id="dataset_row_${ex.id}">
        <div class="flex items-center justify-between text-[11px]">
          <div class="flex items-center gap-2">
            <span class="w-5 h-5 rounded-md bg-amber-500/20 text-amber-300 font-mono text-[10px] font-bold flex items-center justify-center">#${i + 1}</span>
            <span class="font-bold text-amber-300 font-mono">${escapeHtml(ex.node || 'RESPONSE')}</span>
            <span class="text-slate-500">&bull;</span>
            <span class="text-slate-500 font-mono text-[10px]">${escapeHtml(ex.timestamp || '')}</span>
          </div>
          <div class="flex items-center gap-1.5">
            <button type="button" onclick="quickTestDatasetItem('${ex.id}', '${escapeHtml(ex.node || '')}')" class="px-2 py-1 rounded-lg bg-violet-600/20 hover:bg-violet-600/30 text-violet-300 text-[10px] font-semibold border border-violet-500/30 transition cursor-pointer">
              ✨ Test
            </button>
            <button type="button" onclick="deleteGoldenExample('${ex.id}')" class="px-2 py-1 rounded-lg bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 text-[10px] font-semibold border border-rose-500/30 transition cursor-pointer">
              🗑️ Delete
            </button>
          </div>
        </div>

        <div class="text-slate-400 bg-slate-900/70 p-2.5 rounded-lg border border-slate-800/80 space-y-1">
          <div><strong class="text-slate-300">📥 Agent Trigger:</strong> "${escapeHtml(ex.agent_inbound || '')}"</div>
          <div><strong class="text-emerald-400">⭐ Learned Golden Reply:</strong> <span class="text-slate-100 font-medium">"${escapeHtml(ex.final_approved_text || '')}"</span></div>
        </div>

        <div id="dataset_test_res_${ex.id}" class="hidden p-2 rounded-lg bg-indigo-950/40 border border-indigo-500/30 text-[11px] text-slate-200 italic"></div>
      </div>
    `).join('');

  } catch (err) {
    listEl.innerHTML = `<div class="p-3 rounded-xl bg-rose-500/20 text-rose-300 text-xs">Error loading dataset: ${err.message}</div>`;
  }
}

async function quickTestDatasetItem(id, node) {
  const ex = savedGoldenDataset.find(e => e.id === id);
  if (!ex) return;
  const resEl = document.getElementById(`dataset_test_res_${id}`);
  if (!resEl) return;

  resEl.classList.remove("hidden");
  resEl.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span> Testing Gemini output with this golden example...`;

  try {
    const res = await fetch("/api/bot/training/test-generation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node: node || "OFF_MARKET_CONDITION",
        inbound_message: ex.agent_inbound || "Yeah I have an off-market 3/2 fixer.",
        template_reply: ex.final_approved_text
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      resEl.innerHTML = `<strong>✨ Gemini Result:</strong> "${escapeHtml(d.generated_reply)}"`;
    } else {
      resEl.innerText = `Generation error: ${d.message || "Failed"}`;
    }
  } catch (err) {
    resEl.innerText = `Error: ${err.message}`;
  }
}

async function deleteGoldenExample(id) {
  if (!confirm("Are you sure you want to remove this golden training example from Gemini's memory?")) {
    return;
  }
  try {
    const res = await fetch(`/api/bot/training/${encodeURIComponent(id)}`, {
      method: "DELETE"
    });
    const d = await res.json();
    if (d.status === "success") {
      await updateGlobalGoldenCountBadge();
      await loadSavedGoldenDataset();
    } else {
      alert("Error deleting example: " + (d.message || "Unknown error"));
    }
  } catch (err) {
    alert("Error deleting example: " + err.message);
  }
}

async function testCustomScenarioAI() {
  const node = document.getElementById("customScenarioNode")?.value || "OBJECTION_HANDLING";
  const inbound = document.getElementById("customInboundText")?.value.trim() || "";
  const reply = document.getElementById("customGoldenReply")?.value.trim() || "";
  const resContainer = document.getElementById("customTestResultContainer");
  const resText = document.getElementById("customTestResultText");

  if (!inbound || !reply) {
    alert("Please provide both an inbound trigger text and your ideal reply to test.");
    return;
  }

  if (resContainer) resContainer.classList.remove("hidden");
  if (resText) resText.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span> Testing Gemini AI voice...`;

  try {
    const res = await fetch("/api/bot/training/test-generation", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node: node,
        inbound_message: inbound,
        template_reply: reply
      })
    });
    const d = await res.json();
    if (d.status === "success" && resText) {
      resText.innerText = d.generated_reply || reply;
    } else if (resText) {
      resText.innerText = `Error generating reply: ${d.message || "Unknown error"}`;
    }
  } catch (err) {
    if (resText) resText.innerText = `Network error: ${err.message}`;
  }
}

async function saveCustomScenarioGolden() {
  const node = document.getElementById("customScenarioNode")?.value || "OBJECTION_HANDLING";
  const tagsRaw = document.getElementById("customScenarioTags")?.value.trim() || "";
  const inbound = document.getElementById("customInboundText")?.value.trim() || "";
  const reply = document.getElementById("customGoldenReply")?.value.trim() || "";

  if (!inbound || !reply) {
    alert("Please provide both the inbound text and your golden reply.");
    return;
  }

  const tags = tagsRaw.split(",").map(t => t.trim()).filter(Boolean);
  tags.push(node);

  try {
    const res = await fetch("/api/bot/training/add", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        node: node,
        agent_inbound: inbound,
        final_approved_text: reply,
        suggested_text: reply,
        tags: tags,
        agent_desk: activeTrainingDesk || "BROOKE"
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("✓ Custom objection saved to Golden Dataset! Gemini will now use this in future replies.");
      document.getElementById("customInboundText").value = "";
      document.getElementById("customGoldenReply").value = "";
      document.getElementById("customScenarioTags").value = "";
      document.getElementById("customTestResultContainer").classList.add("hidden");
      await updateGlobalGoldenCountBadge();
      switchTrainingTab("dataset");
    } else {
      alert("Error saving custom scenario: " + (d.message || "Unknown error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function saveBotSettings() {
  const alertEl = document.getElementById("botSettingsAlert");
  try {
    const payload = {
      enabled: true,
      mode: botSettings.mode || "copilot",
      bot_name: document.getElementById("botName")?.value.trim() || "Emma",
      partner_name: document.getElementById("botPartnerName").value.trim() || "John",
      call_window_hours: parseInt(document.getElementById("botCallWindow").value, 10) || 3,
      zestimate_gold_threshold: (parseInt(document.getElementById("botGoldThreshold").value, 10) || 80) / 100.0,
      auto_send_delay_seconds: parseInt(document.getElementById("botDelayInput")?.value, 10) || 30,
      campaign_followup_1_days: parseInt(document.getElementById("botFu1Days").value, 10) || 3,
      campaign_followup_2_days: parseInt(document.getElementById("botFu2Days").value, 10) || 7,
      campaign_coldcall_days: parseInt(document.getElementById("botColdCallDays").value, 10) || 14,
      gemini_api_key: document.getElementById("botGeminiApiKey")?.value.trim() || "",
      gemini_model: document.getElementById("botGeminiModel")?.value || "gemini-3.5-flash-lite",
      use_gemini_enhancer: Boolean(document.getElementById("botGeminiEnabled")?.checked),
      auto_cadence_followup_enabled: Boolean(document.getElementById("botAutoCadenceEnabled")?.checked)
    };

    const res = await fetch("/api/bot/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (d.status === "success") {
      botSettings = d.settings;
      updateSettingsUI();
      fetchSchedulerStatus();
      alertEl.innerText = "✓ Lead Vetting Bot Settings saved successfully!";
      alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30";
      setTimeout(() => {
        alertEl.classList.add("hidden");
        closeModal("botSettingsModal");
      }, 1000);
    }
  } catch (err) {
    alertEl.innerText = "Error saving bot settings: " + err.message;
    alertEl.className = "p-3 rounded-xl text-xs font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30";
  }
}

async function fetchSchedulerStatus() {
  try {
    const res = await fetch("/api/scheduler/status");
    const d = await res.json();
    const sumEl = document.getElementById("schedulerStatusSummary");
    const chk = document.getElementById("botAutoCadenceEnabled");
    if (chk) chk.checked = d.enabled;
    if (sumEl) {
      if (d.enabled) {
        sumEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span><span>Scheduler Active &bull; Next run: ${escapeHtml(d.next_run_display || 'Today at 9:00 AM')}</span>`;
      } else {
        sumEl.innerHTML = `<span class="w-2 h-2 rounded-full bg-slate-500 inline-block"></span><span class="text-slate-400">Scheduler Paused</span>`;
      }
    }
  } catch (err) {
    console.error("Error fetching scheduler status:", err);
  }
}

async function triggerCadenceRunNow() {
  const btn = document.getElementById("btnRunCadenceNow");
  if (!confirm("Are you sure you want to run the Underdog Cadence Follow-Up cycle right now? This will dispatch Follow-Up #1 & #2 texts to all agents currently due.")) {
    return;
  }
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Dispatching...";
  }
  try {
    const res = await fetch("/api/scheduler/run-now", { method: "POST" });
    const d = await res.json();
    alert("🚀 " + (d.message || "Cadence follow-up cycle triggered!"));
    setTimeout(() => {
      fetchSchedulerStatus();
      loadStats();
      loadAgents();
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = "<span>⚡ Run Cadence Now</span>";
      }
    }, 2000);
  } catch (err) {
    alert("Error triggering cadence: " + err.message);
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "<span>⚡ Run Cadence Now</span>";
    }
  }
}


let currentStageFilter = "ALL";

function handleStageFilter(val) {
  currentStageFilter = val || "ALL";
  if (currentStageFilter !== "ALL") {
    currentTab = "ALL";
    document.querySelectorAll(".tab-btn").forEach(btn => {
      btn.className = "tab-btn px-4 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-2";
    });
    const allBtn = document.getElementById("tab_ALL");
    if (allBtn) {
      allBtn.className = "tab-btn px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-lg shadow-indigo-600/25";
    }
  }
  loadAgents();
}

async function loadAgents() {
  try {
    let url = `/api/agents?county=${currentCounty}`;
    if (currentStageFilter && currentStageFilter !== "ALL") {
      url += `&stage=${encodeURIComponent(currentStageFilter)}`;
    } else if (currentTab === "whales") {
      url += `&tier=Whale`;
    } else if (currentTab === "chatted") {
      url += `&stage=chatted`;
    } else if (currentTab === "TIER_1") {
      url += `&tier=TIER_1`;
    } else if (currentTab === "TIER_2") {
      url += `&tier=TIER_2`;
    } else if (currentTab === "GOLD") {
      url += `&stage=GOLD`;
    } else if (currentTab === "FOLLOWUP_1") {
      url += `&stage=FOLLOWUP_1`;
    } else if (currentTab === "FOLLOWUP_2") {
      url += `&stage=FOLLOWUP_2`;
    } else if (currentTab === "COLDCALL") {
      url += `&stage=COLDCALL`;
    } else if (currentTab === "DEAD") {
      url += `&tier=DEAD`;
    } else if (currentTab === "cadence_due") {
      url += `&stage=cadence_due`;
    } else if (currentTab === "stale_dom") {
      url += `&stage=stale_dom`;
    } else if (currentTab !== "ALL") {
      url += `&stage=${encodeURIComponent(currentTab)}`;
    }
    if (searchQuery) {
      url += `&search=${encodeURIComponent(searchQuery)}`;
    }

    const res = await fetch(url);
    allAgents = await res.json();

    // Update Chatted Tab Count Badge
    const chattedBadge = document.getElementById("tabCount_chatted");
    if (chattedBadge) {
      const chattedCount = allAgents.filter(a => a.unread_replies > 0 || a.last_contact_date || a.last_reply_text || ["Contacted", "Warm / In Discussion", "Pocket Deal Review", "Appointment Pending", "Appointment Confirmed", "Contract Sent"].includes(a.pipeline_stage)).length;
      chattedBadge.innerText = chattedCount;
      chattedBadge.classList.toggle("hidden", chattedCount === 0);
    }

    renderAgentTable(allAgents);
  } catch (err) {
    console.error("Error loading agents:", err);
  }
}

function renderAgentTable(agents) {
  const tbody = document.getElementById("agentTableBody");
  const countDisplay = document.getElementById("agentCountDisplay");
  countDisplay.innerText = `Showing ${agents.length} agent${agents.length === 1 ? '' : 's'}`;

  if (!agents || agents.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center py-12 text-slate-500 font-medium">No agents found matching current filters.</td></tr>`;
    return;
  }

  tbody.innerHTML = agents.map(a => {
    const isTestAgent = Boolean(
      a.is_test || 
      a.is_custom ||
      (a.tier && a.tier.toLowerCase().includes("test")) ||
      (a.full_name && a.full_name.toLowerCase().includes("test")) || 
      a.agent_id?.toLowerCase().startsWith("test") ||
      a.agent_id?.toLowerCase().startsWith("custom")
    );

    let tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-slate-800 text-slate-300">${a.tier}</span>`;
    if (a.tier.includes("Tier 1")) {
      tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">🔥 ${escapeHtml(a.tier)}</span>`;
    } else if (a.is_gold_deal || a.tier.includes("GOLD")) {
      tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/25 text-amber-200 border border-amber-500/50">⭐ THE GOLD (≤80%)</span>`;
    } else if (a.tier.includes("Tier 2")) {
      tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">🌱 Tier 2: Pocket</span>`;
    } else if (a.tier.includes("Dead")) {
      tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-950/60 text-red-400 border border-red-800/40">🛑 Dead / Opt-Out</span>`;
    } else if (a.tier.includes("Whale")) {
      tierBadge = `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/10 text-amber-300 border border-amber-500/20">🐋 Whale Producer</span>`;
    }

    const customBadge = isTestAgent
      ? `<span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-violet-500/20 text-violet-300 border border-violet-500/30">🧪 Sandbox Agent</span>`
      : '';

    let campaignBadge = '';
    if (a.campaign_status) {
      const step = a.campaign_status.campaign_step;
      if (step === "FOLLOW_UP_1") {
        campaignBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] bg-yellow-500/20 text-yellow-300 font-bold border border-yellow-500/30">🟡 Follow-Up #1 (${a.campaign_status.days_silent}d)</span>`;
      } else if (step === "FOLLOW_UP_2") {
        campaignBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">🟠 Follow-Up #2 (${a.campaign_status.days_silent}d)</span>`;
      } else if (step === "COLD_CALL_BUCKET") {
        campaignBadge = `<span class="px-1.5 py-0.5 rounded text-[9px] bg-purple-500/20 text-purple-300 font-bold border border-purple-500/30">📞 Cold Call Queue</span>`;
      }
    }

    const botScriptBadge = a.last_bot_suggestion
      ? `<span class="px-1.5 py-0.5 rounded text-[9px] bg-indigo-500/30 text-indigo-200 font-bold border border-indigo-500/50 animate-pulse">🤖 Script Ready</span>`
      : '';

    const apptBadge = (a.bot_vetting && a.bot_vetting.appointment_time)
      ? `<span class="px-1.5 py-0.5 rounded text-[9px] bg-emerald-500/25 text-emerald-300 font-bold border border-emerald-500/40">📅 Appt: ${escapeHtml(a.bot_vetting.appointment_time)}</span>`
      : '';

    const stageBadgeClass = {
      "New Ingest": "bg-slate-800 text-slate-300 border-slate-700",
      "Contacted": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
      "Warm / In Discussion": "bg-amber-500/10 text-amber-300 border-amber-500/30",
      "Pocket Deal Review": "bg-fuchsia-500/10 text-fuchsia-300 border-fuchsia-500/30",
      "Contract Sent": "bg-purple-500/10 text-purple-300 border-purple-500/30",
      "Appointment Pending": "bg-rose-500/20 text-rose-300 border-rose-500/40 font-bold",
      "Appointment Confirmed": "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 font-bold",
      "Tier 2 Nurture": "bg-emerald-500/10 text-emerald-400 border-emerald-500/30",
      "Follow-up 30 Days": "bg-blue-500/10 text-blue-300 border-blue-500/30",
      "DND": "bg-red-500/10 text-red-400 border-red-500/30"
    }[a.pipeline_stage] || "bg-slate-800 text-slate-300 border-slate-700";

    const primPrice = a.primary_price > 0 ? `$${a.primary_price.toLocaleString()}` : "Price Unlisted";
    const primDom = a.primary_dom ? `${a.primary_dom} DOM` : "";

    return `
      <tr class="hover:bg-slate-800/40 transition group">
        <!-- Agent & Brokerage -->
        <td class="py-3.5 px-4">
          <div class="flex items-center gap-2 flex-wrap">
            <span class="font-bold text-white text-xs hover:text-indigo-400 cursor-pointer" onclick="openAgentDrawer('${a.agent_id}')">
              ${escapeHtml(a.full_name)}
            </span>
            ${tierBadge}
            ${customBadge}
            ${campaignBadge}
            ${botScriptBadge}
            ${apptBadge}
            ${a.cadence_due ? `<span class="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">⏰ 21d+ Due</span>` : ''}
            ${a.is_stale_dom ? `<span class="px-1.5 py-0.5 rounded text-[9px] bg-rose-500/20 text-rose-300 font-bold border border-rose-500/30">⏳ ${a.max_dom}d DOM</span>` : ''}
            ${(a.unread_replies && a.unread_replies > 0) ? `<span class="px-1.5 py-0.5 rounded text-[9px] bg-indigo-500 text-white font-bold animate-pulse">📬 New Reply</span>` : ''}
          </div>
          <div class="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
            <span>🏢 ${escapeHtml(a.brokerage)}</span>
            <span>&bull;</span>
            <span class="text-slate-500">${a.county} County</span>
          </div>
        </td>

        <!-- Contact Info -->
        <td class="py-3.5 px-4">
          <div class="font-mono text-emerald-400 text-xs font-semibold flex items-center gap-1.5">
            <span>📞</span>
            <a href="tel:${a.phone}" class="hover:underline">${a.phone || "No Phone"}</a>
          </div>
          <div class="font-mono text-cyan-400 text-[11px] mt-0.5 flex items-center gap-1.5">
            <span>✉️</span>
            <a href="mailto:${a.email}" class="hover:underline truncate max-w-[180px]">${a.email || "No Email"}</a>
          </div>
        </td>

        <!-- Active Listings Count -->
        <td class="py-3.5 px-4">
          <div class="font-bold text-white text-xs">${a.listing_count} Active Listing${a.listing_count === 1 ? '' : 's'}</div>
          <div class="text-[11px] text-slate-400 font-mono mt-0.5">$${(a.total_volume).toLocaleString()} Total</div>
        </td>

        <!-- Primary Listing with Direct Zillow/Redfin Links -->
        <td class="py-3.5 px-4">
          <div class="flex items-center justify-between gap-1.5 max-w-[240px]">
            <div class="font-semibold text-white text-xs truncate" title="${escapeHtml(a.primary_address)}">
              📍 ${escapeHtml(a.primary_address)}
            </div>
            ${a.primary_address ? `
              <div class="flex items-center gap-1 flex-shrink-0" onclick="event.stopPropagation()">
                <a href="https://www.zillow.com/homes/${encodeURIComponent(a.primary_address + ', ' + (a.primary_city || '') + ', FL')}_rb/" target="_blank" class="px-1.5 py-0.5 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 text-[9px] font-bold transition flex items-center gap-0.5" title="View ${escapeHtml(a.primary_address)} on Zillow">
                  <span>Z</span><span>↗</span>
                </a>
              </div>
            ` : ''}
          </div>
          <div class="text-[11px] text-slate-400 flex items-center gap-2 mt-0.5">
            <span>${escapeHtml(a.primary_city)}, FL</span>
            <span class="font-mono font-bold text-indigo-300">${primPrice}</span>
            ${primDom ? `<span class="px-1.5 py-0.2 rounded bg-slate-800 text-[9px] text-slate-400 font-mono">${primDom}</span>` : ''}
          </div>
        </td>

        <!-- Stage Badge -->
        <td class="py-3.5 px-4">
          <select onchange="handleStageChange('${a.agent_id}', this.value)" class="text-[11px] font-semibold rounded-lg px-2 py-1 border cursor-pointer ${stageBadgeClass} focus:outline-none">
            <option value="New Ingest" ${a.pipeline_stage === 'New Ingest' ? 'selected' : ''}>⭐ New Ingest</option>
            <option value="Contacted" ${a.pipeline_stage === 'Contacted' ? 'selected' : ''}>💬 Contacted</option>
            <option value="Warm / In Discussion" ${a.pipeline_stage === 'Warm / In Discussion' ? 'selected' : ''}>🔥 In Discussion</option>
            <option value="Appointment Pending" ${a.pipeline_stage === 'Appointment Pending' ? 'selected' : ''}>📅 Appt Pending (Matt)</option>
            <option value="Appointment Confirmed" ${a.pipeline_stage === 'Appointment Confirmed' ? 'selected' : ''}>✅ Appt Booked</option>
            <option value="Tier 2 Nurture" ${a.pipeline_stage === 'Tier 2 Nurture' ? 'selected' : ''}>🌱 Tier 2 Nurture</option>
            <option value="Pocket Deal Review" ${a.pipeline_stage === 'Pocket Deal Review' ? 'selected' : ''}>💼 Pocket Deal</option>
            <option value="Contract Sent" ${a.pipeline_stage === 'Contract Sent' ? 'selected' : ''}>🖋️ Contract Sent</option>
            <option value="Follow-up 30 Days" ${a.pipeline_stage === 'Follow-up 30 Days' ? 'selected' : ''}>🔄 Follow-up 30d</option>
            <option value="DND" ${a.pipeline_stage === 'DND' ? 'selected' : ''}>🚫 DND</option>
          </select>
        </td>

        <!-- Quick Actions -->
        <td class="py-3.5 px-4 text-right">
          <div class="flex items-center justify-end gap-1.5">
            ${a.last_bot_suggestion ? `
              <button type="button" onclick="openAgentDrawer('${a.agent_id}')" class="px-2.5 py-1 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold text-xs shadow transition flex items-center gap-1 cursor-pointer" title="Review &amp; Approve Flowchart Bot Suggestion">
                <span>🤖 Copilot</span>
              </button>
            ` : ''}

            <!-- Smart SMS Button with Status & History Color -->
            ${(() => {
              const hasUnread = (a.unread_replies && a.unread_replies > 0);
              const hasReplied = hasUnread || !!a.last_reply_text || ["Warm / In Discussion", "Pocket Deal Review"].includes(a.pipeline_stage);
              const hasChatted = !!a.last_contact_date || a.pipeline_stage === "Contacted" || hasReplied;

              if (hasUnread) {
                return `
                  <button type="button" onclick="openSmsModal('${a.agent_id}')" class="px-2 py-1 rounded-lg bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs border border-purple-400/50 shadow-md shadow-purple-600/30 transition cursor-pointer animate-pulse flex items-center gap-1" title="New text reply received from agent! Click to respond">
                    <span>💬</span>
                    <span>Reply!</span>
                  </button>
                `;
              } else if (hasReplied) {
                return `
                  <button type="button" onclick="openSmsModal('${a.agent_id}')" class="px-2 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-xs border border-amber-500/40 transition cursor-pointer flex items-center gap-1 shadow-sm" title="Agent previously replied. Click to view history and text">
                    <span>💬</span>
                    <span>Replied</span>
                  </button>
                `;
              } else if (hasChatted) {
                return `
                  <button type="button" onclick="openSmsModal('${a.agent_id}')" class="px-2 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 font-semibold text-xs border border-indigo-500/30 transition cursor-pointer flex items-center gap-1" title="Outreach sent (${a.last_contact_date || ''}). Click to send follow-up">
                    <span>💬</span>
                    <span>Sent</span>
                  </button>
                `;
              } else {
                return `
                  <button type="button" onclick="openSmsModal('${a.agent_id}')" class="p-1.5 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 transition cursor-pointer" title="Send Cellular SMS (Android Gateway)">
                    💬
                  </button>
                `;
              }
            })()}

            <!-- Email Button -->
            <button type="button" onclick="openEmailModal('${a.agent_id}')" class="p-1.5 rounded-lg bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/20 transition cursor-pointer" title="Send Email Offer (SMTP2GO)">
              ✉️
            </button>

            <!-- Setup Call HUD -->
            <button type="button" onclick="openNegotiationHud('${a.agent_id}')" class="p-1.5 rounded-lg bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/20 transition cursor-pointer font-bold text-xs" title="Open Setup Call Negotiation HUD">
              📞 HUD
            </button>

            <!-- LOI Deal Analyzer Button -->
            <button type="button" onclick="openLoiAnalyzer('${a.agent_id}')" class="p-1.5 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/20 transition cursor-pointer font-bold text-xs" title="Analyze Deal &amp; Draft Cash LOI">
              📊 LOI
            </button>

            <!-- Edit Agent Button -->
            <button type="button" onclick="openEditAgentModal('${a.agent_id}')" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition cursor-pointer font-bold text-xs" title="Edit Agent Details &amp; Contact Info">
              ✏️
            </button>

            <!-- PandaDoc FAR/BAR Contract -->
            <!-- Quick Delete Button (Direct 1 Click Delete) - Hidden for Test Agent -->
            ${!isTestAgent ? `
            <button type="button" onclick="quickDeleteAgent('${a.agent_id}', '${escapeHtml(a.full_name || 'Agent')}')" class="p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/25 text-rose-400 hover:text-rose-300 border border-rose-500/20 transition cursor-pointer font-bold text-xs" title="Delete Agent &amp; Property Record">
              🗑️
            </button>
            ` : ''}
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

async function quickDeleteAgent(agentId, agentName) {
  if (agentId?.toLowerCase().startsWith("test") || agentName?.toLowerCase().includes("test")) {
    alert("Test Agent is protected and cannot be deleted.");
    return;
  }
  if (!confirm(`Are you sure you want to delete ${agentName || 'this agent'} and their property records from your database?`)) {
    return;
  }
  try {
    const res = await fetch(`/api/agent/${agentId}`, { method: "DELETE" });
    if (res.ok) {
      loadStats();
      loadAgents();
    } else {
      const d = await res.json();
      alert("Failed to delete agent: " + (d.detail || "Error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

// Handlers
function handleCountyChange(val) {
  currentCounty = val;
  loadAgents();
}

function setPipelineTab(tab) {
  currentTab = tab;
  currentStageFilter = "ALL";
  const stageSel = document.getElementById("stageFilterSelect");
  if (stageSel) stageSel.value = "ALL";
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.className = "tab-btn px-3.5 py-2 rounded-xl text-xs font-semibold text-slate-400 hover:text-white transition flex items-center gap-1.5";
  });
  const activeBtn = document.getElementById(`tab_${tab}`);
  if (activeBtn) {
    activeBtn.className = "tab-btn px-3.5 py-2 rounded-xl text-xs font-bold transition flex items-center gap-1.5 bg-indigo-600 text-white shadow-lg shadow-indigo-600/25";
  }
  loadAgents();
}

let searchTimer;
function handleSearch(val) {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    searchQuery = val;
    loadAgents();
  }, 250);
}

function refreshData() {
  loadStats();
  loadAgents();
}

async function handleStageChange(agentId, newStage) {
  try {
    await fetch(`/api/agent/${agentId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pipeline_stage: newStage })
    });
    loadStats();
  } catch (err) {
    console.error("Error updating stage:", err);
  }
}

// SMS Outreach Modal
let activeSmsOverrides = null;
let activeEmailOverrides = null;

function openSmsModal(agentId, overrides = null) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;
  selectedAgent = agent;
  activeSmsOverrides = overrides;

  document.getElementById("smsAgentId").value = agent.agent_id;
  document.getElementById("smsPhoneInput").value = overrides?.phone || agent.phone || "";
  document.getElementById("smsAgentNameDisplay").innerText = agent.full_name;
  const displayAddr = overrides?.address || agent.primary_address || "Florida Property";
  const city = agent.primary_city || "FL";
  const zillowUrl = `https://www.zillow.com/homes/${encodeURIComponent(displayAddr + ', ' + city + ', FL')}_rb/`;

  document.getElementById("smsListingDisplay").innerHTML = `
    <span class="text-slate-300">📍 ${escapeHtml(displayAddr)} (${city})</span>
    <span class="inline-flex items-center gap-1.5 ml-2">
      <a href="${zillowUrl}" target="_blank" class="px-1.5 py-0.5 rounded bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 border border-blue-500/30 text-[9px] font-bold transition">Zillow ↗</a>
    </span>
  `;
  document.getElementById("smsListingAddress").value = displayAddr;
  document.getElementById("smsCity").value = agent.primary_city || "";

  const targetTmpl = overrides?.template || "icebreaker";
  const select = document.getElementById("smsTemplateSelect");
  if (select) select.value = targetTmpl;

  applySmsTemplate(targetTmpl, overrides);
  loadSmsModalHistory(agent.agent_id);
  openModal("smsModal");
}

async function loadSmsModalHistory(agentId) {
  const container = document.getElementById("smsModalHistorySection");
  const thread = document.getElementById("smsModalChatThread");
  const badge = document.getElementById("smsModalHistoryBadge");
  if (!container || !thread) return;

  container.classList.remove("hidden");
  thread.classList.remove("hidden");
  const toggleText = document.getElementById("smsModalHistoryToggleText");
  if (toggleText) toggleText.innerText = "Hide ▲";
  thread.innerHTML = `<div class="text-center py-2 text-slate-500 text-xs italic">Loading previous conversation...</div>`;

  try {
    const res = await fetch(`/api/agent/${agentId}`);
    if (!res.ok) throw new Error("Failed to load history");
    const d = await res.json();
    const outreach = d.outreach || [];
    if (badge) badge.innerText = `${outreach.length} msg${outreach.length === 1 ? '' : 's'}`;

    if (outreach.length > 0) {
      thread.innerHTML = renderChatBubbles(d.agent, outreach);
      setTimeout(() => { thread.scrollTop = thread.scrollHeight; }, 60);
    } else {
      container.classList.add("hidden");
      thread.innerHTML = "";
    }
  } catch (err) {
    container.classList.add("hidden");
  }
}

function toggleSmsModalHistory() {
  const thread = document.getElementById("smsModalChatThread");
  const toggleText = document.getElementById("smsModalHistoryToggleText");
  if (!thread) return;
  const isHidden = thread.classList.toggle("hidden");
  if (toggleText) toggleText.innerText = isHidden ? "Show ▼" : "Hide ▲";
}

function applySmsTemplate(type, overrides = null) {
  if (!selectedAgent) return;
  const ovr = overrides || activeSmsOverrides;
  
  let tmpl;
  if (type === 'icebreaker') {
    tmpl = getRandomBrookeIcebreaker();
  } else {
    tmpl = SMS_TEMPLATES[type] || SMS_TEMPLATES.icebreaker;
  }

  const prim = (selectedAgent.listings && selectedAgent.listings[0]) || {};
  const arvVal = ovr?.arv || prim.estimated_value || selectedAgent.primary_price || 275000;
  const repairsVal = ovr?.repairs || Math.round(((prim.sqft || 1500) * 30) / 1000) * 1000 || 45000;
  const offerVal = ovr?.offerAmount || Math.round((arvVal * 0.55) / 1000) * 1000 || 130000;
  const addressVal = ovr?.address || selectedAgent.primary_address || "the property";
  const agentNameVal = type === 'loi_offer' ? (selectedAgent.full_name || selectedAgent.first_name || "there") : (selectedAgent.first_name || "there");

  const arvFmt = `$${Math.round(arvVal).toLocaleString()}`;
  const repairsFmt = `$${Math.round(repairsVal).toLocaleString()}`;
  const offerFmt = `$${Math.round(offerVal).toLocaleString()}`;

  let rendered = tmpl
    .replace(/{Agent_FirstName}/g, () => agentNameVal)
    .replace(/{Agent_Name}/g, () => selectedAgent.full_name || agentNameVal)
    .replace(/{Listing_Address}/g, () => addressVal)
    .replace(/{City}/g, () => selectedAgent.primary_city || "the area")
    .replace(/\${ARV}/g, () => arvFmt)
    .replace(/{ARV}/g, () => arvFmt)
    .replace(/\${Repairs}/g, () => repairsFmt)
    .replace(/{Repairs}/g, () => repairsFmt)
    .replace(/\${Offer_Amount}/g, () => offerFmt)
    .replace(/{Offer_Amount}/g, () => offerFmt);

  rendered = resolveSpintax(rendered);
  rendered = sanitizeSmsNoHyphens(rendered);
  document.getElementById("smsMessageText").value = rendered;
  updateCharCount();
}

function spinBrookeSmsVariation() {
  const select = document.getElementById("smsTemplateSelect");
  if (select) select.value = "icebreaker";
  applySmsTemplate("icebreaker");
  const txtArea = document.getElementById("smsMessageText");
  if (txtArea) {
    txtArea.classList.add("ring-2", "ring-amber-400");
    setTimeout(() => txtArea.classList.remove("ring-2", "ring-amber-400"), 500);
  }
}

function updateCharCount() {
  const val = document.getElementById("smsMessageText").value || "";
  document.getElementById("smsCharCount").innerText = `${val.length} characters (approx ${Math.ceil(val.length / 160)} SMS segment${val.length > 160 ? 's' : ''})`;
}

async function handleSendSmsSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("smsModalAlert");
  const btn = document.getElementById("btnDispatchSms");
  btn.disabled = true;
  btn.innerText = "Dispatching via Android...";

  try {
    const payload = {
      agent_id: document.getElementById("smsAgentId").value,
      phone: document.getElementById("smsPhoneInput").value,
      message: document.getElementById("smsMessageText").value
    };

    const res = await fetch("/api/sms/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    alertBox.classList.remove("hidden");
    if (data.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ ${data.message}`;
      setTimeout(() => {
        closeModal("smsModal");
        alertBox.classList.add("hidden");
        loadAgents();
      }, 1800);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${data.message}`;
    }
  } catch (err) {
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
    alertBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Send Cellular SMS";
  }
}

// Email Outreach Modal
function openEmailModal(agentId, overrides = null) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;
  selectedAgent = agent;
  activeEmailOverrides = overrides;

  document.getElementById("emailAgentId").value = agent.agent_id;
  document.getElementById("emailRecipientInput").value = overrides?.recipientEmail || agent.email || "";
  const displayAddr = overrides?.address || agent.primary_address || "Florida Property";
  document.getElementById("emailListingAddress").value = displayAddr;
  document.getElementById("emailCity").value = agent.primary_city || "";

  const targetTmpl = overrides?.template || "pocket_hunt";
  const select = document.getElementById("emailTemplateSelect");
  if (select) select.value = targetTmpl;

  applyEmailTemplate(targetTmpl, overrides);
  openModal("emailModal");
}

function applyEmailTemplate(type, overrides = null) {
  if (!selectedAgent) return;
  const ovr = overrides || activeEmailOverrides;
  const tmpl = EMAIL_TEMPLATES[type] || EMAIL_TEMPLATES.pocket_hunt;

  const prim = (selectedAgent.listings && selectedAgent.listings[0]) || {};
  const arvVal = ovr?.arv || prim.estimated_value || selectedAgent.primary_price || 275000;
  const repairsVal = ovr?.repairs || Math.round(((prim.sqft || 1500) * 30) / 1000) * 1000 || 45000;
  const offerVal = ovr?.offerAmount || Math.round((arvVal * 0.55) / 1000) * 1000 || 130000;
  const addressVal = ovr?.address || selectedAgent.primary_address || "the property";
  const agentNameVal = type === 'loi_offer' ? (selectedAgent.full_name || selectedAgent.first_name || "there") : (selectedAgent.first_name || "there");

  const arvFmt = `$${Math.round(arvVal).toLocaleString()}`;
  const repairsFmt = `$${Math.round(repairsVal).toLocaleString()}`;
  const offerFmt = `$${Math.round(offerVal).toLocaleString()}`;

  const subj = tmpl.subject
    .replace(/{City}/g, selectedAgent.primary_city || "Florida")
    .replace(/{Listing_Address}/g, addressVal);

  const body = tmpl.body
    .replace(/{Agent_FirstName}/g, () => agentNameVal)
    .replace(/{Agent_Name}/g, () => selectedAgent.full_name || agentNameVal)
    .replace(/{Listing_Address}/g, () => addressVal)
    .replace(/{City}/g, () => selectedAgent.primary_city || "Florida")
    .replace(/\${ARV}/g, () => arvFmt)
    .replace(/{ARV}/g, () => arvFmt)
    .replace(/\${Repairs}/g, () => repairsFmt)
    .replace(/{Repairs}/g, () => repairsFmt)
    .replace(/\${Offer_Amount}/g, () => offerFmt)
    .replace(/{Offer_Amount}/g, () => offerFmt);

  document.getElementById("emailSubjectInput").value = subj;
  document.getElementById("emailBodyText").value = body;
}

async function handleSendEmailSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("emailModalAlert");
  const btn = document.getElementById("btnDispatchEmail");
  btn.disabled = true;
  btn.innerText = "Sending via SMTP2GO...";

  try {
    const payload = {
      agent_id: document.getElementById("emailAgentId").value,
      recipient_email: document.getElementById("emailRecipientInput").value,
      subject: document.getElementById("emailSubjectInput").value,
      html_content: document.getElementById("emailBodyText").value
    };

    const res = await fetch("/api/email/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    alertBox.classList.remove("hidden");
    if (data.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
      alertBox.innerText = `✓ ${data.message}`;
      setTimeout(() => {
        closeModal("emailModal");
        alertBox.classList.add("hidden");
        loadAgents();
      }, 1800);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${data.message}`;
    }
  } catch (err) {
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
    alertBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Send Email Offer";
  }
}

// Setup Call Negotiation HUD
async function openNegotiationHud(agentId) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;
  selectedAgent = agent;

  const prim = agent.listings[0] || {};
  const payload = {
    agent_name: agent.full_name,
    property_address: agent.primary_address,
    listing_price: agent.primary_price,
    estimated_value: prim.estimated_value || agent.primary_price,
    sqft: prim.sqft || 1500,
    year_built: prim.year_built || 1980,
    condition: "average",
    occupancy: "Vacant",
    timeline: "ASAP"
  };

  try {
    const res = await fetch("/api/deal/calculate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    currentHudData = await res.json();

    // Render HUD Bar
    const b = currentHudData.buy_box;
    document.getElementById("hudArv").innerText = `$${b.arv.toLocaleString()}`;
    document.getElementById("hudRehab").innerText = `$${b.est_rehab.toLocaleString()}`;
    document.getElementById("hudRange").innerText = `$${b.target_low.toLocaleString()} – $${b.target_high.toLocaleString()}`;
    document.getElementById("hudMao").innerText = `$${b.formula_mao.toLocaleString()}`;

    // Render Steps
    const stepsDiv = document.getElementById("hudStepsContainer");
    stepsDiv.innerHTML = currentHudData.hud.steps.map(s => `
      <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-3.5 space-y-1.5">
        <div class="flex items-center justify-between">
          <div class="font-bold text-indigo-400 flex items-center gap-2">
            <span class="w-5 h-5 rounded-full bg-indigo-500/20 text-[10px] flex items-center justify-center font-mono">${s.step_num}</span>
            <span>${s.title}</span>
          </div>
          <span class="text-[10px] text-slate-500 italic">${s.objective}</span>
        </div>
        <p class="text-slate-200 text-xs leading-relaxed bg-[#0b1220] p-2.5 rounded-lg border border-slate-800/80 font-medium">
          "${escapeHtml(s.script)}"
        </p>
      </div>
    `).join("");

    openModal("negotiationModal");
  } catch (err) {
    console.error("Error generating HUD:", err);
  }
}

function launchContractFromHud() {
  closeModal("negotiationModal");
  if (selectedAgent) {
    openContractModal(selectedAgent.agent_id);
  }
}

async function openPocketDealPrompt() {
  if (!selectedAgent) return;
  const addr = prompt("Enter the Off-Market Pocket Property Address:", selectedAgent.primary_address);
  if (!addr) return;
  const price = prompt("Enter Target Asking Price ($):", "250000");
  if (!price) return;
  const notes = prompt("Enter Condition / Situation Notes:", "Vacant, original condition, seller wants fast cash close");

  try {
    await fetch(`/api/agent/${selectedAgent.agent_id}/pocket-deal`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        address: addr,
        city: selectedAgent.primary_city,
        condition_notes: notes,
        asking_price: parseFloat(price) || 0,
        timeline: "ASAP"
      })
    });
    alert("✓ Off-Market Pocket Deal logged to Agent profile!");
    loadStats();
    loadAgents();
  } catch (err) {
    alert("Error logging pocket deal: " + err.message);
  }
}

// Contract & PandaDoc Modal (Official Florida FAR/BAR ASIS-7x)
let activeContractType = "farbar";
function setContractType(type = "farbar") {
  activeContractType = "farbar";
  const farbarActions = document.getElementById("contractFarbarActions");
  const advancedDetails = document.getElementById("contractAdvancedDetails");
  const envSwitcher = document.getElementById("contractEnvSwitcher");
  const badge = document.getElementById("contractPandadocBadge");

  if (farbarActions) farbarActions.classList.remove("hidden");
  if (advancedDetails) advancedDetails.classList.remove("hidden");
  
  // Only show sandbox switcher for the test agent; hide completely for live agents
  const isTestAgent = Boolean(
    selectedAgent?.is_test || 
    selectedAgent?.is_custom ||
    (selectedAgent?.tier && selectedAgent.tier.toLowerCase().includes("test")) ||
    (selectedAgent?.full_name && selectedAgent.full_name.toLowerCase().includes("test")) || 
    selectedAgent?.agent_id?.toLowerCase().startsWith("test") ||
    selectedAgent?.agent_id?.toLowerCase().startsWith("custom")
  );
  if (envSwitcher) {
    if (isTestAgent) {
      envSwitcher.classList.remove("hidden");
    } else {
      envSwitcher.classList.add("hidden");
    }
  }

  if (badge) {
    const mode = document.getElementById("contractModalMode")?.value || "production";
    badge.innerText = mode === "production" ? "PANDADOC (LIVE PROD)" : "PANDADOC (TEST SANDBOX)";
    badge.className = mode === "production" 
      ? "px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold"
      : "px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold";
  }
}

function setContractModalMode(mode) {
  document.getElementById("contractModalMode").value = mode;
  const btnSandbox = document.getElementById("btnContractModeSandbox");
  const btnProd = document.getElementById("btnContractModeProd");
  const explain = document.getElementById("contractModeExplain");
  const badge = document.getElementById("contractPandadocBadge");
  const btnDispatch = document.getElementById("btnDispatchContract");

  if (mode === "sandbox") {
    btnSandbox.className = "px-2.5 py-1 rounded-lg text-xs font-bold bg-purple-600 text-white cursor-pointer transition shadow";
    btnProd.className = "px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white cursor-pointer transition";
    explain.innerText = "(Watermarked Test Invite)";
    explain.className = "text-[10px] text-purple-300 font-mono";
    if (badge) {
      badge.innerText = "PANDADOC (TEST SANDBOX)";
      badge.className = "px-2 py-0.5 rounded text-[10px] bg-purple-500/20 text-purple-300 border border-purple-500/30 font-bold";
    }
    if (btnDispatch) btnDispatch.innerHTML = "<span>🖋️ Send Test E-Sign (Sandbox)</span>";
  } else {
    btnProd.className = "px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-600 text-white cursor-pointer transition shadow";
    btnSandbox.className = "px-2.5 py-1 rounded-lg text-xs font-semibold text-slate-400 hover:text-white cursor-pointer transition";
    explain.innerText = "(Legally Binding Live Dispatch)";
    explain.className = "text-[10px] text-emerald-300 font-mono";
    if (badge) {
      badge.innerText = "PANDADOC (LIVE PROD)";
      badge.className = "px-2 py-0.5 rounded text-[10px] bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-bold";
    }
    if (btnDispatch) btnDispatch.innerHTML = "<span>🚀 Send Live Contract via PandaDoc</span>";
  }
}

function openContractModal(agentId) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;
  selectedAgent = agent;

  const prim = (agent.listings && agent.listings[0]) || {};
  document.getElementById("contractAgentId").value = agent.agent_id;
  document.getElementById("contractPropertyAddress").value = agent.primary_address || "";
  document.getElementById("contractAgentEmail").value = agent.email || "";

  // Complete Form Fields
  document.getElementById("contractSellerName").value = prim.owner_name || "Property Owner of Record";
  document.getElementById("contractCity").value = agent.primary_city || "";
  document.getElementById("contractCounty").value = agent.county || "FL";
  document.getElementById("contractZip").value = prim.zip || "";
  document.getElementById("contractApn").value = prim.apn || "";
  document.getElementById("contractLegalDescription").value = prim.legal_description || "Recorded Public Records / Subdivision Plat";
  document.getElementById("contractTitleCompany").value = pandadocSettings.default_title_company || "Title Insights";
  document.getElementById("contractBuyerName").value = pandadocSettings.buyer_name || "Peak Investments LLC";
  document.getElementById("contractBuyerSignerName").value = pandadocSettings.buyer_signer_name || "Johnathan Roberts";
  document.getElementById("contractAgentNameInput").value = agent.full_name || "Listing Agent";
  document.getElementById("contractBrokerageInput").value = agent.brokerage || "Listing Brokerage";
  document.getElementById("contractAcceptanceDays").value = 3;
  
  // Leave purchase price blank so user enters their exact chosen offer
  document.getElementById("contractPrice").value = "";
  document.getElementById("contractEscrow").value = "";
  document.getElementById("contractInspection").value = pandadocSettings.default_inspection_days || 5;
  document.getElementById("contractClosing").value = pandadocSettings.default_closing_days || 21;

  // Initialize LOI Breakdown inputs
  const arvEst = prim.estimated_value || agent.primary_price || 275000;
  const rehabEst = Math.round(((prim.sqft || 1500) * 30) / 1000) * 1000 || 45000;
  const loiArvInput = document.getElementById("contractLoiArv");
  const loiRepairsInput = document.getElementById("contractLoiRepairs");
  if (loiArvInput) loiArvInput.value = arvEst;
  if (loiRepairsInput) loiRepairsInput.value = rehabEst;

  document.getElementById("contractAgentDisplay").innerText = agent.full_name;
  document.getElementById("contractBrokerageDisplay").innerText = agent.brokerage;

  // Set mode: Test agent uses Sandbox; Live agents are ALWAYS locked to Production
  const isTestAgent = Boolean(
    agent.is_test || 
    agent.is_custom ||
    (agent.tier && agent.tier.toLowerCase().includes("test")) ||
    (agent.full_name && agent.full_name.toLowerCase().includes("test")) || 
    agent.agent_id?.toLowerCase().startsWith("test") ||
    agent.agent_id?.toLowerCase().startsWith("custom")
  );

  const envSwitcher = document.getElementById("contractEnvSwitcher");
  if (isTestAgent) {
    setContractModalMode("sandbox");
    if (envSwitcher) envSwitcher.classList.remove("hidden");
  } else {
    // Live / Real agents are ALWAYS in Production mode!
    setContractModalMode("production");
    if (envSwitcher) envSwitcher.classList.add("hidden");
  }

  setContractType("farbar");
  openModal("contractModal");
}

function handleContractPriceChange() {
  const price = parseFloat(document.getElementById("contractPrice").value) || 0;
  if (price > 0) {
    document.getElementById("contractEscrow").value = Math.round(price * 0.01);
  } else {
    document.getElementById("contractEscrow").value = "";
  }
}

function getContractPayload() {
  const isTestAgent = Boolean(
    selectedAgent?.is_test || 
    selectedAgent?.is_custom ||
    (selectedAgent?.tier && selectedAgent.tier.toLowerCase().includes("test")) ||
    (selectedAgent?.full_name && selectedAgent.full_name.toLowerCase().includes("test")) || 
    selectedAgent?.agent_id?.toLowerCase().startsWith("test") ||
    selectedAgent?.agent_id?.toLowerCase().startsWith("custom")
  );
  const activeMode = isTestAgent 
    ? (document.getElementById("contractModalMode").value || "sandbox")
    : "production";

  return {
    agent_id: document.getElementById("contractAgentId").value,
    contract_type: activeContractType,
    mode: activeMode,
    property_address: document.getElementById("contractPropertyAddress").value,
    recipient_email: document.getElementById("contractAgentEmail").value,
    purchase_price: parseFloat(document.getElementById("contractPrice").value) || 0,
    escrow_deposit: parseFloat(document.getElementById("contractEscrow").value) || 2500,
    inspection_days: parseInt(document.getElementById("contractInspection").value) || 7,
    closing_days: parseInt(document.getElementById("contractClosing").value) || 14,
    acceptance_days: parseInt(document.getElementById("contractAcceptanceDays").value) || 3,
    city: document.getElementById("contractCity").value,
    county: document.getElementById("contractCounty").value,
    zip: document.getElementById("contractZip").value,
    apn: document.getElementById("contractApn").value,
    legal_description: document.getElementById("contractLegalDescription").value,
    seller_name: document.getElementById("contractSellerName").value,
    agent_name: document.getElementById("contractAgentNameInput").value || selectedAgent?.full_name || "Listing Agent",
    brokerage_name: document.getElementById("contractBrokerageInput").value || selectedAgent?.brokerage || "Listing Brokerage",
    buyer_name: document.getElementById("contractBuyerName").value || "Peak Investments LLC",
    buyer_signer_name: document.getElementById("contractBuyerSignerName").value || "Johnathan Roberts",
    title_company: document.getElementById("contractTitleCompany").value || "Title Insights"
  };
}

async function handleSendContractSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("contractModalAlert");
  const btn = document.getElementById("btnDispatchContract");
  btn.disabled = true;
  btn.innerText = "Dispatching via PandaDoc...";

  try {
    const payload = getContractPayload();
    const res = await fetch("/api/contract/pandadoc/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    alertBox.classList.remove("hidden");
    if (data.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30";
      alertBox.innerHTML = `✓ ${data.message} ${data.session_url ? `<br><a href="${data.session_url}" target="_blank" class="underline text-purple-200 mt-1 block">Click here to view live PandaDoc Signing Link</a>` : ''}`;
      setTimeout(() => {
        loadStats();
        loadAgents();
      }, 2500);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${data.message}`;
    }
  } catch (err) {
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
    alertBox.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    const currentMode = document.getElementById("contractModalMode").value || "sandbox";
    btn.innerHTML = currentMode === "sandbox" ? "<span>🖋️ Send Test E-Sign (Sandbox)</span>" : "<span>🚀 Send Live Contract via PandaDoc</span>";
  }
}

async function downloadContractPdf() {
  const btn = document.querySelector("button[onclick='downloadContractPdf()']");
  const originalHtml = btn ? btn.innerHTML : "<span>📄 Download PDF</span>";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Generating PDF...</span>`;
  }
  const payload = getContractPayload();
  try {
    const res = await fetch("/api/contract/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      let detailMsg = "Failed to render PDF";
      try {
        const errJson = await res.json();
        if (errJson.detail) detailMsg = errJson.detail;
      } catch (_) {}
      throw new Error(detailMsg);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const safeName = (payload.property_address || "Agreement").replace(/[^a-zA-Z0-9_-]/g, "_");
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeContractType.toUpperCase()}_${safeName}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(url), 2000);
  } catch (err) {
    alert("Error downloading PDF: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

// Agent Detail Drawer
async function openAgentDrawer(agentId) {
  try {
    window.currentOpenDrawerAgentId = agentId;
    const res = await fetch(`/api/agent/${agentId}`);
    const data = await res.json();
    const a = data.agent;
    const outreach = data.outreach || [];
    selectedAgent = a;
    const isTest = Boolean(
      a.is_test || 
      a.is_custom ||
      (a.tier && a.tier.toLowerCase().includes("test")) ||
      (a.full_name && a.full_name.toLowerCase().includes("test")) || 
      a.agent_id?.toLowerCase().startsWith("test") ||
      a.agent_id?.toLowerCase().startsWith("custom")
    );

    document.getElementById("drawerAgentName").innerText = a.full_name;
    document.getElementById("drawerAgentBrokerage").innerText = `${a.brokerage} &bull; ${a.county} County`;

    const tierBadge = document.getElementById("drawerAgentTierBadge");
    if (tierBadge) {
      if (a.tier) {
        tierBadge.innerText = a.tier;
        tierBadge.className = (a.is_gold_deal || a.tier.includes("GOLD"))
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 inline-block"
          : a.tier.includes("Tier 1")
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 inline-block"
          : a.tier.includes("Tier 2")
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 inline-block"
          : "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 inline-block";
        tierBadge.classList.remove("hidden");
      } else {
        tierBadge.classList.add("hidden");
      }
    }

    const dBody = document.getElementById("drawerBody");
    dBody.innerHTML = `
      <!-- Contact Cards -->
      <div class="grid grid-cols-2 gap-3">
        <div class="bg-slate-900 border border-slate-800 p-3 rounded-xl font-mono">
          <div class="text-[10px] text-slate-400 font-sans uppercase">Phone</div>
          <div class="text-xs font-bold text-emerald-400 mt-0.5">${a.phone || 'N/A'}</div>
        </div>
        <div class="bg-slate-900 border border-slate-800 p-3 rounded-xl font-mono">
          <div class="text-[10px] text-slate-400 font-sans uppercase">Email</div>
          <div class="text-xs font-bold text-cyan-400 mt-0.5 truncate">${a.email || 'N/A'}</div>
        </div>
      </div>

      <!-- DEDICATED SANDBOX INBOUND TESTING CONSOLE (Test Agent Only) -->
      ${isTest ? renderTestAgentSandboxConsole(a) : ''}

      <!-- Lead Vetting Copilot Card (Flowchart & Underdog Engine) -->
      ${renderBotCopilotCard(a)}

      <!-- Pocket Deals Section -->
      <div class="space-y-2">
        <div class="flex items-center justify-between">
          <h4 class="text-xs font-bold text-white uppercase tracking-wider">Off-Market Pocket Deals (${a.pocket_deals?.length || 0})</h4>
          <button type="button" onclick="openPocketDealPrompt()" class="text-[11px] text-fuchsia-400 hover:underline">+ Log Deal</button>
        </div>
        ${(a.pocket_deals && a.pocket_deals.length > 0) ? a.pocket_deals.map(pd => `
          <div class="bg-fuchsia-950/20 border border-fuchsia-500/30 p-3 rounded-xl text-xs space-y-1.5">
            <div class="flex items-center justify-between">
              <span class="font-bold text-fuchsia-200">📍 ${escapeHtml(pd.address)}, ${escapeHtml(pd.city)}</span>
              <button type="button" onclick="openLoiAnalyzer('${a.agent_id}', '${escapeHtml(pd.address)}', ${pd.asking_price || 0}, 1500)" class="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/20 text-[11px] font-bold transition flex items-center gap-1 cursor-pointer">
                <span>📊 Calc LOI</span>
              </button>
            </div>
            <div class="text-slate-300">Target Ask: $${(pd.asking_price).toLocaleString()} &bull; Timeline: ${pd.timeline}</div>
            <div class="text-slate-400 text-[11px]">${escapeHtml(pd.condition_notes)}</div>
          </div>
        `).join('') : '<div class="text-slate-500 text-xs italic">No off-market deals logged yet for this agent.</div>'}
      </div>

      <!-- Active On-Market MLS Listings -->
      <div class="space-y-2">
        <h4 class="text-xs font-bold text-white uppercase tracking-wider">Active On-Market Listings (${a.listings.length})</h4>
        <div class="space-y-2">
          ${a.listings.map(l => `
            <div class="bg-slate-900 border border-slate-800 p-3.5 rounded-xl space-y-2 text-xs">
              <div class="flex items-center justify-between">
                <span class="font-bold text-white">📍 ${escapeHtml(l.address)}, ${escapeHtml(l.city)}</span>
                <span class="font-mono font-bold text-indigo-400">$${(l.listing_price).toLocaleString()}</span>
              </div>
              <div class="text-[11px] text-slate-400 flex items-center gap-3">
                <span>🛏️ ${l.beds}b / 🛁 ${l.baths}ba</span>
                <span>📐 ${l.sqft} sqft</span>
                <span>📅 Built ${l.year_built}</span>
                <span>⏱️ ${l.days_on_market} DOM</span>
              </div>
              <div class="flex items-center justify-between pt-1 border-t border-slate-800/80">
                <div class="text-[10px] text-slate-500 font-mono">APN: ${l.apn || 'N/A'} &bull; Est. Value: $${(l.estimated_value || 0).toLocaleString()}</div>
                <button type="button" onclick="openLoiAnalyzer('${a.agent_id}', '${escapeHtml(l.address)}', ${l.listing_price || 0}, ${l.sqft || 1500}, ${l.beds || 3}, ${l.baths || 2}, ${l.year_built || 1980})" class="px-2.5 py-1 rounded-lg bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-300 border border-indigo-500/20 text-[11px] font-bold transition flex items-center gap-1 cursor-pointer">
                  <span>📊 Calc LOI Offer</span>
                </button>
              </div>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- 2-WAY LIVE SMS CONVERSATION THREAD -->
      <div class="space-y-3 pt-2 border-t border-slate-800">
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <h4 class="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
              <span>💬</span>
              <span>2-Way SMS Conversation Thread</span>
            </h4>
            <span class="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">
              ${a.phone ? `● Live (${a.phone})` : 'No Phone'}
            </span>
          </div>
          <span class="text-[10px] text-slate-500 font-mono">${outreach.length} message${outreach.length === 1 ? '' : 's'}</span>
        </div>

        <!-- Chat Bubble Container -->
        <div id="drawerChatThread" data-count="${outreach.length}" class="bg-[#0b1220] border border-slate-800 rounded-2xl p-4 max-h-[360px] overflow-y-auto space-y-3 flex flex-col">
          ${renderChatBubbles(a, outreach)}
        </div>

        <!-- Direct In-Drawer Reply Bar -->
        <div class="bg-slate-900 border border-slate-800 rounded-2xl p-3.5 space-y-2.5">
          ${!isTest ? `
            <div class="bg-amber-500/10 border border-amber-500/30 rounded-xl px-3 py-1.5 text-[11px] text-amber-300 font-semibold flex items-center gap-1.5">
              <span>⚠️</span>
              <span>LIVE MLS REALTOR: Messages sent here will dispatch real cellular SMS to ${escapeHtml(a.phone)}.</span>
            </div>
          ` : `
            <div class="bg-emerald-500/10 border border-emerald-500/30 rounded-xl px-3 py-1.5 text-[11px] text-emerald-300 font-semibold flex items-center gap-1.5">
              <span>🧪</span>
              <span>SANDBOX TEST AGENT: Safe environment. SMS dispatches directly to your personal phone (${escapeHtml(a.phone)}).</span>
            </div>
          `}
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
              <span>✍️</span>
              <span>Direct Reply to ${escapeHtml(a.first_name || 'Agent')}</span>
            </span>
            <span class="text-[10px] text-slate-500 font-mono" id="drawerCharCount">0 chars</span>
          </div>

          <!-- Quick Template Chips -->
          <div class="flex items-center gap-1.5 overflow-x-auto pb-0.5 text-[10px]">
            <button type="button" onclick="insertDrawerTemplate('icebreaker')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition whitespace-nowrap cursor-pointer">🎯 Icebreaker</button>
            <button type="button" onclick="insertDrawerTemplate('double_comm')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition whitespace-nowrap cursor-pointer">💰 Double Comm</button>
            <button type="button" onclick="insertDrawerTemplate('checkin')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition whitespace-nowrap cursor-pointer">🔄 30d Check-in</button>
            <button type="button" onclick="insertDrawerTemplate('backup_offer')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition whitespace-nowrap cursor-pointer">⚡ Backup Offer</button>
          </div>

          <div>
            <textarea id="drawerReplyText" rows="2" placeholder="Type SMS message to ${escapeHtml(a.first_name || 'agent')}... (dispatches live from your phone via Android Gateway)" oninput="updateDrawerCharCount()" class="w-full bg-[#0b1220] border border-slate-700 rounded-xl p-2.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"></textarea>
          </div>

          <div id="drawerReplyAlert" class="hidden p-2.5 rounded-xl text-xs font-semibold"></div>

          <div class="flex items-center justify-between pt-1">
            <button type="button" onclick="openNegotiationHud('${a.agent_id}')" class="px-3 py-1.5 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold transition flex items-center gap-1 cursor-pointer" title="Open Setup Call Negotiation HUD">
              <span>📞 Setup Call HUD</span>
            </button>
            <div class="flex items-center gap-2">
              <button type="button" onclick="openLoiAnalyzer('${a.agent_id}')" class="px-3 py-1.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition flex items-center gap-1 cursor-pointer" title="Calculate Offer & Draft LOI">
                <span>📊 LOI Calc</span>
              </button>
              <button type="button" onclick="openContractModal('${a.agent_id}')" class="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold transition flex items-center gap-1 cursor-pointer" title="Official Florida FAR/BAR ASIS Contract">
                <span>🖋️ FAR/BAR</span>
              </button>
              <button type="button" id="btnDrawerSendSms" onclick="sendDrawerReply('${a.agent_id}', '${escapeHtml(a.phone)}')" class="px-4 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-md shadow-emerald-600/30 cursor-pointer">
                <span>🚀 Send SMS</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    `;

    document.getElementById("agentDrawer").classList.remove("translate-x-full");

    // Auto-scroll chat thread to bottom
    setTimeout(() => {
      const thread = document.getElementById("drawerChatThread");
      if (thread) thread.scrollTop = thread.scrollHeight;
    }, 50);

  } catch (err) {
    console.error("Error opening drawer:", err);
  }
}

function closeAgentDrawer() {
  window.currentOpenDrawerAgentId = null;
  document.getElementById("agentDrawer").classList.add("translate-x-full");
}

function renderTestAgentSandboxConsole(a) {
  const currentPartner = (window.botSettings && window.botSettings.partner_name) ? window.botSettings.partner_name : "Jessica";
  return `
    <!-- DEDICATED SANDBOX INBOUND TESTING CONSOLE -->
    <div class="rounded-2xl border border-violet-500/50 bg-gradient-to-b from-violet-950/40 via-slate-900 to-slate-900 p-4 space-y-3.5 shadow-xl shadow-violet-950/30">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-8 h-8 rounded-xl bg-violet-500/20 text-violet-300 border border-violet-500/30 flex items-center justify-center text-sm font-bold shadow">🧪</div>
          <div>
            <h4 class="text-xs font-bold text-white flex items-center gap-1.5">
              <span>Dedicated Sandbox Simulator</span>
              <span class="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wide bg-violet-500/20 text-violet-300 border border-violet-500/30">TEST AGENT ONLY</span>
            </h4>
            <div class="text-[10px] text-slate-400">Isolated testing environment &bull; Dispatches to your phone <span class="font-mono text-emerald-300 font-bold">${escapeHtml(a.phone || '')}</span></div>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <button type="button" onclick="toggleTestAgentAutopilot('${a.agent_id}')" class="px-2.5 py-1 rounded-lg ${a.test_autopilot ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/30' : 'bg-slate-800 text-slate-400 hover:text-white border border-slate-700'} text-[10px] font-bold transition flex items-center gap-1 cursor-pointer" title="Toggle Auto-Pilot for this test agent only (dispatches SMS automatically without requiring manual approval)">
            <span>⚡ Auto-Pilot:</span>
            <span>${a.test_autopilot ? 'ON' : 'OFF'}</span>
          </button>
          <button type="button" onclick="resetTestAgentHistory('${a.agent_id}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-rose-500/20 text-slate-300 hover:text-rose-300 border border-slate-700 hover:border-rose-500/30 text-[10px] font-bold transition cursor-pointer" title="Wipe chat history for this test agent">
            🗑️ Reset Chat
          </button>
        </div>
      </div>

      <!-- Quick Scenario Triggers -->
      <div class="space-y-1.5">
        <span class="text-[10px] font-bold text-slate-300 uppercase tracking-wider block">One-Click Flowchart Testing Presets:</span>
        <div class="grid grid-cols-2 gap-2 text-[11px]">
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Hey Johnathan, I have an off-market 3/2 fixer at 789 Ocean Breeze Ave in Melbourne, seller asking $180k cash.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-amber-300 border border-amber-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>⭐</span>
            <span class="truncate">1. Pitch Fixer ($180k Ask)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Roof is about 12 years old, AC is working fine. Needs full kitchen and bathroom update, cosmetic rehab throughout.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-emerald-300 border border-emerald-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>🔨</span>
            <span class="truncate">2. Condition (Roof/AC/Rehab)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Here is a drive link with photos: drive.google.com/test123')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-cyan-300 border border-cyan-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>📸</span>
            <span class="truncate">3. Photos (Drive Link)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Seller wants to close within the next 2-3 weeks, needs cash fast.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-indigo-300 border border-indigo-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>📅</span>
            <span class="truncate">4. Timeline (2-3 Weeks)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Tomorrow at 2pm works great for us to speak with ${escapeHtml(currentPartner)}.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-emerald-300 border border-emerald-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>✅</span>
            <span class="truncate">5. Confirm Appt (${escapeHtml(currentPartner)})</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'It is 100 Luxury Way in Viera, completely turnkey asking $410k on MLS.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-purple-300 border border-purple-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>🏡</span>
            <span class="truncate">6. Turnkey ($410k Creative)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'No, cash offers only. They will not do creative terms.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-yellow-300 border border-yellow-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>🌱</span>
            <span class="truncate">7. Decline Terms (Tier 2)</span>
          </button>
          <button type="button" onclick="triggerTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}', 'Please remove me from your list, STOP.')" class="px-3 py-2 rounded-xl bg-[#0b1220] hover:bg-violet-900/30 text-rose-300 border border-rose-500/30 font-bold text-left transition flex items-center gap-1.5 cursor-pointer shadow-sm">
            <span>🛑</span>
            <span class="truncate">8. Opt-Out (Stop / Dead)</span>
          </button>
        </div>
      </div>

      <!-- Custom Inbound Message Input -->
      <div class="space-y-1.5 pt-1.5 border-t border-slate-800">
        <label class="text-[10px] text-slate-400 block font-medium">Or simulate custom incoming text from this test agent:</label>
        <div class="flex gap-2">
          <input type="text" id="customTestAgentMsgInput" placeholder="Type custom message as if test agent texted you..." class="w-full bg-[#0b1220] border border-slate-700 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-violet-500 font-sans" onkeydown="if (event.key === 'Enter') { triggerCustomTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}'); }">
          <button type="button" onclick="triggerCustomTestAgentSimulation('${a.agent_id}', '${escapeHtml(a.phone)}')" class="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-bold text-xs whitespace-nowrap shadow-md shadow-violet-600/30 transition cursor-pointer">
            ⚡ Simulate Text
          </button>
        </div>
      </div>
    </div>
  `;
}

let typingCountdownInterval = null;
function startTypingCountdown(seconds) {
  if (typingCountdownInterval) clearInterval(typingCountdownInterval);
  let remaining = seconds;
  const countEl = document.getElementById("autopilotCountdown");
  typingCountdownInterval = setInterval(() => {
    remaining -= 1;
    const el = document.getElementById("autopilotCountdown");
    if (el) {
      if (remaining > 0) {
        el.innerText = `(~${remaining}s human delay)`;
      } else {
        el.innerText = `(sending via Android Gateway...)`;
      }
    }
    if (remaining <= -10) {
      clearInterval(typingCountdownInterval);
    }
  }, 1000);
}

async function triggerTestAgentSimulation(agentId, phone, message) {
  const thread = document.getElementById("drawerChatThread");
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });

  // OPTIMISTICALLY render inbound bubble immediately
  const inbId = "inb_" + Date.now();
  const inbHtml = `
    <div class="flex flex-col items-start gap-1 max-w-[85%]" id="${inbId}">
      <div class="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium px-1">
        <span class="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span>
        <span class="font-bold text-slate-200">📥 ${escapeHtml(selectedAgent?.first_name || 'Agent')}</span>
        <span class="text-slate-600">&bull;</span>
        <span class="font-mono text-slate-500 text-[9px]">${timeStr}</span>
      </div>
      <div class="bg-slate-800 text-slate-100 border border-slate-700/80 rounded-2xl rounded-tl-none p-3 text-xs leading-relaxed shadow-sm">
        ${escapeHtml(message)}
      </div>
    </div>
  `;

  if (thread) {
    if (thread.innerHTML.includes("No outreach history yet")) {
      thread.innerHTML = "";
    }
    thread.insertAdjacentHTML("beforeend", inbHtml);
    const currentCount = parseInt(thread.getAttribute("data-count") || "0", 10);
    thread.setAttribute("data-count", currentCount + 1);

    // If Autopilot is active, show typing indicator immediately
    const isAutopilot = Boolean(
      botSettings?.mode === "autopilot" || selectedAgent?.test_autopilot
    );
    if (isAutopilot) {
      // Remove any existing typing indicator
      const oldTyping = document.getElementById("drawerTypingIndicator");
      if (oldTyping) oldTyping.remove();

      const delayVal = botSettings?.auto_send_delay_seconds || 30;
      const typingHtml = `
        <div id="drawerTypingIndicator" class="flex items-center gap-2 p-3 rounded-2xl bg-indigo-950/40 border border-indigo-500/30 text-indigo-300 text-xs shadow-sm max-w-[85%] ml-auto">
          <span class="flex h-2 w-2 relative">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
          </span>
          <span class="font-bold">Johnathan is typing...</span>
          <span class="text-slate-400 font-mono text-[10px]" id="autopilotCountdown">(~${delayVal}s human delay)</span>
        </div>
      `;
      thread.insertAdjacentHTML("beforeend", typingHtml);
      startTypingCountdown(delayVal);
    }
    thread.scrollTop = thread.scrollHeight;
  }

  try {
    const res = await fetch("/api/sms/simulate-inbound", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        phone: phone,
        message: message
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      loadStats();
      loadAgents();
      // If NOT in autopilot, update drawer immediately to show new suggestion card
      const isAutopilot = Boolean(
        botSettings?.mode === "autopilot" || selectedAgent?.test_autopilot
      );
      if (!isAutopilot) {
        await openAgentDrawer(agentId);
      }
    } else {
      alert("Simulation error: " + (d.message || "Failed"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

function triggerCustomTestAgentSimulation(agentId, phone) {
  const el = document.getElementById("customTestAgentMsgInput");
  if (!el) return;
  const msg = el.value.trim();
  if (!msg) {
    alert("Please type a message to simulate.");
    return;
  }
  triggerTestAgentSimulation(agentId, phone, msg);
}

async function resetTestAgentHistory(agentId) {
  if (!confirm("Reset all test conversation history and pipeline state for this test agent?")) return;
  try {
    const res = await fetch(`/api/agent/${agentId}/reset-history`, {
      method: "POST"
    });
    const d = await res.json();
    if (d.status === "success") {
      await openAgentDrawer(agentId);
      loadStats();
      loadAgents();
    } else {
      alert("Error: " + (d.message || "Failed to reset"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function toggleTestAgentAutopilot(agentId) {
  try {
    const res = await fetch(`/api/agent/${agentId}/toggle-autopilot`, {
      method: "POST"
    });
    const d = await res.json();
    if (d.status === "success") {
      await openAgentDrawer(agentId);
      loadStats();
      loadAgents();
    }
  } catch (err) {
    alert("Error toggling autopilot: " + err.message);
  }
}

function renderBotCopilotCard(a) {
  const isGold = Boolean(a.is_gold_deal || (a.tier && a.tier.includes("GOLD")));
  const botVetting = a.bot_vetting || {};
  const stateData = botVetting.state_data || {};
  const currentMode = (window.botSettings && window.botSettings.mode) ? window.botSettings.mode : "copilot";
  const partnerName = (window.botSettings && window.botSettings.partner_name) ? window.botSettings.partner_name : "Matt";
  const currentNode = a.last_bot_node || botVetting.node || "INITIAL_OUTREACH";
  const lastSuggestion = a.last_bot_suggestion || "";
  const suggestionReason = a.last_bot_reason || "";
  const campaign = a.campaign_status || {};
  const apptTime = stateData.appointment_time || "";

  // Deal ratio calculation
  let askPrice = stateData.asking_price || (a.pocket_deals?.[0]?.asking_price) || (a.listings?.[0]?.listing_price) || 0;
  let estVal = stateData.zestimate || (a.listings?.[0]?.estimated_value) || (a.primary_price ? a.primary_price * 1.1 : 0);
  let ratioPct = (askPrice > 0 && estVal > 0) ? Math.round((askPrice / estVal) * 100) : null;

  const tierOptions = [
    { value: "Tier 1: Hot Deal / Underwrite", label: "🔥 Tier 1: Hot Deal / Underwrite" },
    { value: "⭐ THE GOLD (≤80%)", label: "⭐ THE GOLD (≤80% Zestimate)" },
    { value: "Tier 2: Pocket Lead Nurture", label: "🌱 Tier 2: Pocket Lead Nurture" },
    { value: "Tier 3: Inactive", label: "⚪ Tier 3: Inactive" },
    { value: "Cash Agent Dead (Opt-out)", label: "🛑 Cash Agent Dead (Opt-out)" }
  ];

  const escapedScriptParam = encodeURIComponent(lastSuggestion);

  return `
    <!-- LEAD VETTING COPILOT CARD -->
    <div class="rounded-2xl border p-4 space-y-3.5 transition-all ${
      isGold 
        ? 'bg-gradient-to-b from-amber-950/40 to-slate-900 border-amber-500/50 shadow-lg shadow-amber-950/30' 
        : 'bg-slate-900/90 border-slate-800'
    }">
      <!-- Header row -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <div class="w-7 h-7 rounded-lg ${isGold ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'} flex items-center justify-center text-sm font-bold">
            ${isGold ? '⭐' : '🤖'}
          </div>
          <div>
            <h4 class="text-xs font-bold text-white flex items-center gap-1.5">
              <span>Lead Vetting Copilot</span>
              <span class="px-2 py-0.5 rounded text-[9px] font-extrabold uppercase tracking-wide ${
                currentMode === 'autopilot' 
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' 
                  : 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
              }">${currentMode}</span>
            </h4>
            <div class="text-[10px] text-slate-400">Flowchart Node: <span class="font-mono text-indigo-300 font-bold">${escapeHtml(currentNode)}</span></div>
          </div>
        </div>

        <!-- Quick Tier Selector -->
        <div class="flex items-center gap-1.5">
          <label class="text-[10px] text-slate-400">Funnel:</label>
          <select onchange="setAgentTierQuick('${a.agent_id}', this.value)" class="bg-[#0b1220] border border-slate-700 rounded-lg px-2 py-1 text-[11px] font-bold text-white focus:outline-none focus:border-indigo-500 cursor-pointer">
            ${tierOptions.map(opt => `<option value="${opt.value}" ${(a.tier === opt.value || (opt.value.includes('GOLD') && isGold)) ? 'selected' : ''}>${opt.label}</option>`).join('')}
          </select>
        </div>
      </div>

      <!-- Ratio & Status Strip -->
      <div class="grid grid-cols-2 gap-2 text-xs">
        <div class="bg-[#0b1220] border border-slate-800 rounded-xl p-2.5 space-y-1">
          <div class="text-[10px] text-slate-400 uppercase font-medium flex items-center justify-between">
            <span>Price vs Zestimate</span>
            ${ratioPct ? (ratioPct <= 80 ? '<span class="text-amber-400 font-bold text-[9px]">⭐ THE GOLD</span>' : '<span class="text-slate-400 text-[9px]">Turnkey</span>') : ''}
          </div>
          <div class="font-bold flex items-center gap-2">
            ${ratioPct !== null 
              ? `<span class="${ratioPct <= 80 ? 'text-amber-300 text-sm' : 'text-slate-200'} font-mono font-bold">${ratioPct}%</span>
                 <span class="text-[10px] text-slate-400">($${Math.round(askPrice/1000)}k ask / $${Math.round(estVal/1000)}k est)</span>`
              : `<span class="text-slate-500 italic text-[11px]">Awaiting price info</span>`
            }
          </div>
        </div>

        <div class="bg-[#0b1220] border border-slate-800 rounded-xl p-2.5 space-y-1">
          <div class="text-[10px] text-slate-400 uppercase font-medium">Underwriting Appt (${partnerName})</div>
          <div class="font-bold">
            ${apptTime 
              ? `<span class="text-emerald-400 text-[11px] flex items-center gap-1 font-mono">📅 ${escapeHtml(apptTime)}</span>`
              : `<span class="text-slate-500 italic text-[11px]">Not scheduled yet</span>`
            }
          </div>
        </div>
      </div>

      <!-- Suggested Next Reply Script (if available) -->
      ${lastSuggestion ? `
        <div class="space-y-2 bg-[#0b1220] border ${isGold ? 'border-amber-500/40' : 'border-indigo-500/40'} rounded-xl p-3">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-bold ${isGold ? 'text-amber-300' : 'text-indigo-300'} flex items-center gap-1.5">
              <span>💡</span>
              <span>Recommended Script (${escapeHtml(currentNode)})</span>
            </span>
            ${suggestionReason ? `<span class="text-[9px] text-slate-400 max-w-[200px] truncate" title="${escapeHtml(suggestionReason)}">${escapeHtml(suggestionReason)}</span>` : ''}
          </div>
          
          <div class="p-2.5 bg-slate-900/80 rounded-lg text-xs text-white leading-relaxed font-sans border border-slate-800">
            "${escapeHtml(lastSuggestion)}"
          </div>

          <div class="flex items-center justify-end gap-2 pt-1">
            <button type="button" onclick="copyBotScriptToInput(decodeURIComponent('${escapedScriptParam}'))" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-[11px] font-bold border border-slate-700 transition flex items-center gap-1 cursor-pointer">
              <span>✏️ Copy to Reply Bar</span>
            </button>
            <button type="button" onclick="approveBotReply('${a.agent_id}')" class="px-3.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold shadow-md shadow-emerald-600/30 transition flex items-center gap-1.5 cursor-pointer">
              <span>🚀 1-Click Approve & Send</span>
            </button>
          </div>
        </div>
      ` : ''}

      <!-- Underdog Cadence Action if due -->
      ${(campaign && campaign.eligible) ? `
        <div class="flex items-center justify-between bg-yellow-500/10 border border-yellow-500/30 rounded-xl p-2.5 text-xs">
          <div class="space-y-0.5">
            <span class="font-bold text-yellow-300 flex items-center gap-1">
              <span>⏰</span>
              <span>${(campaign.campaign_step || '').replace(/_/g, ' ')} Due</span>
            </span>
            <span class="text-[10px] text-slate-400">${campaign.days_since_outreach} days since first message without response</span>
          </div>
          <button type="button" onclick="sendCampaignFollowup('${a.agent_id}')" class="px-3 py-1 rounded-lg bg-yellow-500 hover:bg-yellow-400 text-slate-950 font-bold text-[11px] transition shadow cursor-pointer">
            📤 Send Cadence Text
          </button>
        </div>
      ` : ''}
    </div>
  `;
}

function copyBotScriptToInput(script) {
  const el = document.getElementById("drawerReplyText");
  if (!el) return;
  el.value = script;
  updateDrawerCharCount();
  el.focus();
  el.scrollIntoView({ behavior: "smooth", block: "center" });
}

async function approveBotReply(agentId, customText = null) {
  const isTest = Boolean(
    selectedAgent?.is_test || 
    selectedAgent?.is_custom ||
    (selectedAgent?.tier && selectedAgent.tier.toLowerCase().includes("test")) ||
    (selectedAgent?.full_name && selectedAgent.full_name.toLowerCase().includes("test")) || 
    agentId?.toLowerCase().startsWith("test") ||
    agentId?.toLowerCase().startsWith("custom")
  );
  if (!isTest) {
    if (!confirm(`⚠️ LIVE REALTOR WARNING:\n\nYou are about to dispatch a REAL cellular SMS to listing agent ${selectedAgent?.full_name || 'Agent'} (${selectedAgent?.phone || ''}).\n\nAre you sure you want to approve and send this live SMS?`)) {
      return;
    }
  }

  const thread = document.getElementById("drawerChatThread");
  const textToSend = customText || selectedAgent?.last_bot_suggestion || "Great, let's connect.";

  // OPTIMISTIC RENDERING: Immediately append outbound bubble to chat thread
  const optId = "opt_" + Date.now();
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const optHtml = `
    <div class="flex flex-col items-end gap-1 max-w-[85%] ml-auto" id="${optId}">
      <div class="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium px-1">
        <span class="font-mono text-slate-500 text-[9px]">${timeStr}</span>
        <span class="text-slate-600">&bull;</span>
        <span class="font-bold text-indigo-300">📤 You (407 Flips)</span>
        <span class="text-[8px] uppercase px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold animate-pulse" id="${optId}_status">Sending...</span>
      </div>
      <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none p-3 text-xs font-medium leading-relaxed shadow-md shadow-indigo-600/20 border border-indigo-500/30">
        ${escapeHtml(textToSend)}
      </div>
    </div>
  `;

  if (thread) {
    if (thread.innerHTML.includes("No outreach history yet")) {
      thread.innerHTML = "";
    }
    thread.insertAdjacentHTML("beforeend", optHtml);
    thread.scrollTop = thread.scrollHeight;
    const currentCount = parseInt(thread.getAttribute("data-count") || "0", 10);
    thread.setAttribute("data-count", currentCount + 1);
  }

  // Hide the copilot suggestion banner in drawer if present
  const suggBanner = document.getElementById("drawerBotSuggestionBanner");
  if (suggBanner) suggBanner.classList.add("hidden");

  try {
    const res = await fetch("/api/bot/approve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        approved_text: customText
      })
    });
    const d = await res.json();
    const statusBadge = document.getElementById(`${optId}_status`);
    if (d.status === "success") {
      if (statusBadge) {
        statusBadge.className = "text-[8px] uppercase px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-bold";
        statusBadge.innerText = "SMS";
      }
      loadStats();
      loadAgents();
      updateGlobalGoldenCountBadge();
    } else {
      if (statusBadge) {
        statusBadge.className = "text-[8px] uppercase px-1 py-0.5 rounded bg-rose-500/30 text-rose-300 font-bold";
        statusBadge.innerText = "FAILED";
      }
      alert("Error approving reply: " + (d.message || "Failed"));
    }
  } catch (err) {
    const statusBadge = document.getElementById(`${optId}_status`);
    if (statusBadge) {
      statusBadge.className = "text-[8px] uppercase px-1 py-0.5 rounded bg-rose-500/30 text-rose-300 font-bold";
      statusBadge.innerText = "NET ERROR";
    }
    alert("Network error: " + err.message);
  }
}

async function setAgentTierQuick(agentId, tier) {
  try {
    const res = await fetch("/api/bot/set-tier", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        tier: tier
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      loadStats();
      loadAgents();
      const tierBadge = document.getElementById("drawerAgentTierBadge");
      if (tierBadge) {
        tierBadge.innerText = tier;
        tierBadge.className = tier.includes("GOLD")
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30 inline-block"
          : tier.includes("Tier 1")
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/30 inline-block"
          : tier.includes("Tier 2")
          ? "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 inline-block"
          : "px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 inline-block";
        tierBadge.classList.remove("hidden");
      }
    } else {
      alert("Error updating tier: " + (d.message || "Failed"));
    }
  } catch (err) {
    console.error("Error setting tier:", err);
  }
}

async function sendCampaignFollowup(agentId) {
  if (!confirm("Send automated Underdog Model cadence follow-up text to this agent now?")) return;
  try {
    const res = await fetch("/api/campaigns/send-followup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_id: agentId })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("✓ Follow-up campaign text dispatched via Android Gateway!");
      if (window.currentOpenDrawerAgentId === agentId) {
        await openAgentDrawer(agentId);
      }
      loadStats();
      loadAgents();
    } else {
      alert("Error: " + (d.message || "Failed to send follow-up"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function approveBotReplyFromInbox(agentId) {
  await approveBotReply(agentId);
  await markInboxRead(agentId);
  openInboxModal();
}

function renderChatBubbles(a, outreach) {
  if (!outreach || outreach.length === 0) {
    return `
      <div class="text-center py-8 text-slate-500 text-xs italic">
        No outreach history yet with ${escapeHtml(a.full_name)}. Use the reply box below to send the first icebreaker text!
      </div>
    `;
  }
  return [...outreach].reverse().map(o => {
    const isInbound = o.direction === 'INBOUND' || o.sender_phone;
    if (isInbound) {
      return `
        <!-- Inbound Message (From Agent) -->
        <div class="flex flex-col items-start gap-1 max-w-[85%]">
          <div class="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium px-1">
            <span class="w-2 h-2 rounded-full bg-emerald-400 inline-block animate-pulse"></span>
            <span class="font-bold text-slate-200">📥 ${escapeHtml(a.first_name || 'Agent')}</span>
            <span class="text-slate-600">&bull;</span>
            <span class="font-mono text-slate-500 text-[9px]">${o.timestamp}</span>
          </div>
          <div class="bg-slate-800 text-slate-100 border border-slate-700/80 rounded-2xl rounded-tl-none p-3 text-xs leading-relaxed shadow-sm">
            ${escapeHtml(o.message || '')}
          </div>
        </div>
      `;
    } else {
      return `
        <!-- Outbound Message (From You) -->
        <div class="flex flex-col items-end gap-1 max-w-[85%] ml-auto">
          <div class="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium px-1">
            <span class="font-mono text-slate-500 text-[9px]">${o.timestamp}</span>
            <span class="text-slate-600">&bull;</span>
            <span class="font-bold text-indigo-300">📤 You (407 Flips)</span>
            <span class="text-[8px] uppercase px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-bold">${o.channel || 'SMS'}</span>
          </div>
          <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none p-3 text-xs font-medium leading-relaxed shadow-md shadow-indigo-600/20 border border-indigo-500/30">
            ${escapeHtml(o.message || o.subject || '')}
          </div>
        </div>
      `;
    }
  }).join('');
}

function insertDrawerTemplate(type) {
  if (!selectedAgent) return;
  const tmpl = type === 'icebreaker' ? getRandomBrookeIcebreaker() : (SMS_TEMPLATES[type] || SMS_TEMPLATES.icebreaker);
  let rendered = tmpl
    .replace(/{Agent_FirstName}/g, selectedAgent.first_name || "there")
    .replace(/{Listing_Address}/g, selectedAgent.primary_address || "your listing")
    .replace(/{City}/g, selectedAgent.primary_city || "the area");

  rendered = resolveSpintax(rendered);
  rendered = sanitizeSmsNoHyphens(rendered);

  const input = document.getElementById("drawerReplyText");
  if (input) {
    input.value = rendered;
    updateDrawerCharCount();
    input.focus();
  }
}

function updateDrawerCharCount() {
  const el = document.getElementById("drawerReplyText");
  const countEl = document.getElementById("drawerCharCount");
  if (!el || !countEl) return;
  const len = el.value.length;
  countEl.innerText = `${len} chars (${Math.ceil(len / 160) || 1} SMS)`;
}

async function sendDrawerReply(agentId, phone) {
  const textEl = document.getElementById("drawerReplyText");
  const alertEl = document.getElementById("drawerReplyAlert");
  const btn = document.getElementById("btnDrawerSendSms");
  const thread = document.getElementById("drawerChatThread");

  if (!textEl) return;
  const msg = textEl.value.trim();

  if (!msg) {
    alert("Please type a message before sending.");
    return;
  }
  if (!phone) {
    alert("This agent does not have a valid phone number.");
    return;
  }

  const isTest = Boolean(
    selectedAgent?.is_test || 
    selectedAgent?.is_custom ||
    (selectedAgent?.tier && selectedAgent.tier.toLowerCase().includes("test")) ||
    (selectedAgent?.full_name && selectedAgent.full_name.toLowerCase().includes("test")) || 
    agentId?.toLowerCase().startsWith("test") ||
    agentId?.toLowerCase().startsWith("custom")
  );
  if (!isTest) {
    if (!confirm(`⚠️ LIVE REALTOR WARNING:\n\nYou are about to dispatch a REAL cellular SMS to listing agent ${selectedAgent?.full_name || 'Agent'} at ${phone}.\n\nAre you sure you want to send this live SMS?`)) {
      return;
    }
  }

  // OPTIMISTIC RENDERING: Immediately append outgoing bubble to chat thread
  const optId = "opt_" + Date.now();
  const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const optHtml = `
    <div class="flex flex-col items-end gap-1 max-w-[85%] ml-auto" id="${optId}">
      <div class="flex items-center gap-1.5 text-[10px] text-slate-400 font-medium px-1">
        <span class="font-mono text-slate-500 text-[9px]">${timeStr}</span>
        <span class="text-slate-600">&bull;</span>
        <span class="font-bold text-indigo-300">📤 You (407 Flips)</span>
        <span class="text-[8px] uppercase px-1 py-0.5 rounded bg-amber-500/20 text-amber-300 font-bold animate-pulse" id="${optId}_status">Sending...</span>
      </div>
      <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-none p-3 text-xs font-medium leading-relaxed shadow-md shadow-indigo-600/20 border border-indigo-500/30">
        ${escapeHtml(msg)}
      </div>
    </div>
  `;

  if (thread) {
    if (thread.innerHTML.includes("No outreach history yet")) {
      thread.innerHTML = "";
    }
    thread.insertAdjacentHTML("beforeend", optHtml);
    thread.scrollTop = thread.scrollHeight;
    const currentCount = parseInt(thread.getAttribute("data-count") || "0", 10);
    thread.setAttribute("data-count", currentCount + 1);
  }

  // Clear input immediately so user knows their message has been sent
  textEl.value = "";
  updateDrawerCharCount();

  btn.disabled = true;
  btn.innerText = "Dispatching...";
  alertEl.classList.add("hidden");

  try {
    const res = await fetch("/api/sms/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        phone: phone,
        message: msg
      })
    });
    const d = await res.json();
    const statusBadge = document.getElementById(`${optId}_status`);
    if (d.status === "success") {
      if (statusBadge) {
        statusBadge.className = "text-[8px] uppercase px-1 py-0.2 rounded bg-indigo-500/20 text-indigo-300 font-bold";
        statusBadge.innerText = "SMS";
      }
      alertEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertEl.innerText = "✓ Dispatched via Android Gateway!";
      alertEl.classList.remove("hidden");
      setTimeout(() => alertEl.classList.add("hidden"), 3000);
      loadStats();
      loadAgents();
    } else {
      if (statusBadge) {
        statusBadge.className = "text-[8px] uppercase px-1 py-0.5 rounded bg-rose-500/30 text-rose-300 font-bold";
        statusBadge.innerText = "FAILED";
      }
      alertEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertEl.innerText = `Error: ${d.message}`;
      alertEl.classList.remove("hidden");
    }
  } catch (err) {
    const statusBadge = document.getElementById(`${optId}_status`);
    if (statusBadge) {
      statusBadge.className = "text-[8px] uppercase px-1 py-0.5 rounded bg-rose-500/30 text-rose-300 font-bold";
      statusBadge.innerText = "NET ERROR";
    }
    alertEl.className = "p-2.5 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertEl.innerText = `Network error: ${err.message}`;
    alertEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Send SMS";
  }
}

// CSV Upload Handler
async function handleCsvUpload(e) {
  const file = e.target.files[0];
  if (!file) return;

  const inputEl = e.target;
  const labelEl = inputEl.closest("label");
  const origText = labelEl ? labelEl.innerHTML : "";
  if (labelEl) {
    labelEl.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span> Enriching agent phone numbers...`;
  }

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await fetch("/api/upload-csv", {
      method: "POST",
      body: formData
    });
    const d = await res.json();
    if (d.status === "success") {
      alert(`✓ ${d.message}`);
      await loadCounties();
      await loadStats();
      await loadAgents();
    } else {
      alert(`Upload error: ${d.message}`);
    }
  } catch (err) {
    alert("Upload failed: " + err.message);
  } finally {
    inputEl.value = "";
    if (labelEl && origText) {
      labelEl.innerHTML = origText;
    }
  }
}

// Settings Handlers
function setPandaDocMode(mode) {
  pandadocSettings.mode = mode;
  const btnSandbox = document.getElementById("btnPandaModeSandbox");
  const btnProd = document.getElementById("btnPandaModeProduction");
  if (btnSandbox && btnProd) {
    btnSandbox.className = mode === "sandbox" ? "px-3 py-1 rounded-lg text-xs font-bold bg-purple-600 text-white cursor-pointer" : "px-3 py-1 rounded-lg text-xs font-semibold text-slate-400 cursor-pointer";
    btnProd.className = mode === "production" ? "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-600 text-white cursor-pointer" : "px-3 py-1 rounded-lg text-xs font-semibold text-slate-400 cursor-pointer";
  }
}

async function testPandaDocConnection() {
  const alertBox = document.getElementById("pandadocSettingsAlert");
  const btn = document.getElementById("btnTestPandadoc");
  if (!alertBox || !btn) return;

  const mode = pandadocSettings.mode || "sandbox";
  const key = mode === "production" 
    ? document.getElementById("pandaProdKey").value.trim() 
    : document.getElementById("pandaSandboxKey").value.trim();

  btn.disabled = true;
  btn.innerHTML = `<span>⏳</span> <span>Testing ${mode.toUpperCase()}...</span>`;
  alertBox.classList.remove("hidden");
  alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700";
  alertBox.innerText = `Connecting to PandaDoc ${mode.toUpperCase()} API...`;

  try {
    const res = await fetch("/api/pandadoc/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: mode, key: key })
    });
    const data = await res.json();
    if (data.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ ${data.message}`;
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${data.message}`;
    }
  } catch (err) {
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>⚡ Test API Key</span>`;
  }
}

async function savePandaDocSettings() {
  pandadocSettings.sandbox_key = document.getElementById("pandaSandboxKey").value;
  pandadocSettings.production_key = document.getElementById("pandaProdKey").value;
  pandadocSettings.buyer_name = document.getElementById("pandaBuyerName").value;
  pandadocSettings.buyer_signer_name = document.getElementById("pandaSignerName").value;
  const tmplInput = document.getElementById("pandaFarbarTemplateId");
  if (tmplInput) pandadocSettings.farbar_template_id = tmplInput.value.trim();

  await fetch("/api/pandadoc/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pandadocSettings)
  });
  updateSettingsUI();
  closeModal("pandadocSettingsModal");
  alert("✓ PandaDoc settings saved!");
}

function setSmsMode(mode) {
  smsSettings.mode = mode;
  document.getElementById("btnSmsModeCloud").className = mode === "cloud" ? "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-600 text-white" : "px-3 py-1 rounded-lg text-xs font-semibold text-slate-400";
  document.getElementById("btnSmsModeLocal").className = mode === "local" ? "px-3 py-1 rounded-lg text-xs font-bold bg-emerald-600 text-white" : "px-3 py-1 rounded-lg text-xs font-semibold text-slate-400";
}

async function saveSmsSettings() {
  smsSettings.base_url = document.getElementById("smsBaseUrl").value;
  smsSettings.username = document.getElementById("smsUser").value;
  smsSettings.password = document.getElementById("smsPass").value;

  await fetch("/api/sms/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(smsSettings)
  });
  closeModal("smsSettingsModal");
  alert("✓ SMS Gateway settings saved!");
}

async function testSmsGatewayConnection() {
  try {
    const res = await fetch("/api/sms/test", { method: "POST" });
    const d = await res.json();
    alert(d.message);
  } catch (err) {
    alert("Connection error: " + err.message);
  }
}

async function saveEmailSettings() {
  emailSettings.smtp_server = document.getElementById("emailHost").value;
  emailSettings.smtp_port = parseInt(document.getElementById("emailPort").value) || 2525;
  emailSettings.smtp_user = document.getElementById("emailUser").value;
  emailSettings.smtp_password = document.getElementById("emailPass").value;
  emailSettings.sender_email = document.getElementById("emailSender").value;
  emailSettings.reply_to = document.getElementById("emailReplyTo").value;

  await fetch("/api/email/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(emailSettings)
  });
  closeModal("emailSettingsModal");
  alert("✓ SMTP2GO Email settings saved!");
}

async function testEmailConnection() {
  try {
    const res = await fetch("/api/email/test", { method: "POST" });
    const d = await res.json();
    alert(d.message);
  } catch (err) {
    alert("Connection error: " + err.message);
  }
}

async function openInboxModal() {
  openModal('inboxModal');
  const container = document.getElementById("inboxFeedContainer");
  container.innerHTML = `<div class="text-center py-8 text-slate-500 text-xs">Loading inbound replies...</div>`;

  try {
    const res = await fetch("/api/inbox");
    const d = await res.json();
    const msgs = d.messages || [];

    const unreadPill = document.getElementById("inboxUnreadPill");
    if (unreadPill) {
      unreadPill.innerText = `${d.unread_count || 0} Unread`;
    }

    if (msgs.length === 0) {
      container.innerHTML = `
        <div class="text-center py-10 space-y-2">
          <div class="text-3xl">📭</div>
          <div class="text-xs text-slate-400 font-medium">No inbound agent replies or messages.</div>
          <div class="text-[11px] text-slate-500 max-w-sm mx-auto">
            Configure your Android SMS Gateway webhook to point to <code class="text-indigo-300 bg-slate-900 px-1.5 py-0.5 rounded font-mono">http://&lt;your-ip&gt;:8001/api/sms/inbound</code> to auto-capture agent text replies!
          </div>
        </div>
      `;
      return;
    }

    container.innerHTML = msgs.map(m => {
      const aid = m.agent_id;
      const isUnknown = !aid || m.agent_name === "Unknown Agent";
      return `
        <div class="bg-slate-900/90 border ${isUnknown ? 'border-slate-800/80 bg-slate-900/50' : 'border-slate-800'} rounded-xl p-3.5 space-y-2.5 transition hover:border-slate-700">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              ${aid ? `
                <span class="font-bold text-white text-xs">${escapeHtml(m.agent_name || 'Agent')}</span>
                <span class="px-1.5 py-0.5 rounded text-[9px] bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">REALTOR</span>
              ` : `
                <span class="font-bold text-slate-300 text-xs">${escapeHtml(m.agent_name || 'Non-Agent')}</span>
                <span class="px-1.5 py-0.5 rounded text-[9px] bg-amber-500/20 text-amber-300 font-bold border border-amber-500/30">⚠️ UNMATCHED / SPAM</span>
              `}
              <span class="font-mono text-emerald-400 text-[11px]">${m.sender_phone || ''}</span>
            </div>
            <span class="font-mono text-[10px] text-slate-500">${m.timestamp}</span>
          </div>

          <p class="text-xs text-slate-200 bg-[#0b1220] p-2.5 rounded-lg border border-slate-800/80 font-medium leading-relaxed">
            "${escapeHtml(m.message)}"
          </p>

          ${m.last_bot_suggestion ? `
            <div class="bg-[#0f172a] border ${m.is_gold_deal ? 'border-amber-500/50 bg-amber-950/20' : 'border-indigo-500/30'} rounded-xl p-3 space-y-2">
              <div class="flex items-center justify-between text-[11px]">
                <span class="font-bold ${m.is_gold_deal ? 'text-amber-300' : 'text-indigo-300'} flex items-center gap-1.5">
                  <span>🤖 Flowchart Copilot Suggestion</span>
                  ${m.is_gold_deal ? '<span class="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 font-extrabold text-[9px] border border-amber-500/30">⭐ THE GOLD</span>' : ''}
                </span>
                <span class="font-mono text-slate-400 text-[10px]">${escapeHtml(m.last_bot_node || '')}</span>
              </div>
              <p class="text-xs text-slate-100 font-sans leading-relaxed bg-[#0b1220] p-2.5 rounded-lg border border-slate-800">
                "${escapeHtml(m.last_bot_suggestion)}"
              </p>
              <div class="flex items-center justify-end gap-2 pt-0.5">
                <button type="button" onclick="approveBotReplyFromInbox('${aid}')" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold shadow-md shadow-emerald-600/30 transition flex items-center gap-1.5 cursor-pointer">
                  <span>🚀 1-Click Approve & Send</span>
                </button>
              </div>
            </div>
          ` : ''}

          <div class="flex items-center justify-between pt-1 border-t border-slate-800/50">
            <span class="text-[10px] text-slate-500">Android SMS Gateway</span>
            <div class="flex items-center gap-1.5">
              ${aid ? `
                <button type="button" onclick="closeModal('inboxModal'); openAgentDrawer('${aid}'); markInboxRead('${aid}')" class="px-2.5 py-1 rounded-lg bg-indigo-600/20 hover:bg-indigo-600/40 text-indigo-300 text-[11px] font-bold border border-indigo-500/30 transition cursor-pointer">
                  📂 Open Drawer
                </button>
                <button type="button" onclick="closeModal('inboxModal'); openSmsModal('${aid}'); markInboxRead('${aid}')" class="px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-bold transition flex items-center gap-1 cursor-pointer">
                  💬 Reply via SMS
                </button>
                <button type="button" onclick="closeModal('inboxModal'); openNegotiationHud('${aid}'); markInboxRead('${aid}')" class="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 text-[11px] font-bold border border-amber-500/30 transition cursor-pointer">
                  📞 Setup Call HUD
                </button>
              ` : ''}
              <button type="button" onclick="deleteInboxMessage('${escapeHtml(m.id || '')}', '${escapeHtml(m.timestamp || '')}', '${escapeHtml(m.sender_phone || '')}', this)" class="px-2.5 py-1 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 text-[11px] font-semibold transition cursor-pointer flex items-center gap-1" title="Delete message">
                🗑️ Delete
              </button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    container.innerHTML = `<div class="p-3 text-xs text-red-400">Error loading inbox: ${err.message}</div>`;
  }
}

async function deleteInboxMessage(msgId, timestamp, senderPhone, btnEl = null) {
  if (!confirm("Are you sure you want to delete this message?")) {
    return;
  }
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.innerText = "Deleting...";
  }
  try {
    const res = await fetch("/api/inbox/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id: msgId, timestamp: timestamp, sender_phone: senderPhone })
    });
    const d = await res.json();
    if (d.status === "success") {
      await openInboxModal();
      loadStats();
      loadAgents();
    } else {
      alert("Error deleting message: " + (d.message || "Failed"));
      if (btnEl) {
        btnEl.disabled = false;
        btnEl.innerHTML = "🗑️ Delete";
      }
    }
  } catch (err) {
    alert("Network error: " + err.message);
    if (btnEl) {
      btnEl.disabled = false;
      btnEl.innerHTML = "🗑️ Delete";
    }
  }
}

async function confirmClearSpamInbox() {
  if (!confirm("Are you sure you want to delete all spam, bank codes, and non-agent messages? This will keep only texts from registered agents.")) {
    return;
  }
  const alertBox = document.getElementById("inboxModalAlert");
  const btn = document.getElementById("btnClearSpamInbox");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Clearing...";
  }
  try {
    const res = await fetch("/api/inbox/clear-spam", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    const d = await res.json();
    if (alertBox) {
      alertBox.classList.remove("hidden");
      alertBox.className = "px-4 py-2 mx-6 mt-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ ${d.message || 'Spam messages cleared'}`;
      setTimeout(() => alertBox.classList.add("hidden"), 3500);
    }
    await openInboxModal();
    loadStats();
    loadAgents();
  } catch (err) {
    alert("Error clearing spam: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `<span>🧹 Clear Spam / Non-Agent</span>`;
    }
  }
}

async function markInboxRead(agentId) {
  try {
    await fetch(`/api/inbox/read/${agentId}`, { method: "POST" });
    loadStats();
    loadAgents();
  } catch (e) {}
}

// Helpers
function openModal(id) {
  document.getElementById(id).classList.remove("hidden");
}

function closeModal(id) {
  document.getElementById(id).classList.add("hidden");
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// --- Live Test Handlers (SMS Outbound & SMTP2GO) ---
async function sendTestSms() {
  const phone = document.getElementById("smsTestPhone").value.trim();
  const message = document.getElementById("smsTestMessage").value.trim();
  const alertBox = document.getElementById("smsTestAlert");
  const btn = document.getElementById("btnSendTestSms");

  if (!phone) {
    alert("Please enter a test cell phone number.");
    return;
  }

  btn.disabled = true;
  btn.innerText = "Dispatching Test SMS via Android Gateway...";
  alertBox.classList.add("hidden");

  try {
    const res = await fetch("/api/sms/test-send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, message })
    });
    const d = await res.json();
    alertBox.classList.remove("hidden");
    if (d.status === "success") {
      alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ Test SMS successfully dispatched to ${d.phone || phone}! Check your phone.`;
    } else {
      alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${d.message}`;
    }
  } catch (err) {
    alertBox.classList.remove("hidden");
    alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Connection error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Dispatch Test SMS to My Phone";
  }
}

async function sendTestEmail() {
  const recipient = document.getElementById("emailTestRecipient").value.trim();
  const subject = document.getElementById("emailTestSubject").value.trim();
  const alertBox = document.getElementById("emailTestAlert");
  const btn = document.getElementById("btnSendTestEmail");

  if (!recipient) {
    alert("Please enter a recipient email address.");
    return;
  }

  btn.disabled = true;
  btn.innerText = "Sending Test Email via SMTP2GO...";
  alertBox.classList.add("hidden");

  try {
    const res = await fetch("/api/email/test-send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_email: recipient, subject })
    });
    const d = await res.json();
    alertBox.classList.remove("hidden");
    if (d.status === "success") {
      alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-cyan-500/20 text-cyan-300 border border-cyan-500/30";
      alertBox.innerText = `✓ ${d.message} Check your inbox.`;
    } else {
      alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${d.message}`;
    }
  } catch (err) {
    alertBox.classList.remove("hidden");
    alertBox.className = "p-2.5 rounded-lg text-[11px] font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "🚀 Dispatch Test Email to My Inbox";
  }
}

// --- Inbound SMS Simulator Handlers ---
function openSimulateInboundModal() {
  const sel = document.getElementById("simInboundAgentSelect");
  sel.innerHTML = "";

  const customOpt = document.createElement("option");
  customOpt.value = "custom";
  customOpt.textContent = "⚙️ Custom / Manual Phone Number";
  sel.appendChild(customOpt);

  allAgents.forEach(a => {
    const opt = document.createElement("option");
    opt.value = a.agent_id;
    opt.textContent = `👤 ${a.full_name} (${a.phone || 'No phone'}) - ${a.brokerage}`;
    sel.appendChild(opt);
  });

  if (allAgents.length > 0) {
    sel.value = allAgents[0].agent_id;
    document.getElementById("simInboundPhone").value = allAgents[0].phone || "";
  } else {
    document.getElementById("simInboundPhone").value = "";
  }

  document.getElementById("simInboundAlert").classList.add("hidden");
  openModal("simulateInboundModal");
}

function handleSimAgentSelectChange(aid) {
  if (aid === "custom") {
    document.getElementById("simInboundPhone").value = "";
    document.getElementById("simInboundPhone").focus();
  } else {
    const agent = allAgents.find(a => a.agent_id === aid);
    if (agent) {
      document.getElementById("simInboundPhone").value = agent.phone || "";
    }
  }
}

async function handleSimulateInboundSubmit(e) {
  e.preventDefault();
  const phone = document.getElementById("simInboundPhone").value.trim();
  const message = document.getElementById("simInboundMessage").value.trim();
  const alertBox = document.getElementById("simInboundAlert");
  const btn = document.getElementById("btnSimulateInbound");

  btn.disabled = true;
  btn.innerText = "Simulating Inbound Webhook...";
  alertBox.classList.add("hidden");

  try {
    const res = await fetch("/api/sms/simulate-inbound", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone, message })
    });
    const d = await res.json();
    alertBox.classList.remove("hidden");
    if (d.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      const matchedName = d.agent ? d.agent.full_name : "Unmatched Phone";
      alertBox.innerHTML = `✓ Inbound text received!<br>Matched: <strong>${escapeHtml(matchedName)}</strong><br>Stage moved to <em>Warm / In Discussion</em> &amp; Unread Feed updated.`;
      
      await loadStats();
      await loadAgents();

      setTimeout(() => {
        closeModal("simulateInboundModal");
        openInboxModal();
      }, 1600);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${d.message}`;
    }
  } catch (err) {
    alertBox.classList.remove("hidden");
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "⚡ Trigger Inbound Text";
  }
}

// --- Add Sandbox Test Agent Handlers ---
function openAddAgentModal() {
  document.getElementById("addAgentAlert").classList.add("hidden");
  openModal("addAgentModal");
}

async function handleCreateAgentSubmit(e) {
  e.preventDefault();
  const alertBox = document.getElementById("addAgentAlert");
  const btn = document.getElementById("btnCreateAgent");

  const payload = {
    full_name: document.getElementById("createAgentName").value.trim(),
    brokerage: document.getElementById("createAgentBrokerage").value.trim(),
    phone: document.getElementById("createAgentPhone").value.trim(),
    email: document.getElementById("createAgentEmail").value.trim(),
    address: document.getElementById("createAgentAddress").value.trim(),
    city: document.getElementById("createAgentCity").value.trim(),
    county: document.getElementById("createAgentCounty").value.trim().toUpperCase(),
    listing_price: parseFloat(document.getElementById("createAgentPrice").value) || 275000,
    days_on_market: parseInt(document.getElementById("createAgentDom").value) || 14,
    notes: document.getElementById("createAgentNotes").value.trim()
  };

  btn.disabled = true;
  btn.innerText = "Creating Sandbox Agent...";
  alertBox.classList.add("hidden");

  try {
    const res = await fetch("/api/agent/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    alertBox.classList.remove("hidden");
    if (d.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ Sandbox Agent created! Added to your pipeline.`;
      
      await loadCounties();
      await loadStats();
      await loadAgents();

      setTimeout(() => {
        closeModal("addAgentModal");
      }, 1200);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${d.message}`;
    }
  } catch (err) {
    alertBox.classList.remove("hidden");
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "➕ Create Test Agent";
  }
}

// --- Edit Agent Handlers ---
function openEditAgentModal(agentId) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;

  selectedAgent = agent;
  document.getElementById("editAgentId").value = agent.agent_id;
  document.getElementById("editAgentFullName").value = agent.full_name || "";
  document.getElementById("editAgentBrokerage").value = agent.brokerage || "";
  document.getElementById("editAgentPhone").value = agent.phone || "";
  document.getElementById("editAgentEmail").value = agent.email || "";
  document.getElementById("editAgentAddress").value = agent.primary_address || "";
  document.getElementById("editAgentCity").value = agent.primary_city || "";
  document.getElementById("editAgentPrice").value = agent.primary_price || "";
  document.getElementById("editAgentStage").value = agent.pipeline_stage || "New Ingest";
  document.getElementById("editAgentNotes").value = agent.notes || "";

  const delBtn = document.getElementById("btnDeleteCustomAgent");
  if (agent.is_custom || (agent.tier && agent.tier.includes("Test"))) {
    delBtn.classList.remove("hidden");
  } else {
    delBtn.classList.add("hidden");
  }

  document.getElementById("editAgentAlert").classList.add("hidden");
  openModal("editAgentModal");
}

function editAgentFromDrawer() {
  if (selectedAgent) {
    closeAgentDrawer();
    openEditAgentModal(selectedAgent.agent_id);
  }
}

async function handleEditAgentSubmit(e) {
  e.preventDefault();
  const aid = document.getElementById("editAgentId").value;
  const alertBox = document.getElementById("editAgentAlert");
  const btn = document.getElementById("btnSaveAgentEdit");

  const payload = {
    full_name: document.getElementById("editAgentFullName").value.trim(),
    brokerage: document.getElementById("editAgentBrokerage").value.trim(),
    phone: document.getElementById("editAgentPhone").value.trim(),
    email: document.getElementById("editAgentEmail").value.trim(),
    primary_address: document.getElementById("editAgentAddress").value.trim(),
    primary_city: document.getElementById("editAgentCity").value.trim(),
    primary_price: parseFloat(document.getElementById("editAgentPrice").value) || 0,
    pipeline_stage: document.getElementById("editAgentStage").value,
    notes: document.getElementById("editAgentNotes").value.trim()
  };

  btn.disabled = true;
  btn.innerText = "Saving Changes...";
  alertBox.classList.add("hidden");

  try {
    const res = await fetch(`/api/agent/${aid}/edit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    alertBox.classList.remove("hidden");
    if (d.status === "success") {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertBox.innerText = `✓ Agent updated successfully!`;

      await loadStats();
      await loadAgents();

      setTimeout(() => {
        closeModal("editAgentModal");
      }, 1000);
    } else {
      alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
      alertBox.innerText = `Error: ${d.message}`;
    }
  } catch (err) {
    alertBox.classList.remove("hidden");
    alertBox.className = "p-3 rounded-xl text-xs font-semibold bg-red-500/20 text-red-300 border border-red-500/30";
    alertBox.innerText = `Network error: ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerText = "✓ Save Agent";
  }
}

async function deleteCurrentAgent() {
  const aid = document.getElementById("editAgentId").value;
  if (!aid) return;
  if (!confirm("Are you sure you want to delete this agent from your database?")) return;

  try {
    const res = await fetch(`/api/agent/${aid}`, { method: "DELETE" });
    const d = await res.json();
    if (d.status === "success") {
      closeModal("editAgentModal");
      await loadStats();
      await loadAgents();
      alert("✓ Agent deleted.");
    } else {
      alert("Error: " + d.message);
    }
  } catch (err) {
    alert("Delete failed: " + err.message);
  }
}

// ==========================================
// --- LOI DEAL ANALYZER & CALCULATOR ---
// ==========================================
let activeLoiRule = '75';
let activeRehabTier = 'medium';

function openLoiAnalyzer(agentId, propertyAddress = null, listPrice = null, sqft = null, beds = null, baths = null, yearBuilt = null) {
  const agent = allAgents.find(a => a.agent_id === agentId);
  if (!agent) return;
  selectedAgent = agent;

  const prim = (agent.listings && agent.listings[0]) || {};
  const addr = propertyAddress || prim.address || agent.primary_address || "Florida Property";
  const price = (listPrice !== null && listPrice !== undefined) ? Number(listPrice) : (Number(prim.listing_price) || Number(agent.primary_price) || 250000);
  const sq = (sqft !== null && sqft !== undefined) ? Number(sqft) : (Number(prim.sqft) || 1500);
  const b = (beds !== null && beds !== undefined) ? beds : (prim.beds || 3);
  const ba = (baths !== null && baths !== undefined) ? baths : (prim.baths || 2);
  const yb = (yearBuilt !== null && yearBuilt !== undefined) ? yearBuilt : (prim.year_built || 1985);
  const estimatedArv = prim.estimated_value || Math.round(price * 1.15) || 275000;

  document.getElementById("loiAgentId").value = agent.agent_id;
  document.getElementById("loiPropertyAddress").value = addr;
  document.getElementById("loiAgentEmail").value = agent.email || "";
  document.getElementById("loiAgentPhone").value = agent.phone || "";

  document.getElementById("loiPropertySubtitle").innerText = `Comp analysis & instant offer calculation for ${agent.full_name || 'Agent'}`;
  document.getElementById("loiDisplayAddress").innerText = `📍 ${addr}${agent.primary_city ? ', ' + agent.primary_city : ''}`;
  document.getElementById("loiDisplaySpecs").innerText = `${b} Beds • ${ba} Baths • ${sq.toLocaleString()} sqft • Built ${yb}`;
  document.getElementById("loiDisplayListPrice").innerText = `$${Math.round(price).toLocaleString()}`;

  document.getElementById("loiArvInput").value = estimatedArv;
  document.getElementById("loiSqftInput").value = sq;

  // Initialize with Medium rehab tier ($35/sqft) and 75% Rule
  setRehabTier('medium');
  setLoiRule('75');

  openModal("loiAnalyzerModal");
}

function setRehabTier(tier) {
  activeRehabTier = tier;
  let rate = 35;
  if (tier === 'light') rate = 20;
  if (tier === 'medium') rate = 35;
  if (tier === 'heavy') rate = 55;

  const slider = document.getElementById("loiRehabSlider");
  if (slider) slider.value = rate;

  updateRehabTierStyles(tier, rate);
  updateRehabTotalFromRate(rate);
  recalculateLoiDeal();
}

function updateRehabTierStyles(tier, rate) {
  const btnLight = document.getElementById("btnRehabLight");
  const btnMed = document.getElementById("btnRehabMedium");
  const btnHeavy = document.getElementById("btnRehabHeavy");
  const rateDisplay = document.getElementById("loiRehabRateDisplay");

  if (rateDisplay) rateDisplay.innerText = `$${rate} / sqft`;

  if (btnLight) {
    btnLight.className = tier === 'light'
      ? "py-2 px-2.5 rounded-lg text-xs font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 transition text-center cursor-pointer shadow"
      : "py-2 px-2.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 hover:border-emerald-500/50 transition text-center cursor-pointer";
  }
  if (btnMed) {
    btnMed.className = tier === 'medium'
      ? "py-2 px-2.5 rounded-lg text-xs font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 transition text-center cursor-pointer shadow"
      : "py-2 px-2.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 hover:border-amber-500/50 transition text-center cursor-pointer";
  }
  if (btnHeavy) {
    btnHeavy.className = tier === 'heavy'
      ? "py-2 px-2.5 rounded-lg text-xs font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40 transition text-center cursor-pointer shadow"
      : "py-2 px-2.5 rounded-lg text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700 hover:border-rose-500/50 transition text-center cursor-pointer";
  }
}

function handleRehabSliderChange(rateVal) {
  const rate = Number(rateVal) || 35;
  let matchedTier = 'custom';
  if (rate <= 25) matchedTier = 'light';
  else if (rate <= 45) matchedTier = 'medium';
  else matchedTier = 'heavy';

  activeRehabTier = matchedTier;
  updateRehabTierStyles(matchedTier, rate);
  updateRehabTotalFromRate(rate);
  recalculateLoiDeal();
}

function updateRehabTotalFromRate(rate) {
  const sqft = Number(document.getElementById("loiSqftInput").value) || 1500;
  const total = Math.round(sqft * rate);
  const totalInput = document.getElementById("loiTotalRehabInput");
  if (totalInput) totalInput.value = total;
}

function handleRehabTotalChange(totalVal) {
  const total = Number(totalVal) || 0;
  const sqft = Number(document.getElementById("loiSqftInput").value) || 1500;
  const rate = sqft > 0 ? Math.round(total / sqft) : 35;

  const slider = document.getElementById("loiRehabSlider");
  if (slider) slider.value = Math.min(80, Math.max(10, rate));

  const rateDisplay = document.getElementById("loiRehabRateDisplay");
  if (rateDisplay) rateDisplay.innerText = `$${rate} / sqft`;

  recalculateLoiDeal();
}

function setLoiRule(rule) {
  activeLoiRule = rule;
  const btn70 = document.getElementById("btnRule70");
  const btn75 = document.getElementById("btnRule75");
  const btnMargin = document.getElementById("btnRuleMargin");

  if (btn70) btn70.className = rule === '70' ? "py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white transition cursor-pointer shadow" : "py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";
  if (btn75) btn75.className = rule === '75' ? "py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white transition cursor-pointer shadow" : "py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";
  if (btnMargin) btnMargin.className = rule === 'margin' ? "py-1.5 rounded-lg text-xs font-bold bg-indigo-600 text-white transition cursor-pointer shadow" : "py-1.5 rounded-lg text-xs font-semibold text-slate-400 hover:text-white transition cursor-pointer";

  recalculateLoiDeal();
}

function recalculateLoiDeal() {
  const arv = Number(document.getElementById("loiArvInput")?.value) || 0;
  const rehab = Number(document.getElementById("loiTotalRehabInput")?.value) || 0;

  let ruleMultiplier = 0.75;
  if (activeLoiRule === '70') ruleMultiplier = 0.70;
  else if (activeLoiRule === 'margin') ruleMultiplier = 0.77;

  const calculatedOffer = Math.max(0, Math.round((arv * ruleMultiplier) - rehab));

  const offerEl = document.getElementById("loiCalculatedOffer");
  const explEl = document.getElementById("loiOfferExplanation");
  const scriptEl = document.getElementById("loiScriptPreview");

  if (offerEl) offerEl.innerText = `$${calculatedOffer.toLocaleString()}`;
  if (explEl) explEl.innerText = `Formula: (${Math.round(ruleMultiplier * 100)}% of $${Math.round(arv).toLocaleString()} ARV) - $${Math.round(rehab).toLocaleString()} Repairs`;

  if (scriptEl) {
    scriptEl.innerText = `"With fully renovated comps around $${Math.round(arv).toLocaleString()} and roughly $${Math.round(rehab).toLocaleString()} in needed work, I’m at $${calculatedOffer.toLocaleString()} cash, as-is, 5-day inspection, 21-day close, and we cover standard buyer closing costs."`;
  }
}

function dispatchLoiSmsFromAnalyzer() {
  const agentId = document.getElementById("loiAgentId").value;
  const address = document.getElementById("loiPropertyAddress").value;
  const offerAmount = parseInt(document.getElementById("loiCalculatedOffer").innerText.replace(/[^0-9]/g, "")) || 0;
  const arv = parseFloat(document.getElementById("loiArvInput").value) || 0;
  const repairs = parseFloat(document.getElementById("loiTotalRehabInput").value) || 0;

  closeModal("loiAnalyzerModal");
  openSmsModal(agentId, {
    template: "loi_offer",
    address: address,
    offerAmount: offerAmount,
    arv: arv,
    repairs: repairs
  });
}

function dispatchLoiEmailFromAnalyzer() {
  const agentId = document.getElementById("loiAgentId").value;
  const address = document.getElementById("loiPropertyAddress").value;
  const offerAmount = parseInt(document.getElementById("loiCalculatedOffer").innerText.replace(/[^0-9]/g, "")) || 0;
  const arv = parseFloat(document.getElementById("loiArvInput").value) || 0;
  const repairs = parseFloat(document.getElementById("loiTotalRehabInput").value) || 0;
  const email = document.getElementById("loiAgentEmail").value;

  closeModal("loiAnalyzerModal");
  openEmailModal(agentId, {
    template: "loi_offer",
    address: address,
    offerAmount: offerAmount,
    arv: arv,
    repairs: repairs,
    recipientEmail: email
  });
}

async function downloadLoiPdfFromAnalyzer() {
  const agentId = document.getElementById("loiAgentId").value;
  const address = document.getElementById("loiPropertyAddress").value;
  const offerAmount = parseInt(document.getElementById("loiCalculatedOffer").innerText.replace(/[^0-9]/g, "")) || 0;
  const email = document.getElementById("loiAgentEmail").value || "investor@407flips.com";

  const btn = document.querySelector("button[onclick='downloadLoiPdfFromAnalyzer()']");
  const originalHtml = btn ? btn.innerHTML : "<span>📄 Download 1-Page LOI PDF</span>";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Generating LOI PDF...</span>`;
  }

  const payload = {
    agent_id: agentId,
    contract_type: "loi",
    property_address: address,
    recipient_email: email,
    purchase_price: offerAmount,
    escrow_deposit: Math.round(offerAmount * 0.01),
    inspection_days: 5,
    closing_days: 21,
    buyer_name: "Peak Investments LLC"
  };

  try {
    const res = await fetch("/api/contract/pdf", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      let msg = "PDF rendering failed";
      try {
        const err = await res.json();
        if (err.detail) msg = err.detail;
      } catch (_) {}
      throw new Error(msg);
    }
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const safeName = (payload.property_address || "LOI").replace(/[^a-zA-Z0-9_-]/g, "_");
    const a = document.createElement("a");
    a.href = url;
    a.download = `LOI_${safeName}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => window.URL.revokeObjectURL(url), 2000);
  } catch (err) {
    alert("Error downloading LOI PDF: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = originalHtml;
    }
  }
}

// =========================================================================
// TRIPLE-DESK ACQUISITION ENGINE: BROOKE (OFF-MARKET) / LAUREN (FIXERS) / LANA (INFILL LAND)
// =========================================================================

function switchDesk(desk) {
  currentDesk = desk;
  const btnBrooke = document.getElementById("btnDeskBrooke");
  const btnLauren = document.getElementById("btnDeskLauren");
  const btnLana = document.getElementById("btnDeskLana");
  const brookeView = document.getElementById("brookeDeskView");
  const laurenView = document.getElementById("laurenDeskView");
  const lanaView = document.getElementById("lanaDeskView");
  const personaBadge = document.getElementById("activePersonaBadge");

  const unselectedCls = "px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 text-slate-400 hover:text-white cursor-pointer";
  if (btnBrooke) btnBrooke.className = unselectedCls;
  if (btnLauren) btnLauren.className = unselectedCls;
  if (btnLana) btnLana.className = unselectedCls;

  if (brookeView) brookeView.classList.add("hidden");
  if (laurenView) laurenView.classList.add("hidden");
  if (lanaView) lanaView.classList.add("hidden");

  if (desk === "BROOKE") {
    if (btnBrooke) {
      btnBrooke.className = "px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-indigo-600 text-white shadow-lg shadow-indigo-600/30 cursor-pointer";
    }
    if (brookeView) brookeView.classList.remove("hidden");
    if (personaBadge) {
      personaBadge.className = "px-3 py-1 rounded-xl bg-indigo-500/10 text-indigo-300 border border-indigo-500/30 text-xs font-bold flex items-center gap-1.5";
      personaBadge.innerHTML = `<span>🌿 Brooke</span> <span class="text-slate-400 font-normal">&bull; Off-Market Lead Scout</span>`;
    }
  } else if (desk === "LAUREN") {
    if (btnLauren) {
      btnLauren.className = "px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-amber-600 text-white shadow-lg shadow-amber-600/30 cursor-pointer";
    }
    if (laurenView) laurenView.classList.remove("hidden");
    if (personaBadge) {
      personaBadge.className = "px-3 py-1 rounded-xl bg-amber-500/10 text-amber-300 border border-amber-500/30 text-xs font-bold flex items-center gap-1.5";
      personaBadge.innerHTML = `<span>🔨 Lauren</span> <span class="text-slate-400 font-normal">&bull; Trojan Horse Fixer Underwriter</span>`;
    }
    loadFixers();
  } else if (desk === "LANA") {
    if (btnLana) {
      btnLana.className = "px-4 py-2 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-emerald-600 text-white shadow-lg shadow-emerald-600/30 cursor-pointer";
    }
    if (lanaView) lanaView.classList.remove("hidden");
    if (personaBadge) {
      personaBadge.className = "px-3 py-1 rounded-xl bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 text-xs font-bold flex items-center gap-1.5";
      personaBadge.innerHTML = `<span>📐 Lana</span> <span class="text-slate-400 font-normal">&bull; On-Market Infill Land Specialist</span>`;
    }
    loadLots();
  }
}

async function loadFixers() {
  try {
    const res = await fetch("/api/fixers");
    if (!res.ok) throw new Error("Failed to load fixers");
    allFixers = await res.json();

    // Top switcher badge
    const headerBadge = document.getElementById("headerLaurenBadge");
    if (headerBadge) headerBadge.innerText = allFixers.length;

    // Metrics ribbon
    const statCount = document.getElementById("statFixersCount");
    if (statCount) statCount.innerText = allFixers.length;

    let totalArv = 0;
    let totalMao = 0;
    let loisCount = 0;

    allFixers.forEach(f => {
      const arv = (f.underwriting && f.underwriting.arv) || f.redfin_estimate || f.list_price || 0;
      const mao = (f.underwriting && f.underwriting.offer_price) || 0;
      totalArv += arv;
      totalMao += mao;
      if (f.standing_loi_sent) loisCount++;
    });

    const statAvgArv = document.getElementById("statFixersAvgArv");
    if (statAvgArv) {
      statAvgArv.innerText = allFixers.length > 0 ? `$${Math.round(totalArv / allFixers.length).toLocaleString()}` : "$0";
    }

    const statAvgMao = document.getElementById("statFixersAvgMao");
    if (statAvgMao) {
      statAvgMao.innerText = allFixers.length > 0 ? `$${Math.round(totalMao / allFixers.length).toLocaleString()}` : "$0";
    }

    const statLois = document.getElementById("statFixersLoiSent");
    if (statLois) statLois.innerText = loisCount;

    populateFixerFilterDropdowns();
    filterFixersList();
  } catch (err) {
    console.error("Error loading fixers:", err);
  }
}

function populateFixerFilterDropdowns() {
  const countySel = document.getElementById("fixerCountyFilter");
  if (countySel) {
    const currentCountyVal = countySel.value || "ALL";
    const counties = [...new Set(allFixers.map(f => (f.county || "").toUpperCase().trim()).filter(Boolean))].sort();
    let countyHtml = `<option value="ALL">All Counties</option>`;
    counties.forEach(c => {
      const selected = c === currentCountyVal ? "selected" : "";
      countyHtml += `<option value="${escapeHtml(c)}" ${selected}>${escapeHtml(c)}</option>`;
    });
    countySel.innerHTML = countyHtml;
  }

  populateFixerCityDropdown();
}

function populateFixerCityDropdown() {
  const countySel = document.getElementById("fixerCountyFilter");
  const citySel = document.getElementById("fixerCityFilter");
  if (!citySel) return;

  const currentCountyVal = countySel ? countySel.value : "ALL";
  const currentCityVal = citySel.value || "ALL";

  let eligibleFixers = allFixers;
  if (currentCountyVal !== "ALL") {
    eligibleFixers = allFixers.filter(f => (f.county || "").toUpperCase().trim() === currentCountyVal);
  }

  const cities = [...new Set(eligibleFixers.map(f => (f.city || "").trim()).filter(Boolean))].sort();
  let cityHtml = `<option value="ALL">All Cities</option>`;
  cities.forEach(c => {
    const selected = c.toLowerCase() === currentCityVal.toLowerCase() ? "selected" : "";
    cityHtml += `<option value="${escapeHtml(c)}" ${selected}>${escapeHtml(c)}</option>`;
  });
  citySel.innerHTML = cityHtml;
}

function handleFixerCountyFilterChange() {
  populateFixerCityDropdown();
  filterFixersList();
}

function isFixerContacted(f) {
  const hasMessages = Array.isArray(f.messages) && f.messages.length > 0;
  const isOutreachStatus = f.status && !["NEW", "SCRAPED", ""].includes(f.status.toUpperCase());
  return hasMessages || isOutreachStatus || !!f.standing_loi_sent;
}

function hasFixerReplies(f) {
  return Array.isArray(f.messages) && f.messages.some(m => (m.direction || "").toUpperCase() === "INBOUND");
}

function filterFixersList() {
  const searchInput = document.getElementById("fixerSearchInput");
  const query = searchInput ? searchInput.value.toLowerCase().trim() : "";
  const contactFilter = document.getElementById("fixerContactFilter") ? document.getElementById("fixerContactFilter").value : "ALL";
  const countyFilter = document.getElementById("fixerCountyFilter") ? document.getElementById("fixerCountyFilter").value : "ALL";
  const cityFilter = document.getElementById("fixerCityFilter") ? document.getElementById("fixerCityFilter").value : "ALL";

  const isFiltered = query !== "" || contactFilter !== "ALL" || countyFilter !== "ALL" || cityFilter !== "ALL";

  const resetBtn = document.getElementById("btnResetFixerFilters");
  if (resetBtn) {
    if (isFiltered) resetBtn.classList.remove("hidden");
    else resetBtn.classList.add("hidden");
  }

  const filteredBadge = document.getElementById("fixerFilteredBadge");
  if (filteredBadge) {
    if (isFiltered) filteredBadge.classList.remove("hidden");
    else filteredBadge.classList.add("hidden");
  }

  filteredFixers = allFixers.filter(f => {
    // 1. Text search
    if (query) {
      const addr = (f.address || "").toLowerCase();
      const city = (f.city || "").toLowerCase();
      const county = (f.county || "").toLowerCase();
      const agent = (f.agent_name || "").toLowerCase();
      const brokerage = (f.brokerage || "").toLowerCase();
      const remarks = (f.remarks || "").toLowerCase();
      const status = (f.status || "").toLowerCase();
      const matchesQuery = addr.includes(query) || city.includes(query) || county.includes(query) || agent.includes(query) || brokerage.includes(query) || remarks.includes(query) || status.includes(query);
      if (!matchesQuery) return false;
    }

    // 2. Contact Status Filter
    if (contactFilter === "CONTACTED") {
      if (!isFixerContacted(f)) return false;
    } else if (contactFilter === "UNCONTACTED") {
      if (isFixerContacted(f)) return false;
    } else if (contactFilter === "REPLIED") {
      if (!hasFixerReplies(f)) return false;
    } else if (contactFilter === "LOI_SENT") {
      if (!f.standing_loi_sent && (f.status || "").toUpperCase() !== "STANDING_LOI_SENT") return false;
    }

    // 3. County Filter
    if (countyFilter !== "ALL") {
      const fCounty = (f.county || "").toUpperCase().trim();
      if (fCounty !== countyFilter.toUpperCase().trim()) return false;
    }

    // 4. City Filter
    if (cityFilter !== "ALL") {
      const fCity = (f.city || "").toLowerCase().trim();
      if (fCity !== cityFilter.toLowerCase().trim()) return false;
    }

    return true;
  });

  const countDisplay = document.getElementById("fixerCountDisplay");
  if (countDisplay) {
    if (isFiltered) {
      countDisplay.innerHTML = `<span class="text-amber-300 font-bold">Showing ${filteredFixers.length}</span> of ${allFixers.length} fixer listings`;
    } else {
      countDisplay.innerText = `Showing ${filteredFixers.length} of ${allFixers.length} fixer listings`;
    }
  }

  renderFixers(filteredFixers);
}

function resetFixerFilters() {
  const searchInput = document.getElementById("fixerSearchInput");
  if (searchInput) searchInput.value = "";
  const contactFilter = document.getElementById("fixerContactFilter");
  if (contactFilter) contactFilter.value = "ALL";
  const countyFilter = document.getElementById("fixerCountyFilter");
  if (countyFilter) countyFilter.value = "ALL";
  populateFixerCityDropdown();
  const cityFilter = document.getElementById("fixerCityFilter");
  if (cityFilter) cityFilter.value = "ALL";
  filterFixersList();
}

const expandedFixerIds = new Set();

function toggleFixerCard(fixerId) {
  const detailsEl = document.getElementById(`fixer_details_${fixerId}`);
  const btnEl = document.getElementById(`btn_chevron_${fixerId}`);
  if (!detailsEl) return;
  const isHidden = detailsEl.classList.contains("hidden");
  if (isHidden) {
    detailsEl.classList.remove("hidden");
    expandedFixerIds.add(fixerId);
    if (btnEl) btnEl.innerHTML = `<span>▲ Collapse</span>`;
  } else {
    detailsEl.classList.add("hidden");
    expandedFixerIds.delete(fixerId);
    if (btnEl) btnEl.innerHTML = `<span>▼ Details</span>`;
  }
}

function toggleAllFixerCards() {
  const container = document.getElementById("fixersContainer");
  if (!container) return;
  const detailPanels = container.querySelectorAll('[id^="fixer_details_"]');
  if (detailPanels.length === 0) return;

  let anyHidden = false;
  detailPanels.forEach(p => {
    if (p.classList.contains("hidden")) anyHidden = true;
  });

  detailPanels.forEach(p => {
    const id = p.id.replace("fixer_details_", "");
    const btnEl = document.getElementById(`btn_chevron_${id}`);
    if (anyHidden) {
      p.classList.remove("hidden");
      expandedFixerIds.add(id);
      if (btnEl) btnEl.innerHTML = `<span>▲ Collapse</span>`;
    } else {
      p.classList.add("hidden");
      expandedFixerIds.delete(id);
      if (btnEl) btnEl.innerHTML = `<span>▼ Details</span>`;
    }
  });

  const btnAll = document.getElementById("btnToggleAllFixers");
  if (btnAll) {
    btnAll.innerHTML = anyHidden ? `<span>⛶ Collapse All</span>` : `<span>⛶ Expand All</span>`;
  }
}

function renderFixers(fixers) {
  const container = document.getElementById("fixersContainer");
  if (!container) return;

  if (!fixers || fixers.length === 0) {
    container.innerHTML = `
      <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-12 text-center space-y-4">
        <div class="w-16 h-16 rounded-2xl bg-amber-500/10 text-amber-400 border border-amber-500/20 text-3xl flex items-center justify-center mx-auto">
          🔨
        </div>
        <div class="max-w-md mx-auto space-y-1">
          <h4 class="text-base font-bold text-white">No On-Market Redfin Fixers Yet</h4>
          <p class="text-xs text-slate-400">
            Open any fixer listing on Redfin.com, click your <strong>407 Flips Chrome Extension</strong>, and push the deal straight to Lauren's Desk!
          </p>
        </div>
        <div>
          <button type="button" onclick="openModal('chromeExtensionModal')" class="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-bold transition shadow-lg shadow-amber-600/30 cursor-pointer">
            View Chrome Extension Setup Guide &rarr;
          </button>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = fixers.map(f => {
    const uw = f.underwriting || {};
    const arv = uw.arv || f.redfin_estimate || f.list_price || 250000;
    const mao = uw.offer_price || 0;
    const rehabPerSqft = uw.rehab_per_sqft || 40;
    const sqft = f.sqft || 1200;
    const totalRehab = uw.total_rehab || (sqft * rehabPerSqft + (uw.high_ticket_total || 0));
    const totalFees = uw.total_fees || Math.round(arv * 0.09);
    const flipperProfit = uw.flippers_profit || Math.round(arv * 0.15);
    const discountPct = f.list_price ? Math.round(((f.list_price - mao) / f.list_price) * 100) : 0;
    const isExpanded = expandedFixerIds.has(f.id);

    // Status Badge styling
    let statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/30">🆕 NEW</span>`;
    if (f.status === "OUTREACH_SENT") {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">📤 OUTREACH SENT</span>`;
    } else if (f.status === "STANDING_LOI_SENT" || f.standing_loi_sent) {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">📄 STANDING LOI ACTIVE</span>`;
    } else if (f.current_node && f.current_node !== "OPENING_HOOK") {
      statusBadge = `<span class="px-2 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30">💬 SOCRATIC: ${escapeHtml(f.current_node)}</span>`;
    }

    // Socratic Stage indicator
    const socraticStages = [
      { key: "OPENING_HOOK", label: "1. Hook" },
      { key: "ASKED_REPAIR_SCOPE", label: "2. Scope" },
      { key: "ASKED_REPAIR_COST", label: "3. Rehab $" },
      { key: "ASKED_AGENT_ARV", label: "4. Resale ARV" },
      { key: "MATH_PRESENTED", label: "5. Math Drop" }
    ];

    const currentStageKey = f.current_node || "OPENING_HOOK";
    const messages = f.messages || [];
    const currentMsgCount = messages.length;
    const latestInbound = [...messages].reverse().find(m => m.direction === "INBOUND");
    const photoUrl = f.photo_url || "https://images.unsplash.com/photo-1570129477492-45c003edd2be?auto=format&fit=crop&w=600&q=80";

    // Format Remarks with highlighting
    let formattedRemarks = escapeHtml(f.remarks || "No public remarks provided.");
    ["cash", "as-is", "as is", "roof", "hvac", "a/c", "ac", "plumbing", "repairs", "handyman", "tlc"].forEach(kw => {
      const reg = new RegExp(`(${kw})`, "gi");
      formattedRemarks = formattedRemarks.replace(reg, `<span class="bg-amber-500/30 text-amber-200 px-1 rounded font-bold">$1</span>`);
    });

    return `
      <div class="bg-slate-900/90 border border-slate-800 hover:border-slate-700 rounded-2xl shadow-lg transition overflow-hidden" id="fixer_card_${f.id}">
        
        <!-- CARD HEADER & COMPACT SUMMARY BAR (CLICKABLE ACCORDION HEADER) -->
        <div class="p-4 sm:p-5 cursor-pointer flex flex-col lg:flex-row items-start justify-between gap-4 select-none hover:bg-slate-800/30 transition" onclick="toggleFixerCard('${f.id}')">
          
          <div class="flex items-start gap-4 flex-1 min-w-0">
            <!-- Property Thumbnail -->
            <div class="w-20 h-20 sm:w-24 sm:h-24 rounded-xl overflow-hidden border border-slate-700 flex-shrink-0 bg-slate-950 relative">
              <img src="${escapeHtml(photoUrl)}" alt="${escapeHtml(f.address)}" class="w-full h-full object-cover" onerror="this.src='https://images.unsplash.com/photo-1570129477492-45c003edd2be?auto=format&fit=crop&w=600&q=80'">
              <div class="absolute bottom-1 right-1 bg-slate-950/80 px-1.5 py-0.5 rounded text-[9px] font-mono text-slate-300">
                ${f.dom || 0}d DOM
              </div>
            </div>

            <!-- Property Info -->
            <div class="space-y-1.5 flex-1 min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                ${statusBadge}
                <span class="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">${(f.sqft || 0).toLocaleString()} sqft</span>
                ${f.county ? `<span class="text-xs font-mono text-slate-400 bg-slate-800/80 px-2 py-0.5 rounded">${escapeHtml(f.county)}</span>` : ''}
              </div>

              <h3 class="text-base sm:text-lg font-black text-white truncate flex items-center gap-2">
                <span>${escapeHtml(f.address)}</span>
                ${f.redfin_url ? `<a href="${escapeHtml(f.redfin_url)}" target="_blank" onclick="event.stopPropagation()" class="text-xs text-amber-400 hover:underline inline-flex items-center gap-0.5 font-normal"><span>Redfin</span> ↗</a>` : ''}
              </h3>

              <div class="text-xs text-slate-400">
                ${escapeHtml(f.city || '')}${f.zip ? `, FL ${escapeHtml(f.zip)}` : ''}
              </div>

              <!-- Listing Agent Bar -->
              <div class="flex flex-wrap items-center gap-x-3 gap-y-1 pt-0.5 text-xs text-slate-300">
                <span class="font-bold text-amber-300 flex items-center gap-1">
                  <span>👤</span>
                  <span>${escapeHtml(f.agent_name || 'Listing Agent')}</span>
                </span>
                ${f.agent_phone ? `
                  <a href="tel:${escapeHtml(f.agent_phone)}" onclick="event.stopPropagation()" class="text-indigo-400 hover:underline flex items-center gap-1 font-mono">
                    <span>📱</span>
                    <span>${escapeHtml(f.agent_phone)}</span>
                  </a>
                  <button type="button" onclick="event.stopPropagation(); quickEditFixerPhone('${f.id}')" class="text-[10px] text-slate-500 hover:text-indigo-300" title="Edit agent phone">✏️</button>
                  ${f.rerouted_from_phone ? `<span class="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 font-mono">🔀 Re-routed from ${escapeHtml(f.rerouted_from_phone)}</span>` : ''}
                ` : `
                  <div class="flex items-center gap-1.5">
                    <button type="button" onclick="event.stopPropagation(); quickEditFixerPhone('${f.id}')" class="px-2 py-0.5 rounded-md bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[10px] font-bold transition flex items-center gap-1 cursor-pointer" title="Manually type agent phone number">
                      <span>📱 + Add Phone</span>
                    </button>
                    <button type="button" id="btn_lookup_${f.id}" onclick="event.stopPropagation(); lookupFixerPhone('${f.id}')" class="px-2 py-0.5 rounded-md bg-indigo-500/15 hover:bg-indigo-500/25 border border-indigo-500/30 text-indigo-300 text-[10px] font-bold transition flex items-center gap-1 cursor-pointer" title="Auto-find phone on Google/Realtor.com">
                      <span>⚡ Find Phone</span>
                    </button>
                    ${f.agent_name ? `
                      <a href="https://www.google.com/search?q=${encodeURIComponent((f.agent_name || '') + ' ' + (f.brokerage || '') + ' ' + (f.city || '') + ' FL realtor phone number')}" target="_blank" onclick="event.stopPropagation()" class="text-[10px] text-slate-400 hover:text-amber-300 underline" title="Search Google directly">
                        Google ↗
                      </a>
                    ` : ''}
                  </div>
                `}
                ${f.agent_email ? `
                  <a href="mailto:${escapeHtml(f.agent_email)}" onclick="event.stopPropagation()" class="text-cyan-400 hover:underline flex items-center gap-1">
                    <span>✉️</span>
                    <span class="truncate max-w-[180px]">${escapeHtml(f.agent_email)}</span>
                  </a>
                ` : ''}
                ${f.brokerage ? `<span class="text-slate-400 truncate max-w-[200px]">&bull; ${escapeHtml(f.brokerage)}</span>` : ''}
              </div>
            </div>
          </div>

          <!-- Price & Target Offer Badges + Expand/Collapse Button -->
          <div class="flex items-center justify-between w-full lg:w-auto gap-3 flex-shrink-0">
            <div class="flex items-center gap-3 bg-slate-950/60 p-3 rounded-xl border border-slate-800">
              <div class="text-right">
                <div class="text-[10px] text-slate-400 uppercase font-semibold">List Price</div>
                <div class="text-base sm:text-lg font-black text-white">$${(f.list_price || 0).toLocaleString()}</div>
                <div class="text-[10px] text-slate-500">Redfin Est: $${(f.redfin_estimate || 0).toLocaleString()}</div>
              </div>
              <div class="text-right border-l border-slate-800 pl-3">
                <div class="text-[10px] text-emerald-400 uppercase font-bold flex items-center justify-end gap-1">
                  <span>🎯 Lauren Cash MAO</span>
                </div>
                <div class="text-lg sm:text-xl font-black text-emerald-400" id="fixer_header_mao_${f.id}">$${Math.round(mao).toLocaleString()}</div>
                <div class="text-[10px] text-amber-300 font-medium" id="fixer_header_discount_${f.id}">${discountPct > 0 ? `${discountPct}% below list` : 'Formula calculated'}</div>
              </div>
            </div>

            <div class="flex items-center gap-1.5">
              <!-- Delete Fixer Card (Accessible in Collapsed Mode) -->
              <button type="button" onclick="event.stopPropagation(); deleteFixer('${f.id}')" class="p-2.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/25 border border-rose-500/30 text-rose-400 hover:text-rose-300 text-xs font-bold transition flex items-center gap-1 cursor-pointer shadow-sm" title="Delete Property Card">
                <span>🗑️</span>
              </button>

              <!-- Sleek Expand / Collapse Button -->
              <button type="button" id="btn_chevron_${f.id}" onclick="event.stopPropagation(); toggleFixerCard('${f.id}')" class="px-3.5 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 hover:border-amber-500/50 border border-slate-700 text-amber-300 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm">
                <span>${isExpanded ? '▲ Collapse' : '▼ Details'}</span>
              </button>
            </div>
          </div>

        </div>

        <!-- COLLAPSIBLE DETAILS BODY -->
        <div id="fixer_details_${f.id}" class="${isExpanded ? '' : 'hidden'} p-5 pt-0 border-t border-slate-800/80 space-y-4">

        <!-- UNDERWRITING CONTRADICTION ALERT (IF FLAGGED) -->
        ${(f.underwriting_contradiction_flag || (f.contradiction_details && f.contradiction_details.length > 0)) ? `
          <div class="bg-amber-500/15 border border-amber-500/40 rounded-xl p-3 text-xs text-amber-200 space-y-1">
            <div class="flex items-center gap-1.5 font-bold text-amber-300">
              <span>⚠️ Underwriting Contradiction Warning:</span>
            </div>
            <div class="text-[11px] leading-relaxed text-amber-200/90 pl-5 space-y-0.5">
              ${(f.contradiction_details || ["Agent reported mechanicals/roof in good condition. Review repair budget before sending Math Drop."]).map(c => `<div>• ${escapeHtml(c)}</div>`).join('')}
            </div>
          </div>
        ` : ''}

        <!-- 30-DAY FOLLOW-UP TASK (IF SCHEDULED) -->
        ${f.followup_task ? `
          <div class="bg-indigo-500/15 border border-indigo-500/40 rounded-xl p-2.5 text-xs text-indigo-200 flex items-center justify-between">
            <div class="flex items-center gap-2 font-bold text-indigo-300">
              <span>📅 30-Day Check-in Task:</span>
              <span class="font-mono text-slate-300 font-normal">Scheduled for ${escapeHtml(f.followup_task.scheduled_date || '30 days')}</span>
              ${f.followup_task.note ? `<span class="text-[10px] text-slate-400 italic">(${escapeHtml(f.followup_task.note)})</span>` : ''}
            </div>
            <span class="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-700/60 font-bold">${escapeHtml(f.followup_task.status || 'PENDING')}</span>
          </div>
        ` : ''}

        <!-- REMARKS ("DON'T LOOK STUPID" AWARENESS) -->
        <div class="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 text-xs space-y-1">
          <div class="flex items-center justify-between text-[11px] font-semibold text-slate-400">
            <span class="flex items-center gap-1.5 text-amber-300 font-bold">
              <span>💡</span>
              <span>Listing Remarks ("Don't Look Stupid" Intel):</span>
            </span>
            <span class="text-[10px] text-slate-500 font-mono">Disclosed facts to acknowledge</span>
          </div>
          <p class="text-slate-300 text-xs leading-relaxed max-h-20 overflow-y-auto pr-1">
            ${formattedRemarks}
          </p>
        </div>

        <!-- NATE BARGER UNDERWRITING CALCULATOR WIDGET -->
        <div class="bg-[#0b1220] border border-slate-800 rounded-xl p-4 space-y-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-amber-400 font-bold text-xs">🧮 Nate Barger Formula Underwriting</span>
              <span class="text-[10px] text-slate-400">(ARV - Repairs - 9% Fees - Margin - WS)</span>
            </div>
            <button type="button" onclick="saveFixerUnderwriting('${f.id}')" class="px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 text-[11px] font-semibold transition cursor-pointer">
              <span>💾 Save Underwriting</span>
            </button>
          </div>

          <!-- Inputs Grid -->
          <div class="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 text-xs">
            <div>
              <label class="block text-[10px] text-slate-400 uppercase font-semibold mb-1">Renovated ARV ($)</label>
              <input type="number" id="fixer_arv_${f.id}" value="${Math.round(arv)}" oninput="calculateFixerMaoLive('${f.id}')" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono">
            </div>

            <div>
              <label class="block text-[10px] text-slate-400 uppercase font-semibold mb-1">Property Sqft</label>
              <input type="number" id="fixer_sqft_${f.id}" value="${sqft}" oninput="calculateFixerMaoLive('${f.id}')" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono">
            </div>

            <div class="col-span-2">
              <div class="flex items-center justify-between mb-1">
                <label class="text-[10px] text-slate-400 uppercase font-semibold">Rehab $/sqft</label>
                <span class="text-[11px] text-amber-300 font-mono font-bold" id="fixer_rehab_val_${f.id}">$${rehabPerSqft}/sqft</span>
              </div>
              <input type="range" id="fixer_rehab_slider_${f.id}" min="20" max="80" step="5" value="${rehabPerSqft}" oninput="calculateFixerMaoLive('${f.id}')" class="w-full accent-amber-500 cursor-pointer">
            </div>

            <div>
              <label class="block text-[10px] text-slate-400 uppercase font-semibold mb-1">Flipper Margin</label>
              <select id="fixer_margin_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500">
                <option value="0.15" selected>15% (Standard Flip)</option>
                <option value="0.18">18% (Heavy Rehab)</option>
                <option value="0.12">12% (Light Cosmetic)</option>
              </select>
            </div>

            <div>
              <label class="block text-[10px] text-slate-400 uppercase font-semibold mb-1">Wholesale Fee ($)</label>
              <input type="number" id="fixer_ws_${f.id}" value="0" oninput="calculateFixerMaoLive('${f.id}')" class="w-full bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500 font-mono">
            </div>
          </div>

          <!-- High-Ticket Repair Checkboxes -->
          <div class="flex flex-wrap items-center gap-3 pt-1 border-t border-slate-800/80 text-[11px]">
            <span class="text-slate-400 font-semibold uppercase text-[10px]">High Ticket Repairs:</span>
            
            <label class="flex items-center gap-1.5 text-slate-300 cursor-pointer hover:text-white">
              <input type="checkbox" id="fixer_ht_roof_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0">
              <span>Roof ($12.5k)</span>
            </label>

            <label class="flex items-center gap-1.5 text-slate-300 cursor-pointer hover:text-white">
              <input type="checkbox" id="fixer_ht_hvac_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0">
              <span>HVAC ($6k)</span>
            </label>

            <label class="flex items-center gap-1.5 text-slate-300 cursor-pointer hover:text-white">
              <input type="checkbox" id="fixer_ht_repipe_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0">
              <span>Re-pipe ($15k)</span>
            </label>

            <label class="flex items-center gap-1.5 text-slate-300 cursor-pointer hover:text-white">
              <input type="checkbox" id="fixer_ht_wh_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0">
              <span>Water Heater ($3k)</span>
            </label>

            <label class="flex items-center gap-1.5 text-slate-300 cursor-pointer hover:text-white">
              <input type="checkbox" id="fixer_ht_elec_${f.id}" onchange="calculateFixerMaoLive('${f.id}')" class="rounded bg-slate-800 border-slate-700 text-amber-500 focus:ring-0">
              <span>Panel ($4k)</span>
            </label>
          </div>

          <!-- Formula Results Bar -->
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800/80 text-xs">
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400">Total Rehab Cost:</div>
              <div class="font-bold text-amber-300" id="fixer_calc_rehab_${f.id}">$${Math.round(totalRehab).toLocaleString()}</div>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400">9% Carry + Comm Fees:</div>
              <div class="font-bold text-slate-200" id="fixer_calc_fees_${f.id}">$${Math.round(totalFees).toLocaleString()}</div>
            </div>
            <div class="bg-slate-900/60 p-2 rounded-lg border border-slate-800">
              <div class="text-[10px] text-slate-400">Flipper Profit:</div>
              <div class="font-bold text-slate-200" id="fixer_calc_profit_${f.id}">$${Math.round(flipperProfit).toLocaleString()}</div>
            </div>
            <div class="bg-emerald-950/40 p-2 rounded-lg border border-emerald-500/30">
              <div class="text-[10px] text-emerald-300 font-semibold">Formula Cash Target:</div>
              <div class="font-black text-emerald-400 text-sm" id="fixer_calc_mao_${f.id}">$${Math.round(mao).toLocaleString()}</div>
            </div>
          </div>

        </div>

        <!-- SOCRATIC TROJAN HORSE & OUTREACH CONTROL -->
        <div class="space-y-2.5">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <div class="flex items-center gap-1.5 text-xs">
              <span class="text-amber-400 font-bold">🐴 Trojan Horse Flow:</span>
              <div class="flex items-center gap-1">
                ${socraticStages.map(s => {
                  const isActive = currentStageKey === s.key;
                  return `
                    <span class="text-[10px] px-2 py-0.5 rounded-full font-mono font-medium ${isActive ? 'bg-amber-500 text-slate-950 font-bold shadow' : 'bg-slate-800 text-slate-400'}">
                      ${s.label}
                    </span>
                  `;
                }).join("")}
              </div>
            </div>
            <div class="flex items-center gap-2">
              <button type="button" onclick="openFixerInboundModal('${f.id}')" class="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-bold transition flex items-center gap-1 cursor-pointer">
                <span>💬 Simulate Agent Reply</span>
              </button>
              <button type="button" onclick="toggleFixerThread('${f.id}')" class="px-3 py-1.5 rounded-xl ${latestInbound ? 'bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-200 border border-indigo-500/50 font-bold shadow-sm' : 'bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 font-semibold'} text-xs transition flex items-center gap-1 cursor-pointer" title="Click to view full message transcript">
                <span>💬 Thread (${currentMsgCount})${latestInbound ? ' • Inbound' : ''}</span>
              </button>
            </div>
          </div>

          <!-- LIVE TWO-WAY CONVERSATION CHAT THREAD (INBOUND + OUTBOUND) -->
          ${(messages && messages.length > 0) ? `
            <div class="p-3.5 rounded-2xl bg-[#070d18] border border-slate-800 space-y-2.5 shadow-inner">
              <div class="flex items-center justify-between text-[11px] pb-1 border-b border-slate-800/60">
                <span class="font-bold text-amber-300 flex items-center gap-1.5">
                  <span>💬</span>
                  <span>Live SMS Conversation (${escapeHtml(f.agent_name || 'Agent')}):</span>
                </span>
                <span class="text-[10px] text-slate-400 font-mono">${messages.length} message${messages.length === 1 ? '' : 's'}</span>
              </div>
              <div class="space-y-2 max-h-60 overflow-y-auto pr-1">
                ${messages.map(m => {
                  const isOut = m.direction === "OUTBOUND";
                  return `
                    <div class="flex flex-col ${isOut ? 'items-end ml-auto' : 'items-start mr-auto'} max-w-[88%] space-y-0.5">
                      <div class="flex items-center gap-1.5 text-[9px] text-slate-400">
                        <span class="font-bold ${isOut ? 'text-amber-400' : 'text-indigo-300'}">${escapeHtml(m.sender || (isOut ? 'Lauren (You)' : (f.agent_name || 'Agent')))}</span>
                        <span>&bull;</span>
                        <span class="font-mono text-slate-500">${escapeHtml(m.timestamp || '')}</span>
                      </div>
                      <div class="p-2.5 rounded-2xl text-xs leading-relaxed ${isOut ? 'bg-amber-500/20 border border-amber-500/35 text-amber-100 rounded-tr-none' : 'bg-slate-800/95 border border-slate-700 text-slate-100 rounded-tl-none'}">
                        ${escapeHtml(m.text || '')}
                      </div>
                    </div>
                  `;
                }).join('')}
              </div>
            </div>
          ` : ''}

          <!-- Suggested Reply Box -->
          <div class="space-y-1">
            <div class="flex items-center justify-between">
              <label class="block text-[11px] text-slate-400 font-semibold">
                Lauren's Suggested Next SMS (dispatches via Android Gateway):
              </label>
              <button type="button" onclick="spinFixerHookLive('${f.id}')" class="text-[10px] text-amber-400 hover:text-amber-300 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 px-2 py-0.5 rounded-lg flex items-center gap-1 font-bold cursor-pointer transition shadow-sm" title="Spin and generate a fresh wording variation">
                <span>🎲 Mix It Up</span>
              </button>
            </div>
            <textarea id="fixer_msg_${f.id}" rows="2" class="w-full bg-[#0b1220] border border-slate-700 rounded-xl p-3 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-amber-500">${escapeHtml(f.suggested_reply || f.opening_hook || '')}</textarea>
          </div>

          <!-- Action Buttons Bar -->
          <div class="flex flex-wrap items-center justify-between gap-2 pt-1">
            <button type="button" onclick="deleteFixer('${f.id}')" class="px-3 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold transition cursor-pointer">
              <span>🗑️ Remove Fixer</span>
            </button>

            <div class="flex items-center gap-2">
              <button type="button" onclick="sendFixerStandingLoi('${f.id}')" class="px-4 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow" title="Send Official Standing Written LOI with 30-Day Open Term & Page 12 Commission Guarantee">
                <span>📄 Send Standing LOI + SMS</span>
              </button>
              <button type="button" onclick="sendFixerSms('${f.id}')" class="px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-emerald-600/30 cursor-pointer">
                <span>🚀 Send SMS via Phone</span>
              </button>
            </div>
          </div>
        </div><!-- END COLLAPSIBLE DETAILS BODY -->

      </div><!-- END FIXER CARD -->
    `;
  }).join("");
}

function calculateFixerMaoLive(fixerId) {
  const arvInput = document.getElementById(`fixer_arv_${fixerId}`);
  const sqftInput = document.getElementById(`fixer_sqft_${fixerId}`);
  const rehabSlider = document.getElementById(`fixer_rehab_slider_${fixerId}`);
  const marginSelect = document.getElementById(`fixer_margin_${fixerId}`);
  const wsInput = document.getElementById(`fixer_ws_${fixerId}`);

  if (!arvInput || !sqftInput || !rehabSlider) return;

  const arv = parseFloat(arvInput.value) || 0;
  const sqft = parseFloat(sqftInput.value) || 1200;
  const rehabRate = parseFloat(rehabSlider.value) || 40;
  const margin = parseFloat(marginSelect ? marginSelect.value : 0.15) || 0.15;
  const wsFee = parseFloat(wsInput ? wsInput.value : 0) || 0;

  // Update slider label
  const rehabValLabel = document.getElementById(`fixer_rehab_val_${fixerId}`);
  if (rehabValLabel) rehabValLabel.innerText = `$${rehabRate}/sqft`;

  // Calculate high ticket additions
  let highTicketTotal = 0;
  if (document.getElementById(`fixer_ht_roof_${fixerId}`)?.checked) highTicketTotal += 12500;
  if (document.getElementById(`fixer_ht_hvac_${fixerId}`)?.checked) highTicketTotal += 6000;
  if (document.getElementById(`fixer_ht_repipe_${fixerId}`)?.checked) highTicketTotal += 15000;
  if (document.getElementById(`fixer_ht_wh_${fixerId}`)?.checked) highTicketTotal += 3000;
  if (document.getElementById(`fixer_ht_elec_${fixerId}`)?.checked) highTicketTotal += 4000;

  const totalRehab = (sqft * rehabRate) + highTicketTotal;
  const totalFees = arv * 0.09;
  const flipperProfit = arv * margin;
  const calculatedMao = Math.max(0, arv - totalRehab - totalFees - flipperProfit - wsFee);

  // Update display values
  const elRehab = document.getElementById(`fixer_calc_rehab_${fixerId}`);
  if (elRehab) elRehab.innerText = `$${Math.round(totalRehab).toLocaleString()}`;

  const elFees = document.getElementById(`fixer_calc_fees_${fixerId}`);
  if (elFees) elFees.innerText = `$${Math.round(totalFees).toLocaleString()}`;

  const elProfit = document.getElementById(`fixer_calc_profit_${fixerId}`);
  if (elProfit) elProfit.innerText = `$${Math.round(flipperProfit).toLocaleString()}`;

  const elMao = document.getElementById(`fixer_calc_mao_${fixerId}`);
  if (elMao) elMao.innerText = `$${Math.round(calculatedMao).toLocaleString()}`;

  const elHeaderMao = document.getElementById(`fixer_header_mao_${fixerId}`);
  if (elHeaderMao) elHeaderMao.innerText = `$${Math.round(calculatedMao).toLocaleString()}`;

  // Update discount vs list
  const fixer = allFixers.find(f => f.id === fixerId);
  if (fixer && fixer.list_price) {
    const discPct = Math.round(((fixer.list_price - calculatedMao) / fixer.list_price) * 100);
    const elHeaderDisc = document.getElementById(`fixer_header_discount_${fixerId}`);
    if (elHeaderDisc) {
      elHeaderDisc.innerText = discPct > 0 ? `${discPct}% below list` : "Formula calculated";
    }
  }
}

async function saveFixerUnderwriting(fixerId) {
  const arv = parseFloat(document.getElementById(`fixer_arv_${fixerId}`)?.value) || 250000;
  const sqft = parseFloat(document.getElementById(`fixer_sqft_${fixerId}`)?.value) || 1200;
  const rehabRate = parseFloat(document.getElementById(`fixer_rehab_slider_${fixerId}`)?.value) || 40;
  const margin = parseFloat(document.getElementById(`fixer_margin_${fixerId}`)?.value) || 0.15;
  const wsFee = parseFloat(document.getElementById(`fixer_ws_${fixerId}`)?.value) || 0;

  let highTicketTotal = 0;
  if (document.getElementById(`fixer_ht_roof_${fixerId}`)?.checked) highTicketTotal += 12500;
  if (document.getElementById(`fixer_ht_hvac_${fixerId}`)?.checked) highTicketTotal += 6000;
  if (document.getElementById(`fixer_ht_repipe_${fixerId}`)?.checked) highTicketTotal += 15000;
  if (document.getElementById(`fixer_ht_wh_${fixerId}`)?.checked) highTicketTotal += 3000;
  if (document.getElementById(`fixer_ht_elec_${fixerId}`)?.checked) highTicketTotal += 4000;

  try {
    const res = await fetch("/api/fixers/calculate-mao", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        arv: arv,
        sqft: sqft,
        rehab_per_sqft: rehabRate,
        high_ticket_total: highTicketTotal,
        closing_cost_pct: 0.02,
        carrying_cost_pct: 0.02,
        commission_pct: 0.05,
        flipper_profit_pct: margin,
        wholesale_fee: wsFee
      })
    });
    const calc = await res.json();

    const fixer = allFixers.find(f => f.id === fixerId);
    if (fixer) {
      fixer.underwriting = calc;
    }
    alert(`✓ Underwriting saved!\nTarget Cash MAO: $${Math.round(calc.offer_price).toLocaleString()}`);
  } catch (err) {
    alert("Error saving underwriting: " + err.message);
  }
}

async function spinFixerHookLive(fixerId) {
  try {
    const res = await fetch(`/api/fixers/${fixerId}/spin-hook`, { method: "POST" });
    if (!res.ok) throw new Error("Failed to spin fixer hook");
    const data = await res.json();
    const txtArea = document.getElementById(`fixer_msg_${fixerId}`);
    if (txtArea && data.suggested_reply) {
      txtArea.value = data.suggested_reply;
      txtArea.classList.add("ring-2", "ring-amber-400");
      setTimeout(() => txtArea.classList.remove("ring-2", "ring-amber-400"), 600);
    }
    const fixer = allFixers.find(f => f.id === fixerId);
    if (fixer) {
      fixer.opening_hook = data.opening_hook;
      fixer.suggested_reply = data.suggested_reply;
    }
  } catch (err) {
    console.error("Error spinning fixer hook:", err);
  }
}

async function sendFixerSms(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  if (!fixer) return;

  const msgInput = document.getElementById(`fixer_msg_${fixerId}`);
  const message = msgInput ? msgInput.value.trim() : fixer.suggested_reply || fixer.opening_hook;

  if (!fixer.agent_phone) {
    alert("This fixer listing does not have a phone number for the agent.");
    return;
  }

  if (!confirm(`⚠️ DISPATCH OUTBOUND SMS:\n\nTo Agent: ${fixer.agent_name || 'Agent'} (${fixer.agent_phone})\nProperty: ${fixer.address}\n\nMessage:\n"${message}"\n\nDispatch live via Android Gateway?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/fixers/${fixerId}/send-sms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message })
    });
    const data = await res.json();
    if (data.status === "success") {
      alert("✓ Outbound SMS dispatched successfully through Android cellular gateway!");
      await loadFixers();
    } else {
      alert("Error dispatching SMS: " + (data.message || "Unknown error"));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function sendFixerStandingLoi(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  if (!fixer) return;

  const offerVal = (fixer.underwriting && fixer.underwriting.offer_price) || 120000;

  if (!confirm(`📄 SEND STANDING WRITTEN LOI:\n\nProperty: ${fixer.address}\nListing Agent: ${fixer.agent_name || 'Agent'} (${fixer.agent_email || 'No email'})\nOffer Amount: $${Math.round(offerVal).toLocaleString()} NET CASH\n\nTerms included:\n• 30-Day Standing Validity\n• Full Page 12 Commission Guarantee\n• Companion SMS alert to listing agent\n\nProceed with dispatch?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/fixers/${fixerId}/send-standing-loi`, {
      method: "POST"
    });
    const data = await res.json();
    if (data.status === "success") {
      alert(`✓ Official Standing LOI sent successfully!\n\nEmail: ${data.email_res.status}\nSMS: ${data.sms_res.status}`);
      await loadFixers();
    } else {
      alert("Error sending Standing LOI: " + JSON.stringify(data));
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

function openFixerInboundModal(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  if (!fixer) return;

  document.getElementById("fixerInboundFixerId").value = fixerId;
  const subtitle = document.getElementById("fixerInboundSubtitle");
  if (subtitle) {
    subtitle.innerText = `Simulate reply from ${fixer.agent_name || 'Agent'} for ${fixer.address}`;
  }

  const msgBox = document.getElementById("fixerInboundMessage");
  if (msgBox) msgBox.value = "";

  const resBox = document.getElementById("fixerInboundResultBox");
  if (resBox) resBox.classList.add("hidden");

  openModal("fixerInboundModal");
}

function setInboundPreset(text, autoSubmit = false) {
  const msgBox = document.getElementById("fixerInboundMessage");
  if (msgBox) msgBox.value = text;

  // Immediately clear old result so user never reads stale analysis
  const resBox = document.getElementById("fixerInboundResultBox");
  if (resBox) resBox.classList.add("hidden");

  if (autoSubmit) {
    submitFixerInbound();
  }
}

async function resetFixerFlowFromModal() {
  const fixerId = document.getElementById("fixerInboundFixerId").value;
  if (!fixerId) return;
  try {
    const res = await fetch(`/api/fixers/${fixerId}/reset-flow`, { method: "POST" });
    if (res.ok) {
      const resBox = document.getElementById("fixerInboundResultBox");
      if (resBox) resBox.classList.add("hidden");
      const msgBox = document.getElementById("fixerInboundMessage");
      if (msgBox) msgBox.value = "";
      alert("✓ Property reset back to Step 1 Hook! Ready to test from the beginning.");
      await loadFixers();
    }
  } catch (err) {
    alert("Error resetting flow: " + err.message);
  }
}

async function submitFixerInbound() {
  const fixerId = document.getElementById("fixerInboundFixerId").value;
  const message = document.getElementById("fixerInboundMessage").value.trim();

  if (!message) {
    alert("Please enter what the agent replied.");
    return;
  }

  const btn = document.getElementById("btnSubmitFixerInbound");
  const origText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳</span> <span>Evaluating Socratic Logic...</span>`;
  }

  // Instantly show loading state in result box so old content is replaced immediately
  const resBox = document.getElementById("fixerInboundResultBox");
  const badge = document.getElementById("fixerInboundNodeBadge");
  const reason = document.getElementById("fixerInboundReason");
  const suggested = document.getElementById("fixerInboundSuggestedReply");

  if (resBox) {
    resBox.classList.remove("hidden");
    if (badge) badge.innerText = "EVALUATING...";
    if (reason) reason.innerText = "Running Socratic logic & Asymmetric ARV Arbitrage...";
    if (suggested) suggested.innerHTML = `<span class="inline-block animate-spin mr-1">⏳</span> Lauren is analyzing your message...`;
  }

  try {
    const res = await fetch(`/api/fixers/${fixerId}/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message })
    });
    const data = await res.json();

    if (resBox && data.eval) {
      resBox.classList.remove("hidden");
      if (badge) badge.innerText = data.eval.node || "NEXT_STEP";
      if (reason) reason.innerText = data.eval.reason || "Trojan Horse evaluation complete.";
      if (suggested) suggested.innerText = data.eval.reply_text || "No reply suggested.";
    }

    // Refresh fixer in list
    await loadFixers();
  } catch (err) {
    alert("Error evaluating inbound message: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}

async function deleteFixer(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  const addr = fixer ? fixer.address : "this listing";

  if (!confirm(`Are you sure you want to remove ${addr} from Lauren's Desk?`)) {
    return;
  }

  try {
    const res = await fetch(`/api/fixers/${fixerId}`, {
      method: "DELETE"
    });
    if (res.ok) {
      await loadFixers();
    } else {
      alert("Failed to delete fixer.");
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}

async function clearEntireFixerDesk() {
  const count = allFixers ? allFixers.length : 0;
  const msg = count > 0 
    ? `⚠️ ARE YOU SURE YOU WANT TO CLEAR LAUREN'S DESK?\n\nThis will remove all ${count} fixer listings from Lauren's Desk so you can start completely fresh.\n\nThis action cannot be undone.`
    : `⚠️ Clear and reset Lauren's Desk on the server to start fresh?`;

  if (!confirm(msg)) {
    return;
  }

  try {
    const res = await fetch("/api/fixers/clear", {
      method: "POST"
    });
    
    if (res.ok) {
      allFixers = [];
      filteredFixers = [];
      
      // Update UI elements directly
      const headerBadge = document.getElementById("headerLaurenBadge");
      if (headerBadge) headerBadge.innerText = "0";
      const statCount = document.getElementById("statFixersCount");
      if (statCount) statCount.innerText = "0";
      const statAvgArv = document.getElementById("statFixersAvgArv");
      if (statAvgArv) statAvgArv.innerText = "$0";
      const statAvgMao = document.getElementById("statFixersAvgMao");
      if (statAvgMao) statAvgMao.innerText = "$0";
      const statLois = document.getElementById("statFixersLoiSent");
      if (statLois) statLois.innerText = "0";
      const countDisplay = document.getElementById("fixerCountDisplay");
      if (countDisplay) countDisplay.innerText = "Showing 0 of 0 fixer listings";

      populateFixerFilterDropdowns();
      renderFixers([]);
      
      alert("✅ Lauren's Desk has been completely cleared. Ready for fresh Redfin scrapes!");
    } else {
      const delRes = await fetch("/api/fixers", { method: "DELETE" });
      if (delRes.ok) {
        allFixers = [];
        filteredFixers = [];
        populateFixerFilterDropdowns();
        renderFixers([]);
        alert("✅ Lauren's Desk has been completely cleared. Ready for fresh Redfin scrapes!");
      } else {
        alert("Failed to clear desk. Please check server logs.");
      }
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}
window.clearEntireFixerDesk = clearEntireFixerDesk;

function toggleFixerThread(fixerId) {
  const el = document.getElementById(`fixer_thread_${fixerId}`);
  if (el) {
    el.classList.toggle("hidden");
  }
}

// --- AUTO-DRIP OUTBOUND QUEUE CONTROLLER (LOAD & GO) ---
let currentDripState = null;

async function quickEditFixerPhone(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  const currentPhone = fixer ? (fixer.agent_phone || "") : "";
  const agentName = fixer ? (fixer.agent_name || "Listing Agent") : "Agent";

  const newPhone = prompt(`Enter phone number for ${agentName} (${fixer?.address || ''}):`, currentPhone);
  if (newPhone === null) return;

  const cleaned = newPhone.trim();
  try {
    const res = await fetch(`/api/fixers/${fixerId}/phone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: cleaned })
    });
    if (res.ok) {
      if (fixer) fixer.agent_phone = cleaned;
      filterFixersList();
    } else {
      alert("Failed to update phone number.");
    }
  } catch (err) {
    alert("Network error: " + err.message);
  }
}
window.quickEditFixerPhone = quickEditFixerPhone;

async function lookupFixerPhone(fixerId) {
  const fixer = allFixers.find(f => f.id === fixerId);
  const agentName = fixer ? (fixer.agent_name || "Agent") : "Agent";
  const brokerage = fixer ? (fixer.brokerage || "") : "";
  const city = fixer ? (fixer.city || "") : "";

  const btn = document.getElementById(`btn_lookup_${fixerId}`);
  const origHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Searching...</span>`;
  }
  try {
    const res = await fetch(`/api/fixers/${fixerId}/lookup-phone`, { method: "POST" });
    const d = await res.json();
    if (d.status === "success" && d.phone) {
      if (fixer) fixer.agent_phone = d.phone;
      filterFixersList();
    } else {
      const gUrl = `https://www.google.com/search?q=${encodeURIComponent(agentName + ' ' + brokerage + ' ' + city + ' FL realtor phone number')}`;
      if (confirm(`🔍 Web lookup didn't find a direct number.\n\nWould you like to open Google Search for "${agentName}" to grab their number?`)) {
        window.open(gUrl, '_blank');
        setTimeout(() => {
          quickEditFixerPhone(fixerId);
        }, 500);
      }
    }
  } catch (err) {
    alert("Lookup error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}
window.lookupFixerPhone = lookupFixerPhone;

async function lookupAllFixerPhones() {
  const btn = document.querySelector('[title*="Search Google & Realtor.com"]');
  const origText = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Searching Web...</span>`;
  }
  try {
    const res = await fetch("/api/fixers/lookup-all-phones", { method: "POST" });
    const d = await res.json();
    await loadFixers();
    alert(d.message || "Lookup complete!");
  } catch (err) {
    alert("Batch lookup error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origText;
    }
  }
}
window.lookupAllFixerPhones = lookupAllFixerPhones;

async function startDripQueue(desk) {
  const pacingEl = document.getElementById(desk === "BROOKE" ? "brookeDripPacing" : (desk === "LANA" ? "lanaDripPacing" : "laurenDripPacing"));
  const pacingVal = pacingEl ? pacingEl.value : "60-120";
  const [minDelay, maxDelay] = pacingVal.split('-').map(Number);

  const btn = document.getElementById(desk === "BROOKE" ? "btnStartBrookeDrip" : (desk === "LANA" ? "btnStartLanaDrip" : "btnStartLaurenDrip"));
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Starting Queue...";
  }

  const countyVal = desk === "BROOKE" 
    ? (currentCounty !== "ALL" ? currentCounty : null)
    : desk === "LANA"
    ? (document.getElementById("lotCountyFilter") && document.getElementById("lotCountyFilter").value !== "ALL"
        ? document.getElementById("lotCountyFilter").value
        : null)
    : (document.getElementById("fixerCountyFilter") && document.getElementById("fixerCountyFilter").value !== "ALL" 
        ? document.getElementById("fixerCountyFilter").value 
        : null);

  try {
    const res = await fetch("/api/drip/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        desk: desk,
        min_delay: minDelay || 60,
        max_delay: maxDelay || 120,
        county: countyVal
      })
    });
    const data = await res.json();
    if (data.status === "success") {
      pollDripStatus();
      setTimeout(async () => {
        if (desk === "BROOKE") await loadAgents();
        else if (desk === "LANA") await loadLots();
        else await loadFixers();
      }, 1500);
    } else {
      alert(data.message || "Failed to start drip queue.");
    }
  } catch (err) {
    alert("Error starting drip queue: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = "<span>🚀 Start Load &amp; Go</span>";
    }
  }
}

async function pauseDripQueue() {
  try {
    const res = await fetch("/api/drip/pause", { method: "POST" });
    const data = await res.json();
    pollDripStatus();
  } catch (err) {
    console.error("Error pausing drip:", err);
  }
}

async function stopDripQueue() {
  if (!confirm("Are you sure you want to stop and clear the Auto-Drip queue?")) return;
  try {
    const res = await fetch("/api/drip/stop", { method: "POST" });
    const data = await res.json();
    pollDripStatus();
    if (currentDesk === "BROOKE") await loadAgents();
    else if (currentDesk === "LANA") await loadLots();
    else await loadFixers();
  } catch (err) {
    console.error("Error stopping drip:", err);
  }
}

async function pollDripStatus() {
  try {
    const res = await fetch("/api/drip/status");
    const data = await res.json();
    currentDripState = data;
    renderDripStatus(data);
  } catch (err) {
    console.warn("Failed to poll drip status", err);
  }
}

function renderDripStatus(s) {
  // Brooke Desk Elements
  const bBadge = document.getElementById("brookeDripStatusBadge");
  const bSub = document.getElementById("brookeDripSubtitle");
  const btnStartB = document.getElementById("btnStartBrookeDrip");
  const btnPauseB = document.getElementById("btnPauseBrookeDrip");
  const btnStopB = document.getElementById("btnStopBrookeDrip");

  // Lauren Desk Elements
  const lBadge = document.getElementById("laurenDripStatusBadge");
  const lSub = document.getElementById("laurenDripSubtitle");
  const btnStartL = document.getElementById("btnStartLaurenDrip");
  const btnPauseL = document.getElementById("btnPauseLaurenDrip");
  const btnStopL = document.getElementById("btnStopLaurenDrip");

  // Lana Desk Elements
  const laBadge = document.getElementById("lanaDripStatusBadge");
  const laSub = document.getElementById("lanaDripSubtitle");
  const btnStartLa = document.getElementById("btnStartLanaDrip");
  const btnPauseLa = document.getElementById("btnPauseLanaDrip");
  const btnStopLa = document.getElementById("btnStopLanaDrip");

  const isRunning = s.status === "RUNNING";
  const isPaused = s.status === "PAUSED";
  const isQuiet = s.status === "QUIET_HOURS";
  const isCompleted = s.status === "COMPLETED";

  const desk = s.active_desk;

  function updateDeskUI(badge, sub, btnStart, btnPause, btnStop, deskName) {
    if (!badge) return;

    if (desk === deskName && isRunning) {
      badge.className = "px-2.5 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 animate-pulse";
      badge.innerHTML = `🟢 Dripping: ${s.sent_count} / ${s.total_queued} Sent • Next in ${s.seconds_remaining}s`;
      sub.innerHTML = `<span class="text-emerald-300 font-semibold">Active:</span> Targeting <strong class="text-white">${escapeHtml(s.current_target?.name || 'Agent')}</strong> (${escapeHtml(s.current_target?.address || '')}) • Next text at ${s.next_send_time || 'shortly'}.`;
      
      btnStart.classList.add("hidden");
      btnPause.classList.remove("hidden");
      btnPause.className = "px-4 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 text-amber-300 text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-amber-500/10 cursor-pointer";
      btnPause.innerHTML = "<span>⏸️ Pause Queue</span>";
      btnStop.classList.remove("hidden");
    } else if (desk === deskName && isPaused) {
      badge.className = "px-2.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30";
      badge.innerHTML = `⏸️ Paused (${s.sent_count} / ${s.total_queued} Sent)`;
      sub.innerText = `Queue is paused. Hit Resume to continue sending with ${s.min_delay}-${s.max_delay}s natural pacing.`;
      
      btnStart.classList.add("hidden");
      btnPause.classList.remove("hidden");
      btnPause.className = "px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition flex items-center gap-1.5 shadow-lg shadow-emerald-600/30 cursor-pointer animate-pulse";
      btnPause.innerHTML = "<span>▶️ Resume Queue</span>";
      btnStop.classList.remove("hidden");
    } else if (desk === deskName && isQuiet) {
      badge.className = "px-2.5 py-0.5 rounded text-[10px] font-bold bg-purple-500/20 text-purple-300 border border-purple-500/30";
      badge.innerHTML = `🌙 Quiet Hours (Sleeping until 8:30 AM)`;
      sub.innerText = "Carrier safety active: Outreach automatically pauses outside business hours and resumes at 8:30 AM EST.";
      
      btnStart.classList.add("hidden");
      btnPause.classList.remove("hidden");
      btnStop.classList.remove("hidden");
    } else if (desk === deskName && isCompleted) {
      badge.className = "px-2.5 py-0.5 rounded text-[10px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30";
      badge.innerHTML = `✓ Completed (${s.sent_count} Sent)`;
      sub.innerText = `All queued contacts have been texted! Inbound replies will be evaluated automatically by the Underdog bot.`;
      
      btnStart.classList.remove("hidden");
      btnPause.classList.add("hidden");
      btnStop.classList.add("hidden");
    } else {
      badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400 border border-slate-700";
      badge.innerHTML = "⚪ Idle";
      sub.innerText = deskName === "BROOKE" 
        ? "Paces natural carrier-safe outreach (60-120s random delay) across uncontacted agents in the background."
        : deskName === "LAUREN"
        ? "Paces Trojan Horse opening hooks (60-120s random delay) across scraped Redfin fixers in the background."
        : "Paces builder-framed opening hooks & doorbell texts (60-120s delay) across on-market infill land with zero hyphens.";
      
      btnStart.classList.remove("hidden");
      btnPause.classList.add("hidden");
      btnStop.classList.add("hidden");
    }
  }

  updateDeskUI(bBadge, bSub, btnStartB, btnPauseB, btnStopB, "BROOKE");
  updateDeskUI(lBadge, lSub, btnStartL, btnPauseL, btnStopL, "LAUREN");
  updateDeskUI(laBadge, laSub, btnStartLa, btnPauseLa, btnStopLa, "LANA");
}

window.startDripQueue = startDripQueue;
window.pauseDripQueue = pauseDripQueue;
window.stopDripQueue = stopDripQueue;
window.pollDripStatus = pollDripStatus;

// =========================================================================
// LANA'S ON-MARKET INFILL LAND SPECIALIST DESK CONTROLLER
// =========================================================================

let allLots = [];
let lotExpandedCards = new Set();
let lotExpandedThreads = new Set();
let currentEditingLotId = null;

async function loadLots() {
  try {
    const res = await fetch("/api/lana/lots");
    if (!res.ok) throw new Error("Failed to load infill lots");
    const data = await res.json();
    allLots = Array.isArray(data) ? data : (data.lots || []);

    // Top switcher badge
    const headerBadge = document.getElementById("headerLanaBadge");
    if (headerBadge) headerBadge.innerText = allLots.length;

    // Metrics ribbon
    const statCount = document.getElementById("statLotsCount");
    if (statCount) statCount.innerText = allLots.length;

    let totalAsking = 0;
    let totalNewbuild = 0;
    let totalMaxPayable = 0;
    let loisCount = 0;

    allLots.forEach(l => {
      const asking = l.list_price || 0;
      const uw = l.underwriting || {};
      const newbuild = uw.finished_newbuild_value || 0;
      const maxPayable = uw.max_payable || 0;
      totalAsking += asking;
      totalNewbuild += newbuild;
      totalMaxPayable += maxPayable;
      if (l.loi_sent) loisCount++;
    });

    const statAvgAsking = document.getElementById("statLotsAvgAsking");
    if (statAvgAsking) {
      statAvgAsking.innerText = allLots.length > 0 ? `$${Math.round(totalAsking / allLots.length).toLocaleString()}` : "$0";
    }

    const statAvgNewbuild = document.getElementById("statLotsAvgNewbuild");
    if (statAvgNewbuild) {
      statAvgNewbuild.innerText = allLots.length > 0 ? `$${Math.round(totalNewbuild / allLots.length).toLocaleString()}` : "$0";
    }

    const statAvgMaxPayable = document.getElementById("statLotsAvgMaxPayable");
    if (statAvgMaxPayable) {
      statAvgMaxPayable.innerText = allLots.length > 0 ? `$${Math.round(totalMaxPayable / allLots.length).toLocaleString()}` : "$0";
    }

    const statLois = document.getElementById("statLotsLoiSent");
    if (statLois) statLois.innerText = loisCount;

    populateLotFilterDropdowns();
    filterLotsList();
  } catch (err) {
    console.error("Error loading infill lots:", err);
  }
}

function populateLotFilterDropdowns() {
  const countySel = document.getElementById("lotCountyFilter");
  if (countySel) {
    const currentCountyVal = countySel.value || "ALL";
    const counties = [...new Set(allLots.map(l => (l.county || "").toUpperCase().trim()).filter(Boolean))].sort();
    let countyHtml = `<option value="ALL">All Counties</option>`;
    counties.forEach(c => {
      const selected = c === currentCountyVal ? "selected" : "";
      countyHtml += `<option value="${escapeHtml(c)}" ${selected}>${escapeHtml(c)}</option>`;
    });
    countySel.innerHTML = countyHtml;
  }
  populateLotCityDropdown();
}

function populateLotCityDropdown() {
  const citySel = document.getElementById("lotCityFilter");
  if (!citySel) return;
  const countySel = document.getElementById("lotCountyFilter");
  const selectedCounty = countySel ? countySel.value : "ALL";

  const currentCityVal = citySel.value || "ALL";
  let filtered = allLots;
  if (selectedCounty !== "ALL") {
    filtered = filtered.filter(l => (l.county || "").toUpperCase().trim() === selectedCounty);
  }

  const cities = [...new Set(filtered.map(l => (l.city || "").trim()).filter(Boolean))].sort();
  let cityHtml = `<option value="ALL">All Cities</option>`;
  cities.forEach(c => {
    const selected = c === currentCityVal ? "selected" : "";
    cityHtml += `<option value="${escapeHtml(c)}" ${selected}>${escapeHtml(c)}</option>`;
  });
  citySel.innerHTML = cityHtml;
}

function handleLotCountyFilterChange() {
  populateLotCityDropdown();
  filterLotsList();
}

function filterLotsList() {
  const searchInput = document.getElementById("lotSearchInput");
  const query = (searchInput ? searchInput.value : "").trim().toLowerCase();

  const contactFilter = document.getElementById("lotContactFilter");
  const contactVal = contactFilter ? contactFilter.value : "ALL";

  const countyFilter = document.getElementById("lotCountyFilter");
  const countyVal = countyFilter ? countyFilter.value : "ALL";

  const cityFilter = document.getElementById("lotCityFilter");
  const cityVal = cityFilter ? cityFilter.value : "ALL";

  const sizeFilter = document.getElementById("lotSizeFilter");
  const sizeVal = sizeFilter ? sizeFilter.value : "INFILL";

  let filtered = allLots.filter(lot => {
    if (query) {
      const match = (lot.address || "").toLowerCase().includes(query) ||
                    (lot.city || "").toLowerCase().includes(query) ||
                    (lot.county || "").toLowerCase().includes(query) ||
                    (lot.parcel_id || "").toLowerCase().includes(query) ||
                    (lot.agent_name || "").toLowerCase().includes(query) ||
                    (lot.brokerage || "").toLowerCase().includes(query);
      if (!match) return false;
    }

    if (countyVal !== "ALL") {
      if ((lot.county || "").toUpperCase().trim() !== countyVal) return false;
    }

    if (cityVal !== "ALL") {
      if ((lot.city || "").toLowerCase().trim() !== cityVal.toLowerCase().trim()) return false;
    }

    if (sizeVal === "INFILL") {
      const acres = lot.lot_acres || 0;
      if (acres < 0.08 || acres > 0.55) return false;
    } else if (sizeVal === "SUB_HALF") {
      if ((lot.lot_acres || 0) > 0.50) return false;
    } else if (sizeVal === "LARGE") {
      if ((lot.lot_acres || 0) <= 0.50) return false;
    }

    if (contactVal === "NEW") {
      if (lot.doorbell_sent || lot.loi_sent || (lot.messages && lot.messages.length > 0)) return false;
    } else if (contactVal === "CONTACTED") {
      if (!lot.doorbell_sent && (!lot.messages || lot.messages.length === 0)) return false;
    } else if (contactVal === "REPLIED") {
      const hasInbound = (lot.messages || []).some(m => m.direction === "INBOUND");
      if (!hasInbound) return false;
    } else if (contactVal === "LOI_SENT") {
      if (!lot.loi_sent) return false;
    } else if (contactVal === "UNDERWRITTEN") {
      const uw = lot.underwriting || {};
      if (!uw.passes_send_rule) return false;
    }

    return true;
  });

  const countDisplay = document.getElementById("lotCountDisplay");
  if (countDisplay) {
    countDisplay.innerText = `Showing ${filtered.length} of ${allLots.length} infill lots`;
  }

  const filterBadge = document.getElementById("lotFilteredBadge");
  const isFiltered = query || contactVal !== "ALL" || countyVal !== "ALL" || cityVal !== "ALL" || sizeVal !== "INFILL";
  if (filterBadge) {
    filterBadge.classList.toggle("hidden", !isFiltered);
  }

  const resetBtn = document.getElementById("btnResetLotFilters");
  if (resetBtn) {
    resetBtn.classList.toggle("hidden", !isFiltered);
  }

  renderLots(filtered);
}

function resetLotFilters() {
  const s = document.getElementById("lotSearchInput"); if (s) s.value = "";
  const ct = document.getElementById("lotContactFilter"); if (ct) ct.value = "ALL";
  const co = document.getElementById("lotCountyFilter"); if (co) co.value = "ALL";
  const sz = document.getElementById("lotSizeFilter"); if (sz) sz.value = "INFILL";
  populateLotCityDropdown();
  filterLotsList();
}

function toggleLotCard(lotId) {
  if (lotExpandedCards.has(lotId)) {
    lotExpandedCards.delete(lotId);
  } else {
    lotExpandedCards.add(lotId);
  }
  const el = document.getElementById(`lotDetails_${lotId}`);
  const btn = document.getElementById(`lotToggleBtn_${lotId}`);
  if (el) el.classList.toggle("hidden", !lotExpandedCards.has(lotId));
  if (btn) btn.innerHTML = lotExpandedCards.has(lotId) ? "▲ Less" : "▼ Details";
}

function toggleAllLotCards() {
  const shouldExpand = lotExpandedCards.size === 0;
  if (shouldExpand) {
    allLots.forEach(l => lotExpandedCards.add(l.id));
  } else {
    lotExpandedCards.clear();
  }
  allLots.forEach(l => {
    const el = document.getElementById(`lotDetails_${l.id}`);
    const btn = document.getElementById(`lotToggleBtn_${l.id}`);
    if (el) el.classList.toggle("hidden", !shouldExpand);
    if (btn) btn.innerHTML = shouldExpand ? "▲ Less" : "▼ Details";
  });
  const topBtn = document.getElementById("btnToggleAllLots");
  if (topBtn) topBtn.innerHTML = shouldExpand ? "<span>⛶ Collapse All</span>" : "<span>⛶ Expand All</span>";
}

function toggleLotThread(lotId) {
  if (lotExpandedThreads.has(lotId)) {
    lotExpandedThreads.delete(lotId);
  } else {
    lotExpandedThreads.add(lotId);
  }
  const el = document.getElementById(`lotThread_${lotId}`);
  if (el) el.classList.toggle("hidden", !lotExpandedThreads.has(lotId));
}

function renderLots(lots) {
  const container = document.getElementById("lotsContainer");
  if (!container) return;

  if (lots.length === 0) {
    container.innerHTML = `
      <div class="p-12 text-center bg-slate-900/60 border border-slate-800 rounded-2xl space-y-3">
        <div class="text-3xl">📐</div>
        <h3 class="text-base font-bold text-white">No Infill Lots Found</h3>
        <p class="text-xs text-slate-400 max-w-md mx-auto">
          No lots match your active filters. Try adjusting your county or size filter, or upload a county MLS/Redfin land CSV to populate Lana's desk.
        </p>
        <div class="flex items-center justify-center gap-2 pt-2">
          <button type="button" onclick="openAddLotModal()" class="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold transition cursor-pointer">
            ➕ Add Lot Manually
          </button>
          <button type="button" onclick="document.getElementById('lotCsvFileInput').click()" class="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-emerald-300 text-xs font-bold border border-slate-700 transition cursor-pointer">
            📁 Ingest CSV
          </button>
        </div>
      </div>
    `;
    return;
  }

  container.innerHTML = lots.map(lot => {
    const uw = lot.underwriting || {};
    const asking = lot.list_price || 0;
    const offerPrice = uw.offer_price || Math.round(asking * 0.60);
    const maxPayable = uw.max_payable || 0;
    const passesRule = uw.passes_send_rule !== undefined ? uw.passes_send_rule : (offerPrice <= maxPayable);
    const finishedValue = uw.finished_newbuild_value || 0;
    const buildPsf = uw.build_cost_psf || 165;
    const plannedSqft = uw.planned_sqft || 2000;

    const isExpanded = lotExpandedCards.has(lot.id);
    const isThreadExpanded = lotExpandedThreads.has(lot.id);

    // Status Pill
    let statusPill = "";
    if (lot.loi_sent) {
      statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">📄 Standing LOI Sent</span>`;
    } else if (lot.doorbell_sent) {
      statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40">📱 Doorbell Sent</span>`;
    } else if (passesRule) {
      statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">✅ 60% Offer ≤ Max Residual</span>`;
    } else {
      statusPill = `<span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40">⚠️ Spread Deficit (Offer > Max)</span>`;
    }

    const messages = lot.messages || [];
    const hasReplies = messages.some(m => m.direction === "INBOUND");
    const photoUrl = lot.photo_url || 'https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=600&q=80';

    return `
      <div class="bg-slate-900/90 border border-slate-800 hover:border-emerald-500/40 rounded-2xl p-4 sm:p-5 transition shadow-md space-y-4" id="lotCard_${lot.id}">
        <!-- Top Bar: Thumbnail & Address & Badges -->
        <div class="flex flex-wrap items-start justify-between gap-3">
          <div class="flex items-start gap-3 flex-1 min-w-[260px]">
            <!-- Property Thumbnail -->
            <div class="w-16 h-16 sm:w-20 sm:h-20 rounded-xl overflow-hidden border border-slate-700/80 flex-shrink-0 bg-slate-950 relative shadow-inner">
              <img src="${escapeHtml(photoUrl)}" alt="${escapeHtml(lot.address || 'Infill Lot')}" class="w-full h-full object-cover" onerror="this.src='https://images.unsplash.com/photo-1500382017468-9049fed747ef?auto=format&fit=crop&w=600&q=80'">
              <div class="absolute bottom-1 right-1 bg-slate-950/80 px-1.5 py-0.5 rounded text-[9px] font-mono text-slate-300">
                ${lot.days_on_market || 0}d DOM
              </div>
            </div>

            <div class="space-y-1 flex-1 min-w-0">
              <div class="flex flex-wrap items-center gap-2">
                <span class="text-base font-bold text-white">${escapeHtml(lot.address || 'Vacant Land')}</span>
                ${lot.redfin_url ? `<a href="${escapeHtml(lot.redfin_url)}" target="_blank" onclick="event.stopPropagation()" class="text-xs text-amber-400 hover:text-amber-300 hover:underline inline-flex items-center gap-0.5 font-normal ml-0.5" title="View listing on Redfin"><span>Redfin</span> ↗</a>` : ''}
                ${statusPill}
                ${hasReplies ? '<span class="px-2 py-0.5 rounded-full text-[10px] font-mono font-bold bg-purple-500/20 text-purple-300 border border-purple-500/40 animate-pulse">📥 Inbound Reply</span>' : ''}
              </div>
              <div class="flex flex-wrap items-center gap-2 text-xs text-slate-400">
                <span>📍 ${escapeHtml(lot.city || '')}, ${escapeHtml(lot.county || '')} FL ${escapeHtml(lot.zip || '')}</span>
                <span>&bull;</span>
                <span>📏 ${lot.lot_acres ? lot.lot_acres + ' AC' : ''} (${(lot.lot_sqft || 0).toLocaleString()} sqft)</span>
                <span>&bull;</span>
                <span class="text-amber-300 font-semibold">⏳ ${lot.days_on_market || 0} DOM</span>
                ${lot.parcel_id ? `<span>&bull;</span> <span class="font-mono text-slate-500 text-[11px]">APN: ${escapeHtml(lot.parcel_id)}</span>` : ''}
                ${lot.zoning ? `<span>&bull;</span> <span class="text-slate-400">Zoning: ${escapeHtml(lot.zoning)}</span>` : ''}
              </div>
            </div>
          </div>

          <!-- Quick Action Buttons Top Right -->
          <div class="flex items-center gap-1.5 flex-wrap">
            <button type="button" id="lotToggleBtn_${lot.id}" onclick="toggleLotCard('${lot.id}')" class="px-2.5 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-semibold transition cursor-pointer">
              ${isExpanded ? '▲ Less' : '▼ Details'}
            </button>
            <button type="button" onclick="deleteLot('${lot.id}')" class="p-1.5 rounded-xl bg-slate-800/60 hover:bg-rose-500/20 text-slate-400 hover:text-rose-300 transition cursor-pointer" title="Delete Lot">
              🗑️
            </button>
          </div>
        </div>

        <!-- Underwriting & Price Metrics Grid -->
        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2.5 bg-slate-950/70 p-3 rounded-xl border border-slate-800/80 text-xs font-mono">
          <div>
            <div class="text-[10px] text-slate-500 font-sans uppercase">Asking Price</div>
            <div class="text-sm font-bold text-amber-300 mt-0.5">$${Math.round(asking).toLocaleString()}</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-500 font-sans uppercase">Target Cash Offer</div>
            <div class="text-sm font-bold text-white mt-0.5">$${Math.round(offerPrice).toLocaleString()}</div>
          </div>
          <div class="bg-emerald-950/20 border border-emerald-500/20 rounded-lg p-1">
            <div class="text-[10px] text-emerald-400 font-sans uppercase font-semibold">Max Allowable Basis</div>
            <div class="text-sm font-black text-emerald-300 mt-0.5">$${Math.round(maxPayable).toLocaleString()}</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-500 font-sans uppercase">New-Build Target</div>
            <div class="text-xs font-bold text-slate-300 mt-0.5">$${Math.round(finishedValue).toLocaleString()}</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-500 font-sans uppercase">Build $/SqFt</div>
            <div class="text-xs font-bold text-slate-300 mt-0.5">$${buildPsf}/sqft (${plannedSqft}sf)</div>
          </div>
          <div>
            <div class="text-[10px] text-slate-500 font-sans uppercase">Viability Send Rule</div>
            <div class="text-xs font-bold ${passesRule ? 'text-emerald-400' : 'text-rose-400'} mt-0.5">
              ${passesRule ? '✅ VIABLE' : '⚠️ DEFICIT'}
            </div>
          </div>
        </div>

        <!-- Agent Details & Direct Actions Bar -->
        <div class="flex flex-wrap items-center justify-between gap-3 pt-1 border-t border-slate-800/60">
          <div class="flex flex-wrap items-center gap-3 text-xs">
            <div class="flex items-center gap-1.5">
              <span class="text-slate-400 font-semibold">Agent:</span>
              <strong class="text-white">${escapeHtml(lot.agent_name || 'Listing Agent')}</strong>
              <span class="text-slate-500">(${escapeHtml(lot.brokerage || 'Brokerage')})</span>
            </div>
            <div class="flex items-center gap-1.5">
              <span class="text-slate-400">Cell:</span>
              ${lot.agent_phone ? `
                <a href="tel:${escapeHtml(lot.agent_phone)}" class="text-emerald-300 font-mono font-bold hover:underline">
                  ${escapeHtml(lot.agent_phone)}
                </a>
                <button type="button" onclick="quickEditLotPhone('${lot.id}')" class="text-[10px] text-slate-500 hover:text-emerald-300 px-1" title="Edit Phone Number">✏️</button>
                ${lot.phone_lookup_source ? `<span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 font-mono">${escapeHtml(lot.phone_lookup_source)}</span>` : ''}
              ` : `
                <span class="text-rose-400 italic font-mono text-[11px]">Missing Phone</span>
                <button type="button" onclick="quickEditLotPhone('${lot.id}')" class="px-2 py-0.5 rounded-md bg-amber-500/15 hover:bg-amber-500/25 border border-amber-500/30 text-amber-300 text-[10px] font-bold transition flex items-center gap-1 cursor-pointer" title="Manually type agent phone">
                  <span>📱 + Add</span>
                </button>
                <button type="button" id="btn_lookup_lot_${lot.id}" onclick="lookupLotPhone('${lot.id}')" class="px-2 py-0.5 rounded-md bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-300 text-[10px] font-bold transition flex items-center gap-1 cursor-pointer" title="Auto-find phone on Redfin & Google/Realtor.com">
                  <span>⚡ Find Phone</span>
                </button>
                ${lot.agent_name && lot.agent_name !== 'Listing Agent' ? `
                  <a href="https://www.google.com/search?q=${encodeURIComponent((lot.agent_name || '') + ' ' + (lot.brokerage || '') + ' ' + (lot.city || '') + ' FL realtor phone number')}" target="_blank" class="text-[10px] text-slate-400 hover:text-amber-300 underline" title="Search Google directly">
                    Google ↗
                  </a>
                ` : ''}
              `}
            </div>
            ${lot.agent_email ? `
              <div class="flex items-center gap-1">
                <span class="text-slate-400">Email:</span>
                <span class="text-slate-300 font-mono text-[11px]">${escapeHtml(lot.agent_email)}</span>
              </div>
            ` : ''}
          </div>

          <!-- Desk Action Buttons -->
          <div class="flex items-center gap-2 flex-wrap">
            <button type="button" onclick="sendLotDoorbell('${lot.id}')" class="px-3 py-1.5 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm" title="Send direct cash offer SMS with 21-day close">
              <span>💬 Send Offer SMS</span>
            </button>
            <button type="button" onclick="sendLotFormalLoiSms('${lot.id}')" class="px-3 py-1.5 rounded-xl bg-teal-600/20 hover:bg-teal-600/30 text-teal-300 border border-teal-500/30 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm" title="Send full written LOI terms via SMS text">
              <span>📱 LOI via Text</span>
            </button>
            <button type="button" onclick="sendLotFormalLoiEmail('${lot.id}')" class="px-3 py-1.5 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm" title="Send formal written LOI email with full commission protected">
              <span>✉️ LOI via Email</span>
            </button>
            <button type="button" onclick="openUnderwriteLotModal('${lot.id}')" class="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 text-xs font-semibold transition flex items-center gap-1 cursor-pointer">
              <span>📐 Underwrite</span>
            </button>
            <button type="button" onclick="openLotInboundModal('${lot.id}')" class="px-3 py-1.5 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/30 text-xs font-semibold transition flex items-center gap-1 cursor-pointer" title="Simulate agent response to test Lana's objection handler">
              <span>💬 Test Inbound</span>
            </button>
            ${messages.length > 0 ? `
              <button type="button" onclick="toggleLotThread('${lot.id}')" class="px-2.5 py-1.5 rounded-xl bg-slate-800/80 hover:bg-slate-700 text-slate-300 text-xs font-semibold border border-slate-700 transition cursor-pointer">
                🧵 Thread (${messages.length})
              </button>
            ` : ''}
          </div>
        </div>

        <!-- Collapsible Details Section -->
        <div id="lotDetails_${lot.id}" class="${isExpanded ? '' : 'hidden'} space-y-3 pt-3 border-t border-slate-800 text-xs">
          ${lot.remarks ? `
            <div class="bg-slate-950/80 p-3 rounded-xl border border-slate-800">
              <strong class="text-slate-300 block mb-1">Public Remarks &amp; Features:</strong>
              <p class="text-slate-400 text-[11px] leading-relaxed">${escapeHtml(lot.remarks)}</p>
            </div>
          ` : ''}

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 text-slate-400 bg-slate-950/50 p-3 rounded-xl border border-slate-800/80">
            <div>
              <strong class="text-slate-300">Underwriting Rationale:</strong>
              <p class="mt-1 text-[11px]">
                Targeting new build resale of <strong>$${Math.round(finishedValue).toLocaleString()}</strong>. Standard structure cost: <strong>$${buildPsf}/sqft</strong> for a <strong>${plannedSqft} sqft</strong> home. Max allowable land basis: <strong>$${Math.round(maxPayable).toLocaleString()}</strong>.
              </p>
            </div>
            <div>
              <strong class="text-slate-300">Proposed Contract Terms:</strong>
              <ul class="mt-1 space-y-0.5 text-[11px] list-disc list-inside">
                <li>$2,500 Earnest Money deposited upon contract</li>
                <li>14-day feasibility study (survey &amp; utility checks)</li>
                <li>${lot.close_days || 21}-day cash closing with verified funds</li>
                <li>Full listing agent commission protected</li>
              </ul>
            </div>
          </div>
        </div>

        <!-- Collapsible SMS Conversation Thread -->
        <div id="lotThread_${lot.id}" class="${isThreadExpanded ? '' : 'hidden'} space-y-2 pt-2 border-t border-slate-800">
          <strong class="text-slate-300 text-xs block">SMS Conversation History:</strong>
          <div class="space-y-2 max-h-60 overflow-y-auto p-2 rounded-xl bg-slate-950/90 border border-slate-800">
            ${messages.map(m => {
              const isOut = m.direction === "OUTBOUND";
              return `
                <div class="flex ${isOut ? 'justify-end' : 'justify-start'}">
                  <div class="max-w-[80%] p-2.5 rounded-xl text-xs ${isOut ? 'bg-emerald-950/60 border border-emerald-500/30 text-emerald-200' : 'bg-slate-800 text-slate-200'}">
                    <div class="flex items-center justify-between gap-2 text-[10px] text-slate-400 mb-1">
                      <span class="font-bold">${isOut ? 'Lana (Outbound)' : escapeHtml(lot.agent_name || 'Agent')}</span>
                      <span>${escapeHtml(m.timestamp || '')}</span>
                    </div>
                    <p>${escapeHtml(m.text || '')}</p>
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------------------
// UNDERWRITING MODAL HANDLERS
// -------------------------------------------------------------------------

function openUnderwriteLotModal(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  if (!lot) return;

  currentEditingLotId = lotId;
  const modal = document.getElementById("underwriteLotModal");
  if (!modal) return;

  const uw = lot.underwriting || {};
  const asking = lot.list_price || 0;
  const offerPrice = uw.offer_price || Math.round(asking * 0.60);

  document.getElementById("underwriteLotId").value = lotId;
  document.getElementById("uwLotAddress").innerText = lot.address || "Vacant Lot";
  document.getElementById("uwLotDetails").innerText = `${lot.city || ''}, ${lot.county || ''} FL • ${lot.lot_acres || ''} AC`;
  document.getElementById("uwLotListPrice").innerText = `$${Math.round(asking).toLocaleString()}`;
  document.getElementById("uwLotOfferPrice").innerText = `$${Math.round(offerPrice).toLocaleString()}`;

  document.getElementById("uwFinishedValue").value = uw.finished_newbuild_value || Math.round(asking * 3.5);
  document.getElementById("uwPlannedSqft").value = uw.planned_sqft || 2000;
  document.getElementById("uwBuildCostPsf").value = uw.build_cost_psf || 165;
  document.getElementById("uwProfitPct").value = uw.builder_profit_pct !== undefined ? uw.builder_profit_pct : 0.18;
  document.getElementById("uwFeesPct").value = uw.fees_pct !== undefined ? uw.fees_pct : 0.04;

  calculateLotResidualLive();
  openModal("underwriteLotModal");
}

function calculateLotResidualLive() {
  const finishedVal = parseFloat(document.getElementById("uwFinishedValue").value) || 0;
  const sqft = parseFloat(document.getElementById("uwPlannedSqft").value) || 2000;
  const buildPsf = parseFloat(document.getElementById("uwBuildCostPsf").value) || 165;
  const profitPct = parseFloat(document.getElementById("uwProfitPct").value) || 0.18;
  const feesPct = parseFloat(document.getElementById("uwFeesPct").value) || 0.04;

  const totalBuildCost = buildPsf * sqft;
  const builderMargin = finishedVal * profitPct;
  const fees = finishedVal * feesPct;
  const maxPayable = Math.max(0, finishedVal - totalBuildCost - builderMargin - fees);

  const lot = allLots.find(l => l.id === currentEditingLotId);
  const asking = lot ? (lot.list_price || 0) : 0;
  const offerPrice = Math.round(asking * 0.60);
  const isViable = offerPrice <= maxPayable;

  document.getElementById("calcTotalBuildCost").innerText = `$${Math.round(totalBuildCost).toLocaleString()}`;
  document.getElementById("calcBuilderMargin").innerText = `$${Math.round(builderMargin).toLocaleString()}`;
  document.getElementById("calcFees").innerText = `$${Math.round(fees).toLocaleString()}`;
  document.getElementById("calcMaxPayable").innerText = `$${Math.round(maxPayable).toLocaleString()}`;

  const badge = document.getElementById("uwViabilityBadge");
  if (badge) {
    if (isViable) {
      badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/20 text-emerald-300 border border-emerald-500/40";
      badge.innerText = `PASS: 60% Offer ($${offerPrice.toLocaleString()}) ≤ Max Payable ($${Math.round(maxPayable).toLocaleString()})`;
    } else {
      badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/40";
      badge.innerText = `DEFICIT: 60% Offer ($${offerPrice.toLocaleString()}) > Max Payable ($${Math.round(maxPayable).toLocaleString()})`;
    }
  }
}

async function saveLotUnderwritingFromModal() {
  const lotId = document.getElementById("underwriteLotId").value;
  if (!lotId) return;

  const finishedVal = parseFloat(document.getElementById("uwFinishedValue").value) || 0;
  const sqft = parseFloat(document.getElementById("uwPlannedSqft").value) || 2000;
  const profitPct = parseFloat(document.getElementById("uwProfitPct").value) || 0.18;
  const feesPct = parseFloat(document.getElementById("uwFeesPct").value) || 0.04;

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/underwrite`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        finished_newbuild_value: finishedVal,
        planned_sqft: sqft,
        builder_profit_pct: profitPct,
        fees_pct: feesPct
      })
    });
    const d = await res.json();
    if (d.status === "success") {
      closeModal("underwriteLotModal");
      await loadLots();
    } else {
      alert("Error saving underwriting: " + (d.message || "Unknown error"));
    }
  } catch (err) {
    alert("Error saving underwriting: " + err.message);
  }
}

// -------------------------------------------------------------------------
// SMS DOORBELL & EMAIL FORMAL LOI DISPATCH
// -------------------------------------------------------------------------

async function sendLotDoorbell(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  if (!lot) return;

  if (!lot.agent_phone) {
    if (confirm("Agent has no phone number on file. Would you like to enter it now?")) {
      await quickEditLotPhone(lotId);
    }
    return;
  }

  const promptMsg = `Send Lana's Doorbell SMS to ${lot.agent_name || 'Agent'} (${lot.agent_phone}) for ${lot.address}?`;
  if (!confirm(promptMsg)) return;

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/send-sms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("✓ Doorbell SMS sent successfully!");
      await loadLots();
    } else {
      alert("Failed to send Doorbell SMS: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error sending SMS: " + err.message);
  }
}

async function sendLotFormalLoiSms(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  if (!lot) return;

  const phonePrompt = prompt(`Enter listing agent phone number for written LOI via text:`, lot.agent_phone || "");
  if (phonePrompt === null) return;
  const recipientPhone = phonePrompt.trim();
  if (!recipientPhone) {
    alert("Phone number is required to dispatch LOI via SMS.");
    return;
  }

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/send-loi-sms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: recipientPhone, close_days: 21 })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("✓ Written LOI terms dispatched directly via SMS text!");
      await loadLots();
    } else {
      alert("Failed to send LOI SMS: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error sending LOI SMS: " + err.message);
  }
}

async function sendLotFormalLoiEmail(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  if (!lot) return;

  const emailPrompt = prompt(`Enter listing agent email address for written LOI:`, lot.agent_email || "");
  if (emailPrompt === null) return;
  const recipientEmail = emailPrompt.trim();
  if (!recipientEmail) {
    alert("Email address is required to dispatch formal LOI.");
    return;
  }

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/send-loi-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_email: recipientEmail, close_days: 21 })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert("✓ Written LOI sent via email and SMS notification dispatched!");
      await loadLots();
    } else {
      alert("Failed to send LOI email: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error sending LOI: " + err.message);
  }
}

// -------------------------------------------------------------------------
// INBOUND SIMULATION MODAL
// -------------------------------------------------------------------------

function openLotInboundModal(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  if (!lot) return;

  document.getElementById("lotInboundLotId").value = lotId;
  document.getElementById("lotInboundSubtitle").innerText = `Testing Lana Engine on ${lot.address || 'Lot'}`;
  document.getElementById("lotInboundMessage").value = "";
  document.getElementById("lotInboundResultBox").classList.add("hidden");

  openModal("lotInboundModal");
}

function setLotInboundPreset(text) {
  document.getElementById("lotInboundMessage").value = text;
  submitLotInbound();
}

async function submitLotInbound() {
  const lotId = document.getElementById("lotInboundLotId").value;
  const msg = document.getElementById("lotInboundMessage").value.trim();
  if (!msg) {
    alert("Please enter a listing agent message to test.");
    return;
  }

  const btn = document.getElementById("btnSubmitLotInbound");
  if (btn) {
    btn.disabled = true;
    btn.innerText = "Analyzing...";
  }

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/inbound`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg })
    });
    const d = await res.json();
    if (d.status === "success") {
      const box = document.getElementById("lotInboundResultBox");
      document.getElementById("lotInboundNodeBadge").innerText = d.node || "RESPONSE";
      document.getElementById("lotInboundReason").innerText = d.reason || "";
      document.getElementById("lotInboundSuggestedReply").innerText = d.suggested_reply || "";
      box.classList.remove("hidden");
      await loadLots();
    } else {
      alert("Evaluation failed: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error analyzing inbound: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "🧠 Analyze with Lana Engine";
    }
  }
}

// -------------------------------------------------------------------------
// FRIDAY SEQUENCE MODAL
// -------------------------------------------------------------------------

async function openFridaySequenceModal() {
  openModal("fridaySequenceModal");
  const listEl = document.getElementById("fridaySequenceList");
  listEl.innerHTML = `<div class="text-center py-6 text-slate-500"><span class="inline-block animate-spin mr-2">⏳</span> Scanning lots for Friday follow-ups...</div>`;

  try {
    const res = await fetch("/api/lana/run-friday-sequence", { method: "POST" });
    const d = await res.json();
    const items = d.results || [];
    if (items.length === 0) {
      listEl.innerHTML = `<div class="p-6 text-center text-slate-500 bg-slate-950 rounded-xl">No active lots currently need Friday check-ins. Send initial offers first!</div>`;
      return;
    }

    listEl.innerHTML = items.map((item, idx) => `
      <div class="bg-slate-950 p-3.5 rounded-xl border border-slate-800 space-y-2">
        <div class="flex items-center justify-between text-[11px]">
          <strong class="text-white">${idx + 1}. ${escapeHtml(item.address || 'Lot')}</strong>
          <span class="text-emerald-400 font-mono font-bold">$${Math.round(item.offer_price || 0).toLocaleString()} Cash</span>
        </div>
        <div class="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-200 text-xs">
          ${escapeHtml(item.friday_sms || '')}
        </div>
      </div>
    `).join('');
  } catch (err) {
    listEl.innerHTML = `<div class="p-4 rounded-xl bg-rose-500/20 text-rose-300">Error: ${escapeHtml(err.message)}</div>`;
  }
}

async function runFridaySequence() {
  openFridaySequenceModal();
}

// -------------------------------------------------------------------------
// MULTI-LOT AGENT CONSOLIDATION
// -------------------------------------------------------------------------

function openConsolidateModal() {
  openModal("consolidateAgentModal");
  const listEl = document.getElementById("consolidateAgentList");

  // Group lots by agent_name
  const agentGroups = {};
  allLots.forEach(l => {
    const name = (l.agent_name || "Listing Agent").trim();
    if (!agentGroups[name]) agentGroups[name] = [];
    agentGroups[name].push(l);
  });

  const multiAgents = Object.keys(agentGroups).filter(name => agentGroups[name].length > 1);

  if (multiAgents.length === 0) {
    listEl.innerHTML = `
      <div class="p-8 text-center text-slate-500 bg-slate-950 rounded-xl space-y-2">
        <div class="text-2xl">📑</div>
        <p>No agents with 2 or more lots detected yet.</p>
        <p class="text-[11px] text-slate-600">When multiple lots share the same listing agent, Lana bundles them into a portfolio LOI text.</p>
      </div>
    `;
    return;
  }

  listEl.innerHTML = multiAgents.map(name => {
    const lots = agentGroups[name];
    const totalList = lots.reduce((acc, l) => acc + (l.list_price || 0), 0);
    const totalOffer = lots.reduce((acc, l) => acc + ((l.underwriting && l.underwriting.offer_price) || (l.list_price * 0.60)), 0);

    return `
      <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 space-y-3">
        <div class="flex items-center justify-between">
          <div>
            <h4 class="text-sm font-bold text-white">${escapeHtml(name)}</h4>
            <span class="text-[11px] text-slate-400">${lots.length} active lots listed • Combined Asking: $${Math.round(totalList).toLocaleString()}</span>
          </div>
          <button type="button" onclick="runConsolidateAgent('${escapeHtml(name)}')" class="px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-bold transition cursor-pointer">
            📑 Generate Portfolio Offer
          </button>
        </div>
        <div class="space-y-1 text-xs">
          ${lots.map(l => `
            <div class="flex items-center justify-between text-slate-300 py-1 border-t border-slate-900">
              <span>📍 ${escapeHtml(l.address)} (${l.lot_acres || ''} AC)</span>
              <span class="font-mono text-amber-300">$${Math.round(l.list_price || 0).toLocaleString()}</span>
            </div>
          `).join('')}
        </div>
        <div class="pt-2 border-t border-slate-800 flex items-center justify-between text-xs font-bold text-emerald-400">
          <span>Combined 60% Portfolio Cash Offer:</span>
          <span class="font-mono text-sm">$${Math.round(totalOffer).toLocaleString()}</span>
        </div>
      </div>
    `;
  }).join('');
}

async function runConsolidateAgent(agentName) {
  try {
    const res = await fetch("/api/lana/consolidate-agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ agent_name: agentName, close_days: 14 })
    });
    const d = await res.json();
    if (d.status === "success") {
      alert(`Consolidated Portfolio SMS Text for ${agentName}:\n\n` + d.sms_text);
    } else {
      alert("Error: " + (d.message || "Failed to generate"));
    }
  } catch (err) {
    alert("Error: " + err.message);
  }
}

// -------------------------------------------------------------------------
// ADD LOT MANUALLY & CSV INGEST
// -------------------------------------------------------------------------

function openAddLotModal() {
  openModal("addLotModal");
}

async function submitAddLot() {
  const address = document.getElementById("addLotAddress").value.trim();
  if (!address) {
    alert("Property address is required.");
    return;
  }

  const payload = {
    address: address,
    city: document.getElementById("addLotCity").value.trim() || "Orlando",
    county: document.getElementById("addLotCounty").value.trim() || "ORANGE",
    zip: document.getElementById("addLotZip").value.trim() || "",
    list_price: parseFloat(document.getElementById("addLotPrice").value) || 110000,
    lot_acres: parseFloat(document.getElementById("addLotAcres").value) || 0.20,
    days_on_market: parseInt(document.getElementById("addLotDom").value) || 60,
    agent_name: document.getElementById("addLotAgentName").value.trim() || "Listing Agent",
    agent_phone: document.getElementById("addLotAgentPhone").value.trim() || "",
    agent_email: document.getElementById("addLotAgentEmail").value.trim() || "",
    brokerage: document.getElementById("addLotBrokerage").value.trim() || "",
    remarks: document.getElementById("addLotRemarks").value.trim() || ""
  };

  try {
    const res = await fetch("/api/lana/lots", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const d = await res.json();
    if (d.status === "success") {
      closeModal("addLotModal");
      await loadLots();
      alert("✓ Infill lot added to Lana's Desk!");
    } else {
      alert("Failed to add lot: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error adding lot: " + err.message);
  }
}

async function handleLotCsvUpload(input) {
  const file = input.files && input.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);
  input.value = "";

  try {
    const res = await fetch("/api/lana/lots/upload-csv", {
      method: "POST",
      body: formData
    });
    const d = await res.json();
    if (d.status === "success") {
      alert(`✓ Ingested ${d.ingested ?? d.added_count} infill lots into Lana's Desk (${d.filtered_out || 0} filtered out).`);
      await loadLots();
    } else {
      alert("CSV upload failed: " + (d.message || d.detail || "Error"));
    }
  } catch (err) {
    alert("Error uploading CSV: " + err.message);
  }
}

// -------------------------------------------------------------------------
// PHONE QUICK EDIT & CLEAR DESK
// -------------------------------------------------------------------------

async function quickEditLotPhone(lotId) {
  const lot = allLots.find(l => l.id === lotId);
  const currentPhone = lot ? (lot.agent_phone || "") : "";
  const newPhone = prompt("Enter listing agent cell phone:", currentPhone);
  if (newPhone === null) return;

  try {
    const res = await fetch(`/api/lana/lots/${lotId}/phone`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ phone: newPhone.trim() })
    });
    const d = await res.json();
    if (d.status === "success") {
      if (lot) lot.agent_phone = newPhone.trim();
      filterLotsList();
    } else {
      alert("Failed to update phone: " + (d.message || "Error"));
    }
  } catch (err) {
    alert("Error updating phone: " + err.message);
  }
}
window.quickEditLotPhone = quickEditLotPhone;

async function lookupLotPhone(lotId) {
  const lot = (allLots || []).find(l => l.id === lotId);
  const agentName = lot ? (lot.agent_name || "Agent") : "Agent";
  const brokerage = lot ? (lot.brokerage || "") : "";
  const city = lot ? (lot.city || "") : "";

  const btn = document.getElementById(`btn_lookup_lot_${lotId}`);
  const origHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Searching...</span>`;
  }
  try {
    const res = await fetch(`/api/lana/lots/${lotId}/lookup-phone`, { method: "POST" });
    const d = await res.json();
    if (d.status === "success" && d.phone) {
      if (lot) {
        lot.agent_phone = d.phone;
        if (d.photo_url) lot.photo_url = d.photo_url;
        if (d.agent_name && d.agent_name !== "Listing Agent") lot.agent_name = d.agent_name;
        if (d.brokerage && d.brokerage !== "Local Realty") lot.brokerage = d.brokerage;
      }
      filterLotsList();
    } else {
      const gUrl = `https://www.google.com/search?q=${encodeURIComponent(agentName + ' ' + brokerage + ' ' + city + ' FL realtor phone number')}`;
      if (confirm(`🔍 Redfin/Web lookup didn't find a direct number for ${agentName}.\n\nWould you like to open Google Search to grab their cell phone?`)) {
        window.open(gUrl, '_blank');
        setTimeout(() => {
          quickEditLotPhone(lotId);
        }, 500);
      }
    }
  } catch (err) {
    alert("Lookup error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}
window.lookupLotPhone = lookupLotPhone;

async function lookupAllLotPhones() {
  const btn = document.getElementById("btnLookupAllLotPhones");
  const origHtml = btn ? btn.innerHTML : "";
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `<span>⏳ Finding Phones...</span>`;
  }
  try {
    const res = await fetch("/api/lana/lots/lookup-all-phones", { method: "POST" });
    const d = await res.json();
    await loadLots();
    alert(d.message || "Phone lookup complete!");
  } catch (err) {
    alert("Batch phone lookup error: " + err.message);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = origHtml;
    }
  }
}
window.lookupAllLotPhones = lookupAllLotPhones;

async function deleteLot(lotId) {
  if (!confirm("Are you sure you want to remove this lot from Lana's Desk?")) return;
  try {
    const res = await fetch(`/api/lana/lots/${lotId}`, { method: "DELETE" });
    const d = await res.json();
    if (d.status === "success") {
      allLots = allLots.filter(l => l.id !== lotId);
      filterLotsList();
    }
  } catch (err) {
    alert("Error deleting lot: " + err.message);
  }
}

async function clearEntireLotDesk() {
  if (!confirm("⚠️ Are you sure you want to clear ALL lots from Lana's Desk?")) return;
  try {
    const res = await fetch("/api/lana/lots/clear", { method: "POST" });
    const d = await res.json();
    if (d.status === "success") {
      allLots = [];
      filterLotsList();
      alert("✓ Lana's desk cleared.");
    }
  } catch (err) {
    alert("Error clearing desk: " + err.message);
  }
}

// -------------------------------------------------------------------------
// FLORIDA DOR SDF COMPS & BENCHMARKS
// -------------------------------------------------------------------------

async function openSdfCompsModal() {
  openModal("sdfCompsModal");
  await loadSdfComps();
}

async function loadSdfComps() {
  try {
    const res = await fetch("/api/lana/comps");
    const d = await res.json();

    const counties = Object.keys(d);
    document.getElementById("sdfActiveCounties").innerText = counties.length > 0 ? counties.join(", ") : "None";

    let totalVacant = 0;
    let totalSfh = 0;
    let totalPsf = 0;
    let psfCount = 0;
    let marketAreasHtml = "";

    counties.forEach(countyKey => {
      const c = d[countyKey];
      totalVacant += c.total_vacant_sales || 0;
      totalSfh += c.total_sfh_sales || 0;
      if (c.median_psf) {
        totalPsf += c.median_psf;
        psfCount++;
      }

      const mktAreas = c.market_areas || {};
      Object.keys(mktAreas).forEach(mkKey => {
        const m = mktAreas[mkKey];
        marketAreasHtml += `
          <div class="bg-slate-900 p-2.5 rounded-lg border border-slate-800 flex items-center justify-between text-xs">
            <div>
              <strong class="text-white">${escapeHtml(countyKey)} • Area ${escapeHtml(mkKey)}</strong>
              <div class="text-[10px] text-slate-400 mt-0.5">Vacant: ${m.vacant_count || 0} sales • SFH: ${m.sfh_count || 0} comps</div>
            </div>
            <div class="text-right font-mono">
              <div class="text-emerald-300 font-bold">$${Math.round(m.sfh_median_price || 0).toLocaleString()}</div>
              <div class="text-[10px] text-slate-500">$${Math.round(m.sfh_median_psf || 0)}/sqft</div>
            </div>
          </div>
        `;
      });
    });

    document.getElementById("sdfVacantCount").innerText = totalVacant.toLocaleString();
    document.getElementById("sdfSfhCount").innerText = totalSfh.toLocaleString();
    document.getElementById("sdfMedianPsf").innerText = psfCount > 0 ? `$${Math.round(totalPsf / psfCount)}/sqft` : "$0";

    const mktContainer = document.getElementById("sdfMarketAreasContainer");
    if (mktContainer) {
      mktContainer.innerHTML = marketAreasHtml || `<div class="p-4 text-center text-slate-500">No market areas loaded yet. Run parser below!</div>`;
    }
  } catch (err) {
    console.error("Error loading SDF comps:", err);
  }
}

async function runSdfParserFromModal() {
  const path = document.getElementById("sdfParserPathInput").value.trim();
  const btn = document.getElementById("btnRunSdfParser");
  const alertEl = document.getElementById("sdfParserStatusAlert");

  if (btn) {
    btn.disabled = true;
    btn.innerText = "Parsing...";
  }

  try {
    const res = await fetch("/api/lana/run-sdf-parser", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ directory_or_file: path })
    });
    const d = await res.json();
    if (d.status === "success") {
      alertEl.className = "text-[11px] p-2 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30";
      alertEl.innerText = `✓ Successfully parsed county file! Processed ${d.parsed_count} record groups.`;
      alertEl.classList.remove("hidden");
      await loadSdfComps();
    } else {
      alertEl.className = "text-[11px] p-2 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/30";
      alertEl.innerText = `Error: ${d.message || 'Parser failed'}`;
      alertEl.classList.remove("hidden");
    }
  } catch (err) {
    alertEl.className = "text-[11px] p-2 rounded-lg bg-rose-500/20 text-rose-300 border border-rose-500/30";
    alertEl.innerText = `Error: ${err.message}`;
    alertEl.classList.remove("hidden");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = "Run Parser";
    }
  }
}

// Global window registrations
window.switchDesk = switchDesk;
window.loadLots = loadLots;
window.filterLotsList = filterLotsList;
window.resetLotFilters = resetLotFilters;
window.handleLotCountyFilterChange = handleLotCountyFilterChange;
window.toggleLotCard = toggleLotCard;
window.toggleAllLotCards = toggleAllLotCards;
window.toggleLotThread = toggleLotThread;
window.openUnderwriteLotModal = openUnderwriteLotModal;
window.calculateLotResidualLive = calculateLotResidualLive;
window.saveLotUnderwritingFromModal = saveLotUnderwritingFromModal;
window.sendLotDoorbell = sendLotDoorbell;
window.sendLotFormalLoiSms = sendLotFormalLoiSms;
window.sendLotFormalLoiEmail = sendLotFormalLoiEmail;
window.openLotInboundModal = openLotInboundModal;
window.setLotInboundPreset = setLotInboundPreset;
window.submitLotInbound = submitLotInbound;
window.openFridaySequenceModal = openFridaySequenceModal;
window.runFridaySequence = runFridaySequence;
window.openConsolidateModal = openConsolidateModal;
window.runConsolidateAgent = runConsolidateAgent;
window.openAddLotModal = openAddLotModal;
window.submitAddLot = submitAddLot;
window.handleLotCsvUpload = handleLotCsvUpload;
window.deleteLot = deleteLot;
window.clearEntireLotDesk = clearEntireLotDesk;
window.quickEditLotPhone = quickEditLotPhone;
window.openSdfCompsModal = openSdfCompsModal;
window.loadSdfComps = loadSdfComps;
window.runSdfParserFromModal = runSdfParserFromModal;

