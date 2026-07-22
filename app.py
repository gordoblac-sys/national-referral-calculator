from __future__ import annotations

import csv
import io
import math
import re
from dataclasses import dataclass
from typing import Dict, List

import streamlit as st


# ============================================================
# NATIONAL REFERRAL CALCULATOR
# Logic reconstructed from:
# EHP Referral Calculator - New ADT Plans (1.12.26)
# ============================================================

st.set_page_config(
    page_title="National Referral Calculator",
    page_icon="🧮",
    layout="wide",
    initial_sidebar_state="expanded",
)


# -----------------------------
# Configuration and source data
# -----------------------------

STARTING_RESIDENTIAL_COMMISSION = 650.0
COMMERCIAL_PAR_COMMISSION = 400.0
MAX_COMMISSION_POINTS = 650.0

NAP_MONTHLY_FEE = 7.0
NAP_ADDITIONAL_PACKAGE_POINTS = 60.0
MAX_MONTHLY_FEE = 10.0
MAX_ADDITIONAL_COMMISSION_POINTS = 75.0
INSTALLATION_OPTION_FEE = 199.0
INSTALLATION_ADDITIONAL_COMMISSION_POINTS = 50.0
VRC_REWARD_AMOUNT = 100.0
VRC_COMMISSION_POINTS = -50.0

POSITIVE_MMR_POINT_RATE = 15.0
NEGATIVE_MMR_POINT_RATE = 35.0


@dataclass(frozen=True)
class EquipmentItem:
    name: str
    points: int
    category: str
    maximum: int = 20


@dataclass(frozen=True)
class Package:
    name: str
    account_type: str
    package_points: int
    standard_mmr: float
    allowed_mmr: tuple[float, ...]
    included_equipment: Dict[str, int]
    nap_included: bool = False
    activation_minimum: float | None = None
    activation_par: float | None = None
    activation_maximum: float | None = None


EQUIPMENT: Dict[str, EquipmentItem] = {
    # Security & Life Safety
    '7" Panel Upgrade': EquipmentItem('7" Panel Upgrade', 40, "Security & Life Safety", 1),
    "Contacts": EquipmentItem("Contacts", 20, "Security & Life Safety", 40),
    "KeyFob": EquipmentItem("KeyFob", 20, "Security & Life Safety", 10),
    "Motion Detector": EquipmentItem("Motion Detector", 40, "Security & Life Safety", 20),
    "Glass Break Detector": EquipmentItem("Glass Break Detector", 60, "Security & Life Safety", 10),
    "Shock Sensor": EquipmentItem("Shock Sensor", 40, "Security & Life Safety", 20),
    "Flood Detector": EquipmentItem("Flood Detector", 50, "Security & Life Safety", 10),
    "Smoke/Heat Detector": EquipmentItem("Smoke/Heat Detector", 50, "Security & Life Safety", 10),
    "Carbon Detector": EquipmentItem("Carbon Detector", 50, "Security & Life Safety", 10),
    "Smoke Combo": EquipmentItem("Smoke Combo", 100, "Security & Life Safety", 10),
    "WL-WL Converter": EquipmentItem("WL-WL Converter", 75, "Security & Life Safety", 5),
    "HW-WL Converter": EquipmentItem("HW-WL Converter", 75, "Security & Life Safety", 5),
    "Outdoor Siren": EquipmentItem("Outdoor Siren", 80, "Security & Life Safety", 5),
    "Indoor Siren": EquipmentItem("Indoor Siren", 60, "Security & Life Safety", 5),
    "Wireless Touchscreen": EquipmentItem("Wireless Touchscreen", 120, "Security & Life Safety", 5),

    # Video
    "Indoor Camera": EquipmentItem("Indoor Camera", 130, "Video", 10),
    "Outdoor Camera": EquipmentItem("Outdoor Camera", 150, "Video", 10),
    "Nest Doorbell": EquipmentItem("Nest Doorbell", 140, "Video", 10),
    "WiFi Mesh Extender (Eero 6)": EquipmentItem(
        "WiFi Mesh Extender (Eero 6)", 120, "Video", 5
    ),

    # Automation
    "Doorlock": EquipmentItem("Doorlock", 130, "Automation", 10),
    "Thermostat": EquipmentItem("Thermostat", 130, "Automation", 5),
    "Garage Door Controller": EquipmentItem(
        "Garage Door Controller", 130, "Automation", 5
    ),
    "Hub 7in": EquipmentItem("Hub 7in", 100, "Automation", 1),
    "Hub Max": EquipmentItem("Hub Max", 170, "Automation", 1),
    "Lamp Module (Versa)": EquipmentItem(
        "Lamp Module (Versa)", 40, "Automation", 10
    ),
}


RESIDENTIAL_PACKAGES: Dict[str, Package] = {
    "Complete w. NAP - $64.99 + $7 = $71.99": Package(
        name="Complete w. NAP - $64.99 + $7 = $71.99",
        account_type="Residential",
        package_points=310,
        standard_mmr=64.99,
        allowed_mmr=(
            64.99, 63.99, 62.99, 61.99, 60.99, 59.99, 58.99,
            57.99, 56.99, 55.99, 54.99, 53.99, 52.99, 51.99,
        ),
        included_equipment={
            "Contacts": 3,
            "Motion Detector": 1,
            "Outdoor Camera": 1,
        },
        nap_included=True,
    ),
    "Complete - $64.99": Package(
        name="Complete - $64.99",
        account_type="Residential",
        package_points=270,
        standard_mmr=64.99,
        allowed_mmr=(
            64.99, 63.99, 62.99, 61.99, 60.99, 59.99, 58.99,
            57.99, 56.99, 55.99, 54.99, 53.99, 52.99, 51.99,
        ),
        included_equipment={
            "Contacts": 3,
            "Motion Detector": 1,
            "Outdoor Camera": 1,
        },
    ),
    "Smart - $63.99": Package(
        name="Smart - $63.99",
        account_type="Residential",
        package_points=270,
        standard_mmr=63.99,
        allowed_mmr=(
            63.99, 62.99, 61.99, 60.99, 59.99, 58.99, 57.99,
            56.99, 55.99, 54.99, 53.99, 52.99, 51.99, 50.99, 49.99,
        ),
        included_equipment={
            "Contacts": 3,
            "Motion Detector": 1,
            "Doorlock": 1,
            "Lamp Module (Versa)": 1,
        },
    ),
    "Secure - $53.99": Package(
        name="Secure - $53.99",
        account_type="Residential",
        package_points=100,
        standard_mmr=53.99,
        allowed_mmr=(
            53.99, 52.99, 51.99, 50.99, 49.99, 48.99,
            47.99, 46.99, 45.99, 44.99, 43.99, 42.99,
        ),
        included_equipment={
            "Contacts": 3,
            "Motion Detector": 1,
        },
    ),
}


COMMERCIAL_PACKAGES: Dict[str, Package] = {
    "Total Productivity @62.99": Package(
        name="Total Productivity @62.99",
        account_type="Commercial",
        package_points=250,
        standard_mmr=62.99,
        allowed_mmr=(66.99, 65.99, 64.99, 63.99, 62.99, 61.99, 60.99, 59.99, 58.99),
        included_equipment={
            "Contacts": 2,
            "Motion Detector": 1,
            "Indoor Camera": 1,
            "Lamp Module (Versa)": 1,
        },
        activation_minimum=99,
        activation_par=299,
        activation_maximum=599,
    ),
    "Enterprise View @57.99": Package(
        name="Enterprise View @57.99",
        account_type="Commercial",
        package_points=210,
        standard_mmr=57.99,
        allowed_mmr=(61.99, 60.99, 59.99, 58.99, 57.99, 56.99, 55.99, 54.99, 53.99),
        included_equipment={
            "Contacts": 2,
            "Motion Detector": 1,
            "Indoor Camera": 1,
        },
        activation_minimum=99,
        activation_par=199,
        activation_maximum=499,
    ),
    "Premise Remote @51.99": Package(
        name="Premise Remote @51.99",
        account_type="Commercial",
        package_points=80,
        standard_mmr=51.99,
        allowed_mmr=(55.99, 54.99, 53.99, 52.99, 51.99, 50.99, 49.99),
        included_equipment={
            "Contacts": 2,
            "Motion Detector": 1,
        },
        activation_minimum=99,
        activation_par=199,
        activation_maximum=499,
    ),
    "Premise Secure+ @49.99": Package(
        name="Premise Secure+ @49.99",
        account_type="Commercial",
        package_points=80,
        standard_mmr=49.99,
        allowed_mmr=(51.99, 50.99, 49.99, 48.99, 47.99, 46.99, 45.99),
        included_equipment={
            "Contacts": 2,
            "Motion Detector": 1,
        },
        activation_minimum=99,
        activation_par=99,
        activation_maximum=399,
    ),
}


# -----------------------------
# Calculation engine
# -----------------------------

def equipment_total_points(quantities: Dict[str, int]) -> int:
    return sum(EQUIPMENT[name].points * int(quantity) for name, quantity in quantities.items())


def package_included_points(package: Package) -> int:
    return equipment_total_points(package.included_equipment)


def mmr_commission_adjustment(selected_mmr: float, standard_mmr: float) -> float:
    """
    Exact workbook logic:
      positive MMR difference = 15 points per $1
      negative MMR difference = 35 points deducted per $1
    """
    difference = round(selected_mmr - standard_mmr, 2)
    if difference > 0:
        return difference * POSITIVE_MMR_POINT_RATE
    return difference * NEGATIVE_MMR_POINT_RATE


def commercial_activation_commission(
    actual_activation: float,
    par_activation: float,
) -> float:
    """
    Exact workbook logic:
      At/below par: $1 activation difference = 1 commission point.
      Above par: $1 activation difference = 0.833333333 commission points.
      Maximum commission = 650 points.
    """
    if actual_activation <= par_activation:
        adjustment = actual_activation - par_activation
    else:
        adjustment = (actual_activation - par_activation) * 0.833333333

    return min(
        MAX_COMMISSION_POINTS,
        COMMERCIAL_PAR_COMMISSION + adjustment,
    )


def calculate_results(
    package: Package,
    selected_mmr: float,
    quantities: Dict[str, int],
    installation_option: bool = False,
    nap_option: bool = False,
    max_option: bool = False,
    vrc_option: bool = False,
    actual_activation: float | None = None,
) -> Dict[str, float]:
    selected_equipment_points = float(equipment_total_points(quantities))

    extra_package_points = (
        NAP_ADDITIONAL_PACKAGE_POINTS
        if nap_option and not package.nap_included
        else 0.0
    )
    total_equipment_allowance = float(package.package_points) + extra_package_points
    equipment_overage = max(0.0, selected_equipment_points - total_equipment_allowance)
    unused_equipment_points = max(0.0, total_equipment_allowance - selected_equipment_points)

    mmr_points = mmr_commission_adjustment(selected_mmr, package.standard_mmr)

    if package.account_type == "Residential":
        automatic_commission_before_equipment = STARTING_RESIDENTIAL_COMMISSION
        automatic_commission_before_equipment += (
            INSTALLATION_ADDITIONAL_COMMISSION_POINTS if installation_option else 0.0
        )
        automatic_commission_before_equipment += (
            MAX_ADDITIONAL_COMMISSION_POINTS if max_option else 0.0
        )
        automatic_commission_before_equipment += (
            VRC_COMMISSION_POINTS if vrc_option else 0.0
        )
        activation_commission = 0.0
    else:
        if actual_activation is None or package.activation_par is None:
            raise ValueError("Commercial activation is required.")
        activation_commission = commercial_activation_commission(
            actual_activation,
            package.activation_par,
        )
        automatic_commission_before_equipment = activation_commission

    remaining_commission = (
        automatic_commission_before_equipment
        + mmr_points
        - equipment_overage
    )

    nap_selected = package.nap_included or nap_option
    total_monthly_mmr = selected_mmr
    if nap_selected:
        total_monthly_mmr += NAP_MONTHLY_FEE
    if max_option:
        total_monthly_mmr += MAX_MONTHLY_FEE

    return {
        "included_equipment_points": float(package_included_points(package)),
        "selected_equipment_points": selected_equipment_points,
        "base_package_points": float(package.package_points),
        "additional_package_points": extra_package_points,
        "total_equipment_allowance": total_equipment_allowance,
        "equipment_overage": equipment_overage,
        "unused_equipment_points": unused_equipment_points,
        "standard_mmr": package.standard_mmr,
        "selected_base_mmr": selected_mmr,
        "total_monthly_mmr": total_monthly_mmr,
        "mmr_difference": round(selected_mmr - package.standard_mmr, 2),
        "mmr_commission_adjustment": mmr_points,
        "automatic_commission_before_equipment": automatic_commission_before_equipment,
        "activation_commission": activation_commission,
        "remaining_commission": remaining_commission,
        "installation_fee": INSTALLATION_OPTION_FEE if installation_option else 0.0,
        "vrc_reward": VRC_REWARD_AMOUNT if vrc_option else 0.0,
    }


# -----------------------------
# Internal validation
# -----------------------------

def run_formula_tests() -> None:
    for package in list(RESIDENTIAL_PACKAGES.values()) + list(COMMERCIAL_PACKAGES.values()):
        included = package_included_points(package)
        assert included <= package.package_points, (
            f"{package.name}: included equipment exceeds package points."
        )

    secure = RESIDENTIAL_PACKAGES["Secure - $53.99"]
    secure_base = calculate_results(
        secure, secure.standard_mmr, dict(secure.included_equipment)
    )
    assert secure_base["remaining_commission"] == 650

    secure_with_camera = dict(secure.included_equipment)
    secure_with_camera["Indoor Camera"] = 1
    secure_camera = calculate_results(
        secure, secure.standard_mmr, secure_with_camera
    )
    assert secure_camera["equipment_overage"] == 130
    assert secure_camera["remaining_commission"] == 520

    secure_lower_mmr = calculate_results(
        secure, 52.99, dict(secure.included_equipment)
    )
    assert secure_lower_mmr["mmr_commission_adjustment"] == -35
    assert secure_lower_mmr["remaining_commission"] == 615

    total_productivity = COMMERCIAL_PACKAGES["Total Productivity @62.99"]
    at_par = calculate_results(
        total_productivity,
        total_productivity.standard_mmr,
        dict(total_productivity.included_equipment),
        actual_activation=299,
    )
    assert math.isclose(at_par["remaining_commission"], 400, abs_tol=0.001)

    at_max = calculate_results(
        total_productivity,
        total_productivity.standard_mmr,
        dict(total_productivity.included_equipment),
        actual_activation=599,
    )
    assert math.isclose(at_max["remaining_commission"], 650, abs_tol=0.001)


run_formula_tests()


# -----------------------------
# Display helpers
# -----------------------------

def money(value: float) -> str:
    return f"${value:,.2f}"


def points(value: float) -> str:
    if math.isclose(value, round(value), abs_tol=0.0001):
        return f"{int(round(value)):,}"
    return f"{value:,.2f}"


def safe_key(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()


def signed_points(value: float) -> str:
    return f"{value:+,.2f}".replace(".00", "")


def equipment_session_key(account_type: str, package_name: str, item_name: str) -> str:
    return (
        f"equipment__{safe_key(account_type)}__"
        f"{safe_key(package_name)}__{safe_key(item_name)}"
    )


def reset_current_equipment(account_type: str, package_name: str) -> None:
    prefix = f"equipment__{safe_key(account_type)}__{safe_key(package_name)}__"
    for key in list(st.session_state):
        if key.startswith(prefix):
            del st.session_state[key]
    st.rerun()


def build_csv_summary(
    package: Package,
    selected_mmr: float,
    quantities: Dict[str, int],
    results: Dict[str, float],
    installation_option: bool,
    nap_option: bool,
    max_option: bool,
    vrc_option: bool,
    actual_activation: float | None,
) -> str:
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["National Referral Calculator"])
    writer.writerow([])
    writer.writerow(["Account Type", package.account_type])
    writer.writerow(["Package", package.name])
    writer.writerow(["Approved Base MMR", f"{selected_mmr:.2f}"])
    writer.writerow(["Total Monthly MMR", f"{results['total_monthly_mmr']:.2f}"])

    if package.account_type == "Residential":
        writer.writerow(["$199 Installation Option", "Yes" if installation_option else "No"])
        writer.writerow(["NAP Option", "Included" if package.nap_included else ("Yes" if nap_option else "No")])
        writer.writerow(["$10 MMR MAX Option", "Yes" if max_option else "No"])
        writer.writerow(["$100 VRC Option", "Yes" if vrc_option else "No"])
        writer.writerow(["Installation Fee", f"{results['installation_fee']:.2f}"])
    else:
        writer.writerow(["Actual Activation", f"{actual_activation:.2f}" if actual_activation is not None else ""])

    writer.writerow([])
    writer.writerow(["Final Equipment", "Quantity", "Points Each", "Total Points"])

    writer.writerow(["Panel (5in) Command", 1, 0, 0])
    writer.writerow(["Radio", 1, 0, 0])

    for name, quantity in quantities.items():
        if quantity:
            item = EQUIPMENT[name]
            writer.writerow([name, quantity, item.points, quantity * item.points])

    writer.writerow([])
    writer.writerow(["Calculation", "Value"])
    writer.writerow(["Base Package Points", results["base_package_points"]])
    writer.writerow(["Additional Package Points", results["additional_package_points"]])
    writer.writerow(["Total Equipment Allowance", results["total_equipment_allowance"]])
    writer.writerow(["Selected Equipment Points", results["selected_equipment_points"]])
    writer.writerow(["Equipment Overage", results["equipment_overage"]])
    writer.writerow(["MMR Commission Adjustment", results["mmr_commission_adjustment"]])
    if package.account_type == "Commercial":
        writer.writerow(["Activation Commission", results["activation_commission"]])
    writer.writerow(["Remaining Commission Points", results["remaining_commission"]])
    writer.writerow(["Configuration Valid", "Yes" if results["remaining_commission"] >= 0 else "No"])

    return output.getvalue()


# -----------------------------
# Styles
# -----------------------------

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1500px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }

        .hero {
            border: 1px solid rgba(128,128,128,.28);
            border-radius: 16px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1rem;
        }

        .hero h1 {
            margin: 0 0 .25rem 0;
        }

        .step-title {
            margin-top: 1.3rem;
            padding-bottom: .35rem;
            border-bottom: 1px solid rgba(128,128,128,.25);
        }

        div[data-testid="stMetric"] {
            border: 1px solid rgba(128,128,128,.25);
            border-radius: 12px;
            padding: .9rem;
        }

        .locked-note {
            padding: .75rem 1rem;
            border-radius: 10px;
            background: rgba(128,128,128,.08);
            margin-bottom: .75rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# -----------------------------
# Application
# -----------------------------

st.markdown(
    """
    <div class="hero">
        <h1>National Referral Calculator</h1>
        <div>
            Select the account, package, approved pricing options, and final
            equipment quantities. All commission and point calculations are
            automatic and locked.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Referral Setup")
    account_type = st.radio(
        "Account type",
        ("Residential", "Commercial"),
        key="account_type",
    )

    st.divider()
    st.markdown(
        """
        **Locked calculations**

        EHPs cannot enter or override commission points. The calculator
        automatically applies package points, approved MMR adjustments,
        activation, equipment overages, and customer options.
        """
    )

packages = RESIDENTIAL_PACKAGES if account_type == "Residential" else COMMERCIAL_PACKAGES

st.markdown('<h2 class="step-title">1. Select the package</h2>', unsafe_allow_html=True)

package_name = st.selectbox(
    "Referral package",
    list(packages.keys()),
    key=f"package_{safe_key(account_type)}",
)
package = packages[package_name]

top_metrics = st.columns(4)
top_metrics[0].metric("Package Points", points(package.package_points))
top_metrics[1].metric("Standard Base MMR", money(package.standard_mmr))
top_metrics[2].metric("Included Equipment Points", points(package_included_points(package)))
top_metrics[3].metric(
    "Built-In Available Points",
    points(package.package_points - package_included_points(package)),
)

st.caption("Every package also includes one 5-inch Command panel and one radio at zero points.")

st.markdown('<h2 class="step-title">2. Select approved pricing options</h2>', unsafe_allow_html=True)

pricing_left, pricing_right = st.columns(2)

with pricing_left:
    selected_mmr = st.selectbox(
        "Approved base MMR",
        options=package.allowed_mmr,
        index=package.allowed_mmr.index(package.standard_mmr),
        format_func=lambda value: money(value),
        help=(
            "The commission impact of moving above or below standard MMR is "
            "calculated automatically from the workbook formula."
        ),
        key=f"mmr_{safe_key(account_type)}_{safe_key(package.name)}",
    )

installation_option = False
nap_option = False
max_option = False
vrc_option = False
actual_activation = None

with pricing_right:
    if account_type == "Residential":
        installation_option = st.checkbox(
            "$199 Installation Option",
            help=(
                "Adds a $199 customer installation charge and automatically "
                "adds 50 commission points."
            ),
            key=f"install_{safe_key(package.name)}",
        )

        if package.nap_included:
            st.checkbox(
                "$7 Nest Aware Plus (NAP)",
                value=True,
                disabled=True,
                help="NAP is already included in this package.",
                key=f"nap_included_{safe_key(package.name)}",
            )
        else:
            nap_option = st.checkbox(
                "$7 Nest Aware Plus (NAP) Option",
                help=(
                    "Adds $7 monthly and automatically adds 60 package points."
                ),
                key=f"nap_{safe_key(package.name)}",
            )

        max_option = st.checkbox(
            "$10 MMR MAX Option",
            help=(
                "Adds $10 monthly and automatically adds 75 commission points."
            ),
            key=f"max_{safe_key(package.name)}",
        )

        vrc_option = st.checkbox(
            "VRC ($100) Option",
            help=(
                "Provides the $100 VRC and automatically deducts 50 commission points."
            ),
            key=f"vrc_{safe_key(package.name)}",
        )
    else:
        assert package.activation_minimum is not None
        assert package.activation_par is not None
        assert package.activation_maximum is not None

        actual_activation = st.number_input(
            "Actual commercial activation",
            min_value=float(package.activation_minimum),
            max_value=float(package.activation_maximum),
            value=float(package.activation_par),
            step=1.0,
            format="%.2f",
            help=(
                "The commission is calculated automatically from minimum, par, "
                "maximum, and the workbook activation formula."
            ),
            key=f"activation_{safe_key(package.name)}",
        )

        activation_cols = st.columns(3)
        activation_cols[0].metric("Minimum", money(package.activation_minimum))
        activation_cols[1].metric("Par", money(package.activation_par))
        activation_cols[2].metric("Maximum", money(package.activation_maximum))


st.markdown('<h2 class="step-title">3. Add or remove equipment</h2>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="locked-note">
        Quantities below represent the <strong>final equipment going to the
        customer</strong>. Package equipment is preloaded. Reduce a quantity to
        remove or swap equipment, or increase it to add giveaway/MAX equipment.
        Point and commission impacts update automatically.
    </div>
    """,
    unsafe_allow_html=True,
)

reset_col, _ = st.columns([1, 4])
with reset_col:
    if st.button("Reset Equipment to Package", use_container_width=True):
        reset_current_equipment(account_type, package.name)

quantities: Dict[str, int] = {}

categories = ("Security & Life Safety", "Video", "Automation")
category_tabs = st.tabs(categories)

for tab, category in zip(category_tabs, categories):
    with tab:
        category_items = [item for item in EQUIPMENT.values() if item.category == category]
        columns = st.columns(3)

        for index, item in enumerate(category_items):
            included_quantity = int(package.included_equipment.get(item.name, 0))
            key = equipment_session_key(account_type, package.name, item.name)

            with columns[index % 3]:
                quantity = st.number_input(
                    item.name,
                    min_value=0,
                    max_value=item.maximum,
                    value=included_quantity,
                    step=1,
                    help=(
                        f"Package quantity: {included_quantity}. "
                        f"Point value: {item.points} per unit."
                    ),
                    key=key,
                )

                delta = int(quantity) - included_quantity
                if delta > 0:
                    st.caption(
                        f"Added: +{delta} • {delta * item.points:,} points"
                    )
                elif delta < 0:
                    st.caption(
                        f"Removed: {abs(delta)} • {abs(delta) * item.points:,} points released"
                    )
                else:
                    st.caption(
                        f"Package quantity: {included_quantity} • {item.points} points each"
                    )

            quantities[item.name] = int(quantity)


results = calculate_results(
    package=package,
    selected_mmr=float(selected_mmr),
    quantities=quantities,
    installation_option=installation_option,
    nap_option=nap_option,
    max_option=max_option,
    vrc_option=vrc_option,
    actual_activation=actual_activation,
)


st.markdown('<h2 class="step-title">4. Automatic results</h2>', unsafe_allow_html=True)

result_metrics = st.columns(5)
result_metrics[0].metric("Total Monthly MMR", money(results["total_monthly_mmr"]))
result_metrics[1].metric("Equipment Allowance", points(results["total_equipment_allowance"]))
result_metrics[2].metric("Selected Equipment", points(results["selected_equipment_points"]))
result_metrics[3].metric(
    "Equipment Overage",
    points(results["equipment_overage"]),
    delta=(
        f"-{points(results['equipment_overage'])} commission"
        if results["equipment_overage"] > 0 else "No deduction"
    ),
    delta_color="inverse",
)
result_metrics[4].metric(
    "Remaining Commission",
    points(results["remaining_commission"]),
)

if account_type == "Residential":
    customer_cost_cols = st.columns(3)
    customer_cost_cols[0].metric(
        "Installation Fee",
        money(results["installation_fee"]),
    )
    customer_cost_cols[1].metric(
        "NAP Monthly",
        money(NAP_MONTHLY_FEE) if (package.nap_included or nap_option) else money(0),
    )
    customer_cost_cols[2].metric(
        "MAX Monthly",
        money(MAX_MONTHLY_FEE) if max_option else money(0),
    )
else:
    commercial_cols = st.columns(2)
    commercial_cols[0].metric(
        "Activation-Based Commission",
        points(results["activation_commission"]),
    )
    commercial_cols[1].metric(
        "MMR Commission Adjustment",
        signed_points(results["mmr_commission_adjustment"]),
    )

calculation_rows: List[Dict[str, str]] = [
    {
        "Automatic Calculation": "Base package point allowance",
        "Result": points(results["base_package_points"]),
    },
    {
        "Automatic Calculation": "Additional NAP package points",
        "Result": signed_points(results["additional_package_points"]),
    },
    {
        "Automatic Calculation": "Total equipment allowance",
        "Result": points(results["total_equipment_allowance"]),
    },
    {
        "Automatic Calculation": "Final equipment point total",
        "Result": points(results["selected_equipment_points"]),
    },
    {
        "Automatic Calculation": "Equipment points deducted from commission",
        "Result": f"-{points(results['equipment_overage'])}",
    },
    {
        "Automatic Calculation": "Approved MMR commission adjustment",
        "Result": signed_points(results["mmr_commission_adjustment"]),
    },
    {
        "Automatic Calculation": (
            "Activation-based commission"
            if account_type == "Commercial"
            else "Commission after selected customer options"
        ),
        "Result": points(results["automatic_commission_before_equipment"]),
    },
    {
        "Automatic Calculation": "Remaining commission points",
        "Result": points(results["remaining_commission"]),
    },
]

st.dataframe(calculation_rows, hide_index=True, use_container_width=True)

if results["remaining_commission"] < 0:
    st.error(
        "NOT ALLOWED: This configuration reduces remaining commission below zero. "
        "Remove equipment or change approved pricing options."
    )
elif results["equipment_overage"] > 0:
    st.warning(
        f"The final equipment exceeds the available package allowance by "
        f"{points(results['equipment_overage'])} points. That amount is "
        f"automatically deducted from commission."
    )
else:
    st.success(
        f"This configuration is within the package allowance. "
        f"{points(results['unused_equipment_points'])} equipment points remain available."
    )

if results["mmr_commission_adjustment"] < 0:
    st.info(
        f"The selected base MMR is {money(abs(results['mmr_difference']))} below "
        f"standard, automatically reducing commission by "
        f"{points(abs(results['mmr_commission_adjustment']))} points."
    )
elif results["mmr_commission_adjustment"] > 0:
    st.info(
        f"The selected base MMR is {money(results['mmr_difference'])} above "
        f"standard, automatically adding "
        f"{points(results['mmr_commission_adjustment'])} commission points."
    )


st.subheader("Final Customer Equipment")

final_rows = [
    {
        "Equipment": "Panel (5in) Command",
        "Final Quantity": 1,
        "Points Each": 0,
        "Total Points": 0,
        "Package Quantity": 1,
        "Change": "Included",
    },
    {
        "Equipment": "Radio",
        "Final Quantity": 1,
        "Points Each": 0,
        "Total Points": 0,
        "Package Quantity": 1,
        "Change": "Included",
    },
]

for item_name, quantity in quantities.items():
    if quantity == 0 and package.included_equipment.get(item_name, 0) == 0:
        continue

    included_quantity = int(package.included_equipment.get(item_name, 0))
    delta = quantity - included_quantity
    if delta > 0:
        change = f"Added {delta}"
    elif delta < 0:
        change = f"Removed {abs(delta)}"
    else:
        change = "No change"

    final_rows.append(
        {
            "Equipment": item_name,
            "Final Quantity": quantity,
            "Points Each": EQUIPMENT[item_name].points,
            "Total Points": quantity * EQUIPMENT[item_name].points,
            "Package Quantity": included_quantity,
            "Change": change,
        }
    )

st.dataframe(final_rows, hide_index=True, use_container_width=True)


summary_csv = build_csv_summary(
    package=package,
    selected_mmr=float(selected_mmr),
    quantities=quantities,
    results=results,
    installation_option=installation_option,
    nap_option=nap_option,
    max_option=max_option,
    vrc_option=vrc_option,
    actual_activation=actual_activation,
)

st.download_button(
    "Download Calculation Summary",
    data=summary_csv,
    file_name="national_referral_calculation.csv",
    mime="text/csv",
    type="primary",
    use_container_width=True,
)

with st.expander("Calculation rules used"):
    st.markdown(
        f"""
        - Residential commission starts at **{points(STARTING_RESIDENTIAL_COMMISSION)} points**.
        - The **$199 installation option** automatically adds
          **{points(INSTALLATION_ADDITIONAL_COMMISSION_POINTS)} commission points**.
        - The **$7 NAP option** automatically adds
          **{points(NAP_ADDITIONAL_PACKAGE_POINTS)} package points**.
        - The **$10 MMR MAX option** automatically adds
          **{points(MAX_ADDITIONAL_COMMISSION_POINTS)} commission points**.
        - The **$100 VRC option** automatically deducts
          **{points(abs(VRC_COMMISSION_POINTS))} commission points**.
        - Approved MMR above standard adds
          **{points(POSITIVE_MMR_POINT_RATE)} points per $1**.
        - Approved MMR below standard deducts
          **{points(NEGATIVE_MMR_POINT_RATE)} points per $1**.
        - Equipment exceeding the package allowance is deducted point-for-point.
        - Commercial activation commission is calculated from the selected
          package's minimum, par, and maximum and is capped at
          **{points(MAX_COMMISSION_POINTS)} points**.
        - A configuration is not allowed when remaining commission is below zero.
        """
    )
