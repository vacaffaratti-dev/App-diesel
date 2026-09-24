#!/usr/bin/env python3
from pathlib import Path
import sys
root = Path(sys.argv[1])

p = root / "server/src/routes/auth.js"
s = p.read_text()
if "function recoveryCodeMatches" not in s:
    needle = '''function validatePassword(password) {
  return typeof password === "string" && password.length >= MIN_PASSWORD_LENGTH && password.length <= 256;
}
'''
    insert = '''function validatePassword(password) {
  return typeof password === "string" && password.length >= MIN_PASSWORD_LENGTH && password.length <= 256;
}

function recoveryCodeMatches(provided) {
  const configured = process.env.ASTIE_RECOVERY_CODE;
  if (typeof configured !== "string" || configured.length < 12 || typeof provided !== "string") return false;
  const a = Buffer.from(provided, "utf8");
  const b = Buffer.from(configured, "utf8");
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}
'''
    s = s.replace(needle, insert)
if 'router.post("/reset-setup"' not in s:
    reset = '''// Recuperación administrativa protegida por ASTIE_RECOVERY_CODE en el servidor.
router.post("/reset-setup", async (req, res, next) => {
  try {
    const { recoveryCode, admin, seller, storeName } = req.body || {};
    if (!recoveryCodeMatches(recoveryCode)) return res.status(401).json({ error: "Código de recuperación inválido" });
    if (!validatePassword(admin) || !validatePassword(seller)) return res.status(422).json({ error: "Las contraseñas deben tener entre " + MIN_PASSWORD_LENGTH + " y 256 caracteres" });
    if (admin === seller) return res.status(422).json({ error: "Usa contraseñas distintas para admin y vendedores" });
    const s = await getSettings();
    const data = {
      store_name: String(storeName || s?.store_name || "ASTIE DIESEL").slice(0, 120),
      admin_password_hash: await hashPassword(admin),
      seller_password_hash: await hashPassword(seller),
    };
    const result = s ? await db.entities.AppSettings.update(s.id, data) : await db.entities.AppSettings.create(data);
    revokeStaffTokens("admin");
    revokeStaffTokens("seller");
    res.json({ ok: true, store_name: result.store_name });
  } catch (err) { next(err); }
});

'''
    s = s.replace('router.post("/verify", async (req, res, next) => {', reset + 'router.post("/verify", async (req, res, next) => {')
p.write_text(s)

p = root / "server/src/server.js"
s = p.read_text().replace('["/verify", "/setup", "/customer"]', '["/verify", "/setup", "/reset-setup", "/customer"]')
p.write_text(s)

p = root / "src/lib/settingsService.js"
s = p.read_text()
if "resetInitialSetup" not in s:
    s += '''
export async function resetInitialSetup({ recoveryCode, admin, seller, storeName = "ASTIE DIESEL" }) {
  return apiFetch("POST", "/api/auth/reset-setup", { recoveryCode, admin, seller, storeName });
}
'''
p.write_text(s)

p = root / "src/pages/Entry.jsx"
s = p.read_text()
s = s.replace('import { isSetupComplete, setupMasterPasswords } from "@/lib/settingsService";', 'import { isSetupComplete, setupMasterPasswords, resetInitialSetup } from "@/lib/settingsService";')
if 'const [recovery, setRecovery]' not in s:
    s = s.replace('const [setup, setSetup] = useState({ admin: "", admin2: "", seller: "", seller2: "" });', 'const [setup, setSetup] = useState({ admin: "", admin2: "", seller: "", seller2: "" });\n  const [recovery, setRecovery] = useState({ code: "", admin: "", admin2: "", seller: "", seller2: "" });')
if 'const submitReset = async' not in s:
    s = s.replace('  const submitSetup = async (e) => {', '''  const submitReset = async (e) => {
    e.preventDefault();
    setError("");
    if (recovery.code.length < 12) return setError("El código de recuperación no es válido");
    if (recovery.admin.length < 8 || recovery.seller.length < 8) return setError("Las contraseñas deben tener al menos 8 caracteres");
    if (recovery.admin !== recovery.admin2 || recovery.seller !== recovery.seller2) return setError("La confirmación no coincide");
    if (recovery.admin === recovery.seller) return setError("Usa una contraseña distinta para vendedores");
    setLoading(true);
    try {
      await resetInitialSetup({ recoveryCode: recovery.code, admin: recovery.admin, seller: recovery.seller });
      await loginStaff(recovery.admin, "admin");
      setNeedsSetup(false);
      navigate("/admin");
    } catch (err) {
      setError(err.message || "No se pudo restablecer la configuración");
    } finally {
      setLoading(false);
    }
  };

  const submitSetup = async (e) => {''')
if 'mode === "reset"' not in s:
    marker = '        {mode === "login" && !needsSetup && ('
    block = '''        {mode === "reset" && (
          <div className="entry-card w-full max-w-sm p-8">
            <button onClick={() => { setMode("login"); setError(""); }} className="text-sm text-stone-500 hover:text-emerald-700 mb-6">← Volver</button>
            <h2 className="font-display text-2xl font-semibold mb-1">Restablecer configuración</h2>
            <p className="text-stone-500 text-sm mb-6">Usa el código de recuperación configurado en el servidor. Este proceso no borra clientes, productos ni cotizaciones.</p>
            <form onSubmit={submitReset} className="space-y-4">
              <div><Label className="text-stone-700">Código de recuperación</Label><Input value={recovery.code} onChange={(e) => setRecovery({ ...recovery, code: e.target.value })} type="password" autoFocus /></div>
              <div><Label className="text-stone-700">Nueva contraseña de administrador</Label><Input value={recovery.admin} onChange={(e) => setRecovery({ ...recovery, admin: e.target.value })} type="password" /></div>
              <div><Label className="text-stone-700">Repetir contraseña de administrador</Label><Input value={recovery.admin2} onChange={(e) => setRecovery({ ...recovery, admin2: e.target.value })} type="password" /></div>
              <div><Label className="text-stone-700">Nueva contraseña de vendedores</Label><Input value={recovery.seller} onChange={(e) => setRecovery({ ...recovery, seller: e.target.value })} type="password" /></div>
              <div><Label className="text-stone-700">Repetir contraseña de vendedores</Label><Input value={recovery.seller2} onChange={(e) => setRecovery({ ...recovery, seller2: e.target.value })} type="password" /></div>
              {error && <p className="text-red-600 text-sm">{error}</p>}
              <Button type="submit" disabled={loading} className="w-full green-button">{loading ? "Restableciendo..." : "Restablecer y entrar"}</Button>
            </form>
          </div>
        )}

'''
    s = s.replace(marker, block + marker)
if "Restablecer configuración inicial" not in s:
    s = s.replace('            <div className="flex gap-2 mt-4 text-xs">', '            <button type="button" onClick={() => { setMode("reset"); setError(""); }} className="w-full mt-4 text-xs text-stone-500 hover:text-emerald-700 underline">¿No puedes ingresar? Restablecer configuración inicial</button>\n            <div className="flex gap-2 mt-4 text-xs">', 1)
p.write_text(s)

p = root / "README.md"
s = p.read_text()
if "ASTIE_RECOVERY_CODE" not in s:
    s += '''
## Recuperación segura de credenciales

La app no incluye una contraseña maestra universal. Configura ASTIE_RECOVERY_CODE en el entorno del backend con un código largo y secreto (mínimo 12 caracteres). Desde la pantalla de acceso, usa "¿No puedes ingresar? Restablecer configuración inicial" para establecer nuevas contraseñas de administrador y vendedores. El proceso no borra clientes, productos ni cotizaciones y revoca las sesiones anteriores.
'''
p.write_text(s)

# MODO 100% LOCAL PARA ANDROID.
LOCAL_DB = "import { SCHEMA } from \"@/api/schema\";\nconst P=\"astie_local_v2:\", A=\"astie_auth_headers\"; let auth={}; const subs={};\nconst id=()=>crypto.randomUUID?.() || (Date.now()+\"-\"+Math.random().toString(36).slice(2));\nconst now=()=>new Date().toISOString();\nconst get=(k,d=[])=>{try{return JSON.parse(localStorage.getItem(P+k)||JSON.stringify(d))}catch{return d}}; const put=(k,v)=>localStorage.setItem(P+k,JSON.stringify(v));\nconst settings=()=>get(\"settings\",null); const saveSettings=v=>put(\"settings\",v);\nconst hash=async(p,s=id())=>{const k=await crypto.subtle.importKey(\"raw\",new TextEncoder().encode(p),\"PBKDF2\",false,[\"deriveBits\"]);const b=await crypto.subtle.deriveBits({name:\"PBKDF2\",salt:new TextEncoder().encode(s),iterations:150000,hash:\"SHA-256\"},k,256);return s+\":\"+[...new Uint8Array(b)].map(x=>x.toString(16).padStart(2,\"0\")).join(\"\")};\nconst check=async(p,h)=>{if(!h)return false;const s=h.split(\":\")[0];return await hash(p,s)===h};\nconst recovery=()=>{const b=new Uint8Array(18);crypto.getRandomValues(b);return [...b].map(x=>x.toString(16).padStart(2,\"0\")).join(\"\").match(/.{1,6}/g).join(\"-\").toUpperCase()};\nexport function setAuthHeaders(h){auth={...h}}; export function clearAuthHeaders(){auth={}}; export function storeFor(){return localStorage};\ntry{const x=localStorage.getItem(A);if(x)auth=JSON.parse(x)}catch{} export function persistAuthHeaders(h){auth={...h};localStorage.setItem(A,JSON.stringify(h))}; export function dropAuthHeaders(){auth={};localStorage.removeItem(A)};\nconst role=()=>auth[\"x-astie-role\"]; const cid=()=>auth[\"x-astie-id\"];\nconst allowedRead=(n,r)=>!!r&&((n!==\"AppSettings\")||r===\"admin\"); const allowedWrite=(n,r)=>r===\"admin\"||((r===\"seller\")&&[\"Quote\",\"Message\",\"Customer\"].includes(n))||((r===\"customer\")&&[\"Quote\",\"Message\",\"Customer\"].includes(n));\nconst visible=(n,rows,r)=>{if(r===\"customer\"&&n===\"Customer\")return rows.filter(x=>x.id===cid());if(r===\"customer\"&&n===\"Quote\")return rows.filter(x=>x.customer_id===cid());if(r===\"customer\"&&n===\"Message\"){const qs=get(\"Quote\").filter(q=>q.customer_id===cid()).map(q=>q.id);return rows.filter(x=>qs.includes(x.quote_id))}return rows};\nconst emit=(n,e)=>{(subs[n]||[]).forEach(f=>f(e));const q=e?.data?.quote_id;if(q)(subs[n+\":\"+q]||[]).forEach(f=>f(e))};\nconst filt=(rows,f={})=>rows.filter(r=>Object.entries(f).every(([k,v])=>{if(v&&typeof v===\"object\"&&!Array.isArray(v))return Object.entries(v).every(([op,a])=>({$eq:r[k]===a,$ne:r[k]!==a,$gt:r[k]>a,$gte:r[k]>=a,$lt:r[k]<a,$lte:r[k]<=a,$in:Array.isArray(a)&&a.includes(r[k]),$nin:Array.isArray(a)&&!a.includes(r[k])}[op]));return String(r[k]??\"\")===String(v??\"\")}));\nasync function list(n,sort,limit,skip,filters){const r=role();if(!allowedRead(n,r))throw Object.assign(new Error(\"No autorizado\"),{status:403});let rows=n===\"AppSettings\"?(settings()?[{...settings(),id:\"settings\"}]:[]):visible(n,get(n),r);if(filters)rows=filt(rows,filters);if(sort){const d=String(sort).startsWith(\"-\"),k=String(sort).replace(/^-/, \"\");rows.sort((a,b)=>(d?-1:1)*((a[k]??\"\")<(b[k]??\"\")?-1:(a[k]??\"\")>(b[k]??\"\")?1:0))}const st=Number(skip)||0;return rows.slice(st,limit?st+Number(limit):undefined)}\nasync function create(n,data){const r=role();if(!allowedWrite(n,r))throw Object.assign(new Error(\"No autorizado\"),{status:403});const sc=SCHEMA[n];for(const k of sc?.required||[])if(data[k]==null||data[k]===\"\")throw new Error(\"Falta \"+k);const row={...(sc?.defaults||{}),...data,id:data.id||id(),created_date:now(),updated_date:now()};const rows=get(n);rows.push(row);put(n,rows);emit(n,{id:row.id,type:\"create\",data:row});return row}\nasync function update(n,i,data){const r=role();if(!allowedWrite(n,r))throw Object.assign(new Error(\"No autorizado\"),{status:403});if(n===\"AppSettings\"&&r===\"admin\"){const s={...(settings()||{}),...data,id:\"settings\",updated_date:now()};saveSettings(s);return s}const rows=get(n),j=rows.findIndex(x=>x.id===i);if(j<0)throw Object.assign(new Error(\"No encontrado\"),{status:404});if(r===\"customer\"&&((n===\"Customer\"&&i!==cid())||(n===\"Quote\"&&rows[j].customer_id!==cid())||n===\"Message\"))throw Object.assign(new Error(\"No autorizado\"),{status:403});const row={...rows[j],...data,id:i,updated_date:now()};rows[j]=row;put(n,rows);emit(n,{id:i,type:\"update\",data:row});return row}\nasync function del(n,i){if(role()!==\"admin\")throw Object.assign(new Error(\"Solo administrador\"),{status:403});put(n,get(n).filter(x=>x.id!==i));return{ok:true}}\nasync function imp(n,rows,replace){if(role()!==\"admin\")throw Object.assign(new Error(\"Solo administrador\"),{status:403});const out=(replace?[]:get(n)).concat((rows||[]).map(x=>({...x,id:x.id||id(),created_date:x.created_date||now(),updated_date:now()})));put(n,out);return out}\nexport async function apiFetch(m,path,b){\nif(path===\"/api/auth/setup-done\")return{done:!!settings()?.admin_password_hash};\nif(path===\"/api/auth/setup\"){if(settings()?.admin_password_hash)throw Object.assign(new Error(\"La configuración ya existe\"),{status:409});if(!b?.admin||!b?.seller||b.admin.length<8||b.seller.length<8||b.admin===b.seller)throw new Error(\"Contraseñas no válidas\");const rc=recovery();saveSettings({store_name:b.storeName||\"ASTIE DIESEL\",admin_password_hash:await hash(b.admin),seller_password_hash:await hash(b.seller),recovery_code_hash:await hash(rc),created_date:now(),updated_date:now()});return{ok:true,recoveryCode:rc}}\nif(path===\"/api/auth/verify\"){const s=settings(),rr=b?.role,h=rr===\"admin\"?s?.admin_password_hash:s?.seller_password_hash;if(!s||!await check(b?.password||\"\",h))throw Object.assign(new Error(\"Contraseña incorrecta\"),{status:401});return{ok:true,token:id(),role:rr,name:rr===\"admin\"?\"Administrador\":\"Vendedor\"}}\nif(path===\"/api/auth/change-password\"){if(role()!==\"admin\")throw Object.assign(new Error(\"Solo administrador\"),{status:403});const s=settings();const k=b.role+\"_password_hash\";saveSettings({...s,[k]:await hash(b.newPassword),updated_date:now()});return{ok:true}}\nif(path===\"/api/auth/reset-setup\"){const s=settings();if(!s||!await check(b?.recoveryCode||\"\",s.recovery_code_hash))throw Object.assign(new Error(\"Código de recuperación incorrecto\"),{status:401});if(!b?.admin||!b?.seller||b.admin.length<8||b.seller.length<8||b.admin===b.seller)throw new Error(\"Contraseñas no válidas\");saveSettings({...s,admin_password_hash:await hash(b.admin),seller_password_hash:await hash(b.seller),updated_date:now()});return{ok:true}}\nif(path===\"/api/auth/customer\"){const phone=String(b?.phone||\"\").trim();if(!phone)throw new Error(\"El teléfono es obligatorio\");let rows=get(\"Customer\"),c=rows.find(x=>x.phone===phone);if(!c){c={...(SCHEMA.Customer.defaults||{}),...b,phone,id:id(),created_date:now(),updated_date:now()};rows.push(c)}else c={...c,...b,phone,updated_date:now()};put(\"Customer\",rows);return{customer:c}}\nconst x=path.match(/^\\/api\\/([^/?]+)(?:\\/([^/?]+))?/),n=x?.[1],i=x?.[2];if(!SCHEMA[n])throw Object.assign(new Error(\"Ruta no encontrada\"),{status:404});if(m===\"GET\")return i?((await list(n)).find(x=>x.id===i)||null):list(n);if(m===\"POST\"&&path.endsWith(\"/import\"))return imp(n,b?.rows,b?.replace);if(m===\"POST\")return create(n,b||{});if(m===\"PUT\")return update(n,i,b||{});if(m===\"DELETE\")return del(n,i);throw Object.assign(new Error(\"Ruta no encontrada\"),{status:404})}\nconst entity=n=>({list:(s,l,k)=>list(n,s,l,k),filter:(f,s,l,k)=>list(n,s,l,k,f),get:async i=>(await list(n)).find(x=>x.id===i)||null,create:d=>create(n,d),update:(i,d)=>update(n,i,d),delete:i=>del(n,i),importRows:(r,o={})=>imp(n,r,o.replace),subscribe:(q,cb)=>{const f=typeof q===\"string\"?cb:q,k=typeof q===\"string\"?n+\":\"+q:n;(subs[k]||=[]).push(f);return()=>{subs[k]=(subs[k]||[]).filter(x=>x!==f)}}});\nexport const db={entities:Object.fromEntries(Object.keys(SCHEMA).map(n=>[n,entity(n)]))};\n"
import base64, zlib
PAYLOAD_src_lib_session_jsx = "eNqdVU1P4zAQvfdXzEZ7cKTQ3imgRWzZTy0rymWFEJhk0lokcWU7bVHIf9+JY4eEgFhtTvZ45vm9mfFE5BupDFwij00EFcQKucEzWRjck6HUg/XS0KFdLdIUY+fAs+yexw9QQ6pkDoFqwIL5RLTYFWxQaaHNaWnWX5EntIsgUXIzMPCNOEcTryPQRio8l6oD/DSjw1lyT5iTWBbawBK1FrJw3OB4yJsVZZaFc+97dXF5+mVx+2PxhxwDro3AW90CNIi4tzTTsogNmTz2byW3gqgxSspaZInCAuoQqglAi3vtMIgwGhd0Qzf4PHkWnX8meSKKlfX/2a4H/kaVSP4U0CWYsRCOT+ylAEY9upWHVHxHAJmMebakpPEVTldovhnMWU+15dB8IgVGIWGPMPu+vPg13XCl0R453xpiTrWAqrbbZ8Is5ZlG61VHcH3T8m3ZuDK3knxXMKZ7EnoXa3dVX1VDkNwHgvRYUASWtTaKGIn0kWI6jUj0hgAKc7nFN5IyEDpSlMmVKM5Kasgc1QtdXD8WMbDYnX7mhveEtvHUOj64pnC+48J0jc6CwLY3p8cw8+5kHQDPe6Dr9sUQXgXB/sD284GSGQaHEPQAujOR0Ik/mIoE6hZu/CyZww4HDvQCGvghukgGmBEUPCeXu49VZ02p/28bcw09a0akrBWeniAI6rsplTFnYQSbtSywh2r3WEDORdYz233U9P5hL72OskJTqqKz+z51SsbFpZeXpq9XdsO13klF0hr1o9omVJd/qukWFfVo0EzXBoh0OuCO9Pt1bQM7q5EPWJC54TC1m/+sqS+bBbJFqcN3cibL0Qtvc/NypLNw3t3WjsJXYF29joYDfeqHL2x5VuJxVUE3bLspOnicUa+ckadZ1yeVn9310eyNO07mk3r8F2imsptU/aEfm71T7341Q1CbvGaKfSDHEMxayR0UuIOFUlKx4BkVcmIO99hgJbATZi1Gv57AwvmWNvuG6F+J+pNv";
PAYLOAD_src_lib_settingsService_js = "eNq1k01vm0AQhu/+FVNOi4RxKvVUZKlJ6laW+hHJuUWRtYbBrAS7aHepayH+e2cX4+A0cXzJCdiZeeeZ4V1R1UpbaCHbRMBr8Q1tWkAHuVYVBF9mdDTLNkEymeBfn8nNXqaQNzK1QkkQZoW2qW9VVZdokYXQTgBSJY0XVRJJbA58x4U96rPg++I+iCDw8ryxxcw4lanLD8KEFDR9awk3SpXIJXMBOu9ew/DlP7mxqO+4MTulM8Na4FklZETRskRNT6s0/uIVElFwvbpfLuDrcrFa/Aig68EPbZ9A736vXiKlozPq3Ruop6BM04wR1IfPi0HSgsstToc6j9RLSdwN4p+Puuep/qAW+f4CMKv3bvRn//N/ul5wBDXmGMazusEEOucY7nzHUGtqAyL3r7Gx3DYG5vM5fLr6GA5lOS8N1dlCqx1QnpN4dbIt2uu6JpdaIbeGjaag52BV6gGsHyrbxCitsAJNPCqMS2EsC8OHq8fEFzrGD+bIJJuyTMaKPHc2ayGOYwNdH8rQXRIfi7171sNW1gU3RXKS0PvqXIbGVNGe9+tUZdjHfZsDkstxB91hu+0J67mdaSSXLiUtgZf+fjNX2ze7pV7Ru9ws33X6dL8u7Nj7+h8rlZ8Q";
PAYLOAD_src_pages_Entry_jsx = "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";
PAYLOAD__env_android = "eNoVykEKgzAQBdC9p/gg3RY9gtAsAlKK2m4lxB8IxBlI0tIreY5eTPrWr8UwL9bgZs1sRoS3+KjisBFB8+7Qd90FSb1LoIAJlel3BBW9Ni3uCqFnidXhZRezDg+7PqcRElGYP3HTDH4r8/+fc9oj8g==";
for rel,payload in [("src/lib/session.jsx",PAYLOAD_src_lib_session_jsx),("src/lib/settingsService.js",PAYLOAD_src_lib_settingsService_js),("src/pages/Entry.jsx",PAYLOAD_src_pages_Entry_jsx),(".env.android",PAYLOAD__env_android)]: out=root/rel; out.parent.mkdir(parents=True,exist_ok=True); out.write_bytes(zlib.decompress(base64.b64decode(payload)))
(root/"src/api/db.js").write_text(LOCAL_DB)
