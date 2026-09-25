#!/usr/bin/env bash
set -euo pipefail
rm -rf app
mkdir -p app
unzip -q ASTIE_DIESEL_completo.zip -d app

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

mkdir -p "$ROOT/public"
if [ -f "branding/ypf-agro-logo.png" ]; then
  cp "branding/ypf-agro-logo.png" "$ROOT/public/ypf-agro-logo.png"
fi

python3 - "$ROOT" "$API" <<'PY'
from pathlib import Path
import sys
root=Path(sys.argv[1]); api=sys.argv[2]

# API online + polling para la PWA.
p=root/"src/api/db.js"
s=p.read_text()
s=s.replace(
    'const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:3001";',
    f'const API_BASE = import.meta.env.VITE_API_URL || "{api}";'
)
if "class RealtimeBus" in s and "setInterval(poll,5000)" not in s:
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

# Sesión: usar la API de Supabase en producción.
p=root/"src/lib/session.jsx"
s=p.read_text()
s=s.replace(
    'const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:3001";',
    f'const API_BASE = import.meta.env.VITE_API_URL || "{api}";'
)
p.write_text(s)

# Segunda pasada visual: reemplazar acentos cálidos heredados por verde.
import subprocess
subprocess.run(
    ["bash","-lc", "find src -type f \\( -name '*.jsx' -o -name '*.js' -o -name '*.css' \\) -print0 | xargs -0 sed -i -E 's/(amber|yellow|orange)-([0-9]+)/emerald-\\2/g'"],
    cwd=root, check=True
)

# Logo en la pantalla de entrada.
entry=root/"src/pages/Entry.jsx"
if entry.exists():
    s=entry.read_text()
    needle='<div className="entry-page min-h-screen text-stone-900 flex flex-col">'
    repl=needle+'''
              <div className="pt-8 flex justify-center">
                <img src="/ypf-agro-logo.png" alt="YPF agro" className="w-40 h-24 object-contain" />
              </div>'''
    if needle in s and '/ypf-agro-logo.png' not in s:
        entry.write_text(s.replace(needle,repl,1))

# Identidad visual refinada: fondo blanco, negro suave, verde, bordes y estados de foco.
css=root/"src/index.css"
css.write_text(css.read_text()+'''
\n/* ASTIE DIESEL — segunda pasada visual YPF agro */
:root {
  --primary: 145 72% 38%;
  --primary-foreground: 0 0% 100%;
  --secondary: 145 24% 96%;
  --secondary-foreground: 150 35% 14%;
  --accent: 145 55% 94%;
  --accent-foreground: 145 72% 29%;
  --ring: 145 72% 38%;
  --border: 150 10% 88%;
  --input: 150 10% 84%;
}
html, body, #root { background: #fff !important; }
body { color: #171717 !important; }
input:focus, textarea:focus, select:focus {
  border-color: #16a34a !important;
  box-shadow: 0 0 0 3px rgba(22,163,74,.12) !important;
  outline: none !important;
}
button.bg-emerald-600, a.bg-emerald-600 {
  box-shadow: 0 5px 14px rgba(22,163,74,.16);
}
button.bg-emerald-600:hover, a.bg-emerald-600:hover {
  box-shadow: 0 7px 18px rgba(22,163,74,.22);
}
.rounded-xl, .rounded-2xl {
  box-shadow: 0 4px 18px rgba(15,23,42,.045);
}
::selection { background: rgb(22 163 74 / .18); color: rgb(20 83 45); }
::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-track { background: #f5f5f5; }
::-webkit-scrollbar-thumb { background: #d4d4d8; border-radius: 999px; }
::-webkit-scrollbar-thumb:hover { background: #16a34a; }
''')
PY

cd "$ROOT"
npm install --no-audit --no-fund
npm run build
