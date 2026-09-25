#!/usr/bin/env bash
set -euo pipefail
rm -rf app
mkdir -p app
unzip -q ASTIE_DIESEL_completo.zip -d app

# El ZIP contiene también un package.json dentro de server/.
# Buscamos explícitamente el package de la app Vite mediante su API frontend.
DB_FILE="$(find app -type f -path '*/src/api/db.js' -print -quit)"
if [ -z "$DB_FILE" ]; then
  echo "No se encontró src/api/db.js dentro del proyecto"
  find app -maxdepth 4 -type f -name package.json -print
  exit 1
fi
ROOT="$(dirname "$(dirname "$(dirname "$DB_FILE")")")"
if [ ! -f "$ROOT/package.json" ] || [ ! -f "$ROOT/index.html" ]; then
  echo "No se pudo identificar la raíz de la app Vite: $ROOT"
  exit 1
fi

API="https://xyggsdkxjsemvjjlveey.supabase.co/functions/v1/astie-api"

# Identidad visual: blanco + negro + verde YPF Agro.
mkdir -p "$ROOT/public"
if [ -f "branding/ypf-agro-logo.png" ]; then
  cp "branding/ypf-agro-logo.png" "$ROOT/public/ypf-agro-logo.png"
fi
python3 - "$ROOT" "$API" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); api=sys.argv[2]
for rel in ["src/api/db.js","src/lib/session.jsx"]:
    p=root/rel
    s=p.read_text()
    s=s.replace(
        'const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:3001";',
        f'const API_BASE = import.meta.env.VITE_API_URL || "{api}";'
    )
    if rel=="src/api/db.js":
        s=s.replace('const WS_BASE  = API_BASE.replace(/^http/, "ws");','')
        a=s.index("class RealtimeBus {")
        b=s.index("// ── Fábrica de entidades",a)
        s=s[:a]+"""class RealtimeBus {
  constructor(){ this._timers=new Map(); }
  reset(){ for(const t of this._timers.values()) clearInterval(t); this._timers.clear(); }
  subscribe(entity, quoteId, callback){
    const key=quoteId ? entity+":"+quoteId : entity;
    let last="";
    const poll=async()=>{
      try{
        const path=quoteId ? "/api/"+entity+"/"+quoteId : "/api/"+entity+"?sort=-updated_date&limit=50";
        const data=await apiFetch("GET",path); const sig=JSON.stringify(data);
        if(last && sig!==last) callback({type:"data-changed",data});
        last=sig;
      }catch{}
    };
    poll();
    const timer=setInterval(poll,5000);
    this._timers.set(key,timer);
    return ()=>{clearInterval(timer);this._timers.delete(key);};
  }
}
const bus=new RealtimeBus();

"""+s[b:]
    p.write_text(s)
PY

cd "$ROOT"
npm install --no-audit --no-fund
npm run build
