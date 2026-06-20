from __future__ import annotations

"""RWA 不動產代幣化 PoC — Vercel Python Serverless 後端 (真功能 · 即時運算).

純 Python 移植自 RWA_不動產代幣化_POC/backend/app.py 與
RWA_Assignment2/POC_backend/app.py：所有 compute_* 公式照搬，移除 pandas/numpy，
資料硬編為 Python 常數 (免檔案路徑問題)，PDF 以 reportlab 內嵌粉圓字型輸出。

主標的：台北市信義計畫區「信義之星」(代幣 XYRE)
  估值 4.8 億、NOI 600 萬、現金殖利率 1.25%、48 萬代幣 @ NT$1,000、最低 1 萬、
  PoR 覆蓋率 100%、ROI = 配息 1.25% + 假設增值 3% = 4.25%。

合規 / PoC 免責：所有上鏈、Oracle、KYC、智能合約配息均為模擬示意，非真實上鏈，
不構成投資招攬或證券要約。本案標的約 4.8 億遠超台灣 STO 豁免門檻
(單一平台合計 ≤ 1 億、單檔 ≤ 3,000 萬免申報)，落地須走金融監理沙盒、
不動產投資信託 / 信託受益權架構、或限專業投資人私募；轉讓須白名單(KYC)、
不可自由流通 (對標 ERC-3643/1400)；VASP 須依洗錢防制法登記。
"""

import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response


# ---------------------------------------------------------------------------
# 合規 / PoC 免責
# ---------------------------------------------------------------------------
COMPLIANCE_DISCLAIMER = (
    "本系統為概念驗證 (PoC)：所有上鏈、Oracle 餵價、KYC、智能合約配息均為模擬示意，"
    "非真實上鏈，不構成投資招攬或證券要約。本案標的約 4.8 億遠超台灣 STO 豁免門檻 "
    "(單一平台合計 ≤ 1 億、單檔 ≤ 3,000 萬免申報)，落地須走金融監理沙盒、"
    "不動產投資信託 / 信託受益權架構、或限專業投資人私募；轉讓須白名單(KYC)、"
    "不可自由流通 (對標 ERC-3643/1400)；VASP 須依洗錢防制法登記。"
)


# ===========================================================================
# 硬編資料 (取代 CSV)：主標的 (信義之星) + 多標的池 (推薦用)
# ===========================================================================
# 主標的：信義之星 (對應 RWA_不動產代幣化_POC/backend/data/property.csv)
XINYI_ASSET: dict[str, Any] = {
    "asset_id": "XYRE-001",
    "asset_name": "信義之星",
    "asset_name_en": "Xinyi Star Residence",
    "asset_type": "real_estate",
    "location": "台北市信義計畫區",
    "area_ping": 80.0,
    "area_sqm": 264.5,
    "oracle_unit_price_per_ping": 6000000.0,
    "annual_gross_rent": 7200000.0,
    "annual_opex": 1200000.0,
    "occupancy_rate": 1.0,
    "custody_proof_units": 480000.0,
    "onchain_token_supply": 480000.0,
    "token_unit_price": 1000.0,
    "min_invest_units": 10,
    "token_symbol": "XYRE",
    "oracle_appreciation_rate": 0.03,
    "oracle_feed_time": "2026-06-16T09:00:00+08:00",
    "custodian_name": "信義不動產信託股份有限公司",
}

# 主標的投資人 (對應 investors.csv)
XINYI_INVESTORS: list[dict[str, Any]] = [
    {"investor_id": "INV-001", "name": "林承佑", "name_en": "Lin Cheng-Yu", "type": "retail",
     "kyc": "verified", "whitelisted": True, "frozen": False, "holding_units": 10},
    {"investor_id": "INV-002", "name": "陳曉君", "name_en": "Chen Hsiao-Chun", "type": "retail",
     "kyc": "verified", "whitelisted": True, "frozen": False, "holding_units": 50},
    {"investor_id": "INV-003", "name": "小資族 王小明", "name_en": "Wang Hsiao-Ming", "type": "retail",
     "kyc": "verified", "whitelisted": True, "frozen": False, "holding_units": 25},
    {"investor_id": "INV-004", "name": "宏遠家族辦公室", "name_en": "Hongyuan Family Office", "type": "professional",
     "kyc": "verified", "whitelisted": True, "frozen": False, "holding_units": 120000},
    {"investor_id": "INV-005", "name": "永豐人壽保險股份有限公司", "name_en": "SinoPac Life Insurance", "type": "professional",
     "kyc": "verified", "whitelisted": True, "frozen": False, "holding_units": 180000},
    {"investor_id": "INV-006", "name": "張庭瑋", "name_en": "Chang Ting-Wei", "type": "retail",
     "kyc": "pending", "whitelisted": False, "frozen": False, "holding_units": 0},
    {"investor_id": "INV-007", "name": "被凍結帳戶 李大同", "name_en": "Li Da-Tong (frozen)", "type": "retail",
     "kyc": "verified", "whitelisted": True, "frozen": True, "holding_units": 200},
]

# 多標的資產池 (對應 RWA_Assignment2/POC_backend/data/assets.csv) — 推薦 / 報告用。
# 主標的以 XYRE-001 對齊，數字與信義之星一致。
ASSET_POOL: list[dict[str, Any]] = [
    {
        "asset_id": "XYRE-001", "asset_name": "信義之星", "asset_name_en": "Xinyi Star Residence",
        "asset_type": "real_estate", "location": "台北市信義計畫區",
        "area_sqm": 264.5, "annual_rent": 7200000.0, "annual_opex": 1200000.0,
        "discount_rate": 0.01363, "comparable_unit_price": 1665000.0, "occupancy_rate": 1.0,
        "ltv": 0.50, "debtor_credit_score": 85, "liquidity_score": 80,
        "custody_proof_units": 480000.0, "onchain_token_supply": 480000.0,
        "token_unit_price": 1000.0, "min_invest_units": 10,
        "debtor_name": "信義不動產信託股份有限公司", "maturity_months": 0, "face_value": 0,
        "oracle_appreciation_rate": 0.03,
    },
    {
        "asset_id": "A-002", "asset_name": "台中七期商辦B座", "asset_name_en": "Taichung 7th Redevelopment Office B",
        "asset_type": "real_estate", "location": "台中市西屯區",
        "area_sqm": 6500.0, "annual_rent": 72000000.0, "annual_opex": 16500000.0,
        "discount_rate": 0.058, "comparable_unit_price": 420000.0, "occupancy_rate": 0.88,
        "ltv": 0.60, "debtor_credit_score": 76, "liquidity_score": 70,
        "custody_proof_units": 800000.0, "onchain_token_supply": 800000.0,
        "token_unit_price": 3300.0, "min_invest_units": 100,
        "debtor_name": "惠中資產管理股份有限公司", "maturity_months": 0, "face_value": 0,
        "oracle_appreciation_rate": 0.025,
    },
    {
        "asset_id": "A-003", "asset_name": "中小企業應收帳款池", "asset_name_en": "SME Accounts Receivable Pool",
        "asset_type": "receivable", "location": "台北市內湖區",
        "area_sqm": 0.0, "annual_rent": 0.0, "annual_opex": 0.0,
        "discount_rate": 0.075, "comparable_unit_price": 0.0, "occupancy_rate": 1.0,
        "ltv": 0.70, "debtor_credit_score": 68, "liquidity_score": 55,
        "custody_proof_units": 500000.0, "onchain_token_supply": 500000.0,
        "token_unit_price": 1000.0, "min_invest_units": 500,
        "debtor_name": "鴻儀電子股份有限公司", "maturity_months": 9, "face_value": 520000000.0,
        "oracle_appreciation_rate": 0.0,
    },
    {
        "asset_id": "A-004", "asset_name": "高雄亞灣物流倉", "asset_name_en": "Kaohsiung Asia Bay Logistics Warehouse",
        "asset_type": "real_estate", "location": "高雄市前鎮區",
        "area_sqm": 12000.0, "annual_rent": 54000000.0, "annual_opex": 12000000.0,
        "discount_rate": 0.065, "comparable_unit_price": 180000.0, "occupancy_rate": 0.92,
        "ltv": 0.50, "debtor_credit_score": 80, "liquidity_score": 62,
        "custody_proof_units": 650000.0, "onchain_token_supply": 650000.0,
        "token_unit_price": 3200.0, "min_invest_units": 100,
        "debtor_name": "亞灣物流股份有限公司", "maturity_months": 0, "face_value": 0,
        "oracle_appreciation_rate": 0.02,
    },
]


# ===========================================================================
# 工具函式 (純 Python，移除 numpy)
# ===========================================================================
def to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").replace("，", "").strip()
        if value == "":
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return round(value, digits)


def clean_json(value: Any) -> Any:
    """純 Python 序列化清洗 (移除 numpy 依賴)。"""
    if isinstance(value, dict):
        return {str(k): clean_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [clean_json(v) for v in value]
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def get_pool_row(asset_id: str) -> dict[str, Any]:
    for row in ASSET_POOL:
        if str(row["asset_id"]) == str(asset_id):
            return dict(row)
    raise HTTPException(status_code=404, detail=f"找不到資產 {asset_id}")


# ===========================================================================
# 信義之星估值 / PoR / 代幣化 / 分配 / ROI (照搬 property 後端公式)
# ===========================================================================
def compute_valuation(row: dict[str, Any]) -> dict[str, Any]:
    """Oracle 每坪單價 × 坪數 為市場可比估值；NOI 為淨營運租金；殖利率 NOI/估值 真算。"""
    area_ping = to_float(row.get("area_ping")) or 0.0
    area_sqm = to_float(row.get("area_sqm")) or 0.0
    unit_price = to_float(row.get("oracle_unit_price_per_ping")) or 0.0
    gross_rent = to_float(row.get("annual_gross_rent")) or 0.0
    opex = to_float(row.get("annual_opex")) or 0.0
    occupancy = to_float(row.get("occupancy_rate"))
    occupancy = 1.0 if occupancy is None else occupancy

    market_value = unit_price * area_ping
    noi = (gross_rent * occupancy) - opex
    fair_value = market_value
    cash_yield = (noi / fair_value) if fair_value > 0 else None

    return {
        "area_ping": round_or_none(area_ping, 1),
        "area_sqm": round_or_none(area_sqm, 1),
        "oracle_unit_price_per_ping": round_or_none(unit_price, 0),
        "market_value": round_or_none(market_value, 0),
        "annual_gross_rent": round_or_none(gross_rent, 0),
        "annual_opex": round_or_none(opex, 0),
        "noi": round_or_none(noi, 0),
        "occupancy_rate": round_or_none(occupancy, 4),
        "fair_value": round_or_none(fair_value, 0),
        "cash_yield_pct": round_or_none((cash_yield or 0) * 100, 4),
        "valuation_factors": [
            {"factor": "市場可比法 (Oracle 餵價)",
             "detail": f"每坪 {unit_price:,.0f} × {area_ping:,.0f} 坪 = NT$ {market_value:,.0f}",
             "value": round_or_none(market_value, 0)},
            {"factor": "淨營運收入 NOI",
             "detail": f"年毛租 {gross_rent:,.0f} × 出租率 {occupancy:.0%} − 管理稅費 {opex:,.0f} = NT$ {noi:,.0f}",
             "value": round_or_none(noi, 0)},
            {"factor": "現金殖利率 (NOI / 估值)",
             "detail": f"{noi:,.0f} / {fair_value:,.0f} = {(cash_yield or 0):.4%} (台灣住宅殖利率本就偏低，誠實揭露)",
             "value": round_or_none((cash_yield or 0) * 100, 4)},
        ],
    }


def compute_reserve(row: dict[str, Any]) -> dict[str, Any]:
    """Proof-of-Reserve：鏈上代幣供給 vs 鏈下託管 / 信託憑證。"""
    custody = to_float(row.get("custody_proof_units")) or 0.0
    onchain = to_float(row.get("onchain_token_supply")) or 0.0
    diff = onchain - custody
    over_issued = diff > 1e-9
    coverage = (custody / onchain) if onchain > 0 else None

    if over_issued:
        message = (
            f"偵測到超額發行：鏈上代幣供給 {onchain:,.0f} 枚 > 鏈下託管/信託憑證 {custody:,.0f} 單位，"
            f"超額 {diff:,.0f} 枚 (覆蓋率僅 {(coverage or 0):.1%})。發行上限應鎖定託管憑證。"
        )
    else:
        message = (
            f"勾稽通過：鏈上供給 {onchain:,.0f} 枚 ≤ 託管/信託憑證 {custody:,.0f} 單位，"
            f"無超額發行 (覆蓋率 {(coverage or 0):.1%})。"
        )
    recommended_cap = custody

    return {
        "custody_proof_units": round_or_none(custody, 0),
        "onchain_token_supply": round_or_none(onchain, 0),
        "diff": round_or_none(diff, 0),
        "over_issued": over_issued,
        "coverage_ratio": round_or_none(coverage, 4) if coverage is not None else None,
        "status": "mismatch" if over_issued else "match",
        "message": message,
        "recommended_supply_cap": round_or_none(recommended_cap, 0),
        "custodian_name": row.get("custodian_name"),
        "evidence": (
            f"託管證明 (Proof-of-Reserve)：{row.get('custodian_name', '託管機構')} 出具之不動產信託受益權憑證共 "
            f"{custody:,.0f} 單位，為 ERC-20 可鑄造上限的唯一依據 (1 憑證 = 1 代幣 = 1/{custody:,.0f} 持分)。"
        ),
    }


def compute_tokenization(row: dict[str, Any], fair_value: float, supply_cap: float) -> dict[str, Any]:
    """ERC-20 分割參數 (依估值與託管上限)。"""
    token_unit_price = to_float(row.get("token_unit_price"))
    min_units = int(to_float(row.get("min_invest_units")) or 10)
    symbol = str(row.get("token_symbol") or "XYRE")

    total_supply = int(supply_cap)
    nav_unit_price = round(fair_value / total_supply, 2) if total_supply > 0 else 0.0
    if not token_unit_price or token_unit_price <= 0:
        token_unit_price = nav_unit_price

    nominal_raise = total_supply * token_unit_price
    min_investment = min_units * token_unit_price

    seed = f"{row.get('asset_id')}|{total_supply}|{token_unit_price}"
    tx_hash = "0x" + format(abs(hash(seed)) % (16 ** 40), "040x")

    return {
        "token_symbol": symbol,
        "token_standard": "ERC-20 (分割所有權) + ERC-3643/1400 許可型轉讓限制",
        "total_supply": total_supply,
        "token_unit_price": round(token_unit_price, 2),
        "implied_nav_per_token": round_or_none(nav_unit_price, 2),
        "fraction_per_token": f"1/{total_supply:,}",
        "min_invest_units": min_units,
        "min_investment": round(min_investment, 0),
        "nominal_raise": round(nominal_raise, 0),
        "supply_cap_source": "鏈下託管 / 信託受益權憑證 (Proof-of-Reserve)",
        "mint_tx_hash": tx_hash,
        "mint_status": "simulated (示意非真實上鏈)",
        "transfer_restriction": "限白名單 (KYC) 持有人；凍結帳戶與未通過 KYC 不可受讓 (對標 ERC-3643)。",
    }


def eligible_holders(investors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        inv for inv in investors
        if inv["kyc"] == "verified" and inv["whitelisted"] and not inv["frozen"] and inv["holding_units"] > 0
    ]


def compute_distribution(net_rent: float, total_supply: int, token_unit_price: float,
                         investors: list[dict[str, Any]]) -> dict[str, Any]:
    """pull-based：可分配淨租金 → 每代幣配息 (= 12.5 = 600萬/48萬) → 各白名單投資人應領。"""
    holders = eligible_holders(investors)
    held_units = sum(inv["holding_units"] for inv in holders)
    per_token = (net_rent / total_supply) if total_supply > 0 else 0.0

    rows: list[dict[str, Any]] = []
    total_paid = 0.0
    for inv in investors:
        units = inv["holding_units"]
        eligible = inv["kyc"] == "verified" and inv["whitelisted"] and not inv["frozen"] and units > 0
        if not eligible:
            reason = []
            if inv["kyc"] != "verified":
                reason.append("KYC 未通過")
            if not inv["whitelisted"]:
                reason.append("未列白名單")
            if inv["frozen"]:
                reason.append("帳戶凍結")
            if units <= 0:
                reason.append("無持倉")
            rows.append({
                "investor_id": inv["investor_id"], "name": inv["name"], "type": inv["type"],
                "kyc": inv["kyc"], "whitelisted": inv["whitelisted"], "frozen": inv["frozen"],
                "holding_units": units, "share_pct": 0.0, "claimable": 0.0,
                "note": "不予分配：" + "、".join(reason) + " (對標 ERC-3643 轉讓/領取限制)。",
            })
            continue
        claimable = units * per_token
        total_paid += claimable
        rows.append({
            "investor_id": inv["investor_id"], "name": inv["name"], "type": inv["type"],
            "kyc": inv["kyc"], "whitelisted": inv["whitelisted"], "frozen": inv["frozen"],
            "holding_units": units,
            "share_pct": round_or_none(units / total_supply * 100, 4) if total_supply else 0.0,
            "claimable": round(claimable, 2),
            "note": "RentClaimed：智能合約 pull-based 依持倉比例領取。",
        })

    return {
        "net_rent_distributable": round(net_rent, 0),
        "held_units_eligible": held_units,
        "total_supply": total_supply,
        "yield_per_token": round(per_token, 4),
        "total_paid": round(total_paid, 2),
        "residual_unallocated": round(net_rent - total_paid, 2),
        "investors": rows,
    }


def compute_roi(row: dict[str, Any], annual_per_token_yield: float, token_unit_price: float,
                appreciation_rate: float, investors: list[dict[str, Any]]) -> dict[str, Any]:
    """每位投資人 ROI = 現金殖利率 (年配息/成本) + 假設年增值情境。"""
    cash_yield = (annual_per_token_yield / token_unit_price) if token_unit_price > 0 else 0.0
    total_return = cash_yield + appreciation_rate

    rows: list[dict[str, Any]] = []
    for inv in investors:
        units = inv["holding_units"]
        cost = units * token_unit_price
        annual_income = units * annual_per_token_yield if (
            inv["kyc"] == "verified" and inv["whitelisted"] and not inv["frozen"]
        ) else 0.0
        appreciation_gain = cost * appreciation_rate
        rows.append({
            "investor_id": inv["investor_id"], "name": inv["name"], "type": inv["type"],
            "holding_units": units,
            "cost_basis": round(cost, 0),
            "annual_rent_income": round(annual_income, 2),
            "cash_yield_pct": round_or_none((annual_income / cost * 100) if cost > 0 else 0.0, 4),
            "assumed_appreciation_gain": round(appreciation_gain, 0),
            "total_return_pct": round_or_none(((annual_income + appreciation_gain) / cost * 100) if cost > 0 else 0.0, 4),
        })

    return {
        "appreciation_rate": round_or_none(appreciation_rate, 4),
        "appreciation_pct": round_or_none(appreciation_rate * 100, 2),
        "cash_yield_pct": round_or_none(cash_yield * 100, 4),
        "total_return_pct": round_or_none(total_return * 100, 4),
        "annual_yield_per_token": round(annual_per_token_yield, 4),
        "token_unit_price": round(token_unit_price, 2),
        "note": "現金殖利率為 NOI/估值 真算；增值為情境假設 (非保證)。價值主張：分割可及性＋流動性＋透明＋自動分潤。",
        "investors": rows,
    }


def _xinyi_pipeline(row: dict[str, Any]) -> dict[str, Any]:
    val = compute_valuation(row)
    reserve = compute_reserve(row)
    cap = to_float(reserve["recommended_supply_cap"]) or 0.0
    tok = compute_tokenization(row, to_float(val["fair_value"]) or 0.0, cap)
    return {"valuation": val, "reserve": reserve, "tokenization": tok}


# ===========================================================================
# 多標的：估值 / 違約機率 / 評級 / 勾稽 / 代幣化 / 分配 / 推薦 (照搬 assets 後端公式)
# ===========================================================================
def pool_valuation(row: dict[str, Any]) -> dict[str, Any]:
    """DCF 收益法 + 市場可比 + 規則式因子校正 (多標的)。"""
    asset_type = str(row.get("asset_type") or "real_estate")
    annual_rent = to_float(row.get("annual_rent")) or 0.0
    annual_opex = to_float(row.get("annual_opex")) or 0.0
    discount_rate = to_float(row.get("discount_rate")) or 0.06
    comparable_unit_price = to_float(row.get("comparable_unit_price")) or 0.0
    area = to_float(row.get("area_sqm")) or 0.0
    occupancy = to_float(row.get("occupancy_rate"))
    occupancy = 1.0 if occupancy is None else occupancy
    face_value = to_float(row.get("face_value")) or 0.0
    maturity_months = to_float(row.get("maturity_months")) or 0.0

    factors: list[dict[str, Any]] = []

    if asset_type == "receivable":
        years = maturity_months / 12.0 if maturity_months else 0.0
        dcf_value = face_value / ((1 + discount_rate) ** years) if years > 0 else face_value
        market_value = 0.0
        weight_dcf, weight_market = 1.0, 0.0
        factors.append({"factor": "面值折現 (DCF)",
                        "detail": f"面值 {face_value:,.0f} / (1+{discount_rate:.3f})^{years:.2f} 年",
                        "contribution": round(dcf_value, 0)})
    else:
        noi = (annual_rent * occupancy) - annual_opex
        dcf_value = noi / discount_rate if discount_rate > 0 else 0.0
        market_value = comparable_unit_price * area
        weight_dcf, weight_market = 0.6, 0.4
        factors.append({"factor": "DCF 收益法",
                        "detail": f"NOI {noi:,.0f} (年租金 {annual_rent:,.0f} × 出租率 {occupancy:.0%} − 費用 {annual_opex:,.0f}) / 折現率 {discount_rate:.3f}",
                        "contribution": round(dcf_value, 0)})
        factors.append({"factor": "市場可比法",
                        "detail": f"可比單價 {comparable_unit_price:,.0f} × 面積 {area:,.0f} ㎡",
                        "contribution": round(market_value, 0)})

    base_value = dcf_value * weight_dcf + market_value * weight_market
    credit_score = to_float(row.get("debtor_credit_score")) or 70.0
    occ_adj = (occupancy - 0.9) * 0.5
    credit_adj = (credit_score - 75.0) / 100.0 * 0.4
    regression_multiplier = 1.0 + occ_adj + credit_adj
    fair_value = base_value * regression_multiplier

    factors.append({"factor": "因子校正係數(示意)",
                    "detail": f"出租率調整 {occ_adj:+.3f} + 信用調整 {credit_adj:+.3f} → ×{regression_multiplier:.3f}",
                    "contribution": round(fair_value - base_value, 0)})

    low = fair_value * 0.92
    high = fair_value * 1.08

    return {
        "asset_type": asset_type,
        "dcf_value": round_or_none(dcf_value, 0),
        "market_value": round_or_none(market_value, 0),
        "weighted_base": round_or_none(base_value, 0),
        "regression_multiplier": round_or_none(regression_multiplier, 4),
        "fair_value": round_or_none(fair_value, 0),
        "value_low": round_or_none(low, 0),
        "value_high": round_or_none(high, 0),
        "weights": {"dcf": weight_dcf, "market": weight_market},
        "factors": factors,
    }


def compute_default_probability(row: dict[str, Any]) -> float:
    """以 LTV / 出租率 / 信用分數 / 流動性 線性組合過 logistic 估違約機率。"""
    ltv = to_float(row.get("ltv")) or 0.6
    occupancy = to_float(row.get("occupancy_rate"))
    occupancy = 1.0 if occupancy is None else occupancy
    credit_score = to_float(row.get("debtor_credit_score")) or 70.0
    liquidity = to_float(row.get("liquidity_score")) or 60.0

    score = (
        ltv * 2.5
        + (1 - occupancy) * 1.5
        + (1 - credit_score / 100) * 2.0
        + (1 - liquidity / 100) * 1.0
    )
    pd_value = 1 / (1 + math.exp(-(score - 4.85) * 1.6))
    return round(pd_value, 4)


def compute_rating(row: dict[str, Any], pd_value: float) -> dict[str, Any]:
    """依 LTV / 出租率 / 信用 / 流動性 計算 0~100 綜合評分並映射 AAA–C。"""
    ltv = to_float(row.get("ltv")) or 0.6
    occupancy = to_float(row.get("occupancy_rate"))
    occupancy = 1.0 if occupancy is None else occupancy
    credit_score = to_float(row.get("debtor_credit_score")) or 70.0
    liquidity = to_float(row.get("liquidity_score")) or 60.0

    ltv_pts = max(0.0, (1 - ltv)) * 100 * 0.30
    occ_pts = occupancy * 100 * 0.25
    credit_pts = credit_score * 0.30
    liq_pts = liquidity * 0.15
    composite = ltv_pts + occ_pts + credit_pts + liq_pts

    if composite >= 90:
        grade = "AAA"
    elif composite >= 82:
        grade = "AA"
    elif composite >= 74:
        grade = "A"
    elif composite >= 65:
        grade = "BBB"
    elif composite >= 55:
        grade = "BB"
    elif composite >= 45:
        grade = "B"
    else:
        grade = "C"

    rating_factors = [
        {"factor": "LTV (貸款成數)", "input": f"{ltv:.0%}", "weight": "30%", "points": round(ltv_pts, 1)},
        {"factor": "出租率 / 收回率", "input": f"{occupancy:.0%}", "weight": "25%", "points": round(occ_pts, 1)},
        {"factor": "債務人信用分數", "input": f"{credit_score:.0f}", "weight": "30%", "points": round(credit_pts, 1)},
        {"factor": "流動性分數", "input": f"{liquidity:.0f}", "weight": "15%", "points": round(liq_pts, 1)},
    ]
    return {"grade": grade, "composite_score": round(composite, 1),
            "default_probability": pd_value, "rating_factors": rating_factors}


def compute_reconciliation(row: dict[str, Any]) -> dict[str, Any]:
    custody = to_float(row.get("custody_proof_units")) or 0.0
    onchain = to_float(row.get("onchain_token_supply")) or 0.0
    diff = onchain - custody
    over_issued = diff > 0
    coverage = (custody / onchain) if onchain > 0 else None

    status = "mismatch" if over_issued else "match"
    severity = "high" if over_issued else "ok"
    if over_issued:
        message = (f"偵測到超額發行：鏈上代幣供給 {onchain:,.0f} 枚 > 鏈下託管憑證 {custody:,.0f} 枚，"
                   f"超額 {diff:,.0f} 枚 (覆蓋率僅 {coverage:.1%})。")
        recommended_cap = custody
        evidence = (f"託管證明 (Proof-of-Reserve)：{row.get('debtor_name', '託管機構')} 出具之合格不動產/應收憑證共 "
                    f"{custody:,.0f} 單位，為可發行上限的唯一依據。")
    else:
        message = f"勾稽通過：鏈上供給 {onchain:,.0f} 枚 ≤ 託管憑證 {custody:,.0f} 枚，無超額發行。"
        recommended_cap = onchain
        evidence = f"託管證明顯示 {custody:,.0f} 單位可完整覆蓋鏈上流通量。"

    return {
        "custody_proof_units": round_or_none(custody, 0),
        "onchain_token_supply": round_or_none(onchain, 0),
        "diff": round_or_none(diff, 0),
        "over_issued": over_issued,
        "coverage_ratio": round_or_none(coverage, 4) if coverage is not None else None,
        "status": status, "severity": severity, "message": message, "evidence": evidence,
        "recommended_supply_cap": round_or_none(recommended_cap, 0),
    }


def pool_tokenization(row: dict[str, Any], fair_value: float, supply_cap: float) -> dict[str, Any]:
    token_unit_price = to_float(row.get("token_unit_price"))
    min_units = int(to_float(row.get("min_invest_units")) or 100)

    if not token_unit_price or token_unit_price <= 0:
        token_unit_price = round(fair_value / supply_cap, 2) if supply_cap > 0 else 0.0

    total_supply = int(supply_cap)
    raised = total_supply * token_unit_price
    min_investment = min_units * token_unit_price

    seed = f"{row.get('asset_id')}|{total_supply}|{token_unit_price}"
    tx_hash = "0x" + format(abs(hash(seed)) % (16 ** 40), "040x")

    return {
        "token_standard": "ERC-3643/1400 (許可型證券代幣)",
        "total_supply": total_supply,
        "token_unit_price": round(token_unit_price, 2),
        "min_invest_units": min_units,
        "min_investment": round(min_investment, 0),
        "nominal_raise": round(raised, 0),
        "implied_nav_per_token": round_or_none(fair_value / total_supply, 2) if total_supply else None,
        "supply_cap_source": "鏈下託管憑證 (Proof-of-Reserve)",
        "mint_tx_hash": tx_hash,
        "mint_status": "simulated (示意非真實上鏈)",
    }


def pool_distribution(row: dict[str, Any], total_supply: int, token_unit_price: float) -> dict[str, Any]:
    asset_type = str(row.get("asset_type") or "real_estate")
    if asset_type == "receivable":
        face_value = to_float(row.get("face_value")) or 0.0
        discount_rate = to_float(row.get("discount_rate")) or 0.07
        maturity_months = to_float(row.get("maturity_months")) or 9.0
        distributable = face_value * discount_rate * (maturity_months / 12.0)
    else:
        annual_rent = to_float(row.get("annual_rent")) or 0.0
        annual_opex = to_float(row.get("annual_opex")) or 0.0
        occupancy = to_float(row.get("occupancy_rate"))
        occupancy = 1.0 if occupancy is None else occupancy
        distributable = (annual_rent * occupancy) - annual_opex

    per_token = distributable / total_supply if total_supply > 0 else 0.0
    return {
        "distributable_income": round(distributable, 0),
        "yield_per_token": round(per_token, 4),
        "annual_yield_pct": round_or_none(per_token / token_unit_price * 100, 2) if token_unit_price else None,
    }


def _asset_metrics(row: dict[str, Any]) -> dict[str, Any]:
    """對單一資產跑完整估值 / 評級 / 勾稽 / 代幣化 / 收益管線 (多標的)。"""
    val = pool_valuation(row)
    fv = to_float(val["fair_value"]) or 0.0
    pd_value = compute_default_probability(row)
    rating = compute_rating(row, pd_value)
    recon = compute_reconciliation(row)
    cap = to_float(recon["recommended_supply_cap"]) or 0.0
    tok = pool_tokenization(row, fv, cap)
    dist = pool_distribution(row, tok["total_supply"], tok["token_unit_price"])
    return {"valuation": val, "fair_value": fv, "pd": pd_value, "rating": rating,
            "reconciliation": recon, "tokenization": tok, "distribution": dist}


PROFILE_WEIGHTS: dict[str, dict[str, Any]] = {
    "保守": {"quality": 0.40, "safety": 0.25, "yield": 0.10, "liq": 0.25, "label": "保守型", "desc": "重視本金安全與流動性"},
    "穩健": {"quality": 0.30, "safety": 0.15, "yield": 0.30, "liq": 0.25, "label": "穩健型", "desc": "風險與報酬平衡"},
    "積極": {"quality": 0.15, "safety": 0.05, "yield": 0.55, "liq": 0.25, "label": "積極型", "desc": "追求較高報酬，可承受較高風險"},
}
GRADE_RANK = {"AAA": 7, "AA": 6, "A": 5, "BBB": 4, "BB": 3, "B": 2, "C": 1}


def compute_recommendation(profile: str, budget: float | None = None) -> dict[str, Any]:
    """依投資人風險屬性，對所有資產計算適配分數並排序 (真實運算)。"""
    w = PROFILE_WEIGHTS.get(profile) or PROFILE_WEIGHTS["穩健"]
    items: list[dict[str, Any]] = []
    for row in ASSET_POOL:
        m = _asset_metrics(row)
        rating, tok, dist = m["rating"], m["tokenization"], m["distribution"]
        yld = to_float(dist["annual_yield_pct"]) or 0.0
        min_inv = to_float(tok["min_investment"]) or 0.0
        liq = to_float(row.get("liquidity_score")) or 50.0
        quality = to_float(rating["composite_score"]) or 0.0
        safety = max(0.0, 1 - m["pd"]) * 100
        yield_score = min(yld / 6.0 * 100, 100.0)
        fit = w["quality"] * quality + w["safety"] * safety + w["yield"] * yield_score + w["liq"] * liq
        affordable = budget is None or min_inv <= budget
        notes: list[str] = []
        if profile == "保守" and GRADE_RANK.get(rating["grade"], 0) < 4:
            notes.append("評級低於投資級，與保守型風險屬性不符")
        if profile == "積極" and yld < 3:
            notes.append("配息偏低，資本利得空間有限")
        if budget is not None and not affordable:
            notes.append(f"最低投資 NT$ {min_inv:,.0f} 超出預算")
        items.append({
            "asset_id": row.get("asset_id"), "asset_name": row.get("asset_name"),
            "asset_type": row.get("asset_type"), "grade": rating["grade"],
            "pd_pct": round(m["pd"] * 100, 2), "annual_yield_pct": round(yld, 2),
            "min_investment": round(min_inv, 0), "liquidity_score": round(liq, 0),
            "fair_value": round(m["fair_value"], 0), "fit_score": round(fit, 1),
            "affordable": affordable,
            "rationale": f"{w['label']}加權 → 評級 {rating['grade']}、安全 {safety:.0f}、配息 {yld:.1f}%、流動性 {liq:.0f}",
            "notes": notes,
        })
    items.sort(key=lambda x: (x["affordable"], x["fit_score"]), reverse=True)
    return {"profile": profile, "profile_label": w["label"], "profile_desc": w["desc"],
            "budget": round_or_none(budget, 0),
            "weights": {k: w[k] for k in ("quality", "safety", "yield", "liq")},
            "ranked": items, "top_pick": items[0] if items else None}


# ===========================================================================
# 一鍵報告 HTML / PDF (內嵌粉圓字型) — 多標的
# ===========================================================================
def build_report_html(asset_id: str) -> str:
    row = get_pool_row(asset_id)
    m = _asset_metrics(row)
    v, r, rc, tk, d = m["valuation"], m["rating"], m["reconciliation"], m["tokenization"], m["distribution"]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    def trows(pairs: list[tuple[str, Any]]) -> str:
        return "".join(
            f"<tr><th style='text-align:left;background:#EEF1F6;color:#1A2B4C;padding:6px 10px;border:1px solid #D3D1C7;width:40%'>{k}</th>"
            f"<td style='padding:6px 10px;border:1px solid #D3D1C7'>{val}</td></tr>" for k, val in pairs)

    return (
        "<!doctype html><html lang='zh-Hant'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>RWA 鏈通 估值風險報告 {asset_id}</title><style>"
        "body{font-family:-apple-system,'PingFang TC','Microsoft JhengHei',sans-serif;color:#222;max-width:820px;margin:24px auto;padding:0 18px;line-height:1.6}"
        "h1{color:#1A2B4C;margin:0 0 2px}h2{color:#0F6E56;font-size:16px;margin:20px 0 6px}.sub{color:#5F5E5A;font-size:13px}"
        "table{border-collapse:collapse;width:100%;font-size:14px}"
        ".disc{margin-top:18px;font-size:12px;color:#8A5A00;background:#FFF7E6;border-left:4px solid #E0A100;padding:10px 12px}"
        ".btn{display:inline-block;margin:10px 0;padding:8px 14px;background:#1A2B4C;color:#fff;border-radius:8px;text-decoration:none}"
        "@media print{.noprint{display:none}}</style></head><body>"
        "<h1>RWA 鏈通 — 資產估值與風險報告</h1>"
        f"<div class='sub'>Valuation &amp; Risk Report · {row.get('asset_name')} ({asset_id}) · 產生時間 {ts}</div>"
        "<a class='btn noprint' href='javascript:window.print()'>列印 / 另存 PDF</a>"
        "<h2>一、資產基本資料</h2><table>"
        + trows([("資產名稱", row.get("asset_name") or "-"), ("資產類型", row.get("asset_type") or "-"),
                 ("座落 / 發行方", f"{row.get('location') or '-'} / {row.get('debtor_name') or '-'}")]) + "</table>"
        "<h2>二、AI 三法估值</h2><table>"
        + trows([("DCF 收益法", f"NT$ {v['dcf_value']:,.0f}"), ("市場可比法", f"NT$ {v['market_value']:,.0f}"),
                 ("加權基準 × 因子校正", f"NT$ {v['weighted_base']:,.0f} × {v['regression_multiplier']}"),
                 ("公允價值 (區間)", f"NT$ {m['fair_value']:,.0f}　({v['value_low']:,.0f} ~ {v['value_high']:,.0f})")]) + "</table>"
        "<h2>三、風險評級</h2><table>"
        + trows([("信用評級", r["grade"]), ("綜合評分", r["composite_score"]), ("違約機率 PD", f"{m['pd']*100:.2f}%")]) + "</table>"
        f"<h2>四、Proof-of-Reserve 勾稽</h2><p>{rc['message']}</p>"
        "<h2>五、代幣化與收益</h2><table>"
        + trows([("代幣標準 / 總量", f"{tk['token_standard']} / {tk['total_supply']:,} 枚"),
                 ("單位價格 (NAV)", f"NT$ {tk['token_unit_price']:,.0f}"),
                 ("名目募資 / 最低投資", f"NT$ {tk['nominal_raise']:,.0f} / NT$ {tk['min_investment']:,.0f}"),
                 ("年化配息率", f"{d['annual_yield_pct']}%")]) + "</table>"
        "<div class='disc'>※ 本報告為概念驗證 (PoC) 之程式即時計算結果，輸入為模擬資料；區塊鏈/Oracle/KYC 為模擬示意，"
        "非真實上鏈。不構成投資建議或證券要約。RWA 具證券性質，台灣 STO 限專業投資人。</div></body></html>"
    )


_CJK_FONT: str | None = None


def _register_cjk_font() -> str:
    """登錄內嵌的粉圓 (jf-openhuninn) 繁中 TrueType 字型；找不到才退回內建 CID。"""
    global _CJK_FONT
    if _CJK_FONT:
        return _CJK_FONT
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    font_path = Path(__file__).parent / "fonts" / "jf-openhuninn.ttf"
    try:
        if font_path.exists():
            pdfmetrics.registerFont(TTFont("RWACJK", str(font_path)))
            _CJK_FONT = "RWACJK"
            return _CJK_FONT
    except Exception:
        pass
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _CJK_FONT = "STSong-Light"
    return _CJK_FONT


def build_report_pdf(asset_id: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    FONT = _register_cjk_font()
    row = get_pool_row(asset_id)
    m = _asset_metrics(row)
    v, r, rc, tk, d = m["valuation"], m["rating"], m["reconciliation"], m["tokenization"], m["distribution"]
    NAVY = colors.HexColor("#1A2B4C")
    TEAL = colors.HexColor("#0F6E56")
    GREYL = colors.HexColor("#EEF1F6")
    GRID = colors.HexColor("#D3D1C7")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm, title="RWA 鏈通 資產估值與風險報告")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontName=FONT, fontSize=18, textColor=NAVY, spaceAfter=2)
    sub = ParagraphStyle("sub", fontName=FONT, fontSize=10, textColor=colors.HexColor("#5F5E5A"), spaceAfter=10)
    h2 = ParagraphStyle("h2", fontName=FONT, fontSize=12.5, textColor=TEAL, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", fontName=FONT, fontSize=10, leading=15)
    disc = ParagraphStyle("disc", fontName=FONT, fontSize=8.5, leading=12, textColor=colors.HexColor("#8A5A00"))

    def tbl(data: list[list[str]], w0: float = 55) -> "Table":
        t = Table(data, colWidths=[w0 * mm, (174 - w0) * mm])
        t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (0, -1), NAVY), ("BACKGROUND", (0, 0), (0, -1), GREYL),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4), ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, GRID)]))
        return t

    el = [
        Paragraph("RWA 鏈通 — 資產估值與風險報告", h1),
        Paragraph(f"Valuation &amp; Risk Report · {row.get('asset_name')} ({asset_id}) · 產生時間 {datetime.now():%Y-%m-%d %H:%M}", sub),
        Paragraph("一、資產基本資料", h2),
        tbl([["資產名稱", str(row.get("asset_name") or "-")], ["資產類型", str(row.get("asset_type") or "-")],
             ["座落 / 發行方", f"{row.get('location') or '-'} / {row.get('debtor_name') or '-'}"]], 40),
        Paragraph("二、AI 三法估值", h2),
        tbl([["DCF 收益法", f"NT$ {v['dcf_value']:,.0f}"], ["市場可比法", f"NT$ {v['market_value']:,.0f}"],
             ["加權基準 × 因子校正", f"NT$ {v['weighted_base']:,.0f} × {v['regression_multiplier']}"],
             ["公允價值 (區間)", f"NT$ {m['fair_value']:,.0f}  ({v['value_low']:,.0f} ~ {v['value_high']:,.0f})"]]),
        Paragraph("三、風險評級", h2),
        tbl([["信用評級", str(r["grade"])], ["綜合評分", str(r["composite_score"])], ["違約機率 PD", f"{m['pd']*100:.2f}%"]]),
        Paragraph("四、Proof-of-Reserve 勾稽", h2), Paragraph(rc["message"], body),
        Paragraph("五、代幣化與收益", h2),
        tbl([["代幣標準 / 總量", f"{tk['token_standard']} / {tk['total_supply']:,} 枚"],
             ["單位價格 (NAV)", f"NT$ {tk['token_unit_price']:,.0f}"],
             ["名目募資 / 最低投資", f"NT$ {tk['nominal_raise']:,.0f} / NT$ {tk['min_investment']:,.0f}"],
             ["年化配息率", f"{d['annual_yield_pct']}%"]]),
        Spacer(1, 10),
        Paragraph("※ 本報告為概念驗證 (PoC) 之程式即時計算結果，輸入為模擬資料；區塊鏈/Oracle/KYC 為模擬示意，非真實上鏈。不構成投資建議或證券要約。RWA 具證券性質，台灣 STO 限專業投資人。", disc),
    ]
    doc.build(el)
    return buf.getvalue()


# ===========================================================================
# FastAPI app — 服務全站 (/、/app、/api/*)；Vercel ASGI 以 `app` 變數偵測。
# Vercel 將整個專案視為 Python 應用、把所有路由導到本函式，故由 FastAPI
# 統一服務靜態頁與 API，避免根路徑 `/` 的靜態解析邊界問題。
# ===========================================================================
app = FastAPI(title="RWA 不動產代幣化 PoC — Vercel Serverless (真功能)")

_STATIC_DIR = Path(__file__).resolve().parent / "static"


def _load_static(name: str) -> str:
    """讀取與函式同捆的靜態 HTML (api/static/，同 fonts/ 一併打包)。"""
    try:
        return (_STATIC_DIR / name).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"找不到頁面 {name}")


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    """互動原型 (五頁式 PoC)。"""
    return HTMLResponse(_load_static("index.html"))


@app.get("/app", response_class=HTMLResponse)
def app_ui() -> HTMLResponse:
    """呼叫即時 API 的護眼操作介面。"""
    return HTMLResponse(_load_static("app.html"))


@app.get("/console", response_class=HTMLResponse)
def chain_console() -> HTMLResponse:
    """RWA 鏈通 · 操作介面（離線版，內嵌運算快照，免後端）。"""
    return HTMLResponse(_load_static("console.html"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True}


@app.get("/api/asset")
def asset() -> dict[str, Any]:
    """標的與 Oracle 餵入之房價 / 租金 / 估值 (信義之星)。"""
    row = XINYI_ASSET
    val = compute_valuation(row)
    return clean_json({
        "asset_id": row.get("asset_id"),
        "asset_name": row.get("asset_name"),
        "asset_name_en": row.get("asset_name_en"),
        "asset_type": row.get("asset_type"),
        "location": row.get("location"),
        "token_symbol": row.get("token_symbol"),
        "oracle": {
            "feed_time": row.get("oracle_feed_time"),
            "unit_price_per_ping": val["oracle_unit_price_per_ping"],
            "annual_gross_rent": val["annual_gross_rent"],
            "appreciation_rate_assumption": round_or_none(to_float(row.get("oracle_appreciation_rate")), 4),
            "source": "Oracle 餵入房價指數與租金行情 (模擬示意)",
        },
        "valuation": val,
        "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        "agent_trace": [
            {"agent": "Oracle Agent", "status": "done",
             "detail": f"餵入每坪 {val['oracle_unit_price_per_ping']:,.0f} 元、年毛租 {val['annual_gross_rent']:,.0f} 元。"},
            {"agent": "Valuation Agent", "status": "done",
             "detail": f"公允估值 NT$ {val['fair_value']:,.0f}，現金殖利率 {val['cash_yield_pct']}%。"},
        ],
    })


@app.post("/api/tokenize")
def tokenize(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """ERC-20 分割參數 + proof-of-reserve 勾稽 (信義之星)。"""
    row = XINYI_ASSET
    pipe = _xinyi_pipeline(row)
    val, reserve, tok = pipe["valuation"], pipe["reserve"], pipe["tokenization"]
    return clean_json({
        "asset_id": row.get("asset_id"),
        "asset_name": row.get("asset_name"),
        "fair_value": val["fair_value"],
        "proof_of_reserve": reserve,
        "tokenization": tok,
        "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        "agent_trace": [
            {"agent": "Proof-of-Reserve Guardrail",
             "status": "review" if reserve["over_issued"] else "done",
             "detail": reserve["message"]},
            {"agent": "Tokenization Agent", "status": "done",
             "detail": f"ERC-20 發行 {tok['total_supply']:,} 枚 @ NT$ {tok['token_unit_price']:,.0f}，"
                       f"最低投資 {tok['min_invest_units']} 枚 = NT$ {tok['min_investment']:,.0f}。"},
            {"agent": "Mint Simulator", "status": "done",
             "detail": f"模擬 Minted 事件，交易雜湊 {tok['mint_tx_hash'][:18]}…"},
        ],
    })


@app.post("/api/distribute-rent")
def distribute_rent(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """依持倉 pull-based 分配淨租金。payload 可帶 net_rent、period。"""
    row = XINYI_ASSET
    pipe = _xinyi_pipeline(row)
    val, tok = pipe["valuation"], pipe["tokenization"]

    investors = [dict(i) for i in XINYI_INVESTORS]
    net_rent = to_float(payload.get("net_rent"))
    if net_rent is None:
        net_rent = to_float(val["noi"]) or 0.0
    period = str(payload.get("period") or "年度 (Annual)")

    dist = compute_distribution(net_rent, tok["total_supply"], tok["token_unit_price"], investors)
    per_token_on_total = (net_rent / tok["total_supply"]) if tok["total_supply"] else 0.0
    paid = [d for d in dist["investors"] if d["claimable"] > 0]

    return clean_json({
        "asset_id": row.get("asset_id"),
        "asset_name": row.get("asset_name"),
        "period": period,
        "net_rent_distributable": dist["net_rent_distributable"],
        "yield_per_token_circulating": dist["yield_per_token"],
        "yield_per_token_on_total_supply": round_or_none(per_token_on_total, 4),
        "token_unit_price": tok["token_unit_price"],
        "distribution": dist,
        "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        "agent_trace": [
            {"agent": "Smart Contract Distributor", "status": "done",
             "detail": f"RentDeposited：本期淨租金 NT$ {dist['net_rent_distributable']:,.0f}，"
                       f"每流通代幣可領 NT$ {dist['yield_per_token']:.4f}。"},
            {"agent": "Whitelist / KYC Gate", "status": "done",
             "detail": f"{len(paid)} 位白名單投資人可 RentClaimed，未通過/凍結者依 ERC-3643 規則排除。"},
            {"agent": "Pull Distribution Agent", "status": "done",
             "detail": f"已分配 NT$ {dist['total_paid']:,.0f}，殘額 NT$ {dist['residual_unallocated']:,.0f} (未售代幣不參與)。"},
        ],
    })


@app.post("/api/roi")
def roi(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """ROI = 現金殖利率 (NOI/估值 真算) + 假設增值情境；可帶 appreciation。"""
    row = XINYI_ASSET
    pipe = _xinyi_pipeline(row)
    val, tok = pipe["valuation"], pipe["tokenization"]
    investors = [dict(i) for i in XINYI_INVESTORS]

    noi = to_float(val["noi"]) or 0.0
    total_supply = tok["total_supply"]
    annual_per_token = (noi / total_supply) if total_supply > 0 else 0.0

    appreciation = to_float(payload.get("appreciation"))
    if appreciation is None:
        appreciation = to_float(row.get("oracle_appreciation_rate")) or 0.03

    result = compute_roi(row, annual_per_token, tok["token_unit_price"], appreciation, investors)
    return clean_json({
        "asset_id": row.get("asset_id"),
        "asset_name": row.get("asset_name"),
        "roi": result,
        "compliance_disclaimer": COMPLIANCE_DISCLAIMER,
        "agent_trace": [
            {"agent": "Yield Agent", "status": "done",
             "detail": f"每代幣年配息 NT$ {annual_per_token:.4f}，現金殖利率 {result['cash_yield_pct']}%。"},
            {"agent": "Appreciation Scenario Agent", "status": "done",
             "detail": f"套用假設年增值 {result['appreciation_pct']}% (情境假設，非保證)。"},
            {"agent": "ROI Agent", "status": "done",
             "detail": f"示意總報酬約 {result['total_return_pct']}% (配息 {result['cash_yield_pct']}% + 增值 {result['appreciation_pct']}%)。"},
        ],
    })


@app.post("/api/recommend")
def recommend(payload: dict[str, Any] = Body(default={})) -> dict[str, Any]:
    """投資人適配推薦：依風險屬性(保守/穩健/積極)加權排序資產。"""
    profile = str(payload.get("profile") or "穩健")
    budget = to_float(payload.get("budget"))
    rec = compute_recommendation(profile, budget)
    top = rec["top_pick"]
    rec["compliance_disclaimer"] = COMPLIANCE_DISCLAIMER
    rec["agent_trace"] = [
        {"agent": "Investor Profile Agent", "status": "done",
         "detail": f"風險屬性：{rec['profile_label']}（{rec['profile_desc']}）"
                   + (f"；預算 NT$ {budget:,.0f}" if budget else "")},
        {"agent": "Asset Scoring Agent", "status": "done",
         "detail": f"對 {len(rec['ranked'])} 檔資產以 評級/安全/配息/流動性 加權計算適配分數。"},
        {"agent": "Recommendation Agent", "status": "done",
         "detail": (f"首選：{top['asset_name']}（適配分數 {top['fit_score']}）。" if top else "查無符合資產。")},
    ]
    return clean_json(rec)


@app.get("/api/report/{asset_id}")
def report(asset_id: str, format: str = "pdf") -> Response:
    """一鍵估值/風險報告：format=pdf(下載) / html(瀏覽) / json(資料)；預設 pdf。"""
    get_pool_row(asset_id)  # 觸發 404 (資產不存在)
    if format == "json":
        data = _asset_metrics(get_pool_row(asset_id))
        data["compliance_disclaimer"] = COMPLIANCE_DISCLAIMER
        return Response(content=json.dumps(clean_json(data), ensure_ascii=False),
                        media_type="application/json; charset=utf-8")
    if format == "html":
        return Response(content=build_report_html(asset_id), media_type="text/html; charset=utf-8")
    try:
        pdf = build_report_pdf(asset_id)
    except Exception:  # reportlab 異常時退回 HTML，確保 demo 不中斷
        return Response(content=build_report_html(asset_id), media_type="text/html; charset=utf-8")
    from urllib.parse import quote
    fname = quote(f"RWA鏈通_{asset_id}_估值風險報告.pdf")
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{fname}"})
