import sqlite3
import json
import time
import re
import pickle
from pathlib import Path
from typing import List, Dict, Optional, Any
from collections import OrderedDict
from .config import CONFIG

class TokenizerCompression:
    """Compress and normalize tokens for better n-gram matching"""
    
    def __init__(self, vocab_size: int = 128000):
        self.vocab_size = vocab_size
    
    def normalize_token(self, token: str) -> str:
        """Normalize token to canonical form"""
        normalized = token.strip().replace('▁', '').replace('Ġ', '')
        normalized = normalized.lower()
        return normalized
    
    def compress_sequence(self, tokens: List[str]) -> List[str]:
        """Compress a sequence of tokens"""
        return [self.normalize_token(t) for t in tokens]

class EngramMemoryStore:
    """
    N-gram based memory store with SQLite persistence.
    """
    
    def __init__(self, 
                 storage_path: str = "./engram_memory",
                 ngram_orders: List[int] = None,
                 max_memory_mb: int = 512):
        
        if ngram_orders is None:
            ngram_orders = [2, 3]
            
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True, parents=True)
        
        self.db_path = self.storage_path / "engram_memory.db"
        self.ngram_orders = ngram_orders
        
        # Initialize SQLite
        self._init_db()
        
        # In-memory LRU cache
        self.cache = OrderedDict()
        self.max_cache_entries = (max_memory_mb * 1024 * 1024) // 1000 # Roughly
        
        self.stats = {
            'lookups': 0, 'hits': 0, 'misses': 0, 'cache_hits': 0, 'db_reads': 0
        }
        
        # Track unsaved changes for batching
        self._pending_entries = []
        
        # Migrate old pickle files if they exist
        self._migrate_pickles()

    def _init_db(self):
        """Initialize SQLite database and schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ngrams (
                    n INTEGER,
                    ngram_key TEXT,
                    value_json TEXT,
                    hit_count INTEGER DEFAULT 1,
                    last_accessed REAL,
                    PRIMARY KEY (n, ngram_key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ngrams_key ON ngrams(ngram_key)")
            conn.commit()

    def _migrate_pickles(self):
        """Migrate legacy .pkl files to SQLite"""
        migrated = False
        for n in self.ngram_orders:
            pkl_path = self.storage_path / f"ngram_{n}.pkl"
            if pkl_path.exists():
                print(f"[Engram] Migrating {pkl_path} to SQLite...")
                try:
                    with open(pkl_path, 'rb') as f:
                        data = pickle.load(f)
                        for key, entries in data.items():
                            # Entries is a list in the old format
                            self._store_to_db(n, key, json.dumps(entries))
                    pkl_path.rename(pkl_path.with_suffix('.pkl.bak'))
                    migrated = True
                except Exception as e:
                    print(f"[Engram] Migration error for {pkl_path}: {e}")
        
        if migrated:
            print("[Engram] Migration complete.")

    def _store_to_db(self, n: int, key: str, value_json: str, conn: Optional[sqlite3.Connection] = None):
        """Directly store to database"""
        def _execute(c):
            c.execute("""
                INSERT INTO ngrams (n, ngram_key, value_json, last_accessed)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(n, ngram_key) DO UPDATE SET
                value_json = excluded.value_json,
                hit_count = hit_count + 1,
                last_accessed = excluded.last_accessed
            """, (n, key, value_json, time.time()))
            c.commit()

        if conn:
            _execute(conn)
        else:
            with sqlite3.connect(self.db_path) as new_conn:
                _execute(new_conn)

    def _make_ngram_key(self, tokens: List[str], n: int) -> Optional[str]:
        if len(tokens) < n: return None
        return '|'.join(tokens[-n:])

    def store(self, context_tokens: List[str], information: str, metadata: Optional[Dict] = None):
        """Store information with batching support"""
        timestamp = time.time()
        with sqlite3.connect(self.db_path) as conn:
            for n in self.ngram_orders:
                key = self._make_ngram_key(context_tokens, n)
                if not key: continue

                # Simple approach: append to pending and flush periodically
                # For simplicity in this version, we'll just update the existing entry if found
                # or append to the list of info for that key.

                existing = self.lookup_key(n, key, conn=conn) or []
                existing.append({
                    'info': information,
                    'metadata': metadata or {},
                    'timestamp': timestamp,
                    'count': 1
                })

                self._store_to_db(n, key, json.dumps(existing), conn=conn)

                # Update cache if present
                cache_key = f"{n}:{key}"
                if cache_key in self.cache:
                    self.cache[cache_key] = existing

    def lookup_key(self, n: int, key: str, conn: Optional[sqlite3.Connection] = None) -> Optional[List[Dict]]:
        """Lookup a specific key, checking cache first"""
        cache_key = f"{n}:{key}"
        if cache_key in self.cache:
            self.stats['cache_hits'] += 1
            self.cache.move_to_end(cache_key)
            return self.cache[cache_key]

        self.stats['db_reads'] += 1

        def _query(c):
            cursor = c.execute("SELECT value_json FROM ngrams WHERE n = ? AND ngram_key = ?", (n, key))
            return cursor.fetchone()

        if conn:
            row = _query(conn)
        else:
            with sqlite3.connect(self.db_path) as new_conn:
                row = _query(new_conn)

        if row:
            data = json.loads(row[0])
            self.cache[cache_key] = data
            if len(self.cache) > self.max_cache_entries:
                self.cache.popitem(last=False)
            return data

        return None

    def lookup(self, tokens: List[str]) -> Dict[int, List[Dict]]:
        """Lookup information for token sequence across all orders"""
        self.stats['lookups'] += 1
        results = {}
        
        with sqlite3.connect(self.db_path) as conn:
            for n in self.ngram_orders:
                key = self._make_ngram_key(tokens, n)
                if not key: continue

                entries = self.lookup_key(n, key, conn=conn)
                if entries:
                    self.stats['hits'] += 1
                    results[n] = entries
                else:
                    self.stats['misses'] += 1
        
        return results

    def force_save(self):
        """No-op for SQLite as it's auto-committed, but kept for API compatibility"""
        pass

    def get_stats(self) -> Dict:
        hit_rate = (self.stats['hits'] / self.stats['lookups'] * 100 if self.stats['lookups'] > 0 else 0)
        cache_rate = (self.stats['cache_hits'] / self.stats['lookups'] * 100 if self.stats['lookups'] > 0 else 0)
        
        db_size = 0
        if self.db_path.exists():
            db_size = self.db_path.stat().st_size
            
        return {
            **self.stats,
            'hit_rate_%': round(hit_rate, 2),
            'cache_hit_rate_%': round(cache_rate, 2),
            'cache_entries': len(self.cache),
            'max_cache_entries': self.max_cache_entries,
            'db_size_mb': round(db_size / (1024 * 1024), 2),
            'db_path': str(self.db_path)
        }
