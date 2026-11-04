"use strict";
(() => {
  const $=id=>document.getElementById(id), md=(id,value)=>RealignMarkdown.render($(id),value);
  const el=(tag,text,cls)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined){if(['pre','code','option'].includes(tag))n.textContent=text;else {n.classList.add('markdown');n.append(RealignMarkdown.fragment(text));}}return n;};
  const human=value=>String(value??'Unknown').replaceAll('_',' ').toLowerCase().replace(/^\w/,c=>c.toUpperCase());
  const short=value=>value?String(value).slice(0,12)+'…':'Unavailable';
  const sec=value=>Number.isFinite(value)?value.toFixed(1)+' s':'Unknown';
  let token=null,busy=false,polling=false,connected=false,scanning=false,hasScanned=false,previewTimer=null,lastLive=null,lastScan=null,lastOverlay=null,lastScience=null,lastHistory=null,lastEvents=null,pendingRequest=null;
  function error(message){$('error').hidden=!message;md('error',message||'');}
  async function api(path,body){
    const response=await fetch(path,{cache:'no-store',...(body!==undefined?{method:'POST',headers:{'Content-Type':'application/json','X-Live-Lab-Token':token},body:JSON.stringify(body)}:{})});
    const result=await response.json();if(!response.ok)throw Error(result.error||`HTTP ${response.status}`);return result;
  }
  const metadata=()=>({role:$('role').value,operator:$('operator').value,rig_id:$('rig').value,...($('request').value?{response_to_request_id:$('request').value}:{})});
  async function action(path,body={}){
    if(busy){error('A local capture control is still finishing. Retry after it completes.');return;}
    busy=true;error('');try{const r=await api(path,body);await status();await recordings();return r;}catch(e){error(e.message);}finally{busy=false;}
  }
  async function priority(path,body={}){try{error('');await api(path,body);await status();}catch(e){error(e.message);}}
  async function status(){
    if(polling)return;polling=true;
    try{
      const s=await api('/api/status');token=s.control_token;connected=Boolean(s.camera)&&!['IDLE','FAILED'].includes(s.state);
      md('camera-state',s.state+(s.error?` · ${s.error}`:'')+(s.camera_stalled?' · CAMERA_STALLED':''));$('camera-state').classList.toggle('live',s.state==='RECORDING');
      const c=s.capture;md('telemetry',`${c.frames.toLocaleString()} recorded frames · arrival FPS ${c.effective_fps?.toFixed(2)??'unknown'} · ${c.gap_indicators} gap indicators · physical timing unverified`);
      md('capture-indicator',s.state==='RECORDING'?'● RECORDING':connected?'● LIVE PREVIEW':'CAMERA OFFLINE');
      $('start').disabled=busy||!connected||s.state==='RECORDING'||s.camera_stalled;$('stop').disabled=busy||s.state!=='RECORDING';$('connect').disabled=busy||connected||scanning||(hasScanned&&!$('devices').options.length);$('scan').disabled=busy||connected||scanning;$('devices').disabled=busy||connected||scanning||(hasScanned&&!$('devices').options.length);$('disconnect').disabled=busy||!s.camera;$('import').disabled=busy||s.state==='RECORDING';
      $('preview').hidden=!connected;$('preview-empty').hidden=connected;
      if(connected&&!previewTimer)nextPreview();if(!connected&&previewTimer){clearTimeout(previewTimer);previewTimer=null;}
      lastScan=s.device_scan;renderInvestigation(s.investigation,s.state);
      if($('raw-audit').parentElement.open)$('raw-audit').textContent=JSON.stringify({investigation:lastLive,camera_discovery:lastScan},null,2);
    }catch(e){error(`Controller unavailable: ${e.message}`);}finally{polling=false;}
  }
  function nextPreview(){if(!connected){previewTimer=null;return;}$('preview').src='/preview.jpg?t='+Date.now();previewTimer=setTimeout(nextPreview,100);}
  function renderInvestigation(live,capture){
    lastLive=live;const active=Boolean(live?.usage.enabled),paused=Boolean(live?.usage.paused);
    $('ai-start').disabled=Boolean(live);$('ai-stop').disabled=!active;$('ai-pause').disabled=!active||paused;$('ai-pause').hidden=paused;$('ai-resume').hidden=!paused;$('ai-resume').disabled=!active;$('admit-evidence').disabled=!active||paused;
    const phases=[Boolean(live),connected,Boolean(live?.unique_observations),Boolean(live?.experiment_history.length)];
    ['authorize','connect','observe','experiment'].forEach((name,i)=>{const n=$('step-'+name);n.classList.toggle('done',phases[i]);n.classList.toggle('active',!phases[i]&&(i===0||phases[i-1]));});
    if(!live){drawTrajectory([]);return;}
    $('fixture-label').hidden=live.source!=='TEST_FIXTURE';
    const u=live.usage,sc=live.scientific,latest=live.latest,d=latest?.diagnostic;
    md('ai-state',`${live.mode} · ${live.lifecycle} · ${live.state} · ${live.source}`);
    md('usage-count',`${u.total_requests} attempts`);md('sam-usage',`${u.attempted_requests.sam} / ${u.policy.sam_requests}`);md('muse-usage',`${u.attempted_requests.muse} / ${u.policy.muse_requests}`);
    $('usage-progress').value=Number(u.reserved_usd);$('usage-progress').max=Number(u.ceiling_usd);
    md('ai-usage',`**USD ${u.reserved_usd} reserved** of USD ${u.ceiling_usd} authorized. Uploads and retries count. ${paused?'AI is paused.':!active?'Authorization revoked; no further requests.':'Request counts and reserves are enforced before dispatch.'}`);
    const t=live.throughput;
    md('ai-queues',`**${live.finalized_windows}** finalized video windows · **${live.processed_windows}** completed video responses · **${live.usable_windows}** usable responses.\n\n${live.queued_frames} queued frames / ${live.queued_windows} pending video windows. **${Object.values(live.dropped).reduce((a,b)=>a+b,0)}** skipped or dropped work items.\n\nPolicy: one freshest pending window. Configured interval ${sec(t.analysis_interval_s)}; adaptive interval ${sec(t.effective_analysis_interval_s)}. ${t.service_slower_than_cadence?'SAM is slower than the configured cadence. Tracking is intermittent.':''}\n\n${Object.entries(t.skipped_windows_by_reason).map(([k,v])=>`- ${human(k)}: ${v}`).join('\n')}`);
    const ov=live.overlay,samState=live.target_blocked?'NO_TARGET_OBSERVED':t.sam_active_window?'SAM_PENDING':ov?.status||'SAM_PENDING';md('sam-status',samState);
    $('sam-status').classList.toggle('live',Boolean(ov)&&ov.status==='SAM_CONFIRMED');
    md('metric-points',String(live.unique_observations));md('metric-masks',d?String(d.returned_mask_count):ov?String(ov.boxes.length):'—');md('metric-lag',sec(ov?.processing_latency_s??t.last_service_latency_s));
    const confidence=ov?.boxes[0]?.confidence;md('metric-confidence',Number.isFinite(confidence)?`SAM confidence ${(confidence*100).toFixed(1)}%`:'Confidence unknown · not supplied');
    if(d){
      md('ai-detection',`**${d.returned_mask_count} masks returned** · ${d.valid_frame_count} valid / ${d.invalid_or_missing_frame_count} missing or rejected frames. ${latest.media_kind==='image'?'Startup image':'Video window'} \`${latest.window_id}\` · service ${sec(latest.latency_s)}.`);
      md('detection-guidance',`**${d.code}**\n\n${d.guidance}`);
      md('target-identity',`Target: **${d.target_prompt}** · ${d.target_identity_status}. Returned SAM IDs: ${d.returned_object_ids.join(', ')||'none'}.`);
      const p=d.preprocessing;md('preprocessing-status',`Source **${p.source_size.join(' × ')}** → processed **${p.processed_size.join(' × ')}**. Scale ${p.scale_xy.map(x=>x.toFixed(3)).join(' / ')}. ${p.visibility}.\n\n${Object.entries(d.rejection_reasons).map(([k,v])=>`- ${k}: ${v}`).join('\n')}`);
    }else md('ai-detection',t.sam_active_window?`SAM processing \`${t.sam_active_window}\`. Verified partial masks may appear before stream completion.`:'Waiting for the first saved source frame. No Muse call is needed yet.');
    if(live.perception_error){md('sam-status','TRACK_LOST');md('detection-guidance',`**${live.perception_error.code}**\n\nSAM did not produce a completed usable result. Inspect the safe error and call receipts in the audit; earlier partial masks do not become scientific evidence.`);}
    $('target-revision').hidden=!live.target_blocked;
    if(live.target_blocked&&!$('revised-prompt').value)$('revised-prompt').value=live.windowing.target_prompt;
    if(ov){
      $('sam-preview').hidden=false;
      if(lastOverlay!==ov.revision){lastOverlay=ov.revision;$('sam-overlay').src='/sam-frame.jpg?revision='+ov.revision;}
      const stale=ov.source_frame_age_s>Math.max(10,t.effective_analysis_interval_s*2+live.windowing.window_s);
      md('tracking-label',ov.status==='TRACK_LOST'||stale?'TRACK_LOST · last source':`SAM_CONFIRMED · ${ov.stream_completed?'completed':'partial stream'}`);
      md('overlay-age',`Frame ${ov.source_frame.capture_sequence} · ${sec(ov.source_frame_age_s)} old · latency ${sec(ov.processing_latency_s)}${ov.presentation_only?' · presentation only':''}`);
      if(ov.stream_completed){$('processed').hidden=false;$('processed').src='/processed.jpg?window='+encodeURIComponent(ov.window_id);md('processed-label',`${ov.window_id} · exact source frame ${ov.source_frame.capture_sequence} · ${short(ov.source_sha256)} · delayed evidence`);}
    }else $('sam-preview').hidden=true;
    md('readiness-text',sc.readiness?`**${sc.readiness.code}**\n\n${sc.readiness.operator_request}`:'Waiting for new eligible evidence.');
    const failure=sc.last_error;$('science-error').hidden=!failure;if(failure)md('science-error',`**${failure.category} · ${failure.code}**\n\nHTTP ${failure.http_status??'not applicable / not recorded'}. ${failure.guidance}`);
    renderScience(sc);renderAction(live.pending_action,active&&!paused);renderHistory(live);
    drawTrajectory(live.historical_trajectory,sc.trajectory_comparison);
    md('audit-label',`Hash-linked · ${short(live.audit_head)}`);
  }
  function renderScience(sc){
    const sig=JSON.stringify([sc.hypotheses,sc.tool_results,sc.decision,sc.state,sc.visual_observation]);if(sig===lastScience)return;lastScience=sig;
    const root=$('science-status');root.replaceChildren();
    if(!sc.hypotheses.length)root.append(el('p',sc.state==='AGENT_INVESTIGATING'?'Muse is examining the new evidence…':'Muse is waiting for new usable observations.','waiting-title'));
    for(const h of sc.hypotheses){const card=el('article',undefined,'hypothesis-card');card.append(el('h3',human(h.family)),el('p',`**${h.status}** · ${h.evidence_refs.length} source reference${h.evidence_refs.length===1?'':'s'}`));if(h.evidence_refs.length)card.append(el('p',h.evidence_refs.map(r=>`\`${short(r)}\``).join(' · ')));root.append(card);}
    const motion=sc.visual_observation?.pixel_motion;
    if(motion)root.append(el('p',`**Observed pixels:** ${motion.samples} samples; displacement ${motion.displacement_px.map(x=>x.toFixed(1)).join(' / ')} px. ${motion.samples<2?'One still image cannot establish motion.':'These sampled pixel changes do not establish physical velocity.'}`));
    if(sc.decision)root.append(el('div',`### ${human(sc.decision.outcome)}\n\n${sc.decision.reasons.map(human).join('\n\n')}\n\nIndependent validation: **${sc.independent_validation??'NOT_RUN'}**`));
    if(sc.hypotheses.length&&!sc.physical_evidence_accepted)root.append(el('p','Preliminary visual evidence only. Metric fitting and physical repair acceptance remain blocked.'));
    const tools=$('tool-results');tools.replaceChildren();
    for(const r of sc.tool_results.slice(-5)){const result=r.result||r;const card=el('article',undefined,'tool-card');card.append(el('h3',human(r.name||r.tool||'Scientific tool')),el('p',`Evidence: \`${short(result.evidence_ref)}\``));const rows=Object.entries(result).filter(([k,v])=>k!=='evidence_ref'&&(typeof v==='number'||typeof v==='boolean'||v===null)).slice(0,8);if(rows.length)card.append(el('div','| Metric | Result |\n| --- | --- |\n'+rows.map(([k,v])=>`| ${human(k)} | ${v===null?'Unavailable':v} |`).join('\n')));tools.append(card);}
  }
  const actionGuidance={STATIONARY_REFERENCE:'Keep the camera and support fixed. Record the target at rest as an independent stationary reference.',CAMERA_CALIBRATION:'Measure and record the calibration geometry in the motion plane. Supply independently reviewed calibration evidence.',RELEASE:'Perform the approved release experiment with a fixed pivot and a visible release. Supply independent timing and human annotations.',REPEAT:'Repeat the specified experiment as a genuinely distinct recording. Preserve the same reviewed rig and measurement setup.'};
  function renderAction(pending,active){
    pendingRequest=pending?.request_id;$('pending-action').hidden=!pending;if(!pending)return;
    const a=pending.candidate.action;md('action-title',human(a.kind));
    const params=Object.entries(a).filter(([k])=>!['kind','schema_version'].includes(k)).map(([k,v])=>`- **${human(k)}:** ${typeof v==='object'?'See approved action in audit':v}`).join('\n');
    md('action-text',`**${a.kind}**\n\n${actionGuidance[a.kind]||'Perform only the approved physical action; review its exact parameters in the audit.'}\n\n${params}\n\n${pending.confirmed_utc?'**Human intent confirmed.** Recording response evidence; waiting for independent admission.':'**Waiting for you.** The scientific checkpoint is preserved.'}\n\nRequest \`${short(pending.request_id)}\``);
    $('confirm-action').disabled=!active||Boolean(pending.confirmed_utc);$('request').value=pending.request_id;
  }
  function renderHistory(live){
    const hs=JSON.stringify(live.experiment_history);if(hs!==lastHistory){lastHistory=hs;const root=$('experiment-history');root.replaceChildren();if(!live.experiment_history.length)root.append(el('p','No experiment response has passed admission yet.','fine'));for(const h of live.experiment_history)root.append(el('div',`**${human(h.candidate.action.kind)}** · ${h.state}\n\nResponse manifest \`${short(h.response_manifest_sha256)}\``));}
    const events=live.events.slice(-16).reverse(),es=JSON.stringify(events.map(e=>e.hash));if(es===lastEvents)return;lastEvents=es;const root=$('ai-events');root.replaceChildren();
    for(const event of events){const p=event.payload,li=el('li');const time=el('time',new Date(p.utc).toLocaleTimeString());time.dateTime=p.utc;li.append(time,el('strong',human(event.kind)));const detail=p.code||p.window_id||p.kind||p.operation||(p.request_id?'Request '+short(p.request_id):p.reason);if(detail)li.append(el('p',human(detail)));root.append(li);}
  }
  function drawTrajectory(rows=[],comparison){
    const canvas=$('trajectory'),ctx=canvas.getContext('2d'),w=canvas.width,h=canvas.height;ctx.clearRect(0,0,w,h);ctx.strokeStyle='#e8eee2';ctx.lineWidth=1;
    for(let x=40;x<w;x+=80){ctx.beginPath();ctx.moveTo(x,15);ctx.lineTo(x,h-15);ctx.stroke();}for(let y=30;y<h;y+=60){ctx.beginPath();ctx.moveTo(15,y);ctx.lineTo(w-15,y);ctx.stroke();}
    $('trajectory-empty').hidden=Boolean(rows.length||comparison);
    const line=(points,size,color)=>{ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();points.forEach((p,i)=>{const x=p[0]*w/size[0],y=p[1]*h/size[1];if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.stroke();};
    if(comparison){md('simulation-status',`${comparison.trial_id} · ${comparison.scope}. Measured green / nominal prediction amber. Independent evaluation has not run.`);for(const [key,color] of [['measured_px','#2c856b'],['simulated_px','#bb9045']])line(comparison[key],comparison.image_size,color);return;}
    let group=[],key=null;for(const row of rows){const k=[row.recording_id,row.window_id,row.object_id].join(':');if(key&&k!==key){line(group.map(r=>r.xy_px),group[0].processed_size||[640,480],'#2c856b');group=[];}key=k;group.push(row);}if(group.length)line(group.map(r=>r.xy_px),group[0].processed_size||[640,480],'#2c856b');
    for(const r of rows.slice(-150)){const size=r.processed_size||[640,480];ctx.beginPath();ctx.arc(r.xy_px[0]*w/size[0],r.xy_px[1]*h/size[1],2.3,0,Math.PI*2);ctx.fillStyle='#3c9174';ctx.fill();}
  }
  async function recordings(){
    const data=await api('/api/recordings'),root=$('recordings');root.replaceChildren();if(!data.recordings.length)root.append(el('p','No saved source recordings yet. Capture or import an original clip.','fine'));
    for(const r of data.recordings){const card=el('article',undefined,'clip');card.append(el('h3',r.id),el('p',`**${r.status}** · ${r.state||'Unavailable'}`));if(!r.media){root.append(card);continue;}const m=r.media;card.append(el('p',`${m.status} · ${m.decoded_frames??'?'} decoded frames · ${m.width??'?'} × ${m.height??'?'} · variable frame rate ${m.variable_frame_rate??'unknown'}`),el('p','SHA-256: '+r.video_sha256,'hash'),el('p',`Source ${r.provenance.kind} · SAM ${r.sam.status} · calibration ${r.calibration_grade} · physical timing unverified`));const frames=el('div',undefined,'frames');for(const file of m.review_frames||[]){const img=el('img');img.src=`/files/${r.id}/${file}`;img.alt='Clean source review: '+file;frames.append(img);}card.append(frames);if(m.status==='ADMITTED'){const video=el('video');video.controls=true;video.preload='none';video.src=`/files/${r.id}/recording.mp4`;video.setAttribute('aria-label','Saved recording '+r.id);card.append(video);}const list=el('ul');for(const b of r.blockers)list.append(el('li',b));card.append(list);for(const [file,label] of [['recording.mp4','Download recording'],['report.json','Source and PTS report'],['phone_manifest.draft.json','Phone manifest draft']]){const a=el('a',label);a.href=`/files/${r.id}/${file}`;a.download=file;card.append(a);}root.append(card);}
  }
  $('open-authorization').onclick=()=>{$('authorization').open=!$('authorization').open;if($('authorization').open)$('authorization').scrollIntoView({behavior:'smooth',block:'start'});};
  $('scan').onclick=async()=>{
    if(busy)return error('A local control is still finishing. Retry Find cameras when it completes.');
    scanning=true;$('scan').disabled=true;$('connect').disabled=true;$('devices').disabled=true;$('scan').setAttribute('aria-busy','true');md('scan-label','Searching…');
    md('camera-discovery','Searching camera inputs 0–7. This may take a few seconds; no video is uploaded.');
    try{
      const r=await action('/api/scan',{maximum:8});if(!r){md('camera-discovery','Camera search could not complete. Review the local error above, then try Find cameras again.');return;}
      hasScanned=true;$('devices').replaceChildren();
      for(const d of r.devices){const o=el('option',`Camera ${d.index} · ${d.backend}`);o.value=d.index;$('devices').append(o);}
      md('camera-discovery',r.devices.length?`**${r.devices.length} camera${r.devices.length===1?'':'s'} found.** Select a device, then Connect to identify your phone in the preview. ${r.scan?.probe_errors?.length?'Some inputs could not be probed; their safe codes are in the audit.':''}`:'**No cameras found on inputs 0–7.** Check Windows camera permissions, connect your phone through its webcam app/USB, close other apps using it, then try Find cameras again. You can also import the original MP4.');
    }finally{scanning=false;$('scan').removeAttribute('aria-busy');md('scan-label','Find cameras');await status();}
  };
  $('connect').onclick=()=>action('/api/connect',{index:Number($('devices').value)});$('disconnect').onclick=()=>action('/api/disconnect');$('start').onclick=()=>action('/api/start',metadata());$('stop').onclick=()=>action('/api/stop');$('import').onclick=()=>action('/api/import',{...metadata(),path:$('path').value});
  $('ai-start').onclick=async()=>{
    const r=await action('/api/auto-live/authorize',{authorization:{consent:$('ai-consent').checked,standard_tier_confirmed:$('ai-consent').checked,sam_requests:Number($('sam-cap').value),muse_requests:Number($('muse-cap').value),ceiling_usd:$('spend-cap').value,sam_reserve_usd:$('sam-reserve').value,muse_reserve_usd:$('muse-reserve').value},windowing:{window_s:Number($('window-seconds').value),overlap_s:Number($('overlap-seconds').value),analysis_interval_s:Number($('analysis-interval').value),processing_width:Number($('processing-width').value),target_prompt:$('target-prompt').value,target_confirmed:$('target-confirmed').checked},metadata:{operator:$('operator').value,rig_id:$('rig').value}});
    if(r){$('authorization').open=false;$('workspace').scrollIntoView({behavior:'smooth',block:'start'});}
  };
  $('ai-stop').onclick=()=>priority('/api/ai/stop');$('ai-pause').onclick=()=>priority('/api/ai/pause');$('ai-resume').onclick=()=>priority('/api/ai/resume');
  $('reselect-target').onclick=async()=>{const consent=$('revision-consent').checked;const r=await action('/api/ai/reselect',{target_prompt:$('revised-prompt').value,target_confirmed:consent,consent});if(r)$('revision-consent').checked=false;};
  $('confirm-action').onclick=()=>action('/api/ai/confirm-action',{request_id:pendingRequest});$('admit-evidence').onclick=()=>action('/api/ai/admit',{manifest:$('approved-manifest').value});$('refresh').onclick=()=>recordings().catch(e=>error(e.message));
  $('raw-audit').parentElement.addEventListener('toggle',()=>{if($('raw-audit').parentElement.open)$('raw-audit').textContent=JSON.stringify({investigation:lastLive,camera_discovery:lastScan},null,2);});
  $('sam-overlay').onerror=()=>{lastOverlay=null;};
  status();recordings().catch(e=>error(e.message));setInterval(status,600);
})();
