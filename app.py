import json, os, subprocess, threading, time
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string
app = Flask(__name__)
STATE_FILE=os.getenv("STATE_FILE","/tmp/state.json")
INITIAL=float(os.getenv("INITIAL_CASH","10000")); SYMBOL=os.getenv("SYMBOL","BTC/USD")
LOCK=threading.RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def fresh():
 return {"paper_only":True,"running":False,"cash":INITIAL,"asset":0.0,"avg_price":0.0,"realized_pnl":0.0,"trades":[],"prices":[],"last_price":None,"last_action":"Pronto para iniciar","last_update":None,"initial_cash":INITIAL,"symbol":SYMBOL,"errors":[]}
def save():
 os.makedirs(os.path.dirname(STATE_FILE) or ".",exist_ok=True)
 with open(STATE_FILE+".tmp","w") as f: json.dump(state,f)
 os.replace(STATE_FILE+".tmp",STATE_FILE)
def load():
 try:
  with open(STATE_FILE) as f:
   s=fresh(); s.update(json.load(f)); return s
 except Exception: return fresh()
state=load()
def cli(args):
 p=subprocess.run(["kraken"]+args+["-o","json"],capture_output=True,text=True,timeout=25)
 if p.returncode: raise RuntimeError((p.stderr or p.stdout or "Kraken CLI error")[-500:])
 return json.loads(p.stdout)
def findprice(x):
 if isinstance(x,dict):
  for k in ("last_price","last","price"):
   try:
    if float(x[k])>0:return float(x[k])
   except Exception:pass
  for v in x.values():
   p=findprice(v)
   if p:return p
 elif isinstance(x,list):
  for v in x:
   p=findprice(v)
   if p:return p
 return None
def getprice():
 p=findprice(cli(["ticker",SYMBOL]))
 if not p: raise RuntimeError("Não consegui interpretar a cotação do Kraken CLI.")
 return p
def avg(a): return sum(a)/len(a) if a else 0
def worker():
 while True:
  time.sleep(15)
  with LOCK:
   if not state["running"]:continue
   try:
    price=getprice(); state["prices"]=(state["prices"]+[price])[-100:]
    state["last_price"]=price; state["last_update"]=now(); ps=state["prices"]
    if len(ps)>=21:
     fast,slow=avg(ps[-9:]),avg(ps[-21:])
     if fast>slow and state["asset"]==0 and state["cash"]>10:
      amount=state["cash"]*.10; qty=amount/price; state["cash"]-=amount; state["asset"]=qty; state["avg_price"]=price
      state["trades"].append({"time":now(),"side":"BUY","price":price,"qty":qty,"notional":amount,"reason":"Média 9 acima da 21"})
      state["last_action"]=f"COMPRA SIMULADA · {qty:.6f} {SYMBOL.split('/')[0]}"
     elif fast<slow and state["asset"]>0:
      qty=state["asset"]; proceeds=qty*price; pnl=(price-state["avg_price"])*qty
      state["cash"]+=proceeds; state["asset"]=0.0; state["realized_pnl"]+=pnl
      state["trades"].append({"time":now(),"side":"SELL","price":price,"qty":qty,"notional":proceeds,"pnl":pnl,"reason":"Média 9 abaixo da 21"})
      state["last_action"]=f"VENDA SIMULADA · P&L {pnl:+.2f}"
    save()
   except Exception as e:
    state["last_update"]=now(); state["errors"]=(state["errors"]+[str(e)])[-5:]
    state["last_action"]="Erro na cotação; veja a mensagem abaixo"; save()
threading.Thread(target=worker,daemon=True).start()
PAGE = r"""
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#201c35"><title>Kraken Paper Trader</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101018;color:#f4f3fa;font:16px system-ui,sans-serif}.wrap{max-width:850px;margin:auto;padding:18px}.top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}.brand{font-size:22px;font-weight:800}.tag{background:#164b3b;color:#a4f3cf;padding:7px 10px;border-radius:999px;font-size:12px;font-weight:800}.sub,.label{color:#aaa7bd;font-size:12px;margin-top:5px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0}.card{background:#1b1a27;border:1px solid #302d42;border-radius:16px;padding:15px;min-width:0}.val{font-size:22px;font-weight:750;margin-top:6px;overflow-wrap:anywhere}.buttons{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.btn{border:0;border-radius:12px;padding:13px 17px;font-weight:750;font-size:14px;background:#8264ff;color:white}.stop{background:#3a354c}.section{font-weight:750;margin:22px 0 10px}.trade{display:grid;grid-template-columns:70px 1fr 1fr;gap:8px;padding:11px 0;border-bottom:1px solid #302d42;font-size:12px}.buy{color:#6ce5b1}.sell{color:#ff8d9a}.foot{color:#8c899f;font-size:12px;line-height:1.5;margin-top:20px}.error{color:#ff9a9a;font-size:12px;margin-top:10px}@media(min-width:600px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}.val{font-size:24px}}
</style></head><body><main class="wrap"><div class="top"><div><div class="brand">Kraken Paper Trader</div><div class="sub">Painel móvel · estratégia EMA 9/21 · dados públicos</div></div><div class="tag">SIMULAÇÃO · SEM DINHEIRO REAL</div></div>
<div class="grid"><div class="card"><div class="label">Patrimônio simulado</div><div class="val" id="equity">—</div></div><div class="card"><div class="label">Preço de mercado</div><div class="val" id="price">—</div></div><div class="card"><div class="label">P&L total</div><div class="val" id="pnl">—</div></div><div class="card"><div class="label">Estado do robô</div><div class="val" id="run">Parado</div></div></div>
<div class="buttons"><button class="btn" onclick="act('start')">Iniciar robô demo</button><button class="btn stop" onclick="act('stop')">Parar robô</button><button class="btn stop" onclick="act('reset')">Reiniciar saldo demo</button></div>
<div class="card"><div class="label">Última ação</div><div class="val" style="font-size:16px" id="action">Carregando…</div><div class="sub" id="updated"></div><div class="error" id="err"></div></div>
<div class="section">Histórico de operações simuladas</div><div class="card" id="trades">Nenhuma operação ainda.</div>
<div class="foot">O app consulta apenas cotações públicas e simula compras/vendas dentro do servidor. Não usa API Key e não envia ordens reais. Estratégia didática, sem garantia de lucro. Primeiro sinal após 21 amostras de preço.</div></main>
<script>
const money=n=>Number(n||0).toLocaleString('en-US',{style:'currency',currency:'USD'});
async function refresh(){try{let r=await fetch('/api/state'),s=await r.json();let equity=s.cash+s.asset*(s.last_price||s.avg_price||0);document.getElementById('equity').textContent=money(equity);document.getElementById('price').textContent=s.last_price?money(s.last_price):'Aguardando';let pnl=equity-s.initial_cash,p=document.getElementById('pnl');p.textContent=(pnl>=0?'+':'')+money(pnl);p.style.color=pnl>=0?'#6ce5b1':'#ff8d9a';document.getElementById('run').textContent=s.running?'Rodando':'Parado';document.getElementById('action').textContent=s.last_action;document.getElementById('updated').textContent='Atualização: '+(s.last_update||'—')+' · '+s.symbol;document.getElementById('err').textContent=(s.errors||[]).slice(-1)[0]||'';let rows=(s.trades||[]).slice().reverse().slice(0,20);document.getElementById('trades').innerHTML=rows.length?rows.map(t=>`<div class="trade"><b class="${t.side==='BUY'?'buy':'sell'}">${t.side==='BUY'?'COMPRA':'VENDA'}</b><span>${new Date(t.time).toLocaleString()}</span><span>${money(t.price)}</span><span>Qtd. ${Number(t.qty).toFixed(6)}</span><span>${money(t.notional)}</span><span>${t.pnl===undefined?'':'P&L '+money(t.pnl)}</span></div>`).join(''):'Nenhuma operação ainda.'}catch(e){}}
async function act(a){let r=await fetch('/api/'+a,{method:'POST'}),j=await r.json();if(!r.ok)alert(j.error||'Erro');refresh()}setInterval(refresh,5000);refresh();
</script></body></html>
"""
@app.get("/")
def home(): return render_template_string(PAGE)
@app.get("/health")
def health(): return jsonify({"ok":True,"paper_only":True})
@app.get("/api/state")
def api_state():
 with LOCK:
  s=dict(state); s["equity"]=s["cash"]+s["asset"]*(s["last_price"] or s["avg_price"] or 0); return jsonify(s)
@app.post("/api/start")
def start():
 with LOCK:
  state["running"]=True; state["last_action"]="Robô iniciado em SIMULAÇÃO, sem ordens reais."; save(); return jsonify({"ok":True})
@app.post("/api/stop")
def stop():
 with LOCK:
  state["running"]=False; state["last_action"]="Robô parado."; save(); return jsonify({"ok":True})
@app.post("/api/reset")
def reset():
 global state
 with LOCK:
  state=fresh(); save(); return jsonify({"ok":True})
if __name__=="__main__": app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
