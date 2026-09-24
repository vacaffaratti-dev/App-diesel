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
# Reemplaza la capa HTTP por almacenamiento local y elimina la dependencia del backend.
import base64, zlib

PAYLOAD_src_api_db_js = "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"
PAYLOAD_src_lib_session_jsx = "eNqdVU1P4zAQvfdXzEZ7cKTQ3imgRWzZTy0rymWFEJhk0lokcWU7bVHIf9+JY4eEgFhtTvZ45vm9mfFE5BupDFwij00EFcQKucEzWRjck6HUg/XS0KFdLdIUY+fAs+yexw9QQ6pkDoFqwIL5RLTYFWxQaaHNaWnWX5EntIsgUXIzMPCNOEcTryPQRio8l6oD/DSjw1lyT5iTWBbawBK1FrJw3OB4yJsVZZaFc+97dXF5+mVx+2PxhxwDro3AW90CNIi4tzTTsogNmTz2byW3gqgxSspaZInCAuoQqglAi3vtMIgwGhd0Qzf4PHkWnX8meSKKlfX/2a4H/kaVSP4U0CWYsRCOT+ylAEY9upWHVHxHAJmMebakpPEVTldovhnMWU+15dB8IgVGIWGPMPu+vPg13XCl0R453xpiTrWAqrbbZ8Is5ZlG61VHcH3T8m3ZuDK3knxXMKZ7EnoXa3dVX1VDkNwHgvRYUASWtTaKGIn0kWI6jUj0hgAKc7nFN5IyEDpSlMmVKM5Kasgc1QtdXD8WMbDYnX7mhveEtvHUOj64pnC+48J0jc6C3xfLqyCCwLY3p8cw8+5kHQDPe6Dr9sUQXgXB/sD284GSGQaHEPQAujOR0Ik/mIoE6hZu/CyZww4HDvQCGvghukgGmBEUPCeXu49VZ02p/28bcw09a0akrBWeniAI6rsplTFnYQSbtSywh2r3WEDORdYz233U9P5hL72OskJTqqKz+z51SsbFpZeXpq9XdsO13klF0hr1o9omVJd/qukWFfVo0EzXBoh0OuCO9Pt1bQM7q5EPWJC54TC1m/+sqS+bBbJFqcN3cibL0Qtvc/NypLNw3t3WjsJXYF29joYDfeqHL2x5VuJxVUE3bLspOnicUa+ckadZ1yeVn9310eyNO07mk3r8F2imsptU/aEfm71T7341Q1CbvGaKfSDHEMxayR0UuIOFUlKx4BkVcmIO99hgJbATZi1Gv57AwvmWNvuG6F+J+pNv"
PAYLOAD_src_lib_settingsService_js = "eNq1k01vm0AQhu/+FVNOi4RxKvVUZKlJ6laW+hHJuUWRtYbBrAS7aHepayH+e2cX4+A0cXzJCdiZeeeZ4V1R1UpbaCHbRMBr8Q1tWkAHuVYVBF9mdDTLNkEymeBfn8nNXqaQNzK1QkkQZoW2qW9VVZdokYXQTgBSJY0XVRJJbA58x4U96rPg++I+iCDw8ryxxcw4lanLD8KEFDR9awk3SpXIJXMBOu9ew/DlP7mxqO+4MTulM8Na4FklZETRskRNT6s0/uIVElFwvbpfLuDrcrFa/Aig68EPbZ9A736vXiKlozPq3Ruop6BM04wR1IfPi0HSgsstToc6j9RLSdwN4p+Puuep/qAW+f4CMKv3bvRn//N/ul5wBDXmGMazusEEOucY7nzHUGtqAyL3r7Gx3DYG5vM5fLr6GA5lOS8N1dlCqx1QnpN4dbIt2uu6JpdaIbeGjaag52BV6gGsHyrbxCitsAJNPCqMS2EsC8OHq8fEFzrGD+bIJJuyTMaKPHc2ayGOYwNdH8rQXRIfi7171sNW1gU3RXKS0PvqXIbGVNGe9+tUZdjHfZsDkstxB91hu+0J67mdaSSXLiUtgZf+fjNX2ze7pV7Ru9ws33X6dL8u7Nj7+h8rlZ8Q"
PAYLOAD_src_pages_Entry_jsx = "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"
PAYLOAD_src_lib_session_jsx = "eNqdVU1P4zAQvfdXzEZ7cKTQ3imgRWzZTy0rymWFEJhk0lokcWU7bVHIf9+JY4eEgFhtTvZ45vm9mfFE5BupDFwij00EFcQKucEzWRjck6HUg/XS0KFdLdIUY+fAs+yexw9QQ6pkDoFqwIL5RLTYFWxQaaHNaWnWX5EntIsgUXIzMPCNOEcTryPQRio8l6oD/DSjw1lyT5iTWBbawBK1FrJw3OB4yJsVZZaFc+97dXF5+mVx+2PxhxwDro3AW90CNIi4tzTTsogNmTz2byW3gqgxSspaZInCAuoQqglAi3vtMIgwGhd0Qzf4PHkWnX8meSKKlfX/2a4H/kaVSP4U0CWYsRCOT+ylAEY9upWHVHxHAJmMebakpPEVTldovhnMWU+15dB8IgVGIWGPMPu+vPg13XCl0R453xpiTrWAqrbbZ8Is5ZlG61VHcH3T8m3ZuDK3knxXMKZ7EnoXa3dVX1VDkNwHgvRYUASWtTaKGIn0kWI6jUj0hgAKc7nFN5IyEDpSlMmVKM5Kasgc1QtdXD8WMbDYnX7mhveEtvHUOj64pnC+48J0jc6Hys6J0jc6C3xfLqyCCwLY3p8cw8+5kHQDPe6Dr9sUQXgXB/sD284GSGQaHEPQAujOR0Ik/mIoE6hZu/CyZww4HDvQCGvghukgGmBEUPCeXu49VZ02p/28bcw09a0akrBWeniAI6rsplTFnYQSbtSywh2r3WEDORdYz233U9P5hL72OskJTqqKz+z51SsbFpZeXpq9XdsO13klF0hr1o9omVJd/qukWFfVo0EzXBoh0OuCO9Pt1bQM7q5EPWJC54TC1m/+sqS+bBbJFqcN3cibL0Qtvc/NypLNw3t3WjsJXYF29joYDfeqHL2x5VuJxVUE3bLspOnicUa+ckadZ1yeVn9310eyNO07mk3r8F2imsptU/aEfm71T7341Q1CbvGaKfSDHEMxayR0UuIOFUlKx4BkVcmIO99hgJbATZi1Gv57AwvmWNvuG6F+J+pNv"
PAYLOAD_src_lib_settingsService_js = "eNq1k01vm0AQhu/+FVNOi4RxKvVUZKlJ6laW+hHJuUWRtYbBrAS7aHepayH+e2cX4+A0cXzJCdiZeeeZ4V1R1UpbaCHbRMBr8Q1tWkAHuVYVBF9mdDTLNkEymeBfn8nNXqaQNzK1QkkQZoW2qW9VVZdokYXQTgBSJY0XVRJJbA58x4U96rPg++I+iCDw8ryxxcw4lanLD8KEFDR9awk3SpXIJXMBOu9ew/DlP7mxqO+4MTulM8Na4FklZETRskRNT6s0/uIVElFwvbpfLuDrcrFa/Aig68EPbZ9A736vXiKlozPq3Ruop6BM04wR1IfPi0HSgsstToc6j9RLSdwN4p+Puuep/qAW+f4CMKv3bvRn//N/ul5wBDXmGMazusEEOucY7nzHUGtqAyL3r7Gx3DYG5vM5fLr6GA5lOS8N1dlCqx1QnpN4dbIt2uu6JpdaIbeGjaag52BV6gGsHyrbxCitsAJNPCqMS2EsC8OHq8fEFzrGD+bIJJuyTMaKPHc2ayGOYwNdH8rQXRIfi7171sNW1gU3RXKS0PvqXIbGVNGe9+tUZdjHfZsDkstxB91hu+0J67mdaSSXLiUtgZf+fjNX2ze7pV7Ru9ws33X6dL8u7Nj7+h8rlZ8Q"
PAYLOAD_src_pages_Entry_jsx = "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"
PAYLOAD__env_android = "eNoVykEKgzAQBdC9p/gg3RY9gtAsAlKK2m4lxB8IxBlI0tIreY5eTPrWr8UwL9bgZs1sRoS3+KjisBFB8+7Qd90FSb1LoIAJlel3BBW9Ni3uCqFnidXhZRezDg+7PqcRElGYP3HTDH4r8/+fc9oj8g=="

for rel, payload in {
    "src/api/db.js": PAYLOAD_src_api_db_js,
    "src/lib/session.jsx": PAYLOAD_src_lib_session_jsx,
    "src/lib/settingsService.js": PAYLOAD_src_lib_settingsService_js,
    "src/pages/Entry.jsx": PAYLOAD_src_pages_Entry_jsx,
    ".env.android": PAYLOAD__env_android,
}.items():
    out = root / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(zlib.decompress(base64.b64decode(payload)))
