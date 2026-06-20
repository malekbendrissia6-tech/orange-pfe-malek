"""
File de priorite + rate-limiter pour les appels Gemini — Orange Tunisie.
Max 12 req/min (quota Gemini Free). Niveaux : HIGH (chatbot), NORMAL (KPIs), LOW (prefetch).
"""
import queue
import threading
from time import time, sleep


# ── Blocage quota global ──────────────────────────────────────────────────────

_quota_blocked_until: float = 0.0
_quota_lock = threading.Lock()


def is_quota_blocked() -> bool:
    with _quota_lock:
        return time() < _quota_blocked_until


def set_quota_blocked(seconds: int = 120) -> None:
    global _quota_blocked_until
    with _quota_lock:
        _quota_blocked_until = time() + seconds
    print(f"[GeminiQueue] Quota bloque pour {seconds}s.")


def quota_unblocks_in() -> int:
    with _quota_lock:
        return max(0, int(_quota_blocked_until - time()))


# ── File prioritaire ──────────────────────────────────────────────────────────

class GeminiQueue:
    HIGH   = 0   # chatbot interactif — reponse temps reel
    NORMAL = 1   # interpretations KPI — declenchees par clic
    LOW    = 2   # prefetch / preloading en arriere-plan

    _RPM     = 12    # requetes par minute (limite Gemini Free)
    _WINDOW  = 60.0  # fenetre glissante (secondes)
    _TIMEOUT = 25    # secondes max d'attente pour un appelant

    def __init__(self):
        self._pq           = queue.PriorityQueue()
        self._history: list = []
        self._hist_lock    = threading.Lock()
        self._api_calls    = 0
        self._fallbacks    = 0
        self._worker       = threading.Thread(
            target=self._run, daemon=True, name='GeminiWorker'
        )
        self._worker.start()

    # ── Interface publique ────────────────────────────────────────────────────

    def submit(self, fn, priority: int = NORMAL, timeout: int = _TIMEOUT):
        """
        Soumet fn() dans la file. Bloque jusqu'au resultat ou timeout.
        Retourne la valeur de fn(), ou None si timeout / quota bloque.
        """
        if is_quota_blocked():
            self.incr_fallbacks()
            return None

        ev     = threading.Event()
        result = [None]
        error  = [None]

        def _task():
            try:
                result[0] = fn()
                with self._hist_lock:
                    self._api_calls += 1
            except Exception as exc:
                error[0] = exc
            finally:
                ev.set()

        self._pq.put((priority, time(), _task))
        done = ev.wait(timeout=timeout)

        if not done:
            return None

        if error[0] is not None:
            raise error[0]

        return result[0]

    def incr_fallbacks(self) -> None:
        with self._hist_lock:
            self._fallbacks += 1

    def stats(self) -> dict:
        with self._hist_lock:
            now    = time()
            recent = sum(1 for t in self._history if now - t < self._WINDOW)
            return {
                'api_calls_total':  self._api_calls,
                'fallbacks_total':  self._fallbacks,
                'calls_last_60s':   recent,
                'rpm_limit':        self._RPM,
                'queue_size':       self._pq.qsize(),
                'quota_blocked':    is_quota_blocked(),
                'quota_unblocks_in': quota_unblocks_in(),
            }

    # ── Boucle worker ─────────────────────────────────────────────────────────

    def _run(self):
        while True:
            try:
                priority, ts, task = self._pq.get(timeout=1)
            except queue.Empty:
                continue

            self._wait_for_token()
            task()
            self._pq.task_done()

    def _wait_for_token(self):
        """Token-bucket : attend qu'un slot soit disponible dans la fenetre de 60s."""
        while True:
            if is_quota_blocked():
                sleep(1)
                continue
            with self._hist_lock:
                now = time()
                self._history = [t for t in self._history if now - t < self._WINDOW]
                if len(self._history) < self._RPM:
                    self._history.append(now)
                    return
            sleep(0.5)


# Singleton
gemini_queue = GeminiQueue()
