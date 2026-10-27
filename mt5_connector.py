import os
import requests
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)
API = "https://api.fxapis.com/v1"

PAGE = r"""
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar MT5 Demo · FXAPIs</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#10131b;color:#f4f6fb;font:16px system-ui,sans-serif}.wrap{max-width:680px;margin:auto;padding:20px}.card{background:#1a2030;border:1px solid #303a50;border-radius:18px;padding:18px;margin:14px 0}h1{font-size:25px;margin:0 0 8px}.muted{color:#aab5c8;font-size:13px;line-height:1.5}.pill{display:inline-block;border-radius:99px;padding:6px 10px;background:#48391c;color:#ffdc8a;font-size:12px;font-weight:700}label{display:block;font-size:13px;color:#bac5d8;margin:14px 0 6px}input,select{width:100%;padding:13px;border:1px solid #3a4660;background:#0f1420;color:#fff;border-radius:10px;font-size:16px}button{border:0;border-radius:11px;padding:13px 15px;font-weight:750;font-size:15px;cursor:pointer;background:#6f8cff;color:#071020;width:100%;margin-top:14px}.secondary{background:#303a50;color:#fff}.status{white-space:pre-wrap;overflow-wrap:anywhere;background:#0e1420;border-radius:10px;padding:12px;margin-top:12px;font-size:13px}.warning{color:#ffdc8a}.ok{color:#82f0bd}.err{color:#ff9aab}.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}@media(max-width:460px){.grid{grid-template-columns:1fr}}
</style></head><body><main class="wrap">
<div class="card"><span class="pill">SOMENTE CONTA DEMO</span><h1>Conectar MetaTrader 5</h1><p class="muted">FXAPIs · EUR/USD · velas M15. A chave e a senha são enviadas ao backend por HTTPS e não são gravadas em arquivo nem no navegador. Este painel não envia ordens de compra/venda.</p></div>
<div class="card"><form id="f">
<label>Chave API FXAPIs (crie uma nova, com accounts:write)</label><input id="key" type="password" autocomplete="off" required placeholder="Cole sua chave FXAPIs nova">
<div class="grid"><div><label>Login MT5</label><input id="login" value="5057912119" required></div><div><label>Servidor exato</label><input id="server" value="MetaQuotes-Demo" required></div></div>
<label>Senha de negociação MT5 (não a senha do investidor)</label><input id="password" type="password" autocomplete="off" required>
<label>Ativo</label><input value="EURUSD" readonly>
<label>Timeframe</label><input value="M15" readonly>
<button id="connect" type="submit">Cadastrar conta demo na FXAPIs</button></form>
<div id="status" class="status">Ainda não conectado.</div>
<button class="secondary" id="warm" disabled>Conectar / colocar conta online</button>
<button class="secondary" id="check" disabled>Verificar estado da conexão</button>
<button class="secondary" id="positions" disabled>Consultar posições</button>
<div class="grid"><div><label>Volume da ordem (lotes)</label><input id="volume" type="number" min="0.01" max="0.01" step="0.01" value="0.01" readonly></div><div><label>Ativo para ordem</label><input value="EURUSD" readonly></div></div><button id="buy" disabled>Comprar EURUSD · 0,01 lote</button><button id="sell" class="secondary" disabled>Vender EURUSD · 0,01 lote</button><p class="muted warning">As ordens só são liberadas depois de a FXAPIs confirmar explicitamente environment=demo e status=ready. Cada ordem exige toque manual e confirmação.</p><p class="muted warning">Importante: só continue se o servidor for realmente demo. O prefixo fx_test_ não garante um ambiente isolado. Nunca use uma conta real aqui. Não feche a página até concluir a verificação; os dados sensíveis ficam apenas na memória desta página.</p>
</div>
<script>
const $=id=>document.getElementById(id);let accountId=null;
function creds(){return {apiKey:$('key').value.trim(),accountId,login:$('login').value.trim(),server:$('server').value.trim(),password:$('password').value}}
function show(x,kind=''){ $('status').className='status '+kind; $('status').textContent=typeof x==='string'?x:JSON.stringify(x,null,2)}
async function call(path,body){let r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let j=await r.json();if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j}
$('f').addEventListener('submit',async e=>{e.preventDefault();$('connect').disabled=true;show('Cadastrando conta demo…');try{let j=await call('/api/connect',creds());accountId=j.accountId;show(j,'ok');$('warm').disabled=false;$('check').disabled=false;$('positions').disabled=false;$('password').value='';}catch(e){show(e.message,'err')}finally{$('connect').disabled=false}});
$('warm').onclick=async()=>{try{show('Conectando a conta…');let j=await call('/api/warm',creds());show(j,'ok')}catch(e){show(e.message,'err')}};
$('check').onclick=async()=>{try{let j=await call('/api/status',creds());show(j,j.environment==='demo'?'ok':'warning');let verified=j.environment==='demo' && String(j.status||'').toLowerCase()==='ready';$('buy').disabled=!verified;$('sell').disabled=!verified;if(!verified)show({...j,warning:'Ordens bloqueadas: confirme environment=demo e status=ready.'},'warning')}catch(e){show(e.message,'err');$('buy').disabled=true;$('sell').disabled=true}};
$('positions').onclick=async()=>{try{let j=await call('/api/positions',creds());show(j,'ok')}catch(e){show(e.message,'err')}};
async function order(side){if(!confirm('Confirmar '+(side==='buy'?'COMPRA':'VENDA')+' manual de EURUSD de 0,01 lote na conta DEMO?'))return;try{let j=await call('/api/order',{...creds(),side,volume:'0.01',instrument:'EURUSD'});show(j,'ok')}catch(e){show(e.message,'err')}}$('buy').onclick=()=>order('buy');$('sell').onclick=()=>order('sell');
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
            data = fx_request("GET", f"/accounts/{account_id}/status", key)
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

@app.post("/api/warm")
def warm():
    return account_action("warm")

@app.post("/api/status")
def status():
    return account_action("status")

@app.post("/api/positions")
def positions():
    return account_action("positions")



@app.post("/api/order")
def place_order():
    try:
        d = request.get_json(force=True)
        key = d.get("apiKey", "")
        account_id = str(d.get("accountId") or "").strip()
        side = str(d.get("side") or "").lower()
        instrument = str(d.get("instrument") or "")
        volume = str(d.get("volume") or "")
        if not account_id:
            return jsonify(error="Cadastre a conta e obtenha o ID primeiro."), 400
        if side not in ("buy", "sell") or instrument != "EURUSD" or volume != "0.01":
            return jsonify(error="Ordem bloqueada: somente buy/sell EURUSD com volume fixo 0.01."), 400
        status_data = fx_request("GET", f"/accounts/{account_id}/status", key)
        environment = str(status_data.get("environment", "")).lower()
        connection_status = str(status_data.get("state") or status_data.get("status") or "").lower()
        if environment != "demo" or connection_status != "ready":
            return jsonify(error="Ordem bloqueada: FXAPIs precisa confirmar environment=demo e status=ready.", environment=environment or None, status=connection_status or None), 409
        import uuid
        idem = str(uuid.uuid4())
        r = requests.post(API + f"/accounts/{account_id}/orders/market",
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Idempotency-Key": idem
            },
            json={"symbol": instrument, "side": side, "volume": volume, "clientOrderId": idem},
            timeout=30)
        try:
            result = r.json()
        except Exception:
            result = {"error": "FXAPIs retornou uma resposta não JSON.", "status": r.status_code}
        if not r.ok:
            err = result.get("error") or result.get("message") or result.get("code") or ("HTTP " + str(r.status_code))
            return jsonify(error=str(err)), r.status_code if 400 <= r.status_code < 600 else 502
        data = result.get("data", result)
        return jsonify({"ok": True, "message": "FXAPIs aceitou a solicitação de ordem na conta confirmada como demo. Confira o status e o ticket retornados pelo broker.", "side": side, "symbol": instrument, "volume": volume, "idempotencyKey": idem, "result": data})
    except Exception as e:
        return jsonify(error=str(e)), 502

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "10000")))
