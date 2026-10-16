import json
import logging
import mimetypes
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlsplit

from config import settings
from src.ingestion.market_data import MarketDataFetcher
from src.intelligence.ollama_client import OllamaClient
from src.pipeline import MarketMonitorPipeline
from src.dashboard.report_parser import parse_markdown_report

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
logger = logging.getLogger(__name__)


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Manejador HTTP REST para el Dashboard del Monitor del Mercado."""

    MAX_REQUEST_BODY = 1_000_000
    _market_fetcher = MarketDataFetcher()

    def _set_headers(self, status: int = 200, content_type: str = "application/json"):
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.end_headers()

    def _is_local_request(self) -> bool:
        host = self.headers.get("Host", "")
        try:
            parsed_host = urlsplit(f"//{host}")
            if parsed_host.hostname not in {"localhost", "127.0.0.1", "::1"}:
                return False
        except ValueError:
            return False

        origin = self.headers.get("Origin")
        if origin:
            try:
                parsed_origin = urlsplit(origin)
                if parsed_origin.scheme != "http" or parsed_origin.hostname not in {
                    "localhost",
                    "127.0.0.1",
                    "::1",
                }:
                    return False
                if parsed_origin.netloc.lower() != host.lower():
                    return False
            except ValueError:
                return False
        return True

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length inválido") from exc
        if length < 0 or length > self.MAX_REQUEST_BODY:
            raise ValueError("Tamaño de solicitud inválido")
        try:
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("El cuerpo debe contener JSON válido") from exc
        if not isinstance(data, dict):
            raise ValueError("El cuerpo JSON debe ser un objeto")
        return data

    @staticmethod
    def _resolve_report_path(rel_path: str):
        reports_root = settings.reports_dir.resolve()
        target = (reports_root / rel_path).resolve()
        if not target.is_relative_to(reports_root) or target.suffix.lower() != ".md":
            return None
        return target

    def _reject_non_local_request(self) -> bool:
        if self._is_local_request():
            return False
        self._set_headers(403)
        self.wfile.write(b'{"error":"Solo se permiten solicitudes locales"}')
        return True

    def do_OPTIONS(self):
        self._set_headers(405)

    def do_GET(self):
        if self._reject_non_local_request():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. Rutas de la API REST
        if path == "/api/status":
            ollama = OllamaClient()
            ollama_online = ollama.is_available()
            feeds = settings.load_feeds().get("categories", {})
            total_feeds = sum(len(c.get("feeds", [])) for c in feeds.values())
            reports = list(settings.reports_dir.rglob("*.md"))

            payload = {
                "ollama_online": ollama_online,
                "ollama_model": ollama.model,
                "ollama_model_available": (
                    ollama.is_model_available() if ollama_online else False
                ),
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
            target_file = self._resolve_report_path(rel_path)

            # Fallback: si no existe en esa ruta exacta, buscar por nombre de archivo
            if target_file is not None and (not target_file.exists() or not target_file.is_file()):
                filename = Path(rel_path).name
                matches = list(settings.reports_dir.rglob(filename))
                if matches:
                    target_file = self._resolve_report_path(
                        str(matches[0].relative_to(settings.reports_dir))
                    )

            if target_file is None or not target_file.exists() or not target_file.is_file():
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
            snap = self._market_fetcher.get_snapshot(symbol)
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
        file_path = file_path.resolve()

        if file_path.is_relative_to(WEB_DIR.resolve()) and file_path.exists() and file_path.is_file():
            mime_type, _ = mimetypes.guess_type(str(file_path))
            content_type = mime_type or "text/plain"
            self._set_headers(200, content_type)
            self.wfile.write(file_path.read_bytes())
        else:
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")

    def _handle_inject_to_trading_bot(self, data: dict | None = None):
        """Reenvía una directiva macro/contrarian a trading_ollama adjuntando X-API-Token si está configurado."""
        import os
        import uuid
        from datetime import datetime, timezone
        import urllib.request
        import urllib.error

        if data is None:
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

        if (
            not isinstance(data.get("asset"), str)
            or not isinstance(data.get("text"), str)
            or not isinstance(data.get("type"), str)
        ):
            self._set_headers(400)
            self.wfile.write(
                '{"error":"La inyección requiere asset, text y type de texto"}'.encode("utf-8")
            )
            return

        payload = dict(data)
        payload.setdefault("id", str(uuid.uuid4()))
        payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        payload.setdefault("source", "Monitor del Mercado")

        headers = {"Content-Type": "application/json"}
        api_token = (
            os.environ.get("TRADING_OLLAMA_API_TOKEN")
            or os.environ.get("APP_SECRET_TOKEN")
            or os.environ.get("APP_TOKEN")
            or ""
        ).strip()
        if api_token:
            headers["X-API-Token"] = api_token

        target_url = "http://127.0.0.1:18767/api/macro/inject"
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=req_data,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=4) as response:
                res_body = response.read().decode("utf-8")
                self._set_headers(response.status)
                self.wfile.write(res_body.encode("utf-8"))
        except urllib.error.HTTPError as e:
            logger.warning("Trading Ollama respondió HTTP %s.", e.code)
            self._set_headers(502)
            self.wfile.write(
                json.dumps(
                    {"error": f"Trading Ollama rechazó la solicitud (HTTP {e.code})."}
                ).encode("utf-8")
            )
        except urllib.error.URLError as e:
            logger.warning("No se pudo contactar Trading Ollama (%s).", type(e).__name__)
            self._set_headers(502)
            err_msg = (
                "No se pudo conectar con Trading Ollama en http://127.0.0.1:18767. "
                "Verifica que el bot de trading esté iniciado y escuchando en el puerto 18767."
            )
            self.wfile.write(json.dumps({"error": err_msg}).encode("utf-8"))
        except Exception as e:
            logger.error("Falló la solicitud a Trading Ollama (%s).", type(e).__name__)
            self._set_headers(500)
            self.wfile.write(
                json.dumps(
                    {"error": "Falló la solicitud al servicio local de Trading Ollama."}
                ).encode("utf-8")
            )

    def do_POST(self):
        if self._reject_non_local_request():
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/scan":
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

            category = data.get("category")
            custom_directive = data.get("custom_directive")
            valid_categories = set(settings.load_feeds().get("categories", {}))
            if category is not None and (
                not isinstance(category, str) or category not in valid_categories
            ):
                self._set_headers(400)
                self.wfile.write('{"error":"Categoría de escaneo inválida"}'.encode("utf-8"))
                return
            if custom_directive is not None and (
                not isinstance(custom_directive, str) or len(custom_directive) > 500
            ):
                self._set_headers(400)
                self.wfile.write('{"error":"Directiva inválida (máximo 500 caracteres)"}'.encode("utf-8"))
                return

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
                logger.error("Falló el escaneo del dashboard (%s).", type(e).__name__)
                self._set_headers(500)
                self.wfile.write(
                    b'{"error":"No se pudo completar el escaneo. Revisa el registro local."}'
                )

        elif parsed.path == "/api/inject_to_trading_bot":
            self._handle_inject_to_trading_bot()
        else:
            self._set_headers(404)
            self.wfile.write(b'{"error": "Ruta no encontrada"}')

    def do_DELETE(self):
        if self._reject_non_local_request():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        if path.startswith("/api/reports/"):
            from urllib.parse import unquote
            rel_path = unquote(path.replace("/api/reports/", "")).strip("/")
            target_file = self._resolve_report_path(rel_path)

            # Fallback si se pasa solo el nombre de archivo
            if target_file is not None and (not target_file.exists() or not target_file.is_file()):
                filename = Path(rel_path).name
                matches = list(settings.reports_dir.rglob(filename))
                if matches:
                    target_file = self._resolve_report_path(
                        str(matches[0].relative_to(settings.reports_dir))
                    )

            if target_file is None or not target_file.exists() or not target_file.is_file():
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
            try:
                s.bind(("127.0.0.1", p))
                return p
            except OSError:
                continue
    raise OSError(f"No hay puertos libres entre {start_port} y {start_port + max_attempts - 1}")


def start_dashboard_server(port: int = 8520):
    """Inicia el servidor web local con auto-resolución de conflictos de puertos."""
    active_port = find_free_port(port)
    server = HTTPServer(("127.0.0.1", active_port), DashboardRequestHandler)
    dashboard_url = f"http://localhost:{active_port}"
    print(f"\n🚀 Dashboard de Monitor del Mercado activo en: {dashboard_url}")
    try:
        if not webbrowser.open(dashboard_url):
            print(f"👉 Abre {dashboard_url} en tu navegador.\n")
    except webbrowser.Error as exc:
        print(f"👉 No se pudo abrir el navegador automáticamente: {exc}")
        print(f"   Abre {dashboard_url} manualmente.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor dashboard detenido.")
    finally:
        server.server_close()
