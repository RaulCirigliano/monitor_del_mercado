import json
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import threading

from config import settings
from src.ingestion.market_data import MarketDataFetcher
from src.intelligence.ollama_client import OllamaClient
from src.pipeline import MarketMonitorPipeline
from src.dashboard.report_parser import parse_markdown_report

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Manejador HTTP REST para el Dashboard del Monitor del Mercado."""

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(200)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. Rutas de la API REST
        if path == "/api/status":
            ollama = OllamaClient()
            feeds = settings.load_feeds().get("categories", {})
            total_feeds = sum(len(c.get("feeds", [])) for c in feeds.values())
            reports = list(settings.reports_dir.glob("*.md"))

            payload = {
                "ollama_online": ollama.is_available(),
                "ollama_model": ollama.model,
                "reports_count": len(reports),
                "total_feeds": total_feeds,
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif path == "/api/reports":
            from datetime import datetime
            reports = sorted(
                settings.reports_dir.rglob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            payload = []
            for r in reports:
                hours_old = max(0.0, (datetime.now() - datetime.fromtimestamp(r.stat().st_mtime)).total_seconds() / 3600.0)
                is_vigente = hours_old <= 48.0
                modo = "BUSQUEDA_ESPECIFICA" if r.name.startswith("ESPECIFICO_") else "RADAR_AUTONOMO"
                rel_path = str(r.relative_to(settings.reports_dir))
                date_folder = r.parent.name if r.parent != settings.reports_dir else "General"

                payload.append({
                    "name": r.name,
                    "rel_path": rel_path,
                    "date_folder": date_folder,
                    "size": r.stat().st_size,
                    "modo": modo,
                    "es_vigente": is_vigente,
                    "horas_antiguedad": round(hours_old, 1),
                })
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif path == "/api/reports/latest":
            reports = sorted(
                settings.reports_dir.rglob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not reports:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": "No hay reportes disponibles"}).encode("utf-8"))
                return

            data = parse_markdown_report(reports[0])
            self._set_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        elif path.startswith("/api/reports/"):
            from urllib.parse import unquote
            rel_path = unquote(path.replace("/api/reports/", ""))
            target_file = (settings.reports_dir / rel_path).resolve()

            # Fallback: si no existe en esa ruta exacta, buscar por nombre de archivo
            if not target_file.exists() or not target_file.is_file():
                filename = Path(rel_path).name
                matches = list(settings.reports_dir.rglob(filename))
                if matches:
                    target_file = matches[0]

            if not target_file.exists() or not target_file.is_file():
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Reporte '{rel_path}' no encontrado"}).encode("utf-8"))
                return

            data = parse_markdown_report(target_file)
            self._set_headers(200)
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return


        elif path == "/api/ticker":
            symbol = query.get("symbol", [""])[0].strip()
            if not symbol:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": "Falta parámetro symbol"}).encode("utf-8"))
                return
            fetcher = MarketDataFetcher()
            snap = fetcher.get_snapshot(symbol)
            if not snap:
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"No se encontraron datos para {symbol}"}).encode("utf-8"))
                return

            from src.ingestion.market_schedule import MarketSchedule
            sch = MarketSchedule.check_status(symbol)
            snap_dict = snap.model_dump()
            snap_dict["schedule"] = sch

            self._set_headers(200)
            self.wfile.write(json.dumps(snap_dict).encode("utf-8"))
            return

        elif path == "/api/market-hours":
            from src.ingestion.market_schedule import MarketSchedule
            configs = MarketSchedule.SCHEDULE_CONFIGS
            self._set_headers(200)
            self.wfile.write(json.dumps(configs, default=str).encode("utf-8"))
            return

        # 2. Servir frontend estático (HTML, JS, CSS)
        if path == "/" or path == "/index.html":
            file_path = WEB_DIR / "index.html"
        else:
            file_path = WEB_DIR / path.lstrip("/")

        if file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            content_type = mime_type or "text/plain"
            self._set_headers(200, content_type)
            self.wfile.write(file_path.read_bytes())
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            category = data.get("category")
            custom_directive = data.get("custom_directive")

            # Ejecutar escaneo a través del pipeline
            try:
                pipeline = MarketMonitorPipeline()
                batch = pipeline.run(
                    category_filter=category,
                    custom_directive=custom_directive,
                )
                self._set_headers(200)
                self.wfile.write(batch.model_dump_json().encode("utf-8"))

            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

        elif parsed.path == "/api/inject_to_trading_bot":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length > 0 else b"{}"
            try:
                data = json.loads(body.decode("utf-8"))
            except Exception:
                data = {}

            # Reenvío directo a Trading Ollama en http://127.0.0.1:18767/api/macro/inject
            import urllib.request
            import urllib.error

            target_url = "http://127.0.0.1:18767/api/macro/inject"
            req_data = json.dumps(data).encode("utf-8")
            req = urllib.request.Request(
                target_url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            try:
                with urllib.request.urlopen(req, timeout=4) as response:
                    res_body = response.read().decode("utf-8")
                    self._set_headers(response.status)
                    self.wfile.write(res_body.encode("utf-8"))
            except urllib.error.URLError as e:
                self._set_headers(502)
                err_msg = (
                    "No se pudo conectar con Trading Ollama en http://127.0.0.1:18767. "
                    "Verifica que el bot de trading esté iniciado y escuchando en el puerto 18767."
                )
                self.wfile.write(json.dumps({"error": err_msg, "detail": str(e)}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/reports/"):
            from urllib.parse import unquote
            rel_path = unquote(path.replace("/api/reports/", "")).strip("/")
            target_file = (settings.reports_dir / rel_path).resolve()

            # Fallback si se pasa solo el nombre de archivo
            if not target_file.exists() or not target_file.is_file():
                filename = Path(rel_path).name
                matches = list(settings.reports_dir.rglob(filename))
                if matches:
                    target_file = matches[0]

            if not target_file.exists() or not target_file.is_file():
                self._set_headers(404)
                self.wfile.write(json.dumps({"error": f"Reporte '{rel_path}' no encontrado"}).encode("utf-8"))
                return

            try:
                parent_dir = target_file.parent
                deleted_name = target_file.name
                target_file.unlink()

                # Si el directorio de fecha queda vacío, eliminarlo limpiamente
                if parent_dir != settings.reports_dir and not any(parent_dir.iterdir()):
                    try:
                        parent_dir.rmdir()
                    except Exception:
                        pass

                self._set_headers(200)
                self.wfile.write(json.dumps({"success": True, "deleted": deleted_name}).encode("utf-8"))
            except Exception as e:
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": f"Error al borrar reporte: {e}"}).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')


def find_free_port(start_port: int = 8520, max_attempts: int = 20) -> int:
    """Busca automáticamente el primer puerto libre a partir de start_port."""
    import socket
    for p in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    return start_port


def start_dashboard_server(port: int = 8520):
    """Inicia el servidor web local con auto-resolución de conflictos de puertos."""
    active_port = find_free_port(port)
    server = HTTPServer(("0.0.0.0", active_port), DashboardRequestHandler)
    print(f"\n🚀 Dashboard de Monitor del Mercado activo en: http://localhost:{active_port}")
    print(f"👉 Abre http://localhost:{active_port} en tu navegador para interactuar con el bot y ver las oportunidades.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor dashboard detenido.")
        server.server_close()
