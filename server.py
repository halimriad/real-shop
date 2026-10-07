#!/usr/bin/env python3
"""
متجر حقيقي + نظام مستخدمين + ربط ديسكورد
"""
import json, sqlite3, os, urllib.request, urllib.parse, base64, hashlib, secrets, time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")
DISCORD_API = "https://discord.com/api/v10"

def get_redirect_uri():
    manual = os.environ.get("DISCORD_REDIRECT_URI")
    if manual: return manual
    render_url = os.environ.get("RENDER_EXTERNAL_URL")
    if render_url: return render_url.rstrip("/") + "/api/discord/callback"
    return f"http://localhost:{os.environ.get('PORT','8080')}/api/discord/callback"

DISCORD_REDIRECT_URI = get_redirect_uri()
DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "shop.db"))

def hash_password(password, salt=None):
    if salt is None: salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return salt, h.hex()

def check_password(password, salt, hashed):
    _, new_hash = hash_password(password, salt)
    return new_hash == hashed

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, price REAL NOT NULL,
        description TEXT, image TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, items TEXT NOT NULL,
        total REAL NOT NULL, customer_name TEXT, customer_phone TEXT,
        status TEXT DEFAULT 'pending', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS discord_link (
        id INTEGER PRIMARY KEY CHECK (id = 1), access_token TEXT, refresh_token TEXT,
        user_id TEXT, username TEXT, global_name TEXT, avatar TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, username TEXT NOT NULL,
        password_salt TEXT NOT NULL, password_hash TEXT NOT NULL, avatar TEXT,
        display_name TEXT, is_verified INTEGER DEFAULT 0, verify_code TEXT,
        verify_expires REAL, token TEXT, token_expires REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        defaults = [
            ("سماعة بلوتوث لاسلكية", 149, "سماعة عالية الجودة مع صوت نقي وبطارية تدوم 20 ساعة", ""),
            ("ساعة ذكية رياضية", 299, "تتبع اللياقة ومعدل ضربات القلب ومقاومة للماء", ""),
            ("شاحن لاسلكي سريع", 79, "شحن سريع 15 واط متوافق مع معظم الهواتف", ""),
            ("حافظة هاتف فاخرة", 45, "حماية قوية وتصميم أنيق بعدة ألوان", ""),
        ]
        c.executemany("INSERT INTO products (name, price, description, image) VALUES (?,?,?,?)", defaults)
    conn.commit(); conn.close()
    print("✅ قاعدة البيانات جاهزة")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def discord_request(method, endpoint, token=None, data=None):
    url = DISCORD_API + endpoint
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    if body: headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            content = resp.read().decode()
            return (json.loads(content) if content else {}), resp.status
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        try: return json.loads(err), e.code
        except: return {"message": err}, e.code
    except Exception as e:
        return {"message": str(e)}, 500

class ShopHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(os.path.dirname(__file__), "public"), **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Key, X-User-Token")
        self.end_headers()

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def check_admin(self):
        return self.headers.get("X-Admin-Key", "") == ADMIN_PASSWORD

    def get_user_from_token(self):
        token = self.headers.get("X-User-Token", "")
        if not token: return None
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE token=? AND token_expires > ?", (token, time.time())).fetchone()
        conn.close()
        return dict(row) if row else None

    def refresh_discord_token(self):
        """Refresh the Discord access token using the stored refresh_token."""
        conn = get_db()
        row = conn.execute("SELECT refresh_token FROM discord_link WHERE id=1").fetchone()
        if not row or not row["refresh_token"]:
            conn.close()
            return None
        refresh_token = row["refresh_token"]
        conn.close()
        basic = base64.b64encode(f"{DISCORD_CLIENT_ID}:{DISCORD_CLIENT_SECRET}".encode()).decode()
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }).encode()
        req = urllib.request.Request(
            "https://discord.com/api/oauth2/token",
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {basic}",
                "User-Agent": "ShopBot/1.0"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode())
            access_token = token_data.get("access_token")
            new_refresh = token_data.get("refresh_token", refresh_token)
            if access_token:
                conn = get_db()
                conn.execute(
                    "UPDATE discord_link SET access_token=?, refresh_token=?, updated_at=CURRENT_TIMESTAMP WHERE id=1",
                    (access_token, new_refresh)
                )
                conn.commit()
                conn.close()
                return access_token
        except Exception as e:
            print(f"Discord token refresh failed: {e}")
        return None

    def get_discord_token(self):
        """Get a valid Discord access token, refreshing if needed."""
        conn = get_db()
        row = conn.execute("SELECT access_token, refresh_token FROM discord_link WHERE id=1").fetchone()
        conn.close()
        if not row or not row["access_token"]:
            return None
        token = row["access_token"]
        # Quick check if token still works
        user_data, status = discord_request("GET", "/users/@me", token=token)
        if status == 200:
            return token
        # Try refresh
        if row["refresh_token"]:
            new_token = self.refresh_discord_token()
            if new_token:
                return new_token
        return None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/auth/me":
            user = self.get_user_from_token()
            if not user:
                self.send_json({"logged_in": False})
                return
            self.send_json({
                "logged_in": True, "id": user["id"], "email": user["email"],
                "username": user["username"], "display_name": user["display_name"] or user["username"],
                "avatar": user["avatar"], "is_verified": bool(user["is_verified"])
            })
            return

        if path == "/api/discord/login":
            if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
                self.send_json({"error": "Discord غير مضبوط"}, 500)
                return
            params = {"client_id": DISCORD_CLIENT_ID, "redirect_uri": DISCORD_REDIRECT_URI,
                      "response_type": "code", "scope": "identify email"}
            url = "https://discord.com/api/oauth2/authorize?" + urllib.parse.urlencode(params)
            self.send_response(302); self.send_header("Location", url); self.end_headers()
            return

        if path == "/api/discord/callback":
            code = query.get("code", [None])[0]
            if not code:
                self.send_response(302)
                self.send_header("Location", "/admin.html?discord=error&msg=no_code")
                self.end_headers(); return
            basic = base64.b64encode(f"{DISCORD_CLIENT_ID}:{DISCORD_CLIENT_SECRET}".encode()).decode()
            data = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code,
                                           "redirect_uri": DISCORD_REDIRECT_URI}).encode()
            req = urllib.request.Request("https://discord.com/api/oauth2/token", data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "Authorization": f"Basic {basic}", "User-Agent": "ShopBot/1.0"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=15) as resp:
                    token_data = json.loads(resp.read().decode())
            except Exception as e:
                self.send_response(302)
                self.send_header("Location", f"/admin.html?discord=error&msg={urllib.parse.quote(str(e)[:80])}")
                self.end_headers(); return
            access_token = token_data.get("access_token")
            user_data, status = discord_request("GET", "/users/@me", token=access_token)
            if status != 200:
                self.send_response(302)
                self.send_header("Location", "/admin.html?discord=error&msg=user_fetch_failed")
                self.end_headers(); return
            conn = get_db()
            conn.execute("DELETE FROM discord_link")
            conn.execute("INSERT INTO discord_link (id, access_token, refresh_token, user_id, username, global_name, avatar) VALUES (1,?,?,?,?,?,?)",
                (access_token, token_data.get("refresh_token"), user_data.get("id"), user_data.get("username"),
                 user_data.get("global_name"), user_data.get("avatar")))
            conn.commit(); conn.close()
            self.send_response(302); self.send_header("Location", "/admin.html?discord=success"); self.end_headers()
            return

        if path == "/api/discord/me":
            if not self.check_admin():
                self.send_json({"error": "غير مصرح"}, 403); return
            token = self.get_discord_token()
            if not token:
                self.send_json({"linked": False}); return
            user_data, status = discord_request("GET", "/users/@me", token=token)
            if status != 200:
                self.send_json({"linked": False}); return
            avatar_url = None
            if user_data.get("avatar"):
                avatar_url = f"https://cdn.discordapp.com/avatars/{user_data['id']}/{user_data['avatar']}.png?size=256"
            self.send_json({"linked": True, "id": user_data.get("id"), "username": user_data.get("username"),
                            "global_name": user_data.get("global_name"), "avatar": avatar_url})
            return

        if path == "/api/products":
            conn = get_db()
            rows = conn.execute("SELECT id, name, price, description, image FROM products ORDER BY id DESC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows]); return

        if path == "/api/orders":
            if not self.check_admin():
                self.send_json({"error": "غير مصرح"}, 403); return
            conn = get_db()
            rows = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows]); return

        if path == "/api/my-orders":
            user = self.get_user_from_token()
            if not user:
                self.send_json({"error": "يجب تسجيل الدخول"}, 401); return
            conn = get_db()
            rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (user["id"],)).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows]); return

        super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8") if length else "{}"
        try: data = json.loads(body)
        except: data = {}

        if path == "/api/auth/register":
            email = (data.get("email") or "").strip().lower()
            username = (data.get("username") or "").strip()
            password = data.get("password") or ""
            if not email or not username or not password:
                self.send_json({"error": "جميع الحقول مطلوبة"}, 400); return
            if len(password) < 6:
                self.send_json({"error": "كلمة المرور 6 أحرف على الأقل"}, 400); return
            if "@" not in email:
                self.send_json({"error": "بريد غير صالح"}, 400); return
            salt, hashed = hash_password(password)
            code = str(secrets.randbelow(900000) + 100000)
            try:
                conn = get_db()
                conn.execute("INSERT INTO users (email, username, password_salt, password_hash, display_name, verify_code, verify_expires) VALUES (?,?,?,?,?,?,?)",
                    (email, username, salt, hashed, username, code, time.time() + 600))
                conn.commit(); conn.close()
                self.send_json({"message": "تم إنشاء الحساب. أدخل كود التحقق.", "need_verify": True, "debug_code": code})
            except sqlite3.IntegrityError:
                self.send_json({"error": "هذا البريد مسجل مسبقاً"}, 400)
            return

        if path == "/api/auth/verify":
            email = (data.get("email") or "").strip().lower()
            code = (data.get("code") or "").strip()
            conn = get_db()
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not row:
                conn.close(); self.send_json({"error": "الحساب غير موجود"}, 404); return
            if row["is_verified"]:
                conn.close(); self.send_json({"message": "مفعّل مسبقاً"}); return
            if not row["verify_code"] or row["verify_code"] != code or (row["verify_expires"] or 0) < time.time():
                conn.close(); self.send_json({"error": "كود خاطئ أو منتهي"}, 400); return
            token = secrets.token_hex(32)
            conn.execute("UPDATE users SET is_verified=1, verify_code=NULL, token=?, token_expires=? WHERE id=?",
                (token, time.time() + 86400*30, row["id"]))
            conn.commit(); conn.close()
            self.send_json({"message": "تم التفعيل", "token": token}); return

        if path == "/api/auth/login":
            email = (data.get("email") or "").strip().lower()
            password = data.get("password") or ""
            conn = get_db()
            row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            if not row or not check_password(password, row["password_salt"], row["password_hash"]):
                conn.close(); self.send_json({"error": "البريد أو كلمة المرور خاطئة"}, 401); return
            if not row["is_verified"]:
                conn.close(); self.send_json({"error": "الحساب غير مفعّل", "need_verify": True}, 403); return
            token = secrets.token_hex(32)
            conn.execute("UPDATE users SET token=?, token_expires=? WHERE id=?", (token, time.time()+86400*30, row["id"]))
            conn.commit(); conn.close()
            self.send_json({"message": "تم الدخول", "token": token, "user": {
                "id": row["id"], "email": row["email"], "username": row["username"],
                "display_name": row["display_name"] or row["username"], "avatar": row["avatar"]
            }}); return

        if path == "/api/auth/profile":
            user = self.get_user_from_token()
            if not user:
                self.send_json({"error": "يجب تسجيل الدخول"}, 401); return
            display_name = (data.get("display_name") or "").strip()
            avatar = data.get("avatar")
            conn = get_db()
            if display_name:
                conn.execute("UPDATE users SET display_name=? WHERE id=?", (display_name, user["id"]))
            if avatar is not None:
                if avatar and not str(avatar).startswith("data:image/") and avatar != "":
                    conn.close(); self.send_json({"error": "صيغة صورة غير صحيحة"}, 400); return
                if avatar and len(str(avatar)) > 350000:
                    conn.close(); self.send_json({"error": "الصورة كبيرة جداً"}, 400); return
                conn.execute("UPDATE users SET avatar=? WHERE id=?", (avatar or None, user["id"]))
            conn.commit()
            row = conn.execute("SELECT id, email, username, display_name, avatar FROM users WHERE id=?", (user["id"],)).fetchone()
            conn.close()
            self.send_json({"message": "تم التحديث", "user": dict(row)}); return

        if path == "/api/discord/update":
            if not self.check_admin():
                self.send_json({"error": "غير مصرح"}, 403); return
            token = self.get_discord_token()
            if not token:
                self.send_json({"error": "غير مربوط أو انتهت صلاحية التوكن. أعد الربط."}, 400); return
            payload = {}
            username = (data.get("username") or "").strip()
            if username:
                if len(username) < 2 or len(username) > 32:
                    self.send_json({"error": "اسم المستخدم يجب أن يكون بين 2 و 32 حرف"}, 400); return
                payload["username"] = username
            if "global_name" in data:
                gn = (data.get("global_name") or "").strip()
                payload["global_name"] = gn if gn else None
            avatar = data.get("avatar")
            if avatar is not None:
                if avatar == "" or avatar is False:
                    payload["avatar"] = None
                else:
                    av = str(avatar)
                    if not av.startswith("data:image/"):
                        self.send_json({"error": "صيغة الصورة غير صحيحة (يجب data:image/...)"}, 400); return
                    if len(av) > 800000:
                        self.send_json({"error": "الصورة كبيرة جداً، قصّها أو صغّرها"}, 400); return
                    payload["avatar"] = av
            if not payload:
                self.send_json({"error": "لا بيانات للتحديث"}, 400); return
            result, status = discord_request("PATCH", "/users/@me", token=token, data=payload)
            if status in (200, 201):
                conn = get_db()
                conn.execute(
                    "UPDATE discord_link SET username=?, global_name=?, avatar=?, updated_at=CURRENT_TIMESTAMP WHERE id=1",
                    (result.get("username"), result.get("global_name"), result.get("avatar"))
                )
                conn.commit()
                conn.close()
                self.send_json({"message": "تم التحديث بنجاح على ديسكورد", "user": result})
            else:
                err_msg = result.get("message") or "فشل التحديث"
                if "errors" in result:
                    details = []
                    for field, errs in result["errors"].items():
                        if isinstance(errs, dict) and "_errors" in errs:
                            for e in errs["_errors"]:
                                details.append(f"{field}: {e.get('message', e)}")
                        else:
                            details.append(f"{field}: {errs}")
                    if details:
                        err_msg = " | ".join(details)
                if status == 401:
                    err_msg = "انتهت صلاحية التوكن. أعد ربط حساب ديسكورد."
                elif "USERNAME" in err_msg.upper() or "username" in str(result).lower():
                    err_msg = "لا يمكن تغيير اسم المستخدم الآن (قد يكون هناك فترة انتظار أو الاسم محجوز)."
                self.send_json({"error": err_msg, "discord_status": status, "raw": result}, status if status >= 400 else 400)
            return

        if path == "/api/products":
            if not self.check_admin():
                self.send_json({"error": "غير مصرح"}, 403); return
            name = data.get("name", "").strip(); price = data.get("price")
            if not name or price is None:
                self.send_json({"error": "الاسم والسعر مطلوبان"}, 400); return
            conn = get_db()
            cur = conn.execute("INSERT INTO products (name, price, description, image) VALUES (?,?,?,?)",
                (name, float(price), data.get("description","").strip(), data.get("image","").strip()))
            conn.commit(); new_id = cur.lastrowid; conn.close()
            self.send_json({"id": new_id, "message": "تم الإضافة"}); return

        if path == "/api/orders":
            items = data.get("items", [])
            if not items:
                self.send_json({"error": "السلة فارغة"}, 400); return
            user = self.get_user_from_token()
            conn = get_db()
            conn.execute("INSERT INTO orders (user_id, items, total, customer_name, customer_phone) VALUES (?,?,?,?,?)",
                (user["id"] if user else None, json.dumps(items, ensure_ascii=False), data.get("total",0),
                 data.get("customer_name","").strip(), data.get("customer_phone","").strip()))
            conn.commit(); conn.close()
            self.send_json({"message": "تم استلام الطلب!"}); return

        self.send_json({"error": "مسار غير موجود"}, 404)

    def do_PUT(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/products/") or not self.check_admin():
            self.send_json({"error": "غير مصرح"}, 403); return
        try: pid = int(path.split("/")[-1])
        except: self.send_json({"error": "معرف خاطئ"}, 400); return
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length).decode() if length else "{}")
        conn = get_db()
        conn.execute("UPDATE products SET name=?, price=?, description=?, image=? WHERE id=?",
            (data.get("name","").strip(), float(data.get("price")), data.get("description","").strip(),
             data.get("image","").strip(), pid))
        conn.commit(); conn.close()
        self.send_json({"message": "تم التحديث"})

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path == "/api/discord/unlink":
            if not self.check_admin():
                self.send_json({"error": "غير مصرح"}, 403); return
            conn = get_db(); conn.execute("DELETE FROM discord_link"); conn.commit(); conn.close()
            self.send_json({"message": "تم فك الربط"}); return
        if path == "/api/auth/logout":
            user = self.get_user_from_token()
            if user:
                conn = get_db()
                conn.execute("UPDATE users SET token=NULL, token_expires=NULL WHERE id=?", (user["id"],))
                conn.commit(); conn.close()
            self.send_json({"message": "تم الخروج"}); return
        if not path.startswith("/api/products/") or not self.check_admin():
            self.send_json({"error": "غير مصرح"}, 403); return
        try: pid = int(path.split("/")[-1])
        except: self.send_json({"error": "معرف خاطئ"}, 400); return
        conn = get_db(); conn.execute("DELETE FROM products WHERE id=?", (pid,)); conn.commit(); conn.close()
        self.send_json({"message": "تم الحذف"})

if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 8080))
    DISCORD_REDIRECT_URI = get_redirect_uri()
    server = HTTPServer(("0.0.0.0", port), ShopHandler)
    print(f"🚀 يعمل على {port} | Redirect: {DISCORD_REDIRECT_URI}")
    try: server.serve_forever()
    except KeyboardInterrupt: print("\nتوقف")
