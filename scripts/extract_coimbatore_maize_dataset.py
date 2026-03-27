from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path


ROOT = Path("/tmp/minor-project-crop-price-prediction/backend/data")
OUT_DIR = Path("/home/arnavbansal/Samaksh_m/extracted_data")

MAIZE_PATH = ROOT / "maize.csv"
WEATHER_PATH = ROOT / "formatted_weather.csv"
POLICY_PATH = ROOT / "coimbatore_crop_policy_2023_2026.csv"


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


def parse_float(value: str) -> float | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_maize_rows() -> list[dict]:
    rows: list[dict] = []
    with MAIZE_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row["district_name"].strip().lower() != "coimbatore":
                continue
            rows.append(
                {
                    "date": parse_date(row["t"]),
                    "market_id": row["market_id"].strip(),
                    "market_name": row["market_name"].strip(),
                    "crop": row["cmdty"].strip(),
                    "variety": row["variety"].strip(),
                    "min_price": parse_float(row["p_min"]),
                    "max_price": parse_float(row["p_max"]),
                    "modal_price": parse_float(row["p_modal"]),
                }
            )
    rows.sort(key=lambda item: (item["date"], item["market_id"], item["variety"]))
    return rows


def load_weather_rows() -> dict[date, dict]:
    weather: dict[date, dict] = {}
    with WEATHER_PATH.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            d = parse_date(row["Price Date"])
            weather[d] = {
                "tavg": parse_float(row.get("tavg", "")),
                "tmin": parse_float(row.get("tmin", "")),
                "tmax": parse_float(row.get("tmax", "")),
                "prcp": parse_float(row.get("prcp", "")),
                "wdir": parse_float(row.get("wdir", "")),
                "wspd": parse_float(row.get("wspd", "")),
                "pres": parse_float(row.get("pres", "")),
            }
    return weather


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


def aggregate_daily(rows: list[dict]) -> dict[date, DailyAggregate]:
    grouped: dict[date, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["date"]].append(row)

    aggregates: dict[date, DailyAggregate] = {}
    for d, day_rows in grouped.items():
        modal_values = [r["modal_price"] for r in day_rows if r["modal_price"] is not None]
        min_values = [r["min_price"] for r in day_rows if r["min_price"] is not None]
        max_values = [r["max_price"] for r in day_rows if r["max_price"] is not None]
        markets = {r["market_id"] for r in day_rows if r["market_id"]}
        varieties = {r["variety"] for r in day_rows if r["variety"]}
        aggregates[d] = DailyAggregate(
            modal_price=sum(modal_values) / len(modal_values),
            min_price=sum(min_values) / len(min_values),
            max_price=sum(max_values) / len(max_values),
            markets_reporting=len(markets),
            varieties_reporting=len(varieties),
            rows_reporting=len(day_rows),
        )
    return aggregates


def latest_policy_for(target_date: date, policy_rows: list[dict]) -> dict:
    latest: dict | None = None
    for row in policy_rows:
        if row["date"] <= target_date:
            latest = row
        else:
            break
    return latest or {}


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
        for d in sorted(daily):
            weather = weather_rows.get(d, {})
            policy = latest_policy_for(d, policy_rows)
            agg = daily[d]
            writer.writerow(
                {
                    "date": d.isoformat(),
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    maize_rows = load_maize_rows()
    weather_rows = load_weather_rows()
    policy_rows = load_policy_rows()

    weather_start = min(weather_rows)
    weather_end = max(weather_rows)
    overlap_rows = [row for row in maize_rows if weather_start <= row["date"] <= weather_end]
    daily = aggregate_daily(overlap_rows)

    panel_path = OUT_DIR / "coimbatore_maize_market_panel.csv"
    model_path = OUT_DIR / "coimbatore_maize_model_daily.csv"

    write_market_panel(overlap_rows, weather_rows, policy_rows, panel_path)
    write_model_daily(daily, weather_rows, policy_rows, model_path)

    unique_markets = len({row["market_id"] for row in overlap_rows})
    unique_varieties = len({row["variety"] for row in overlap_rows})
    print(f"weather_range={weather_start}..{weather_end}")
    print(f"maize_overlap_rows={len(overlap_rows)}")
    print(f"maize_overlap_days={len(daily)}")
    print(f"maize_overlap_markets={unique_markets}")
    print(f"maize_overlap_varieties={unique_varieties}")
    print(f"market_panel={panel_path}")
    print(f"model_daily={model_path}")


if __name__ == "__main__":
    main()
