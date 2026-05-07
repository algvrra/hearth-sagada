from flask import Flask, render_template, request, jsonify, session, send_from_directory, Response
import sqlite3, json, hashlib, uuid, math, os
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'hearth_sagada_2026_secret'
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set True if using HTTPS
GOOGLE_CLIENT_ID = "470534247051-vh1aelihkqbfoa1lrn571hfvo2reujfm.apps.googleusercontent.com"
GOOGLE_CLIENT_SECRET = "GOCSPX-IWk8KT7gdRw9qh_NR1zMkKtYGex"
DB = 'hearth_sagada.db'

SAGADA_LAT, SAGADA_LNG = 17.0867, 120.9028
TRAVEL_SPEED = {'car': 60, 'bus': 50, 'plane': 700}

CITIES = {
    "Manila":(14.5995,120.9842),"Quezon City":(14.6760,121.0437),"Makati":(14.5547,121.0244),
    "Pasig":(14.5764,121.0851),"Taguig":(14.5176,121.0509),"Caloocan":(14.6500,120.9667),
    "Mandaluyong":(14.5794,121.0359),"Parañaque":(14.4793,121.0198),
    "Baguio":(16.4023,120.5960),"Vigan":(17.5747,120.3869),"Laoag":(18.1978,120.5937),
    "San Fernando (La Union)":(16.6159,120.3167),"Dagupan":(16.0430,120.3330),
    "Urdaneta":(15.9754,120.5712),"Cabanatuan":(15.4890,120.9726),
    "Angeles":(15.1450,120.5887),"Olongapo":(14.8292,120.2828),
    "Batangas City":(13.7565,121.0583),"Lucena":(13.9373,121.6170),
    "Legazpi":(13.1391,123.7438),"Naga":(13.6192,123.1814),
    "Cebu":(10.3157,123.8854),"Iloilo":(10.7202,122.5621),"Bacolod":(10.6407,122.9457),
    "Tacloban":(11.2543,124.9966),"Dumaguete":(9.3068,123.3054),"Tagbilaran":(9.6500,123.8500),
    "Davao":(7.1907,125.4553),"Cagayan de Oro":(8.4542,124.6319),"Zamboanga":(6.9214,122.0790),
    "General Santos":(6.1164,125.1716),"Iligan":(8.2280,124.2452),
    "Butuan":(8.9475,125.5406),"Cotabato":(7.2047,124.2310),
}

def haversine(lat1,lon1,lat2,lon2):
    R=6371; p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def get_db():
    conn=sqlite3.connect(DB); conn.row_factory=sqlite3.Row; return conn

def init_db():
    conn=sqlite3.connect(DB); c=conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL DEFAULT '', avatar TEXT DEFAULT '',
            role TEXT DEFAULT 'user', google_id TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, description TEXT, price REAL NOT NULL,
            rating REAL DEFAULT 4.5, reviews INTEGER DEFAULT 0,
            location TEXT DEFAULT 'Sagada, Mtn. Province',
            max_guests INTEGER DEFAULT 4, pet_friendly INTEGER DEFAULT 0,
            pet_policy TEXT DEFAULT '', meal_included TEXT DEFAULT 'breakfast',
            amenities TEXT, photos TEXT DEFAULT '[]', available INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER, meal_type TEXT,
            dish_name TEXT, description TEXT,
            UNIQUE(room_id, meal_type, dish_name),
            FOREIGN KEY (room_id) REFERENCES rooms(id));
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_ref TEXT UNIQUE NOT NULL, user_id INTEGER, room_id INTEGER,
            checkin TEXT NOT NULL, checkout TEXT NOT NULL,
            adults INTEGER DEFAULT 1, children INTEGER DEFAULT 0,
            total_price REAL, payment_method TEXT DEFAULT 'person',
            status TEXT DEFAULT 'pending_deposit', cancellation_fee REAL DEFAULT 0,
            deposit_paid INTEGER DEFAULT 0, deposit_receipt TEXT DEFAULT '',
            travel_hours REAL DEFAULT 0, origin_city TEXT DEFAULT '',
            transport TEXT DEFAULT 'car', split_guests TEXT DEFAULT '[]',
            meal_plan TEXT DEFAULT 'with',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id));
    ''')
    ap=hashlib.sha256('admin123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (name,email,password,role) VALUES (?,?,?,?)",('Admin','admin@hearth.com',ap,'admin'))
    up=hashlib.sha256('user123'.encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (name,email,password,role) VALUES (?,?,?,?)",('Juan dela Cruz','juan@email.com',up,'user'))
    rooms=[
        ('Sumaguing Cave Room',
         'A uniquely designed room featuring stone-textured walls and earthy tones to mimic the natural beauty of Sagada\'s famous caves. This ground-floor unit offers a cool, quiet atmosphere and is the perfect "base camp" for adventurers planning an early morning spelunking trip.',
         2500,4.5,128,4,0,'','breakfast,dinner',
         '["WiFi","Stone Interiors","Hot Shower","Cave Access"]',
         '["/static/sumaguing1.png","/static/sumaguing2.png","/static/sumaguing3.png","/static/sumaguing4.png"]',
         'South Road, Ambasing, Sagada (near the Lumiang-Sumaguing Cave entrance)'),
        ('Inandakos BnB',
         'A family-owned bed and breakfast located on a quiet ridge away from the busy main road. Famous for its large French windows, authentic wooden interiors, and stunning views of cathedral rock formations and pine forests.',
         3200,4.7,95,4,0,'','breakfast',
         '["WiFi","French Windows","Pine Forest View","Wooden Interiors"]',
         '["/static/Inandakos1.png","/static/Inandakos2.png","/static/Inandakos3.png","/static/Inandakos4.png"]',
         'Sitio Kinlibed, Barangay Dagdag, Sagada'),
        ('Kanip-aw Pines View',
         'This lodge is tucked into a pine-filled slope, offering guests a direct view of the mountain valleys. Popular for its large communal spaces and affordable, cozy rooms that capture the chilly mountain atmosphere.',
         4500,4.8,200,6,1,'Pet-friendly lodge with communal garden. Dogs & cats welcome. Please inform us in advance.','breakfast,lunch,dinner',
         '["WiFi","Valley View","Communal Lounge","Pine Terrace"]',
         '["/static/kanipaw1.png","/static/kanipaw2.png","/static/kanipaw3.png","/static/kanipaw4.png"]',
         'Kinlibed, Barangay Dagdag, Sagada (near the Lemon Pie House)'),
        ('Agape Log Cabin',
         'A classic 3-star log cabin guest house known for its warm, rustic charm and hospitable service. Features rooms with mountain views and is conveniently located steps away from the Sagada Public Market and the Lemon Pie House.',
         2800,4.6,74,3,0,'','breakfast',
         '["WiFi","Log Cabin","Mountain View","Market Nearby"]',
         '["/static/agape1.png","/static/agape2.png","/static/agape3.png","/static/agape4.png"]',
         'South Road, Dagdag, Sagada'),
        ('Bomod-ok Falls Cabin',
         'A rustic, standalone wooden cabin located at the edge of the northern cliffs. Features a private balcony where you can hear the distant rush of the "Big Falls." A favorite for hikers who want to stay close to the trail leading down to the Bomod-ok natural pools.',
         3800,4.9,310,5,1,'Small pets only (under 10kg). ₱300 deposit, refundable after checkout inspection.','breakfast,lunch',
         '["WiFi","Private Balcony","Cliff Edge","Hiking Trail Access"]',
         '["/static/bomodok1.png","/static/bomodok2.png","/static/bomodok3.png","/static/bomodok4.png"]',
         'Barangay Fidelisan, Northern Sagada (near the rice terrace trail)'),
        ('Isabelo\'s Inn',
         'A centrally located inn and cafe with cozy wooden interiors and a cabin-like feel. It serves as an ideal hub for travelers due to its proximity to the bus terminal, market, and cultural sites like the Ganduyan Museum.',
         2200,4.4,56,3,0,'','breakfast',
         '["WiFi","Cafe On-site","Central Location","Wooden Interiors"]',
         '["/static/isabelo1.png","/static/isabelo2.png","/static/isabelo3.png","/static/isabelo4.png"]',
         'Poblacion, Sagada (Town Proper)'),
        ('Shamrock Tavern',
         'A long-standing landmark in the town proper, known as a social hub for backpackers. Offers basic, budget-friendly rooms and features a balcony overlooking the bustling town center.',
         1800,4.2,88,4,0,'','breakfast',
         '["WiFi","Town Balcony","Budget-Friendly","Backpacker Hub"]',
         '["/static/shamrock1.png","/static/shamrock2.png","/static/shamrock3.png","/static/shamrock4.png"]',
         'Poblacion, Sagada (near the main intersection/bus stop)'),
        ('Lake Danum Nook',
         'A small, intimate cottage designed specifically for couples and sunset lovers. Located 4km away from the busy town center, this "nook" offers a peaceful lakeside view and easy access to the most famous sunset viewing spot in the Mountain Province.',
         3500,4.7,42,2,0,'','breakfast,dinner',
         '["WiFi","Lake View","Sunset Deck","Romantic Setting"]',
         '["/static/lakedanum1.png","/static/lakedanum2.png","/static/lakedanum3.png","/static/lakedanum4.png"]',
         'Besao Road, Western Sagada (overlooking the lake)'),
        ('Marlboro Hills Attic',
         'A spacious, high-ceiling loft designed for large groups and families. Features multiple floor mattresses and large windows facing the east, allowing guests to wake up to the famous "Sea of Clouds" view without even leaving their room.',
         5500,4.8,63,8,0,'','breakfast,lunch',
         '["WiFi","Sea of Clouds View","Loft Style","Group Friendly"]',
         '["/static/marlboro1.png","/static/marlboro2.png","/static/marlboro3.png","/static/marlboro4.png"]',
         'Eastern Ridge, Barangay Sta. Monica, Sagada'),
        ('The Shire of Sagada',
         'A unique, Hobbit-themed accommodation featuring distinctive round doors and earthy architecture. Offers a higher-end, whimsical stay with cozy interiors inspired by fantasy settings, nestled in a quiet area near the caves.',
         4800,4.9,175,4,0,'','breakfast,dinner',
         '["WiFi","Round Doors","Hobbit Theme","Fireplace"]',
         '["/static/shire1.png","/static/shire2.png","/static/shire3.png","/static/shire4.png"]',
         'South Road, Ambasing, Sagada, Mountain Province'),
        ('St. Joseph\'s Resthouse',
         'One of the most iconic and historic lodging houses in Sagada, managed by the Episcopal Church. Located on a hill right next to the Church of Saint Mary the Virgin, offering a peaceful, heritage-rich environment with sprawling gardens.',
         2600,4.6,220,5,0,'','breakfast',
         '["WiFi","Heritage Site","Garden","Cathedral Views"]',
         '["/static/stjoseph1.png","/static/stjoseph2.png","/static/stjoseph3.png","/static/stjoseph4.png"]',
         'Cathedral Hill, Poblacion, Sagada'),
        ('See Too Ville, Gaia Villa',
         'A charming nature retreat focused on relaxation and stunning vistas. Every room is equipped with a private balcony providing panoramic views of the Sagada mountain ranges. Also famous for its proximity to the ridge used in the film That Thing Called Tadhana, offering serene sunset views.',
         3900,4.7,98,4,0,'','breakfast,dinner',
         '["WiFi","Private Balcony","Panoramic Views","Eco-Friendly"]',
         '["/static/seetoo1.png","/static/seetoo2.png","/static/seetoo3.png","/static/seetoo4.png"]',
         'South Road, Ambasing, Sagada (near the Gaia Sagada Cafe)'),
        ('Mapiya-aw Pension',
         'A family-style pension inn located in a slightly elevated area, offering privacy and peace. Each room features a private terrace for soaking in the mountain air, and is known for having ample parking for those driving to Sagada.',
         2400,4.5,67,4,0,'','breakfast',
         '["WiFi","Private Terrace","Ample Parking","Mountain Air"]',
         '["/static/mapiyaaw1.png","/static/mapiyaaw2.png","/static/mapiyaaw3.png","/static/mapiyaaw4.png"]',
         'South Road, near the border of Poblacion and Dagdag'),
    ]
    # Re-seed rooms every startup so name/description/photo changes always apply
    c.execute("DELETE FROM rooms")
    # Clear all bookings on startup — fresh start
    c.execute("DELETE FROM bookings")
    conn.commit()
    for r in rooms:
        name,description,price,rating,reviews,max_guests,pet_friendly,pet_policy,meal_included,amenities,photos,location = r
        c.execute("INSERT INTO rooms (name,description,price,rating,reviews,location,max_guests,pet_friendly,pet_policy,meal_included,amenities,photos) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                  (name,description,price,rating,reviews,location,max_guests,pet_friendly,pet_policy,meal_included,amenities,photos))
    # Meals start empty — admin inputs dishes per room per day via the Admin Panel
    # Do NOT wipe existing meals on restart so admin entries are preserved
    # Migrate existing DBs: add meal_plan column if missing
    try:
        c.execute("ALTER TABLE bookings ADD COLUMN meal_plan TEXT DEFAULT 'with'")
        conn.commit()
    except:
        pass  # Column already exists
    # Migrate meals table: remove date column and duplicates if old schema exists
    try:
        cols = [row[1] for row in c.execute("PRAGMA table_info(meals)").fetchall()]
        if 'date' in cols:
            # Recreate meals table without date, keeping only unique rows
            c.executescript('''
                CREATE TABLE IF NOT EXISTS meals_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room_id INTEGER, meal_type TEXT,
                    dish_name TEXT, description TEXT,
                    UNIQUE(room_id, meal_type, dish_name));
                INSERT OR IGNORE INTO meals_new (room_id, meal_type, dish_name, description)
                    SELECT room_id, meal_type, dish_name, description FROM meals;
                DROP TABLE meals;
                ALTER TABLE meals_new RENAME TO meals;
            ''')
            conn.commit()
    except:
        pass
    # Migrate old DBs: ensure available column exists on rooms
    try:
        c.execute("ALTER TABLE rooms ADD COLUMN available INTEGER DEFAULT 1")
        conn.commit()
    except:
        pass  # Column already exists
    # Fix any rooms where available is NULL
    c.execute("UPDATE rooms SET available=1 WHERE available IS NULL")
    conn.commit()
    # Ensure all seeded rooms are visible (available=1)
    c.execute("UPDATE rooms SET available=1 WHERE available IS NULL OR available=0")
    conn.commit(); conn.close()

@app.route('/api/register',methods=['POST'])
def register():
    d=request.json or {}
    if not d.get('name') or not d.get('email') or not d.get('password'):
        return jsonify({'success':False,'error':'All fields required'}),400
    pw=hashlib.sha256(d['password'].encode()).hexdigest()
    try:
        conn=get_db()
        conn.execute("INSERT INTO users (name,email,password) VALUES (?,?,?)",(d['name'].strip(),d['email'].strip().lower(),pw))
        conn.commit(); conn.close(); return jsonify({'success':True})
    except: return jsonify({'success':False,'error':'Email already registered'}),400

@app.route('/api/login',methods=['POST'])
def login():
    d=request.json or {}
    if not d.get('email') or not d.get('password'):
        return jsonify({'success':False,'error':'Email and password required'}),400
    pw=hashlib.sha256(d['password'].encode()).hexdigest()
    conn=get_db()
    user=conn.execute("SELECT * FROM users WHERE email=? AND password=?",(d['email'].strip().lower(),pw)).fetchone()
    conn.close()
    if user:
        session['user_id']=user['id']; session['role']=user['role']
        session['name']=user['name']; session['avatar']=user['avatar'] or ''
        return jsonify({'success':True,'role':user['role'],'name':user['name'],'avatar':user['avatar'] or ''})
    return jsonify({'success':False,'error':'Incorrect email or password'}),401

@app.route('/api/google-login',methods=['POST'])
def google_login():
    d=request.json or {}
    if not d.get('email'): return jsonify({'success':False,'error':'Invalid Google data'}),400
    conn=get_db()
    user=conn.execute("SELECT * FROM users WHERE email=?",(d['email'],)).fetchone()
    if not user:
        conn.execute("INSERT INTO users (name,email,password,avatar,google_id) VALUES (?,?,?,?,?)",(d.get('name','Google User'),d['email'],'',d.get('avatar',''),d.get('google_id','')))
        conn.commit(); user=conn.execute("SELECT * FROM users WHERE email=?",(d['email'],)).fetchone()
    conn.close()
    session['user_id']=user['id']; session['role']=user['role']
    session['name']=user['name']; session['avatar']=user['avatar'] or d.get('avatar','')
    return jsonify({'success':True,'role':user['role'],'name':user['name'],'avatar':user['avatar'] or ''})

@app.route('/api/logout',methods=['POST'])
def logout():
    session.clear(); return jsonify({'success':True})

@app.route('/api/me')
def me():
    if 'user_id' not in session: return jsonify({'logged_in':False})
    return jsonify({'logged_in':True,'name':session.get('name'),'role':session.get('role'),'avatar':session.get('avatar','')})

@app.route('/api/rooms')
def get_rooms():
    conn=get_db(); q="SELECT * FROM rooms"; params=[]
    filters=[]
    if request.args.get('pet_friendly')=='1': filters.append("pet_friendly=1")
    filters.append("(available=1 OR available IS NULL)")
    if filters: q+=" WHERE "+" AND ".join(filters)
    rows=conn.execute(q,params).fetchall(); conn.close()
    return jsonify([dict(r) for r in rows])

@app.route('/api/rooms/<int:rid>')
def get_room(rid):
    conn=get_db()
    room=conn.execute("SELECT * FROM rooms WHERE id=?",(rid,)).fetchone()
    if not room: conn.close(); return jsonify({'error':'Not found'}),404
    meals=conn.execute("SELECT * FROM meals WHERE room_id=? ORDER BY meal_type",(rid,)).fetchall()
    conn.close(); r=dict(room); r['meals']=[dict(m) for m in meals]; return jsonify(r)

@app.route('/api/rooms/<int:rid>/booked-dates')
def booked_dates(rid):
    conn=get_db()
    bks=conn.execute("SELECT checkin,checkout FROM bookings WHERE room_id=? AND status='confirmed'",(rid,)).fetchall()
    conn.close(); dates=[]
    for b in bks:
        cur=datetime.strptime(b['checkin'],'%Y-%m-%d'); end=datetime.strptime(b['checkout'],'%Y-%m-%d')
        while cur<=end: dates.append(cur.strftime('%Y-%m-%d')); cur+=timedelta(days=1)
    return jsonify(dates)

@app.route('/api/rooms/<int:rid>/meals')
def room_meals(rid):
    conn=get_db()
    meals=conn.execute("SELECT * FROM meals WHERE room_id=? ORDER BY meal_type",(rid,)).fetchall()
    conn.close(); return jsonify([dict(m) for m in meals])

@app.route('/api/bookings',methods=['POST'])
def create_booking():
    if 'user_id' not in session: return jsonify({'error':'Please login first'}),401
    d=request.json or {}
    if not d.get('room_id') or not d.get('checkin') or not d.get('checkout'):
        return jsonify({'error':'Missing required fields'}),400
    conn=get_db()
    room=conn.execute("SELECT * FROM rooms WHERE id=?",(d['room_id'],)).fetchone()
    if not room: conn.close(); return jsonify({'error':'Room not found'}),404
    checkin=datetime.strptime(d['checkin'],'%Y-%m-%d'); checkout=datetime.strptime(d['checkout'],'%Y-%m-%d')
    nights=max(1,(checkout-checkin).days); adults=max(1,int(d.get('adults',1)))
    base_total=room['price']*nights
    # Meal plan pricing: base price = no meal; +20% with meal, -20% without meal
    meal_plan=d.get('meal_plan','with')
    if meal_plan=='with':
        total=round(base_total*1.20,2)
    else:
        total=round(base_total*0.80,2)
    ref=f"HB{checkin.strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    origin=d.get('origin_city',''); transport=d.get('transport','car')
    travel_hours=0; dist_km=0
    if origin in CITIES:
        lat,lng=CITIES[origin]; dist_km=round(haversine(lat,lng,SAGADA_LAT,SAGADA_LNG),1)
        travel_hours=round(dist_km/TRAVEL_SPEED.get(transport,60),1)
    allowed_payments = ['person', 'gcash']
    payment_method = d.get('payment_method', 'person')
    if payment_method not in allowed_payments:
        payment_method = 'person'
    # Pay in Person → pending_deposit until ₱500 deposit is uploaded
    # GCash → confirmed immediately (full payment sent)
    initial_status = 'pending_deposit' if payment_method == 'person' else 'confirmed'
    conn.execute('''INSERT INTO bookings
        (booking_ref,user_id,room_id,checkin,checkout,adults,children,
         total_price,payment_method,status,travel_hours,origin_city,transport,split_guests,meal_plan)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (ref,session['user_id'],d['room_id'],d['checkin'],d['checkout'],
         adults,int(d.get('children',0)),total,payment_method,initial_status,
         travel_hours,origin,transport,json.dumps(d.get('split_guests',[])),meal_plan))
    conn.commit(); conn.close()
    return jsonify({'success':True,'booking_ref':ref,'total':total,'travel_hours':travel_hours,'dist_km':dist_km,'nights':nights})

@app.route('/api/bookings/my')
def my_bookings():
    if 'user_id' not in session: return jsonify([])
    conn=get_db()
    rows=conn.execute('''SELECT b.*,r.name as room_name FROM bookings b
        JOIN rooms r ON b.room_id=r.id WHERE b.user_id=? ORDER BY b.created_at DESC''',(session['user_id'],)).fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route('/api/bookings/<ref>/cancel',methods=['POST'])
def cancel_booking(ref):
    if 'user_id' not in session: return jsonify({'error':'Not authenticated'}),401
    conn=get_db(); bk=conn.execute("SELECT * FROM bookings WHERE booking_ref=?",(ref,)).fetchone()
    if not bk: conn.close(); return jsonify({'error':'Not found'}),404
    if bk['user_id']!=session['user_id'] and session.get('role')!='admin':
        conn.close(); return jsonify({'error':'Unauthorized'}),403
    # 48-hour free cancellation window
    checkin=datetime.strptime(bk['checkin'],'%Y-%m-%d')
    hours_until = (checkin - datetime.now()).total_seconds() / 3600
    room=conn.execute("SELECT price FROM rooms WHERE id=?",(bk['room_id'],)).fetchone()
    one_night=float(room['price']) if room else 0
    deposit=500.0
    deposit_was_paid = bool(bk['deposit_paid'])
    if hours_until >= 48 or not deposit_was_paid:
        # Free cancellation OR deposit was never actually received — no fee
        cancellation_fee=0
        late=False
    else:
        # Late cancellation AND deposit was confirmed — keep ₱500 as cancellation fee
        cancellation_fee=deposit
        late=True
    refund=float(bk['total_price'])
    conn.execute("UPDATE bookings SET status='cancelled',cancellation_fee=? WHERE booking_ref=?",(cancellation_fee,ref))
    conn.commit(); conn.close()
    return jsonify({'success':True,'cancellation_fee':cancellation_fee,'refund':refund,'late_cancel':late,'one_night_rate':one_night})

@app.route('/api/bookings/<ref>/upload-receipt',methods=['POST'])
def upload_receipt(ref):
    if 'user_id' not in session: return jsonify({'error':'Not authenticated'}),401
    conn=get_db(); bk=conn.execute("SELECT * FROM bookings WHERE booking_ref=?",(ref,)).fetchone()
    if not bk: conn.close(); return jsonify({'error':'Not found'}),404
    if bk['user_id']!=session['user_id']: conn.close(); return jsonify({'error':'Unauthorized'}),403
    d=request.json or {}
    receipt_note=d.get('receipt_note','Receipt submitted').strip()
    conn.execute("UPDATE bookings SET deposit_receipt=? WHERE booking_ref=?",(receipt_note,ref))
    conn.commit(); conn.close()
    return jsonify({'success':True,'message':'Receipt submitted! Admin will confirm your booking shortly.'})

@app.route('/api/admin/bookings/<ref>/confirm-deposit',methods=['POST'])
def confirm_deposit(ref):
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    conn.execute("UPDATE bookings SET status='confirmed',deposit_paid=1 WHERE booking_ref=?",(ref,))
    conn.commit(); conn.close()
    return jsonify({'success':True})

def require_admin(): return session.get('role')=='admin'

@app.route('/api/admin/stats')
def admin_stats():
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    def q(sql,*args): return conn.execute(sql,args).fetchone()[0]
    total=q("SELECT COUNT(*) FROM bookings")
    confirmed=q("SELECT COUNT(*) FROM bookings WHERE status='confirmed'")
    pending=q("SELECT COUNT(*) FROM bookings WHERE status='pending_deposit'")
    cancelled=q("SELECT COUNT(*) FROM bookings WHERE status='cancelled'")
    completed=q("SELECT COUNT(*) FROM bookings WHERE status='completed'")
    revenue=q("SELECT COALESCE(SUM(total_price),0) FROM bookings WHERE status IN ('confirmed','completed')")
    cancel_fees=q("SELECT COALESCE(SUM(cancellation_fee),0) FROM bookings WHERE status='cancelled'")
    users=q("SELECT COUNT(*) FROM users WHERE role='user'")
    popular=conn.execute('''SELECT r.name,COUNT(*) as c FROM bookings b
        JOIN rooms r ON b.room_id=r.id GROUP BY r.id ORDER BY c DESC LIMIT 1''').fetchone()
    monthly=conn.execute('''SELECT strftime('%m',created_at) as mo,COUNT(*) as c,
        COALESCE(SUM(total_price),0) as rev FROM bookings
        WHERE status IN ('confirmed','completed') GROUP BY mo ORDER BY mo''').fetchall()
    recent=conn.execute('''SELECT b.booking_ref,u.name as guest,r.name as room,
        b.checkin,b.checkout,b.total_price,b.status FROM bookings b
        JOIN users u ON b.user_id=u.id JOIN rooms r ON b.room_id=r.id
        ORDER BY b.created_at DESC LIMIT 5''').fetchall()
    conn.close()
    return jsonify({'total':total,'confirmed':confirmed,'pending':pending,'cancelled':cancelled,'completed':completed,
        'revenue':float(revenue),'cancel_fees':float(cancel_fees),'users':users,
        'popular':dict(popular) if popular else {},'monthly':[dict(m) for m in monthly],
        'recent':[dict(r) for r in recent]})

@app.route('/api/admin/bookings')
def admin_bookings():
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    rows=conn.execute('''SELECT b.*,r.name as room_name,u.name as user_name,u.email as user_email
        FROM bookings b JOIN rooms r ON b.room_id=r.id JOIN users u ON b.user_id=u.id
        ORDER BY b.created_at DESC''').fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route('/api/admin/bookings/<ref>/complete',methods=['POST'])
def complete_booking(ref):
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    conn.execute("UPDATE bookings SET status='completed' WHERE booking_ref=?",(ref,))
    conn.commit(); conn.close(); return jsonify({'success':True})

@app.route('/api/admin/users')
def admin_users():
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    rows=conn.execute("SELECT id,name,email,role,created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route('/api/admin/rooms',methods=['GET'])
def admin_rooms():
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db(); rows=conn.execute("SELECT * FROM rooms").fetchall()
    conn.close(); return jsonify([dict(r) for r in rows])

@app.route('/api/admin/rooms/<int:rid>/toggle',methods=['POST'])
def toggle_room(rid):
    if not require_admin(): return jsonify({'error':'Unauthorized'}),403
    conn=get_db()
    conn.execute("UPDATE rooms SET available=CASE WHEN available=1 THEN 0 ELSE 1 END WHERE id=?",(rid,))
    conn.commit(); conn.close(); return jsonify({'success':True})


@app.route('/api/travel-time',methods=['POST'])
def calc_travel_time():
    d=request.json or {}; origin=d.get('city',''); transport=d.get('transport','car')
    if origin not in CITIES: return jsonify({'error':'City not found'}),404
    lat,lng=CITIES[origin]; dist=round(haversine(lat,lng,SAGADA_LAT,SAGADA_LNG),1)
    speed=TRAVEL_SPEED.get(transport,60); hours=dist/speed; h=int(hours); m=int((hours-h)*60)
    eta_str=f"{h}h {m}min" if h>0 else f"{m}min"
    notes={'plane':'✈️ Fly to Manila or Baguio, then take a bus/van to Sagada (~5–8 hrs from Baguio).','bus':'🚌 Take a bus to Baguio then connect via jeepney or van to Sagada.','car':'🚗 Drive via Halsema Highway from Baguio. Road conditions may vary.'}
    return jsonify({'distance_km':dist,'travel_hours':round(hours,1),'eta':eta_str,'note':notes.get(transport,'')})

@app.route('/api/cities')
def get_cities(): return jsonify(list(CITIES.keys()))

@app.route('/api/split',methods=['POST'])
def split_bill():
    d=request.json or {}; total=float(d.get('total',0))
    guests=[g.strip() for g in d.get('guests',[]) if g.strip()]
    if not guests or total<=0: return jsonify({'error':'Invalid data'}),400
    per=round(total/len(guests),2)
    return jsonify([{'name':g,'amount':per,'ref':str(uuid.uuid4())[:8].upper()} for g in guests])

@app.route('/videos/<path:filename>')
def serve_video(filename):
    video_path = os.path.join('videos', filename)
    if not os.path.exists(video_path):
        return 'Video not found', 404

    file_size = os.path.getsize(video_path)
    range_header = request.headers.get('Range', None)

    if not range_header:
        # No range request — send whole file
        def generate():
            with open(video_path, 'rb') as f:
                while chunk := f.read(1024 * 1024):
                    yield chunk
        return Response(generate(), status=200, mimetype='video/mp4',
            headers={'Content-Length': str(file_size), 'Accept-Ranges': 'bytes'})

    # Parse Range header e.g. bytes=0-1023
    byte_start, byte_end = 0, None
    match = range_header.replace('bytes=', '').split('-')
    byte_start = int(match[0]) if match[0] else 0
    byte_end   = int(match[1]) if match[1] else file_size - 1
    byte_end   = min(byte_end, file_size - 1)
    length     = byte_end - byte_start + 1

    def generate_chunk():
        with open(video_path, 'rb') as f:
            f.seek(byte_start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return Response(generate_chunk(), status=206, mimetype='video/mp4',
        headers={
            'Content-Range':  f'bytes {byte_start}-{byte_end}/{file_size}',
            'Content-Length': str(length),
            'Accept-Ranges':  'bytes',
        })

@app.route('/')
def index(): return send_from_directory('templates', 'index.html')

if __name__=='__main__':
    init_db(); app.run(debug=True,port=5000)
