from __future__ import annotations

import csv
import io
import json
import logging
import math
import re
import urllib.parse
import urllib.request
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import pandas as pd


LOGGER = logging.getLogger("build_coimbatore_maize_v3_dataset")

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "backend" / "data"

ZIP_PATH = REPO_ROOT / "ladies_finger.zip"
CURRENT_MAIZE_PATH = DATA_DIR / "maize.csv"
POLICY_PATH = DATA_DIR / "coimbatore_crop_policy_2023_2026.csv"

MODEL_V1_PATH = DATA_DIR / "coimbatore_maize_model_daily.csv"
MODEL_V2_PATH = DATA_DIR / "coimbatore_maize_model_daily_v2.csv"
MODEL_V3_PATH = DATA_DIR / "coimbatore_maize_model_daily_v3.csv"

PANEL_V2_PATH = DATA_DIR / "coimbatore_maize_market_panel_v2.csv"
PANEL_V3_PATH = DATA_DIR / "coimbatore_maize_market_panel_v3.csv"

WEATHER_V3_PATH = DATA_DIR / "coimbatore_weather_nasa_power_daily_20200102_20251030.csv"
VALIDATION_V3_PATH = DATA_DIR / "coimbatore_maize_model_daily_v3_validation.json"

COIMBATORE_LATITUDE = 11.0168
COIMBATORE_LONGITUDE = 76.9558
COIMBATORE_ELEVATION_M = 540.94
NASA_POWER_DAILY_POINT_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
NASA_PARAMETERS = {
    "T2M": "tavg",
    "T2M_MIN": "tmin",
    "T2M_MAX": "tmax",
    "PRECTOTCORR": "prcp",
    "WD10M": "wdir",
    "WS10M": "wspd",
    "PS": "pres",
}
POLICY_COLUMNS = [
    "msp_applicable",
    "msp_value_per_quintal",
    "govt_procurement_active",
    "pmfby_insurance_active",
    "state_scheme_active",
    "harvest_season_active",
    "price_impact_direction",
]


@dataclass(frozen=True)
class DailyAggregate:
    modal_price: float
    min_price: float
    max_price: float
    markets_reporting: int
    varieties_reporting: int
    rows_reporting: int


def parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%y", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported date format: {value}")


def parse_float(value) -> float | None:
    value = "" if value is None else str(value).strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def normalize_text(value) -> str:
    value = "" if pd.isna(value) else str(value).strip().lower()
    return re.sub(r"\s+", " ", value)


def load_policy_rows() -> list[dict]:
    rows: list[dict] = []
    with POLICY_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["crop"].strip().lower() != "maize":
                continue
            rows.append(
                {
                    "date": parse_date(row["date"]),
                    "msp_applicable": row["msp_applicable"].strip(),
                    "msp_value_per_quintal": row["msp_value_per_quintal"].strip(),
                    "govt_procurement_active": row["govt_procurement_active"].strip(),
                    "pmfby_insurance_active": row["pmfby_insurance_active"].strip(),
                    "state_scheme_active": row["state_scheme_active"].strip(),
                    "harvest_season_active": row["harvest_season_active"].strip(),
                    "price_impact_direction": row["price_impact_direction"].strip(),
                }
            )
    rows.sort(key=lambda item: item["date"])
    return rows


def build_market_id_lookup(current_rows: list[dict]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for row in current_rows:
        market_norm = row["market_name_norm"]
        market_id = row["market_id"]
        if market_norm and market_id and market_norm not in lookup:
            lookup[market_norm] = market_id
    return lookup


def load_zip_maize_rows(market_id_lookup: dict[str, str]) -> list[dict]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        with archive.open("maize.csv") as fh:
            df = pd.read_csv(io.BytesIO(fh.read()))

    df = df[df["District Name"].astype(str).str.strip().str.lower() == "coimbatore"].copy()
    rows: list[dict] = []
    for _, row in df.iterrows():
        market_name = str(row["Market Name"]).strip()
        variety = str(row["Variety"]).strip()
        market_name_norm = normalize_text(market_name)
        variety_norm = normalize_text(variety)
        rows.append(
            {
                "date": parse_date(str(row["Price Date"])),
                "market_id": market_id_lookup.get(market_name_norm, ""),
                "market_name": market_name,
                "crop": str(row["Commodity"]).strip(),
                "variety": variety,
                "min_price": parse_float(row["Min Price (Rs./Quintal)"]),
                "max_price": parse_float(row["Max Price (Rs./Quintal)"]),
                "modal_price": parse_float(row["Modal Price (Rs./Quintal)"]),
                "market_name_norm": market_name_norm,
                "variety_norm": variety_norm,
                "source": "zip",
            }
        )
    rows.sort(key=lambda item: (item["date"], item["market_name_norm"], item["variety_norm"]))
    return rows


def load_current_maize_rows() -> list[dict]:
    df = pd.read_csv(CURRENT_MAIZE_PATH)
    df = df[df["district_name"].astype(str).str.strip().str.lower() == "coimbatore"].copy()

    rows: list[dict] = []
    for _, row in df.iterrows():
        market_name = str(row["market_name"]).strip()
        variety = str(row["variety"]).strip()
        rows.append(
            {
                "date": parse_date(str(row["t"])),
                "market_id": str(row["market_id"]).strip(),
                "market_name": market_name,
                "crop": str(row["cmdty"]).strip(),
                "variety": variety,
                "min_price": parse_float(row["p_min"]),
                "max_price": parse_float(row["p_max"]),
                "modal_price": parse_float(row["p_modal"]),
                "market_name_norm": normalize_text(market_name),
                "variety_norm": normalize_text(variety),
                "source": "current_raw",
            }
        )
    rows.sort(key=lambda item: (item["date"], item["market_name_norm"], item["variety_norm"]))
    return rows


def row_key(row: dict) -> str:
    return f"{row['date'].isoformat()}|{row['market_name_norm']}|{row['variety_norm']}"


def combine_sources(zip_rows: list[dict], current_rows: list[dict]) -> list[dict]:
    combined: dict[str, dict] = {}

    for row in zip_rows:
        combined[row_key(row)] = row

    for row in current_rows:
        key = row_key(row)
        if key not in combined:
            combined[key] = row

    rows = sorted(combined.values(), key=lambda item: (item["date"], item["market_name_norm"], item["variety_norm"]))
    return rows


def latest_policy_for(target_date: date, policy_rows: list[dict]) -> dict:
    latest: dict | None = None
    for row in policy_rows:
        if row["date"] <= target_date:
            latest = row
        else:
            break
    return latest or {}


def fetch_nasa_power_weather(start_date: date, end_date: date) -> dict[date, dict]:
    query = {
        "parameters": ",".join(NASA_PARAMETERS.keys()),
        "community": "AG",
        "longitude": f"{COIMBATORE_LONGITUDE:.4f}",
        "latitude": f"{COIMBATORE_LATITUDE:.4f}",
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    url = f"{NASA_POWER_DAILY_POINT_URL}?{urllib.parse.urlencode(query)}"
    LOGGER.info("Fetching NASA POWER weather: %s", url)

    with urllib.request.urlopen(url, timeout=120) as response:
        payload = json.load(response)

    parameter_map = payload["properties"]["parameter"]
    fill_value = float(payload["header"].get("fill_value", -999.0))
    elevation_m = float(payload.get("geometry", {}).get("coordinates", [None, None, COIMBATORE_ELEVATION_M])[2])

    weather: dict[date, dict] = {}
    date_keys = sorted(next(iter(parameter_map.values())).keys())
    for date_key in date_keys:
        current_date = datetime.strptime(date_key, "%Y%m%d").date()
        row = {}
        for nasa_name, output_name in NASA_PARAMETERS.items():
            raw_value = parameter_map[nasa_name].get(date_key)
            if raw_value is None or raw_value == fill_value:
                value = None
            else:
                value = float(raw_value)
                if output_name == "wspd":
                    value = value * 3.6
                if output_name == "pres":
                    station_pressure_hpa = value * 10.0
                    value = station_pressure_hpa / ((1.0 - (elevation_m / 44330.0)) ** 5.255)
            row[output_name] = value
        weather[current_date] = row

    LOGGER.info(
        "Fetched %d NASA POWER weather rows covering %s to %s",
        len(weather),
        start_date,
        end_date,
    )
    return weather


def fill_weather_gaps(weather_rows: dict[date, dict], start_date: date, end_date: date) -> dict[date, dict]:
    from datetime import timedelta

    all_dates = []
    current = start_date
    while current <= end_date:
        all_dates.append(current)
        current += timedelta(days=1)

    columns = list(NASA_PARAMETERS.values())
    forward_values = {column: None for column in columns}
    completed: dict[date, dict] = {}

    for current_date in all_dates:
        source_row = weather_rows.get(current_date, {})
        row = {}
        for column in columns:
            value = source_row.get(column)
            if value is None or (isinstance(value, float) and math.isnan(value)):
                value = forward_values[column]
            else:
                forward_values[column] = value
            row[column] = value
        completed[current_date] = row

    backward_values = {column: None for column in columns}
    for current_date in reversed(all_dates):
        row = completed[current_date]
        for column in columns:
            value = row[column]
            if value is None or (isinstance(value, float) and math.isnan(value)):
                row[column] = backward_values[column]
            else:
                backward_values[column] = value
    return completed


def aggregate_daily(rows: list[dict]) -> dict[date, DailyAggregate]:
    grouped: dict[date, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)

    aggregates: dict[date, DailyAggregate] = {}
    for current_date, day_rows in grouped.items():
        modal_values = [row["modal_price"] for row in day_rows if row["modal_price"] is not None]
        min_values = [row["min_price"] for row in day_rows if row["min_price"] is not None]
        max_values = [row["max_price"] for row in day_rows if row["max_price"] is not None]
        markets = {row["market_name_norm"] for row in day_rows if row["market_name_norm"]}
        varieties = {row["variety_norm"] for row in day_rows if row["variety_norm"]}

        aggregates[current_date] = DailyAggregate(
            modal_price=sum(modal_values) / len(modal_values),
            min_price=sum(min_values) / len(min_values),
            max_price=sum(max_values) / len(max_values),
            markets_reporting=len(markets),
            varieties_reporting=len(varieties),
            rows_reporting=len(day_rows),
        )
    return aggregates


def write_weather_csv(weather_rows: dict[date, dict], out_path: Path) -> None:
    fieldnames = ["date"] + list(NASA_PARAMETERS.values())
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for current_date in sorted(weather_rows):
            writer.writerow({"date": current_date.isoformat(), **weather_rows[current_date]})


def write_market_panel(rows: list[dict], weather_rows: dict[date, dict], policy_rows: list[dict], out_path: Path) -> None:
    fieldnames = [
        "date",
        "market_id",
        "market_name",
        "crop",
        "variety",
        "min_price",
        "max_price",
        "modal_price",
        "tavg",
        "tmin",
        "tmax",
        "prcp",
        "wdir",
        "wspd",
        "pres",
        "msp_applicable",
        "msp_value_per_quintal",
        "govt_procurement_active",
        "pmfby_insurance_active",
        "state_scheme_active",
        "harvest_season_active",
        "price_impact_direction",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            weather = weather_rows.get(row["date"], {})
            policy = latest_policy_for(row["date"], policy_rows)
            writer.writerow(
                {
                    "date": row["date"].isoformat(),
                    "market_id": row["market_id"],
                    "market_name": row["market_name"],
                    "crop": row["crop"],
                    "variety": row["variety"],
                    "min_price": row["min_price"],
                    "max_price": row["max_price"],
                    "modal_price": row["modal_price"],
                    **weather,
                    "msp_applicable": policy.get("msp_applicable", ""),
                    "msp_value_per_quintal": policy.get("msp_value_per_quintal", ""),
                    "govt_procurement_active": policy.get("govt_procurement_active", ""),
                    "pmfby_insurance_active": policy.get("pmfby_insurance_active", ""),
                    "state_scheme_active": policy.get("state_scheme_active", ""),
                    "harvest_season_active": policy.get("harvest_season_active", ""),
                    "price_impact_direction": policy.get("price_impact_direction", ""),
                }
            )


def write_model_daily(daily: dict[date, DailyAggregate], weather_rows: dict[date, dict], policy_rows: list[dict], out_path: Path) -> None:
    fieldnames = [
        "date",
        "modal_price",
        "min_price",
        "max_price",
        "markets_reporting",
        "varieties_reporting",
        "rows_reporting",
        "tavg",
        "tmin",
        "tmax",
        "prcp",
        "wdir",
        "wspd",
        "pres",
        "msp_applicable",
        "msp_value_per_quintal",
        "govt_procurement_active",
        "pmfby_insurance_active",
        "state_scheme_active",
        "harvest_season_active",
        "price_impact_direction",
    ]
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for current_date in sorted(daily):
            agg = daily[current_date]
            weather = weather_rows.get(current_date, {})
            policy = latest_policy_for(current_date, policy_rows)
            writer.writerow(
                {
                    "date": current_date.isoformat(),
                    "modal_price": round(agg.modal_price, 6),
                    "min_price": round(agg.min_price, 6),
                    "max_price": round(agg.max_price, 6),
                    "markets_reporting": agg.markets_reporting,
                    "varieties_reporting": agg.varieties_reporting,
                    "rows_reporting": agg.rows_reporting,
                    **weather,
                    "msp_applicable": policy.get("msp_applicable", ""),
                    "msp_value_per_quintal": policy.get("msp_value_per_quintal", ""),
                    "govt_procurement_active": policy.get("govt_procurement_active", ""),
                    "pmfby_insurance_active": policy.get("pmfby_insurance_active", ""),
                    "state_scheme_active": policy.get("state_scheme_active", ""),
                    "harvest_season_active": policy.get("harvest_season_active", ""),
                    "price_impact_direction": policy.get("price_impact_direction", ""),
                }
            )


def summarize_dataset(csv_path: Path) -> dict:
    df = pd.read_csv(csv_path)
    dates = pd.to_datetime(df["date"], errors="coerce")
    key_columns = ["modal_price", "tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"] + POLICY_COLUMNS
    return {
        "path": str(csv_path),
        "date_start": dates.min().date().isoformat(),
        "date_end": dates.max().date().isoformat(),
        "rows": int(len(df)),
        "unique_weeks": int(dates.dt.to_period("W").nunique()),
        "missingness": {
            column: int(df[column].isna().sum())
            for column in key_columns
            if column in df.columns
        },
    }


def build_validation_report(zip_rows: list[dict], current_rows: list[dict], combined_rows: list[dict]) -> dict:
    zip_dates = sorted({row["date"] for row in zip_rows})
    current_dates = sorted({row["date"] for row in current_rows})
    combined_dates = sorted({row["date"] for row in combined_rows})

    v1_summary = summarize_dataset(MODEL_V1_PATH)
    v2_summary = summarize_dataset(MODEL_V2_PATH)
    v3_summary = summarize_dataset(MODEL_V3_PATH)

    comparison = {
        "zip_source": {
            "start": min(zip_dates).isoformat(),
            "end": max(zip_dates).isoformat(),
            "rows": len(zip_rows),
            "days": len(zip_dates),
        },
        "current_raw_source": {
            "start": min(current_dates).isoformat(),
            "end": max(current_dates).isoformat(),
            "rows": len(current_rows),
            "days": len(current_dates),
        },
        "combined_v3_source": {
            "start": min(combined_dates).isoformat(),
            "end": max(combined_dates).isoformat(),
            "rows": len(combined_rows),
            "days": len(combined_dates),
            "shared_normalized_rows_deduped": int(len(zip_rows) + len(current_rows) - len(combined_rows)),
        },
        "why_v3_is_better_or_not_better_than_v2": (
            "V3 has a much longer real maize price history and more weekly coverage than V2 because it unions "
            "the ZIP historical maize source with the newer raw maize source, using ZIP rows as preferred when "
            "normalized duplicates exist. However, V3 is not a clean drop-in replacement for V2 for modeling yet "
            "because the existing MSP/policy file only begins in 2023-03, so pre-2023 rows in V3 have missing "
            "policy fields."
        ),
        "msp_coverage_complete_v1": all(v1_summary["missingness"].get(column, 0) == 0 for column in POLICY_COLUMNS),
        "msp_coverage_complete_v2": all(v2_summary["missingness"].get(column, 0) == 0 for column in POLICY_COLUMNS),
        "msp_coverage_complete_v3": all(v3_summary["missingness"].get(column, 0) == 0 for column in POLICY_COLUMNS),
        "weather_coverage_complete_v1": all(v1_summary["missingness"].get(column, 0) == 0 for column in ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]),
        "weather_coverage_complete_v2": all(v2_summary["missingness"].get(column, 0) == 0 for column in ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]),
        "weather_coverage_complete_v3": all(v3_summary["missingness"].get(column, 0) == 0 for column in ["tavg", "tmin", "tmax", "prcp", "wdir", "wspd", "pres"]),
        "ready_to_replace_v2": False,
        "ready_to_replace_v2_reason": (
            "Not yet. V3 is the strongest real price/weather dataset, but it extends back before the available "
            "policy/MSP history. Without a deliberate policy-history decision, switching the backend directly to V3 "
            "would introduce incomplete policy coverage in the early period."
        ),
    }

    return {
        "weather_source": {
            "provider": "NASA POWER Daily API",
            "url": NASA_POWER_DAILY_POINT_URL,
            "community": "AG",
            "latitude": COIMBATORE_LATITUDE,
            "longitude": COIMBATORE_LONGITUDE,
            "elevation_m": COIMBATORE_ELEVATION_M,
            "parameters": list(NASA_PARAMETERS.keys()),
            "transformations": {
                "wspd": "WS10M converted from m/s to km/h",
                "pres": "PS converted from kPa surface pressure to approximate sea-level hPa using site elevation",
            },
        },
        "v1": v1_summary,
        "v2": v2_summary,
        "v3": v3_summary,
        "comparison": comparison,
    }


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    current_rows = load_current_maize_rows()
    market_id_lookup = build_market_id_lookup(current_rows)
    zip_rows = load_zip_maize_rows(market_id_lookup)
    policy_rows = load_policy_rows()
    combined_rows = combine_sources(zip_rows, current_rows)

    start_date = min(row["date"] for row in combined_rows)
    end_date = max(row["date"] for row in combined_rows)

    weather_rows = fetch_nasa_power_weather(start_date, end_date)
    weather_rows = fill_weather_gaps(weather_rows, start_date, end_date)
    daily = aggregate_daily(combined_rows)

    write_weather_csv(weather_rows, WEATHER_V3_PATH)
    write_market_panel(combined_rows, weather_rows, policy_rows, PANEL_V3_PATH)
    write_model_daily(daily, weather_rows, policy_rows, MODEL_V3_PATH)

    validation = build_validation_report(zip_rows, current_rows, combined_rows)
    VALIDATION_V3_PATH.write_text(json.dumps(validation, indent=2), encoding="utf-8")

    LOGGER.info("Wrote %s", WEATHER_V3_PATH)
    LOGGER.info("Wrote %s", PANEL_V3_PATH)
    LOGGER.info("Wrote %s", MODEL_V3_PATH)
    LOGGER.info("Wrote %s", VALIDATION_V3_PATH)
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
