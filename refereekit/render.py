# refereekit/render.py
import socket, functools, http.server
from .session import Session

_MARKER = "<!-- INSERT-BELOW -->"

_TEMPLATE = """<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title>
<script>window.MathJax={{tex:{{inlineMath:[['\\\\(','\\\\)'],['$','$']]}}}};</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js" async></script>
<style>body{{font-family:Georgia,serif;max-width:820px;margin:0 auto;padding:24px;line-height:1.6}}
.card{{border:1px solid #ddd;border-radius:10px;margin:18px 0;padding:14px 18px}}
.q{{font-weight:600;background:#f6f6f4;margin:-14px -18px 12px;padding:12px 18px;border-radius:10px 10px 0 0}}
.num{{float:right;color:#999;font-size:12px}}</style></head><body>
<h2>{title}</h2>
{marker}
<script>
let last=null;
setInterval(async()=>{{try{{const r=await fetch(location.href,{{method:'HEAD',cache:'no-store'}});
const m=r.headers.get('Last-Modified');if(last&&m&&m!==last)location.reload();if(m)last=m;}}catch(e){{}}}},1500);
</script></body></html>"""

def init_page(session: Session, title: str) -> None:
    session.html.write_text(_TEMPLATE.format(title=title, marker=_MARKER))
    session.set_state("qa_count", 0)

def append_qa(session: Session, question: str, answer_html: str) -> None:
    n = int(session.get_state("qa_count", 0)) + 1
    card = f'<div class="card"><div class="q"><span class="num">#{n}</span>{question}</div>{answer_html}</div>\n'
    html = session.html.read_text().replace(_MARKER, _MARKER + card, 1)
    session.html.write_text(html)
    session.set_state("qa_count", n)

def pick_port(preferred: int = 8888) -> int:
    port = preferred
    for _ in range(50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
        port += 1
    return preferred

def serve(session: Session, port: int) -> None:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(session.dir))
    http.server.HTTPServer(("127.0.0.1", port), handler).serve_forever()
