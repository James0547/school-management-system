# performance.py - Performance optimization module for School Management System
# Import this into main.py to add caching, connection pooling, and performance features

import sqlite3
import threading
import time
from contextlib import contextmanager
from queue import Queue
from functools import wraps
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import json

# ==================== DATABASE CONNECTION POOL ====================
class DatabasePool:
    """Thread-safe database connection pool for high performance"""
    
    def __init__(self, db_path: str, pool_size: int = 10):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._created = 0
        self._active_connections = 0
        
        # Pre-create connections
        for _ in range(pool_size):
            self._create_connection()
        print(f"✅ Database connection pool created with {pool_size} connections")
    
    def _create_connection(self):
        """Create a new database connection with optimizations"""
        with self._lock:
            if self._created < self.pool_size:
                conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30)
                conn.text_factory = str
                conn.row_factory = sqlite3.Row
                
                # Performance optimizations
                conn.execute("PRAGMA journal_mode=WAL")           # Write-Ahead Logging
                conn.execute("PRAGMA synchronous=NORMAL")         # Balance speed and safety
                conn.execute("PRAGMA cache_size=-20000")          # 20MB cache
                conn.execute("PRAGMA temp_store=MEMORY")          # Temp tables in memory
                conn.execute("PRAGMA mmap_size=268435456")        # 256MB memory mapping
                
                self._pool.put(conn)
                self._created += 1
                self._active_connections += 1
    
    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = self._pool.get()
        try:
            yield conn
        finally:
            self._pool.put(conn)
    
    def get_stats(self):
        """Get pool statistics"""
        return {
            "pool_size": self.pool_size,
            "created": self._created,
            "available": self._pool.qsize(),
            "active": self._active_connections
        }
    
    def close_all(self):
        """Close all connections"""
        while not self._pool.empty():
            try:
                conn = self._pool.get_nowait()
                conn.close()
            except:
                pass
        print("✅ All database connections closed")

# ==================== CACHE SYSTEM ====================
class PerformanceCache:
    """In-memory cache with TTL for lightning-fast responses"""
    
    def __init__(self, default_ttl: int = 300):
        self._cache = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        print(f"✅ Cache system initialized with {default_ttl}s default TTL")
    
    def get(self, key: str):
        """Get value from cache"""
        with self._lock:
            if key in self._cache:
                item = self._cache[key]
                if time.time() < item['expires']:
                    self._hits += 1
                    return item['value']
                else:
                    del self._cache[key]
            self._misses += 1
        return None
    
    def set(self, key: str, value, ttl: int = None):
        """Store value in cache"""
        ttl = ttl or self._default_ttl
        with self._lock:
            self._cache[key] = {
                'value': value,
                'expires': time.time() + ttl
            }
    
    def delete(self, key: str = None):
        """Delete specific key or clear all cache"""
        with self._lock:
            if key:
                self._cache.pop(key, None)
            else:
                self._cache.clear()
                self._hits = 0
                self._misses = 0
    
    def delete_pattern(self, pattern: str):
        """Delete all keys containing pattern"""
        with self._lock:
            keys = [k for k in self._cache.keys() if pattern in k]
            for key in keys:
                del self._cache[key]
    
    def get_stats(self):
        """Get cache statistics"""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0
        return {
            "size": len(self._cache),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%"
        }

# ==================== QUERY CACHE DECORATOR ====================
def cache_result(ttl: int = 300, key_pattern: str = None):
    """Decorator to cache function results"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = key_pattern or f"{func.__name__}_{str(args)}_{str(kwargs)}"
            cached = cache.get(cache_key)
            if cached is not None:
                return cached
            
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            return result
        return wrapper
    return decorator

# ==================== PERFORMANCE MIDDLEWARE ====================
def add_performance_middleware(app):
    """Add performance middleware to FastAPI app"""
    
    # GZip compression
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # CORS for better performance
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Cache headers middleware
    @app.middleware("http")
    async def add_cache_headers(request, call_next):
        response = await call_next(request)
        path = request.url.path
        
        if path.startswith("/static"):
            response.headers["Cache-Control"] = "public, max-age=86400"  # 1 day
        elif path.startswith("/api"):
            response.headers["Cache-Control"] = "public, max-age=60"     # 1 minute
        elif path.startswith("/admin") or path.startswith("/teacher") or path.startswith("/student"):
            response.headers["Cache-Control"] = "no-cache, no-store"
        
        return response
    
    # Performance monitoring middleware
    @app.middleware("http")
    async def monitor_performance(request, call_next):
        start_time = time.time()
        response = await call_next(request)
        duration = (time.time() - start_time) * 1000
        
        # Log slow requests (over 500ms)
        if duration > 500:
            print(f"⚠️ Slow request: {request.url.path} - {duration:.0f}ms")
        
        # Add performance header
        response.headers["X-Response-Time-MS"] = str(int(duration))
        return response
    
    print("✅ Performance middleware added")
    
    # Add performance stats endpoint
    @app.get("/api/performance/stats")
    async def performance_stats():
        return {
            "cache": cache.get_stats(),
            "database_pool": db_pool.get_stats(),
            "timestamp": time.time()
        }
    
    return app

# ==================== OPTIMIZED DATABASE FUNCTIONS ====================
def execute_query(query: str, params: tuple = None, use_cache: bool = True, cache_ttl: int = 300):
    """Execute query with optional caching"""
    if use_cache:
        cache_key = f"query_{hash(query)}_{str(params)}"
        cached = cache.get(cache_key)
        if cached:
            return cached
    
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        result = cursor.fetchall()
        
        if use_cache:
            cache.set(cache_key, result, cache_ttl)
        
        return result

def execute_write(query: str, params: tuple = None, invalidate_pattern: str = None):
    """Execute write query and invalidate cache"""
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        affected = cursor.rowcount
    
    if invalidate_pattern:
        cache.delete_pattern(invalidate_pattern)
    
    return affected

# ==================== BULK OPERATIONS OPTIMIZATION ====================
def bulk_insert(students_data: list):
    """Optimized bulk insert for many records"""
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO students (first_name, last_name, age, parent_name, parent_phone, parent_email, class_name, subjects, enrollment_date)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, students_data)
        conn.commit()
        cache.delete_pattern('all_students')
        cache.delete_pattern('students_by_class')
        return len(students_data)

def bulk_update_marks(marks_data: list):
    """Optimized bulk update for marks"""
    with db_pool.get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            UPDATE marks SET class_test1=?, group_work=?, project=?, class_test2=?, exam=?, 
            ca_score=?, exam_score=?, total=?, submission_date=?
            WHERE student_id=? AND subject=? AND term=?
        """, marks_data)
        conn.commit()
        cache.delete_pattern('student_marks')
        return cursor.rowcount

# ==================== EXPORT EVERYTHING ====================
# Initialize global instances (will be configured when setup is called)
db_pool = None
cache = None

def init_performance(db_path: str, pool_size: int = 10, cache_ttl: int = 300):
    """Initialize performance module with database path"""
    global db_pool, cache
    db_pool = DatabasePool(db_path, pool_size)
    cache = PerformanceCache(cache_ttl)
    print("=" * 50)
    print("🚀 PERFORMANCE MODULE INITIALIZED")
    print(f"   Database Pool: {pool_size} connections")
    print(f"   Cache TTL: {cache_ttl} seconds")
    print("=" * 50)
    return db_pool, cache

# Export all functions
__all__ = [
    'init_performance',
    'db_pool',
    'cache',
    'add_performance_middleware',
    'cache_result',
    'execute_query',
    'execute_write',
    'bulk_insert',
    'bulk_update_marks',
    'DatabasePool',
    'PerformanceCache'
]