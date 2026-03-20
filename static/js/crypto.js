/**
 * FILMI — Client-side AES-256-GCM Encryption
 *
 * This is the ONLY JavaScript file with logic in the app.
 * Everything else is server-rendered HTML + CSS.
 *
 * How it works:
 *   Encryption key = PBKDF2(booth_code, fixed_salt, 100k iterations, SHA-256) → AES-256-GCM
 *   The booth code is the shared secret. Anyone with the code can decrypt photos.
 *   The server receives only ciphertext + IV — it cannot read your photos.
 */

const FilmiCrypto = (() => {
  const ENC = new TextEncoder();
  const SALT = ENC.encode('filmi-booth-key-v1');

  async function deriveKey(boothCode) {
    const raw = await crypto.subtle.importKey(
      'raw', ENC.encode(boothCode.toUpperCase()), { name: 'PBKDF2' }, false, ['deriveKey']
    );
    return crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: SALT, iterations: 100000, hash: 'SHA-256' },
      raw,
      { name: 'AES-GCM', length: 256 },
      false,
      ['encrypt', 'decrypt']
    );
  }

  /** Encrypt a File, returns { encryptedBlob, ivB64 } */
  async function encryptFile(file, boothCode) {
    const key = await deriveKey(boothCode);
    const iv  = crypto.getRandomValues(new Uint8Array(12));
    const plain = await file.arrayBuffer();
    const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, plain);
    // Prepend 32-byte mime type so we can reconstruct the blob on decrypt
    const mime = (file.type || 'image/jpeg').padEnd(32).slice(0, 32);
    const mimeBytes = ENC.encode(mime);
    const combined = new Uint8Array(mimeBytes.length + cipher.byteLength);
    combined.set(mimeBytes, 0);
    combined.set(new Uint8Array(cipher), mimeBytes.length);
    return {
      encryptedBlob: new Blob([combined], { type: 'application/octet-stream' }),
      ivB64: btoa(String.fromCharCode(...iv)),
    };
  }

  /** Fetch an encrypted blob URL, decrypt it, return an object URL (or null on failure) */
  async function decryptUrl(encryptedUrl, boothCode, ivB64) {
    const key = await deriveKey(boothCode);
    const iv  = new Uint8Array(atob(ivB64).split('').map(c => c.charCodeAt(0)));
    const buf = await (await fetch(encryptedUrl)).arrayBuffer();
    const mime = new TextDecoder().decode(buf.slice(0, 32)).trim();
    try {
      const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv }, key, buf.slice(32));
      return URL.createObjectURL(new Blob([plain], { type: mime }));
    } catch {
      return null;
    }
  }

  return { encryptFile, decryptUrl };
})();