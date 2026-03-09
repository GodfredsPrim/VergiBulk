from flask import Flask, request, jsonify, send_from_directory, session
from flask_cors import CORS
import sqlite3
import hashlib
import re
import os


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'vegibulk_secret_key-change-in-production')

# Configure CORS for production
allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
CORS(app, supports_credentials=True, origins=allowed_origins)

from flask import send_from_directory

# Environment configuration
DB_PATH = os.environ.get('DATABASE_PATH', 'vegibulk.db')
DEBUG_MODE = os.environ.get('FLASK_ENV', 'production') == 'development'

@app.route("/")
def home():
    return send_from_directory("templates", "index .html")

@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory("static/vegibulk img", filename)

@app.route("/api/test")
def test():
    return {"message": "Frontend connected to backend successfully"}

_db_initialized = False

def get_db():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.OperationalError:
        # Handle read-only filesystem (Vercel)
        return None

def init_db():
    global _db_initialized
    if _db_initialized:
        return
    try:
        conn = get_db()
        if not conn:
            return
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                image_url TEXT,
                price_per_unit REAL NOT NULL,
                quantity_available REAL NOT NULL,
                unit TEXT DEFAULT 'kg',
                region TEXT NOT NULL,
                town TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                reaction_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(post_id, user_id, reaction_type),
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.execute('''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (post_id) REFERENCES posts(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        _db_initialized = True
    except Exception as e:
        # Silently fail on Vercel (read-only filesystem)
        pass

# Initialize DB on first request
@app.before_request
def before_request():
    init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)

# ── AUTH ROUTES ──
@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.json
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not full_name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
    if not is_valid_email(email):
        return jsonify({'success': False, 'message': 'Please enter a valid email address.'}), 400
    if len(password) < 6:
        return jsonify({'success': False, 'message': 'Password must be at least 6 characters.'}), 400

    try:
        conn = get_db()
        conn.execute(
            'INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)',
            (full_name, email, hash_password(password))
        )
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        session['user_id'] = user['id']
        session['user_name'] = user['full_name']
        session['user_email'] = user['email']
        conn.close()
        return jsonify({'success': True, 'message': 'Account created!', 'user': {'id': user['id'], 'full_name': user['full_name'], 'email': email}})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'An account with this email already exists.'}), 409

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required.'}), 400

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ? AND password_hash = ?',
        (email, hash_password(password))
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({'success': False, 'message': 'Incorrect email or password.'}), 401

    session['user_id'] = user['id']
    session['user_name'] = user['full_name']
    session['user_email'] = user['email']
    return jsonify({'success': True, 'message': f"Welcome back, {user['full_name']}!", 'user': {'id': user['id'], 'full_name': user['full_name'], 'email': user['email']}})

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})

@app.route('/api/auth/me', methods=['GET'])
def me():
    if 'user_id' in session:
        return jsonify({'logged_in': True, 'user': {'name': session['user_name'], 'email': session['user_email']}})
    return jsonify({'logged_in': False})

# ── VEGETABLES ──
vegetables = [
    # ── FRUIT VEGETABLES ──
    {"id": 1,  "name": "Tomatoes",            "local_name": "Tomato",         "category": "Fruit Vegetables",   "price_per_kg": 2.50,  "min_order_kg": 10,  "stock_kg": 2000, "image": "https://images.unsplash.com/photo-1592841200221-a6898f307baa?w=500&h=400&fit=crop", "emoji": "🍅", "origin": "Brong-Ahafo Region",    "description": "Ghana's most important vegetable crop. Ripe, firm tomatoes ideal for stews, soups, and sauces.", "rating": 4.9, "reviews": 412, "tag": "Bestseller"},
    {"id": 2,  "name": "Okra (Okro)",         "local_name": "Nkruma",         "category": "Fruit Vegetables",   "price_per_kg": 3.20,  "min_order_kg": 10,  "stock_kg": 800,  "image": "https://images.unsplash.com/photo-1639024471283-03518883512d?w=500&h=400&fit=crop", "emoji": "🫛", "origin": "Volta Region",          "description": "Fresh okra pods, tender and slimy. Essential for okra soup and stew — a Ghanaian kitchen staple.", "rating": 4.8, "reviews": 327, "tag": "Bestseller"},
    {"id": 3,  "name": "Garden Eggs",         "local_name": "Ntroba / Anyan", "category": "Fruit Vegetables",   "price_per_kg": 2.80,  "min_order_kg": 10,  "stock_kg": 600,  "image": "https://images.unsplash.com/photo-1619566636858-adf3ef46400b?w=500&h=400&fit=crop", "emoji": "🍆", "origin": "Ashanti Region",        "description": "White and purple garden eggs (African eggplant). Used in garden egg stew and palava sauce.", "rating": 4.7, "reviews": 289, "tag": "Popular"},
    {"id": 4,  "name": "Bell Peppers",        "local_name": "Mako Tuntum",    "category": "Fruit Vegetables",   "price_per_kg": 4.20,  "min_order_kg": 10,  "stock_kg": 400,  "image": "https://images.unsplash.com/photo-1596591606975-97ee5cef3a1e?w=500&h=400&fit=crop", "emoji": "🫑", "origin": "Greenhouse, Accra",    "description": "Colorful red, yellow and green bell peppers. Sweet and crunchy, perfect for salads and stir-fries.", "rating": 4.6, "reviews": 142, "tag": "Fresh"},
    {"id": 5,  "name": "Hot Chili Pepper",    "local_name": "Mako Nmuro",     "category": "Fruit Vegetables",   "price_per_kg": 5.50,  "min_order_kg": 5,   "stock_kg": 700,  "image": "https://images.unsplash.com/photo-1601648764658-cf37e8c89b70?w=500&h=400&fit=crop", "emoji": "🌶️", "origin": "Northern Region",       "description": "Fiery hot Ghanaian chili peppers. Ghana ranks 2nd in Africa for pepper production. A must for local dishes.", "rating": 4.9, "reviews": 503, "tag": "Bestseller"},
    {"id": 6,  "name": "Cucumbers",           "local_name": "Cucumber",       "category": "Fruit Vegetables",   "price_per_kg": 1.80,  "min_order_kg": 15,  "stock_kg": 600,  "image": "https://images.unsplash.com/photo-1604977042946-1eecc30f269e?w=500&h=400&fit=crop", "emoji": "🥒", "origin": "Bono Region",           "description": "Fresh cucumbers grown by local farmers. Great for salads, juicing, and snacking.", "rating": 4.6, "reviews": 178, "tag": "Fresh"},
    {"id": 7,  "name": "Pumpkin",             "local_name": "Apatem / Froe",  "category": "Fruit Vegetables",   "price_per_kg": 1.50,  "min_order_kg": 20,  "stock_kg": 900,  "image": "https://images.unsplash.com/photo-1570586437263-ab629fccc818?w=500&h=400&fit=crop", "emoji": "🎃", "origin": "Central Region",        "description": "Large, sweet pumpkins. Both the fruit and leaves are consumed widely in Ghana.", "rating": 4.5, "reviews": 96,  "tag": "Seasonal"},
    {"id": 8,  "name": "Bitter Gourd (Luffa)","local_name": "Zambole",        "category": "Fruit Vegetables",   "price_per_kg": 2.20,  "min_order_kg": 10,  "stock_kg": 350,  "image": "https://images.unsplash.com/photo-1601493700631-2b16ec4b4716?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Savannah Region",       "description": "Sponge gourd (Luffa) known as Zambole/Abrofo Sapo. Consumed as vegetable in northern Ghana.", "rating": 4.3, "reviews": 61,  "tag": "Local"},
    {"id": 9,  "name": "Sweet Corn",          "local_name": "Aburo",          "category": "Fruit Vegetables",   "price_per_kg": 2.10,  "min_order_kg": 20,  "stock_kg": 1200, "image": "https://images.unsplash.com/photo-1551754655-cd27e38d2076?w=500&h=400&fit=crop", "emoji": "🌽", "origin": "Eastern Region",        "description": "Golden sweet corn harvested at peak ripeness. Popular for roasting and in local dishes.", "rating": 4.7, "reviews": 215, "tag": "Seasonal"},
    {"id": 10, "name": "Watermelon",          "local_name": "Watermelon",     "category": "Fruit Vegetables",   "price_per_kg": 1.20,  "min_order_kg": 50,  "stock_kg": 3000, "image": "https://images.unsplash.com/photo-1587049352846-4a222e784d38?w=500&h=400&fit=crop", "emoji": "🍉", "origin": "Northern Region",       "description": "Large, sweet Ghanaian watermelons. Heavily grown in the northern savanna zones.", "rating": 4.8, "reviews": 187, "tag": "Seasonal"},

    # ── LEAFY GREENS ──
    {"id": 11, "name": "Kontomire (Cocoyam Leaf)", "local_name": "Kontomire", "category": "Leafy Greens",      "price_per_kg": 2.50,  "min_order_kg": 5,   "stock_kg": 500,  "image": "https://images.unsplash.com/photo-1604329760661-e71dc83f8f26?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Ashanti Region",        "description": "Taro/cocoyam leaves — one of Ghana's most loved vegetables. Used in kontomire stew (palava sauce).", "rating": 4.9, "reviews": 445, "tag": "Bestseller"},
    {"id": 12, "name": "Spinach (Alefu)",     "local_name": "Alefu / Aleefu", "category": "Leafy Greens",      "price_per_kg": 3.00,  "min_order_kg": 5,   "stock_kg": 300,  "image": "https://images.unsplash.com/photo-1576045057995-568f588f82fb?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Greater Accra",         "description": "African spinach (Amaranth). Tender green leaves used in soups and stews across all regions.", "rating": 4.7, "reviews": 312, "tag": "Organic"},
    {"id": 13, "name": "Jute Mallow (Ayoyo)", "local_name": "Ayoyo",         "category": "Leafy Greens",      "price_per_kg": 2.80,  "min_order_kg": 5,   "stock_kg": 250,  "image": "https://images.unsplash.com/photo-1574316071802-0d684efa7bf5?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Northern Region",       "description": "Jute mallow leaves (Corchorus olitorius). A favourite in northern Ghana — cooked into soups and stews.", "rating": 4.8, "reviews": 198, "tag": "Local"},
    {"id": 14, "name": "Waterleaf",           "local_name": "Gboma / Talinum","category": "Leafy Greens",      "price_per_kg": 2.40,  "min_order_kg": 5,   "stock_kg": 200,  "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Greater Accra",         "description": "Waterleaf (Talinum fruticosum). Soft, succulent leaves widely used in Ghanaian soups.", "rating": 4.6, "reviews": 143, "tag": "Fresh"},
    {"id": 15, "name": "Bitter Leaf",         "local_name": "Bonwire Ntewa",  "category": "Leafy Greens",      "price_per_kg": 3.50,  "min_order_kg": 5,   "stock_kg": 180,  "image": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Volta Region",          "description": "Bitter leaf (Vernonia amygdalina). Medicinal and culinary uses. Adds depth to soups and stews.", "rating": 4.5, "reviews": 88,  "tag": "Medicinal"},
    {"id": 16, "name": "Moringa Leaves",      "local_name": "Yevu-ti / Zogale","category": "Leafy Greens",     "price_per_kg": 6.00,  "min_order_kg": 3,   "stock_kg": 150,  "image": "https://images.unsplash.com/photo-1611721255032-5a4f5de3af41?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Northern Region",       "description": "Moringa (drumstick tree) leaves packed with nutrients. Dried or fresh, used in soups and teas.", "rating": 4.9, "reviews": 267, "tag": "Premium"},
    {"id": 17, "name": "Cabbage",             "local_name": "Kobis",          "category": "Leafy Greens",      "price_per_kg": 0.90,  "min_order_kg": 30,  "stock_kg": 2000, "image": "https://images.unsplash.com/photo-1594282486552-05b4d80fbb9f?w=500&h=400&fit=crop", "emoji": "🥬", "origin": "Eastern Region",        "description": "Firm green cabbages grown across Ghana. Used in coleslaw, salads, and stir-fries.", "rating": 4.5, "reviews": 201, "tag": "Value"},
    {"id": 18, "name": "Lettuce",             "local_name": "Salad",          "category": "Leafy Greens",      "price_per_kg": 3.00,  "min_order_kg": 8,   "stock_kg": 180,  "image": "https://images.unsplash.com/photo-1622206151226-18ca2c9ab4a1?w=500&h=400&fit=crop", "emoji": "🥗", "origin": "Greenhouse, Kumasi",    "description": "Crisp iceberg and romaine lettuce. A staple in Ghanaian salads and light meals.", "rating": 4.4, "reviews": 115, "tag": "Fresh"},
    {"id": 19, "name": "Pumpkin Leaves",      "local_name": "Apatem Nkwan",   "category": "Leafy Greens",      "price_per_kg": 1.80,  "min_order_kg": 5,   "stock_kg": 300,  "image": "https://images.unsplash.com/photo-1604329760661-e71dc83f8f26?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Central Region",        "description": "Young pumpkin leaves and tendrils. Cooked as a vegetable in soups, very nutritious.", "rating": 4.4, "reviews": 72,  "tag": "Local"},
    {"id": 20, "name": "Sweet Potato Leaves", "local_name": "Atornam",        "category": "Leafy Greens",      "price_per_kg": 2.00,  "min_order_kg": 5,   "stock_kg": 220,  "image": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Brong-Ahafo Region",    "description": "Tender sweet potato leaves, iron-rich and delicious. Cooked in soups across Ghana.", "rating": 4.6, "reviews": 94,  "tag": "Organic"},
    {"id": 21, "name": "Cowpea Leaves",       "local_name": "Aboboi Nkwan",   "category": "Leafy Greens",      "price_per_kg": 2.20,  "min_order_kg": 5,   "stock_kg": 200,  "image": "https://images.unsplash.com/photo-1574316071802-0d684efa7bf5?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Upper East Region",     "description": "Young cowpea leaves. Highly nutritious and used in northern Ghanaian soups.", "rating": 4.5, "reviews": 63,  "tag": "Local"},
    {"id": 22, "name": "Roselle (Bissap)",    "local_name": "Bito / Bre",     "category": "Leafy Greens",      "price_per_kg": 4.00,  "min_order_kg": 5,   "stock_kg": 160,  "image": "https://images.unsplash.com/photo-1515543904379-3d757afe72e4?w=500&h=400&fit=crop", "emoji": "🌺", "origin": "Northern Region",       "description": "Roselle (Hibiscus sabdariffa). Leaves used in soups; calyces for juice. Popular in northern Ghana.", "rating": 4.7, "reviews": 109, "tag": "Medicinal"},
    {"id": 23, "name": "African Spider Plant","local_name": "Akutu / Gyanantu","category": "Leafy Greens",     "price_per_kg": 3.00,  "min_order_kg": 3,   "stock_kg": 120,  "image": "https://images.unsplash.com/photo-1511884642898-4c92249e20b6?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Upper West Region",     "description": "African spider plant (Cleome gynandra). A traditional vegetable with a distinct flavour.", "rating": 4.4, "reviews": 47,  "tag": "Local"},
    {"id": 24, "name": "Kenaf Leaves",        "local_name": "Yakuwa",         "category": "Leafy Greens",      "price_per_kg": 2.50,  "min_order_kg": 5,   "stock_kg": 140,  "image": "https://images.unsplash.com/photo-1574316071802-0d684efa7bf5?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Upper East Region",     "description": "Kenaf (Hibiscus cannabinus) leaves. Used in soups in the north. Rich in minerals.", "rating": 4.3, "reviews": 38,  "tag": "Local"},
    {"id": 25, "name": "Broccoli",            "local_name": "Broccoli",       "category": "Leafy Greens",      "price_per_kg": 5.00,  "min_order_kg": 10,  "stock_kg": 250,  "image": "https://images.unsplash.com/photo-1459411621453-7b03977f4bfc?w=500&h=400&fit=crop", "emoji": "🥦", "origin": "Greenhouse, Accra",    "description": "Fresh broccoli crowns. Grown in Ghanaian greenhouses for local markets and hotels.", "rating": 4.6, "reviews": 132, "tag": "Premium"},

    # ── ROOT & TUBER VEGETABLES ──
    {"id": 26, "name": "Onions",              "local_name": "Gyeene",         "category": "Root & Bulb Vegetables", "price_per_kg": 1.20, "min_order_kg": 50, "stock_kg": 5000, "image": "https://images.unsplash.com/photo-1618512496248-a07fe83aa8cb?w=500&h=400&fit=crop", "emoji": "🧅", "origin": "Upper East Region",    "description": "Ghana's 3rd most important vegetable. Red and white onions from the northern lowlands.", "rating": 4.8, "reviews": 524, "tag": "Bestseller"},
    {"id": 27, "name": "Garlic",              "local_name": "Gyeene Fitaa",   "category": "Root & Bulb Vegetables", "price_per_kg": 8.00, "min_order_kg": 5,  "stock_kg": 200,  "image": "https://images.unsplash.com/photo-1611944212129-29977ae1398c?w=500&h=400&fit=crop", "emoji": "🧄", "origin": "Upper West Region",    "description": "Premium Ghanaian garlic with intense aroma. Grown in the upper regions.", "rating": 4.9, "reviews": 338, "tag": "Premium"},
    {"id": 28, "name": "Carrots",             "local_name": "Karot",          "category": "Root & Bulb Vegetables", "price_per_kg": 2.50, "min_order_kg": 20, "stock_kg": 900,  "image": "https://images.unsplash.com/photo-1598170845058-32b9d6a5da37?w=500&h=400&fit=crop", "emoji": "🥕", "origin": "Bono Region",           "description": "Fresh, sweet carrots grown in Ghanaian soils. Used in salads, soups, and juicing.", "rating": 4.6, "reviews": 187, "tag": "Fresh"},
    {"id": 29, "name": "Spring Onions",       "local_name": "Gyeene Fitaa",   "category": "Root & Bulb Vegetables", "price_per_kg": 3.50, "min_order_kg": 10, "stock_kg": 300,  "image": "https://images.unsplash.com/photo-1587049352851-8d4e89133924?w=500&h=400&fit=crop", "emoji": "🧅", "origin": "Greater Accra",         "description": "Fresh spring onions (green onions). A common garnish and ingredient in Ghanaian cooking.", "rating": 4.5, "reviews": 129, "tag": "Fresh"},
    {"id": 30, "name": "Ginger",              "local_name": "Akekaduro",      "category": "Root & Bulb Vegetables", "price_per_kg": 7.00, "min_order_kg": 10, "stock_kg": 400,  "image": "https://images.unsplash.com/photo-1615485500704-8e990f9900f7?w=500&h=400&fit=crop", "emoji": "🫚", "origin": "Eastern Region",        "description": "Spicy, aromatic fresh ginger root. Used in virtually every Ghanaian dish and in ginger tea.", "rating": 4.9, "reviews": 412, "tag": "Bestseller"},
    {"id": 31, "name": "Yam",                 "local_name": "Bayere",         "category": "Root & Tuber Vegetables", "price_per_kg": 1.80, "min_order_kg": 50, "stock_kg": 8000, "image": "https://images.unsplash.com/photo-1596046559697-2e96b5e9bcd4?w=500&h=400&fit=crop", "emoji": "🍠", "origin": "Brong-Ahafo Region",   "description": "White yam — the pride of Ghanaian cuisine. Used in fufu, yam stew, and ampesi.", "rating": 4.9, "reviews": 611, "tag": "Bestseller"},
    {"id": 32, "name": "Cocoyam",             "local_name": "Kookoo / Mankani","category": "Root & Tuber Vegetables","price_per_kg": 1.50,"min_order_kg": 30, "stock_kg": 3000, "image": "https://images.unsplash.com/photo-1590165482129-1b8b27698780?w=500&h=400&fit=crop", "emoji": "🍠", "origin": "Ashanti Region",        "description": "Cocoyam (taro) corms and cormels. Used in fufu, ampesi, and cocoyam porridge.", "rating": 4.7, "reviews": 289, "tag": "Popular"},
    {"id": 33, "name": "Cassava",             "local_name": "Bankye",         "category": "Root & Tuber Vegetables","price_per_kg": 0.80,"min_order_kg": 100,"stock_kg":10000, "image": "https://images.unsplash.com/photo-1604497181015-76590d828b69?w=500&h=400&fit=crop", "emoji": "🍠", "origin": "Eastern Region",        "description": "Starchy cassava roots. The base for gari, fufu, kokonte and ampesi. Widely grown across Ghana.", "rating": 4.7, "reviews": 378, "tag": "Bulk Deal"},
    {"id": 34, "name": "Sweet Potatoes",      "local_name": "Atornam",        "category": "Root & Tuber Vegetables","price_per_kg": 1.50,"min_order_kg": 30, "stock_kg": 2000, "image": "https://images.unsplash.com/photo-1596097635121-14b63b7a0c19?w=500&h=400&fit=crop", "emoji": "🍠", "origin": "Brong-Ahafo Region",   "description": "Orange and white sweet potatoes. Boiled, fried, or mashed. Very popular across Ghana.", "rating": 4.6, "reviews": 243, "tag": "Popular"},
    {"id": 35, "name": "Radish",              "local_name": "Radish",         "category": "Root & Tuber Vegetables","price_per_kg": 3.00,"min_order_kg": 10, "stock_kg": 200,  "image": "https://images.unsplash.com/photo-1530047406236-5dea7826c3e5?w=500&h=400&fit=crop", "emoji": "🌱", "origin": "Greenhouse, Accra",    "description": "Crisp, peppery radishes. Grown in urban gardens for salads and garnishing.", "rating": 4.3, "reviews": 51,  "tag": "Fresh"},

    # ── HERBS & AROMATICS ──
    {"id": 36, "name": "Hot Pepper (Scotch Bonnet)","local_name":"Mako",      "category": "Herbs & Aromatics",  "price_per_kg": 6.00,  "min_order_kg": 5,   "stock_kg": 600,  "image": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=500&h=400&fit=crop", "emoji": "🌶️", "origin": "Northern Region",       "description": "Scotch bonnet and bird's eye chili peppers. The heart of every Ghanaian stew and soup.", "rating": 4.9, "reviews": 556, "tag": "Bestseller"},
    {"id": 37, "name": "Ginger (Dried)",      "local_name": "Akekaduro",      "category": "Herbs & Aromatics",  "price_per_kg": 12.00, "min_order_kg": 5,   "stock_kg": 300,  "image": "https://images.unsplash.com/photo-1615485500704-8e990f9900f7?w=500&h=400&fit=crop", "emoji": "🫚", "origin": "Eastern Region",        "description": "Sun-dried and ground ginger from Ghanaian farms. Intense flavour for cooking and herbal drinks.", "rating": 4.8, "reviews": 214, "tag": "Premium"},
    {"id": 38, "name": "Fresh Basil",         "local_name": "Nufusua",        "category": "Herbs & Aromatics",  "price_per_kg": 8.00,  "min_order_kg": 3,   "stock_kg": 80,   "image": "https://images.unsplash.com/photo-1628556270448-4d4e4148e1b1?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Greater Accra",         "description": "Fragrant fresh basil, locally grown. Used in sauces, salads, and Ghanaian herbal medicine.", "rating": 4.5, "reviews": 67,  "tag": "Organic"},
    {"id": 39, "name": "Shallots",            "local_name": "Kopa",           "category": "Herbs & Aromatics",  "price_per_kg": 4.50,  "min_order_kg": 10,  "stock_kg": 500,  "image": "https://images.unsplash.com/photo-1587049352851-8d4e89133924?w=500&h=400&fit=crop", "emoji": "🧅", "origin": "Upper East Region",     "description": "Small, sweet shallots. A key ingredient in Ghanaian cooking, especially in rice dishes and stews.", "rating": 4.7, "reviews": 193, "tag": "Popular"},
    {"id": 40, "name": "Spring Onion Leaves", "local_name": "Ntroba Fitaa",   "category": "Herbs & Aromatics",  "price_per_kg": 3.50,  "min_order_kg": 5,   "stock_kg": 160,  "image": "https://images.unsplash.com/photo-1574316071802-0d684efa7bf5?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Greater Accra",         "description": "Fresh scallion tops. Used as a garnish and flavoring in rice, stews, and eggs.", "rating": 4.4, "reviews": 82,  "tag": "Fresh"},

    # ── OTHER VEGETABLES ──
    {"id": 41, "name": "Eggplant (Brinjal)",  "local_name": "Anyan",          "category": "Other Vegetables",   "price_per_kg": 2.50,  "min_order_kg": 10,  "stock_kg": 400,  "image": "https://images.unsplash.com/photo-1619566636858-adf3ef46400b?w=500&h=400&fit=crop", "emoji": "🍆", "origin": "Ashanti Region",        "description": "Purple brinjal eggplant. Used in grills, stews, and as a substitute for garden eggs.", "rating": 4.6, "reviews": 127, "tag": "Popular"},
    {"id": 42, "name": "Green Beans",         "local_name": "Aboboi Fitaa",   "category": "Other Vegetables",   "price_per_kg": 4.00,  "min_order_kg": 10,  "stock_kg": 300,  "image": "https://images.unsplash.com/photo-1567375698348-5d9d5ae99de0?w=500&h=400&fit=crop", "emoji": "🫘", "origin": "Eastern Region",        "description": "Tender green beans (French beans). Grown for local markets and export. Great for stir-fries.", "rating": 4.7, "reviews": 169, "tag": "Export Grade"},
    {"id": 43, "name": "Cowpeas (Black-Eyed Peas)","local_name":"Aboboi",     "category": "Other Vegetables",   "price_per_kg": 3.50,  "min_order_kg": 20,  "stock_kg": 1500, "image": "https://images.unsplash.com/photo-1608571423902-eed4a5ad8108?w=500&h=400&fit=crop", "emoji": "🫘", "origin": "Northern Region",       "description": "Dried cowpeas (black-eyed peas). Used in waakye, red-red, and bean stew across Ghana.", "rating": 4.8, "reviews": 298, "tag": "Bestseller"},
    {"id": 44, "name": "Mushrooms",           "local_name": "Odunsini",       "category": "Other Vegetables",   "price_per_kg": 9.00,  "min_order_kg": 5,   "stock_kg": 120,  "image": "https://images.unsplash.com/photo-1518977676601-b53f82aba655?w=500&h=400&fit=crop", "emoji": "🍄", "origin": "Ashanti Region",        "description": "Fresh oyster and button mushrooms. Grown locally and wild-harvested. Rich umami flavour.", "rating": 4.7, "reviews": 88,  "tag": "Premium"},
    {"id": 45, "name": "Turkey Berry",        "local_name": "Abeduru",        "category": "Other Vegetables",   "price_per_kg": 4.50,  "min_order_kg": 5,   "stock_kg": 180,  "image": "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?w=500&h=400&fit=crop", "emoji": "🫐", "origin": "Ashanti Region",        "description": "Turkey berry (Solanum torvum). Small wild fruit used in stews and soups. Known for its health benefits.", "rating": 4.6, "reviews": 74,  "tag": "Local"},
    {"id": 46, "name": "Baobab Leaves",       "local_name": "Kuka",           "category": "Other Vegetables",   "price_per_kg": 5.00,  "min_order_kg": 3,   "stock_kg": 100,  "image": "https://images.unsplash.com/photo-1511884642898-4c92249e20b6?w=500&h=400&fit=crop", "emoji": "🌿", "origin": "Northern Region",       "description": "Dried baobab leaves (Kuka). Used in northern Ghanaian soups. High in iron and calcium.", "rating": 4.5, "reviews": 54,  "tag": "Medicinal"},
    {"id": 47, "name": "Plantain",            "local_name": "Aborodwo / Abali","category": "Other Vegetables",  "price_per_kg": 1.00,  "min_order_kg": 50,  "stock_kg": 6000, "image": "https://images.unsplash.com/photo-1528825871115-3581a5387919?w=500&h=400&fit=crop", "emoji": "🍌", "origin": "Western Region",        "description": "Ripe and unripe plantains. Fried, boiled, or roasted — a cornerstone of Ghanaian cuisine.", "rating": 4.9, "reviews": 732, "tag": "Bestseller"},
    {"id": 48, "name": "Beetroot",            "local_name": "Beetroot",       "category": "Other Vegetables",   "price_per_kg": 3.50,  "min_order_kg": 10,  "stock_kg": 220,  "image": "https://images.unsplash.com/photo-1593105544559-ecb03bf6f466?w=500&h=400&fit=crop", "emoji": "🟣", "origin": "Greenhouse, Accra",    "description": "Deep red beetroot. Growing in popularity for salads, juicing, and healthy eating in Ghana.", "rating": 4.5, "reviews": 96,  "tag": "Fresh"},
]

categories = ["All", "Fruit Vegetables", "Leafy Greens", "Root & Bulb Vegetables", "Root & Tuber Vegetables", "Herbs & Aromatics", "Other Vegetables"]

@app.route('/api/vegetables', methods=['GET'])
def get_vegetables():
    search = request.args.get('search', '').lower()
    category = request.args.get('category', 'All')
    sort = request.args.get('sort', 'default')
    results = vegetables.copy()
    if search:
        results = [v for v in results if search in v['name'].lower() or search in v['category'].lower() or search in v.get('local_name','').lower()]
    if category != 'All':
        results = [v for v in results if v['category'] == category]
    if sort == 'price_asc':
        results.sort(key=lambda x: x['price_per_kg'])
    elif sort == 'price_desc':
        results.sort(key=lambda x: x['price_per_kg'], reverse=True)
    elif sort == 'rating':
        results.sort(key=lambda x: x['rating'], reverse=True)
    elif sort == 'popular':
        results.sort(key=lambda x: x['reviews'], reverse=True)
    return jsonify({"vegetables": results, "total": len(results)})

@app.route('/api/categories', methods=['GET'])
def get_categories():
    return jsonify({"categories": categories})

@app.route('/api/vegetables/<int:veg_id>', methods=['GET'])
def get_vegetable(veg_id):
    veg = next((v for v in vegetables if v['id'] == veg_id), None)
    if not veg:
        return jsonify({"error": "Not found"}), 404
    return jsonify(veg)

@app.route('/api/cart/checkout', methods=['POST'])
def checkout():
    data = request.json
    cart = data.get('cart', [])
    total = sum(item['price_per_kg'] * item['quantity_kg'] for item in cart)
    return jsonify({"success": True, "order_id": "ORD-2024-" + str(abs(hash(str(cart))))[:6], "total": round(total, 2), "message": "Order placed successfully!"})

# ── MARKETPLACE / SELLER ROUTES ──

@app.route('/api/posts', methods=['POST'])
def create_post():
    '''Create a new seller post'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
            
        user_id = session['user_id']
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        category = data.get('category', '').strip()
        price = float(data.get('price_per_unit', 0))
        quantity = float(data.get('quantity_available', 0))
        unit = data.get('unit', 'kg')
        image_url = data.get('image_url', '')
        region = data.get('region', '').strip()
        town = data.get('town', '').strip()
        
        # Validation
        if not title or not description or not category or price <= 0 or quantity <= 0 or not region or not town:
            return jsonify({'success': False, 'message': 'All fields are required and must be valid'}), 400
        
        # Limit image size (5MB max)
        if image_url and len(image_url) > 5 * 1024 * 1024:
            return jsonify({'success': False, 'message': 'Image is too large (max 5MB)'}), 400
        
        conn = get_db()
        cursor = conn.execute(
            '''INSERT INTO posts (user_id, title, description, category, image_url, price_per_unit, quantity_available, unit, region, town)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, title, description, category, image_url, price, quantity, unit, region, town)
        )
        conn.commit()
        post_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'message': 'Post created!', 'post_id': post_id})
    except ValueError as e:
        return jsonify({'success': False, 'message': f'Invalid input: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error creating post: {str(e)}'}), 500

@app.route('/api/posts', methods=['GET'])
def get_posts():
    '''Get all posts with optional filters'''
    try:
        conn = get_db()
        
        # Get filter parameters
        user_id = request.args.get('user_id')
        search = request.args.get('search', '').lower()
        
        query = '''
            SELECT p.id, p.user_id, p.title, p.description, p.image_url, p.category,
                   p.price_per_unit, p.quantity_available, p.unit, p.region, p.town, p.created_at,
                   u.full_name as seller_name,
                   COUNT(DISTINCT r.id) as reaction_count,
                   COUNT(DISTINCT c.id) as comment_count
            FROM posts p
            LEFT JOIN users u ON p.user_id = u.id
            LEFT JOIN reactions r ON p.id = r.post_id
            LEFT JOIN comments c ON p.id = c.post_id
        '''
        
        params = []
        
        if user_id:
            query += ' WHERE p.user_id = ?'
            params.append(user_id)
        elif search:
            query += ' WHERE LOWER(p.title) LIKE ? OR LOWER(p.description) LIKE ? OR LOWER(p.region) LIKE ? OR LOWER(p.town) LIKE ? OR LOWER(p.category) LIKE ?'
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%', f'%{search}%'])
        
        query += ' GROUP BY p.id ORDER BY p.created_at DESC'
        
        posts = conn.execute(query, params).fetchall()
        conn.close()
        
        posts_list = [dict(p) for p in posts]
        return jsonify({'success': True, 'posts': posts_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/posts/<int:post_id>', methods=['GET'])
def get_post(post_id):
    '''Get a single post with all details'''
    try:
        conn = get_db()
        post = conn.execute(
            '''SELECT p.id, p.user_id, p.title, p.description, p.image_url, 
                      p.price_per_unit, p.quantity_available, p.unit, p.region, p.town, p.created_at,
                      u.full_name as seller_name, u.email as seller_email
               FROM posts p
               LEFT JOIN users u ON p.user_id = u.id
               WHERE p.id = ?''',
            (post_id,)
        ).fetchone()
        
        if not post:
            conn.close()
            return jsonify({'success': False, 'message': 'Post not found'}), 404
        
        # Get reactions
        reactions = conn.execute(
            'SELECT reaction_type, COUNT(*) as count FROM reactions WHERE post_id = ? GROUP BY reaction_type',
            (post_id,)
        ).fetchall()
        
        reactions_dict = {r['reaction_type']: r['count'] for r in reactions}
        
        # Get user's reaction if logged in
        user_reaction = None
        if 'user_id' in session:
            user_rxn = conn.execute(
                'SELECT reaction_type FROM reactions WHERE post_id = ? AND user_id = ?',
                (post_id, session['user_id'])
            ).fetchone()
            user_reaction = user_rxn['reaction_type'] if user_rxn else None
        
        conn.close()
        
        post_dict = dict(post)
        post_dict['reactions'] = reactions_dict
        post_dict['user_reaction'] = user_reaction
        
        return jsonify({'success': True, 'post': post_dict})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    '''Delete a post (only by post owner)'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    try:
        conn = get_db()
        post = conn.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
        
        if not post:
            conn.close()
            return jsonify({'success': False, 'message': 'Post not found'}), 404
        
        if post['user_id'] != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'message': 'Not authorized'}), 403
        
        # Delete related data
        conn.execute('DELETE FROM comments WHERE post_id = ?', (post_id,))
        conn.execute('DELETE FROM reactions WHERE post_id = ?', (post_id,))
        conn.execute('DELETE FROM posts WHERE id = ?', (post_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Post deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── REACTIONS / LIKES ──

@app.route('/api/posts/<int:post_id>/reactions', methods=['POST'])
def add_reaction(post_id):
    '''Add or update a reaction to a post'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    data = request.json
    reaction_type = data.get('reaction_type', 'like').lower()  # like, love, excited, thinking
    user_id = session['user_id']
    
    try:
        conn = get_db()
        
        # Check if post exists
        if not conn.execute('SELECT id FROM posts WHERE id = ?', (post_id,)).fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Post not found'}), 404
        
        # Try to remove existing reaction of any type
        conn.execute('DELETE FROM reactions WHERE post_id = ? AND user_id = ?', (post_id, user_id))
        
        # Add new reaction
        conn.execute(
            'INSERT INTO reactions (post_id, user_id, reaction_type) VALUES (?, ?, ?)',
            (post_id, user_id, reaction_type)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': f'Reacted with {reaction_type}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/posts/<int:post_id>/reactions', methods=['DELETE'])
def remove_reaction(post_id):
    '''Remove a reaction from a post'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    user_id = session['user_id']
    
    try:
        conn = get_db()
        conn.execute('DELETE FROM reactions WHERE post_id = ? AND user_id = ?', (post_id, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Reaction removed'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── COMMENTS ──

@app.route('/api/posts/<int:post_id>/comments', methods=['POST'])
def add_comment(post_id):
    '''Add a comment to a post'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    data = request.json
    text = data.get('text', '').strip()
    user_id = session['user_id']
    
    if not text or len(text) < 2:
        return jsonify({'success': False, 'message': 'Comment too short'}), 400
    
    try:
        conn = get_db()
        
        # Check if post exists
        if not conn.execute('SELECT id FROM posts WHERE id = ?', (post_id,)).fetchone():
            conn.close()
            return jsonify({'success': False, 'message': 'Post not found'}), 404
        
        cursor = conn.execute(
            'INSERT INTO comments (post_id, user_id, text) VALUES (?, ?, ?)',
            (post_id, user_id, text)
        )
        conn.commit()
        comment_id = cursor.lastrowid
        conn.close()
        
        return jsonify({'success': True, 'message': 'Comment added', 'comment_id': comment_id})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    '''Get all comments for a post'''
    try:
        conn = get_db()
        comments = conn.execute(
            '''SELECT c.id, c.text, c.created_at, u.full_name as author_name
               FROM comments c
               LEFT JOIN users u ON c.user_id = u.id
               WHERE c.post_id = ?
               ORDER BY c.created_at DESC''',
            (post_id,)
        ).fetchall()
        conn.close()
        
        comments_list = [dict(c) for c in comments]
        return jsonify({'success': True, 'comments': comments_list})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/posts/<int:post_id>/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(post_id, comment_id):
    '''Delete a comment (only by author or post owner)'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    try:
        conn = get_db()
        
        # Get comment and post info
        comment = conn.execute('SELECT user_id FROM comments WHERE id = ?', (comment_id,)).fetchone()
        post = conn.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
        
        if not comment or not post:
            conn.close()
            return jsonify({'success': False, 'message': 'Not found'}), 404
        
        # Check authorization (comment author or post owner)
        if comment['user_id'] != session['user_id'] and post['user_id'] != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'message': 'Not authorized'}), 403
        
        conn.execute('DELETE FROM comments WHERE id = ?', (comment_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Comment deleted'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# ── ANALYTICS ──

@app.route('/api/posts/<int:post_id>/analytics', methods=['GET'])
def get_post_analytics(post_id):
    '''Get analytics for a post (only for post owner)'''
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Must be logged in'}), 401
    
    try:
        conn = get_db()
        
        # Verify ownership
        post = conn.execute('SELECT user_id FROM posts WHERE id = ?', (post_id,)).fetchone()
        if not post or post['user_id'] != session['user_id']:
            conn.close()
            return jsonify({'success': False, 'message': 'Not authorized'}), 403
        
        # Get analytics
        reactions = conn.execute(
            'SELECT reaction_type, COUNT(*) as count FROM reactions WHERE post_id = ? GROUP BY reaction_type',
            (post_id,)
        ).fetchall()
        
        total_reactions = sum(r['count'] for r in reactions)
        total_comments = conn.execute(
            'SELECT COUNT(*) as count FROM comments WHERE post_id = ?',
            (post_id,)
        ).fetchone()['count']
        
        conn.close()
        
        analytics = {
            'post_id': post_id,
            'total_reactions': total_reactions,
            'reactions_by_type': {r['reaction_type']: r['count'] for r in reactions},
            'total_comments': total_comments
        }
        
        return jsonify({'success': True, 'analytics': analytics})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Catch-all route for React Router (must be last)
@app.route('/<path:path>')
def catch_all(path):
    return send_from_directory("templates", "index .html")

if __name__ == '__main__':
    app.run(debug=True, port=5000)
