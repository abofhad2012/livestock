render_host = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
render_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()

_allowed_hosts = {
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
}
if render_host:
    _allowed_hosts.add(render_host)

_allowed_hosts.update({"127.0.0.1", "localhost"})
ALLOWED_HOSTS = sorted(_allowed_hosts)

_csrf_trusted = {
    u.strip()
    for u in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if u.strip()
}
if render_url:
    _csrf_trusted.add(render_url)

CSRF_TRUSTED_ORIGINS = sorted(_csrf_trusted)