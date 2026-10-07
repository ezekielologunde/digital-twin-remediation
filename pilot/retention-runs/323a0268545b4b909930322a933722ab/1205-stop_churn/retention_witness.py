"""Project-filtered continuous Docker event witness, separate from policy input."""
import json
import subprocess
import threading
import time

class Witness:
    def __init__(self, project, path):
        self.path=path
        self.rows=[]
        self.lock=threading.Lock()
        self.stream=path.open('w',encoding='utf8')
        self.errors=path.with_suffix('.stderr.txt').open('w',encoding='utf8')
        self.proc=subprocess.Popen(['docker','events','--filter','label=com.docker.compose.project='+project,'--format','{{json .}}'],stdout=subprocess.PIPE,stderr=self.errors,text=True,bufsize=1)
        self.thread=threading.Thread(target=self._read,daemon=True);self.thread.start()
    def _read(self):
        for line in self.proc.stdout:
            self.stream.write(line);self.stream.flush()
            row=json.loads(line)
            with self.lock:self.rows.append(row)
    def wait(self, container, action, timeout=10):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            with self.lock:
                hits=[e for e in self.rows if e.get('Actor',{}).get('ID')==container and e.get('Action')==action]
            if hits:return hits[-1]
            if self.proc.poll() is not None:raise RuntimeError('Witness ended unexpectedly')
            time.sleep(.05)
        raise RuntimeError('Witness event not received: '+action)
    def close(self):
        self.proc.terminate();self.proc.wait(timeout=10);self.thread.join(timeout=10)
        self.stream.close();self.errors.close()
