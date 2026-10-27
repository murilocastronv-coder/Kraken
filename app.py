import os
import time
import uuid
import threading
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
API = "https://api.fxapis.com/v1"
AUTO_LOCK = threading.Lock()
AUTO_STATE = {"running": False, "message": "Automação desligada", "lastSignal": None, "lastTradeAt": None}
AUTO_THREAD = None

PAGE = r"""
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar MT5 Demo · FXAPIs</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10131b;color:#f4f6fb;font:16px system-ui,sans-serif}.wrap{max-width:680px;margin:auto;padding:20px}.card{background:#1a2030;border:1px solid #303a50;border-radius:18px;padding:18px;margin:14px 0}h1{font-size:25px;margin:0 0 8px}.muted{color:#aab5c8;font-size:13px;line-height:1.5}.pill{display:inline-block;border-radius:99px;padding:6px 10px;background:#48391c;color:#ffdc8a;font-size:12px;font-weight:700}label{display:block;font-size:13px;color:#bac5d8;margin:14px 0 6px}input,select{width:100%;padding:13px;border:1px solid #3a4660;background:#0f1420;color:#fff;border-radius:10px;font-size:16px}button{border:0;border-radius:11px;padding:13px 15px;font-weight:750;font-size:15px;cursor:pointer;background:#6f8cff;color:#071020;width:100%;margin-top:14px}.secondary{background:#303a50;color:#fff}.status{white-space:pre-wrap;overflow-wrap:anywhere;background:#0e1420;border-radius:10px;padding:12px;margin-top:12px;font-size:13px}.warning{color:#ffdc8a}.ok{color:#82f0bd}.err{color:#ff9aab}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:460px){.grid{grid-template-columns:1fr}}
</style></head><body><main class="wrap">
<div class="card"><span class="pill">SOMENTE CONTA DEMO</span><h1>Conectar MetaTrader 5</h1><p class="muted">FXAPIs · EUR/USD. A automação demo de 2 minutos é opcional, usa volume fixo de 0,01 lote e pode perder dinheiro virtual. A chave e a senha são enviadas ao backend por HTTPS e não são gravadas em arquivo nem no navegador.</p></div>
<div class="card"><form id="f">
<label>Chave API FXAPIs (crie uma nova, com accounts:write)</label><input id="key" type="password" autocomplete="off" required placeholder="Cole sua chave FXAPIs nova">
<div class="grid"><div><label>Login MT5</label><input id="login" value="5057942310" required></div><div><label>Servidor exato</label><input id="server" value="MetaQuotes-Demo" required></div></div>
<label>ID da conta já cadastrada na FXAPIs</label><input id="accountIdInput" value="75591689-2129-432e-838a-c1e16c18e836" placeholder="ID da conta FXAPIs">
<label>Senha de negociação MT5 (não a senha do investidor)</label><input id="password" type="password" autocomplete="off" required>
<label>Ativo</label><input value="EURUSD" readonly>
<label>Timeframe</label><input value="M15" readonly>
<button id="connect" type="submit">Cadastrar conta demo na FXAPIs</button><button class="secondary" type="button" id="updatePassword">Atualizar senha da conta existente</button></form>
<div id="status" class="status">Ainda não conectado.</div>
<button class="secondary" id="warm" disabled>Conectar / colocar conta online</button>
<button class="secondary" id="check" disabled>Verificar estado da conexão</button><button class="secondary" id="diagnose" disabled>Diagnosticar servidor e alternativas</button><div class="grid"><div><label>Servidor alternativo (somente se a FXAPIs sugerir)</label><input id="altServer" placeholder="Servidor exato sugerido pela FXAPIs"></div><div><label>&nbsp;</label><button class="secondary" id="moveServer" type="button">Corrigir servidor da conta</button></div></div>
<button class="secondary" id="positions" disabled>Consultar posições</button><button id="autoStart" type="button">Iniciar estratégia automática DEMO (2 min)</button><button class="secondary" id="autoStop" type="button">Parar estratégia automática</button><div id="autoStatus" class="status">Automação desligada. A estratégia só funciona enquanto o serviço estiver ativo.</div>
<div class="grid"><div><label>Volume da ordem (lotes)</label><input id="volume" type="number" min="0.01" max="0.01" step="0.01" value="0.01" readonly></div><div><label>Ativo para ordem</label><input value="EURUSD" readonly></div></div><button id="buy" disabled>Comprar EURUSD · 0,01 lote</button><button id="sell" class="secondary" disabled>Vender EURUSD · 0,01 lote</button><div id="orderResult" class="status" role="status" aria-live="polite">O resultado da última tentativa de ordem aparecerá aqui.</div><p class="muted warning">As ordens só são liberadas depois de a FXAPIs confirmar explicitamente environment=demo e status=ready. Cada ordem exige toque manual e confirmação.</p><p class="muted warning">Importante: só continue se o servidor for realmente demo. O prefixo fx_test_ não garante um ambiente isolado. Nunca use uma conta real aqui. Não feche a página até concluir a verificação; os dados sensíveis ficam apenas na memória desta página.</p>
</div>
<script>
const $=id=>document.getElementById(id);let accountId=null;
function creds(){return {apiKey:$('key').value.trim(),accountId:$('accountIdInput').value.trim()||accountId,login:$('login').value.trim(),server:$('server').value.trim(),password:$('password').value}}
function show(x,kind=''){ $('status').className='status '+kind; $('status').textContent=typeof x==='string'?x:JSON.stringify(x,null,2)}
async function call(path,body){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','Accept':'application/json'},body:JSON.stringify(body)});let raw=await r.text();let j;try{j=JSON.parse(raw)}catch(_){let snippet=raw.replace(/<[^>]*>/g,' ').replace(/\\s+/g,' ').trim().slice(0,220);throw new Error('O servidor respondeu algo que não é JSON (HTTP '+r.status+'). '+(snippet||'Resposta vazia')+' — verifique se a Render terminou o deploy.')}if(!r.ok)throw new Error(j.error||j.message||('HTTP '+r.status));return j}
$('updatePassword').onclick=async()=>{try{show('Atualizando senha da conta existente…');let j=await call('/api/password',creds());accountId=$('accountIdInput').value.trim()||accountId;show(j,'ok');$('warm').disabled=false;$('check').disabled=false;$('diagnose').disabled=false;$('positions').disabled=false;}catch(e){show(e.message,'err')}};
$('f').addEventListener('submit',async e=>{e.preventDefault();$('connect').disabled=true;show('Cadastrando conta demo…');try{let j=await call('/api/connect',creds());accountId=j.accountId;$('accountIdInput').value=j.accountId;show(j,'ok');$('warm').disabled=false;$('check').disabled=false;$('diagnose').disabled=false;$('positions').disabled=false;$('password').value='';}catch(e){show(e.message,'err')}finally{$('connect').disabled=false}});
$('warm').onclick=async()=>{try{show('Conectando a conta…');let j=await call('/api/warm',creds());show(j,'ok')}catch(e){show(e.message,'err')}};
$('check').onclick=async()=>{ $('check').disabled=true;try{let j=await call('/api/status',creds());let lifecycle=String(j.state||j.status||'').toLowerCase();let verified=String(j.environment||'').toLowerCase()==='demo' && lifecycle==='ready';$('buy').disabled=!verified;$('sell').disabled=!verified;show(verified?{...j,notice:'Conta DEMO pronta. Teste manual permitido com 0,01 lote.'}:{...j,warning:'Ordens bloqueadas: a FXAPIs precisa confirmar environment=demo e state/status=ready.'},verified?'ok':'warning')}catch(e){show(e.message,'err');$('buy').disabled=true;$('sell').disabled=true}finally{$('check').disabled=false}};
$('positions').onclick=async()=>{try{let j=await call('/api/positions',creds());show(j,'ok')}catch(e){show(e.message,'err')}};
$('diagnose').onclick=async()=>{try{show('Consultando dados da conta e estado atual, sem tentar novo login…');let j=await call('/api/diagnose',creds());if(j.suggestedServers&&j.suggestedServers.length){$('altServer').value=j.suggestedServers[0];}show(j,j.state==='invalid_credentials'?'warning':'ok')}catch(e){show(e.message,'err')}};
$('autoStart').onclick=async()=>{if(!confirm('Iniciar automação SOMENTE na conta demo confirmada? A estratégia pode perder dinheiro virtual e não garante lucro.'))return;try{show('Validando conta demo e iniciando estratégia…');let j=await call('/api/auto/start',creds());$('autoStatus').textContent=JSON.stringify(j,null,2);show(j,'ok')}catch(e){show(e.message,'err')}};
$('autoStop').onclick=async()=>{try{let j=await call('/api/auto/stop',creds());$('autoStatus').textContent=JSON.stringify(j,null,2);show(j,'ok')}catch(e){show(e.message,'err')}};
$('moveServer').onclick=async()=>{const server=$('altServer').value.trim();if(!server){show('Primeiro clique em Diagnosticar e use somente um servidor sugerido pela FXAPIs.','warning');return;}if(!confirm('Trocar o servidor desta conta existente para '+server+'? A FXAPIs tentará conectar usando a senha já armazenada.'))return;try{show('Atualizando servidor na conta existente…');let j=await call('/api/server',{...creds(),newServer:server});show(j,'ok')}catch(e){show(e.message,'err')}};

async function order(side){const b=side==='buy'?$('buy'):$('sell');if(!confirm('TESTE SOMENTE NA CONTA DEMO: enviar '+(side==='buy'?'COMPRA':'VENDA')+' EURUSD de 0,01 lote?'))return;b.disabled=true;$('buy').disabled=true;$('sell').disabled=true;const out=$('orderResult');out.className='status';out.textContent='Enviando ordem de teste para a FXAPIs…';out.scrollIntoView({behavior:'smooth',block:'center'});show('Enviando ordem de teste 0,01 lote para a FXAPIs…');try{let j=await call('/api/order',{...creds(),side,volume:'0.01',instrument:'EURUSD'});out.className='status ok';out.textContent=JSON.stringify(j,null,2);show(j,'ok')}catch(e){out.className='status err';out.textContent='A ordem não foi confirmada: '+e.message;show('A ordem não foi confirmada: '+e.message,'err')}finally{b.disabled=false;$('sell').disabled=false;$('buy').disabled=false}}$('buy').onclick=()=>order('buy');$('sell').onclick=()=>order('sell');
</script></main></body></html>
"""

def fx_request(method, path, api_key, payload=None):
    if not api_key or not api_key.startswith("fx_"):
        raise ValueError("Informe uma chave FXAPIs válida.")
    r = requests.request(method, API + path, headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, json=payload, timeout=30)
    try:
        data = r.json()
    except Exception:
        data = {"error": "A FXAPIs retornou uma resposta não JSON.", "status": r.status_code}
    if not r.ok:
        msg = data.get("error") or data.get("message") or data.get("code") or ("HTTP " + str(r.status_code))
        raise RuntimeError(str(msg))
    return data.get("data", data)

@app.get("/")
def home():
    return render_template_string(PAGE)

@app.get("/health")
def health():
    return jsonify({"ok": True, "service": "mt5-demo-connector", "trading_enabled": False})

@app.post("/api/connect")
def connect():
    try:
        d = request.get_json(force=True)
        login = str(d.get("login", "")).strip()
        server = str(d.get("server", "")).strip()
        password = d.get("password", "")
        key = d.get("apiKey", "")
        if not login or not server or not password:
            return jsonify(error="Preencha login, servidor e senha de negociação."), 400
        # Restrict this first version to the demo server the user selected.
        if "demo" not in server.lower():
            return jsonify(error="Bloqueado: o servidor não parece ser demo. Use somente conta de demonstração."), 400
        data = fx_request("POST", "/accounts", key, {
            "platform": "mt5", "login": login, "server": server,
            "password": password, "mode": "warm_on_demand",
            "label": "Render EURUSD M15 demo"
        })
        account_id = data.get("id") or data.get("accountId") or data.get("account_id")
        if not account_id:
            return jsonify(error="A FXAPIs não devolveu um ID de conta reconhecido. Resposta omitida por segurança."), 502
        return jsonify({"ok": True, "accountId": account_id, "message": "Conta cadastrada. Agora coloque-a online e verifique que environment é demo."})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except Exception as e:
        return jsonify(error=str(e)), 502

def account_action(action):
    d = request.get_json(force=True)
    account_id = str(d.get("accountId") or "").strip()
    key = d.get("apiKey", "")
    if not account_id:
        return jsonify(error="Cadastre a conta primeiro para receber o ID."), 400
    try:
        if action == "warm":
            data = fx_request("POST", f"/accounts/{account_id}/warm", key, {})
        elif action == "status":
            # The lifecycle endpoint may omit environment; read the account record too.
            status_data = fx_request("GET", f"/accounts/{account_id}/status", key)
            account_data = fx_request("GET", f"/accounts/{account_id}", key)
            data = dict(status_data)
            env = str(account_data.get("environment") or status_data.get("environment") or "").lower()
            if env:
                data["environment"] = env
        else:
            data = fx_request("GET", f"/accounts/{account_id}/positions", key)
        # Never represent an account as safely connected until the provider explicitly confirms demo.
        if action in ("warm", "status"):
            env = str(data.get("environment", "")).lower()
            if env and env != "demo":
                return jsonify(error="Bloqueado: a FXAPIs não confirmou ambiente demo.", environment=env), 409
            data = dict(data)
            data["demo_verified"] = env == "demo"
            data["warning"] = "Se demo_verified for false, não envie ordens."
        return jsonify(data)
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.post("/api/password")
def update_password():
    try:
        d = request.get_json(force=True)
        account_id = str(d.get("accountId") or "").strip()
        password = d.get("password", "")
        server = str(d.get("server") or "").strip()
        key = d.get("apiKey", "")
        if not account_id or not password or not server:
            return jsonify(error="Informe o ID da conta, servidor e senha principal do MT5."), 400
        if "demo" not in server.lower():
            return jsonify(error="Bloqueado: use somente servidor demo."), 400
        data = fx_request("POST", f"/accounts/{account_id}/password", key, {"password": password, "server": server})
        return jsonify({"ok": True, "accountId": account_id, "message": "Senha atualizada. Agora conecte a conta e verifique o estado.", "result": data})
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.post("/api/diagnose")
def diagnose():
    try:
        d = request.get_json(force=True)
        account_id = str(d.get("accountId") or "").strip()
        key = d.get("apiKey", "")
        if not account_id:
            return jsonify(error="Informe o ID da conta FXAPIs."), 400
        account = fx_request("GET", f"/accounts/{account_id}", key)
        status_data = fx_request("GET", f"/accounts/{account_id}/status", key)
        problem = account.get("problem") or status_data.get("problem") or {}
        return jsonify({"ok": True, "accountId": account_id, "login": account.get("login"),
            "server": account.get("server"), "environment": account.get("environment"),
            "state": status_data.get("state") or account.get("state"),
            "detail": status_data.get("detail") or status_data.get("stateDetail"),
            "problem": problem, "suggestedServers": problem.get("otherServers") or [],
            "nextStep": "Use apenas um servidor alternativo explicitamente sugerido pela FXAPIs."})
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.post("/api/server")
def change_server():
    try:
        d = request.get_json(force=True)
        account_id = str(d.get("accountId") or "").strip()
        server = str(d.get("newServer") or "").strip()
        if not account_id or not server:
            return jsonify(error="Informe ID da conta e servidor alternativo."), 400
        if "demo" not in server.lower():
            return jsonify(error="Bloqueado: este painel aceita somente servidores demo."), 400
        data = fx_request("POST", f"/accounts/{account_id}/server", d.get("apiKey", ""),
                          {"server": server, "connect": False})
        return jsonify({"ok": True, "message": "Servidor atualizado sem iniciar login automaticamente.", "result": data})
    except Exception as e:
        return jsonify(error=str(e)), 502

@app.post("/api/warm")
def warm():
    return account_action("warm")

@app.post("/api/status")
def status():
    return account_action("status")

@app.post("/api/positions")
def positions():
    return account_action("positions")



def auto_strategy_worker(api_key, account_id):
    global AUTO_STATE
    API_ROOT = API
    def req(method, path, payload=None, idem=None):
        headers={"Authorization":"Bearer "+api_key,"Accept":"application/json","Content-Type":"application/json"}
        if idem: headers["Idempotency-Key"]=idem
        r=requests.request(method, API_ROOT+path, headers=headers, json=payload, timeout=20)
        try: body=r.json()
        except Exception: raise RuntimeError("Resposta FXAPIs não JSON")
        if not r.ok: raise RuntimeError(str(body.get("error") or body.get("message") or body.get("code") or ("HTTP "+str(r.status_code))))
        return body.get("data", body)
    try:
        while True:
            with AUTO_LOCK:
                if not AUTO_STATE.get("running"): break
            # Trade only at 2-minute boundaries; always close our opened position after 120 seconds.
            now=time.time()
            due=int(now//120)*120
            with AUTO_LOCK:
                opened=AUTO_STATE.get("opened")
            if opened and now-opened.get("openedAt", now)>=120:
                ticket=opened.get("ticket")
                if ticket:
                    req("POST",f"/accounts/{account_id}/positions/{ticket}/close",{}, "close_"+str(opened["orderId"]))
                    with AUTO_LOCK:
                        AUTO_STATE["opened"]=None
                        AUTO_STATE["message"]="Posição fechada após 2 minutos"
                else:
                    raise RuntimeError("FXAPIs não devolveu ticket de posição; automação parada por segurança")
            with AUTO_LOCK:
                opened=AUTO_STATE.get("opened")
                last_cycle=AUTO_STATE.get("lastCycle")
            if not opened and last_cycle != due and now >= due+2:
                status=req("GET",f"/accounts/{account_id}/status")
                account=req("GET",f"/accounts/{account_id}")
                env=str(account.get("environment") or status.get("environment") or "").lower()
                state=str(status.get("state") or status.get("status") or "").lower()
                if env!="demo" or state!="ready":
                    raise RuntimeError("Parada: FXAPIs não confirmou environment=demo e state=ready")
                candles_data=req("GET",f"/accounts/{account_id}/candles?instrument=EURUSD&timeframe=M1&count=40")
                candles=candles_data.get("candles") or []
                if len(candles)<25:
                    raise RuntimeError("Ainda não há 25 candles M1 para calcular o sinal")
                closes=[float(x.get("close")) for x in candles if x.get("close") is not None]
                if len(closes)<25: raise RuntimeError("Candles insuficientes ou inválidos")
                def ema(vals, period):
                    a=2/(period+1); v=vals[0]
                    for x in vals[1:]: v=a*x+(1-a)*v
                    return v
                e9=ema(closes[-30:],9); e21=ema(closes[-30:],21)
                diffs=[closes[i]-closes[i-1] for i in range(1,len(closes))]
                gains=[max(0,x) for x in diffs[-14:]]; losses=[max(0,-x) for x in diffs[-14:]]
                avg_g=sum(gains)/max(1,len(gains)); avg_l=sum(losses)/max(1,len(losses))
                rsi=100 if avg_l==0 else 100-(100/(1+avg_g/avg_l))
                # Conservative directional filter; skips weak/contradictory signals.
                side="buy" if e9>e21 and rsi>=52 else ("sell" if e9<e21 and rsi<=48 else None)
                with AUTO_LOCK:
                    AUTO_STATE["lastCycle"]=due
                    AUTO_STATE["lastSignal"]={"side":side,"ema9":e9,"ema21":e21,"rsi":rsi,"at":datetime.now(timezone.utc).isoformat()}
                if side:
                    order=req("POST",f"/accounts/{account_id}/orders/market",{"symbol":"EURUSD","side":side,"volume":"0.01"}, "auto_"+str(due))
                    ticket=order.get("brokerPositionId")
                    if not ticket: raise RuntimeError("Ordem sem ticket identificável; automação parada por segurança")
                    with AUTO_LOCK:
                        AUTO_STATE["opened"]={"ticket":str(ticket),"orderId":str(order.get("id") or due),"openedAt":time.time(),"side":side}
                        AUTO_STATE["lastTradeAt"]=datetime.now(timezone.utc).isoformat()
                        AUTO_STATE["message"]="Ordem "+side+" aberta; fechamento programado para 120 segundos"
                else:
                    with AUTO_LOCK: AUTO_STATE["message"]="Sem entrada: sinais contraditórios/fracos; ciclo ignorado para proteger a conta"
            time.sleep(1)
    except Exception as e:
        with AUTO_LOCK:
            AUTO_STATE["running"]=False
            AUTO_STATE["message"]="Automação parada por segurança: "+str(e)
    finally:
        with AUTO_LOCK: AUTO_STATE["running"]=False

@app.post("/api/auto/start")
def auto_start():
    global AUTO_THREAD, AUTO_STATE
    d=request.get_json(force=True); key=d.get("apiKey",""); account_id=str(d.get("accountId") or "").strip()
    if not account_id: return jsonify(error="Informe o ID da conta FXAPIs."),400
    try:
        status=fx_request("GET",f"/accounts/{account_id}/status",key)
        account=fx_request("GET",f"/accounts/{account_id}",key)
        env=str(account.get("environment") or status.get("environment") or "").lower()
        state=str(status.get("state") or status.get("status") or "").lower()
        if env!="demo" or state!="ready": return jsonify(error="Bloqueado: a FXAPIs precisa confirmar environment=demo e state=ready.",environment=env,state=state),409
        with AUTO_LOCK:
            if AUTO_STATE.get("running"): return jsonify(ok=True,message="Automação já está rodando.",state=AUTO_STATE)
            AUTO_STATE={"running":True,"message":"Estratégia demo iniciada","lastSignal":None,"lastTradeAt":None,"opened":None,"lastCycle":None}
            AUTO_THREAD=threading.Thread(target=auto_strategy_worker,args=(key,account_id),daemon=True)
            AUTO_THREAD.start()
        return jsonify(ok=True,message="Estratégia demo iniciada. EURUSD, volume fixo 0.01, filtro EMA9/EMA21 + RSI, tentativa a cada 2 minutos, fechamento após 120 s. Sinais fracos são ignorados; lucro não é garantido.",state=AUTO_STATE)
    except Exception as e: return jsonify(error=str(e)),502

@app.post("/api/auto/stop")
def auto_stop():
    global AUTO_STATE
    d=request.get_json(force=True); key=d.get("apiKey",""); account_id=str(d.get("accountId") or "").strip()
    try:
        with AUTO_LOCK:
            opened=AUTO_STATE.get("opened")
            AUTO_STATE["running"]=False
        if opened and opened.get("ticket") and account_id and key:
            fx_request("POST",f"/accounts/{account_id}/positions/{opened['ticket']}/close",key, {})
            with AUTO_LOCK: AUTO_STATE["opened"]=None
        with AUTO_LOCK: AUTO_STATE["message"]="Automação parada; posição da estratégia fechada se estava aberta."
        return jsonify(ok=True,message="Automação parada. A posição gerenciada foi fechada se havia uma aberta.",state=AUTO_STATE)
    except Exception as e:
        with AUTO_LOCK: AUTO_STATE["message"]="Automação parada, mas confirme manualmente se a posição foi fechada: "+str(e)
        return jsonify(ok=False,error="Automação parada; verifique a posição no MT5/FXAPIs para confirmar o fechamento.",state=AUTO_STATE),502

@app.get("/api/auto/status")
def auto_status():
    with AUTO_LOCK: return jsonify(AUTO_STATE)

@app.post("/api/order")
def place_order():
    """Submit one explicitly confirmed demo order; warm and poll the demo account first."""
    try:
        d = request.get_json(force=True)
        key = d.get("apiKey", "")
        account_id = str(d.get("accountId") or "").strip()
        side = str(d.get("side") or "").lower()
        instrument = str(d.get("instrument") or "")
        volume = str(d.get("volume") or "")
        if not account_id:
            return jsonify(error="Informe o ID da conta FXAPIs."), 400
        if side not in ("buy", "sell") or instrument != "EURUSD" or volume != "0.01":
            return jsonify(error="Teste bloqueado: permitido apenas buy/sell EURUSD com volume 0.01 na conta demo."), 400

        # Check the account's actual environment before doing anything that can place an order.
        account_data = fx_request("GET", f"/accounts/{account_id}", key)
        environment = str(account_data.get("environment") or "").lower()
        if environment != "demo":
            return jsonify(error="Bloqueado: a FXAPIs não confirmou que esta conta é DEMO.", environment=environment or None), 409

        # warm_on_demand accounts may not be ready until explicitly warmed. Poll lifecycle safely.
        status_data = fx_request("GET", f"/accounts/{account_id}/status", key)
        state = str(status_data.get("state") or status_data.get("status") or "").lower()
        if state != "ready":
            if state in ("invalid_credentials", "trading_disabled", "needs_2fa", "needs_certificate"):
                return jsonify(error="A conta precisa de atenção antes de negociar.", state=state, detail=status_data.get("detail")), 409
            fx_request("POST", f"/accounts/{account_id}/warm", key, {})
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                time.sleep(2)
                status_data = fx_request("GET", f"/accounts/{account_id}/status", key)
                state = str(status_data.get("state") or status_data.get("status") or "").lower()
                if state == "ready":
                    break
                if state in ("invalid_credentials", "trading_disabled", "needs_2fa", "needs_certificate", "error"):
                    return jsonify(error="A conta não ficou pronta para negociar.", state=state, detail=status_data.get("detail")), 409
            if state != "ready":
                return jsonify(error="Tempo esgotado aguardando a conta demo ficar pronta. Nenhuma ordem foi enviada.", state=state, detail=status_data.get("detail")), 504

        idem = str(uuid.uuid4())
        try:
            r = requests.post(API + f"/accounts/{account_id}/orders/market",
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json",
                         "Accept": "application/json", "Idempotency-Key": idem},
                json={"symbol": instrument, "side": side, "volume": volume, "deviationPoints": 20},
                timeout=90)
        except requests.RequestException as e:
            return jsonify(error="Falha de comunicação ao enviar ordem. Não repita sem verificar o histórico da FXAPIs.", details=str(e), idempotencyKey=idem), 502
        try:
            result = r.json()
        except Exception:
            result = {"error": "FXAPIs retornou resposta não JSON.", "httpStatus": r.status_code}
        data = result.get("data", result)
        if not r.ok:
            err = result.get("error") or result.get("message") or result.get("code") or ("HTTP " + str(r.status_code))
            return jsonify(error=str(err), code=result.get("code"), details=result.get("details"),
                           retryable=result.get("retryable"), httpStatus=r.status_code,
                           providerResponse=data, idempotencyKey=idem), r.status_code if 400 <= r.status_code < 600 else 502
        state = str(data.get("state") or "").lower()
        return jsonify({"ok": True,
            "message": ("Ordem preenchida pelo broker." if state in ("filled", "partially_filled")
                        else "Pedido recebido pela FXAPIs; confira state/retcode e o histórico do MT5 para confirmar o preenchimento."),
            "side": side, "symbol": instrument, "volume": volume, "idempotencyKey": idem, "result": data})
    except Exception as e:
        return jsonify(error=str(e)), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
