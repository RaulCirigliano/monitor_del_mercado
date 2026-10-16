"""Módulo de inteligencia de horarios de mercado y estado de apertura en tiempo real (Hora Argentina UTC-3)."""

import calendar
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

ARG_TZ = timezone(timedelta(hours=-3))
NEW_YORK_TZ = ZoneInfo("America/New_York")


class MarketSchedule:
    """Clasificador y verificador de horarios de mercado para activos globales y locales."""

    @staticmethod
    def _easter_sunday(year: int) -> date:
        """Calcula la fecha gregoriana de Pascua para determinar Viernes Santo."""
        a = year % 19
        b, c = divmod(year, 100)
        d, e = divmod(b, 4)
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i, k = divmod(c, 4)
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        month = (h + l - 7 * m + 114) // 31
        day = (h + l - 7 * m + 114) % 31 + 1
        return date(year, month, day)

    @staticmethod
    def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
        holiday = date(year, month, day)
        if holiday.weekday() == 5:
            return holiday - timedelta(days=1)
        if holiday.weekday() == 6:
            return holiday + timedelta(days=1)
        return holiday

    @classmethod
    def _us_market_holidays(cls, year: int) -> set[date]:
        """NYSE full-day holidays (excluding exceptional closures and early closes)."""
        holidays = {
            cls._observed_fixed_holiday(year, 1, 1),
            cls._observed_fixed_holiday(year, 7, 4),
            cls._observed_fixed_holiday(year, 12, 25),
            cls._easter_sunday(year) - timedelta(days=2),
        }
        if year >= 2022:
            holidays.add(cls._observed_fixed_holiday(year, 6, 19))
        next_new_year = date(year + 1, 1, 1)
        if next_new_year.weekday() == 5:
            holidays.add(next_new_year - timedelta(days=1))

        holidays.add(date(year, 1, 1) + timedelta(days=(0 - date(year, 1, 1).weekday()) % 7 + 14))
        holidays.add(date(year, 2, 1) + timedelta(days=(0 - date(year, 2, 1).weekday()) % 7 + 14))
        holidays.add(date(year, 5, calendar.monthrange(year, 5)[1]) - timedelta(
            days=(date(year, 5, calendar.monthrange(year, 5)[1]).weekday() - 0) % 7
        ))
        holidays.add(date(year, 9, 1) + timedelta(days=(0 - date(year, 9, 1).weekday()) % 7))
        thanksgiving = date(year, 11, 1)
        thanksgiving += timedelta(days=(3 - thanksgiving.weekday()) % 7 + 21)
        holidays.add(thanksgiving)
        return holidays

    @classmethod
    def _next_us_open(cls, now_ny: datetime) -> datetime:
        candidate_date = now_ny.date()
        while True:
            if (
                candidate_date.weekday() < 5
                and candidate_date not in cls._us_market_holidays(candidate_date.year)
            ):
                candidate = datetime.combine(candidate_date, time(9, 30), NEW_YORK_TZ)
                if candidate > now_ny:
                    return candidate
            candidate_date += timedelta(days=1)

    @classmethod
    def _us_market_close(cls, session_date: date) -> time:
        thanksgiving = date(session_date.year, 11, 1)
        thanksgiving += timedelta(days=(3 - thanksgiving.weekday()) % 7 + 21)
        if session_date in {thanksgiving + timedelta(days=1), date(session_date.year, 12, 24), date(session_date.year, 7, 3)}:
            return time(13, 0)
        return time(16, 0)

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
        # 🏢 Empresas Globales, Tech y ETFs Temáticos
        "AAPL": "GLOBAL_TECH",
        "NVDA": "GLOBAL_TECH",
        "TSLA": "GLOBAL_TECH",
        "MSFT": "GLOBAL_TECH",
        "BABA": "GLOBAL_TECH",
        "AMZN": "GLOBAL_TECH",
        "META": "GLOBAL_TECH",
        "GOOGL": "GLOBAL_TECH",
        "MCHI": "GLOBAL_TECH",
        "KWEB": "GLOBAL_TECH",
        "BOTZ": "GLOBAL_TECH",
        # 🇦🇷 Mercado Local / Merval
        "GGAL": "LOCAL_ARG",
        "YPFD": "LOCAL_ARG",
        "PAMP": "LOCAL_ARG",
        "BMA": "LOCAL_ARG",
        "ALUA": "LOCAL_ARG",
        "TXAR": "LOCAL_ARG",
        "GGAL.BA": "LOCAL_ARG",
        "YPFD.BA": "LOCAL_ARG",
        "PAMP.BA": "LOCAL_ARG",
        "BMA.BA": "LOCAL_ARG",
        "ALUA.BA": "LOCAL_ARG",
        "TXAR.BA": "LOCAL_ARG",
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
            "descripcion": "Marcan el termómetro del dinero institucional y tasas de interés en Wall Street. Sesión regular: 09:30-16:00 hora de Nueva York; el horario argentino cambia con el horario de verano de EE. UU.",
            "horario_texto": "Lunes a Viernes de 09:30 a 16:00 hora de Nueva York (ARG varía según horario de verano)",
            "dias_habiles": [0, 1, 2, 3, 4],  # Lunes a Viernes
            "apertura": time(10, 30),
            "cierre": time(17, 0),
        },
        "GLOBAL_TECH": {
            "nombre": "🏢 Empresas Globales y Tech",
            "descripcion": "Alta volatilidad y sensibilidad a balances. Siguen la sesión regular de Wall Street (09:30-16:00 hora de Nueva York); el horario argentino cambia con el horario de verano de EE. UU.",
            "horario_texto": "Lunes a Viernes de 09:30 a 16:00 hora de Nueva York (ARG varía según horario de verano)",
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
        if now.tzinfo is None:
            now = now.replace(tzinfo=ARG_TZ)
        else:
            now = now.astimezone(ARG_TZ)
        mkt_type = cls.get_market_type(ticker)
        cfg = cls.SCHEDULE_CONFIGS.get(mkt_type, cls.SCHEDULE_CONFIGS["GLOBAL_TECH"])
        horario_texto = cfg["horario_texto"]

        if mkt_type == "CRYPTO":
            is_open = True
            estado_texto = "🟢 MERCADO ABIERTO (24/7)"
            proxima_apertura = "Mercado Continuo Activo"
            recomendacion = "Las criptomonedas operan 24/7. El estado horario es informativo; el monitor no transmite ni ejecuta órdenes."
        elif mkt_type == "COMMODITIES":
            weekday = now.weekday()
            current_time = now.time()
            sunday_open = time(19, 0)
            friday_close = time(18, 0)
            is_open = (
                (weekday == 6 and current_time >= sunday_open)
                or weekday in {0, 1, 2, 3}
                or (weekday == 4 and current_time < friday_close)
            )
            if is_open:
                estado_texto = "🟢 MERCADO ABIERTO (horario semanal estimado)"
                proxima_apertura = "Sesión semanal de futuros en curso"
                recomendacion = "Horario semanal estimado. El monitor no transmite ni ejecuta órdenes."
            else:
                estado_texto = "🔴 MERCADO CERRADO"
                proxima_apertura = (
                    "Hoy a las 19:00 ARG"
                    if weekday == 6
                    else "Domingo a las 19:00 ARG"
                )
                recomendacion = (
                    f"Fuera del horario semanal estimado; próxima apertura: {proxima_apertura}. "
                    "El monitor no transmite ni ejecuta órdenes."
                )
        elif mkt_type in {"BONDS_MACRO", "GLOBAL_TECH"}:
            now_ny = now.astimezone(NEW_YORK_TZ)
            session_open = datetime.combine(now_ny.date(), time(9, 30), NEW_YORK_TZ)
            session_close = datetime.combine(
                now_ny.date(), cls._us_market_close(now_ny.date()), NEW_YORK_TZ
            )
            is_open = (
                now_ny.weekday() < 5
                and now_ny.date() not in cls._us_market_holidays(now_ny.year)
                and session_open <= now_ny < session_close
            )
            open_arg = session_open.astimezone(ARG_TZ).strftime("%H:%M")
            close_arg = session_close.astimezone(ARG_TZ).strftime("%H:%M")
            horario_texto = f"Lunes a Viernes de {open_arg} a {close_arg} ARG (09:30-16:00 Nueva York)"
            if is_open:
                estado_texto = "🟢 MERCADO ABIERTO EN VIVO"
                proxima_apertura = f"Cierra hoy a las {close_arg} ARG"
                recomendacion = "El mercado figura en horario de sesión. El monitor no transmite ni ejecuta órdenes."
            else:
                next_open = cls._next_us_open(now_ny)
                next_open_arg = next_open.astimezone(ARG_TZ)
                day_names = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
                if next_open_arg.date() == now.date():
                    proxima_apertura = f"Hoy a las {next_open_arg.strftime('%H:%M')} ARG"
                else:
                    proxima_apertura = (
                        f"{day_names[next_open_arg.weekday()].capitalize()} "
                        f"{next_open_arg.strftime('%d/%m')} a las {next_open_arg.strftime('%H:%M')} ARG"
                    )
                estado_texto = "🔴 MERCADO CERRADO"
                recomendacion = (
                    f"El mercado de {ticker} figura cerrado; las cotizaciones pueden estar desactualizadas. "
                    f"Próxima apertura estimada: {proxima_apertura}. El monitor no transmite ni ejecuta órdenes."
                )
        else:
            weekday = now.weekday()  # 0: Lunes, 6: Domingo
            current_time = now.time()
            is_weekday = weekday in cfg["dias_habiles"]
            apertura = cfg["apertura"]
            cierre = cfg["cierre"]

            if is_weekday and apertura <= current_time < cierre:
                is_open = True
                estado_texto = "🟢 MERCADO ABIERTO EN VIVO"
                proxima_apertura = f"Cierra hoy a las {cierre.strftime('%H:%M')} ARG"
                recomendacion = "El mercado figura en horario de sesión. El monitor no transmite ni ejecuta órdenes."
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
                    f"El mercado de {ticker} figura cerrado; las cotizaciones pueden estar desactualizadas. "
                    f"Próxima apertura estimada: {proxima_apertura}. El monitor no transmite ni ejecuta órdenes."
                )

        return {
            "ticker": ticker,
            "categoria": cfg["nombre"],
            "descripcion": cfg["descripcion"],
            "horario_argentina": horario_texto,
            "mercado_abierto": is_open,
            "estado_texto": estado_texto,
            "proxima_apertura": proxima_apertura,
            "recomendacion_horaria": recomendacion,
        }
