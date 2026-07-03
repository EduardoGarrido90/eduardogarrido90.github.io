/* DL course static vault — client-side AES-GCM decryption.
   Content is stored encrypted; it is only readable with the section password.
   Format of every .enc file:  iv(12 bytes) || ciphertext+tag.
   The key is PBKDF2-SHA256(password, salt, iters) -> AES-GCM 256.
   The salt + iteration count are per-section (embedded in the page config). */
(function (global) {
  "use strict";

  function b64ToBytes(b64) {
    const bin = atob(b64);
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }

  async function deriveKey(password, saltB64, iters) {
    const salt = b64ToBytes(saltB64);
    const base = await crypto.subtle.importKey(
      "raw", new TextEncoder().encode(password), "PBKDF2", false, ["deriveKey"]);
    return crypto.subtle.deriveKey(
      { name: "PBKDF2", salt, iterations: iters, hash: "SHA-256" },
      base, { name: "AES-GCM", length: 256 }, false, ["decrypt"]);
  }

  async function decryptBytes(bytes, key) {
    const iv = bytes.slice(0, 12);
    const ct = bytes.slice(12);
    return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv }, key, ct));
  }

  // Verify a password by decrypting the section check token.
  // Returns the CryptoKey on success, throws on wrong password.
  async function verify(password, cfg) {
    const key = await deriveKey(password, cfg.salt, cfg.iters);
    const token = await decryptBytes(b64ToBytes(cfg.check), key); // throws (OperationError) if wrong
    if (new TextDecoder().decode(token) !== "unlock-ok") throw new Error("bad-token");
    return key;
  }

  // ---- modal viewer ----
  function ensureModal() {
    let m = document.getElementById("vault-modal");
    if (m) return m;
    m = document.createElement("div");
    m.id = "vault-modal";
    m.innerHTML =
      '<div class="bar"><span class="vt"></span>' +
      '<a class="dl" download>Descargar</a>' +
      '<button class="cl">Cerrar &times;</button></div>' +
      '<div class="stage"></div>';
    document.body.appendChild(m);
    m.querySelector(".cl").addEventListener("click", closeModal);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeModal();
    });
    return m;
  }

  let currentUrl = null;
  function closeModal() {
    const m = document.getElementById("vault-modal");
    if (!m) return;
    m.classList.remove("on");
    m.querySelector(".stage").innerHTML = "";
    if (currentUrl) { URL.revokeObjectURL(currentUrl); currentUrl = null; }
  }

  async function open(item, key) {
    const resp = await fetch(item.file);
    if (!resp.ok) throw new Error("fetch failed: " + item.file);
    const enc = new Uint8Array(await resp.arrayBuffer());
    const plain = await decryptBytes(enc, key);
    const m = ensureModal();
    const stage = m.querySelector(".stage");
    const dl = m.querySelector(".dl");
    m.querySelector(".vt").textContent = item.title;
    stage.innerHTML = "";

    if (item.type === "pdf") {
      const blob = new Blob([plain], { type: "application/pdf" });
      currentUrl = URL.createObjectURL(blob);
      const f = document.createElement("iframe");
      f.src = currentUrl;
      stage.appendChild(f);
      dl.style.display = "";
      dl.href = currentUrl;
      dl.setAttribute("download", (item.download || item.title).replace(/[^\w.-]+/g, "_") + ".pdf");
    } else { // html fragment
      const txt = new TextDecoder().decode(plain);
      const wrap = document.createElement("div");
      wrap.className = "htmlbody";
      wrap.innerHTML = txt;
      stage.appendChild(wrap);
      stage.scrollTop = 0;
      dl.style.display = "none";
    }
    m.classList.add("on");
  }

  global.DLVault = { verify, open };
})(window);
