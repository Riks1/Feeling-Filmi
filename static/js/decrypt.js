/**
 * decrypt.js — decrypts photos on gallery page.
 * Depends on crypto.js (FilmiCrypto).
 */
(async () => {
  const imgs = document.querySelectorAll('img.encrypted-photo');
  for (const img of imgs) {
    const encSrc   = img.dataset.src;
    const iv        = img.dataset.iv;
    const boothCode = img.dataset.boothCode;
    if (!encSrc || !iv || !boothCode) continue;
    img.closest('.photo-card')?.classList.add('decrypting');
    const url = await FilmiCrypto.decryptUrl(encSrc, boothCode, iv);
    if (url) {
      img.src = url;
      img.closest('.photo-card')?.classList.remove('decrypting');
      img.style.cursor = 'pointer';
      img.addEventListener('click', () => {
        const lb = document.createElement('div');
        lb.className = 'lightbox';
        lb.innerHTML = `<div class="lightbox-inner"><button class="lightbox-close">✕</button><img src="${url}" /></div>`;
        lb.querySelector('.lightbox-close').onclick = () => lb.remove();
        lb.onclick = e => { if (e.target === lb) lb.remove(); };
        document.body.appendChild(lb);
      });
    } else {
      img.closest('.photo-card')?.classList.add('decrypt-error');
    }
  }
})();