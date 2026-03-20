import os, uuid, random, string, sqlite3
os.chdir(os.path.dirname(os.path.abspath(__file__)))
from flask import (Flask, render_template, request, redirect,
                   url_for, session, flash, send_from_directory, g)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__,
            template_folder=os.path.join(BASE_DIR, 'templates'),
            static_folder=os.path.join(BASE_DIR, 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'takes-a-village')
app.config['DATABASE']    = os.path.join(BASE_DIR, 'filmi.db')
app.config['UPLOAD_FOLDER'] = os.path.join(BASE_DIR, 'static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

REACTIONS = ['🔥', '😭', '💀', '💖', '✨', '😍']

# ── DATABASE ────────────────────────────────────────────────────
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys=ON")
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS user (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at    TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS booth (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            code        TEXT UNIQUE NOT NULL,
            creator_id  INTEGER NOT NULL REFERENCES user(id),
            cover_photo_id INTEGER,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS booth_member (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            booth_id  INTEGER NOT NULL REFERENCES booth(id) ON DELETE CASCADE,
            user_id   INTEGER NOT NULL REFERENCES user(id),
            joined_at TEXT DEFAULT (datetime('now')),
            UNIQUE(booth_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS photo (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            booth_id     INTEGER NOT NULL REFERENCES booth(id) ON DELETE CASCADE,
            uploader_id  INTEGER NOT NULL REFERENCES user(id),
            filename     TEXT NOT NULL,
            iv           TEXT NOT NULL,
            caption      TEXT,
            uploaded_at  TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS likes (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
            user_id  INTEGER NOT NULL REFERENCES user(id),
            UNIQUE(photo_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS reaction (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id  INTEGER NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
            user_id   INTEGER NOT NULL REFERENCES user(id),
            emoji     TEXT NOT NULL,
            UNIQUE(photo_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS comment (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id   INTEGER NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES user(id),
            text       TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS saved_photo (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL REFERENCES photo(id) ON DELETE CASCADE,
            user_id  INTEGER NOT NULL REFERENCES user(id),
            saved_at TEXT DEFAULT (datetime('now')),
            UNIQUE(photo_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS activity (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            booth_id   INTEGER NOT NULL REFERENCES booth(id) ON DELETE CASCADE,
            user_id    INTEGER NOT NULL REFERENCES user(id),
            kind       TEXT NOT NULL,
            detail     TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
    """)
    db.commit()

# ── HELPERS ─────────────────────────────────────────────────────
def gen_code():
    db = get_db()
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not db.execute("SELECT 1 FROM booth WHERE code=?", (code,)).fetchone():
            return code

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            flash('Sign in to continue.', 'error')
            return redirect(url_for('landing'))
        return f(*args, **kwargs)
    return decorated

def member_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        db = get_db()
        booth_id = kwargs.get('booth_id')
        if not db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                          (booth_id, session['user_id'])).fetchone():
            flash('You are not a member of this booth.', 'error')
            return redirect(url_for('booths'))
        return f(*args, **kwargs)
    return decorated

def current_user():
    if 'user_id' not in session: return None
    db = get_db()
    return db.execute("SELECT id, username FROM user WHERE id=?", (session['user_id'],)).fetchone()

def log_activity(booth_id, user_id, kind, detail=None):
    db = get_db()
    db.execute("INSERT INTO activity (booth_id, user_id, kind, detail) VALUES (?,?,?,?)",
               (booth_id, user_id, kind, detail))
    db.commit()

app.jinja_env.globals['current_user'] = current_user
app.jinja_env.globals['REACTIONS'] = REACTIONS

# ── AUTH ────────────────────────────────────────────────────────
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'error')
        elif len(password) < 6:
            flash('Password must be at least 6 characters.', 'error')
        else:
            db = get_db()
            if db.execute("SELECT 1 FROM user WHERE username=?", (username,)).fetchone():
                flash('Username already taken.', 'error')
            else:
                db.execute("INSERT INTO user (username, password_hash) VALUES (?,?)",
                           (username, generate_password_hash(password)))
                db.commit()
                user = db.execute("SELECT id FROM user WHERE username=?", (username,)).fetchone()
                session['user_id'] = user['id']
                flash(f'Welcome to FILMI, @{username}!', 'success')
                return redirect(url_for('booths'))
    return render_template('auth.html', mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        db = get_db()
        user = db.execute("SELECT * FROM user WHERE username=?", (username,)).fetchone()
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid username or password.', 'error')
        else:
            session['user_id'] = user['id']
            return redirect(url_for('booths'))
    return render_template('auth.html', mode='login')

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('landing'))

# ── PAGES ────────────────────────────────────────────────────────
@app.route('/')
def landing():
    if 'user_id' in session: return redirect(url_for('booths'))
    return render_template('landing.html')

@app.route('/booths')
@login_required
def booths():
    db = get_db()
    user_id = session['user_id']
    rows = db.execute("""
        SELECT b.id, b.name, b.code, b.created_at, b.cover_photo_id,
               u.username AS creator,
               (SELECT COUNT(*) FROM photo    WHERE booth_id=b.id) AS photo_count,
               (SELECT COUNT(*) FROM booth_member WHERE booth_id=b.id) AS member_count
        FROM booth b
        JOIN booth_member bm ON b.id=bm.booth_id
        JOIN user u ON b.creator_id=u.id
        WHERE bm.user_id=?
        ORDER BY b.created_at DESC
    """, (user_id,)).fetchall()

    # For each booth with a cover, get its filename+iv
    booths_data = []
    for b in rows:
        cover = None
        if b['cover_photo_id']:
            cr = db.execute("SELECT filename, iv FROM photo WHERE id=?",
                            (b['cover_photo_id'],)).fetchone()
            if cr:
                cover = {'filename': cr['filename'], 'iv': cr['iv']}
        booths_data.append({
            'booth': {
                'id': b['id'], 'name': b['name'], 'code': b['code'],
                'creator': b['creator'], 'photo_count': b['photo_count'],
                'member_count': b['member_count'],
            },
            'cover': cover,
        })
    return render_template('booths.html', booths=booths_data)

@app.route('/booths/new', methods=['GET', 'POST'])
@login_required
def create_booth():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Booth name is required.', 'error')
        elif len(name) > 60:
            flash('Name too long (max 60 chars).', 'error')
        else:
            db = get_db()
            code = gen_code()
            db.execute("INSERT INTO booth (name, code, creator_id) VALUES (?,?,?)",
                       (name, code, session['user_id']))
            db.commit()
            booth = db.execute("SELECT id FROM booth WHERE code=?", (code,)).fetchone()
            db.execute("INSERT INTO booth_member (booth_id, user_id) VALUES (?,?)",
                       (booth['id'], session['user_id']))
            db.commit()
            log_activity(booth['id'], session['user_id'], 'created', f'Created booth "{name}"')
            flash(f'Booth created! Share code: {code}', 'success')
            return redirect(url_for('booth_detail', booth_id=booth['id']))
    return render_template('booth_form.html', action='create')

@app.route('/booths/join', methods=['GET', 'POST'])
@login_required
def join_booth():
    if request.method == 'POST':
        code = request.form.get('code', '').strip().upper()
        db = get_db()
        booth = db.execute("SELECT * FROM booth WHERE code=?", (code,)).fetchone()
        if not booth:
            flash('Invalid booth code.', 'error')
        else:
            existing = db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                                  (booth['id'], session['user_id'])).fetchone()
            if not existing:
                db.execute("INSERT INTO booth_member (booth_id, user_id) VALUES (?,?)",
                           (booth['id'], session['user_id']))
                db.commit()
                u = current_user()
                log_activity(booth['id'], session['user_id'], 'joined', f'@{u["username"]} joined')
            flash(f'Joined "{booth["name"]}"!', 'success')
            return redirect(url_for('booth_detail', booth_id=booth['id']))
    return render_template('booth_form.html', action='join')

@app.route('/booths/<int:booth_id>')
@login_required
@member_required
def booth_detail(booth_id):
    db = get_db()
    user_id = session['user_id']
    booth = db.execute("""
        SELECT b.*, u.username AS creator FROM booth b
        JOIN user u ON b.creator_id=u.id WHERE b.id=?
    """, (booth_id,)).fetchone()

    photos_rows = db.execute("""
        SELECT p.id, p.filename, p.iv, p.uploaded_at, p.caption, u.username AS uploader,
               (SELECT COUNT(*) FROM likes WHERE photo_id=p.id) AS like_count,
               EXISTS(SELECT 1 FROM likes WHERE photo_id=p.id AND user_id=?) AS liked,
               EXISTS(SELECT 1 FROM saved_photo WHERE photo_id=p.id AND user_id=?) AS saved
        FROM photo p JOIN user u ON p.uploader_id=u.id
        WHERE p.booth_id=? ORDER BY p.uploaded_at DESC
    """, (user_id, user_id, booth_id)).fetchall()

    photos = []
    for p in photos_rows:
        comments = db.execute("""
            SELECT c.id, c.text, c.created_at, u.username, c.user_id
            FROM comment c JOIN user u ON c.user_id=u.id
            WHERE c.photo_id=? ORDER BY c.created_at ASC
        """, (p['id'],)).fetchall()

        # Reactions: group by emoji with counts
        reaction_rows = db.execute("""
            SELECT emoji, COUNT(*) as count
            FROM reaction WHERE photo_id=? GROUP BY emoji
        """, (p['id'],)).fetchall()
        my_reaction = db.execute(
            "SELECT emoji FROM reaction WHERE photo_id=? AND user_id=?", (p['id'], user_id)
        ).fetchone()

        photos.append({
            'photo': p,
            'comments': comments,
            'reactions': reaction_rows,
            'my_reaction': my_reaction['emoji'] if my_reaction else None,
        })

    members = db.execute("""
        SELECT u.username FROM booth_member bm
        JOIN user u ON bm.user_id=u.id WHERE bm.booth_id=?
        ORDER BY bm.joined_at ASC
    """, (booth_id,)).fetchall()

    # Activity feed — last 20 events
    activity = db.execute("""
        SELECT a.kind, a.detail, a.created_at, u.username
        FROM activity a JOIN user u ON a.user_id=u.id
        WHERE a.booth_id=? ORDER BY a.created_at DESC LIMIT 20
    """, (booth_id,)).fetchall()

    member_count = len(members)
    is_creator = booth['creator_id'] == user_id

    return render_template('booth_detail.html',
                           booth=booth, photos=photos,
                           member_count=member_count,
                           members=members,
                           activity=activity,
                           booth_code=booth['code'],
                           current_user_id=user_id,
                           is_creator=is_creator)

# ── PHOTOS ──────────────────────────────────────────────────────
@app.route('/booths/<int:booth_id>/upload', methods=['POST'])
@login_required
@member_required
def upload_photo(booth_id):
    iv      = request.form.get('iv', '')
    caption = request.form.get('caption', '').strip()[:200]
    set_cover = request.form.get('set_cover') == '1'
    file    = request.files.get('file')
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('booth_detail', booth_id=booth_id))
    if not iv:
        flash('Encryption data missing.', 'error')
        return redirect(url_for('booth_detail', booth_id=booth_id))
    ext = os.path.splitext(secure_filename(file.filename))[1] or '.bin'
    filename = f"{uuid.uuid4().hex}{ext}"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    db = get_db()
    db.execute("INSERT INTO photo (booth_id, uploader_id, filename, iv, caption) VALUES (?,?,?,?,?)",
               (booth_id, session['user_id'], filename, iv, caption or None))
    db.commit()
    photo = db.execute("SELECT id FROM photo WHERE filename=?", (filename,)).fetchone()
    if set_cover:
        db.execute("UPDATE booth SET cover_photo_id=? WHERE id=?", (photo['id'], booth_id))
        db.commit()
    u = current_user()
    log_activity(booth_id, session['user_id'], 'uploaded', f'@{u["username"]} uploaded a photo')
    flash('Photo uploaded!', 'success')
    return redirect(url_for('booth_detail', booth_id=booth_id))

@app.route('/booths/<int:booth_id>/set_cover/<int:photo_id>', methods=['POST'])
@login_required
@member_required
def set_cover(booth_id, photo_id):
    db = get_db()
    db.execute("UPDATE booth SET cover_photo_id=? WHERE id=?", (photo_id, booth_id))
    db.commit()
    flash('Cover photo updated!', 'success')
    return redirect(url_for('booth_detail', booth_id=booth_id))

@app.route('/photos/<int:photo_id>/like', methods=['POST'])
@login_required
def like_photo(photo_id):
    db = get_db()
    photo = db.execute("SELECT * FROM photo WHERE id=?", (photo_id,)).fetchone()
    if not photo: return redirect(url_for('booths'))
    if not db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                      (photo['booth_id'], session['user_id'])).fetchone():
        flash('Access denied.', 'error')
        return redirect(url_for('booths'))
    existing = db.execute("SELECT 1 FROM likes WHERE photo_id=? AND user_id=?",
                          (photo_id, session['user_id'])).fetchone()
    if existing:
        db.execute("DELETE FROM likes WHERE photo_id=? AND user_id=?", (photo_id, session['user_id']))
    else:
        db.execute("INSERT INTO likes (photo_id, user_id) VALUES (?,?)", (photo_id, session['user_id']))
        u = current_user()
        log_activity(photo['booth_id'], session['user_id'], 'liked', f'@{u["username"]} liked a photo')
    db.commit()
    return redirect(request.referrer or url_for('booth_detail', booth_id=photo['booth_id']))

@app.route('/photos/<int:photo_id>/react', methods=['POST'])
@login_required
def react_photo(photo_id):
    emoji = request.form.get('emoji', '')
    if emoji not in REACTIONS:
        return redirect(request.referrer or url_for('booths'))
    db = get_db()
    photo = db.execute("SELECT * FROM photo WHERE id=?", (photo_id,)).fetchone()
    if not photo: return redirect(url_for('booths'))
    if not db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                      (photo['booth_id'], session['user_id'])).fetchone():
        return redirect(url_for('booths'))
    existing = db.execute("SELECT emoji FROM reaction WHERE photo_id=? AND user_id=?",
                          (photo_id, session['user_id'])).fetchone()
    if existing:
        if existing['emoji'] == emoji:
            # Same emoji — remove it (toggle off)
            db.execute("DELETE FROM reaction WHERE photo_id=? AND user_id=?", (photo_id, session['user_id']))
        else:
            # Different emoji — switch it
            db.execute("UPDATE reaction SET emoji=? WHERE photo_id=? AND user_id=?",
                       (emoji, photo_id, session['user_id']))
    else:
        db.execute("INSERT INTO reaction (photo_id, user_id, emoji) VALUES (?,?,?)",
                   (photo_id, session['user_id'], emoji))
        u = current_user()
        log_activity(photo['booth_id'], session['user_id'], 'reacted',
                     f'@{u["username"]} reacted {emoji}')
    db.commit()
    return redirect(request.referrer or url_for('booth_detail', booth_id=photo['booth_id']))

@app.route('/photos/<int:photo_id>/save', methods=['POST'])
@login_required
def save_photo(photo_id):
    db = get_db()
    photo = db.execute("SELECT * FROM photo WHERE id=?", (photo_id,)).fetchone()
    if not photo: return redirect(url_for('booths'))
    if not db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                      (photo['booth_id'], session['user_id'])).fetchone():
        return redirect(url_for('booths'))
    existing = db.execute("SELECT 1 FROM saved_photo WHERE photo_id=? AND user_id=?",
                          (photo_id, session['user_id'])).fetchone()
    if existing:
        db.execute("DELETE FROM saved_photo WHERE photo_id=? AND user_id=?", (photo_id, session['user_id']))
        flash('Removed from gallery.', 'success')
    else:
        db.execute("INSERT INTO saved_photo (photo_id, user_id) VALUES (?,?)", (photo_id, session['user_id']))
        flash('Saved to gallery!', 'success')
    db.commit()
    return redirect(request.referrer or url_for('booth_detail', booth_id=photo['booth_id']))

# ── COMMENTS ────────────────────────────────────────────────────
@app.route('/photos/<int:photo_id>/comment', methods=['POST'])
@login_required
def add_comment(photo_id):
    db = get_db()
    photo = db.execute("SELECT * FROM photo WHERE id=?", (photo_id,)).fetchone()
    if not photo: return redirect(url_for('booths'))
    if not db.execute("SELECT 1 FROM booth_member WHERE booth_id=? AND user_id=?",
                      (photo['booth_id'], session['user_id'])).fetchone():
        return redirect(url_for('booths'))
    text = request.form.get('text', '').strip()
    if text and len(text) <= 300:
        db.execute("INSERT INTO comment (photo_id, user_id, text) VALUES (?,?,?)",
                   (photo_id, session['user_id'], text))
        u = current_user()
        log_activity(photo['booth_id'], session['user_id'], 'commented',
                     f'@{u["username"]} commented')
        db.commit()
    return redirect(request.referrer or url_for('booth_detail', booth_id=photo['booth_id']))

@app.route('/comments/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    db = get_db()
    comment = db.execute("SELECT * FROM comment WHERE id=?", (comment_id,)).fetchone()
    if comment and comment['user_id'] == session['user_id']:
        db.execute("DELETE FROM comment WHERE id=?", (comment_id,))
        db.commit()
    return redirect(request.referrer or url_for('booths'))

# ── GALLERY ──────────────────────────────────────────────────────
@app.route('/gallery')
@login_required
def gallery():
    db = get_db()
    user_id = session['user_id']
    photos = db.execute("""
        SELECT p.id, p.filename, p.iv, p.uploaded_at, p.caption,
               u.username AS uploader, b.name AS booth_name,
               b.id AS booth_id, b.code AS booth_code,
               (SELECT COUNT(*) FROM likes WHERE photo_id=p.id) AS like_count,
               EXISTS(SELECT 1 FROM likes WHERE photo_id=p.id AND user_id=?) AS liked
        FROM saved_photo sp
        JOIN photo p ON sp.photo_id=p.id
        JOIN user u ON p.uploader_id=u.id
        JOIN booth b ON p.booth_id=b.id
        WHERE sp.user_id=? ORDER BY sp.saved_at DESC
    """, (user_id, user_id)).fetchall()
    return render_template('gallery.html', photos=photos)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ── ERROR HANDLERS ───────────────────────────────────────────────
@app.errorhandler(413)
def too_large(e):
    return render_template('413.html'), 413

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(port=5000, use_reloader=False)