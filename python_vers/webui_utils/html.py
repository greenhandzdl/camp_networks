# -*- coding: utf-8 -*-
"""WebUI HTML 模板"""

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<meta name="theme-color" content="#0f0f13">
<title>Dr.COM 认证</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0f0f13;--card:#1a1a24;--border:#2a2a3a;--primary:#6c5ce7;--primary-light:#a29bfe;
--success:#00b894;--danger:#e17055;--warn:#fdcb6e;--text:#e0e0e0;--text2:#8888a0;--radius:14px}
html,body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,
"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;font-size:15px;line-height:1.5;
min-height:100vh;-webkit-tap-highlight-color:transparent}
.container{max-width:480px;margin:0 auto;padding:16px 16px 92px}
.header{text-align:center;padding:20px 0 12px}
.header h1{font-size:22px;font-weight:700;background:linear-gradient(135deg,var(--primary-light),var(--primary));
-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.header .ver{font-size:12px;color:var(--text2);margin-top:4px}
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
padding:18px;margin-bottom:14px}
.card-title{font-size:14px;font-weight:600;color:var(--text2);text-transform:uppercase;
letter-spacing:.5px;margin-bottom:14px;display:flex;align-items:center;gap:8px}
.card-title .icon{font-size:18px}
.form-group{margin-bottom:14px}
.form-group label{display:block;font-size:13px;color:var(--text2);margin-bottom:6px;font-weight:500}
.form-group input[type=text],.form-group input[type=password],.form-group input[type=number]{
width:100%;padding:12px 14px;background:var(--bg);border:1px solid var(--border);border-radius:10px;
color:var(--text);font-size:15px;outline:none;transition:border-color .2s}
.form-group input:focus{border-color:var(--primary)}
.toggle-row{display:flex;align-items:center;justify-content:space-between;padding:8px 0}
.toggle-row span{font-size:14px;color:var(--text)}
.toggle{position:relative;width:48px;height:28px;cursor:pointer}
.toggle input{display:none}
.toggle .slider{position:absolute;inset:0;background:var(--border);border-radius:14px;transition:.3s}
.toggle .slider:before{content:"";position:absolute;width:22px;height:22px;left:3px;bottom:3px;
background:#fff;border-radius:50%;transition:.3s}
.toggle input:checked+.slider{background:var(--primary)}
.toggle input:checked+.slider:before{transform:translateX(20px)}
.btn{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;padding:14px;
border:none;border-radius:12px;font-size:15px;font-weight:600;cursor:pointer;transition:all .2s}
.btn:active{transform:scale(.97)}
.btn-primary{background:linear-gradient(135deg,var(--primary),var(--primary-light));color:#fff}
.btn-success{background:linear-gradient(135deg,#00b894,#55efc4);color:#1a1a24}
.btn-outline{background:transparent;border:1px solid var(--border);color:var(--text)}
.btn-warn{background:linear-gradient(135deg,#e17055,#fdcb6e);color:#1a1a24}
.btn:disabled{opacity:.5;pointer-events:none}
.btn+.btn{margin-top:10px}
.status-bar{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:10px;
font-size:13px;font-weight:500;margin-bottom:14px}
.status-bar.ok{background:rgba(0,184,148,.12);color:var(--success)}
.status-bar.err{background:rgba(225,112,85,.12);color:var(--danger)}
.status-bar.info{background:rgba(108,92,231,.12);color:var(--primary-light)}
.status-bar.warn{background:rgba(253,203,110,.12);color:var(--warn)}
.output-box{background:var(--bg);border:1px solid var(--border);border-radius:10px;
padding:12px;font-family:"SF Mono",Menlo,Consolas,monospace;font-size:12px;
line-height:1.6;max-height:300px;overflow-y:auto;white-space:pre-wrap;word-break:break-all;
color:var(--text);display:none}
.output-box.show{display:block}
.update-info{font-size:13px;color:var(--text2);line-height:1.6}
.update-info .tag{display:inline-block;background:var(--primary);color:#fff;padding:2px 8px;
border-radius:6px;font-size:12px;font-weight:600}
.update-info a{text-decoration:none}
.spinner{display:inline-block;width:18px;height:18px;border:2px solid transparent;
border-top-color:currentColor;border-radius:50%;animation:spin .6s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
.hidden{display:none}
.toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%) translateY(80px);
background:var(--card);border:1px solid var(--border);padding:12px 24px;border-radius:12px;
font-size:14px;font-weight:500;z-index:999;transition:transform .3s;pointer-events:none}
.toast.show{transform:translateX(-50%) translateY(0)}
.hint{font-size:11px;color:var(--text2);margin-top:8px}
.page{display:none}
.page.show{display:block;animation:fadeIn .25s ease}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}
.nav{position:fixed;bottom:0;left:0;right:0;display:flex;background:rgba(26,26,36,.92);
backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);border-top:1px solid var(--border);
padding:6px 4px calc(6px + env(safe-area-inset-bottom));z-index:100}
.nav-item{flex:1;text-align:center;font-size:11px;color:var(--text2);padding:4px 0;cursor:pointer;
border-radius:10px;transition:color .2s}
.nav-item .nicon{font-size:20px;display:block;margin-bottom:1px}
.nav-item.active{color:var(--primary-light)}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>Dr.COM WLAN</h1>
    <div class="ver" id="modVer"></div>
  </div>

  <!-- 状态页 -->
  <div id="page-status" class="page show">
    <div class="card">
      <div class="card-title"><span class="icon">&#128225;</span> 网络状态</div>
      <div class="update-info" id="netInfo">加载中...</div>
      <button class="btn btn-outline" style="margin-top:12px" onclick="loadNet(true)">刷新</button>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#9200;</span> 自动认证状态</div>
      <div class="update-info" id="autoStatus">加载中...</div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#128230;</span> 模块更新</div>
      <button class="btn btn-outline" id="btnCheck" onclick="checkUpdate()">检查更新</button>
      <div class="update-info hidden" id="updateInfo"></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#128196;</span> 运行日志</div>
      <button class="btn btn-outline" onclick="viewLog()">查看日志</button>
      <div class="output-box" id="logOutput"></div>
    </div>
  </div>

  <!-- 认证页 -->
  <div id="page-auth" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#128273;</span> 认证配置</div>
      <div class="form-group"><label>账号</label>
        <input type="text" id="username" placeholder="学号/工号" autocomplete="off"></div>
      <div class="form-group"><label>密码</label>
        <input type="password" id="password" placeholder="认证密码"></div>
      <div class="form-group"><label>运营商后缀</label>
        <input type="text" id="suffix" placeholder="@cmcc"></div>
      <div class="form-group"><label>认证服务器 IP <span style="font-size:11px;color:var(--text2)">(AUTH_SERVER)</span></label>
        <input type="text" id="authServer" placeholder="__AUTH_SERVER__"></div>
      <div class="form-group"><label>网关重定向地址 <span style="font-size:11px;color:var(--text2)">(REDIRECT_SERVER)</span></label>
        <input type="text" id="redirectServer" placeholder="__REDIRECT_SERVER__"></div>
      <div class="toggle-row"><span>调试模式</span>
        <label class="toggle"><input type="checkbox" id="debug"><span class="slider"></span></label></div>
      <div style="margin-top:16px">
        <button class="btn btn-primary" id="btnSave" onclick="saveConfig()">保存配置</button></div>
    </div>
    <div class="card">
      <div class="card-title"><span class="icon">&#9889;</span> 认证操作</div>
      <div id="authStatus"></div>
      <button class="btn btn-success" id="btnRun" onclick="runAuth()">
        <span id="btnRunText">&#9654; 立即认证</span></button>
      <div class="output-box" id="authOutput"></div>
    </div>
  </div>

  <!-- 自动页 -->
  <div id="page-auto" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#9200;</span> 自动认证</div>
      <div class="toggle-row"><span>启用自动认证</span>
        <label class="toggle"><input type="checkbox" id="autoRun"><span class="slider"></span></label></div>
      <div class="form-group"><label>目标 WiFi 名称（ESSID）</label>
        <div style="display:flex;gap:8px">
          <input type="text" id="targetEssid" placeholder="校园网 WiFi 名称" style="flex:1">
          <button class="btn btn-outline" style="width:auto;padding:12px 14px" onclick="fillEssid()">获取当前</button>
        </div></div>
      <div class="form-group"><label>运行间隔（分钟）</label>
        <input type="number" id="autoInterval" min="1" inputmode="numeric" placeholder="__INTERVAL__"></div>
      <div class="form-group"><label>接入后首次延迟（秒）</label>
        <input type="number" id="autoDelay" min="0" inputmode="numeric" placeholder="__DELAY__"></div>
      <button class="btn btn-primary" id="btnSaveAuto" onclick="saveAuto()">保存自动设置</button>
      <div class="hint">需已配置账号密码。接入目标 WiFi 立即触发认证并按间隔重跑，断开 WiFi 自动停止。</div>
    </div>
  </div>

  <!-- 设置页 -->
  <div id="page-settings" class="page">
    <div class="card">
      <div class="card-title"><span class="icon">&#128268;</span> 服务设置</div>
      <div class="form-group"><label>WebUI 端口</label>
        <input type="number" id="port" placeholder="__PORT__" min="1" max="65535" inputmode="numeric"></div>
      <div class="form-group"><label>日志文件路径</label>
        <input type="text" id="logFile" placeholder="__LOGFILE__"></div>
      <div class="form-group"><label>更新包下载目录</label>
        <input type="text" id="downloadDir" placeholder="__DOWNLOAD__"></div>
      <div class="form-group"><label>更新渠道</label>
        <label style="display:flex;align-items:flex-start;gap:8px;padding:10px 12px;margin-bottom:6px;background:var(--bg);border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:13px">
          <input type="radio" name="updateCh" value="GitHub" style="accent-color:var(--primary);margin-top:2px">
          <span><b>GitHub</b><br><span style="color:var(--text2);font-size:11px">实时更新最快，但国内连接可能不稳定</span></span>
        </label>
        <label style="display:flex;align-items:flex-start;gap:8px;padding:10px 12px;background:var(--bg);border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:13px">
          <input type="radio" name="updateCh" value="CDN" style="accent-color:var(--primary);margin-top:2px">
          <span><b>CDN (jsDelivr)</b><br><span style="color:var(--text2);font-size:11px">国内访问快速稳定，但缓存可能导致更新延迟数小时</span></span>
        </label>
      </div>
      <button class="btn btn-warn" id="btnService" onclick="saveService()">保存服务设置</button>
      <div class="hint">修改端口后服务会关闭，通过 Magisk Manager 重启即可；日志路径下次启动生效</div>
    </div>
  </div>
</div>

<nav class="nav">
  <div class="nav-item active" data-tab="status" onclick="showTab('status')"><span class="nicon">&#128225;</span>状态</div>
  <div class="nav-item" data-tab="auth" onclick="showTab('auth')"><span class="nicon">&#128273;</span>认证</div>
  <div class="nav-item" data-tab="auto" onclick="showTab('auto')"><span class="nicon">&#9200;</span>自动</div>
  <div class="nav-item" data-tab="settings" onclick="showTab('settings')"><span class="nicon">&#9881;</span>设置</div>
</nav>
<div class="toast" id="toast"></div>

<script>
const $=id=>document.getElementById(id),DFT_SUFFIX="__SUFFIX__",DFT_PORT="__PORT__",DFT_LOG="__LOGFILE__",DFT_DL="__DOWNLOAD__",DFT_INT="__INTERVAL__",DFT_DELAY="__DELAY__",DFT_AUTH="__AUTH_SERVER__",DFT_REDIR="__REDIRECT_SERVER__";
let _runBusy=false;
document.addEventListener('DOMContentLoaded',()=>{
  fetch('/api/config').then(r=>r.json()).then(c=>{
    $('username').value=c.username||'';$('password').value=c.password||'';
    $('suffix').value=c.suffix||DFT_SUFFIX;$('debug').checked=c.debug==='true';
    $('authServer').value=c.auth_server||DFT_AUTH;
    $('redirectServer').value=c.redirect_server||DFT_REDIR;
    $('port').value=c.port||DFT_PORT;$('logFile').value=c.log_file||DFT_LOG;
    $('downloadDir').value=c.download_dir||DFT_DL;
    $('autoRun').checked=c.auto_run==='true';$('targetEssid').value=c.target_essid||'';
    $('autoInterval').value=c.auto_interval||DFT_INT;
    $('autoDelay').value=c.auto_delay!==undefined?c.auto_delay:DFT_DELAY;
    const ch=document.querySelector('input[name="updateCh"][value="'+(c.update_channel||'GitHub')+'"]');
    if(ch)ch.checked=true;
  });
  fetch('/api/prop').then(r=>r.json()).then(p=>{
    $('modVer').textContent=(p.name||'')+' '+(p.version||'');
  });
  loadNet(false);
  pollRunStatus();
  setInterval(pollRunStatus,2000);
});
function toast(m){const t=$('toast');t.textContent=m;t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'),2000)}
function btnLoading(b,t){b.disabled=true;b.innerHTML='<span class="spinner"></span> '+t}
function btnReset(b,t){b.disabled=false;b.textContent=t}
function showTab(t){
  document.querySelectorAll('.page').forEach(p=>p.classList.toggle('show',p.id==='page-'+t));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.tab===t));
}

function saveConfig(){
  const b=$('btnSave');btnLoading(b,'保存中...');
  fetch('/api/save',{method:'POST',body:new URLSearchParams({
    username:$('username').value,password:$('password').value,
    suffix:$('suffix').value,debug:$('debug').checked?'true':'false',
    auth_server:$('authServer').value,redirect_server:$('redirectServer').value})})
  .then(r=>r.json()).then(d=>toast(d.ok?'配置已保存':'保存失败: '+d.error))
  .catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存配置'));
}

function runAuth(){
  if(_runBusy){stopRun();return}
  const b=$('btnRun'),t=$('btnRunText'),o=$('authOutput'),s=$('authStatus');
  btnLoading(b,'认证中...');t.innerHTML='<span class="spinner"></span> 认证中...';
  o.className='output-box show';o.textContent='正在执行认证脚本...\n';s.innerHTML='';
  fetch('/api/run').then(r=>r.json()).then(d=>{
    if(d.error==='busy'){toast('已有任务运行中，请先停止');return}
    o.textContent=d.output||'(无输出)';
    s.innerHTML=d.ok?'<div class="status-bar ok">&#10003; 认证完成</div>'
      :'<div class="status-bar err">&#10007; 执行异常</div>';
  }).catch(e=>{o.textContent='请求失败: '+e;
    s.innerHTML='<div class="status-bar err">&#10007; 请求失败</div>';
  }).finally(()=>{
    if(!_runBusy){btnReset(b,'▶ 立即认证');b.classList.remove('btn-warn');b.classList.add('btn-success');}
    pollRunStatus();
  });
}

function stopRun(){
  fetch('/api/stop_run',{method:'POST'}).then(r=>r.json()).then(d=>{
    if(d.ok)toast('已终止认证任务');else toast(d.error||'停止失败');
    setTimeout(pollRunStatus,300);
  }).catch(()=>toast('请求失败'));
}

function pollRunStatus(){
  fetch('/api/run_status').then(r=>r.json()).then(d=>{
    _runBusy=d.running;
    // 更新认证按钮状态
    const b=$('btnRun'),t=$('btnRunText');
    if(d.running){
      b.disabled=false;
      b.classList.remove('btn-success');b.classList.add('btn-warn');
      const srcTxt=d.source==='auto'?'(自动)':'(手动)';
      t.innerHTML='■ 停止任务 '+srcTxt;
    }else{
      btnReset(b,'▶ 立即认证');
      b.classList.remove('btn-warn');b.classList.add('btn-success');
    }
    // 更新自动认证状态卡片
    const el=$('autoStatus');
    let h='';
    if(!d.auto_enabled){
      h='<div style="color:var(--text2)">&#128683; 自动认证未启用</div>';
    }else if(d.running&&d.source==='auto'){
      h='<div>&#9889; 正在执行自动认证...</div>';
    }else if(d.running&&d.source==='manual'){
      h='<div>&#9881; 手动认证任务运行中</div>';
    }else if(d.auto_connected&&d.has_schedule){
      const sec=d.next_run_in;
      h=sec>0
        ?'<div>&#9200; 已连接目标 WiFi，<b>'+sec+'</b> 秒后自动执行</div>'
        :'<div>&#9889; 已连接目标 WiFi，即将执行认证...</div>';
    }else if(d.auto_connected){
      h='<div>&#9889; 已连接目标 WiFi，即将执行认证...</div>';
    }else if(d.waiting_first){
      h='<div>&#9200; 已连接目标 WiFi，等待首次执行...</div>';
    }else{
      h='<div style="color:var(--text2)">&#128683; 未连接目标 WiFi，等待接入后自动触发</div>';
    }
    h+='<div style="margin-top:4px;font-size:11px;color:var(--text2)">未连接目标 WiFi 时不会触发自动认证</div>';
    el.innerHTML=h;
  }).catch(()=>{});
}

function saveService(){
  const v=$('port').value.trim(),n=parseInt(v);
  if(!n||n<1||n>65535)return toast('请输入 1-65535 的有效端口号');
  const b=$('btnService');btnLoading(b,'保存中...');
  fetch('/api/save_service',{method:'POST',body:new URLSearchParams({port:v,log_file:$('logFile').value,download_dir:$('downloadDir').value,update_channel:(document.querySelector('input[name="updateCh"]:checked')||{}).value||'GitHub'})})
  .then(r=>r.json()).then(d=>{
    if(!d.ok){toast('保存失败: '+(d.error||''));return}
    if(d.port_changed){
      document.body.innerHTML='<div style="text-align:center;padding:60px 20px;color:var(--text)">'
        +'<div style="font-size:48px;margin-bottom:16px">&#9889;</div>'
        +'<div style="font-size:18px;font-weight:600">服务已停止</div>'
        +'<div style="font-size:13px;color:var(--text2);margin-top:8px">新端口: '+n
        +'<br>请通过 Magisk Manager 重新启动 WebUI</div></div>';
    }else toast('服务设置已保存');
  }).catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存服务设置'));
}

function viewLog(){
  const o=$('logOutput');o.className='output-box show';o.textContent='加载中...';
  fetch('/api/log').then(r=>r.json()).then(d=>{
    o.textContent=(d.content||'(日志为空)');
    o.scrollTop=o.scrollHeight;
  }).catch(()=>{o.textContent='日志加载失败'});
}

function loadNet(manual){
  const el=$('netInfo');
  if(manual)el.innerHTML='加载中...';
  fetch('/api/network').then(r=>r.json()).then(d=>{
    el.innerHTML='<div>WiFi: '+(d.ssid||'未连接')+'</div>'
      +'<div>BSSID: '+(d.bssid||'-')+'</div>'
      +'<div>IPv4: '+((d.ipv4&&d.ipv4.length)?d.ipv4.join(', '):'-')+'</div>'
      +'<div>IPv6: '+((d.ipv6&&d.ipv6.length)?d.ipv6.join(', '):'-')+'</div>';
  }).catch(()=>{el.innerHTML='<div class="status-bar err">获取网络信息失败</div>'});
}

function fillEssid(){
  fetch('/api/network').then(r=>r.json()).then(d=>{
    if(d.ssid){$('targetEssid').value=d.ssid;toast('已填充当前 WiFi 名称')}
    else toast('未连接 WiFi 或无法获取 WiFi 名称');
  }).catch(()=>toast('获取失败'));
}

function saveAuto(){
  const b=$('btnSaveAuto');btnLoading(b,'保存中...');
  fetch('/api/save_auto',{method:'POST',body:new URLSearchParams({
    auto_run:$('autoRun').checked?'true':'false',
    target_essid:$('targetEssid').value,
    auto_interval:$('autoInterval').value,
    auto_delay:$('autoDelay').value})})
  .then(r=>r.json()).then(d=>toast(d.ok?'自动设置已保存':'保存失败: '+(d.error||'')))
  .catch(()=>toast('网络错误')).finally(()=>btnReset(b,'保存自动设置'));
}

function checkUpdate(){
  const b=$('btnCheck'),info=$('updateInfo');
  btnLoading(b,'检查中...');info.className='update-info hidden';
  fetch('/api/check_update').then(r=>r.json()).then(d=>{
    const cur=d.current_version||'unknown',ch=d.channel||'GitHub';
    if(d.error){
      info.innerHTML='<div style="margin-bottom:8px;font-size:12px;color:var(--text2)">当前版本: '+cur+' | 渠道: '+ch+'</div>'
        +'<div class="status-bar warn">&#9888; '+d.error+'</div>';
      info.className='update-info';return}
    const i=d.info;
    let h='<div style="margin-bottom:10px;font-size:13px;color:var(--text2)">当前版本: '+cur+' | 渠道: '+ch+'</div>';
    if(i.is_newer){
      h+='<div class="status-bar info" style="margin-bottom:8px">发现新版本: <b>'+i.tag+'</b></div>';
      h+='<button class="btn btn-warn" onclick="doUpdate()">下载并安装更新</button>';
      if(i.html_url)h+='<div class="hint"><a href="'+i.html_url+'" target="_blank">查看更新日志</a></div>';
    }else{
      h+='<div class="status-bar ok">&#10003; 已是最新版本 ('+i.tag+')</div>';
    }
    info.innerHTML=h;info.className='update-info';
  }).catch(e=>{info.innerHTML='<div class="status-bar err">检查失败: '+e+'</div>';
    info.className='update-info';
  }).finally(()=>{b.disabled=false;b.textContent='重新检查'});
}

function doUpdate(){
  const info=$('updateInfo');
  info.innerHTML='<div class="status-bar info"><span class="spinner"></span> 正在下载更新...</div>';
  fetch('/api/do_update',{method:'POST'})
  .then(r=>r.json()).then(d=>{
    const cls=d.ok?'ok':'err',icon=d.ok?'&#10003;':'&#10007;';
    const title=d.ok?'更新完成！请在 Magisk Manager 中重新刷入模块。':'更新失败: '+(d.error||'未知错误');
    info.innerHTML='<div class="status-bar '+cls+'">'+icon+' '+title+'</div>'
      +'<div style="font-size:12px;color:var(--text2);margin-top:8px;white-space:pre-wrap">'+(d.output||'')+'</div>';
  }).catch(e=>{info.innerHTML='<div class="status-bar err">更新请求失败: '+e+'</div>'});
}
</script>
</body>
</html>"""
