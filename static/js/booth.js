/**
 * booth.js — upload encryption + photo decryption for booth_detail page.
 * Depends on crypto.js (FilmiCrypto).
 */

const form       = document.getElementById('upload-form');
const fileInput  = document.getElementById('file-input');
const ivField    = document.getElementById('iv-field');
const uploadBtn  = document.getElementById('upload-btn');
const previewEl  = document.getElementById('upload-preview');
const previewImg = document.getElementById('preview-img');
const statusEl   = document.getElementById('upload-status');
const zone       = document.getElementById('upload-zone');

// Show preview when file selected
fileInput.addEventListener('change', () => {
  const file = fileInput.files[0];
  if (!file) return;
  previewImg.src = URL.createObjectURL(file);
  previewEl.style.display = 'flex';
  uploadBtn.style.display = 'block';
  statusEl.textContent = 'Ready — click Upload Photo to encrypt & send';
});

// Drag-and-drop
zone.addEventListener('dragover',  e => { e.preventDefault(); zone.classList.add('drag-over'); });
zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
zone.addEventListener('drop', e => {
  e.preventDefault();
  zone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('image/')) {
    const dt = new DataTransfer();
    dt.items.add(file);
    fileInput.files = dt.files;
    fileInput.dispatchEvent(new Event('change'));
  }
});

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;

  // Get booth code from the form's data attribute
  const boothCode = form.dataset.boothCode;

  if (!boothCode) { alert('Booth code not found — cannot encrypt.'); return; }

  statusEl.textContent = 'Encrypting…';
  uploadBtn.disabled = true;

  try {
    const { encryptedBlob, ivB64 } = await FilmiCrypto.encryptFile(file, boothCode);
    ivField.value = ivB64;

    const encrypted = new File([encryptedBlob], file.name.replace(/\.\w+$/, '.bin'), {
      type: 'application/octet-stream',
    });
    const dt = new DataTransfer();
    dt.items.add(encrypted);
    fileInput.files = dt.files;

    statusEl.textContent = 'Uploading…';
    form.submit();
  } catch (err) {
    statusEl.textContent = 'Encryption failed: ' + err.message;
    uploadBtn.disabled = false;
  }
});

/* Decrypt photos on page */
decryptVisiblePhotos();

async function decryptVisiblePhotos() {
  const imgs = document.querySelectorAll('img.encrypted-photo');
  for (const img of imgs) {
    const { src: encSrc, iv, boothCode } = img.dataset;
    if (!encSrc || !iv || !boothCode) continue;
    img.closest('.photo-card')?.classList.add('decrypting');
    const url = await FilmiCrypto.decryptUrl(encSrc, boothCode, iv);
    if (url) {
      img.src = url;
      img.closest('.photo-card')?.classList.remove('decrypting');
      img.style.cursor = 'pointer';
      img.addEventListener('click', () => openLightbox(url));
    } else {
      img.closest('.photo-card')?.classList.add('decrypt-error');
    }
  }
}

function openLightbox(url) {
  const lb = document.createElement('div');
  lb.className = 'lightbox';
  lb.innerHTML = `<div class="lightbox-inner"><button class="lightbox-close">✕</button><img src="${url}" /></div>`;
  lb.querySelector('.lightbox-close').onclick = () => lb.remove();
  lb.onclick = e => { if (e.target === lb) lb.remove(); };
  document.body.appendChild(lb);
}