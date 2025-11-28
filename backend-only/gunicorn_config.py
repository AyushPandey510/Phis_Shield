"""
Gunicorn Production Configuration for PhisGuard
"""

import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers when code changes (development only)
reload = False

# Security
limit_request_line = 4094
limit_request_fields = 100
limit_request_field_size = 8190

# Process naming
proc_name = 'phisguard-backend'

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "error"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# PID file
pidfile = "/tmp/phisguard.pid"

# User and group to run as (set to appropriate user in production)
# user = "phisguard"
# group = "phisguard"

# Temp directory
tmp_upload_dir = None

# Worker memory management
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# SSL (configure if using HTTPS directly)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

# Environment variables
raw_env = [
    'FLASK_DEBUG=False',
]

# Load environment variables from file
env_file = os.environ.get('GUNICORN_ENV_FILE', '.env')

# Worker heartbeat
worker_tmp_dir = "/dev/shm"

# Hooks
def on_starting(server):
    server.log.info("Starting PhisGuard Gunicorn server")

def on_reload(server):
    server.log.info("Reloading PhisGuard server")

def on_exit(server):
    server.log.info("Shutting down PhisGuard server")

def worker_int(worker):
    worker.log.info("Worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def pre_exec(server):
    server.log.info("Forked child, re-executing.")

def when_ready(server):
    server.log.info("PhisGuard server is ready. Spawning workers")

def worker_abort(worker):
    worker.log.info("Worker received SIGABRT signal")

# Health check endpoint
def health_check(environ, start_response):
    """Simple health check for load balancers"""
    path_info = environ.get('PATH_INFO', '')
    if path_info == '/health':
        status = '200 OK'
        response_headers = [('Content-Type', 'application/json')]
        start_response(status, response_headers)
        return [b'{"status": "healthy", "service": "phisguard-backend"}']
    return False