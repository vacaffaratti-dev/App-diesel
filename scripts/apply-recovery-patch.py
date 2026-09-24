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
LOCAL_SESSION = "import React, { createContext, useContext, useState, useEffect, useCallback } from \"react\";\nimport { persistAuthHeaders, dropAuthHeaders, apiFetch } from \"@/api/db\";\nconst SessionContext=createContext(null), STORAGE_KEY=\"astie_session\";\nexport function SessionProvider({children}){\n const [session,setSession]=useState(null),[loading,setLoading]=useState(true);\n useEffect(()=>{try{const x=localStorage.getItem(STORAGE_KEY);if(x)setSession(JSON.parse(x))}catch{}setLoading(false)},[]);\n const persist=useCallback(s=>{setSession(s);try{s?localStorage.setItem(STORAGE_KEY,JSON.stringify(s)):localStorage.removeItem(STORAGE_KEY)}catch{}},[]);\n const loginCustomer=useCallback(async data=>{const {customer}=await apiFetch(\"POST\",\"/api/auth/customer\",data);persistAuthHeaders({\"x-astie-role\":\"customer\",\"x-astie-id\":customer.id});persist({role:\"customer\",id:customer.id,name:(customer.full_name+\" \"+(customer.last_name||\"\")).trim(),phone:customer.phone,email:customer.email,raw:customer});return customer},[persist]);\n const loginStaff=useCallback(async(password,role)=>{const data=await apiFetch(\"POST\",\"/api/auth/verify\",{role,password});persistAuthHeaders({\"x-astie-role\":role,\"x-astie-token\":data.token});persist({role,name:data.name})},[persist]);\n const logout=useCallback(()=>{dropAuthHeaders();persist(null)},[persist]);\n return <SessionContext.Provider value={{session,loading,loginCustomer,loginStaff,logout}}>{children}</SessionContext.Provider>;\n}\nexport function useSession(){const ctx=useContext(SessionContext);if(!ctx)throw new Error(\"useSession must be used within SessionProvider\");return ctx}\n"
LOCAL_SETTINGS = "import { db, apiFetch } from \"@/api/db\";\nexport async function isSetupComplete(){return Boolean((await apiFetch(\"GET\",\"/api/auth/setup-done\")).done)}\nexport async function setupMasterPasswords({admin,seller,storeName=\"ASTIE DIESEL\"}){return apiFetch(\"POST\",\"/api/auth/setup\",{admin,seller,storeName})}\nexport async function setMasterPassword(role,password){return apiFetch(\"POST\",\"/api/auth/change-password\",{role,newPassword:password})}\nexport async function verifyMasterPassword(role,password){try{await apiFetch(\"POST\",\"/api/auth/verify\",{role,password});return true}catch(e){if(e.status===401)return false;throw e}}\nexport async function getAppSettings(){try{const s=(await db.entities.AppSettings.list())[0];if(!s)return null;const x={...s};delete x.admin_password_hash;delete x.seller_password_hash;delete x.recovery_code_hash;return x}catch{return null}}\nexport async function resetInitialSetup({recoveryCode,admin,seller,storeName=\"ASTIE DIESEL\"}){return apiFetch(\"POST\",\"/api/auth/reset-setup\",{recoveryCode,admin,seller,storeName})}\n"
(root/"src/api/db.js").write_text(LOCAL_DB)
(root/"src/lib/session.jsx").write_text(LOCAL_SESSION)
(root/"src/lib/settingsService.js").write_text(LOCAL_SETTINGS)
(root/".env.android").write_text("")
