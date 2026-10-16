import json
import logging
import mimetypes
import os
import re
import webbrowser
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from config import settings
from src.ingestion.market_data import MarketDataFetcher
from src.intelligence.ollama_client import OllamaClient
from src.pipeline import MarketMonitorPipeline
from src.dashboard.report_parser import parse_markdown_report

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
RADAR_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "config" / "radar_state.json"
logger = logging.getLogger(__name__)
TRADING_API_BASE = os.environ.get("TRADING_OLLAMA_API_URL", "http://127.0.0.1:18767").rstrip("/")
SHARED_DIRECTIVES_PATH = Path(os.environ.get(
    "TRADING_OLLAMA_PROJECT_DIR",
    Path(__file__).resolve().parents[3] / "trading_ollama",
)) / "guias" / "directivas_cerebro.md"

VALID_RADAR_INTERVALS = {
    0: {"label": "Desactivado", "cron": None},
    15: {"label": "Cada 15 min", "cron": "*/15 * * * *"},
    30: {"label": "Cada 30 min", "cron": "*/30 * * * *"},
    60: {"label": "Cada 60 min", "cron": "0 * * * *"},
    120: {"label": "Cada 2 horas", "cron": "0 */2 * * *"},
}


class DashboardRequestHandler(BaseHTTPRequestHandler):
    """Manejador HTTP REST para el Dashboard del Monitor del Mercado."""

    MAX_REQUEST_BODY = 1_000_000
    _market_fetcher = MarketDataFetcher()
    _last_ollama_models: list[str] = []

    @classmethod
    def _load_radar_config(cls) -> dict:
        default_cfg = {
            "interval_minutes": 0,
            "label": "Desactivado",
            "cron_expression": None,
            "engine": "ollama",
            "model": None,
            "auto_inject": False,
        }
        try:
            if RADAR_STATE_FILE.exists():
                raw = json.loads(RADAR_STATE_FILE.read_text(encoding="utf-8"))
                interval = int(raw.get("interval_minutes", 0))
                if interval not in VALID_RADAR_INTERVALS:
                    interval = 0
                meta = VALID_RADAR_INTERVALS[interval]
                return {
                    "interval_minutes": interval,
                    "label": meta["label"],
                    "cron_expression": meta["cron"],
                    "engine": str(raw.get("engine", "ollama")),
                    "model": str(raw.get("model", "")) or None,
                    "auto_inject": bool(raw.get("auto_inject", False)),
                }
        except Exception as exc:
            logger.warning("No se pudo leer radar_state.json (%s)", exc)
        return default_cfg

    @classmethod
    def _save_radar_config(cls, data: dict) -> dict:
        current = cls._load_radar_config()
        if "interval_minutes" in data:
            try:
                interval = int(data["interval_minutes"])
            except (TypeError, ValueError):
                interval = current["interval_minutes"]
            if interval not in VALID_RADAR_INTERVALS:
                raise ValueError(f"Intervalo inválido. Valores permitidos: {list(VALID_RADAR_INTERVALS.keys())}")
            current["interval_minutes"] = interval
            current["label"] = VALID_RADAR_INTERVALS[interval]["label"]
            current["cron_expression"] = VALID_RADAR_INTERVALS[interval]["cron"]
        if "engine" in data and isinstance(data["engine"], str):
            current["engine"] = data["engine"]
        if "model" in data:
            model = data["model"]
            current["model"] = model if isinstance(model, str) and model else None
        if "auto_inject" in data:
            current["auto_inject"] = bool(data["auto_inject"])
        try:
            RADAR_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            RADAR_STATE_FILE.write_text(json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:
            logger.warning("No se pudo guardar radar_state.json (%s)", exc)
        return current

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

    @staticmethod
    def _request_trading_brain(path: str, method: str = "GET", payload: dict | None = None):
        headers = {}
        api_token = (
            os.environ.get("TRADING_OLLAMA_API_TOKEN")
            or os.environ.get("APP_SECRET_TOKEN")
            or os.environ.get("APP_TOKEN")
            or ""
        ).strip()
        if not api_token:
            try:
                from dotenv import dotenv_values

                trading_root = Path(os.environ.get(
                    "TRADING_OLLAMA_PROJECT_DIR",
                    Path(__file__).resolve().parents[3] / "trading_ollama",
                ))
                trading_config = dotenv_values(trading_root / ".env")
                api_token = str(
                    trading_config.get("APP_SECRET_TOKEN")
                    or trading_config.get("APP_TOKEN")
                    or ""
                ).strip()
            except ImportError:
                api_token = ""
        if api_token:
            headers["X-API-Token"] = api_token
        body = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(payload).encode("utf-8")
        request = Request(f"{TRADING_API_BASE}{path}", data=body, headers=headers, method=method)
        with urlopen(request, timeout=4) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _shared_brain_directives() -> str:
        try:
            return SHARED_DIRECTIVES_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError("No se pudieron leer las directivas canónicas compartidas.") from exc

    def do_OPTIONS(self):
        self._set_headers(405)

    def do_GET(self):
        if self._reject_non_local_request():
            return

        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # 1. Rutas de la API REST
        if path == "/api/system/models":
            try:
                _, payload = self._request_trading_brain("/api/system/models")
                models = payload.get("models", []) if isinstance(payload, dict) else []
                if isinstance(models, list):
                    type(self)._last_ollama_models = models
                self._set_headers(200)
                self.wfile.write(json.dumps(payload).encode("utf-8"))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                logger.warning("No se pudo consultar modelos centrales (%s).", type(exc).__name__)
                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "available": False,
                    "models": type(self)._last_ollama_models,
                    "error": "Trading Ollama no está disponible; se conserva la última lista conocida."
                    if type(self)._last_ollama_models
                    else "Trading Ollama no está disponible y no hay modelos en caché.",
                }).encode("utf-8"))
            return

        if path == "/api/system/brain":
            try:
                _, payload = self._request_trading_brain("/api/system/brain")
                self._set_headers(200)
                self.wfile.write(json.dumps(payload).encode("utf-8"))
            except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
                logger.warning("No se pudo consultar el cerebro central (%s).", type(exc).__name__)
                cfg = self._load_radar_config()
                self._set_headers(200)
                self.wfile.write(json.dumps({
                    "engine": cfg.get("engine", "ollama"),
                    "model": cfg.get("model"),
                    "available": False,
                }).encode("utf-8"))
            return

        elif path == "/api/status":
            cfg = self._load_radar_config()
            active_model = cfg.get("model") or settings.ollama_model
            ollama = OllamaClient(model=active_model)
            ollama_online = ollama.is_available()
            feeds = settings.load_feeds().get("categories", {})
            total_feeds = sum(len(c.get("feeds", [])) for c in feeds.values())
            reports = list(settings.reports_dir.rglob("*.md"))

            payload = {
                "ollama_online": ollama_online,
                "ollama_model": active_model,
                "ollama_model_available": (
                    ollama.is_model_available() if ollama_online else False
                ),
                "reports_count": len(reports),
                "total_feeds": total_feeds,
                "radar_config": cfg,
            }
            self._set_headers(200)
            self.wfile.write(json.dumps(payload).encode("utf-8"))
            return

        elif path == "/api/cio/config":
            self._set_headers(200)
            self.wfile.write(json.dumps(self._load_radar_config()).encode("utf-8"))
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

                try:
                    head = r.open(encoding="utf-8").read(400)
                    motor = "Antigravity CIO" if "Antigravity CIO" in head else "Ollama Local"
                except Exception:
                    motor = "Ollama Local"

                payload.append({
                    "name": r.name,
                    "rel_path": rel_path,
                    "date_folder": date_folder,
                    "size": r.stat().st_size,
                    "modo": modo,
                    "es_vigente": is_vigente,
                    "horas_antiguedad": round(hours_old, 1),
                    "motor_evaluador": motor,
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

        elif path == "/api/cio/candidates":
            category = query.get("category", [None])[0]
            custom_directive = query.get("directive", query.get("custom_directive", [None]))[0]
            limit_str = query.get("limit", ["15"])[0]
            try:
                limit = min(max(int(limit_str), 1), 50)
            except ValueError:
                limit = 15

            try:
                pipeline = MarketMonitorPipeline()
                candidates = pipeline.collect_candidates(
                    category_filter=category or None,
                    custom_directive=custom_directive or None,
                    limit_tickers=limit,
                )
                candidates["radar_config"] = self._load_radar_config()
                self._set_headers(200)
                self.wfile.write(json.dumps(candidates, default=str).encode("utf-8"))
            except Exception as e:
                logger.error("Error recopilando candidatos CIO: %s", e)
                self._set_headers(500)
                self.wfile.write(json.dumps({"error": f"Error recopilando candidatos: {e}"}).encode("utf-8"))
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

    @staticmethod
    def _send_macro_injection(data: dict) -> tuple[int, dict]:
        """Envía una directiva a trading_ollama adjuntando X-API-Token si está configurado.
        Retorna (status_code, response_data)."""
        import os
        import uuid
        from datetime import datetime, timezone
        import urllib.request
        import urllib.error

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
                try:
                    res_json = json.loads(res_body)
                except Exception:
                    res_json = {"raw": res_body}
                return response.status, res_json
        except urllib.error.HTTPError as e:
            logger.warning("Trading Ollama respondió HTTP %s.", e.code)
            return 502, {"error": f"Trading Ollama rechazó la solicitud (HTTP {e.code})."}
        except urllib.error.URLError as e:
            logger.warning("No se pudo contactar Trading Ollama (%s).", type(e).__name__)
            return 502, {
                "error": "No se pudo conectar con Trading Ollama en http://127.0.0.1:18767. "
                "Verifica que el bot de trading esté iniciado y escuchando en el puerto 18767."
            }
        except Exception as e:
            logger.error("Falló la solicitud a Trading Ollama (%s).", type(e).__name__)
            return 500, {"error": "Falló la solicitud al servicio local de Trading Ollama."}

    def _handle_inject_to_trading_bot(self, data: dict | None = None):
        """Reenvía una directiva macro/contrarian a trading_ollama adjuntando X-API-Token si está configurado."""
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

        status_code, res_data = self._send_macro_injection(data)
        self._set_headers(status_code)
        self.wfile.write(json.dumps(res_data).encode("utf-8"))

    def _handle_cio_publish(self):
        """Publica un informe estratégico analizado por Antigravity CIO."""
        try:
            data = self._read_json_body()
        except ValueError as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        from datetime import datetime
        from src.models import AnalysisBatch
        from src.reporting import MarkdownReportGenerator

        data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        data.setdefault("motor_evaluador", "Antigravity CIO")
        data.setdefault(
            "total_noticias_analizadas",
            len(data.get("oportunidades", [])) + len(data.get("alertas_peligro", []))
        )
        data.setdefault("total_ruido_descartado", 0)
        data.setdefault(
            "modo_escaneo",
            "BUSQUEDA_ESPECIFICA" if data.get("directiva_personalizada") else "RADAR_AUTONOMO"
        )

        auto_inject = bool(data.pop("auto_inject", False))
        inject_payload = data.pop("inject_payload", None)

        try:
            batch = AnalysisBatch(**data)
        except Exception as e:
            self._set_headers(400)
            self.wfile.write(json.dumps({"error": f"Esquema de reporte inválido: {e}"}).encode("utf-8"))
            return

        try:
            generator = MarkdownReportGenerator()
            report_path = generator.generate_report(batch)
        except Exception as e:
            logger.error("Error generando reporte CIO: %s", e)
            self._set_headers(500)
            self.wfile.write(json.dumps({"error": f"Error guardando reporte: {e}"}).encode("utf-8"))
            return

        injection_result = None
        if auto_inject or inject_payload:
            target_injection = inject_payload
            if not target_injection and batch.oportunidades:
                top_op = batch.oportunidades[0]
                target_injection = {
                    "asset": top_op.ticker,
                    "text": f"[RSI: {top_op.rsi_14 or 'N/D'} | Z-Score: {top_op.z_score_20 or 'N/D'}] Tesis CIO: {top_op.tesis_contrarian}",
                    "confidence": int(top_op.score_asimetria * 10),
                    "type": "Oportunidad",
                    "source": "Antigravity CIO",
                }
            if target_injection:
                target_injection.setdefault("source", "Antigravity CIO")
                status_code, res_data = self._send_macro_injection(target_injection)
                injection_result = {"status_code": status_code, "response": res_data}

        rel_path = str(report_path.relative_to(settings.reports_dir))
        self._set_headers(200)
        self.wfile.write(
            json.dumps({
                "success": True,
                "report_name": report_path.name,
                "rel_path": rel_path,
                "report_path": str(report_path),
                "batch": batch.model_dump(),
                "injection": injection_result,
            }).encode("utf-8")
        )

    def do_POST(self):
        if self._reject_non_local_request():
            return

        parsed = urlparse(self.path)
        if parsed.path == "/api/system/brain":
            try:
                data = self._read_json_body()
                engine = data.get("engine")
                model = data.get("model")
                if engine not in {"ollama", "gemini", "local", "antigravity_cio"}:
                    raise ValueError("Motor de cerebro inválido.")
                if model is not None and (
                    not isinstance(model, str)
                    or len(model) > 120
                    or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model)
                    or any(part in {"", ".", ".."} for part in model.split("/"))
                ):
                    raise ValueError("Nombre de modelo inválido.")
                status, payload = self._request_trading_brain(
                    "/api/system/brain",
                    method="POST",
                    payload={"engine": engine, "model": model},
                )
                self._save_radar_config({"engine": engine, "model": model})
                self._set_headers(status)
                self.wfile.write(json.dumps(payload).encode("utf-8"))
            except ValueError as exc:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(exc)}).encode("utf-8"))
            except HTTPError as exc:
                self._set_headers(exc.code)
                self.wfile.write(json.dumps({"error": "Trading Ollama rechazó la selección."}).encode("utf-8"))
            except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
                logger.warning("No se pudo actualizar el cerebro central (%s).", type(exc).__name__)
                self._set_headers(502)
                self.wfile.write('{"error":"No se pudo guardar la selección en Trading Ollama."}'.encode("utf-8"))

        elif parsed.path == "/api/scan":
            try:
                data = self._read_json_body()
            except ValueError as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
                return

            category = data.get("category")
            custom_directive = data.get("custom_directive")
            engine = data.get("engine", "ollama")
            model = data.get("model")
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
            if engine not in {"ollama", "gemini"}:
                self._set_headers(400)
                self.wfile.write('{"error":"Motor de análisis inválido para escaneo."}'.encode("utf-8"))
                return
            if model is not None and (
                not isinstance(model, str)
                or len(model) > 120
                or not re.fullmatch(r"[A-Za-z0-9._:/-]+", model)
            ):
                self._set_headers(400)
                self.wfile.write('{"error":"Nombre de modelo inválido."}'.encode("utf-8"))
                return

            # Ejecutar escaneo a través del pipeline
            try:
                pipeline = MarketMonitorPipeline(
                    use_gemini=engine == "gemini",
                    model=model,
                )
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
        elif parsed.path == "/api/cio/publish":
            self._handle_cio_publish()
        elif parsed.path == "/api/cio/config":
            try:
                data = self._read_json_body()
                saved = self._save_radar_config(data)
                self._set_headers(200)
                self.wfile.write(json.dumps(saved, ensure_ascii=False).encode("utf-8"))
            except ValueError as e:
                self._set_headers(400)
                self.wfile.write(json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8"))
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
    server = ThreadingHTTPServer(("127.0.0.1", active_port), DashboardRequestHandler)
    dashboard_url = f"http://localhost:{active_port}"
    print(f"\n🚀 Dashboard de Monitor del Mercado activo en: {dashboard_url}")
    if not os.environ.get("MONITOR_NO_BROWSER"):
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
