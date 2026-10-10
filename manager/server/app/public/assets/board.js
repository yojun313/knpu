(function () {
'use strict';
const $ = id => document.getElementById(id);
const escape = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const config = {
 version: {title:'MANAGER 패치노트', description:'매니저 업데이트와 변경 사항을 확인하세요.', create:'＋ MANAGER 패치노트 추가'},
 bug: {title:'버그리포트', description:'문제를 알려주시고 관리자 답변을 확인하세요.', create:'＋ 버그리포트 작성'},
 post: {title:'자유게시판', description:'연구 이야기와 소식을 함께 나누세요.', create:'＋ 글 작성'}
};
let user, tab='post', lists={version:[],bug:[],post:[]}, page=1, selected=null, generation=0, modalGeneration=0, lastFocus=null;
const dialog=$('board-dialog');
const uid = () => crypto.randomUUID();
const canEdit = doc => user && (user.role==='admin' || doc.writerUid===user.uid);
const key = doc => tab==='version' ? doc.versionName : doc.uid;
const path = doc => '/api/board/'+tab+'/'+encodeURIComponent(key(doc));
function toast(message) { $('board-toast').textContent=message; $('board-toast').hidden=false; clearTimeout(toast.timer); toast.timer=setTimeout(()=>$('board-toast').hidden=true,4000); }
async function api(url,method='GET',data) {
 const res=await fetch(url,{method,credentials:'include',cache:'no-store',headers:data?{'Content-Type':'application/json'}:{},body:data?JSON.stringify(data):undefined});
 let payload={};try {payload=await res.json();}catch(e){}
 if(!res.ok){if(res.status===401)throw new Error('로그인이 만료되었습니다. 새로고침 후 다시 로그인해주세요.');let message=payload.detail || payload.message;if(Array.isArray(message))message=message.map(e=>e.msg).join(' / ');throw new Error(message || '요청을 처리하지 못했습니다. 다시 시도해주세요.');}
 return Object.prototype.hasOwnProperty.call(payload,'data')?payload.data:payload;
}
function date(value) { if(!value)return ''; const raw=String(value);if(raw.includes('T')){const d=new Date(raw);if(!isNaN(d))return d.toLocaleString('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'});}return raw; }
function updateLocation(doc) {const url=new URL(location.href);url.searchParams.set('tab',tab);if(doc)url.searchParams.set('uid',key(doc));else url.searchParams.delete('uid');history.replaceState(null,'',url);}
function showDialog(title) { $('board-dialog-title').textContent=title;if(!dialog.open){lastFocus=document.activeElement;dialog.showModal();} }
function closeDialog() {selected=null;modalGeneration++;updateLocation(null);dialog.close();}
dialog.addEventListener('close',()=>{if(dialog.open)return;selected=null;modalGeneration++;updateLocation(null);if(lastFocus&&lastFocus.isConnected)lastFocus.focus();});
$('board-close').onclick=closeDialog;
dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)closeDialog();}});
function selectTab(next) {
 if(!config[next])next='post';if(dialog.open)closeDialog();tab=next;page=1;
 document.querySelectorAll('[data-tab]').forEach(b=>{const active=b.dataset.tab===tab;b.classList.toggle('active',active);b.setAttribute('aria-current',active?'page':'false');});
 $('board-title').textContent=config[tab].title;$('board-description').textContent=config[tab].description;$('board-create').textContent=config[tab].create;$('board-create').hidden=tab==='version'&&user.role!=='admin';
 $('board-filter').innerHTML=tab==='post'?'<option value="all">전체 게시글</option><option value="mine">내가 작성한 글</option><option value="unread">읽지 않은 글</option>':tab==='bug'?'<option value="all">전체 리포트</option><option value="mine">내가 작성한 리포트</option><option value="waiting">답변 대기</option><option value="answered">답변 있음</option>':'<option value="all">전체 MANAGER 패치노트</option>';
 updateLocation(null);renderList();
}
function filtered() {
 const search=$('board-search').value.trim().toLocaleLowerCase(), filter=$('board-filter').value;
 return lists[tab].filter(d=>{
  if(search&&!([d.title,d.text,d.bugTitle,d.bugText,d.versionName,d.changeLog,d.features,d.details,d.writerName,d.publisher].join(' ').toLocaleLowerCase().includes(search)))return false;
  if(filter==='mine'&&d.writerUid!==user.uid)return false;
  if(filter==='unread'&&(d.readByMe||d.writerUid===user.uid))return false;
  if(filter==='waiting'&&(d.replyCount||0)>0)return false;
  if(filter==='answered'&&!(d.replyCount>0))return false;
  return true;
 });
}
function renderList() {
 document.querySelectorAll('[data-count]').forEach(e=>e.textContent=lists[e.dataset.count].length);
 const docs=filtered(), pages=Math.max(1,Math.ceil(docs.length/20));page=Math.min(page,pages);
 $('board-total').textContent=docs.length+'개';$('board-page').textContent=page+' / '+pages;$('board-prev').disabled=page<=1;$('board-next').disabled=page>=pages;
 $('board-list').innerHTML=docs.length?docs.slice((page-1)*20,page*20).map(d=>{
  const title=tab==='version'?'Version '+d.versionName:tab==='bug'?d.bugTitle:d.title;
  const tag=tab==='bug'?(d.replyCount?'답변 '+d.replyCount:'답변 대기'):tab==='version'?(user.role==='admin'?(d.fullUpdate?'전체 업데이트':'업데이트'):''):(!d.readByMe&&d.writerUid!==user.uid?'NEW':'');
  const meta=tab==='version'?[d.releaseDate,d.publisher]:tab==='bug'?[d.writerName,'v'+(d.versionName||'—'),date(d.datetime)]:[d.writerName,date(d.datetime),'조회 '+(d.viewCnt||0),'댓글 '+(d.commentCount||0)];
  return '<button type="button" class="board-row" data-open="'+escape(key(d))+'"><span class="board-row-main"><span class="board-row-title"><strong>'+escape(title)+'</strong>'+(tag?'<span class="board-tag">'+escape(tag)+'</span>':'')+'</span><span class="board-row-meta">'+meta.filter(Boolean).map(v=>'<span>'+escape(v)+'</span>').join('')+'</span></span><span class="board-chevron" aria-hidden="true">›</span></button>';
 }).join(''):'<div class="board-empty">'+($('board-search').value?'검색 조건에 맞는 글이 없습니다.':'게시글이 없습니다. 첫 글을 작성해보세요.')+'</div>';
}
async function refresh(silent=false) {
 const n=++generation;if(!silent){$('board-feedback').textContent='불러오는 중…';$('board-feedback').classList.remove('error');}
 try {const results=await Promise.all(['version','bug','post'].map(t=>api('/api/board/'+t)));if(n!==generation)return;['version','bug','post'].forEach((t,i)=>lists[t]=results[i]);renderList();$('board-feedback').textContent='';}
 catch(e){if(n===generation){$('board-feedback').classList.add('error');$('board-feedback').textContent=e.message;}}
}
async function openDetail(id) {
 const t=tab,n=++modalGeneration;
 showDialog(config[tab].title);$('board-dialog-body').innerHTML='<div class="board-empty">불러오는 중…</div>';
 try {const doc=await api('/api/board/'+t+'/'+encodeURIComponent(id));if(n!==modalGeneration||!dialog.open||t!==tab)return;selected=doc;updateLocation(doc);renderDetail(doc);if(tab==='post'){lists.post=lists.post.map(p=>p.uid===id?{...p,readByMe:true,viewCnt:(doc.viewCnt||[]).length}:p);renderList();window.dispatchEvent(new Event('knpu-board-read'));}}
 catch(e){if(n===modalGeneration&&dialog.open)$('board-dialog-body').innerHTML='<div class="board-form-error" role="alert">'+escape(e.message)+'</div>';}
}
function section(title,text) {return '<h3 class="board-section-title">'+escape(title)+'</h3><div class="board-prose">'+escape(text||'—')+'</div>';}
function renderDetail(doc) {
 const version=tab==='version', bug=tab==='bug', title=version?'Version '+doc.versionName:bug?doc.bugTitle:doc.title;
 $('board-dialog-title').textContent=config[tab].title;
 let html='<div class="board-detail-meta"><span>'+escape(version?doc.publisher:doc.writerName)+'</span><span>'+escape(date(version?doc.releaseDate:doc.datetime))+'</span>'+(bug?'<span>Version '+escape(doc.versionName)+'</span>':'')+'</div><h2 class="board-detail-title">'+escape(title)+'</h2>';
 if(version?user.role==='admin':canEdit(doc))html+='<div class="board-actions"><button type="button" class="board-btn" data-action="edit">수정</button><button type="button" class="board-btn danger" data-action="delete">삭제</button></div>';
 if(version)html+=section('변경 사항',doc.changeLog)+section('주요 기능',doc.features)+section('상세 내용',doc.details)+(user.role==='admin'?'<span class="board-tag">'+(doc.fullUpdate?'전체 업데이트':'업데이트')+'</span>':'');
 else if(bug){html+='<div class="board-prose">'+escape(doc.bugText)+'</div>';if(doc.programLog)html+='<details><summary>프로그램 로그</summary><pre class="board-log">'+escape(doc.programLog)+'</pre></details>';}
 else html+='<div class="board-prose">'+escape(doc.text)+'</div>';
 if(!version){const items=bug?(doc.replies||[]):(doc.comments||[]);html+='<section class="board-discussion"><h3 class="board-section-title">'+(bug?'관리자 답변':'댓글')+' · '+items.length+'</h3>';
 html+=items.map(c=>'<article class="board-comment"><div class="board-comment-meta"><strong>'+escape(c.writerName)+'</strong>'+(bug?'<span class="board-tag">관리자</span>':'')+'<span>'+escape(date(c.datetime))+'</span>'+(c.editedAt?'<span>수정됨</span>':'')+(!bug&&canEdit(c)?'<span class="board-comment-actions"><button type="button" data-comment-edit="'+escape(c.uid)+'">수정</button><button type="button" data-comment-delete="'+escape(c.uid)+'">삭제</button></span>':'')+'</div><div class="board-comment-text">'+escape(c.text)+'</div>'+(bug&&c.mailStatus?'<small>'+escape({pending:'메일 알림 대기',sending:'메일 전송 중',sent:'메일 알림 전송됨',retry:'메일 알림 재시도 대기',skipped:'작성자 이메일 없음'}[c.mailStatus]||'')+'</small>':'')+'</article>').join('');
 if(!items.length)html+='<p class="board-detail-meta">'+(bug?'아직 등록된 관리자 답변이 없습니다.':'첫 댓글을 남겨보세요.')+'</p>';
 if(!bug||user.role==='admin')html+='<form id="board-compose" class="board-editor board-compose"><label>'+(bug?'관리자 답변':'댓글 작성')+'<textarea name="text" maxlength="'+(bug?'20000':'10000')+'" required placeholder="'+(bug?'답변을 등록하면 작성자에게 이메일 알림이 발송됩니다.':'댓글을 입력하세요.')+'"></textarea></label><div class="board-form-error" role="alert"></div><div class="board-form-actions"><button class="board-btn primary" type="submit">'+(bug?'답변 등록':'댓글 등록')+'</button></div></form>';
 html+='</section>';}
 $('board-dialog-body').innerHTML=html;
 const compose=$('board-compose');if(compose){const requestId=uid();compose.onsubmit=async e=>{e.preventDefault();const text=compose.elements.text.value.trim();if(!text)return;await formRequest(compose,()=>api(path(doc)+(bug?'/replies':'/comments'),'POST',{text,requestId}),async()=>{toast(bug?'답변이 등록되었습니다. 이메일 알림이 예약되었습니다.':'댓글이 등록되었습니다.');await openDetail(key(doc));refresh(true);});};}
}
function editorField(name,label,value='',multiline=false) {return '<label>'+escape(label)+(multiline?'<textarea name="'+name+'" rows="'+(name==='text'||name==='bugText'?10:4)+'" '+(name==='text'||name==='bugText'?'required':'')+'>'+escape(value)+'</textarea>':'<input name="'+name+'" value="'+escape(value)+'" required maxlength="'+(name==='versionName'?60:300)+'">')+'</label>';}
function openEditor(doc=null) {
 modalGeneration++;const version=tab==='version',bug=tab==='bug';showDialog(config[tab].title+' '+(doc?'수정':'작성'));
 let html='<form id="board-editor" class="board-editor">';
 if(version)html+=editorField('versionName','버전',doc?.versionName||'')+editorField('changeLog','변경 사항',doc?.changeLog||'',true)+editorField('features','주요 기능',doc?.features||'',true)+editorField('details','상세 내용',doc?.details||'',true)+'<label class="board-checkbox"><input name="fullUpdate" type="checkbox" '+(doc?.fullUpdate?'checked':'')+'>전체 업데이트</label><p class="board-detail-meta">새 MANAGER 패치노트를 등록하면 업데이트 공지가 발송됩니다.</p>';
 else if(bug)html+=editorField('versionName','발생 버전',doc?.versionName||lists.version[0]?.versionName||'')+editorField('bugTitle','제목',doc?.bugTitle||'')+editorField('bugText','문제 내용과 재현 방법',doc?.bugText||'',true);
 else html+=editorField('title','제목',doc?.title||'')+editorField('text','내용',doc?.text||'',true)+(doc?'':'<label class="board-checkbox"><input type="checkbox" name="broadcastNotify">전체 공지 알림 보내기</label>');
 html+='<div class="board-form-error" role="alert"></div><div class="board-form-actions"><button type="button" class="board-btn" data-action="cancel-edit">취소</button><button type="submit" class="board-btn primary">저장</button></div></form>';
 $('board-dialog-body').innerHTML=html;
 const form=$('board-editor');form.onsubmit=async e=>{e.preventDefault();const payload=Object.fromEntries(new FormData(form));Object.keys(payload).forEach(k=>payload[k]=payload[k].trim());if(version)payload.fullUpdate=form.elements.fullUpdate.checked;else if(bug){payload.writerUid=user.uid;payload.programLog='';}else{payload.writerUid=user.uid;payload.broadcastNotify=!!form.elements.broadcastNotify?.checked;}
 await formRequest(form,()=>api(doc?path(doc):'/api/board/'+tab+'/add',doc?'PUT':'POST',payload),async(result)=>{toast('저장되었습니다.');await refresh(true);await openDetail(version?payload.versionName:(result?.uid||doc?.uid));});};
}
async function formRequest(form,operation,success) {const button=form.querySelector('[type="submit"]'),error=form.querySelector('.board-form-error');button.disabled=true;error.textContent='';try{const result=await operation();await success(result);}catch(e){error.textContent=e.message;}finally{button.disabled=false;}}
$('board-dialog-body').addEventListener('click',async e=>{
 const btn=e.target.closest('button');if(!btn)return;
 const action=btn.dataset.action;
 if(action==='edit')return openEditor(selected);
 if(action==='cancel-edit')return selected?renderDetail(selected):closeDialog();
 if(action==='delete'){if(!confirm('이 게시글을 삭제하시겠습니까?'))return;btn.disabled=true;try{await api(path(selected),'DELETE');closeDialog();toast('삭제되었습니다.');refresh();}catch(error){toast(error.message);btn.disabled=false;}return;}
 if(btn.dataset.commentDelete){if(!confirm('이 댓글을 삭제하시겠습니까?'))return;btn.disabled=true;try{await api(path(selected)+'/comments/'+encodeURIComponent(btn.dataset.commentDelete),'DELETE');await openDetail(key(selected));refresh(true);}catch(error){toast(error.message);btn.disabled=false;}return;}
 if(btn.dataset.commentEdit){const comment=selected.comments.find(c=>c.uid===btn.dataset.commentEdit),article=btn.closest('.board-comment');article.innerHTML='<form class="board-editor"><label>댓글 수정<textarea name="text" maxlength="10000" required>'+escape(comment.text)+'</textarea></label><div class="board-form-error" role="alert"></div><div class="board-form-actions"><button type="button" class="board-btn" data-action="cancel-edit">취소</button><button type="submit" class="board-btn primary">저장</button></div></form>';const form=article.querySelector('form');form.onsubmit=async event=>{event.preventDefault();const text=form.elements.text.value.trim();if(!text)return;await formRequest(form,()=>api(path(selected)+'/comments/'+encodeURIComponent(comment.uid),'PUT',{text}),()=>openDetail(key(selected)));};}
});
$('board-list').addEventListener('click',e=>{const b=e.target.closest('[data-open]');if(b)openDetail(b.dataset.open);});
document.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>selectTab(b.dataset.tab));
$('board-search').oninput=()=>{page=1;renderList();};$('board-filter').onchange=()=>{page=1;renderList();};$('board-prev').onclick=()=>{page--;renderList();};$('board-next').onclick=()=>{page++;renderList();};$('board-refresh').onclick=()=>refresh();$('board-create').onclick=()=>{selected=null;openEditor();};
$('board-logout').onclick=async()=>{try{await fetch(KNPU.logoutUrl(),{method:'POST',credentials:'include'});location.href=KNPU.loginUrl();}catch(e){toast('로그아웃하지 못했습니다. 다시 시도해주세요.');}};
(async()=>{try{user=await api('/api/board/me');$('board-user-name').textContent=user.name||'사용자';const params=new URLSearchParams(location.search),initialTab=params.get('tab'),initialUid=params.get('uid');selectTab(initialTab||'post');await refresh();if(initialUid)await openDetail(initialUid);setInterval(()=>{if(!document.hidden)refresh(true);},30000);}catch(e){$('board-feedback').textContent=e.message;$('board-feedback').classList.add('error');$('board-create').disabled=true;}})();
})();
