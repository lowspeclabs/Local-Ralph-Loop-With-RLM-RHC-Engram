import requests
import json
import threading
import queue
import time
import re
from typing import List, Dict, Optional, Any, Union
from .memory import EngramMemoryStore, TokenizerCompression
from .utils import normalize_lm_studio_url
from .config import CONFIG

class LMStudioEngramProxy:
    """Proxy that augments LM Studio with Engram memory."""
    
    def __init__(self,
                 lm_studio_url: str = "http://localhost:1234/v1",
                 memory_store: Optional[EngramMemoryStore] = None,
                 injection_method: str = "system"):
        
        self.lm_studio_url = normalize_lm_studio_url(lm_studio_url)
        self.memory_store = memory_store or EngramMemoryStore()
        self.injection_method = injection_method
        self.compressor = TokenizerCompression()
        
        self.prefetch_queue = queue.Queue()
        self._prefetch_lock = threading.Lock()
        self._prefetch_results = {}
        self._shutdown_event = threading.Event()
        self._start_prefetch_thread()

    def _start_prefetch_thread(self):
        def prefetch_worker():
            while not self._shutdown_event.is_set():
                try:
                    tokens = self.prefetch_queue.get(timeout=CONFIG['PREFETCH_TIMEOUT'])
                    if tokens is None: break
                    
                    results = self.memory_store.lookup(tokens)
                    key = '|'.join(tokens[-3:]) if len(tokens) >= 3 else '|'.join(tokens)
                    
                    with self._prefetch_lock:
                        self._prefetch_results[key] = results
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"[Engram] Prefetch error: {e}")
        
        self.prefetch_thread = threading.Thread(target=prefetch_worker, daemon=True)
        self.prefetch_thread.start()

    def _format_memory_context(self, memory_results: Dict[int, List[Dict]]) -> str:
        if not memory_results: return ""
        
        context_parts = ["[Relevant Context from Engram Memory]:"]
        total_chars = len(context_parts[0])
        max_chars = CONFIG['MAX_MEMORY_INJECT_CHARS']
        
        for n, entries in sorted(memory_results.items()):
            if entries:
                # Get latest entries
                sorted_entries = sorted(entries, key=lambda x: x.get('timestamp', 0), reverse=True)[:CONFIG['TOP_MEMORY_ENTRIES']]
                for entry in sorted_entries:
                    entry_text = f"- {entry['info']}"
                    if total_chars + len(entry_text) + 1 > max_chars:
                        context_parts.append("- [truncated...]")
                        break
                    context_parts.append(entry_text)
                    total_chars += len(entry_text) + 1
        return "\n".join(context_parts)

    def chat_completion(self, messages: List[Dict[str, str]], **kwargs) -> Union[Dict, requests.Response]:
        """Send chat completion request with Engram memory augmentation."""
        import copy
        _t_start = time.time()
        _timings = {}
        
        # Work on a copy to prevent persistent injection bloat in history
        local_messages = copy.deepcopy(messages)
        user_message = next((msg['content'] for msg in reversed(local_messages) if msg['role'] == 'user'), None)
        
        if user_message and self.injection_method != 'none':
            # Tokenize and compress
            _t0 = time.time()
            tokens = re.findall(r'\w+|[^\w\s]', user_message.lower())
            compressed = self.compressor.compress_sequence(tokens)
            _timings['tokenize'] = time.time() - _t0
            
            # OPTIMIZATION: Check prefetch results first
            _t0 = time.time()
            key = '|'.join(compressed[-3:]) if len(compressed) >= 3 else '|'.join(compressed)
            with self._prefetch_lock:
                memory_results = self._prefetch_results.pop(key, None)
            if memory_results is None:
                memory_results = self.memory_store.lookup(compressed)
            else:
                if CONFIG.get('DEBUG_MODE'):
                    print(f"[DEBUG] Cache Hit! Using prefetch results for {key}")
            _timings['memory_lookup'] = time.time() - _t0

            # Inject memory into context
            _t0 = time.time()
            memory_context = self._format_memory_context(memory_results)
            _timings['memory_inject_chars'] = len(memory_context)
            
            if memory_context:
                if self.injection_method == 'system':
                    system_msg = next((msg for msg in local_messages if msg['role'] == 'system'), None)
                    if system_msg: system_msg['content'] += f"\n\n{memory_context}"
                    else: local_messages.insert(0, {'role': 'system', 'content': memory_context})
                elif self.injection_method == 'prefix':
                    for msg in local_messages:
                        if msg['role'] == 'user':
                            msg['content'] = f"{memory_context}\n\n{msg['content']}"
                            break
            _timings['memory_inject'] = time.time() - _t0
            
            # Prefetch for next iteration
            self.prefetch_queue.put(compressed + ['<predict>'])

        # Calculate total message size
        total_chars = sum(len(m.get('content', '')) for m in local_messages)
        _timings['total_input_chars'] = total_chars
        
        # DEBUG: Print timing before request
        if CONFIG.get('DEBUG_MODE'):
            print(f"[DEBUG] Pre-request: tokenize={_timings.get('tokenize', 0)*1000:.1f}ms, "
                  f"lookup={_timings.get('memory_lookup', 0)*1000:.1f}ms, "
                  f"inject={_timings.get('memory_inject', 0)*1000:.1f}ms, "
                  f"input_size={total_chars} chars")

        # API Call
        api_url = f"{self.lm_studio_url}/chat/completions"
        try:
            _t_request = time.time()
            response = requests.post(
                api_url, 
                json={**kwargs, 'messages': local_messages},
                stream=kwargs.get('stream', False),
                timeout=CONFIG['STREAMING_TIMEOUT'] if kwargs.get('stream') else CONFIG['REQUEST_TIMEOUT']
            )
            _timings['time_to_response'] = time.time() - _t_request
            if CONFIG.get('DEBUG_MODE'):
                print(f"[DEBUG] Time to first response: {_timings['time_to_response']*1000:.1f}ms")

            if not response.ok:
                error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                print(f"\n\u26a0 LM Studio API Error: {error_msg}")
                return {'error': error_msg, 'choices': []}
            return response if kwargs.get('stream') else response.json()
        except Exception as e:
            print(f"\n\u26a0 Request failed: {e}")
            return {'error': str(e), 'choices': []}

    def chat_completion_sync(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Helper for non-streaming sync calls, returns content string."""
        kwargs['stream'] = False
        res = self.chat_completion(messages, **kwargs)
        if isinstance(res, dict) and 'choices' in res:
            return res['choices'][0]['message'].get('content', '')
        return str(res)

    def learn_from_conversation(self, user_msg: str, assistant_msg: str, metadata: Dict = None):
        tokens = re.findall(r'\w+|[^\w\s]', user_msg.lower())
        compressed = self.compressor.compress_sequence(tokens)
        self.memory_store.store(compressed, assistant_msg[:CONFIG['MEMORY_TRUNCATE_LENGTH']], metadata)

    def get_statistics(self) -> Dict:
        return {
            'memory': self.memory_store.get_stats(),
            'prefetch_queue_size': self.prefetch_queue.qsize()
        }
