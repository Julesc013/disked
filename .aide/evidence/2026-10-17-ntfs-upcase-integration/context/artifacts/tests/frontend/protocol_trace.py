"""Retain NDJSON request/response state without owning process termination."""
import json
import queue
import threading
import time


class ProtocolTrace:
    def __init__(self, process, output, encode):
        self.process = process
        self.output = output
        self.encode = encode
        self.messages = queue.Queue()
        self.frames = []
        self.error = None
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.log = output.with_name(output.stem + '-late-trace.jsonl')
        self.thread = threading.Thread(target=self.receive, daemon=True)
        self.thread.start()

    def event(self, kind, **values):
        with self.lock:
            with self.log.open('a', encoding='utf-8', newline='\n') as log:
                log.write(json.dumps(dict(seconds=time.monotonic()-self.started,
                                          kind=kind, **values)) + '\n')

    def receive(self):
        try:
            for raw in self.process.stdout:
                frame = self.output.with_name(self.output.stem + '-late-frame-' + str(len(self.frames)) + '.json')
                frame.write_bytes(raw)
                self.frames.append(frame.name)
                value = json.loads(raw)
                self.event('frame', request_id=value.get('request_id'), status=value.get('status'),
                           diagnostics=value.get('diagnostics'), raw=frame.name)
                self.messages.put(value)
        except BaseException as error:
            self.error = repr(error)
            self.event('receiver_error', error=self.error)

    def send(self, request):
        self.event('send', request_id=request['request_id'], command=request['command'])
        self.process.stdin.write(self.encode(request) + b'\n')
        self.process.stdin.flush()

    def get(self, timeout):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty:
            self.event('receive_timeout', timeout=timeout, parent_returncode=self.process.poll(),
                       receiver_error=self.error, queued=self.messages.qsize())
            raise
        self.event('dequeue', request_id=value.get('request_id'), status=value.get('status'),
                   remaining=self.messages.qsize())
        return value

    def snapshot(self, kind):
        with self.messages.mutex:
            pending = [dict(request_id=v.get('request_id'), status=v.get('status'),
                            diagnostics=v.get('diagnostics')) for v in self.messages.queue]
        self.event(kind, pending=pending, parent_returncode=self.process.poll(),
                   receiver_alive=self.thread.is_alive(), receiver_error=self.error)
