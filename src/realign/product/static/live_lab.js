"use strict";
(() => {
  const $ = id => document.getElementById(id);
  let token = null, busy = false, connected = false, previewTimer = null;
  const element = (tag, text) => { const e = document.createElement(tag); if(text !== undefined) e.textContent = text; return e; };
  const metadata = () => ({role:$("role").value,operator:$("operator").value,rig_id:$("rig").value,...($("request").value ? {response_to_request_id:$("request").value} : {})});
  async function api(path, body) {
    const response = await fetch(path, {cache:"no-store", ...(body ? {method:"POST",headers:{"Content-Type":"application/json","X-Live-Lab-Token":token},body:JSON.stringify(body)} : {})});
    const result = await response.json(); if(!response.ok) throw new Error(result.error || `HTTP ${response.status}`); return result;
  }
  async function action(path, body={}) {
    if(busy) return; busy=true; $("error").textContent="";
    try { const r=await api(path,body); await status(); await recordings(); return r; }
    catch(e) { $("error").textContent=e.message; }
    finally {busy=false;}
  }
  async function status() {
    try {
      const s=await api("/api/status"); token=s.control_token;
      connected=Boolean(s.camera) && s.state!=="FAILED" && s.state!=="IDLE";
      $("camera-state").textContent=s.state+(s.error ? ` · ${s.error}` : "")+(s.camera_stalled ? " · CAMERA_STALLED: stop and check connection" : "");
      const c=s.capture;
      $("telemetry").textContent=`${c.frames} recorded frames · arrival FPS ${c.effective_fps?.toFixed(2) ?? "unknown"} · gap indicators ${c.gap_indicators} · physical time UNVERIFIED`;
      $("start").disabled=!connected || s.state==="RECORDING" || s.camera_stalled;
      $("stop").disabled=s.state!=="RECORDING";
      $("connect").disabled=connected; $("scan").disabled=connected;
      $("disconnect").disabled=!s.camera; $("import").disabled=s.state==="RECORDING";
      $("preview").hidden=!connected;
      renderInvestigation(s.investigation, s.state);
      if(connected && !previewTimer) nextPreview();
      if(!connected && previewTimer) {clearTimeout(previewTimer);previewTimer=null;}
    } catch(e) { $("error").textContent=`Controller unavailable: ${e.message}`; }
  }
  let processedWindow = null, pendingRequest = null;
  function renderInvestigation(live, captureState) {
    const active=live && live.usage.enabled;
    $("ai-start").disabled=!connected || Boolean(live);
    for(const id of ["ai-stop","ai-reason","admit-evidence"]) $(id).disabled=!active;
    if(!live) return;
    $("ai-state").textContent=`${captureState==="RECORDING" ? "LIVE CAPTURE · " : ""}${live.state.replaceAll("_"," ")} · ${live.source}`;
    const u=live.usage;
    $("ai-usage").textContent=`Actual dispatched/reserved attempts: SAM ${u.attempted_requests.sam}, Muse ${u.attempted_requests.muse}; total ${u.total_requests}. Reserved USD ${u.reserved_usd} / ${u.ceiling_usd}. ${u.billing_status}`;
    $("ai-queues").textContent=`Windows finalized ${live.finalized_windows}, processed ${live.processed_windows}; queues ${live.queued_frames} frames / ${live.queued_windows} windows. Backpressure drops: ${JSON.stringify(live.dropped)}. Unique source observations: ${live.unique_observations}.`;
    const latest=live.latest;
    $("ai-detection").textContent=latest ? `${latest.status} · ${latest.window_id} · service ${latest.latency_s.toFixed(2)} s · queue + service ${latest.end_to_end_latency_s.toFixed(2)} s · ${latest.identity_continuity}` : "SAM PENDING · waiting for a finalized window";
    if(latest && latest.rows.length && latest.window_id!==processedWindow) {
      processedWindow=latest.window_id; $("processed").hidden=false; $("processed").src="/processed.jpg?window="+encodeURIComponent(latest.window_id)+"&t="+Date.now();
      $("processed-label").textContent=`${latest.window_id} · source frame ${latest.rows.at(-1).capture_sequence} · delayed SAM result; not live preview`;
      const canvas=$("trajectory"),ctx=canvas.getContext("2d"),size=latest.rows[0].processed_size;
      ctx.clearRect(0,0,640,480); ctx.strokeStyle="#24845c";ctx.lineWidth=2;ctx.beginPath();
      latest.rows.forEach((r,i)=>{const x=r.xy_px[0]*640/size[0],y=r.xy_px[1]*480/size[1];if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.stroke();
    }
    $("science-status").textContent=JSON.stringify(live.scientific,null,2);
    const comparison=live.scientific.trajectory_comparison;
    if(comparison) {
      $("simulation-status").textContent=`${comparison.trial_id} · ${comparison.scope} · measured green / nominal simulation amber`;
      const ctx=$("trajectory").getContext("2d");ctx.clearRect(0,0,640,480);
      for(const [key,color] of [["measured_px","#45b985"],["simulated_px","#ffb457"]]) {
        ctx.strokeStyle=color;ctx.beginPath();comparison[key].forEach((p,i)=>{const x=p[0]*640/comparison.image_size[0],y=p[1]*480/comparison.image_size[1];if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.stroke();
      }
    }
    $("experiment-history").textContent=JSON.stringify({experiments:live.experiment_history,audit_head:live.audit_head},null,2);
    const pending=live.pending_action; pendingRequest=pending?.request_id;
    $("pending-action").hidden=!pending;
    if(pending) {$("action-text").textContent=JSON.stringify(pending,null,2);$("confirm-action").disabled=!active || Boolean(pending.confirmed_utc);$("request").value=pending.request_id;}
    const events=$("ai-events");events.replaceChildren();
    for(const event of live.events.slice(-20).reverse()) events.append(element("li",`${event.payload.utc} · ${event.kind} · ${JSON.stringify(event.payload).slice(0,500)}`));
  }
  function nextPreview() {
    if(!connected) {previewTimer=null;return;}
    $("preview").src="/preview.jpg?t="+Date.now();
    previewTimer=setTimeout(nextPreview,100); // latest JPEG only, no frame queue
  }
  async function recordings() {
    const data=await api("/api/recordings"); const root=$("recordings");root.replaceChildren();
    if(!data.recordings.length) root.append(element("p","No saved recordings. Capture or import a real clip."));
    for(const r of data.recordings) {
      const card=element("article");card.className="clip";
      card.append(element("h3",r.id),element("p",`${r.status} · ${r.state || "Unavailable"}`));
      if(!r.media) {root.append(card);continue;}
      const m=r.media;
      card.append(element("p",`Media: ${m.status} · ${m.decoded_frames ?? "?"} decoded frames · ${m.width ?? "?"} × ${m.height ?? "?"} · VFR ${m.variable_frame_rate ?? "unknown"}`));
      const hash=element("p",`SHA-256: ${r.video_sha256}`);hash.className="hash";card.append(hash);
      card.append(element("p",`Source: ${r.provenance.kind} · SAM ${r.sam.status} · calibration ${r.calibration_grade} · PTS_ONLY · independent validation ${r.independent_validation.status}`));
      const frames=element("div");frames.className="frames";
      for(const file of m.review_frames || []) {const img=element("img");img.src=`/files/${r.id}/${file}`;img.alt="Clean framing review: "+file;frames.append(img);}card.append(frames);
      if(m.status==="ADMITTED") {const video=element("video");video.controls=true;video.preload="none";video.src=`/files/${r.id}/recording.mp4`;video.setAttribute("aria-label","Saved recording "+r.id);card.append(video);}
      card.append(element("p","Admission blockers (media preflight alone does not clear them):"));
      const ul=element("ul");for(const b of r.blockers) ul.append(element("li",b));card.append(ul);
      for(const [file,label] of [["recording.mp4","Download recording"],["report.json","Source and PTS report"],["phone_manifest.draft.json","Phone manifest draft"]]) {const a=element("a",label);a.href=`/files/${r.id}/${file}`;a.download=file;card.append(a);}
      root.append(card);
    }
  }
  $("scan").onclick=async()=>{const r=await action("/api/scan");if(!r)return;$("devices").replaceChildren();for(const d of r.devices){const o=element("option",`${d.label} · ${d.backend}`);o.value=d.index;$("devices").append(o);}if(!r.devices.length)$("error").textContent="No camera found. Check Windows device connection or import the original MP4.";};
  $("connect").onclick=()=>action("/api/connect",{index:Number($("devices").value)});
  $("disconnect").onclick=()=>action("/api/disconnect");
  $("start").onclick=()=>action("/api/start",metadata());
  $("stop").onclick=()=>action("/api/stop");
  $("import").onclick=()=>action("/api/import",{...metadata(),path:$("path").value});
  $("ai-start").onclick=()=>action("/api/ai/start",{authorization:{consent:$("ai-consent").checked,standard_tier_confirmed:$("ai-consent").checked,sam_requests:Number($("sam-cap").value),muse_requests:Number($("muse-cap").value),ceiling_usd:$("spend-cap").value,sam_reserve_usd:$("sam-reserve").value,muse_reserve_usd:$("muse-reserve").value},windowing:{window_s:Number($("window-seconds").value),overlap_s:Number($("overlap-seconds").value)}});
  // Revocation stays available while another local media action is busy.
  $("ai-stop").onclick=()=>api("/api/ai/stop",{}).then(status).catch(e=>$("error").textContent=e.message);
  $("processed").onerror=()=>{processedWindow=null;};
  $("ai-reason").onclick=()=>action("/api/ai/reason");
  $("confirm-action").onclick=()=>action("/api/ai/confirm-action",{request_id:pendingRequest});
  $("admit-evidence").onclick=()=>action("/api/ai/admit",{manifest:$("approved-manifest").value});
  $("refresh").onclick=()=>recordings().catch(e=>$("error").textContent=e.message);
  status();recordings().catch(e=>$("error").textContent=e.message);setInterval(status,1500);
})();
