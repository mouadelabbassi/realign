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
      if(connected && !previewTimer) nextPreview();
      if(!connected && previewTimer) {clearTimeout(previewTimer);previewTimer=null;}
    } catch(e) { $("error").textContent=`Controller unavailable: ${e.message}`; }
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
  $("refresh").onclick=()=>recordings().catch(e=>$("error").textContent=e.message);
  status();recordings().catch(e=>$("error").textContent=e.message);setInterval(status,1500);
})();
