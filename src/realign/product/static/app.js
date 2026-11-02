"use strict";

// Read-only presentation of approved backend evidence. Playback never fits a
// model, invokes a scientific tool, or substitutes one observation source.
(() => {
  const $ = (id) => document.getElementById(id);
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
  const list = (value) => Array.isArray(value) ? value : [];
  const text = (value, fallback = "Unavailable") => typeof value === "string" && value.length ? value : fallback;
  const number = (value, places = 3) => finite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: places, minimumFractionDigits: places }) : "Unavailable";
  const integer = (value) => finite(value) ? value.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "Unavailable";
  const shortHash = (value) => typeof value === "string" && /^[a-f0-9]{64}$/.test(value) ? `${value.slice(0, 12)}…${value.slice(-8)}` : "Unavailable";
  const familyName = (value) => ({ NOMINAL_FREE: "Nominal free pendulum", PARAMETER_FREE: "Parameter mismatch", FREE: "Fitted free pendulum", PEG_ONE_SIDE: "One-peg dynamics", MEASUREMENT: "Measurement quality" }[value] || text(value));
  const policyLabel = (value) => ({ DETERMINISTIC: "DETERMINISTIC", MOCK_POLICY: "MOCK POLICY", LIVE_MUSE: "LIVE MUSE", RECORDED_RESPONSE_REPLAY: "RECORDED RESPONSE REPLAY", SIMULATED_API_FIXTURE: "SIMULATED API FIXTURE" }[value] || text(value, "UNKNOWN POLICY"));
  const modelColors = { B0: "#8b967f", B1: "#bf885b", B3: "#306e59" };
  const modelNames = { B0: "B0 · Nominal free", B1: "B1 · Fitted free", B3: "B3 · Fitted peg" };
  const viewMeta = {
    reality: ["Reality vs Simulation", "Follow the observations, inspect the discrepancy, and see what the model can explain."],
    investigation: ["Investigation", "Trace each hypothesis to the numerical tools and exploration evidence that support it."],
    experiment: ["Experiment Loop", "Inspect the requested action, the evidence it returned, and the second observation round."],
    decision: ["Model Decision", "A proposal becomes a frozen decision only after the independent scientific checks."],
    evidence: ["Evidence", "Inspect provenance, frozen model references, evaluation results and the recorded audit."],
  };
  const state = { source: "synthetic", view: "reality", catalog: null, status: null, external: null, closure: null, run: null, selected: null, round: 1, trial: null, model: "B3", frame: 0, playing: false, lastTick: 0, loadToken: 0, failures: {}, externalFrame: 0 };

  function node(tag, attrs = {}, ...children) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === null || value === false) continue;
      if (key === "class") element.className = value;
      else if (key.startsWith("on") && typeof value === "function") element.addEventListener(key.slice(2).toLowerCase(), value);
      else if (key === "value") element.value = value;
      else if (key === "disabled") element.disabled = Boolean(value);
      else element.setAttribute(key, value === true ? "" : String(value));
    }
    function append(child) {
      if (Array.isArray(child)) child.forEach(append);
      else if (child !== null && child !== undefined && child !== false) element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    children.forEach(append);
    return element;
  }

  function svg(tag, attrs = {}, ...children) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    for (const child of children.flat()) if (child !== null && child !== undefined) element.append(child instanceof Node ? child : document.createTextNode(String(child)));
    return element;
  }

  function button(label, handler, style = "button", attrs = {}) {
    return node("button", { type: "button", class: style, onClick: handler, ...attrs }, label);
  }

  function badge(label, kind = "muted") { return node("span", { class: `badge badge-${kind}` }, label); }
  function heading(title, subtitle, extra) {
    return node("div", { class: "panel-heading" }, node("div", {}, node("h2", {}, title), subtitle ? node("p", {}, subtitle) : null), extra);
  }
  function panel(title, subtitle, content, extra) {
    return node("section", { class: "panel" }, heading(title, subtitle, extra), node("div", { class: "panel-pad" }, content));
  }
  function info(message, warn = false) {
    return node("div", { class: `info-strip${warn ? " warn" : ""}` }, node("span", { class: "info-icon", "aria-hidden": "true" }, warn ? "△" : "ⓘ"), node("span", {}, message));
  }
  function factList(rows) {
    return node("dl", { class: "fact-list" }, rows.map(([key, value]) => node("div", { class: "fact-row" }, node("dt", {}, key), node("dd", {}, value === null || value === undefined ? "Unavailable" : value))));
  }
  function metric(label, value, unit, note, accent = false) {
    return node("div", { class: `metric-card${accent ? " accent" : ""}` }, node("div", { class: "metric-label" }, label),
      node("div", { class: "metric-value" }, value === "Unavailable" ? node("span", { class: "unavailable-label" }, value) : value, unit && value !== "Unavailable" ? node("span", { class: "unit" }, unit) : null),
      note ? node("div", { class: "metric-note" }, note) : null);
  }
  function empty(title, description, symbol = "◈", action = null) {
    return node("section", { class: "empty-state" }, node("div", { class: "empty-symbol", "aria-hidden": "true" }, symbol), node("h2", {}, title), node("p", {}, description), action);
  }
  function statusKind(value) {
    return ["PASS", "VERIFIED", "COMPLETED", "OK", "AVAILABLE", "SYNTHETIC_EXERCISE_PASS", "REAL_PHONE_CONSISTENCY_PASS"].includes(value) ? "green" : ["FAILED", "INVALID", "ERROR", "SYNTHETIC_VALIDATION_FAIL", "REAL_PHONE_VALIDATION_FAIL"].includes(value) ? "red" : "amber";
  }
  function statusBadge(value) { return badge(text(value, "NOT AVAILABLE").replaceAll("_", " "), statusKind(value)); }
  function safeLink(url, label) {
    try {
      const parsed = new URL(url);
      if (parsed.protocol === "https:" && !parsed.username && !parsed.password) return node("a", { href: parsed.href, target: "_blank", rel: "noopener noreferrer" }, label);
    } catch (_) { /* Plain text is appropriate when attribution is incomplete. */ }
    return node("span", {}, label);
  }

  async function requestJSON(path) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(path, { signal: controller.signal, headers: { Accept: "application/json" }, cache: "no-store" });
      if (!response.ok) throw new Error(`Local evidence request returned HTTP ${response.status}.`);
      const body = await response.json();
      if (!object(body)) throw new Error("The evidence response is malformed.");
      const h=body.evidence_header;
      if (!object(h)) throw new Error("Missing evidence_header; unlabelled payload refused.");
      for (const key of ["source_domain","policy","run_id","stage","ladder_level"]) {
        if (typeof h[key]!=="string" || !h[key]) throw new Error(`Missing evidence_header.${key}; unlabelled payload refused.`);
      }
      if (!["SYNTHETIC","REAL_EXTERNAL","REAL_PHONE","AGGREGATE"].includes(h.source_domain)) throw new Error("Invalid evidence source domain.");
      if (body.observation_source && h.source_domain!==body.observation_source) throw new Error("Evidence header source differs from payload provenance.");
      return body;
    } catch (error) {
      if (error && error.name === "AbortError") throw new Error("The local evidence request timed out.");
      if (error instanceof SyntaxError) throw new Error("The local evidence response is not valid JSON.");
      if (error instanceof TypeError) throw new Error("The local evidence endpoint is unavailable.");
      throw error;
    } finally { clearTimeout(timeout); }
  }

  function validXY(values, expected) {
    return Array.isArray(values) && values.length === expected && values.every((point) => Array.isArray(point) && point.length === 2 && point.every((v) => v === null || finite(v)));
  }
  function checkRun(run) {
    if (run.status && run.status !== "COMPLETED" && !run.decision) return run;
    if (!object(run.decision) || !Array.isArray(run.rounds) || !Array.isArray(run.trials) || !object(run.integrity)) throw new Error("The recorded investigation is missing required evidence fields.");
    if (!run.rounds.length || run.rounds.some((round) => !object(round) || ![1, 2].includes(round.round) || !Array.isArray(round.hypotheses) || round.hypotheses.some((hypothesis) => !object(hypothesis)))) throw new Error("The recorded investigation has malformed observation rounds.");
    if (!Array.isArray(run.tool_calls) || run.tool_calls.some((call) => !object(call))) throw new Error("The recorded scientific tool log is malformed.");
    for (const trial of run.trials) {
      if (!object(trial) || typeof trial.id !== "string" || !["exploration", "development"].includes(trial.zone) || !Array.isArray(trial.t_s) || !trial.t_s.every(finite) || trial.t_s.length > 10000 || !validXY(trial.xy_px, trial.t_s.length) || !Array.isArray(trial.valid) || trial.valid.length !== trial.t_s.length || !trial.valid.every((v) => typeof v === "boolean")) throw new Error("A recorded trajectory is malformed; it has not been plotted.");
      if (trial.t_s.some((t, i) => i > 0 && t <= trial.t_s[i - 1])) throw new Error("A recorded trajectory has invalid timestamps.");
      if (trial.xy_px.some((point, i) => trial.valid[i] && !point.every(finite))) throw new Error("A valid observation has no finite measured center.");
    }
    if (run.observation_source !== "SYNTHETIC") throw new Error("This investigation view requires explicitly synthetic evidence. Real observations use their own source view.");
    if (run.playback !== "RECORDED_ARTIFACT") throw new Error("The response is not a recorded evidence artifact.");
    if (run.integrity.status !== "VERIFIED" || !object(run.audit) || run.audit.verified !== true) throw new Error("Recorded evidence integrity has not been verified. Model results have not been displayed.");
    return run;
  }

  function renderNotices() {
    $("notices").replaceChildren();
    for (const [key, message] of Object.entries(state.failures)) {
      if (key === "run") continue;
      $("notices").append(node("div", { class: "notice" }, node("p", {}, message), button("Retry", () => loadApp(), "button button-small")));
    }
  }

  async function loadApp() {
    const responses = await Promise.allSettled([requestJSON("/api/catalog"), requestJSON("/api/status"), requestJSON("/api/external"), requestJSON("/api/closure"), requestJSON("/api/release")]);
    const keys = ["catalog", "status", "external", "closure", "release"];
    responses.forEach((result, i) => {
      const key = keys[i];
      if (result.status === "fulfilled") {
        state[key] = result.value;
        delete state.failures[key];
      } else state.failures[key] = text(result.reason && result.reason.message, "A local evidence record is unavailable.");
    });
    const runs = list(state.catalog && state.catalog.runs).filter((run) => object(run) && typeof run.id === "string" && /^[A-Za-z0-9_-]{1,100}$/.test(run.id) && typeof run.title === "string");
    $("run-select").replaceChildren(...runs.map((run) => node("option", { value: run.id }, `${run.title} · ${policyLabel(run.policy)}`)));
    $("run-select").disabled = runs.length === 0;
    if (!runs.length) $("run-select").append(node("option", {}, "No recorded investigation available"));
    renderNotices();
    updateReadiness();
    if (runs.length) {
      const chosen = runs.find((run) => run.id === state.selected) || runs.find((run) => run.id === "det-off-vertical") || runs[0];
      $("run-select").value = chosen.id;
      if (state.selected !== chosen.id || !state.run) await loadRun(chosen.id);
      else render();
    } else {
      state.run = null;
      $("content").setAttribute("aria-busy", "false");
      render();
    }
  }

  async function loadRun(id) {
    state.playing = false;
    const token = ++state.loadToken;
    state.selected = id;
    state.run = null;
    state.trial = null;
    state.frame = 0;
    $("content").setAttribute("aria-busy", "true");
    $("content").replaceChildren(empty("Opening the investigation", "Reading the approved artifact. No numerical refitting or API call is started."));
    try {
      const run = checkRun(await requestJSON(`/api/runs/${encodeURIComponent(id)}`));
      if (token !== state.loadToken) return;
      state.run = run;
      const rounds = list(run.rounds);
      state.round = rounds.length ? rounds[0].round : 1;
      delete state.failures.run;
    } catch (error) {
      if (token !== state.loadToken) return;
      state.failures.run = text(error && error.message, "The investigation record is unavailable.");
    }
    $("content").setAttribute("aria-busy", "false");
    render();
  }

  function updateReadiness() {
    const live = state.status && state.status.live_muse || state.catalog && state.catalog.live;
    const sam = state.status && state.status.sam || state.external && state.external.sam;
    $("sidebar-status").textContent = `Muse: ${text(live && live.status, "unavailable").replaceAll("_", " ")} · SAM: ${text(sam && sam.status, "unavailable").replaceAll("_", " ")}`;
    $("external-state").textContent = sam && ["PASS", "COMPLETED", "AVAILABLE"].includes(sam.status) ? "●" : "○";
    $("phone-state").textContent = "○";
  }

  function setSource(source) {
    state.source = source;
    state.playing = false;
    render();
  }
  function setView(view) {
    state.view = view;
    state.source = "synthetic";
    state.playing = false;
    render();
  }
  function decisionLabel(run) {
    return run.decision && run.decision.outcome === "CORRECT_MEASUREMENT" ? "Measurement correction required" : text(run.decision && run.decision.label);
  }
  function currentRound() { return list(state.run && state.run.rounds).find((round) => round.round === state.round) || null; }
  function availableTrials() {
    if (!state.run) return [];
    return state.run.trials.filter((trial) => state.round === "development" ? trial.zone === "development" : trial.zone === "exploration" && finite(trial.admitted_round) && trial.admitted_round <= state.round);
  }
  function currentTrial() {
    const trials = availableTrials();
    const trial = trials.find((item) => item.id === state.trial) || trials[0] || null;
    state.trial = trial && trial.id;
    if (trial) state.frame = Math.min(Math.max(0, state.frame), Math.max(0, trial.t_s.length - 1));
    return trial;
  }
  function currentPredictions(trial) {
    if (!trial) return {};
    if (trial.zone === "development") return object(trial.predictions) ? trial.predictions : {};
    const byRound = trial.round_predictions;
    if (object(byRound) && object(byRound[String(state.round)])) return byRound[String(state.round)];
    // Explicit fitted-round checks prevent a later fit from appearing in an
    // earlier round when an older artifact has no per-round prediction map.
    return Object.fromEntries(Object.entries(object(trial.predictions) ? trial.predictions : {}).filter(([key, value]) => key === "B0" || object(value) && finite(value.fitted_round) && value.fitted_round <= state.round));
  }
  function predictionRows(trial) {
    const values = currentPredictions(trial);
    return ["B0", "B1", "B3"].filter((key) => object(values[key]) && validXY(values[key].xy_px, trial.t_s.length) && values[key].xy_px.every((point) => point.every(finite))).map((key) => [key, values[key]]);
  }

  function renderReleaseHeader() {
    const release=state.release, host=$("release-header");
    if(!release){host.replaceChildren(info("Release evidence summary unavailable. No higher claim is substituted.",true));return;}
    const ladder=release.ladder;
    const domain=state.source==="synthetic"?"SYNTHETIC":state.source==="external"?"REAL_EXTERNAL":"REAL_PHONE";
    const policy=state.source==="synthetic" && state.run?state.run.policy:"RECORDED_EVIDENCE";
    const stage=state.run && state.source==="synthetic"?"POST_FREEZE_REPLAY":"PUBLIC_EVIDENCE_REPLAY";
    host.replaceChildren(node("div",{class:"release-boundary"},node("div",{class:"badges"},badge(domain,"teal"),badge(policyLabel(policy),"muted"),badge(stage,"muted"),badge("Claim ceiling "+ladder.overall_claim_ceiling,"amber")),
      node("p",{},"Run: "+(state.source==="synthetic"?state.selected:state.source)+" · Per-domain evidence; no physical validation certification."),
      node("p",{class:"negative-results"},list(ladder.negative_results).map(x=>x.kind+": "+x.status).join(" · ")),
      node("p",{},"Next: "+list(ladder.next_unmet_prerequisites).join("; ")),
      list(release.issues).map(x=>node("p",{class:"negative-results"},x))));
  }

  function render() {
    renderReleaseHeader();
    document.querySelectorAll("[data-view]").forEach((item) => {
      const active = state.source === "synthetic" && item.dataset.view === state.view;
      item.classList.toggle("active", active);
      if (active) item.setAttribute("aria-current", "page"); else item.removeAttribute("aria-current");
    });
    document.querySelectorAll("[data-source]").forEach((item) => {
      item.classList.toggle("active", item.dataset.source === state.source);
      item.setAttribute("aria-pressed", String(item.dataset.source === state.source));
    });
    const meta = state.source === "external" ? ["External Video", "A third-party physical recording. Inspect SAM tracking independently from the synthetic investigation."] : state.source === "phone" ? ["Phone Experiments", "Controlled real-world evidence remains separate until recordings and independent measurements are available."] : viewMeta[state.view];
    $("page-title").textContent = meta[0];
    $("page-description").textContent = meta[1];
    $("breadcrumb-view").textContent = meta[0];
    $("page-eyebrow").textContent = state.source === "external" ? "REAL EXTERNAL · TRACKING EVIDENCE ONLY" : state.source === "phone" ? "REAL PHONE · CONTROLLED MEASUREMENT" : "PHYSICS, MEASURED AGAINST EVIDENCE";
    $("run-picker-bar").hidden = state.source !== "synthetic";
    $("replay-button").hidden = state.source !== "synthetic" || !state.run || !state.run.decision;
    $("footer-status").textContent = state.source === "synthetic" ? "Recorded artifacts · Read-only playback" : state.source === "external" ? "External source · Separate perception evidence" : "Real phone · Physical validation pending";
    $("content").setAttribute("aria-busy", "false");
    if (state.source === "external") return renderExternal();
    if (state.source === "phone") return renderPhone();
    const run = state.run;
    if (!run) {
      $("run-provenance").replaceChildren(badge("NO EVIDENCE LOADED", "amber"));
      return $("content").replaceChildren(empty("Evidence record unavailable", state.failures.run || state.failures.catalog || "No approved investigation artifact is available. Use the documented demonstration command to create one.", "◇", button("Reload evidence", () => loadApp())));
    }
    $("run-provenance").replaceChildren(badge("SYNTHETIC", "teal"), badge(policyLabel(run.policy), "green"), badge("RECORDED ARTIFACT", "muted"));
    if (!run.decision) return $("content").replaceChildren(empty(text(run.status, "Investigation unavailable").replaceAll("_", " "), text(run.reason, "No completed frozen investigation is available for this record. The application has not substituted another policy."), "△"));
    const renderView = { reality: renderReality, investigation: renderInvestigation, experiment: renderExperiment, decision: renderDecision, evidence: renderEvidence }[state.view];
    $("content").replaceChildren(renderView());
  }

  function roundControls(includeDevelopment = false) {
    const container = node("div", { class: "round-control", role: "group", "aria-label": "Evidence round" }, node("span", {}, "Evidence snapshot"));
    for (const round of list(state.run.rounds)) container.append(button(`Round ${round.round}`, () => { state.round = round.round; state.trial = null; state.frame = 0; state.playing = false; render(); }, `round-button${state.round === round.round ? " active" : ""}`, { "aria-pressed": String(state.round === round.round) }));
    if (includeDevelopment && state.run.trials.some((trial) => trial.zone === "development")) container.append(button("Post-freeze evaluation", () => { state.round = "development"; state.trial = null; state.frame = 0; state.playing = false; render(); }, `round-button${state.round === "development" ? " active" : ""}`, { "aria-pressed": String(state.round === "development") }));
    return container;
  }
  function field(label, id, options, value, onChange) {
    const select = node("select", { id, onChange: (event) => onChange(event.target.value) }, options.map(([key, name]) => node("option", { value: key }, name)));
    select.value = value;
    return node("div", { class: "field" }, node("label", { for: id }, label), select);
  }

  function renderReality() {
    const run = state.run;
    const trial = currentTrial();
    const body = node("div", {}, roundControls(true));
    if (!trial || !trial.t_s.length) { body.append(empty("No trajectory in this snapshot", "This artifact has no admitted observation for the selected round. No trajectory has been invented.")); return body; }
    const predictions = predictionRows(trial);
    if (!predictions.some(([key]) => key === state.model)) state.model = predictions.some(([key]) => key === "B3") ? "B3" : predictions[0] && predictions[0][0] || "B0";
    const chosen = currentPredictions(trial)[state.model];
    const nValid = trial.valid.filter(Boolean).length;
    const duration = trial.t_s[trial.t_s.length - 1] - trial.t_s[0];
    body.append(node("div", { class: "metric-grid" }, metric("Selected-model discrepancy", number(chosen && chosen.rmse_px), "px RMS", "Same trial · full xy trajectory", true), metric("Observed samples", `${nValid} / ${trial.t_s.length}`, null, `${trial.t_s.length - nValid} missing observations`), metric("Observation duration", number(duration, 2), "s", "Original recorded sample timestamps")));
    body.append(node("div", { class: "toolbar" }, field("Trajectory", "trial-select", availableTrials().map((item, i) => [item.id, `${item.zone === "development" ? "Evaluation" : `Round ${item.admitted_round}`} · Trial ${i + 1} · ${number(item.release_angle_rad, 2)} rad`]), trial.id, (value) => { state.trial = value; state.frame = 0; state.playing = false; render(); }), field("Residual model", "model-select", predictions.map(([key]) => [key, modelNames[key]]), state.model, (value) => { state.model = value; render(); }), node("div", {}, badge(trial.zone === "development" ? "DEVELOPMENT · AFTER FREEZE" : "EXPLORATION", trial.zone === "development" ? "amber" : "teal"))));
    const xy = node("section", { class: "panel" }, heading("Observed and predicted motion", "Image plane · x right, y down · pixels", badge("SYNTHETIC OBSERVATIONS", "teal")), node("div", { class: "chart-container", id: "xy-chart-host" }, xyChart(trial, predictions)), timeline(trial), node("div", { class: "panel-footer" }, chartLegend(predictions), node("span", {}, "Solid points: observed centers")));
    const small = node("div", { class: "small-charts" }, node("section", { class: "panel" }, heading("Position over time", "Measured x and model predictions"), node("div", { class: "chart-container", id: "position-chart-host" }, timeChart(trial, predictions, false))), node("section", { class: "panel" }, heading("Residual over time", `${text(chosen && chosen.label, modelNames[state.model])} · x residual`), node("div", { class: "chart-container", id: "residual-chart-host" }, timeChart(trial, predictions, true))));
    const decision = node("section", { class: "decision-preview" }, node("div", { class: "decision-symbol", "aria-hidden": "true" }, "◇"), node("span", { class: "tiny-label" }, "FROZEN DECISION · FINAL RECORD"), node("h2", {}, decisionLabel(run)), node("p", {}, text(run.decision.explanation)), button("Inspect model decision →", () => setView("decision"), "button button-small"));
    const selectedRound = currentRound();
    const ident = selectedRound && selectedRound.identifiability;
    const snapshot = panel("Evidence in this snapshot", "A round contains only observations admitted by that point.", factList([["Snapshot", state.round === "development" ? "After model freeze" : `Round ${state.round}`], ["Exploration trials", integer(availableTrials().filter((item) => item.zone === "exploration").length)], ["Local sensitivity rank", ident && finite(ident.numerical_rank) ? `${ident.numerical_rank} / 5` : "Unavailable"], ["Causal mechanism identified", "No"], ["Policy", policyLabel(run.policy)]]));
    body.append(node("div", { class: "dashboard-grid" }, node("div", { class: "main-column" }, xy, small), node("div", { class: "side-column" }, decision, snapshot, panel("Read the uncertainty correctly", null, node("p", { class: "explain-text" }, "The shaded x band is ±1.96 localization standard deviations from the supplied covariance. It represents assumed synthetic measurement noise; it is not a model confidence interval.")))));
    body.append(info(state.round === "development" ? "Independent development observations are displayed after the decision was frozen. They were not inputs to investigation or model selection." : `Round ${state.round} predictions use models available in that round. The final frozen decision is shown separately. Pixel trajectories do not represent real physical measurements.`));
    return body;
  }

  function chartLegend(predictions) {
    return node("div", { class: "legend" }, node("span", { class: "legend-item" }, node("span", { class: "legend-dot" }), "Observed"), predictions.map(([key]) => node("span", { class: "legend-item" }, node("span", { class: `legend-swatch${key === state.model ? "" : " dashed"}`, style: `background:${modelColors[key]};border-color:${modelColors[key]}` }), key)), node("span", { class: "legend-item" }, node("span", { class: "legend-swatch", style: "background:#bdd5c0;height:6px" }), "Localization band"));
  }
  function range(values, minimumSpan = 1) {
    const clean = values.filter(finite);
    if (!clean.length) return [0, minimumSpan];
    const lo = Math.min(...clean), hi = Math.max(...clean);
    const span = Math.max(minimumSpan, hi - lo);
    return [(lo + hi - span) / 2 - span * .1, (lo + hi + span) / 2 + span * .1];
  }
  function samplePath(points, x, y, valid = null) {
    let path = "", connected = false;
    points.forEach((point, index) => {
      if ((!valid || valid[index]) && point.every(finite)) {
        path += `${connected ? "L" : "M"}${x(point[0]).toFixed(2)},${y(point[1]).toFixed(2)} `;
        connected = true;
      } else connected = false;
    });
    return path;
  }
  function axes(chart, bounds, xr, yr, xLabel, yLabel) {
    const { left, top, width, height } = bounds;
    for (let i = 0; i <= 4; i++) {
      const x = left + width * i / 4, y = top + height * i / 4;
      chart.append(svg("line", { x1: x, y1: top, x2: x, y2: top + height, class: "chart-grid-line" }), svg("line", { x1: left, y1: y, x2: left + width, y2: y, class: "chart-grid-line" }), svg("text", { x, y: top + height + 17, "text-anchor": "middle", class: "chart-label" }, number(xr[0] + (xr[1] - xr[0]) * i / 4, 1)), svg("text", { x: left - 9, y: y + 3, "text-anchor": "end", class: "chart-label" }, number(yr[0] + (yr[1] - yr[0]) * i / 4, 1)));
    }
    chart.append(svg("text", { x: left + width, y: top + height + 35, "text-anchor": "end", class: "chart-axis-title" }, xLabel), svg("text", { x: left, y: top - 10, class: "chart-axis-title" }, yLabel));
  }
  function xyChart(trial, predictions) {
    const chart = svg("svg", { viewBox: "0 0 650 365", class: "xy-chart", role: "img", "aria-label": "Measured and predicted image-plane trajectories in pixels. Y increases downward." }, svg("title", {}, "Observed and predicted image-plane trajectories"));
    const points = trial.xy_px.filter((point, i) => trial.valid[i]).concat(...predictions.map(([, value]) => value.xy_px));
    const xr = range(points.map((point) => point[0]), 30), yr = range(points.map((point) => point[1]), 30);
    const bounds = { left: 60, top: 26, width: 565, height: 287 };
    // Equal pixel scales preserve the shape of the physical image-plane path.
    const scale = Math.min(bounds.width / (xr[1] - xr[0]), bounds.height / (yr[1] - yr[0]));
    const xmid = (xr[0] + xr[1]) / 2, ymid = (yr[0] + yr[1]) / 2;
    const xRange = [xmid - bounds.width / scale / 2, xmid + bounds.width / scale / 2], yRange = [ymid - bounds.height / scale / 2, ymid + bounds.height / scale / 2];
    const x = (v) => bounds.left + (v - xRange[0]) * scale, y = (v) => bounds.top + (v - yRange[0]) * scale;
    axes(chart, bounds, xRange, yRange, "x (px)", "y (px) ↓");
    predictions.forEach(([key, value]) => chart.append(svg("path", { d: samplePath(value.xy_px, x, y), class: "chart-model", stroke: modelColors[key], "stroke-width": key === state.model ? 2.3 : 1.3, "stroke-dasharray": key === state.model ? "none" : "5 5", opacity: key === state.model ? 1 : .7 })));
    chart.append(svg("path", { d: samplePath(trial.xy_px, x, y, trial.valid), class: "chart-measured" }));
    trial.xy_px.forEach((point, index) => { if (trial.valid[index]) chart.append(svg("circle", { cx: x(point[0]), cy: y(point[1]), r: 2, class: "chart-point" })); });
    const current = trial.xy_px[state.frame];
    if (trial.valid[state.frame] && current && current.every(finite)) chart.append(svg("circle", { cx: x(current[0]), cy: y(current[1]), r: 10, fill: "#459b83", opacity: .12 }), svg("circle", { cx: x(current[0]), cy: y(current[1]), r: 4.8, fill: "#286e57", stroke: "white", "stroke-width": 1.5 }));
    const selected = currentPredictions(trial)[state.model];
    if (selected && validXY(selected.xy_px, trial.t_s.length)) {
      const predicted = selected.xy_px[state.frame];
      if (predicted && predicted.every(finite)) chart.append(svg("circle", { cx: x(predicted[0]), cy: y(predicted[1]), r: 5, fill: "none", stroke: modelColors[state.model], "stroke-width": 1.8 }));
    }
    return chart;
  }

  function sigmaX(trial) {
    const covariance = trial.covariance_px2;
    return Array.isArray(covariance) && Array.isArray(covariance[0]) && finite(covariance[0][0]) && covariance[0][0] >= 0 ? Math.sqrt(covariance[0][0]) : null;
  }
  function timeChart(trial, predictions, residual) {
    const chart = svg("svg", { viewBox: "0 0 400 225", class: "small-chart", role: "img", "aria-label": residual ? "Measured x minus selected model x over observation time in seconds." : "Measured and predicted x in pixels over observation time in seconds, with assumed localization uncertainty." });
    const selected = predictions.find(([key]) => key === state.model);
    if (residual && !selected) return node("div", { class: "chart-unavailable" }, "No model prediction is available for residuals.");
    const points = trial.t_s.map((t, i) => [t, trial.valid[i] ? trial.xy_px[i][0] - (residual ? selected[1].xy_px[i][0] : 0) : null]);
    const sd = sigmaX(trial), halfBand = sd === null ? null : 1.96 * sd;
    const ys = points.filter((point) => finite(point[1])).flatMap((point) => halfBand === null ? [point[1]] : [point[1] - halfBand, point[1] + halfBand]);
    if (!residual) predictions.forEach(([, value]) => ys.push(...value.xy_px.map((point) => point[0])));
    else ys.push(0);
    const xr = [trial.t_s[0], trial.t_s[trial.t_s.length - 1]], yr = range(ys, residual ? 2 : 20);
    const bounds = { left: 54, top: 23, width: 326, height: 150 };
    const x = (value) => bounds.left + (value - xr[0]) / Math.max(1e-9, xr[1] - xr[0]) * bounds.width;
    const y = (value) => bounds.top + (yr[1] - value) / (yr[1] - yr[0]) * bounds.height;
    axes(chart, bounds, xr, [yr[1], yr[0]], "t (s)", residual ? "residual x (px)" : "x (px)");
    // Break uncertainty ribbons at missing observations, rather than bridging gaps.
    if (halfBand !== null) {
      let segment = [];
      function flush() {
        if (segment.length > 1) {
          const upper = segment.map((point) => [point[0], point[1] - halfBand]);
          const lower = segment.slice().reverse().map((point) => [point[0], point[1] + halfBand]);
          chart.append(svg("path", { d: samplePath(upper.concat(lower), x, y) + "Z", class: "chart-uncertainty" }));
        }
        segment = [];
      }
      points.forEach((point) => { if (finite(point[1])) segment.push(point); else flush(); });
      flush();
    }
    if (!residual) predictions.forEach(([key, value]) => chart.append(svg("path", { d: samplePath(trial.t_s.map((t, i) => [t, value.xy_px[i][0]]), x, y), class: "chart-model", stroke: modelColors[key], "stroke-width": key === state.model ? 1.6 : 1, "stroke-dasharray": key === state.model ? "none" : "4 4" })));
    else chart.append(svg("line", { x1: bounds.left, x2: bounds.left + bounds.width, y1: y(0), y2: y(0), stroke: "#a4b397", "stroke-dasharray": "4 4" }));
    chart.append(svg("path", { d: samplePath(points, x, y, trial.valid), class: "chart-measured" }));
    points.forEach((point) => { if (finite(point[1])) chart.append(svg("circle", { cx: x(point[0]), cy: y(point[1]), r: 1.8, class: "chart-point" })); });
    chart.append(svg("line", { x1: x(trial.t_s[state.frame]), x2: x(trial.t_s[state.frame]), y1: bounds.top, y2: bounds.top + bounds.height, class: "chart-cursor" }));
    return chart;
  }
  function timeline(trial) {
    return node("div", { class: "timeline-control" }, button(state.playing ? "Ⅱ" : "▷", togglePlayback, "play-button", { id: "timeline-play", "aria-label": state.playing ? "Pause recorded trajectory" : "Play recorded trajectory", "aria-pressed": String(state.playing) }), node("label", { class: "sr-only", for: "time-scrubber" }, "Recorded sample"), node("input", { id: "time-scrubber", type: "range", min: 0, max: Math.max(0, trial.t_s.length - 1), step: 1, value: state.frame, onInput: (event) => { state.frame = Number(event.target.value); state.playing = false; updateCharts(); } }), node("output", { class: "time-label", id: "timeline-label", for: "time-scrubber" }, `${number(trial.t_s[state.frame], 2)} / ${number(trial.t_s[trial.t_s.length - 1], 2)} s`));
  }
  function updateCharts() {
    if (state.source !== "synthetic" || state.view !== "reality") return;
    const trial = currentTrial();
    if (!trial || !trial.t_s.length) return;
    const predictions = predictionRows(trial);
    if ($("xy-chart-host")) $("xy-chart-host").replaceChildren(xyChart(trial, predictions));
    if ($("position-chart-host")) $("position-chart-host").replaceChildren(timeChart(trial, predictions, false));
    if ($("residual-chart-host")) $("residual-chart-host").replaceChildren(timeChart(trial, predictions, true));
    if ($("time-scrubber")) $("time-scrubber").value = state.frame;
    if ($("timeline-label")) $("timeline-label").textContent = `${number(trial.t_s[state.frame], 2)} / ${number(trial.t_s[trial.t_s.length - 1], 2)} s`;
    if ($("timeline-play")) { $("timeline-play").textContent = state.playing ? "Ⅱ" : "▷"; $("timeline-play").setAttribute("aria-label", state.playing ? "Pause recorded trajectory" : "Play recorded trajectory"); $("timeline-play").setAttribute("aria-pressed", String(state.playing)); }
  }
  function togglePlayback() {
    const trial = currentTrial();
    if (!trial || trial.t_s.length < 2) return;
    if (!state.playing && state.frame >= trial.t_s.length - 1) state.frame = 0;
    state.playing = !state.playing;
    state.lastTick = performance.now();
    updateCharts();
  }
  function tick(now) {
    if (state.playing && state.source === "synthetic" && state.view === "reality") {
      const trial = currentTrial();
      if (!trial || state.frame >= trial.t_s.length - 1) { state.playing = false; updateCharts(); }
      else {
        const interval = Math.max(35, (trial.t_s[state.frame + 1] - trial.t_s[state.frame]) * 1000);
        if (now - state.lastTick >= interval) { state.frame++; state.lastTick = now; if (state.frame >= trial.t_s.length - 1) state.playing = false; updateCharts(); }
      }
    }
    requestAnimationFrame(tick);
  }

  function comparisonTable(comparison) {
    if (!comparison || !list(comparison.scores).length) return node("p", { class: "explain-text panel-pad" }, "No whole-trial comparison was available in this round.");
    return node("div", { class: "table-scroll" }, node("table", { class: "comparison-table" }, node("caption", { class: "sr-only" }, "Whole-trial exploration cross-validation model comparison"), node("thead", {}, node("tr", {}, ["Candidate", "CV MSE (px²)", "Noise ratio"].map((label) => node("th", { scope: "col" }, label)))), node("tbody", {}, comparison.scores.map((row) => node("tr", {}, node("td", {}, familyName(row.candidate)), node("td", {}, number(row.trial_cv_mse_px2)), node("td", {}, finite(row.noise_ratio) ? `${number(row.noise_ratio, 2)}×` : "Unavailable"))))));
  }
  function toolMetrics(metrics) {
    if (!object(metrics)) return [];
    return Object.entries(metrics).filter(([, value]) => finite(value) || typeof value === "boolean" || typeof value === "string" && value.length < 75).slice(0, 4).map(([key, value]) => node("span", {}, `${key.replaceAll("_", " ")}: ${finite(value) ? number(value, 3) : value}`));
  }
  function renderInvestigation() {
    if (state.round === "development") state.round = list(state.run.rounds).at(-1)?.round || 1;
    const round = currentRound();
    const comp = round && round.comparison;
    const hypotheses = list(round && round.hypotheses);
    const calls = list(state.run.tool_calls).filter((call) => call.round === state.round);
    const root = node("div", {}, roundControls());
    root.append(node("div", { class: "hypotheses" }, hypotheses.length ? hypotheses.map((hypothesis, i) => node("article", { class: `hypothesis${hypothesis.status === "PREDICTIVELY_SUPPORTED" ? " supported" : ""}` }, node("span", { class: "hypothesis-number" }, `H${i + 1} / CANDIDATE`), node("h3", {}, familyName(hypothesis.family)), badge(text(hypothesis.status).replaceAll("_", " "), hypothesis.status === "PREDICTIVELY_SUPPORTED" ? "green" : "muted"))) : node("p", { class: "explain-text" }, "No recorded hypotheses are available in this round.")));
    const modelComparison = node("section", { class: "panel" }, heading("Competing dynamical models", "Whole-trial exploration cross-validation", comp ? statusBadge(comp.status) : badge("UNAVAILABLE", "amber")), comparisonTable(comp), node("div", { class: "panel-pad" }, factList([["Normalized minimum-fold gain", number(comp && comp.statistic)], ["Empirical tail rank", number(comp && comp.empirical_tail_probability, 5)], ["Null datasets", integer(comp && comp.null_replicates)], ["Selection support", text(comp && comp.calibrated_support).replaceAll("_", " ")]]), node("p", { class: "policy-note" }, "This finite synthetic gate supports predictive model comparison. It does not identify a unique physical cause.")));
    const ident = round && round.identifiability;
    const identPanel = panel("Can the parameters be distinguished?", "Local sensitivity of the recorded candidate fit.", node("div", {}, factList([["Numerical rank", ident && finite(ident.numerical_rank) ? `${ident.numerical_rank} / 5` : "Unavailable"], ["Locally identifiable", ident && typeof ident.locally_identifiable === "boolean" ? ident.locally_identifiable ? "Yes, locally" : "No" : "Unavailable"], ["Near a parameter bound", ident && typeof ident.near_bound === "boolean" ? ident.near_bound ? "Yes" : "No" : "Unavailable"], ["Globally identified", "No"]]), info("A good trajectory fit can coexist with ambiguous parameters or competing physical explanations.")));
    root.append(node("div", { class: "two-column section-gap" }, modelComparison, identPanel));
    const names = { inspect_discrepancy: "Inspect trajectory discrepancy", fit_candidate_model: "Fit candidate dynamics", compare_candidate_models: "Compare whole-trial predictions", inspect_identifiability: "Inspect parameter identifiability", score_candidate_experiment: "Score candidate experiment" };
    root.append(node("section", { class: "panel" }, heading("Scientific tool record", "Actual recorded backend outputs, in execution order.", badge(`${calls.length} TOOL CALLS`, "muted")), calls.length ? node("ol", { class: "tool-list" }, calls.map((call, i) => node("li", { class: "tool-item" }, node("span", { class: "tool-icon", "aria-hidden": "true" }, String(i + 1).padStart(2, "0")), node("div", {}, node("div", { class: "tool-name" }, names[call.name] || text(call.name)), node("div", { class: "tool-evidence" }, `Evidence ${shortHash(call.evidence_ref)}`), node("div", { class: "tool-metrics" }, toolMetrics(call.metrics), list(call.flags).map((flag) => node("span", {}, text(flag).replaceAll("_", " "))))), node("div", { class: "tool-status" }, statusBadge(call.status))))) : node("div", { class: "panel-pad explain-text" }, "No recorded scientific tool calls in this round.")));
    return root;
  }

  function actionSummary(action) {
    if (!action) return "No experiment requested";
    if (action.kind === "RELEASE") return `Release at ${number(action.release_angle_rad, 2)} rad`;
    return ({ REPEAT: "Repeat an approved observation", CAMERA_CALIBRATION: "Check the camera reference", STATIONARY_REFERENCE: "Collect a stationary reference" }[action.kind] || text(action.kind).replaceAll("_", " "));
  }
  function renderExperiment() {
    const experiment = object(state.run.experiment) ? state.run.experiment : {};
    const action = object(experiment.action) ? experiment.action : null;
    const score = object(experiment.score) ? experiment.score : null;
    const receipt = object(experiment.receipt) ? experiment.receipt : null;
    const initial = state.run.trials.filter((trial) => trial.zone === "exploration" && trial.admitted_round === 1).length;
    const received = Array.isArray(experiment.received_new_trials) ? experiment.received_new_trials.length : finite(experiment.received_new_trials) ? experiment.received_new_trials : receipt && receipt.new_observations;
    const root = node("div", {});
    root.append(node("div", { class: "flow-row" }, node("article", { class: "flow-card" }, node("span", { class: "tiny-label" }, "01 / OBSERVE"), node("h3", {}, "Initial exploration"), node("p", {}, "Only the first admitted observations are available to the investigator."), node("div", { class: "flow-count" }, integer(initial), node("small", {}, "trials"))), node("div", { class: "flow-arrow", "aria-hidden": "true" }, "→"), node("article", { class: "flow-card highlight" }, node("span", { class: "tiny-label" }, "02 / REQUEST"), node("h3", {}, actionSummary(action)), node("p", {}, experiment.requested ? "The investigator requested an approved, numerically scored action." : "This trace contains no experiment request."), node("div", { class: "flow-count" }, action && finite(action.repeats) ? integer(action.repeats) : "—", node("small", {}, action && finite(action.repeats) ? "repeats" : "reference action"))), node("div", { class: "flow-arrow", "aria-hidden": "true" }, "→"), node("article", { class: "flow-card" }, node("span", { class: "tiny-label" }, "03 / RECEIVE"), node("h3", {}, receipt ? "Evidence received" : "No completed receipt"), node("p", {}, receipt ? `Receipt: ${text(receipt.kind).replaceAll("_", " ")}. ${text(receipt.source).replaceAll("_", " ")}.` : "An experiment request alone is not evidence that it was completed."), node("div", { class: "flow-count" }, integer(received), node("small", {}, "new trajectories")))));
    const visualization = node("section", { class: "panel" }, heading("The next observation is deliberate", "The diagram illustrates the requested action; it is not an observed rig or fitted geometry.", badge("SCHEMATIC", "muted")), node("div", { class: "experiment-visual" }, experimentSchematic(action)), node("div", { class: "panel-footer" }, node("span", {}, actionSummary(action)), node("span", {}, "Synthetic environment · No physical actuator")));
    const scoring = panel("Why this action?", "Recorded numerical feasibility and discrimination.", node("div", {}, factList([["Feasible", score && typeof score.feasible === "boolean" ? score.feasible ? "Yes" : "No" : "Unavailable"], ["Predicted separation", score && finite(score.predictive_discrimination_sigma) ? `${number(score.predictive_discrimination_sigma, 2)} σ` : "Unavailable"], ["Ensemble spread", score && finite(score.ensemble_spread_sigma) ? `${number(score.ensemble_spread_sigma, 2)} σ` : "Unavailable"], ["Reference-check priority", integer(score && score.diagnostic_priority)], ["Valid ensemble members", integer(score && score.valid_ensemble_members)], ["Expected information gain", "Unavailable"]]), node("p", { class: "policy-note" }, "Trajectory separation is a heuristic score in localization-noise units. Ensemble spread is not a posterior interval; expected information gain was not computed.")));
    root.append(node("div", { class: "two-column section-gap" }, visualization, scoring));
    root.append(panel("From a request to updated evidence", null, node("div", {}, factList([["Requested action", experiment.requested ? actionSummary(action) : "None recorded"], ["Receipt source", text(receipt && receipt.source).replaceAll("_", " ")], ["New trajectory observations", integer(received)], ["Recorded observation rounds", integer(state.run.rounds.length)]]), node("div", { class: "download-row" }, button("Inspect initial hypotheses", () => { state.round = 1; setView("investigation"); }), button("Inspect the updated round →", () => { const last = list(state.run.rounds).at(-1); state.round = last ? last.round : 1; setView("investigation"); }, "button button-primary")))));
    if (action && ["CAMERA_CALIBRATION", "STATIONARY_REFERENCE"].includes(action.kind)) root.append(info("This action checks measurement quality. Its completion does not establish that a calibration revision was applied or that a corrected measurement was verified.", true));
    return root;
  }
  function experimentSchematic(action) {
    const chart = svg("svg", { viewBox: "0 0 500 245", role: "img", "aria-label": "Illustration of an approved pendulum release action, not a measured rig." });
    const angle = action && finite(action.release_angle_rad) ? action.release_angle_rad : .32;
    const end = [250 + Math.sin(angle) * 165, 34 + Math.cos(angle) * 165];
    chart.append(svg("line", { x1: 162, y1: 28, x2: 338, y2: 28, stroke: "#b7c5a9", "stroke-width": 4, "stroke-linecap": "round" }), svg("line", { x1: 250, y1: 34, x2: 250, y2: 204, stroke: "#c4cfb7", "stroke-dasharray": "4 5" }), svg("path", { d: "M173 185 Q250 226 327 185", fill: "none", stroke: "#e0e8d6", "stroke-width": 1.5 }), svg("line", { x1: 250, y1: 34, x2: end[0], y2: end[1], stroke: "#60814e", "stroke-width": 2 }), svg("circle", { cx: 250, cy: 34, r: 5, fill: "#637b53" }), svg("circle", { cx: end[0], cy: end[1], r: 13, fill: "#aecb92", stroke: "#6d914d", "stroke-width": 1.5 }), svg("circle", { cx: end[0] - 3, cy: end[1] - 4, r: 4, fill: "#d8e8c4" }));
    if (action && finite(action.release_angle_rad)) chart.append(svg("text", { x: 286, y: 83, class: "chart-label" }, `${number(action.release_angle_rad, 2)} rad requested`));
    chart.append(svg("text", { x: 20, y: 233, class: "chart-label" }, "Illustrative geometry only · not to scale"));
    return chart;
  }

  function renderDecision() {
    const run = state.run, decision = run.decision;
    const measurement = decision.outcome === "CORRECT_MEASUREMENT";
    const root = node("div", {}, node("section", { class: "decision-hero" }, badge("FROZEN SCIENTIFIC DECISION", "green"), node("h2", {}, decisionLabel(run)), node("p", {}, measurement ? "A measurement-quality problem was supported by the reference check. A correction still needs to be applied and independently verified; this record does not demonstrate a successful physical correction." : text(decision.explanation)), node("div", { class: "badges" }, badge(decision.accepted === true ? "PROPOSAL ACCEPTED" : "ABSTENTION / PROPOSAL NOT ACCEPTED", decision.accepted === true ? "green" : "amber"), badge("PREDEFINED MODEL SCOPE", "muted"), badge("CAUSAL UNIQUENESS NOT ESTABLISHED", "muted"))));
    root.append(node("div", { class: "metric-grid" }, metric("Independent development error", number(run.evaluation && run.evaluation.rmse_px), "px RMS", "Post-freeze · separate evaluation", true), metric("Logical fit jobs", integer(run.budget && run.budget.fit_jobs), null, "Includes charged cached fit requests"), metric("Scientific tool calls", integer(run.budget && run.budget.tool_calls), null, "Bounded investigation budget")));
    const baseline = node("div", {}), values = ["B0", "B1", "B3"].map((key) => [key, run.baseline && run.baseline[key]]);
    const max = Math.max(1e-9, ...values.map(([, value]) => finite(value) ? value : 0));
    values.forEach(([key, value]) => baseline.append(node("div", { class: "baseline-row" }, node("span", { class: "baseline-name" }, modelNames[key]), node("div", { class: "baseline-bar" }, finite(value) ? node("div", { class: "baseline-fill", style: `width:${Math.max(.8, Math.min(100, value / max * 100))}%;background:${modelColors[key]}` }) : null), node("span", { class: "baseline-value" }, finite(value) ? `${number(value)} px` : "Unavailable"))));
    baseline.append(node("p", { class: "policy-note" }, "All displayed bars use the same backend-reported trajectory RMS metric and evaluation scope. B2 circle reconstruction is a geometric diagnostic and is not compared on this scale."));
    const scope = panel("What this outcome establishes", null, node("div", {}, factList([["Contract outcome", text(decision.outcome)], ["Proposal accepted", decision.accepted === true ? "Yes" : "No"], ["Model reference", shortHash(decision.model_ref)], ["Scope", text(decision.scope).replaceAll("_", " ")], ["Physical causal discovery", "Not established"]]), node("p", { class: "policy-note" }, measurement ? "Measurement correction applied: no. Correction verified: no. The existing CORRECT_MEASUREMENT contract is presented as a required follow-up action." : "KEEP describes adequacy in the explored envelope. A predefined peg model selection supports its predictions, not unique mechanism identification or open-ended equation discovery.")));
    root.append(node("div", { class: "two-column section-gap" }, panel("Baseline comparison", "Recorded trajectory prediction error · lower is better.", baseline), scope));
    root.append(panel("Structured selection among predefined typed models", "B2 uses a separate geometric metric.",
      node("p", {}, "B2 circle fitting is executable in the synthetic baseline study. No B2 score was recorded for this selected investigation; a radial reconstruction error cannot be substituted for its trajectory RMSE.")));
    const value=state.release && state.release.agent_value;
    if(value) root.append(panel(value.label,"Recorded matched synthetic case · post-freeze development prediction, not exploration fitting error.",factList([
      ["Muse error",number(value.live_rmse_px)+" px"],["Deterministic error",number(value.deterministic_rmse_px)+" px"],
      ["Paired difference",number(value.difference_px,9)+" px"],["Logical fit jobs",integer(value.live_fit_jobs)+" / "+integer(value.deterministic_fit_jobs)],
      ["Billed cost","UNVERIFIED"]])));
    root.append(panel("The decision is frozen", "Model identity and decision evidence remain attached to the record.", node("div", {}, hashBlock("FROZEN DECISION SHA-256", decision.freeze_sha256), hashBlock("MODEL RESOURCE", decision.model_ref), node("div", { class: "download-row" }, button("Inspect the audit and provenance →", () => setView("evidence"), "button button-primary")))));
    if (measurement) root.append(info("A completed stationary or camera reference check is evidence about quality. It is not evidence that a physical calibration correction has been completed.", true));
    return root;
  }

  function hashBlock(title, value) {
    const valid = typeof value === "string" && /^[a-f0-9]{64}$/.test(value);
    return node("div", { class: "hash-box" }, node("div", { class: "hash-title" }, node("span", { class: "tiny-label" }, title), valid ? button("Copy", async (event) => {
      const target = event.currentTarget;
      try { await navigator.clipboard.writeText(value); target.textContent = "Copied"; } catch (_) { target.textContent = "Select hash to copy"; }
    }, "button button-small button-ghost") : null), node("div", { class: "hash" }, valid ? value : "Unavailable / no model frozen"));
  }
  function downloadJSON(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
    const link = node("a", { href: url, download: name });
    document.body.append(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  function renderEvidence() {
    const run = state.run;
    const live = state.status && state.status.live_muse || {};
    const api = object(run.api) ? run.api : {};
    const verified = run.integrity.status === "VERIFIED" && run.audit.verified === true;
    const root = node("div", {}, node("div", { class: "metric-grid" }, metric("Recorded audit events", integer(run.audit.event_count), null, verified ? "Artifact and audit checks verified" : "Integrity unavailable", true), metric("Actual API requests · selected run", integer(api.actual_api_requests), null, policyLabel(run.policy)), metric("Live investigator validation", text(live.status, "Unavailable").replaceAll("_", " "), null, "Separate from this recorded policy")));
    const audit = panel("Frozen evidence and replay", "Read-only artifact verification does not rerun numerical fits.", node("div", {}, node("div", { class: "status-line" }, statusBadge(run.integrity.status), node("span", { class: "subtle" }, "Verified local artifact · not a signed authenticity claim")), hashBlock("APPROVED ARTIFACT SHA-256", run.integrity.artifact_sha256), hashBlock("INVESTIGATION AUDIT HEAD", run.audit.head), hashBlock("FROZEN DECISION SHA-256", run.decision.freeze_sha256), node("div", { class: "download-row" }, button("Download evidence JSON ↓", () => downloadJSON(run, `realign-${state.selected}.json`)), button("Replay trajectory →", () => { state.round = 1; state.frame = 0; setView("reality"); }))), badge("RECORDED ARTIFACT", "muted"));
    const provenance = panel("Source and execution provenance", "The origin of data and the policy are different facts.", node("div", {}, node("div", { class: "provenance-block" }, node("strong", {}, "Observation source"), badge("SYNTHETIC", "teal"), node("p", { class: "spaced-top" }, "Numerically generated pendulum trajectories with controlled noise. No phone footage or SAM processing is claimed for this investigation.")), node("div", { class: "provenance-block" }, node("strong", {}, "Investigation policy"), badge(policyLabel(run.policy), run.policy === "LIVE_MUSE" ? "green" : "muted"), node("p", { class: "spaced-top" }, run.policy === "MOCK_POLICY" ? "The mock mirrors the deterministic policy and verifies interface plumbing. It is not evidence of Muse reasoning or superiority." : run.policy === "LIVE_MUSE" ? "This record reports live Muse calls over synthetic exploration evidence. Live reasoning does not make the observations real." : "A deterministic scientific policy using the same approved numerical tools. Playback is a view of the recorded result.")), node("div", { class: "provenance-block" }, node("strong", {}, "Evaluation boundary"), badge("POST-FREEZE DEVELOPMENT", "amber"), node("p", { class: "spaced-top" }, "Development measurements were scored after the frozen decision and were not inputs to investigation or model selection. No sealed validation is claimed."))));
    root.append(node("div", { class: "evidence-grid section-gap" }, audit, provenance));
    root.append(node("div", { class: "two-column section-gap" }, panel("Selected-run API accounting", "Available accounting only; no invented costs.", factList([["Actual API requests", integer(api.actual_api_requests)], ["Input tokens", integer(api.input_tokens)], ["Output tokens", integer(api.output_tokens)], ["API latency", finite(api.api_latency_s) ? `${number(api.api_latency_s, 2)} s` : "Unavailable"], ["Monetary cost", "Unavailable"]])), panel("Scope and remaining limitations", null, list(run.caveats).length ? node("ul", { class: "limitations" }, run.caveats.map((value) => node("li", {}, text(value)))) : node("p", { class: "explain-text" }, "No additional caveats were included in the evidence response. This view does not imply real physical validation."))));
    const independent = state.closure && state.closure.independent;
    if (independent) {
      root.append(panel("Independent validation exercise", "Separate precommitted dataset and model; this is not validation of the currently selected Task 05 recording.", node("div", {},
        badge(independent.commitment && independent.commitment.domain || independent.domain, "amber"),
        statusBadge(independent.independent_verdict || independent.status),
        independent.evaluation ? factList([["Held-out trajectory RMSE", number(independent.evaluation.trajectory_rmse_px)+" px"],
          ["Prediction tolerance", number(independent.commitment.protocol.max_trajectory_rmse_px)+" px"],
          ["Peg-position error", number(independent.reveal.geometry_comparison.peg_position_error_m === null ? null : 1000 * independent.reveal.geometry_comparison.peg_position_error_m)+" mm"],
          ["Peg-position tolerance", number(1000 * independent.commitment.protocol.peg_position_tolerance_m)+" mm"],
          ["Model version", shortHash(independent.frozen_model.content_sha256)], ["Commitment", shortHash(independent.commitment.commitment_sha256)],
          ["Freeze before evaluation", "Enforced by the independent custodian"], ["Holdout reuse", "Rejected after first evaluation"], ["Physical G5 passed", "No"]]) : null,
        info("A synthetic blind workflow exercise is not a real physical blind discovery. Local ordering is not external timestamp attestation.", true))));
    }
    const fixed=state.release && state.release.historical_g5.fixed;
    if(fixed) root.append(panel("Separate fixed synthetic positive control", "Historical G5 protocol and thresholds unchanged; not a physical blind discovery.",
      node("div",{},statusBadge(fixed.independent_verdict),factList([["Trajectory RMSE",number(fixed.evaluation.trajectory_rmse_px)+" px"],
      ["Peg-position error",number(1000*fixed.reveal.geometry_comparison.peg_position_error_m)+" mm"],
      ["Registered peg tolerance",number(1000*fixed.commitment.protocol.peg_position_tolerance_m)+" mm"],
      ["Challenge",fixed.commitment.challenge_id],["Content hash",shortHash(fixed.frozen_model.content_sha256)]]))));
    if(state.release) root.append(panel("Run locally", "Viewing is read-only. Live execution requires separately authorized CLI use.",
      node("div",{},Object.entries(state.release.run_locally).map(([k,v])=>node("p",{},node("strong",{},k+": "),node("code",{},v))))));
    if (run.policy === "LIVE_MUSE") root.append(panel("Actual Muse reasoning contribution", "The recorded model chose hypotheses, scientific tool calls and an experiment; numerical tools computed every score.",
      node("p", {class:"explain-text"}, "This authentic Muse trace runs over synthetic observations. The matched deterministic policy reaches the same predictive error. The result verifies integration without demonstrating Muse superiority.")));
    root.append(info("Integrity checks detect changes against the approved local artifact and its audit. They do not establish causal uniqueness, real-world validation, or a comparison showing Muse superiority."));
    return root;
  }

  function renderExternal() {
    const data = state.external;
    if (!data) return $("content").replaceChildren(empty("External tracking evidence unavailable", state.failures.external || "The external source record has not been loaded. This does not affect the separate synthetic demonstration.", "▷", button("Reload source evidence", () => loadApp())));
    if (data.observation_source !== "REAL_EXTERNAL") return $("content").replaceChildren(empty("External provenance could not be verified", "The response does not explicitly identify REAL_EXTERNAL evidence. No video or tracking result has been displayed.", "△"));
    const metadata = object(data.metadata) ? data.metadata : {}, provenance = object(data.provenance) ? data.provenance : {}, sam = object(data.sam) ? data.sam : {};
    const assessment = state.closure && state.closure.manual;
    const review = assessment ? Object.assign({}, assessment, assessment.metrics) : object(data.manual_review) ? data.manual_review : {};
    const track = object(data.track) ? data.track : null;
    const validTrack = track && Array.isArray(metadata.t_s) && validXY(track.xy_px, metadata.t_s.length) && Array.isArray(track.valid) && track.valid.length === metadata.t_s.length && track.valid.every((v) => typeof v === "boolean") && track.xy_px.every((p, i) => !track.valid[i] || p.every(finite));
    const validFrames = validTrack ? track.valid.filter(Boolean).length : null;
    const root = node("div", {}, node("div", { class: "run-picker-bar" }, node("div", {}, node("span", { class: "tiny-label" }, "INDEPENDENT PERCEPTION SOURCE"), node("strong", { class: "subtle" }, "Third-party blocked-pendulum recording")), node("div", { class: "run-provenance" }, badge("REAL EXTERNAL", "teal"), statusBadge(sam.status), badge("TRACKING ONLY", "amber"))));
    root.append(node("div", { class: "metric-grid" }, metric("Tracked frames", integer(validFrames), null, validTrack ? `Of ${integer(metadata.t_s.length)} original timestamps` : "No validated tracked centers available", true), metric("SAM successful calls", integer(sam.successful_calls), null, `${integer(sam.failed_calls)} failed calls reported`), metric("Manual review discrepancy", number(review.rmse_px), "px RMS", text(review.status, "Manual review pending").replaceAll("_", " "))));
    const stage = node("div", { class: "video-stage" });
    stage.append(node("div",{class:"external-watermark"},"REAL_EXTERNAL · External footage, not our experiment · MikeRun · CC BY-SA 4.0"));
    const mediaOK = typeof data.media_url === "string" && /^\/media\/[A-Za-z0-9_.-]+$/.test(data.media_url);
    let video = null, overlay = null;
    if (finite(metadata.width) && finite(metadata.height) && metadata.width > 0 && metadata.height > 0) stage.style.aspectRatio = `${metadata.width} / ${metadata.height}`;
    if (mediaOK) {
      video = node("video", { controls: true, playsinline: true, preload: "metadata", src: data.media_url, "aria-label": "Original third-party physical recording. Playback timing is not verified capture timing." });
      video.addEventListener("error", () => { stage.replaceChildren(node("div", { class: "video-empty" }, node("strong", {}, "Local video is unavailable"), node("p", {}, "No replacement video or tracking has been substituted."))); });
      stage.append(video);
      if (validTrack && finite(metadata.width) && finite(metadata.height)) { overlay = svg("svg", { viewBox: `0 0 ${metadata.width} ${metadata.height}`, class: "video-overlay", "aria-hidden": "true" }); stage.append(overlay); }
    } else stage.append(node("div", { class: "video-empty" }, node("strong", {}, "No local video available"), node("p", {}, "Source provenance is retained. SAM processing is reported separately.")));
    const timeOutput = node("span", {}, "Original PTS available in evidence metadata");
    const videoPanel = node("section", { class: "panel" }, heading("External recording and tracked bob", "External footage is not a REALIGN phone experiment.", badge("REAL EXTERNAL", "teal")), stage, node("div", { class: "video-meta" }, timeOutput, node("span", {}, validTrack ? "Overlay: actual tracked centers" : "No SAM overlay available")));
    if (video) video.addEventListener("timeupdate", () => {
      const times = list(metadata.t_s);
      if (!times.length || !times.every(finite)) return;
      const target = times[0] + video.currentTime;
      let lo = 0, hi = times.length - 1;
      while (lo < hi) { const mid = Math.floor((lo + hi) / 2); if (times[mid] < target) lo = mid + 1; else hi = mid; }
      const index = lo > 0 && Math.abs(times[lo - 1] - target) < Math.abs(times[lo] - target) ? lo - 1 : lo;
      timeOutput.textContent = `Frame ${index + 1} · presentation t = ${number(times[index], 4)} s${Array.isArray(metadata.pts) ? ` · PTS ${metadata.pts[index]}` : ""}`;
      if (overlay) {
        overlay.replaceChildren();
        if (track.valid[index]) overlay.append(svg("circle", { cx: track.xy_px[index][0], cy: track.xy_px[index][1], r: Math.max(4, metadata.width / 100), fill: "none", stroke: "#a5e3a5", "stroke-width": Math.max(1.5, metadata.width / 500) }), svg("circle", { cx: track.xy_px[index][0], cy: track.xy_px[index][1], r: Math.max(1.5, metadata.width / 350), fill: "#d1ffb8" }));
      }
    });
    const origin = panel("Attribution and source", "Provenance belongs to this external recording.", node("div", {}, factList([["Creator", text(provenance.creator)], ["License", safeLink(provenance.license_url, text(provenance.license_id))], ["Source page", safeLink(provenance.source_page_url, "Open original source ↗")], ["Capture time scale", provenance.capture_time_scale_verified === true ? "Independently verified" : "Unverified"]]), node("p", { class: "video-attribution spaced-top" }, text(provenance.attribution, "Attribution not available in this response."))));
    const quality = panel("Tracking and review", "No physical dynamics inference is implied.", factList([["SAM processing", text(sam.status).replaceAll("_", " ")], ["Tracked centers", validTrack ? `${integer(validFrames)} / ${integer(metadata.t_s.length)}` : "Unavailable"], ["Missing tracking frames", validTrack ? integer(metadata.t_s.length - validFrames) : "Unavailable"], ["Manual review", text(review.status).replaceAll("_", " ")], ["Physical model comparison", "Unavailable"]]));
    root.append(node("div", { class: "video-grid" }, node("div", { class: "main-column" }, videoPanel, info("Presentation timestamps describe playback. Physical acceleration, peg geometry and dynamical agreement are not inferred without independently verified capture timing and metric calibration.", true)), node("div", { class: "side-column" }, origin, quality)));
    root.append(node("div", { class: "spaced-top" }, panel("Real-video limitations", "Real API and real physical validation are separate acceptance checks.", list(data.limitations).length ? node("ul", { class: "limitations" }, data.limitations.map((value) => node("li", {}, text(value)))) : node("p", { class: "explain-text" }, "The external view contains tracking evidence only. It is not an end-to-end real physical model investigation."))));
    if (assessment) {
      root.append(panel("Independent measurement review", "Reference centers are supplied by a human on clean frames; no SAM hints are prefilled.", node("div", {},
        statusBadge(assessment.status), factList([["Reviewed frames", `${integer(assessment.annotated_frames)} / ${integer(assessment.expected_reference_frames)}`],
          ["Horizontal / vertical bias", Array.isArray(assessment.metrics.bias_px) ? assessment.metrics.bias_px.map(v=>number(v)).join(" / ")+" px" : "Unavailable"],
          ["Median error", finite(assessment.metrics.median_error_px) ? number(assessment.metrics.median_error_px)+" px" : "Unavailable"],
          ["95th percentile error", finite(assessment.metrics.p95_error_px) ? number(assessment.metrics.p95_error_px)+" px" : "Unavailable"],
          ["Reference independence", text(assessment.attestation_status).replaceAll("_", " ")]]),
        state.closure.review_url ? node("a", {href:state.closure.review_url,target:"_blank",rel:"noopener",class:"button"}, "Open independent clean-frame annotation") : null,
        info("The existing twenty-frame sample starts at playback "+number(state.closure.review_sample && state.closure.review_sample.first_pts_s,3)+" s. It does not cover the early rejected frames or validate the full video."),
        panel("Tracking acceptance by playback interval", "Acceptance is a QA count, not measured localization accuracy.", node("div", {}, list(assessment.tracking_intervals).map(row=>node("p", {}, `${number(row.start_pts_s,1)}?${number(row.end_pts_s,1)} s: ${integer(row.accepted_frames)} accepted / ${integer(row.total_frames)}; ${integer(row.rejected_frames)} rejected`)))),
        panel("Visually reviewed contexts", "Visual tags are not physical event ground truth.", factList(Object.entries(assessment.contexts || {}).map(([key,value])=>[key.replaceAll("_"," "), finite(value.rmse_px) ? number(value.rmse_px)+" px RMS ("+integer(value.paired_frames)+" frames)" : "Not validated"]))),
        node("p", {class:"policy-note"}, "Missing independent references remain NOT VALIDATED. No physical G2 acceptance follows from this pixel comparison."))));
    }
    $("content").replaceChildren(root);
  }

  function renderPhone() {
    const phone = state.status && state.status.phone || state.catalog && state.catalog.phone || {};
    const root = node("div", {}, node("section", { class: "decision-hero" }, badge("REAL PHONE", "teal"), node("h2", {}, "The next evidence comes from the rig."), node("p", {}, "Controlled physical recordings, independent calibration and reviewed tracking are required before this source can support a real-world investigation."), node("div", { class: "badges" }, statusBadge(phone.status), badge("PHYSICAL VALIDATION PENDING", "amber"))));
    const physical = state.closure && state.closure.phone;
    if (physical) {
      root.append(panel("Controlled investigation status", "A physical request is completed only by a matching, validated recording response.", node("div", {},
        statusBadge(physical.status), node("ul", {class:"limitations"}, list(physical.blockers).map(x=>node("li", {}, text(x)))),
        physical.pending_action ? factList([["Pending action", actionSummary(physical.pending_action.candidate && physical.pending_action.candidate.action)],
          ["Request hash", shortHash(physical.pending_action.request_id)], ["Response received", "No"], ["Model frozen", "No"]]) : node("p", {}, physical.model_frozen ? "The investigation decision is frozen. Any received recording is documented in its audited receipt; independent evaluation is reported separately." : "No physical experiment has been requested: independent recording prerequisites are still missing."),
        physical.model_frozen ? hashBlock("FROZEN PHYSICAL MODEL DECISION", physical.decision && physical.decision.freeze_sha256) : null)));
    }
    const requirements = [
      ["Original phone recordings", "Stationary reference, repeated free swings and peg-contact trials. Preserve the original files and capture metadata."],
      ["Independent camera measurements", "Measured planar calibration points, a physical scale reference and pivot location; lens calibration when needed."],
      ["Reviewed reference frames", "Manually reviewed bob centers, release-time brackets and a documented uncertainty estimate."],
      ["Frozen trial assignments", "Distinct exploration, development and future sealed recordings, assigned before analysis."],
    ];
    root.append(node("div", { class: "two-column" }, panel("Required physical inputs", "Follow docs/REAL_DATA_COLLECTION_PROTOCOL.md.", node("ol", { class: "phone-checklist" }, requirements.map(([title, detail]) => node("li", {}, node("div", {}, node("strong", {}, title), node("p", {}, detail)))))), panel("Why this view remains separate", null, node("div", {}, node("p", { class: "explain-text" }, "Synthetic study outcomes, real external video tracking and controlled phone experiments answer different scientific questions. None can silently stand in for another."), info("The synthetic null calibration does not authorize structural repair acceptance on real measurements.", true), node("div", { class: "download-row" }, button("Inspect the synthetic demonstration →", () => setSource("synthetic")), button("Inspect external SAM evidence", () => setSource("external")))))));
    $("content").replaceChildren(root);
  }

  document.querySelectorAll("[data-view]").forEach((item) => item.addEventListener("click", () => setView(item.dataset.view)));
  document.querySelectorAll("[data-source]").forEach((item) => item.addEventListener("click", () => setSource(item.dataset.source)));
  $("run-select").addEventListener("change", (event) => loadRun(event.target.value));
  $("replay-button").addEventListener("click", () => {
    state.source = "synthetic"; state.view = "reality"; state.frame = 0; state.playing = false;
    if (state.round === "development") state.round = 1;
    render(); togglePlayback();
  });
  window.addEventListener("pagehide", () => { state.playing = false; });
  loadApp();
  requestAnimationFrame(tick);
})();
