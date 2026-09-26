# Incident Desk reference deployment
This benchmark runs locally using Python's reference WSGI server. It is not a
production deployment. For production select and pin a supported WSGI server,
run as a dedicated unprivileged user, bind to loopback behind a TLS reverse
proxy, and store DB_PATH on a persistent volume writable only by that user.
Inject API_KEY through the runtime secret manager; never put it in source,
command-line arguments, request logs, or images. Rotate by replacing the runtime
secret and restarting at an announced maintenance boundary.

Launch local acceptance service: API_KEY=<local-test-key> DB_PATH=<path> python3 service.py
PORT defaults to 8080. Stop with SIGTERM; the supervisor should wait and restart.
SQLite writes are short transactions. This reference service is single-host.
Use SQLite's online backup API, encrypt backups, and test restoration to a new
path with the service stopped before switching DB_PATH. Check /healthz after
restoration and compare incident counts. No HA or load-test claim is made.
