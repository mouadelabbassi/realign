"use strict";


(() => {
  const escape = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const math = (text,display) => katex.renderToString(text,{displayMode:display,throwOnError:false,trust:false,maxExpand:1000,maxSize:20,strict:'ignore'});
  marked.use({gfm:true,breaks:true,renderer:{
    html:token=>escape(token.text),
    image:token=>`<span class="markdown-image-label">${escape(token.text || 'Image omitted')}</span>`,
    checkbox:token=>`<span class="task-check" aria-label="${token.checked?'complete':'incomplete'}">${token.checked?'☑':'☐'}</span>`
  },extensions:[
    {name:'displayMath',level:'block',start:src=>src.search(/\$\$|\\\[/),
      tokenizer(src){const m=/^(?:\$\$([\s\S]+?)\$\$|\\\[([\s\S]+?)\\\])(?:\n|$)/.exec(src);if(m)return {type:'displayMath',raw:m[0],text:m[1]??m[2]};},
      renderer:token=>math(token.text,true)},
    {name:'inlineMath',level:'inline',start:src=>src.search(/\$|\\\(/),
      tokenizer(src){const m=/^(?:\$([^$\n]+?)\$(?!\$)|\\\(([\s\S]+?)\\\))/.exec(src);if(m)return {type:'inlineMath',raw:m[0],text:m[1]??m[2]};},
      renderer:token=>math(token.text,false)}
  ]});
  function fragment(value,{inline=false}={}) {
    const source = String(value??'').replace(/^\uFEFF/,'');
    const html = inline ? marked.parseInline(source) : marked.parse(source);
    const result = DOMPurify.sanitize(html,{RETURN_DOM_FRAGMENT:true,FORBID_TAGS:['img','iframe','object','embed','form','style','input','button','textarea','select'],FORBID_ATTR:['id','name'],ALLOW_DATA_ATTR:false});
    for(const a of result.querySelectorAll('a')) {
      const href=a.getAttribute('href')||'';
      try {
        const u=new URL(href,location.href);
        if(!['https:','http:'].includes(u.protocol)||u.username||u.password||href.startsWith('//')) throw Error('unsupported link');
        a.rel='noopener noreferrer';if(u.origin!==location.origin)a.target='_blank';
      } catch(_) {a.removeAttribute('href');}
    }

    if(result.childElementCount===1&&result.firstElementChild.tagName==='P') {
      const p=result.firstElementChild;
      const flat=document.createDocumentFragment();flat.append(...p.childNodes);return flat;
    }
    return result;
  }
  function render(root,value,options) {
    const signature=String(value??'');
    if(root.dataset.markdownSource===signature)return;
    root.dataset.markdownSource=signature;
    root.classList.add('markdown');root.replaceChildren(fragment(signature,options));
  }
  window.RealignMarkdown=Object.freeze({fragment,render});
})();
