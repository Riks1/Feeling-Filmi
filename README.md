# Feeling-Filmi


> *snap. share. stay filmi.*

A private, end-to-end encrypted photo booth app for your people. Create a booth, drop the code, and share moments that only your crew can see -cause the server literally cannot read your photos.

Built with love (and a lot of neon) by **Haarika**.

---

## ✦ what it does

| feature | vibe |
|---|---|
| 🔐 **E2E Encryption** | Photos are encrypted in your browser with AES-256-GCM before they ever leave your device. The server stores only ciphertext. |
| 📸 **Photo Booths** | Create a private booth and invite people with a 6-character code. |
| 💬 **Comments** | Drop a comment on any photo. |
| 🔥 **Reactions** | React with emojis  |
| 🔖 **Personal Gallery** | Save your favourite shots to your own in-app gallery. |
| 📋 **Activity Feed** | See who joined, uploaded, liked, and reacted — live on every booth page. |
| ⭐ **Cover Photos** | Booth creators can pin any photo as the booth's cover card. |
| 🎨 **The Aesthetic** | Dark & moody, neon-on-black, desi baddie energy |

---

## ✦ how the encryption works

```
your photo
    ↓
Browser derives AES-256-GCM key
from booth code via PBKDF2
(100,000 iterations, SHA-256)
    ↓
Photo encrypted client-side
with a random IV
    ↓
Only ciphertext + IV
sent to server
    ↓
Server stores an opaque .bin blob
— it cannot read your photos
    ↓
Viewer's browser re-derives
the same key from the booth code
and decrypts locally
```

The **booth code is the shared secret**. Anyone who has it can decrypt photos — which is exactly the right model for a private group photo booth.

---

## ✦ tech stack

```
Backend   →  Python + Flask + SQLite (sqlite3, no ORM)
Frontend  →  Jinja2 templates + vanilla CSS + minimal JS
Crypto    →  Web Crypto API (AES-256-GCM, PBKDF2) — browser-native, no libraries
Fonts     →  Palatino, Georgia, Trebuchet MS — system fonts, no CDN needed
```


## ✦ getting started

**1. Install dependencies**
```bash
pip install flask werkzeug gunicorn
```

**2. Run locally**
```bash
cd filmi2
python app.py
```

Open `http://localhost:5000` — the database is created automatically on first run.



