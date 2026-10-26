import json, os, threading, time, subprocess
from datetime import datetime, timezone
from flask import Flask, jsonify, render_template_string
app = Flask(__name__)
STATE_FILE=os.getenv("STATE_FILE","/tmp/state.json")
INITIAL=float(os.getenv("INITIAL_CASH","100")); SYMBOL=os.getenv("SYMBOL","BTC/USD")
LOCK=threading.RLock()
def now(): return datetime.now(timezone.utc).isoformat()
def fresh():
 return {"paper_only":True,"running":False,"cash":INITIAL,"asset":0.0,"avg_price":0.0,"position_margin":0.0,"position_side":None,"leverage":1,"trade_amount":10.0,"take_profit_pct":3.0,"stop_loss_pct":2.0,"realized_pnl":0.0,"trades":[],"prices":[],"last_price":None,"last_action":"Pronto para iniciar","last_update":None,"initial_cash":INITIAL,"symbol":SYMBOL,"errors":[]}
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
def findprice(x):
 if isinstance(x,dict):
  for k in ("last_price","last","price","c"):
   v=x.get(k)
   try:
    if isinstance(v,list): v=v[0]
    if float(v)>0:return float(v)
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
 # Uses the installed official Kraken CLI, public market data only.
 pair = "BTCUSD" if SYMBOL.replace(" ","").upper() in ("BTC/USD","BTCUSD","XBT/USD","XBTUSD") else SYMBOL.replace("/","")
 proc=subprocess.run(["kraken","ticker",pair,"-o","json"],capture_output=True,text=True,timeout=20)
 if proc.returncode != 0:
  raise RuntimeError("Kraken CLI: " + (proc.stderr or proc.stdout or "falha ao consultar ticker")[-400:])
 try: data=json.loads(proc.stdout)
 except Exception as e: raise RuntimeError("Resposta JSON inválida do Kraken CLI: "+str(e))
 price=findprice(data)
 if not price: raise RuntimeError("Não consegui interpretar a cotação do Kraken CLI.")
 return price
def avg(a): return sum(a)/len(a) if a else 0
def worker():
 while True:
  time.sleep(5)
  with LOCK:
   if not state["running"]: continue
   try:
    price=getprice(); bucket=int(time.time()//60)
    state["last_price"]=price; state["last_update"]=now()
    state["prices"]=(state.get("prices",[])+[price])[-300:]
    candle=state.get("current_candle")
    if candle is None:
     state["current_candle"]={"bucket":bucket,"open":price,"high":price,"low":price,"close":price,"time":now()}
     state["last_candle_bucket"]=bucket
     state["signal_status"]="Montando a vela atual de 1 minuto"
    elif bucket == state.get("last_candle_bucket"):
     candle["high"]=max(candle["high"],price); candle["low"]=min(candle["low"],price); candle["close"]=price
     state["current_candle"]=candle
    else:
     closed=dict(candle); closed["close"]=price; closed["closed_at"]=now()
     state["candles"]=(state.get("candles",[])+[closed])[-100:]
     # Always close the previous one-minute position at the candle boundary.
     side=state.get("position_side","LONG")
     if state.get("asset",0)>0:
      qty=state["asset"]; direction=1 if side=="LONG" else -1
      pnl=(price-state["avg_price"])*qty*direction; margin=max(state.get("position_margin",0.0),0.01)
      state["cash"]+=max(0.0,margin+pnl); state["asset"]=0.0; state["position_margin"]=0.0; state["position_side"]=None; state["realized_pnl"]+=pnl
      state["trades"].append({"time":now(),"side":"SELL" if side=="LONG" else "BUY_TO_COVER","price":price,"qty":qty,"notional":qty*price,"pnl":pnl,"reason":"Fechamento obrigatório no fim da vela de 1 minuto","candle":"1m","position_side":side})
      state["last_action"]=f"FECHAMENTO SIMULADO {side} · fim da vela 1m · P&L {pnl:+.2f} USD"
     state["current_candle"]={"bucket":bucket,"open":price,"high":price,"low":price,"close":price,"time":now()}
     state["last_candle_bucket"]=bucket
     cs=state.get("candles",[]); direction=None
     if cs:
      prev=cs[-1]
      if prev["close"]>prev["open"]: direction="LONG"
      elif prev["close"]<prev["open"]: direction="SHORT"
     # One position per minute: follow the direction of the just-closed candle.
     if state.get("asset",0)<=0 and direction and state.get("cash",0)>=state.get("trade_amount",10):
      margin=min(state.get("trade_amount",10),state["cash"]); qty=(margin*state.get("leverage",1))/price
      state["cash"]-=margin; state["asset"]=qty; state["avg_price"]=price; state["position_margin"]=margin; state["position_side"]=direction
      state["trades"].append({"time":now(),"side":"BUY" if direction=="LONG" else "SELL_SHORT","price":price,"qty":qty,"notional":qty*price,"margin":margin,"leverage":state.get("leverage",1),"reason":"Direção da vela de 1 minuto anterior","candle":"1m","position_side":direction})
      state["last_action"]=f"ENTRADA SIMULADA {direction} · ciclo de 1 minuto"
      state["signal_status"]="Uma única posição; fechamento na próxima virada do minuto"
     else:
      state["signal_status"]="Vela neutra ou sem margem disponível; aguardando próxima vela"
    save()
   except Exception as e:
    state["last_update"]=now(); state["errors"]=(state.get("errors",[])+[str(e)])[-5:]; state["last_action"]="Erro na cotação; veja a mensagem abaixo"; state["signal_status"]="Erro ao atualizar preço"; save()
threading.Thread(target=worker,daemon=True).start()
PAGE = r"""
<!doctype html><html lang="pt-br"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#201c35"><title>Kraken Paper Trader</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101018;color:#f4f3fa;font:16px system-ui,sans-serif}.wrap{max-width:850px;margin:auto;padding:18px}.top{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}.brand{font-size:22px;font-weight:800}.tag{background:#164b3b;color:#a4f3cf;padding:7px 10px;border-radius:999px;font-size:12px;font-weight:800}.sub,.label{color:#aaa7bd;font-size:12px;margin-top:5px}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:18px 0}.card{background:#1b1a27;border:1px solid #302d42;border-radius:16px;padding:15px;min-width:0}.val{font-size:22px;font-weight:750;margin-top:6px;overflow-wrap:anywhere}.buttons{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0}.btn{border:0;border-radius:12px;padding:13px 17px;font-weight:750;font-size:14px;background:#8264ff;color:white}.stop{background:#3a354c}.section{font-weight:750;margin:22px 0 10px}.trade{display:grid;grid-template-columns:70px 1fr 1fr;gap:8px;padding:11px 0;border-bottom:1px solid #302d42;font-size:12px}.buy{color:#6ce5b1}.sell{color:#ff8d9a}.foot{color:#8c899f;font-size:12px;line-height:1.5;margin-top:20px}.error{color:#ff9a9a;font-size:12px;margin-top:10px}@media(min-width:600px){.grid{grid-template-columns:repeat(4,minmax(0,1fr))}.val{font-size:24px}}
</style></head><body><main class="wrap"><div class="top"><div><div class="brand">Kraken Paper Trader</div><div class="sub">Operações em tempo real · acompanhamento de posições · dados públicos</div></div><div class="tag">SIMULAÇÃO · SEM DINHEIRO REAL</div></div>
<div class="grid"><div class="card"><div class="label">Patrimônio simulado</div><div class="val" id="equity">—</div><div class="sub">Capital inicial: <span id="initial">—</span></div></div><div class="card"><div class="label">Preço de mercado</div><div class="val" id="price">—</div></div><div class="card"><div class="label">P&L total</div><div class="val" id="pnl">—</div></div><div class="card"><div class="label">Estado do robô</div><div class="val" id="run">Parado</div></div></div>
<div class="card"><div class="label">Valor por operação (margem em USD)</div><input id="tradeAmount" type="number" min="5" max="100" step="5" value="10" onchange="setTradeAmount(this.value)" style="margin-top:8px;padding:12px;border-radius:10px;background:#29263a;color:#fff;border:1px solid #48415f;width:100%;font-size:16px"><div class="label" style="margin-top:12px">Take Profit (% da margem)</div><input id="tp" type="number" min="0.5" max="50" step="0.5" value="3" onchange="setRisk()" style="padding:10px;background:#29263a;color:#fff;width:100%"><div class="label" style="margin-top:12px">Stop Loss (% da margem)</div><input id="sl" type="number" min="0.5" max="50" step="0.5" value="2" onchange="setRisk()" style="padding:10px;background:#29263a;color:#fff;width:100%"><div class="label" style="margin-top:12px">Alavancagem (leverage) — apenas simulação</div><select id="leverage" onchange="setLeverage(this.value)" style="margin-top:8px;padding:12px;border-radius:10px;background:#29263a;color:#fff;border:1px solid #48415f;width:100%;font-size:16px"><option value="1">1x · Sem alavancagem</option><option value="2">2x</option><option value="3">3x</option><option value="5">5x</option><option value="10">10x</option><option value="15">15x</option><option value="20">20x</option></select><div class="sub">A alavancagem amplia ganhos e perdas. TP/SL são simulados e podem sofrer slippage em mercado real.</div></div><div class="buttons"><button class="btn" onclick="act('start')">Iniciar robô demo</button><button class="btn stop" onclick="act('stop')">Parar robô</button><button class="btn stop" onclick="act('reset')">Reiniciar saldo demo</button></div>
<div class="card"><div class="label">Última ação</div><div class="val" style="font-size:16px" id="action">Carregando…</div><div class="sub" id="updated"></div><div class="error" id="err"></div></div>
<div class="section">Posição aberta e evolução</div><div class="grid"><div class="card"><div class="label">Valor da posição</div><div class="val" id="position">—</div></div><div class="card"><div class="label">Lucro/prejuízo não realizado</div><div class="val" id="unrealized">—</div></div></div><div class="card"><div class="label">Gráfico de preço recente</div><svg id="chart" viewBox="0 0 600 150" style="width:100%;height:auto;margin-top:12px" role="img" aria-label="Gráfico do preço recente"><polyline points="" fill="none" stroke="#8b6cff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg><div class="sub">Amostras recebidas enquanto o robô está ligado.</div></div><div class="section">Histórico de ordens simuladas</div><div class="card" id="trades">Nenhuma ordem ainda.</div>
<div class="foot">O app consulta apenas cotações públicas e simula compras/vendas dentro do servidor. Não usa API Key e não envia ordens reais. Estratégia didática, sem garantia de lucro. Primeiro sinal após 21 amostras de preço.</div></main>
<script>
async function postSettings(path,data){let r=await fetch(path,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data)});let j=await r.json();if(!r.ok)alert(j.error||"Erro ao atualizar");refresh()}
async function setLeverage(v){postSettings("/api/leverage",{leverage:Number(v)})}
async function setTradeAmount(v){postSettings("/api/amount",{amount:Number(v)})}
async function setRisk(){postSettings("/api/risk",{take_profit_pct:Number(document.getElementById("tp").value),stop_loss_pct:Number(document.getElementById("sl").value)})}
const money=n=>Number(n||0).toLocaleString('en-US',{style:'currency',currency:'USD'});
async function refresh(){try{let r=await fetch('/api/state'),s=await r.json();let equity=s.cash+s.position_margin+s.asset*((s.last_price||s.avg_price||0)-(s.avg_price||0))*(s.position_side==="SHORT"?-1:1);document.getElementById("leverage").value=String(s.leverage||1);document.getElementById("tradeAmount").value=String(s.trade_amount||10);document.getElementById("tp").value=String(s.take_profit_pct||3);document.getElementById("sl").value=String(s.stop_loss_pct||2);document.getElementById('equity').textContent=money(equity);document.getElementById('initial').textContent=money(s.initial_cash);document.getElementById('price').textContent=s.last_price?money(s.last_price):'Aguardando';let pnl=equity-s.initial_cash,p=document.getElementById('pnl');p.textContent=(pnl>=0?'+':'')+money(pnl);p.style.color=pnl>=0?'#6ce5b1':'#ff8d9a';document.getElementById('run').textContent=s.running?'Rodando':'Parado';document.getElementById('position').textContent=money(s.asset*(s.last_price||s.avg_price||0));let upnl=s.asset*((s.last_price||s.avg_price||0)-(s.avg_price||0))*(s.position_side==="SHORT"?-1:1);let u=document.getElementById('unrealized');u.textContent=(upnl>=0?'+':'')+money(upnl);u.style.color=upnl>=0?'#6ce5b1':'#ff8d9a';let vals=s.prices||[];let line=document.querySelector('#chart polyline');if(vals.length>1){let lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1;line.setAttribute('points',vals.map((v,i)=>`${i*600/(vals.length-1)},${140-((v-lo)/span)*125}`).join(' '))}document.getElementById('action').textContent=s.last_action;document.getElementById('updated').textContent='Atualização: '+(s.last_update||'—')+' · '+s.symbol;document.getElementById('err').textContent=(s.errors||[]).slice(-1)[0]||'';let rows=(s.trades||[]).slice().reverse().slice(0,20);document.getElementById('trades').innerHTML=rows.length?rows.map(t=>`<div class="trade"><b class="${t.side==='BUY'?'buy':'sell'}">${t.side==='BUY'?'COMPRA':'VENDA'}</b><span>${new Date(t.time).toLocaleString()}</span><span>${money(t.price)}</span><span>Qtd. ${Number(t.qty).toFixed(6)}</span><span>${money(t.notional)}</span><span>${t.pnl===undefined?'':'P&L '+money(t.pnl)}</span></div>`).join(''):'Nenhuma operação ainda.'}catch(e){}}
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
  s=dict(state); s["equity"]=s["cash"]+s.get("position_margin",0)+s["asset"]*((s["last_price"] or s["avg_price"] or 0)-(s["avg_price"] or 0))*(1 if s.get("position_side","LONG")=="LONG" else -1); return jsonify(s)
@app.post("/api/leverage")
def set_leverage():
 from flask import request
 try: lev=int((request.get_json(silent=True) or {}).get("leverage",1))
 except Exception: return jsonify({"error":"Leverage inválido"}),400
 if lev not in (1,2,3,5,10,15,20): return jsonify({"error":"Escolha 1x, 2x, 3x, 5x, 10x, 15x ou 20x"}),400
 with LOCK:
  state["leverage"]=lev; state["last_action"]=f"Leverage definido para {lev}x (simulação)."; save(); return jsonify({"ok":True,"leverage":lev})
@app.post("/api/amount")
def set_amount():
 from flask import request
 try: amount=float((request.get_json(silent=True) or {}).get("amount",10))
 except Exception: return jsonify({"error":"Valor inválido"}),400
 if not 5 <= amount <= INITIAL: return jsonify({"error":f"Escolha entre US$ 5 e US$ {INITIAL:.0f}"}),400
 with LOCK:
  if state["asset"]>0: return jsonify({"error":"Feche a posição simulada antes de alterar o valor"}),400
  state["trade_amount"]=amount; save(); return jsonify({"ok":True,"amount":amount})
@app.post("/api/risk")
def set_risk():
 from flask import request
 data=request.get_json(silent=True) or {}
 try: tp=float(data.get("take_profit_pct",3)); sl=float(data.get("stop_loss_pct",2))
 except Exception: return jsonify({"error":"Percentuais inválidos"}),400
 if not 0.5 <= tp <= 50 or not 0.5 <= sl <= 50: return jsonify({"error":"TP e SL devem ficar entre 0,5% e 50% da margem"}),400
 with LOCK:
  state["take_profit_pct"]=tp; state["stop_loss_pct"]=sl; save(); return jsonify({"ok":True,"take_profit_pct":tp,"stop_loss_pct":sl})
@app.post("/api/start")
def start():
 with LOCK:
  state["running"]=True
  state["last_action"]="Robô iniciado em SIMULAÇÃO; aguardando o sinal da vela de 1 minuto."
  state["signal_status"]="Uma posição no máximo; fechamento ao fim da vela de 1 minuto"
  save(); return jsonify({"ok":True,"paper_only":True})
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
