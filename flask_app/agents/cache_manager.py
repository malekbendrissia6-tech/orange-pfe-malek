"""
Cache TTL 2h pour les reponses Gemini — Orange Tunisie.
Thread-safe. Statistiques : hits, misses, hit_rate.
"""
import hashlib
import json
import threading
from time import time


class CacheManager:
    def __init__(self, ttl_seconds: int = 7200):
        self._store: dict = {}
        self._lock  = threading.Lock()
        self.ttl    = ttl_seconds
        self._hits   = 0
        self._misses = 0

    @staticmethod
    def make_key(prefix: str, *args) -> str:
        raw = json.dumps([prefix, *args], ensure_ascii=False, default=str, sort_keys=True)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if time() - entry['t'] > self.ttl:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return entry['v']

    def set(self, key: str, value) -> None:
        with self._lock:
            self._store[key] = {'v': value, 't': time()}

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._hits = 0
            self._misses = 0

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def stats(self) -> dict:
        with self._lock:
            now = time()
            active = sum(1 for e in self._store.values() if now - e['t'] <= self.ttl)
            total  = self._hits + self._misses
            return {
                'active_entries': active,
                'total_entries':  len(self._store),
                'ttl_seconds':    self.ttl,
                'hits':           self._hits,
                'misses':         self._misses,
                'hit_rate':       round(self._hits / total * 100, 1) if total else 0.0,
            }


# Singleton partage — TTL 2 heures
gemini_cache = CacheManager(ttl_seconds=7200)
