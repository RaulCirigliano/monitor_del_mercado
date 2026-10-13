"""Módulo de inteligencia de horarios de mercado y estado de apertura en tiempo real (Hora Argentina UTC-3)."""

from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

ARG_TZ = timezone(timedelta(hours=-3))


class MarketSchedule:
    """Clasificador y verificador de horarios de mercado para activos globales y locales."""

    # Mapeo de tickers a tipos de mercado
    TICKER_MARKET_MAP = {
        # 🛢️ Materias Primas y Energía
        "CL=F": "COMMODITIES",
        "GC=F": "COMMODITIES",
        "SI=F": "COMMODITIES",
        "NG=F": "COMMODITIES",
        "BZ=F": "COMMODITIES",
        # ⚡ Criptomonedas
        "BTC-USD": "CRYPTO",
        "ETH-USD": "CRYPTO",
        "SOL-USD": "CRYPTO",
        "BTC": "CRYPTO",
        "ETH": "CRYPTO",
        "SOL": "CRYPTO",
        # 🏛️ Bonos e Índices Macro
        "TLT": "BONDS_MACRO",
        "^GSPC": "BONDS_MACRO",
        "SPY": "BONDS_MACRO",
        "QQQ": "BONDS_MACRO",
        "DIA": "BONDS_MACRO",
        "DX-Y.NYB": "COMMODITIES",
        # 🏢 Empresas Globales y Tech
        "AAPL": "GLOBAL_TECH",
        "NVDA": "GLOBAL_TECH",
        "TSLA": "GLOBAL_TECH",
        "MSFT": "GLOBAL_TECH",
        "BABA": "GLOBAL_TECH",
        "AMZN": "GLOBAL_TECH",
        "META": "GLOBAL_TECH",
        "GOOGL": "GLOBAL_TECH",
        # 🇦🇷 Mercado Local / Merval
        "GGAL": "LOCAL_ARG",
        "YPFD": "LOCAL_ARG",
        "PAMP": "LOCAL_ARG",
        "BMA": "LOCAL_ARG",
        "ALUA": "LOCAL_ARG",
        "TXAR": "LOCAL_ARG",
        "GGAL.BA": "LOCAL_ARG",
        "YPFD.BA": "LOCAL_ARG",
    }

    SCHEDULE_CONFIGS = {
        "COMMODITIES": {
            "nombre": "🛢️ Materias Primas y Energía (Futuros)",
            "descripcion": "Activos físicos y refugio macroeconómico. Operan en futuros casi 24hs en la semana, con mayor volumen en aperturas de Londres y Nueva York (04:00 AM - 14:00 PM ARG).",
            "horario_texto": "Dom 19:00 a Vie 18:00 ARG (Pico volumen: 04:00 AM a 14:00 PM ARG)",
            "dias_habiles": [0, 1, 2, 3, 4],  # Lunes a Viernes (y Domingo noche)
            "apertura": time(0, 0),
            "cierre": time(18, 0),
        },
        "CRYPTO": {
            "nombre": "⚡ Criptomonedas",
            "descripcion": "Operan 24/7 continuo con liquidaciones en USDT. Recomendado operar Lunes a Viernes para capturar el flujo institucional real; evitar fines de semana de bajo volumen.",
            "horario_texto": "24/7 Continuo (Recomendado Lunes a Viernes flujo institucional)",
            "dias_habiles": [0, 1, 2, 3, 4, 5, 6],
            "apertura": time(0, 0),
            "cierre": time(23, 59, 59),
        },
        "BONDS_MACRO": {
            "nombre": "🏛️ Bonos e Índices Macro",
            "descripcion": "Marcan el termómetro del dinero institucional y tasas de interés en Wall Street. Horario clave: Lunes a Viernes de 10:30 AM a 17:00 PM ARG.",
            "horario_texto": "Lunes a Viernes de 10:30 AM a 17:00 PM ARG",
            "dias_habiles": [0, 1, 2, 3, 4],  # Lunes a Viernes
            "apertura": time(10, 30),
            "cierre": time(17, 0),
        },
        "GLOBAL_TECH": {
            "nombre": "🏢 Empresas Globales y Tech",
            "descripcion": "Alta volatilidad y sensibilidad a balances. Siguen el horario de Wall Street (10:30 AM a 17:00 PM ARG) y sesión asiática para BABA.",
            "horario_texto": "Lunes a Viernes de 10:30 AM a 17:00 PM ARG",
            "dias_habiles": [0, 1, 2, 3, 4],
            "apertura": time(10, 30),
            "cierre": time(17, 0),
        },
        "LOCAL_ARG": {
            "nombre": "🇦🇷 Mercado Local (BYMA / Merval)",
            "descripcion": "Acciones y bonos argentinos. Sensibles a liquidez local y Dólar CCL. Lunes a Viernes de 11:00 AM a 17:00 PM ARG.",
            "horario_texto": "Lunes a Viernes de 11:00 AM a 17:00 PM ARG",
            "dias_habiles": [0, 1, 2, 3, 4],
            "apertura": time(11, 0),
            "cierre": time(17, 0),
        },
    }

    @classmethod
    def get_market_type(cls, ticker: str) -> str:
        """Determina la categoría de mercado para un símbolo."""
        clean = ticker.strip().upper()
        if clean in cls.TICKER_MARKET_MAP:
            return cls.TICKER_MARKET_MAP[clean]
        if clean.endswith("-USD") or clean.endswith("USDT"):
            return "CRYPTO"
        if clean.endswith("=F"):
            return "COMMODITIES"
        if clean.endswith(".BA"):
            return "LOCAL_ARG"
        # Por defecto tratar como acción global / Wall Street
        return "GLOBAL_TECH"

    @classmethod
    def check_status(cls, ticker: str, ref_dt: Optional[datetime] = None) -> Dict[str, Any]:
        """Calcula el estado de apertura en tiempo real y la próxima ventana de ejecución para el activo."""
        now = ref_dt or datetime.now(ARG_TZ)
        mkt_type = cls.get_market_type(ticker)
        cfg = cls.SCHEDULE_CONFIGS.get(mkt_type, cls.SCHEDULE_CONFIGS["GLOBAL_TECH"])

        weekday = now.weekday()  # 0: Lunes, 6: Domingo
        current_time = now.time()

        if mkt_type == "CRYPTO":
            is_open = True
            estado_texto = "🟢 MERCADO ABIERTO (24/7)"
            proxima_apertura = "Mercado Continuo Activo"
            recomendacion = "El mercado de criptomonedas opera 24/7. Puedes enviar órdenes a tu bot en cualquier momento."
        else:
            is_weekday = weekday in cfg["dias_habiles"]
            apertura = cfg["apertura"]
            cierre = cfg["cierre"]

            if is_weekday and apertura <= current_time < cierre:
                is_open = True
                estado_texto = "🟢 MERCADO ABIERTO EN VIVO"
                proxima_apertura = f"Cierra hoy a las {cierre.strftime('%H:%M')} ARG"
                recomendacion = "El mercado está recibiendo volumen y velas en vivo. Puedes ingresar u ordenar la compra con liquidez real."
            else:
                is_open = False
                estado_texto = "🔴 MERCADO CERRADO"

                # Calcular próxima apertura
                dias_semana_nombres = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
                if is_weekday and current_time < apertura:
                    # Abre hoy más tarde
                    proxima_apertura = f"Hoy a las {apertura.strftime('%H:%M')} ARG"
                elif is_weekday and weekday < 4:
                    # Lunes a Jueves después del cierre: abre mañana
                    proxima_apertura = f"Mañana ({dias_semana_nombres[weekday + 1]}) a las {apertura.strftime('%H:%M')} ARG"
                elif weekday == 4:
                    # Viernes después de hora: abre el Lunes
                    proxima_apertura = f"El próximo Lunes a las {apertura.strftime('%H:%M')} ARG"
                elif weekday == 5:
                    # Sábado: abre el Lunes
                    proxima_apertura = f"El próximo Lunes a las {apertura.strftime('%H:%M')} ARG"
                else:
                    # Domingo: abre el Lunes
                    proxima_apertura = f"Mañana Lunes a las {apertura.strftime('%H:%M')} ARG"

                recomendacion = (
                    f"Tu tesis macro es impecable, pero el mercado físico de {ticker} está cerrado ahora. "
                    f"No dispares órdenes con datos congelados para evitar el riesgo de Gap de apertura. "
                    f"Prepara tu orden para gatillar a partir de: {proxima_apertura}."
                )

        return {
            "ticker": ticker,
            "categoria": cfg["nombre"],
            "descripcion": cfg["descripcion"],
            "horario_argentina": cfg["horario_texto"],
            "mercado_abierto": is_open,
            "estado_texto": estado_texto,
            "proxima_apertura": proxima_apertura,
            "recomendacion_horaria": recomendacion,
        }
