# main.py - PostgreSQL Compatible Version (Works with both SQLite and PostgreSQL)
from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os
from datetime import datetime
from pathlib import Path
import io
import zipfile
import sys
import base64
import json
import hashlib
import time
import re
import asyncio
from typing import Optional

# ==================== DATABASE MODE DETECTION ====================
DATABASE_URL = os.environ.get('DATABASE_URL', '')
USE_POSTGRES = DATABASE_URL != ''

# Only import asyncpg if we're using PostgreSQL
if USE_POSTGRES:
    import asyncpg
    print("✅ asyncpg loaded for PostgreSQL support")
else:
    print("📁 Using SQLite (no asyncpg needed)")

print(f"🔧 Database mode: {'PostgreSQL (Production)' if USE_POSTGRES else 'SQLite (Development)'}")


# ==================== PATH FUNCTIONS ====================
def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).parent.absolute()

def get_template_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "templates"
    else:
        return Path(__file__).parent / "templates"

def get_static_path():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "static"
    else:
        return Path(__file__).parent / "static"

# ==================== CREATE APP ====================
app = FastAPI()

# Add CORS for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== SETUP DIRECTORIES ====================
BASE_DIR = get_base_dir()
TEMPLATES_DIR = get_template_path()
STATIC_DIR = get_static_path()

if not getattr(sys, 'frozen', False):
    STATIC_DIR.mkdir(exist_ok=True)
    TEMPLATES_DIR.mkdir(exist_ok=True)


# ==================== MOUNT STATIC FILES ====================
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ==================== DATABASE SETUP ====================
DB_PATH = BASE_DIR / "school.db"

# Simple cache
class SimpleCache:
    def __init__(self, default_ttl=300):
        self._cache = {}
        self._default_ttl = default_ttl
    
    def get(self, key):
        if key in self._cache:
            item = self._cache[key]
            if time.time() < item['expires']:
                return item['value']
            else:
                del self._cache[key]
        return None
    
    def set(self, key, value, ttl=None):
        ttl = ttl or self._default_ttl
        self._cache[key] = {'value': value, 'expires': time.time() + ttl}
    
    def delete(self, key=None):
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

cache = SimpleCache()

# ==================== DATABASE CONNECTION FUNCTIONS ====================
async def get_postgres_connection():
    """Get PostgreSQL connection"""
    return await asyncpg.connect(DATABASE_URL)

def get_sqlite_connection():
    """Get SQLite connection"""
    conn = sqlite3.connect(str(DB_PATH))
    conn.text_factory = str
    conn.row_factory = sqlite3.Row
    return conn

async def execute_query(query: str, params: tuple = None):
    """Execute query based on database mode"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        try:
            if params:
                return await conn.fetch(query, *params)
            else:
                return await conn.fetch(query)
        finally:
            await conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            return cursor.fetchall()
        finally:
            conn.close()

async def execute_write(query: str, params: tuple = None):
    """Execute write query based on database mode"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        try:
            if params:
                return await conn.execute(query, *params)
            else:
                return await conn.execute(query)
        finally:
            await conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

async def execute_scalar(query: str, params: tuple = None):
    """Execute query and return single value"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        try:
            if params:
                result = await conn.fetchval(query, *params)
            else:
                result = await conn.fetchval(query)
            return result
        finally:
            await conn.close()
    else:
        conn = get_sqlite_connection()
        try:
            cursor = conn.cursor()
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            row = cursor.fetchone()
            return row[0] if row else None
        finally:
            conn.close()

def get_db():
    """Get SQLite connection (for backward compatibility)"""
    return get_sqlite_connection()


# ==================== DATABASE INITIALIZATION ====================
async def init_db_async():
    """Initialize database tables asynchronously for PostgreSQL"""
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        try:
            # Create tables for PostgreSQL
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS app_auth (
                    id SERIAL PRIMARY KEY,
                    is_unlocked INTEGER DEFAULT 0
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS school (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    location TEXT,
                    phone TEXT,
                    marquee TEXT
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS class_list (
                    id SERIAL PRIMARY KEY,
                    name TEXT UNIQUE,
                    description TEXT
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS teachers (
                    id SERIAL PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    email TEXT,
                    subjects TEXT,
                    class_teaching TEXT,
                    password TEXT
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS teacher_classes (
                    id SERIAL PRIMARY KEY,
                    teacher_id INTEGER,
                    class_name TEXT,
                    subject TEXT
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS students (
                    id SERIAL PRIMARY KEY,
                    first_name TEXT,
                    last_name TEXT,
                    age INTEGER,
                    parent_name TEXT,
                    parent_phone TEXT,
                    parent_email TEXT,
                    class_name TEXT,
                    subjects TEXT,
                    enrollment_date TIMESTAMP,
                    password TEXT DEFAULT 'student123',
                    birthday DATE
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS marks (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    teacher_id INTEGER,
                    subject TEXT,
                    class_test1 REAL DEFAULT 0,
                    group_work REAL DEFAULT 0,
                    project REAL DEFAULT 0,
                    class_test2 REAL DEFAULT 0,
                    exam REAL DEFAULT 0,
                    ca_score REAL DEFAULT 0,
                    exam_score REAL DEFAULT 0,
                    total REAL DEFAULT 0,
                    term TEXT,
                    year INTEGER,
                    is_locked INTEGER DEFAULT 0,
                    is_confirmed INTEGER DEFAULT 0,
                    submission_date TIMESTAMP,
                    UNIQUE(student_id, subject, term)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS exam_papers (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    teacher_id INTEGER,
                    subject TEXT,
                    term TEXT,
                    exam_year INTEGER,
                    file_name TEXT,
                    file_data TEXT,
                    file_hash TEXT,
                    uploaded_at TIMESTAMP,
                    verified INTEGER DEFAULT 0,
                    marks_match INTEGER DEFAULT 0,
                    auto_verified INTEGER DEFAULT 0,
                    confidence_score INTEGER DEFAULT 0,
                    extracted_name TEXT,
                    extracted_subject TEXT,
                    extracted_mark INTEGER,
                    verified_by INTEGER,
                    verified_at TIMESTAMP,
                    admin_override INTEGER DEFAULT 0,
                    admin_notes TEXT
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS verification_logs (
                    id SERIAL PRIMARY KEY,
                    paper_id INTEGER,
                    admin_id INTEGER,
                    action TEXT,
                    notes TEXT,
                    created_at TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS announcements (
                    id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    image_data TEXT,
                    image_type TEXT,
                    announcement_type TEXT DEFAULT 'general',
                    target_role TEXT DEFAULT 'all',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    created_by INTEGER
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS holiday_greetings (
                    id SERIAL PRIMARY KEY,
                    holiday_name TEXT NOT NULL,
                    message TEXT NOT NULL,
                    image_data TEXT,
                    image_type TEXT,
                    animation_style TEXT DEFAULT 'snow',
                    is_active INTEGER DEFAULT 0,
                    is_manual INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    activated_by INTEGER,
                    activated_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS term_completion (
                    id SERIAL PRIMARY KEY,
                    class_name TEXT,
                    term TEXT,
                    academic_year TEXT,
                    is_completed INTEGER DEFAULT 0,
                    completed_at TIMESTAMP,
                    UNIQUE(class_name, term, academic_year)
                )
            ''')
            
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS promotion_log (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER,
                    from_class TEXT,
                    to_class TEXT,
                    term TEXT,
                    academic_year TEXT,
                    promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert default data
            await conn.execute("INSERT INTO app_auth (id, is_unlocked) VALUES (1, 0) ON CONFLICT (id) DO NOTHING")
            await conn.execute("INSERT INTO school (id, name, location, phone, marquee) VALUES (1, 'School Management System', '', '', 'System designed by JSLY @ 2026') ON CONFLICT (id) DO NOTHING")
            
            # Insert sample classes
            sample_classes = ['Form 1A', 'Form 1B', 'Form 2A', 'Form 2B', 'Form 3A', 'Form 3B']
            for cls in sample_classes:
                await conn.execute("INSERT INTO class_list (name) VALUES ($1) ON CONFLICT (name) DO NOTHING", cls)
            
            # Insert sample teacher
            await conn.execute('''
                INSERT INTO teachers (id, first_name, last_name, phone, email, subjects, class_teaching, password) 
                VALUES (1, 'John', 'Smith', '1234567890', 'john@school.com', 'Math, English', 'Form 1A, Form 2A', 'teacher123')
                ON CONFLICT (id) DO NOTHING
            ''')
            
            # Insert sample student
            await conn.execute('''
                INSERT INTO students (id, first_name, last_name, age, parent_name, parent_phone, class_name, subjects, enrollment_date) 
                VALUES (1, 'James', 'Wilson', 15, 'Mr. Wilson', '1234567890', 'Form 1A', 'Math, English, Science', CURRENT_TIMESTAMP)
                ON CONFLICT (id) DO NOTHING
            ''')
            
            print("✅ PostgreSQL database initialized with all tables!")
        finally:
            await conn.close()
    else:
        # SQLite initialization
        init_sqlite_db()

def init_sqlite_db():
    """Initialize SQLite database with all tables"""
    conn = get_sqlite_connection()
    c = conn.cursor()
    
    # Create app_auth table
    c.execute("""
        CREATE TABLE IF NOT EXISTS app_auth (
            id INTEGER PRIMARY KEY,
            is_unlocked INTEGER DEFAULT 0
        )
    """)
    c.execute("INSERT OR IGNORE INTO app_auth (id, is_unlocked) VALUES (1, 0)")
    
    # Create school table
    c.execute("""
        CREATE TABLE IF NOT EXISTS school (
            id INTEGER PRIMARY KEY,
            name TEXT,
            location TEXT,
            phone TEXT,
            marquee TEXT
        )
    """)
    c.execute("INSERT OR IGNORE INTO school (id, name, location, phone, marquee) VALUES (1, 'School Management System', '', '', 'System designed by JSLY @ 2026')")
    
    # Create class_list table
    c.execute("""
        CREATE TABLE IF NOT EXISTS class_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT
        )
    """)
    
    sample_classes = ['Form 1A', 'Form 1B', 'Form 2A', 'Form 2B', 'Form 3A', 'Form 3B']
    for cls in sample_classes:
        c.execute("INSERT OR IGNORE INTO class_list (name) VALUES (?)", (cls,))
    
    # Create teachers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            phone TEXT,
            email TEXT,
            subjects TEXT,
            class_teaching TEXT,
            password TEXT
        )
    """)
    c.execute("INSERT OR IGNORE INTO teachers (id, first_name, last_name, phone, email, subjects, class_teaching, password) VALUES (1, 'John', 'Smith', '1234567890', 'john@school.com', 'Math, English', 'Form 1A, Form 2A', 'teacher123')")
    
    # Create teacher_classes table
    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER,
            class_name TEXT,
            subject TEXT
        )
    """)
    
    # Create students table
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            first_name TEXT,
            last_name TEXT,
            age INTEGER,
            parent_name TEXT,
            parent_phone TEXT,
            parent_email TEXT,
            class_name TEXT,
            subjects TEXT,
            enrollment_date TEXT,
            password TEXT DEFAULT 'student123',
            birthday TEXT
        )
    """)
    c.execute("INSERT OR IGNORE INTO students (id, first_name, last_name, age, parent_name, parent_phone, class_name, subjects, enrollment_date) VALUES (1, 'James', 'Wilson', 15, 'Mr. Wilson', '1234567890', 'Form 1A', 'Math, English, Science', '2024-01-15')")
    
    # Create marks table
    c.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            teacher_id INTEGER,
            subject TEXT,
            class_test1 REAL DEFAULT 0,
            group_work REAL DEFAULT 0,
            project REAL DEFAULT 0,
            class_test2 REAL DEFAULT 0,
            exam REAL DEFAULT 0,
            ca_score REAL DEFAULT 0,
            exam_score REAL DEFAULT 0,
            total REAL DEFAULT 0,
            term TEXT,
            year INTEGER,
            is_locked INTEGER DEFAULT 0,
            is_confirmed INTEGER DEFAULT 0,
            submission_date TEXT,
            UNIQUE(student_id, subject, term)
        )
    """)
    
    # Create exam_papers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS exam_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            teacher_id INTEGER,
            subject TEXT,
            term TEXT,
            exam_year INTEGER,
            file_name TEXT,
            file_data TEXT,
            file_hash TEXT,
            uploaded_at TEXT,
            verified INTEGER DEFAULT 0,
            marks_match INTEGER DEFAULT 0,
            auto_verified INTEGER DEFAULT 0,
            confidence_score INTEGER DEFAULT 0,
            extracted_name TEXT,
            extracted_subject TEXT,
            extracted_mark INTEGER,
            verified_by INTEGER,
            verified_at TEXT,
            admin_override INTEGER DEFAULT 0,
            admin_notes TEXT
        )
    """)
    
    # Create verification_logs table
    c.execute("""
        CREATE TABLE IF NOT EXISTS verification_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            admin_id INTEGER,
            action TEXT,
            notes TEXT,
            created_at TEXT
        )
    """)
    
    # Create announcements table
    c.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            image_data TEXT,
            image_type TEXT,
            announcement_type TEXT DEFAULT 'general',
            target_role TEXT DEFAULT 'all',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER
        )
    """)
    
    # Create holiday_greetings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS holiday_greetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            holiday_name TEXT NOT NULL,
            message TEXT NOT NULL,
            image_data TEXT,
            image_type TEXT,
            animation_style TEXT DEFAULT 'snow',
            is_active INTEGER DEFAULT 0,
            is_manual INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_by INTEGER,
            activated_at TIMESTAMP,
            expires_at TIMESTAMP
        )
    """)
    
    # Create term_completion table
    c.execute("""
        CREATE TABLE IF NOT EXISTS term_completion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT,
            term TEXT,
            academic_year TEXT,
            is_completed INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            UNIQUE(class_name, term, academic_year)
        )
    """)
    
    # Create promotion_log table
    c.execute("""
        CREATE TABLE IF NOT EXISTS promotion_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER,
            from_class TEXT,
            to_class TEXT,
            term TEXT,
            academic_year TEXT,
            promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    conn.commit()
    conn.close()
    print("✅ SQLite database initialized with all tables!")

# Run the appropriate initialization
def init_database():
    """Initialize database based on mode"""
    if USE_POSTGRES:
        import asyncio
        asyncio.run(init_db_async())
    else:
        init_sqlite_db()

# Call initialization
init_database()

# For backward compatibility with existing code
FIRST_RUN = True  # Set to True since we just initialized


# ==================== AUTH CHECK ====================
def check_auth():
    cached_auth = cache.get('is_unlocked')
    if cached_auth is not None:
        return cached_auth
    
    try:
        if USE_POSTGRES:
            conn = asyncio.run(get_postgres_connection())
            result = asyncio.run(conn.fetchval("SELECT is_unlocked FROM app_auth WHERE id=1"))
            asyncio.run(conn.close())
            is_unlocked = result == 1 if result else False
        else:
            conn = get_sqlite_connection()
            c = conn.cursor()
            c.execute("SELECT is_unlocked FROM app_auth WHERE id=1")
            res = c.fetchone()
            conn.close()
            is_unlocked = res[0] == 1 if res else False
        cache.set('is_unlocked', is_unlocked, 60)
        return is_unlocked
    except Exception as e:
        print(f"Auth error: {e}")
        return False

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    skip_paths = ["/unlock", "/static", "/favicon.ico", "/health"]
    if any(request.url.path.startswith(path) for path in skip_paths):
        return await call_next(request)
    if not check_auth():
        return RedirectResponse(url="/unlock", status_code=302)
    return await call_next(request)


# ==================== UNLOCK ROUTES ====================
@app.get("/unlock", response_class=HTMLResponse)
async def unlock_page(request: Request):
    return templates.TemplateResponse("unlock.html", {"request": request})

@app.post("/unlock")
async def unlock(password: str = Form(...)):
    DEVELOPER_PASSWORD = "HeroHero@1234"
    if password == DEVELOPER_PASSWORD:
        if USE_POSTGRES:
            conn = await get_postgres_connection()
            await conn.execute("UPDATE app_auth SET is_unlocked = 1 WHERE id = 1")
            await conn.close()
        else:
            conn = get_sqlite_connection()
            conn.execute("UPDATE app_auth SET is_unlocked = 1 WHERE id=1")
            conn.commit()
            conn.close()
        cache.set('is_unlocked', True, 60)
        return RedirectResponse(url="/", status_code=302)
    return HTMLResponse(content="<h1>Wrong Password</h1><a href='/unlock'>Try Again</a>", status_code=401)


# ==================== LOGIN ROUTES ====================
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...), role: str = Form(...)):
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        try:
            if role == "admin":
                if username == "admin" and password == "admin123":
                    return RedirectResponse(url="/admin/dashboard", status_code=302)
            elif role == "teacher":
                teacher = await conn.fetchrow("SELECT id FROM teachers WHERE first_name = $1 AND password = $2", username, password)
                if teacher:
                    return RedirectResponse(url=f"/teacher/dashboard/{teacher['id']}", status_code=302)
            elif role == "student":
                student = await conn.fetchrow("SELECT id FROM students WHERE first_name = $1 AND password = $2", username, password)
                if not student:
                    student = await conn.fetchrow("SELECT id FROM students WHERE first_name = $1 AND last_name = $2", username, password)
                if student:
                    return RedirectResponse(url=f"/student/dashboard/{student['id']}", status_code=302)
        finally:
            await conn.close()
    else:
        conn = get_sqlite_connection()
        c = conn.cursor()
        try:
            if role == "admin":
                if username == "admin" and password == "admin123":
                    return RedirectResponse(url="/admin/dashboard", status_code=302)
            elif role == "teacher":
                teacher = c.execute("SELECT id FROM teachers WHERE first_name = ? AND password = ?", (username, password)).fetchone()
                if teacher:
                    return RedirectResponse(url=f"/teacher/dashboard/{teacher[0]}", status_code=302)
            elif role == "student":
                student = c.execute("SELECT id FROM students WHERE first_name = ? AND password = ?", (username, password)).fetchone()
                if not student:
                    student = c.execute("SELECT id FROM students WHERE first_name = ? AND last_name = ?", (username, password)).fetchone()
                if student:
                    return RedirectResponse(url=f"/student/dashboard/{student[0]}", status_code=302)
        finally:
            conn.close()
    
    return HTMLResponse("Invalid credentials")

# ==================== DASHBOARD ROUTES ====================
@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin_dashboard.html", {"request": request})

@app.get("/teacher/dashboard/{teacher_id}", response_class=HTMLResponse)
async def teacher_dashboard(request: Request, teacher_id: int):
    return templates.TemplateResponse("teacher_dashboard.html", {"request": request, "teacher_id": teacher_id})

@app.get("/student/dashboard/{student_id}", response_class=HTMLResponse)
async def student_dashboard(request: Request, student_id: int):
    return templates.TemplateResponse("student_dashboard.html", {"request": request, "student_id": student_id})


# ==================== SIMPLE API ROUTES (PostgreSQL Compatible) ====================
@app.get("/api/school")
async def get_school():
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        school = await conn.fetchrow("SELECT name, location, phone, marquee FROM school WHERE id=1")
        await conn.close()
        return dict(school) if school else {"name": "School Management", "location": "", "phone": "", "marquee": ""}
    else:
        conn = get_sqlite_connection()
        school = conn.execute("SELECT name, location, phone, marquee FROM school WHERE id=1").fetchone()
        conn.close()
        return dict(school) if school else {"name": "School Management", "location": "", "phone": "", "marquee": ""}

@app.post("/api/school")
async def update_school(data: dict):
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        await conn.execute("UPDATE school SET name=$1, location=$2, phone=$3, marquee=$4 WHERE id=1",
                          data.get('name', ''), data.get('location', ''), data.get('phone', ''), data.get('marquee', ''))
        await conn.close()
    else:
        conn = get_sqlite_connection()
        conn.execute("UPDATE school SET name=?, location=?, phone=?, marquee=? WHERE id=1", 
                    (data.get('name', ''), data.get('location', ''), data.get('phone', ''), data.get('marquee', '')))
        conn.commit()
        conn.close()
    return {"success": True}

@app.get("/api/stats")
async def get_stats():
    if USE_POSTGRES:
        conn = await get_postgres_connection()
        total_students = await conn.fetchval("SELECT COUNT(*) FROM students")
        total_teachers = await conn.fetchval("SELECT COUNT(*) FROM teachers")
        total_classes = await conn.fetchval("SELECT COUNT(*) FROM class_list")
        await conn.close()
    else:
        conn = get_sqlite_connection()
        total_students = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        total_teachers = conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
        total_classes = conn.execute("SELECT COUNT(*) FROM class_list").fetchone()[0]
        conn.close()
    return {"total_students": total_students, "total_teachers": total_teachers, "total_classes": total_classes, "pending_submissions": 0}


# ==================== TEACHERS API ====================
@app.get("/api/teachers")
async def get_teachers():
    conn = get_db()
    teachers = conn.execute("SELECT id, first_name, last_name, phone, COALESCE(email, '') as email, subjects, class_teaching FROM teachers").fetchall()
    conn.close()
    return [dict(t) for t in teachers]

@app.post("/api/teachers")
async def add_teacher(data: dict):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO teachers (first_name, last_name, phone, email, subjects, class_teaching, password) VALUES (?,?,?,?,?,?,?)",
              (data['first_name'], data['last_name'], data.get('phone', ''), data.get('email', ''),
               data.get('subjects', ''), data.get('class_teaching', ''), data.get('password', 'teacher123')))
    teacher_id = c.lastrowid
    classes = [c.strip() for c in data.get('class_teaching', '').split(',') if c.strip()]
    subjects = [s.strip() for s in data.get('subjects', '').split(',') if s.strip()]
    for cls in classes:
        for subj in subjects:
            c.execute("INSERT INTO teacher_classes (teacher_id, class_name, subject) VALUES (?, ?, ?)", (teacher_id, cls, subj))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM teacher_classes WHERE teacher_id=?", (teacher_id,))
    c.execute("DELETE FROM teachers WHERE id=?", (teacher_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/teachers/{teacher_id}")
async def get_teacher(teacher_id: int):
    conn = get_db()
    teacher = conn.execute("SELECT id, first_name, last_name, phone, COALESCE(email, '') as email, subjects, class_teaching FROM teachers WHERE id=?", (teacher_id,)).fetchone()
    conn.close()
    if teacher:
        return dict(teacher)
    raise HTTPException(404, "Teacher not found")

@app.get("/api/teachers/{teacher_id}/classes")
async def get_teacher_classes(teacher_id: int):
    conn = get_db()
    classes = conn.execute("SELECT class_name, subject FROM teacher_classes WHERE teacher_id=?", (teacher_id,)).fetchall()
    conn.close()
    return [dict(c) for c in classes]

@app.put("/api/teachers/{teacher_id}")
async def update_teacher(teacher_id: int, data: dict):
    conn = get_db()
    c = conn.cursor()
    
    update_fields = []
    params = []
    for field in ['first_name', 'last_name', 'phone', 'email', 'subjects', 'class_teaching']:
        if field in data:
            update_fields.append(f"{field}=?")
            params.append(data[field])
    
    if data.get('password') and data['password'].strip():
        update_fields.append("password=?")
        params.append(data['password'])
    
    params.append(teacher_id)
    query = f"UPDATE teachers SET {', '.join(update_fields)} WHERE id=?"
    c.execute(query, params)
    
    if 'class_teaching' in data and 'subjects' in data:
        c.execute("DELETE FROM teacher_classes WHERE teacher_id=?", (teacher_id,))
        classes = [c.strip() for c in data['class_teaching'].split(',') if c.strip()]
        subjects = [s.strip() for s in data['subjects'].split(',') if s.strip()]
        for cls in classes:
            for subj in subjects:
                c.execute("INSERT INTO teacher_classes (teacher_id, class_name, subject) VALUES (?, ?, ?)", (teacher_id, cls, subj))
    
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== STUDENTS API ====================
@app.get("/api/students")
async def get_students():
    conn = get_db()
    students = conn.execute("SELECT id, first_name, last_name, age, parent_name, COALESCE(parent_phone, '') as parent_phone, COALESCE(parent_email, '') as parent_email, class_name, COALESCE(subjects, '') as subjects, COALESCE(password, 'student123') as password FROM students").fetchall()
    conn.close()
    return [dict(s) for s in students]

@app.post("/api/students")
async def add_student(data: dict):
    conn = get_db()
    # Get password or use default
    password = data.get('password', 'student123')
    birthday = data.get('birthday', None)
    
    conn.execute("""
        INSERT INTO students (first_name, last_name, age, parent_name, parent_phone, parent_email, 
                              class_name, subjects, enrollment_date, password, birthday) 
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (data['first_name'], data['last_name'], data['age'], data.get('parent_name', ''), 
          data.get('parent_phone', ''), data.get('parent_email', ''), data['class_name'], 
          data.get('subjects', ''), datetime.now().strftime('%Y-%m-%d'), password, birthday))
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== STUDENT PASSWORD MANAGEMENT ====================

@app.get("/api/students/{student_id}/password")
async def get_student_password(student_id: int):
    """Admin can view student password"""
    conn = get_db()
    try:
        result = conn.execute("SELECT password FROM students WHERE id=?", (student_id,)).fetchone()
        conn.close()
        if result:
            return {"password": result[0], "success": True}
        raise HTTPException(404, "Student not found")
    except Exception as e:
        conn.close()
        raise HTTPException(500, str(e))

@app.put("/api/students/{student_id}/password")
async def reset_student_password(student_id: int, data: dict):
    """Admin can reset student password"""
    new_password = data.get('password')
    if not new_password or len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    conn = get_db()
    try:
        conn.execute("UPDATE students SET password=? WHERE id=?", (new_password, student_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Password updated successfully"}
    except Exception as e:
        conn.close()
        raise HTTPException(500, str(e))

@app.post("/api/students/reset-password")
async def reset_student_password_by_admin(data: dict):
    """Admin can reset student password without knowing old password"""
    student_id = data.get('student_id')
    new_password = data.get('new_password')
    
    if not new_password or len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    conn = get_db()
    try:
        conn.execute("UPDATE students SET password=? WHERE id=?", (new_password, student_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Password reset successfully"}
    except Exception as e:
        conn.close()
        raise HTTPException(500, str(e))

@app.post("/api/students/change-password")
async def change_student_password(data: dict):
    """Student changes their own password"""
    student_id = data.get('student_id')
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    
    if not new_password or len(new_password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    conn = get_db()
    try:
        # Verify current password
        student = conn.execute("SELECT password FROM students WHERE id=?", (student_id,)).fetchone()
        if not student or student[0] != current_password:
            conn.close()
            raise HTTPException(401, "Current password is incorrect")
        
        # Update to new password
        conn.execute("UPDATE students SET password=? WHERE id=?", (new_password, student_id))
        conn.commit()
        conn.close()
        return {"success": True, "message": "Password changed successfully"}
    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(500, str(e))
    
    
@app.delete("/api/students/{student_id}")
async def delete_student(student_id: int):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM marks WHERE student_id=?", (student_id,))
    c.execute("DELETE FROM students WHERE id=?", (student_id,))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/students/{student_id}")
async def get_student(student_id: int):
    conn = get_db()
    student = conn.execute("SELECT id, first_name, last_name, age, parent_name, parent_phone, parent_email, class_name, subjects, COALESCE(password, 'student123') as password FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    if student:
        return dict(student)
    raise HTTPException(404, "Student not found")

@app.put("/api/students/{student_id}")
async def update_student(student_id: int, data: dict):
    conn = get_db()
    conn.execute("""UPDATE students SET first_name=?, last_name=?, age=?, parent_name=?, 
                 parent_phone=?, parent_email=?, class_name=?, subjects=? WHERE id=?""",
              (data['first_name'], data['last_name'], data['age'], data['parent_name'],
               data['parent_phone'], data.get('parent_email', ''), data['class_name'], 
               data.get('subjects', ''), student_id))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/students/by_class/{class_name}")
async def get_students_by_class(class_name: str):
    conn = get_db()
    students = conn.execute("SELECT id, first_name, last_name, age, parent_name, parent_phone, class_name, subjects FROM students WHERE class_name=?", (class_name,)).fetchall()
    conn.close()
    return [dict(s) for s in students]

# ==================== CLASSES API ====================
@app.get("/api/classes")
async def get_classes():
    conn = get_db()
    classes = conn.execute("SELECT id, name, COALESCE(description, '') as description FROM class_list").fetchall()
    conn.close()
    return [dict(c) for c in classes]

@app.post("/api/classes")
async def add_class(data: dict):
    conn = get_db()
    conn.execute("INSERT INTO class_list (name, description) VALUES (?,?)", (data['name'], data.get('description', '')))
    conn.commit()
    conn.close()
    return {"success": True}

@app.delete("/api/classes/{class_id}")
async def delete_class(class_id: int):
    conn = get_db()
    c = conn.cursor()
    class_name = c.execute("SELECT name FROM class_list WHERE id=?", (class_id,)).fetchone()
    if class_name:
        c.execute("UPDATE students SET class_name = NULL WHERE class_name=?", (class_name[0],))
    c.execute("DELETE FROM class_list WHERE id=?", (class_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== MARKS ROUTES ====================
@app.post("/api/marks")
async def save_marks(data: dict):
    conn = get_db()
    c = conn.cursor()
    
    # Check if locked
    existing = c.execute("SELECT is_locked FROM marks WHERE student_id=? AND subject=? AND term=?", 
                        (data['student_id'], data['subject'], data['term'])).fetchone()
    if existing and existing['is_locked'] == 1:
        conn.close()
        return {"error": "Marks are locked by admin", "success": False}
    
    # ========== STRICT MARKS VALIDATION ==========
    # Get values and enforce limits
    class_test1_raw = float(data.get('class_test1', 0))
    group_work_raw = float(data.get('group_work', 0))
    project_raw = float(data.get('project', 0))
    class_test2_raw = float(data.get('class_test2', 0))
    exam_raw = float(data.get('exam', 0))
    
    # Apply limits: cannot exceed max, cannot go below 0
    class_test1 = max(0, min(class_test1_raw, 30))   # Max 30
    group_work = max(0, min(group_work_raw, 20))     # Max 20
    project = max(0, min(project_raw, 20))           # Max 20
    class_test2 = max(0, min(class_test2_raw, 30))   # Max 30
    exam = max(0, min(exam_raw, 100))                 # Max 100
    
    # Check if any values were capped
    warnings = []
    if class_test1_raw > 30:
        warnings.append(f"Test 1 was {class_test1_raw} but max is 30. Capped to 30.")
    if group_work_raw > 20:
        warnings.append(f"Group Work was {group_work_raw} but max is 20. Capped to 20.")
    if project_raw > 20:
        warnings.append(f"Project was {project_raw} but max is 20. Capped to 20.")
    if class_test2_raw > 30:
        warnings.append(f"Test 2 was {class_test2_raw} but max is 30. Capped to 30.")
    if exam_raw > 100:
        warnings.append(f"Exam was {exam_raw} but max is 100. Capped to 100.")
    
    # Calculate scores
    ca_score = (class_test1 + group_work + project + class_test2) / 2
    exam_score = exam / 2
    total = ca_score + exam_score
    current_year = datetime.now().year
    
    # INSERT OR REPLACE to prevent duplicates
    c.execute("""INSERT OR REPLACE INTO marks 
                 (student_id, teacher_id, subject, class_test1, group_work, project, class_test2, exam, 
                  ca_score, exam_score, total, term, year, is_locked, is_confirmed, submission_date) 
                 VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,0,?)""",
              (data['student_id'], data['teacher_id'], data['subject'], class_test1, group_work, 
               project, class_test2, exam, ca_score, exam_score, total, data['term'], 
               current_year, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True, 
        "total": total, 
        "ca_score": ca_score, 
        "exam_score": exam_score,
        "warnings": warnings,
        "limits_applied": {
            "class_test1": {"max": 30, "original": class_test1_raw, "capped": class_test1},
            "group_work": {"max": 20, "original": group_work_raw, "capped": group_work},
            "project": {"max": 20, "original": project_raw, "capped": project},
            "class_test2": {"max": 30, "original": class_test2_raw, "capped": class_test2},
            "exam": {"max": 100, "original": exam_raw, "capped": exam}
        }
    }

@app.get("/api/marks/student/{student_id}/{term}")
async def get_student_marks(student_id: int, term: str):
    conn = get_db()
    marks = conn.execute("""SELECT id, student_id, teacher_id, subject, class_test1, group_work, project, 
                         class_test2, exam, ca_score, exam_score, total, term, is_locked, is_confirmed
                         FROM marks WHERE student_id=? AND term=?""", (student_id, term)).fetchall()
    conn.close()
    return [dict(m) for m in marks]

@app.get("/api/marks/student/{student_id}/{subject}/{term}")
async def get_student_subject_marks(student_id: int, subject: str, term: str):
    conn = get_db()
    marks = conn.execute("""SELECT id, student_id, teacher_id, subject, class_test1, group_work, project, 
                         class_test2, exam, ca_score, exam_score, total, term, is_locked, is_confirmed
                         FROM marks WHERE student_id=? AND subject=? AND term=?""", (student_id, subject, term)).fetchone()
    conn.close()
    return dict(marks) if marks else None

@app.post("/api/teacher/send_to_admin")
async def send_to_admin(data: dict):
    conn = get_db()
    conn.execute("UPDATE marks SET is_locked=1 WHERE teacher_id=? AND term=?", (data['teacher_id'], data['term']))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/teacher_submissions/{term}")
async def get_teacher_submissions(term: str):
    conn = get_db()
    submissions = conn.execute("""
        SELECT DISTINCT m.teacher_id, m.subject, t.first_name, t.last_name, 
               GROUP_CONCAT(DISTINCT tc.class_name) as class_names,
               COUNT(DISTINCT m.student_id) as student_count,
               SUM(m.total) as total_score_sum
        FROM marks m
        JOIN teachers t ON m.teacher_id = t.id
        LEFT JOIN teacher_classes tc ON t.id = tc.teacher_id AND tc.subject = m.subject
        WHERE m.term = ? AND m.is_locked = 1 AND m.is_confirmed = 0
        GROUP BY m.teacher_id, m.subject
    """, (term,)).fetchall()
    conn.close()
    return [dict(s) for s in submissions]

@app.post("/api/confirm_submission")
async def confirm_submission(data: dict):
    conn = get_db()
    conn.execute("UPDATE marks SET is_confirmed = 1 WHERE teacher_id = ? AND subject = ? AND term = ?",
                (data['teacher_id'], data['subject'], data['term']))
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== ANNOUNCEMENTS API ====================

@app.post("/api/announcements")
async def create_announcement(data: dict):
    """Admin creates an announcement with optional image"""
    conn = get_db()
    c = conn.cursor()
    
    # Handle base64 image if provided
    image_data = data.get('image_data')
    image_type = data.get('image_type')
    
    c.execute("""
        INSERT INTO announcements (title, content, image_data, image_type, announcement_type, target_role, expires_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (data['title'], data['content'], image_data, image_type, 
          data.get('announcement_type', 'general'), data.get('target_role', 'all'),
          data.get('expires_at'), data.get('created_by', 1)))
    
    announcement_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "id": announcement_id}

@app.get("/api/announcements/{role}")
async def get_announcements(role: str):
    """Get announcements for a specific role"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    announcements = c.execute("""
        SELECT id, title, content, image_data, image_type, announcement_type, created_at
        FROM announcements 
        WHERE is_active=1 AND (target_role=? OR target_role='all')
        AND (expires_at IS NULL OR expires_at > ?)
        ORDER BY created_at DESC
        LIMIT 10
    """, (role, now)).fetchall()
    
    conn.close()
    
    result = []
    for a in announcements:
        result.append({
            "id": a[0],
            "title": a[1],
            "content": a[2],
            "image_data": a[3],
            "image_type": a[4],
            "announcement_type": a[5],
            "created_at": a[6]
        })
    
    return result

@app.delete("/api/announcements/{announcement_id}")
async def delete_announcement(announcement_id: int):
    """Soft delete an announcement"""
    conn = get_db()
    conn.execute("UPDATE announcements SET is_active=0 WHERE id=?", (announcement_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== HOLIDAY GREETINGS API ====================

@app.post("/api/holiday/activate")
async def activate_holiday_greeting(data: dict):
    """Activate a holiday greeting (manual or automatic)"""
    conn = get_db()
    c = conn.cursor()
    
    holiday_name = data.get('holiday_name')
    message = data.get('message')
    image_data = data.get('image_data')
    image_type = data.get('image_type')
    is_manual = data.get('is_manual', 1)
    animation_style = data.get('animation_style', 'snow')
    expires_at = data.get('expires_at')
    
    # Deactivate all current greetings
    c.execute("UPDATE holiday_greetings SET is_active=0")
    
    # Insert new active greeting
    c.execute("""
        INSERT INTO holiday_greetings (holiday_name, message, image_data, image_type, animation_style, 
                                       is_active, is_manual, activated_by, activated_at, expires_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
    """, (holiday_name, message, image_data, image_type, animation_style,
          is_manual, data.get('activated_by', 1), datetime.now().isoformat(), expires_at))
    
    greeting_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "id": greeting_id, "holiday": holiday_name}

@app.post("/api/holiday/deactivate")
async def deactivate_holiday_greeting():
    """Deactivate current holiday greeting"""
    conn = get_db()
    conn.execute("UPDATE holiday_greetings SET is_active=0")
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/holiday/current")
async def get_current_holiday():
    """Get currently active holiday greeting"""
    conn = get_db()
    c = conn.cursor()
    
    greeting = c.execute("""
        SELECT holiday_name, message, image_data, image_type, animation_style, 
               is_manual, created_at, activated_at
        FROM holiday_greetings 
        WHERE is_active=1
        ORDER BY created_at DESC LIMIT 1
    """).fetchone()
    
    conn.close()
    
    if greeting:
        # Check if automatic holiday detection should override
        current_month = datetime.now().month
        auto_holiday = None
        
        # Automatic holiday detection
        if 12 <= current_month or current_month == 1:
            # Check if Christmas season (Dec 15 - Jan 5)
            day = datetime.now().day
            if (current_month == 12 and day >= 15) or (current_month == 1 and day <= 5):
                auto_holiday = "Merry Christmas"
            elif current_month == 1:
                auto_holiday = "Happy New Year"
        elif current_month == 3 or current_month == 4:
            # Easter period (March or April)
            auto_holiday = "Happy Easter"
        
        return {
            "holiday": greeting[0],
            "message": greeting[1],
            "image_data": greeting[2],
            "image_type": greeting[3],
            "animation_style": greeting[4],
            "is_manual": greeting[5] == 1,
            "auto_holiday": auto_holiday
        }
    
    return None

@app.get("/api/holiday/available")
async def get_available_holidays():
    """Get list of available holiday templates"""
    holidays = [
        {
            "name": "Merry Christmas",
            "default_message": "🎄 Wishing you a Merry Christmas and a Happy New Year! May this festive season bring joy and success to your academic journey. 🎅",
            "animation_style": "christmas",
            "icon": "🎄",
            "colors": ["red", "green", "gold"]
        },
        {
            "name": "Happy New Year",
            "default_message": "🎊 Happy New Year! Wishing all students, teachers, and staff a prosperous and successful year ahead! May 2024 bring you excellence! 🎉",
            "animation_style": "newyear",
            "icon": "🎊",
            "colors": ["gold", "silver", "blue"]
        },
        {
            "name": "Happy Easter",
            "default_message": "🐰 Happy Easter! May this season of renewal bring you hope, joy, and academic excellence! Christ is Risen! 🌸",
            "animation_style": "easter",
            "icon": "🐣",
            "colors": ["pink", "yellow", "purple"]
        },
        {
            "name": "Happy Birthday",
            "default_message": "🎂 Happy Birthday! Wishing you a fantastic day filled with joy and celebration! May your year ahead be blessed! 🎈",
            "animation_style": "birthday",
            "icon": "🎂",
            "colors": ["pink", "blue", "gold"]
        }
    ]
    return holidays# ==================== ANNOUNCEMENTS API ====================

@app.post("/api/announcements")
async def create_announcement(data: dict):
    """Admin creates an announcement with optional image"""
    conn = get_db()
    c = conn.cursor()
    
    # Handle base64 image if provided
    image_data = data.get('image_data')
    image_type = data.get('image_type')
    
    c.execute("""
        INSERT INTO announcements (title, content, image_data, image_type, announcement_type, target_role, expires_at, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (data['title'], data['content'], image_data, image_type, 
          data.get('announcement_type', 'general'), data.get('target_role', 'all'),
          data.get('expires_at'), data.get('created_by', 1)))
    
    announcement_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "id": announcement_id}

@app.get("/api/announcements/{role}")
async def get_announcements(role: str):
    """Get announcements for a specific role"""
    conn = get_db()
    c = conn.cursor()
    now = datetime.now().isoformat()
    
    announcements = c.execute("""
        SELECT id, title, content, image_data, image_type, announcement_type, created_at
        FROM announcements 
        WHERE is_active=1 AND (target_role=? OR target_role='all')
        AND (expires_at IS NULL OR expires_at > ?)
        ORDER BY created_at DESC
        LIMIT 10
    """, (role, now)).fetchall()
    
    conn.close()
    
    result = []
    for a in announcements:
        result.append({
            "id": a[0],
            "title": a[1],
            "content": a[2],
            "image_data": a[3],
            "image_type": a[4],
            "announcement_type": a[5],
            "created_at": a[6]
        })
    
    return result

@app.delete("/api/announcements/{announcement_id}")
async def delete_announcement(announcement_id: int):
    """Soft delete an announcement"""
    conn = get_db()
    conn.execute("UPDATE announcements SET is_active=0 WHERE id=?", (announcement_id,))
    conn.commit()
    conn.close()
    return {"success": True}

# ==================== HOLIDAY GREETINGS API ====================

@app.post("/api/holiday/activate")
async def activate_holiday_greeting(data: dict):
    """Activate a holiday greeting (manual or automatic)"""
    conn = get_db()
    c = conn.cursor()
    
    holiday_name = data.get('holiday_name')
    message = data.get('message')
    image_data = data.get('image_data')
    image_type = data.get('image_type')
    is_manual = data.get('is_manual', 1)
    animation_style = data.get('animation_style', 'snow')
    expires_at = data.get('expires_at')
    
    # Deactivate all current greetings
    c.execute("UPDATE holiday_greetings SET is_active=0")
    
    # Insert new active greeting
    c.execute("""
        INSERT INTO holiday_greetings (holiday_name, message, image_data, image_type, animation_style, 
                                       is_active, is_manual, activated_by, activated_at, expires_at)
        VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
    """, (holiday_name, message, image_data, image_type, animation_style,
          is_manual, data.get('activated_by', 1), datetime.now().isoformat(), expires_at))
    
    greeting_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return {"success": True, "id": greeting_id, "holiday": holiday_name}

@app.post("/api/holiday/deactivate")
async def deactivate_holiday_greeting():
    """Deactivate current holiday greeting"""
    conn = get_db()
    conn.execute("UPDATE holiday_greetings SET is_active=0")
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/holiday/current")
async def get_current_holiday():
    """Get currently active holiday greeting"""
    conn = get_db()
    c = conn.cursor()
    
    greeting = c.execute("""
        SELECT holiday_name, message, image_data, image_type, animation_style, 
               is_manual, created_at, activated_at
        FROM holiday_greetings 
        WHERE is_active=1
        ORDER BY created_at DESC LIMIT 1
    """).fetchone()
    
    conn.close()
    
    if greeting:
        # Check if automatic holiday detection should override
        current_month = datetime.now().month
        auto_holiday = None
        
        # Automatic holiday detection
        if 12 <= current_month or current_month == 1:
            # Check if Christmas season (Dec 15 - Jan 5)
            day = datetime.now().day
            if (current_month == 12 and day >= 15) or (current_month == 1 and day <= 5):
                auto_holiday = "Merry Christmas"
            elif current_month == 1:
                auto_holiday = "Happy New Year"
        elif current_month == 3 or current_month == 4:
            # Easter period (March or April)
            auto_holiday = "Happy Easter"
        
        return {
            "holiday": greeting[0],
            "message": greeting[1],
            "image_data": greeting[2],
            "image_type": greeting[3],
            "animation_style": greeting[4],
            "is_manual": greeting[5] == 1,
            "auto_holiday": auto_holiday
        }
    
    return None

@app.get("/api/holiday/available")
async def get_available_holidays():
    """Get list of available holiday templates"""
    holidays = [
        {
            "name": "Merry Christmas",
            "default_message": "🎄 Wishing you a Merry Christmas and a Happy New Year! May this festive season bring joy and success to your academic journey. 🎅",
            "animation_style": "christmas",
            "icon": "🎄",
            "colors": ["red", "green", "gold"]
        },
        {
            "name": "Happy New Year",
            "default_message": "🎊 Happy New Year! Wishing all students, teachers, and staff a prosperous and successful year ahead! May 2024 bring you excellence! 🎉",
            "animation_style": "newyear",
            "icon": "🎊",
            "colors": ["gold", "silver", "blue"]
        },
        {
            "name": "Happy Easter",
            "default_message": "🐰 Happy Easter! May this season of renewal bring you hope, joy, and academic excellence! Christ is Risen! 🌸",
            "animation_style": "easter",
            "icon": "🐣",
            "colors": ["pink", "yellow", "purple"]
        },
        {
            "name": "Happy Birthday",
            "default_message": "🎂 Happy Birthday! Wishing you a fantastic day filled with joy and celebration! May your year ahead be blessed! 🎈",
            "animation_style": "birthday",
            "icon": "🎂",
            "colors": ["pink", "blue", "gold"]
        }
    ]
    return holidays

# ==================== CLASS PROMOTION SYSTEM ====================

def get_next_class(current_class):
    """Get the next class name based on the current class"""
    # Define class progression mapping
    class_progression = {
        'Form 1A': 'Form 2A',
        'Form 1B': 'Form 2B',
        'Form 2A': 'Form 3A',
        'Form 2B': 'Form 3B',
        'Form 3A': 'Form 4A',
        'Form 3B': 'Form 4B',
        'Form 4A': 'Form 5A',
        'Form 4B': 'Form 5B',
        'Form 5A': 'Graduated',
        'Form 5B': 'Graduated',
        'Grade 1': 'Grade 2',
        'Grade 2': 'Grade 3',
        'Grade 3': 'Grade 4',
        'Grade 4': 'Grade 5',
        'Grade 5': 'Grade 6',
        'Grade 6': 'Grade 7',
        'Grade 7': 'Grade 8',
        'Grade 8': 'Grade 9',
        'Grade 9': 'Grade 10',
        'Grade 10': 'Graduated',
    }
    
    # Also handle classes without "Form" prefix
    if current_class not in class_progression:
        # Try to extract number and increment
        import re
        match = re.search(r'(\d+)', current_class)
        if match:
            current_num = int(match.group(1))
            next_num = current_num + 1
            next_class = current_class.replace(str(current_num), str(next_num))
            return next_class
    
    return class_progression.get(current_class, None)

def check_term_completion_status(term, academic_year):
    """Check which classes have completed all requirements for a term"""
    conn = get_db()
    c = conn.cursor()
    
    # Get all classes
    classes = c.execute("SELECT name FROM class_list").fetchall()
    completed_classes = []
    
    for cls in classes:
        class_name = cls[0]
        
        # Check if term is already marked as completed
        already_completed = c.execute("""
            SELECT id FROM term_completion 
            WHERE class_name=? AND term=? AND academic_year=? AND is_completed=1
        """, (class_name, term, academic_year)).fetchone()
        
        if already_completed:
            completed_classes.append(class_name)
            continue
        
        # Get all students in this class
        students = c.execute("SELECT id FROM students WHERE class_name=?", (class_name,)).fetchall()
        
        if len(students) == 0:
            continue
        
        # Check if all students have confirmed marks for this term
        all_confirmed = True
        for student in students:
            # Count confirmed marks for this student in this term
            confirmed_marks = c.execute("""
                SELECT COUNT(*) FROM marks 
                WHERE student_id=? AND term=? AND is_confirmed=1
            """, (student[0], term)).fetchone()[0]
            
            # Get student's subjects
            student_data = c.execute("SELECT subjects FROM students WHERE id=?", (student[0],)).fetchone()
            if student_data and student_data[0]:
                subject_count = len(student_data[0].split(','))
            else:
                subject_count = 3  # Default assumption
            
            # If student has fewer confirmed marks than subjects, not complete
            if confirmed_marks < subject_count:
                all_confirmed = False
                break
        
        if all_confirmed:
            # Mark this class as completed for this term
            c.execute("""
                INSERT OR REPLACE INTO term_completion (class_name, term, academic_year, is_completed, completed_at)
                VALUES (?, ?, ?, 1, ?)
            """, (class_name, term, academic_year, datetime.now().isoformat()))
            completed_classes.append(class_name)
    
    conn.commit()
    conn.close()
    return completed_classes

def auto_promote_students():
    """Automatically promote students after Term 3 completion"""
    current_year = datetime.now().year
    current_term = get_current_term()
    
    # Only run auto-promotion after Term 3
    if current_term != "Term 3":
        return {"promoted": 0, "message": "Auto-promotion only runs after Term 3 completion"}
    
    conn = get_db()
    c = conn.cursor()
    
    # Check which classes have completed Term 3
    completed_classes = check_term_completion_status("Term 3", current_year)
    
    promoted_count = 0
    promotion_details = []
    
    for class_name in completed_classes:
        # Check if already promoted this academic year
        already_promoted = c.execute("""
            SELECT id FROM promotion_log 
            WHERE from_class=? AND academic_year=? AND term='Term 3'
        """, (class_name, current_year)).fetchone()
        
        if already_promoted:
            continue
        
        next_class = get_next_class(class_name)
        
        if not next_class:
            promotion_details.append({
                "from_class": class_name,
                "to_class": "Graduated",
                "students_count": 0,
                "message": f"{class_name} students have graduated!"
            })
            continue
        
        if next_class == "Graduated":
            # Mark students as graduated
            students = c.execute("SELECT id, first_name, last_name FROM students WHERE class_name=?", (class_name,)).fetchall()
            
            for student in students:
                # Optionally move to a "Graduated" status or keep in current class
                # For now, we'll leave them but mark graduation in log
                c.execute("""
                    INSERT INTO promotion_log (student_id, from_class, to_class, term, academic_year, promoted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student[0], class_name, "Graduated", "Term 3", current_year, datetime.now().isoformat()))
                promoted_count += 1
            
            promotion_details.append({
                "from_class": class_name,
                "to_class": "Graduated",
                "students_count": len(students),
                "message": f"🎓 {len(students)} students graduated from {class_name}!"
            })
        else:
            # Promote students to next class
            students = c.execute("SELECT id, first_name, last_name FROM students WHERE class_name=?", (class_name,)).fetchall()
            
            for student in students:
                # Update student's class
                c.execute("UPDATE students SET class_name=? WHERE id=?", (next_class, student[0]))
                
                # Log promotion
                c.execute("""
                    INSERT INTO promotion_log (student_id, from_class, to_class, term, academic_year, promoted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (student[0], class_name, next_class, "Term 3", current_year, datetime.now().isoformat()))
                promoted_count += 1
            
            promotion_details.append({
                "from_class": class_name,
                "to_class": next_class,
                "students_count": len(students),
                "message": f"✅ {len(students)} students promoted from {class_name} to {next_class}"
            })
    
    conn.commit()
    conn.close()
    
    # Also check for manual promotion trigger
    trigger_promotion_check()
    
    return {
        "promoted": promoted_count,
        "message": f"Successfully promoted {promoted_count} students",
        "details": promotion_details,
        "term": "Term 3",
        "academic_year": current_year
    }

def trigger_promotion_check():
    """Check if promotion should be triggered (can be called manually or automatically)"""
    current_year = datetime.now().year
    current_month = datetime.now().month
    
    # Promotion typically happens in December/January after Term 3
    # You can also add a manual trigger via admin panel
    
    # For automatic check, we'll check if we're in promotion period (December - January)
    is_promotion_period = current_month == 12 or current_month == 1
    
    if is_promotion_period:
        return auto_promote_students()
    
    return {"message": "Not in promotion period", "promoted": 0}

# ==================== API ENDPOINTS FOR PROMOTION ====================

@app.get("/api/promotion/status")
async def get_promotion_status():
    """Get promotion status for all classes"""
    conn = get_db()
    c = conn.cursor()
    
    current_year = datetime.now().year
    
    # Get all classes
    classes = c.execute("SELECT name FROM class_list").fetchall()
    
    promotion_status = []
    
    for cls in classes:
        class_name = cls[0]
        
        # Get students in this class
        students = c.execute("SELECT COUNT(*) FROM students WHERE class_name=?", (class_name,)).fetchone()[0]
        
        # Check if Term 3 is completed for this class
        term_completed = c.execute("""
            SELECT is_completed, completed_at FROM term_completion 
            WHERE class_name=? AND term='Term 3' AND academic_year=?
        """, (class_name, current_year)).fetchone()
        
        # Check if already promoted
        already_promoted = c.execute("""
            SELECT COUNT(*) FROM promotion_log 
            WHERE from_class=? AND academic_year=? AND term='Term 3'
        """, (class_name, current_year)).fetchone()[0]
        
        next_class = get_next_class(class_name)
        
        # Check if all students have confirmed marks
        all_confirmed = True
        if students > 0:
            student_confirmation = c.execute("""
                SELECT COUNT(DISTINCT m.student_id) 
                FROM marks m
                JOIN students s ON m.student_id = s.id
                WHERE s.class_name=? AND m.term='Term 3' AND m.is_confirmed=1
            """, (class_name,)).fetchone()[0]
            
            all_confirmed = student_confirmation >= students
        
        promotion_status.append({
            "class_name": class_name,
            "students_count": students,
            "term_3_completed": term_completed[0] == 1 if term_completed else False,
            "term_3_completed_date": term_completed[1] if term_completed else None,
            "already_promoted": already_promoted > 0,
            "next_class": next_class,
            "all_marks_confirmed": all_confirmed,
            "can_promote": all_confirmed and not already_promoted and students > 0
        })
    
    conn.close()
    return promotion_status

@app.post("/api/promotion/class/{class_name}")
async def promote_single_class(class_name: str, data: dict = None):
    """Manually promote a specific class"""
    conn = get_db()
    c = conn.cursor()
    
    current_year = datetime.now().year
    term = data.get('term', 'Term 3') if data else 'Term 3'
    
    next_class = get_next_class(class_name)
    
    if not next_class:
        conn.close()
        return {"success": False, "error": f"Cannot determine next class for {class_name}"}
    
    # Get students
    students = c.execute("SELECT id, first_name, last_name FROM students WHERE class_name=?", (class_name,)).fetchall()
    
    if len(students) == 0:
        conn.close()
        return {"success": False, "error": "No students in this class"}
    
    promoted_count = 0
    
    for student in students:
        if next_class == "Graduated":
            # Log graduation
            c.execute("""
                INSERT INTO promotion_log (student_id, from_class, to_class, term, academic_year, promoted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student[0], class_name, "Graduated", term, current_year, datetime.now().isoformat()))
        else:
            # Update student's class
            c.execute("UPDATE students SET class_name=? WHERE id=?", (next_class, student[0]))
            
            # Log promotion
            c.execute("""
                INSERT INTO promotion_log (student_id, from_class, to_class, term, academic_year, promoted_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (student[0], class_name, next_class, term, current_year, datetime.now().isoformat()))
        
        promoted_count += 1
    
    # Mark term as completed for this class if not already
    c.execute("""
        INSERT OR REPLACE INTO term_completion (class_name, term, academic_year, is_completed, completed_at)
        VALUES (?, ?, ?, 1, ?)
    """, (class_name, term, current_year, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {
        "success": True,
        "promoted": promoted_count,
        "from_class": class_name,
        "to_class": next_class,
        "message": f"Successfully promoted {promoted_count} students from {class_name} to {next_class}"
    }

@app.post("/api/promotion/auto")
async def trigger_auto_promotion():
    """Manually trigger auto-promotion check"""
    result = auto_promote_students()
    return result

@app.get("/api/promotion/log/{class_name}")
async def get_promotion_log(class_name: str = None):
    """Get promotion history"""
    conn = get_db()
    c = conn.cursor()
    
    if class_name:
        logs = c.execute("""
            SELECT pl.*, s.first_name, s.last_name, s.email
            FROM promotion_log pl
            JOIN students s ON pl.student_id = s.id
            WHERE pl.from_class=? OR pl.to_class=?
            ORDER BY pl.promoted_at DESC
            LIMIT 100
        """, (class_name, class_name)).fetchall()
    else:
        logs = c.execute("""
            SELECT pl.*, s.first_name, s.last_name, s.email
            FROM promotion_log pl
            JOIN students s ON pl.student_id = s.id
            ORDER BY pl.promoted_at DESC
            LIMIT 100
        """).fetchall()
    
    conn.close()
    return [dict(log) for log in logs]

@app.post("/api/term/complete/{class_name}/{term}")
async def mark_term_complete(class_name: str, term: str):
    """Admin can manually mark a term as complete for a class"""
    current_year = datetime.now().year
    
    conn = get_db()
    c = conn.cursor()
    
    # Check if all students have confirmed marks
    students = c.execute("SELECT COUNT(*) FROM students WHERE class_name=?", (class_name,)).fetchone()[0]
    confirmed_marks = c.execute("""
        SELECT COUNT(DISTINCT m.student_id) 
        FROM marks m
        JOIN students s ON m.student_id = s.id
        WHERE s.class_name=? AND m.term=? AND m.is_confirmed=1
    """, (class_name, term)).fetchone()[0]
    
    if students > 0 and confirmed_marks < students:
        conn.close()
        return {
            "success": False, 
            "error": f"Not all students have confirmed marks. {confirmed_marks}/{students} students have confirmed marks."
        }
    
    c.execute("""
        INSERT OR REPLACE INTO term_completion (class_name, term, academic_year, is_completed, completed_at)
        VALUES (?, ?, ?, 1, ?)
    """, (class_name, term, current_year, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    # If this is Term 3, trigger promotion check
    if term == "Term 3":
        promotion_result = auto_promote_students()
        return {
            "success": True,
            "message": f"Term {term} marked as complete for {class_name}",
            "promotion_result": promotion_result
        }
    
    return {"success": True, "message": f"Term {term} marked as complete for {class_name}"}

# Helper function to get current term
def get_current_term():
    """Determine current term based on date"""
    month = datetime.now().month
    if month <= 4:
        return "Term 1"
    elif month <= 8:
        return "Term 2"
    else:
        return "Term 3"
    
@app.post("/api/confirm_all_submissions")
async def confirm_all_submissions(data: dict):
    conn = get_db()
    conn.execute("UPDATE marks SET is_confirmed = 1 WHERE term = ? AND is_locked = 1 AND is_confirmed = 0",
                (data['term'],))
    count = conn.total_changes
    conn.commit()
    conn.close()
    return {"success": True, "count": count}

@app.post("/api/lock_marks")
async def lock_marks(data: dict):
    conn = get_db()
    lock_value = 1 if data.get('lock', True) else 0
    conn.execute("""UPDATE marks SET is_locked = ?, is_confirmed = ? 
                 WHERE student_id IN (SELECT id FROM students WHERE class_name=?) 
                 AND term = ?""", (lock_value, lock_value, data.get('class_name'), data.get('term')))
    conn.commit()
    conn.close()
    return {"success": True}

@app.get("/api/marks_status/{class_name}/{term}")
async def get_marks_status(class_name: str, term: str):
    conn = get_db()
    c = conn.cursor()
    
    total_students = c.execute("SELECT COUNT(*) FROM students WHERE class_name=?", (class_name,)).fetchone()[0]
    locked_count = c.execute("""SELECT COUNT(DISTINCT m.student_id) FROM marks m 
                              JOIN students s ON m.student_id = s.id 
                              WHERE s.class_name=? AND m.term=? AND m.is_locked=1""", 
                              (class_name, term)).fetchone()[0]
    confirmed_count = c.execute("""SELECT COUNT(DISTINCT m.student_id) FROM marks m 
                                 JOIN students s ON m.student_id = s.id 
                                 WHERE s.class_name=? AND m.term=? AND m.is_confirmed=1""", 
                                 (class_name, term)).fetchone()[0]
    conn.close()
    
    return {
        "total_students": total_students,
        "locked_count": locked_count,
        "confirmed_count": confirmed_count,
        "is_fully_locked": locked_count == total_students and total_students > 0,
        "is_fully_confirmed": confirmed_count == total_students and total_students > 0
    }

# ==================== EXAM PAPER UPLOAD & VERIFICATION ====================
@app.post("/api/upload_exam_paper")
async def upload_exam_paper(request: Request):
    try:
        form = await request.form()
        student_id = int(form.get('student_id'))
        teacher_id = int(form.get('teacher_id'))
        subject = form.get('subject')
        term = form.get('term')
        file = form.get('file')
        
        if not file:
            return {"success": False, "error": "No file uploaded"}
        
        file_content = await file.read()
        file_name = file.filename
        file_data_base64 = base64.b64encode(file_content).decode('utf-8')
        file_hash = hashlib.md5(file_content).hexdigest()
        
        conn = get_db()
        c = conn.cursor()
        
        existing = c.execute("SELECT id FROM exam_papers WHERE student_id=? AND subject=? AND term=?", 
                            (student_id, subject, term)).fetchone()
        
        if existing:
            c.execute("""UPDATE exam_papers SET file_name=?, file_data=?, file_hash=?, uploaded_at=?, 
                         verified=0, marks_match=0, verified_by=NULL, verified_at=NULL 
                         WHERE student_id=? AND subject=? AND term=?""",
                      (file_name, file_data_base64, file_hash, datetime.now().isoformat(),
                       student_id, subject, term))
            paper_id = existing[0]
        else:
            c.execute("""INSERT INTO exam_papers (student_id, teacher_id, subject, term, exam_year, 
                         file_name, file_data, file_hash, uploaded_at) 
                         VALUES (?,?,?,?,?,?,?,?,?)""",
                      (student_id, teacher_id, subject, term, datetime.now().year,
                       file_name, file_data_base64, file_hash, datetime.now().isoformat()))
            paper_id = c.lastrowid
        
        conn.commit()
        conn.close()
        
        return {"success": True, "paper_id": paper_id, "message": "Exam paper uploaded successfully"}
    
    except Exception as e:
        print(f"Upload error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/check_verification_status/{class_name}/{term}")
async def check_verification_status(class_name: str, term: str):
    conn = get_db()
    c = conn.cursor()
    
    students = c.execute("SELECT id, first_name, last_name FROM students WHERE class_name=?", (class_name,)).fetchall()
    
    results = []
    for student in students:
        marks = c.execute("""SELECT subject, total, is_confirmed FROM marks 
                           WHERE student_id=? AND term=? AND is_confirmed=1""", 
                         (student[0], term)).fetchall()
        
        papers = c.execute("""SELECT id, subject, file_name, uploaded_at, verified, marks_match 
                           FROM exam_papers WHERE student_id=? AND term=?""", 
                         (student[0], term)).fetchall()
        
        for paper in papers:
            mark_for_subject = next((m for m in marks if m[0] == paper[1]), None)
            
            results.append({
                "student_id": student[0],
                "student_name": f"{student[1]} {student[2]}",
                "subject": paper[1],
                "paper_id": paper[0],
                "file_name": paper[2],
                "uploaded_at": paper[3],
                "verified": paper[4] == 1,
                "marks_match": paper[5] == 1,
                "entered_mark": mark_for_subject[1] if mark_for_subject else None,
                "has_marks": mark_for_subject is not None
            })
    
    conn.close()
    return results

@app.post("/api/verify_exam_paper")
async def verify_exam_paper(data: dict):
    conn = get_db()
    c = conn.cursor()
    
    paper_id = data.get('paper_id')
    marks_match = data.get('marks_match', False)
    admin_id = data.get('admin_id', 1)
    notes = data.get('notes', '')
    
    c.execute("""UPDATE exam_papers SET verified=1, marks_match=?, verified_by=?, verified_at=? 
                 WHERE id=?""", 
              (1 if marks_match else 0, admin_id, datetime.now().isoformat(), paper_id))
    
    c.execute("""INSERT INTO verification_logs (paper_id, admin_id, action, notes, created_at) 
                 VALUES (?,?,?,?,?)""",
              (paper_id, admin_id, 'verify', notes, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    return {"success": True, "message": "Exam paper verified"}

@app.get("/api/teacher/verification_status/{teacher_id}/{term}")
async def teacher_verification_status(teacher_id: int, term: str):
    conn = get_db()
    c = conn.cursor()
    
    papers = c.execute("""SELECT ep.id, s.first_name, s.last_name, ep.subject, ep.file_name, 
                                 ep.uploaded_at, ep.verified, ep.marks_match, 
                                 m.total as entered_mark
                          FROM exam_papers ep
                          JOIN students s ON ep.student_id = s.id
                          LEFT JOIN marks m ON m.student_id = ep.student_id 
                              AND m.subject = ep.subject AND m.term = ep.term
                          WHERE ep.teacher_id=? AND ep.term=?
                          ORDER BY ep.uploaded_at DESC""", 
                       (teacher_id, term)).fetchall()
    
    results = []
    for paper in papers:
        results.append({
            "paper_id": paper[0],
            "student_name": f"{paper[1]} {paper[2]}",
            "subject": paper[3],
            "file_name": paper[4],
            "uploaded_at": paper[5],
            "verified": paper[6] == 1,
            "marks_match": paper[7] == 1,
            "entered_mark": paper[8] if paper[8] else None
        })
    
    conn.close()
    return results

@app.get("/api/view_exam_paper/{paper_id}")
async def view_exam_paper(paper_id: int):
    conn = get_db()
    paper = conn.execute("SELECT file_data, file_name FROM exam_papers WHERE id=?", (paper_id,)).fetchone()
    conn.close()
    
    if paper:
        file_data = base64.b64decode(paper[0])
        return Response(content=file_data, media_type="application/pdf",
                       headers={"Content-Disposition": f"inline; filename={paper[1]}"})
    
    raise HTTPException(404, "Paper not found")

@app.get("/api/verification_summary/{term}")
async def verification_summary(term: str):
    conn = get_db()
    c = conn.cursor()
    
    total_uploads = c.execute("SELECT COUNT(*) FROM exam_papers WHERE term=?", (term,)).fetchone()[0]
    verified_count = c.execute("SELECT COUNT(*) FROM exam_papers WHERE term=? AND verified=1", (term,)).fetchone()[0]
    matched_count = c.execute("SELECT COUNT(*) FROM exam_papers WHERE term=? AND marks_match=1", (term,)).fetchone()[0]
    
    pending_by_class = c.execute("""
        SELECT s.class_name, COUNT(ep.id) 
        FROM exam_papers ep
        JOIN students s ON ep.student_id = s.id
        WHERE ep.term=? AND ep.verified=0
        GROUP BY s.class_name
    """, (term,)).fetchall()
    
    conn.close()
    
    return {
        "total_uploads": total_uploads,
        "verified_count": verified_count,
        "matched_count": matched_count,
        "pending_count": total_uploads - verified_count,
        "pending_by_class": [{"class": c[0], "count": c[1]} for c in pending_by_class]
    }

# ==================== PDF GENERATION ====================
@app.get("/admin/generate_report/{student_id}/{term}")
async def admin_generate_report(student_id: int, term: str):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(500, "ReportLab not installed. Run: pip install reportlab")
    
    conn = get_db()
    student = conn.execute("SELECT first_name, last_name, class_name, parent_name, parent_phone FROM students WHERE id=?", (student_id,)).fetchone()
    school = conn.execute("SELECT name, location, phone FROM school WHERE id=1").fetchone()
    marks = conn.execute("""SELECT subject, class_test1, group_work, project, class_test2, exam, 
                         ca_score, exam_score, total FROM marks WHERE student_id=? AND term=? AND is_confirmed=1""", 
                         (student_id, term)).fetchall()
    conn.close()
    
    if not student:
        raise HTTPException(404, "Student not found")
    
    pdf_path = str(BASE_DIR / f"report_{student_id}_{term}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 50
    
    if school:
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, y, school[0])
        c.setFont("Helvetica", 10)
        c.drawString(50, y-20, f"{school[1]} | Tel: {school[2]}")
    
    y -= 60
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, f"REPORT CARD - {term}")
    
    y -= 40
    c.setFont("Helvetica", 12)
    c.drawString(50, y, f"Student: {student[0]} {student[1]}")
    c.drawString(300, y, f"Class: {student[2]}")
    y -= 25
    c.drawString(50, y, f"Parent: {student[3]} | Phone: {student[4]}")
    
    y -= 45
    c.setFont("Helvetica-Bold", 9)
    headers = ["Subject", "T1(30)", "Grp(20)", "Proj(20)", "T2(30)", "Exam(100)", "CA(50)", "ExSc(50)", "Total(100)", "Grade"]
    x_positions = [50, 95, 130, 165, 200, 235, 275, 315, 355, 400]
    for i, header in enumerate(headers):
        c.drawString(x_positions[i], y, header)
    
    y -= 15
    c.line(50, y, 550, y)
    y -= 20
    c.setFont("Helvetica", 8)
    
    grand_total = 0
    for m in marks:
        total = m[8]
        grand_total += total
        grade = "Excellent" if total >= 90 else "Very Good" if total >= 70 else "Good" if total >= 55 else "Credit" if total >= 40 else "Fail"
        c.drawString(50, y, m[0][:12])
        c.drawString(95, y, str(m[1] or 0))
        c.drawString(130, y, str(m[2] or 0))
        c.drawString(165, y, str(m[3] or 0))
        c.drawString(200, y, str(m[4] or 0))
        c.drawString(235, y, str(m[5] or 0))
        c.drawString(275, y, f"{m[6]:.1f}" if m[6] else "0")
        c.drawString(315, y, f"{m[7]:.1f}" if m[7] else "0")
        c.drawString(355, y, f"{total:.1f}")
        c.drawString(400, y, grade)
        y -= 18
        if y < 50:
            c.showPage()
            y = height - 50
    
    y -= 25
    c.setFont("Helvetica-Bold", 12)
    avg_score = grand_total / len(marks) if marks else 0
    overall_grade = "Excellent" if avg_score >= 90 else "Very Good" if avg_score >= 70 else "Good" if avg_score >= 55 else "Credit" if avg_score >= 40 else "Fail"
    c.drawString(50, y, f"GRAND TOTAL: {grand_total:.1f} / {len(marks) * 100}")
    c.drawString(300, y, f"AVERAGE: {avg_score:.1f}%")
    y -= 20
    c.drawString(50, y, f"OVERALL GRADE: {overall_grade}")
    
    y -= 60
    c.line(50, y, 200, y)
    c.drawString(50, y-10, "Principal's Signature")
    c.line(350, y, 500, y)
    c.drawString(350, y-10, "Parent's Signature")
    
    c.setFont("Helvetica", 8)
    c.drawString(50, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d')} | System designed by JSLY @ 2026")
    c.save()
    
    return FileResponse(pdf_path, media_type='application/pdf', filename=f"report_{student[0]}_{student[1]}_{term}.pdf")

@app.get("/admin/generate_class_reports/{class_name}/{term}")
async def admin_generate_class_reports(class_name: str, term: str):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        raise HTTPException(500, "ReportLab not installed. Run: pip install reportlab")
    
    conn = get_db()
    students = conn.execute("SELECT id, first_name, last_name FROM students WHERE class_name=?", (class_name,)).fetchall()
    school = conn.execute("SELECT name, location, phone FROM school WHERE id=1").fetchone()
    conn.close()
    
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for student in students:
            conn = get_db()
            marks = conn.execute("""SELECT subject, class_test1, group_work, project, class_test2, exam, 
                                 ca_score, exam_score, total FROM marks WHERE student_id=? AND term=? AND is_confirmed=1""", 
                                 (student[0], term)).fetchall()
            parent = conn.execute("SELECT parent_name, parent_phone FROM students WHERE id=?", (student[0],)).fetchone()
            conn.close()
            
            if not marks:
                continue
            
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=letter)
            width, height = letter
            y = height - 50
            
            if school:
                c.setFont("Helvetica-Bold", 18)
                c.drawString(50, y, school[0])
                c.setFont("Helvetica", 10)
                c.drawString(50, y-20, f"{school[1]} | Tel: {school[2]}")
            
            y -= 60
            c.setFont("Helvetica-Bold", 16)
            c.drawString(50, y, f"REPORT CARD - {term}")
            
            y -= 40
            c.setFont("Helvetica", 12)
            c.drawString(50, y, f"Student: {student[1]} {student[2]}")
            c.drawString(300, y, f"Class: {class_name}")
            y -= 25
            if parent:
                c.drawString(50, y, f"Parent: {parent[0]} | Phone: {parent[1]}")
            
            y -= 45
            c.setFont("Helvetica-Bold", 9)
            headers = ["Subject", "T1(30)", "Grp(20)", "Proj(20)", "T2(30)", "Exam(100)", "CA(50)", "ExSc(50)", "Total(100)", "Grade"]
            x_positions = [50, 95, 130, 165, 200, 235, 275, 315, 355, 400]
            for i, header in enumerate(headers):
                c.drawString(x_positions[i], y, header)
            
            y -= 15
            c.line(50, y, 550, y)
            y -= 20
            c.setFont("Helvetica", 8)
            
            grand_total = 0
            for m in marks:
                total = m[8]
                grand_total += total
                grade = "Excellent" if total >= 90 else "Very Good" if total >= 70 else "Good" if total >= 55 else "Credit" if total >= 40 else "Fail"
                c.drawString(50, y, m[0][:12])
                c.drawString(95, y, str(m[1] or 0))
                c.drawString(130, y, str(m[2] or 0))
                c.drawString(165, y, str(m[3] or 0))
                c.drawString(200, y, str(m[4] or 0))
                c.drawString(235, y, str(m[5] or 0))
                c.drawString(275, y, f"{m[6]:.1f}" if m[6] else "0")
                c.drawString(315, y, f"{m[7]:.1f}" if m[7] else "0")
                c.drawString(355, y, f"{total:.1f}")
                c.drawString(400, y, grade)
                y -= 18
                if y < 50:
                    c.showPage()
                    y = height - 50
            
            y -= 25
            c.setFont("Helvetica-Bold", 12)
            avg_score = grand_total / len(marks) if marks else 0
            c.drawString(50, y, f"GRAND TOTAL: {grand_total:.1f} / {len(marks) * 100}")
            c.drawString(300, y, f"AVERAGE: {avg_score:.1f}%")
            
            y -= 60
            c.line(50, y, 200, y)
            c.drawString(50, y-10, "Principal's Signature")
            c.line(350, y, 500, y)
            c.drawString(350, y-10, "Parent's Signature")
            
            c.setFont("Helvetica", 8)
            c.drawString(50, 50, f"Generated on {datetime.now().strftime('%Y-%m-%d')}")
            c.save()
            
            pdf_buffer.seek(0)
            zip_file.writestr(f"{student[1]}_{student[2]}_{term}_report.pdf", pdf_buffer.getvalue())
    
    zip_buffer.seek(0)
    return Response(content=zip_buffer.getvalue(), media_type="application/zip", 
                   headers={"Content-Disposition": f"attachment; filename={class_name}_{term}_reports.zip"})

# ==================== STUDENT PASSWORD VIEW ====================
@app.get("/api/students/{student_id}/password")
async def get_student_password(student_id: int):
    conn = get_db()
    result = conn.execute("SELECT password FROM students WHERE id=?", (student_id,)).fetchone()
    conn.close()
    if result:
        return {"password": result[0]}
    raise HTTPException(404, "Student not found")

# ==================== RUN APP ====================
if __name__ == "__main__":
    import uvicorn
    
    print("=" * 60)
    print("SCHOOL MANAGEMENT SYSTEM")
    print("=" * 60)
    print("\nMARKS CALCULATION FORMULA:")
    print("   CA = (Test1 + Group + Project + Test2) / 2 (Max: 50)")
    print("   Exam Score = Exam / 2 (Max: 50)")
    print("   Total = CA + Exam Score (Max: 100)")
    print("\nMAXIMUM MARKS (Automatically enforced):")
    print("   1st Class Test: ≤30 | Group Work: ≤20 | Project: ≤20")
    print("   2nd Class Test: ≤30 | Exam: ≤100")
    print("=" * 60)
    
    if FIRST_RUN:
        print("\n✅ FIRST TIME SETUP COMPLETE!")
        print("   Developer Password: HeroHero@1234")
        print()
    
    print(f"Server: http://127.0.0.1:8000")
    print("\nLOGIN CREDENTIALS (after unlock):")
    print("   Admin:    admin / admin123")
    print("   Teacher:  John / teacher123")
    print("   Student:  James / Wilson")
    print("=" * 60)
    print("\nFIXES INCLUDED:")
    print("   ✅ Database tables created properly")
    print("   ✅ No duplicate marks (UNIQUE constraint on student_id, subject, term)")
    print("   ✅ Max marks enforced (≤30, ≤20, ≤20, ≤30, ≤100)")
    print("   ✅ Student password management (view & reset)")
    print("   ✅ Exam paper upload & verification")
    print("   ✅ Admin can view student passwords")
    print("=" * 60)
    print("\nStarting server...\n")
    
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")