from socket import *
from fib import fib
#from threading import Thread for use with Thread
#from concurrent.futures import ProcessPoolExecutor as Pool for use with Thread
from concurrent.futures import ProcessPoolExecutor as Pool
from collections import deque
from select import select

pool = Pool(8)
tasks = deque()
recv_wait = { }
send_wait = { }
future_wait = { }

future_notify, future_event = socketpair()

def future_done(future):
    tasks.append(future_wait.pop(future))
    future_notify.send(b'x')

def future_monitor():
    while True:
        yield 'recv', future_event
        future_event.recv(100)

tasks.append(future_monitor())
def run():
    while any ([tasks, recv_wait, send_wait]):
        while not tasks:
            can_recv, can_send, _ = select(recv_wait, send_wait, [])
            for s in can_recv:
                tasks.append(recv_wait.pop(s))
            for s in can_send:
                tasks.append(send_wait.pop(s))
        task = tasks.popleft()
        try:
            why, what = next(task) # Run to yield
            if why == 'recv':
                recv_wait[what] = task
            elif why == 'send':
                send_wait[what] = task
            elif why == 'future':
                future_wait[what] = task
                what.add_done_callback(future_done)
            else:
                raise RuntimeError("ARG!")
        except StopIteration:
            print("task done")

class AsyncSocket(object):
    def __init__(self, sock):
        self.sock = sock
    def recv(self, maxsize):
        yield 'recv', self.sock
        return self.sock.recv(maxsize)
    def send(self, data):
        yield 'send', self.sock
        return self.sock.send(data)
    def accept(self):
        yield 'recv', self.sock
        client, addr = self.sock.accept()
        return AsyncSocket(client), addr
    def __getattr__(self, name):
        return getattr(self.sock, name)


# pool = Pool(4)
def fib_server(address):
    sock = AsyncSocket(socket(AF_INET, SOCK_STREAM))
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(5)
    while True:
        client, addr = yield from sock.accept()
        print("Connection", addr)
        tasks.append(fib_handler(client))
        #Thread(target=fib_handler, args=(client,), daemon=True).start() for use with Thread

def fib_handler(client):
    while True:
        req = yield from client.recv(100)
        if not req:
            break
        n = int(req)
        #future = pool.submit(fib, n) for use with thread
        #result = future.result() for use with Thread
        future = pool.submit(fib, n)
        yield 'future', future
        result = future.result()
        resp = str(result).encode('ascii') + b'\n'
        yield from client.send(resp)
    print("Closed")

tasks.append(fib_server(('',25000)))
run()