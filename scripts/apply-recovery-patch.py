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
