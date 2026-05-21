from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = parse_qs(urlparse(self.path).query)
        code = qs.get("code", [None])[0]

        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        if code:
            self.wfile.write(
                f"<h2>인가 코드 수신 성공</h2><p>code: {code}</p>".encode("utf-8")
            )
            print("authorize_code =", code)
        else:
            self.wfile.write("<h2>code 파라미터가 없습니다.</h2>".encode("utf-8"))


if __name__ == "__main__":
    print("http://localhost:8000/callback 대기 중...")
    HTTPServer(("localhost", 8000), Handler).serve_forever()
