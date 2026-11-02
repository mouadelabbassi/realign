// Expanded review extension. Human input only; tracker/AI outputs never loaded.
let lockedDocument=null;
$('not-visible').addEventListener('click',()=>{rows[frame].center_px=null;rows[frame].annotation_sigma_px=null;rows[frame].not_visible=true;$('sigma').value='';draw();$('coordinate').textContent='Marked not visible.';});
canvas.addEventListener('click',()=>{rows[frame].not_visible=false;draw();});
$('clear').addEventListener('click',()=>{rows[frame].not_visible=false;draw();});
function canonicalJSON(value){
  if(Array.isArray(value))return '['+value.map(canonicalJSON).join(',')+']';
  if(value!==null&&typeof value==='object')return '{'+Object.keys(value).sort().map(k=>JSON.stringify(k)+':'+canonicalJSON(value[k])).join(',')+'}';
  return JSON.stringify(value);
}
$('lock').addEventListener('click',async()=>{
  const placed=rows.filter(r=>r.center_px!==null);
  if(!$('reviewer').value.trim()||!$('independent').checked){$('status').textContent='Confirm named independent annotation before locking.';return;}
  if(rows.some(r=>r.center_px===null&&r.not_visible!==true)||placed.some(r=>r.annotation_sigma_px===null)){$('status').textContent='Review every frame with a center and uncertainty, or mark it not visible.';return;}
  annotation.reviewer=$('reviewer').value.trim();annotation.independent_of_sam=true;annotation.reviewed_utc=new Date().toISOString();
  const payload=canonicalJSON(annotation),bytes=new TextEncoder().encode(payload);
  const hash=await crypto.subtle.digest('SHA-256',bytes);
  lockedDocument=structuredClone(annotation);lockedDocument.lock={payload_json:payload,sha256:Array.from(new Uint8Array(hash)).map(x=>x.toString(16).padStart(2,'0')).join('')};
  document.querySelectorAll('input,#clear,#not-visible,#lock').forEach(e=>e.disabled=true);canvas.style.pointerEvents='none';
  $('download').disabled=false;$('status').textContent='LOCKED locally. Download JSON and import it explicitly with the CLI. No server write occurred.';
});
$('download').addEventListener('click',()=>{
  if(!lockedDocument)return;
  const url=URL.createObjectURL(new Blob([JSON.stringify(lockedDocument,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='external-independent-locked.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
