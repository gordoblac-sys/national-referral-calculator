from __future__ import annotations

import base64
import csv
import io
import math
import re
from dataclasses import dataclass
from pathlib import Path
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

COMPLETE_RESIDENTIAL_PACKAGE_NAME = "Complete - $64.99"
MAX_ADDITIONAL_COMMISSION_POINTS = 75.0
INSTALLATION_OPTION_FEE = 199.0
INSTALLATION_ADDITIONAL_COMMISSION_POINTS = 50.0
VRC_REWARD_AMOUNT = 100.0
VRC_COMMISSION_POINTS = -50.0

POSITIVE_MMR_POINT_RATE = 15.0
NEGATIVE_MMR_POINT_RATE = 35.0



COMMERCIAL_PROHIBITED_LIFE_SAFETY = frozenset(
    {
        "Smoke/Heat Detector",
        "Carbon Detector",
        "Smoke Combo",
    }
)




RESIDENTIAL_PACKAGE_ALLOWED_CATEGORIES = {
    "Secure - $53.99": (
        "Security & Life Safety",
    ),
    "Smart - $63.99": (
        "Security & Life Safety",
        "Automation",
    ),
    "Complete - $64.99": (
        "Security & Life Safety",
        "Video",
        "Automation",
    ),
}



COMMERCIAL_PACKAGE_ALLOWED_CATEGORIES = {
    "Premise Secure+ @49.99": (
        "Security & Life Safety",
    ),
    "Premise Remote @51.99": (
        "Security & Life Safety",
    ),
    "Enterprise View @57.99": (
        "Security & Life Safety",
        "Video",
    ),
    "Total Productivity @62.99": (
        "Security & Life Safety",
        "Video",
        "Automation",
    ),
}

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


def equipment_allowed_for_account(
    account_type: str,
    item_name: str,
) -> bool:
    """Return whether equipment is allowed for this account type."""
    return not (
        account_type == "Commercial"
        and item_name in COMMERCIAL_PROHIBITED_LIFE_SAFETY
    )




def allowed_equipment_categories(
    package: Package,
) -> tuple[str, ...]:
    """Return categories available for the selected package."""

    package_rules = (
        COMMERCIAL_PACKAGE_ALLOWED_CATEGORIES
        if package.account_type == "Commercial"
        else RESIDENTIAL_PACKAGE_ALLOWED_CATEGORIES
    )

    try:
        return package_rules[package.name]
    except KeyError as error:
        raise ValueError(
            f"Equipment-category rules are missing for "
            f"{package.name}."
        ) from error



def equipment_allowed_for_package(
    package: Package,
    item: EquipmentItem,
) -> bool:
    """Return whether one equipment item is allowed."""

    if item.category not in allowed_equipment_categories(
        package
    ):
        return False

    if (
        package.account_type == "Commercial"
        and item.name
        in COMMERCIAL_PROHIBITED_LIFE_SAFETY
    ):
        return False

    return True


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
    # COMMERCIAL_CALCULATION_SAFETY_LOCK
    # COMPLETE_PACKAGE_ADDON_SAFETY
    if (
        package.account_type == "Residential"
        and package.name
        != COMPLETE_RESIDENTIAL_PACKAGE_NAME
        and (nap_option or max_option)
    ):
        raise ValueError(
            "NAP and MAX upgrades are only "
            "available from the Complete package."
        )

    if package.account_type == "Commercial":
        prohibited_selected = sorted(
            item_name
            for item_name, quantity in quantities.items()
            if int(quantity) > 0
            and not equipment_allowed_for_account(
                package.account_type,
                item_name,
            )
        )

        if prohibited_selected:
            raise ValueError(
                "The following equipment is not permitted "
                "on Commercial referrals: "
                + ", ".join(prohibited_selected)
            )

    # PACKAGE_EQUIPMENT_CATEGORY_SAFETY_LOCK
    invalid_package_equipment = sorted(
        item_name
        for item_name, quantity in quantities.items()
        if int(quantity) > 0
        and item_name in EQUIPMENT
        and not equipment_allowed_for_package(
            package,
            EQUIPMENT[item_name],
        )
    )

    if invalid_package_equipment:
        raise ValueError(
            f"The selected {package.name} package does not "
            "allow the following equipment: "
            + ", ".join(invalid_package_equipment)
        )

    # UNIFIED_PACKAGE_EQUIPMENT_SAFETY_LOCK
    invalid_equipment = sorted(
        item_name
        for item_name, quantity in quantities.items()
        if int(quantity) > 0
        and item_name in EQUIPMENT
        and not equipment_allowed_for_package(
            package,
            EQUIPMENT[item_name],
        )
    )

    if invalid_equipment:
        raise ValueError(
            f"The selected {package.name} package does not "
            "allow the following equipment: "
            + ", ".join(invalid_equipment)
        )

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
    """Validate package, equipment, MMR, and commission rules."""

    all_packages = [
        *RESIDENTIAL_PACKAGES.values(),
        *COMMERCIAL_PACKAGES.values(),
    ]

    for package in all_packages:
        included_points = package_included_points(
            package
        )

        assert included_points <= package.package_points, (
            f"{package.name}: included equipment exceeds "
            "the package point allowance."
        )

        for item_name, quantity in (
            package.included_equipment.items()
        ):
            if quantity <= 0:
                continue

            assert item_name in EQUIPMENT, (
                f"{package.name}: unknown equipment "
                f"{item_name}."
            )

            assert equipment_allowed_for_package(
                package,
                EQUIPMENT[item_name],
            ), (
                f"{package.name}: included equipment "
                f"{item_name} is not allowed."
            )

    assert set(RESIDENTIAL_PACKAGES) == {
        "Secure - $53.99",
        "Smart - $63.99",
        "Complete - $64.99",
    }

    assert set(COMMERCIAL_PACKAGES) == {
        "Premise Secure+ @49.99",
        "Premise Remote @51.99",
        "Enterprise View @57.99",
        "Total Productivity @62.99",
    }

    # Residential package-category rules
    secure = RESIDENTIAL_PACKAGES[
        "Secure - $53.99"
    ]
    smart = RESIDENTIAL_PACKAGES[
        "Smart - $63.99"
    ]
    complete = RESIDENTIAL_PACKAGES[
        "Complete - $64.99"
    ]

    assert allowed_equipment_categories(secure) == (
        "Security & Life Safety",
    )

    assert allowed_equipment_categories(smart) == (
        "Security & Life Safety",
        "Automation",
    )

    assert allowed_equipment_categories(complete) == (
        "Security & Life Safety",
        "Video",
        "Automation",
    )

    assert equipment_allowed_for_package(
        secure,
        EQUIPMENT["Smoke/Heat Detector"],
    )

    assert not equipment_allowed_for_package(
        secure,
        EQUIPMENT["Indoor Camera"],
    )

    assert equipment_allowed_for_package(
        smart,
        EQUIPMENT["Doorlock"],
    )

    assert not equipment_allowed_for_package(
        smart,
        EQUIPMENT["Indoor Camera"],
    )

    assert equipment_allowed_for_package(
        complete,
        EQUIPMENT["Indoor Camera"],
    )

    assert equipment_allowed_for_package(
        complete,
        EQUIPMENT["Doorlock"],
    )

    # Commercial package-category rules
    premise_secure_plus = COMMERCIAL_PACKAGES[
        "Premise Secure+ @49.99"
    ]
    premise_remote = COMMERCIAL_PACKAGES[
        "Premise Remote @51.99"
    ]
    enterprise_view = COMMERCIAL_PACKAGES[
        "Enterprise View @57.99"
    ]
    total_productivity = COMMERCIAL_PACKAGES[
        "Total Productivity @62.99"
    ]

    assert allowed_equipment_categories(
        premise_secure_plus
    ) == (
        "Security & Life Safety",
    )

    assert allowed_equipment_categories(
        premise_remote
    ) == (
        "Security & Life Safety",
    )

    assert allowed_equipment_categories(
        enterprise_view
    ) == (
        "Security & Life Safety",
        "Video",
    )

    assert allowed_equipment_categories(
        total_productivity
    ) == (
        "Security & Life Safety",
        "Video",
        "Automation",
    )

    assert equipment_allowed_for_package(
        premise_secure_plus,
        EQUIPMENT["Contacts"],
    )

    assert not equipment_allowed_for_package(
        premise_secure_plus,
        EQUIPMENT["Indoor Camera"],
    )

    assert not equipment_allowed_for_package(
        premise_remote,
        EQUIPMENT["Indoor Camera"],
    )

    assert equipment_allowed_for_package(
        enterprise_view,
        EQUIPMENT["Indoor Camera"],
    )

    assert not equipment_allowed_for_package(
        enterprise_view,
        EQUIPMENT["Doorlock"],
    )

    assert equipment_allowed_for_package(
        total_productivity,
        EQUIPMENT["Indoor Camera"],
    )

    assert equipment_allowed_for_package(
        total_productivity,
        EQUIPMENT["Doorlock"],
    )

    # Commercial life safety must always remain prohibited.
    for commercial_package in (
        premise_secure_plus,
        premise_remote,
        enterprise_view,
        total_productivity,
    ):
        for prohibited_item in (
            "Smoke/Heat Detector",
            "Carbon Detector",
            "Smoke Combo",
        ):
            assert not equipment_allowed_for_package(
                commercial_package,
                EQUIPMENT[prohibited_item],
            )

    # Residential commission and equipment-overage tests
    secure_base = calculate_results(
        secure,
        secure.standard_mmr,
        dict(secure.included_equipment),
    )

    assert secure_base["remaining_commission"] == 650

    secure_with_smoke_combo = dict(
        secure.included_equipment
    )
    secure_with_smoke_combo["Smoke Combo"] = 1

    secure_security_overage = calculate_results(
        secure,
        secure.standard_mmr,
        secure_with_smoke_combo,
    )

    assert (
        secure_security_overage[
            "equipment_overage"
        ]
        == 100
    )

    assert (
        secure_security_overage[
            "remaining_commission"
        ]
        == 550
    )

    secure_lower_mmr = calculate_results(
        secure,
        52.99,
        dict(secure.included_equipment),
    )

    assert (
        secure_lower_mmr[
            "mmr_commission_adjustment"
        ]
        == -35
    )

    assert (
        secure_lower_mmr[
            "remaining_commission"
        ]
        == 615
    )

    # Complete NAP and MAX tests
    complete_with_nap = calculate_results(
        complete,
        complete.standard_mmr,
        dict(complete.included_equipment),
        nap_option=True,
    )

    assert (
        complete_with_nap[
            "total_monthly_mmr"
        ]
        == 71.99
    )

    complete_with_nap_and_max = calculate_results(
        complete,
        complete.standard_mmr,
        dict(complete.included_equipment),
        nap_option=True,
        max_option=True,
    )

    assert (
        complete_with_nap_and_max[
            "total_monthly_mmr"
        ]
        == 81.99
    )

    # Commercial activation commission tests
    at_par = calculate_results(
        total_productivity,
        total_productivity.standard_mmr,
        dict(total_productivity.included_equipment),
        actual_activation=299,
    )

    assert math.isclose(
        at_par["remaining_commission"],
        400,
        abs_tol=0.001,
    )

    at_max = calculate_results(
        total_productivity,
        total_productivity.standard_mmr,
        dict(total_productivity.included_equipment),
        actual_activation=599,
    )

    assert math.isclose(
        at_max["remaining_commission"],
        650,
        abs_tol=0.001,
    )


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

# SAFESTREETS_CLEAN_BRAND_START

def _ss_image_data_uri(image_path: Path) -> str:
    """Convert the local shield PNG into a browser image."""
    if not image_path.exists():
        return ""

    encoded = base64.b64encode(
        image_path.read_bytes()
    ).decode("ascii")

    return f"data:image/png;base64,{encoded}"


_ss_shield_path = (
    Path(__file__).resolve().parent
    / "assets"
    / "safestreets-shield.png"
)

_ss_shield_uri = _ss_image_data_uri(
    _ss_shield_path
)

_ss_shield_markup = (
    f'<img class="ss-brand-shield" '
    f'src="{_ss_shield_uri}" '
    f'alt="SafeStreets shield" />'
    if _ss_shield_uri
    else (
        '<div class="ss-brand-shield-fallback">'
        '🛡️'
        '</div>'
    )
)

st.markdown(
    """
<style>
    .block-container {
        padding-bottom: 5rem !important;
    }

    .ss-brand-strip {
        display: grid;
        grid-template-columns:
            auto minmax(0, 1fr) auto;
        align-items: center;
        gap: 1rem;
        margin: 0 0 1rem;
        padding: .8rem 1rem;
        border: 1px solid
            rgba(14, 165, 233, .28);
        border-radius: 18px;
        background:
            radial-gradient(
                circle at 92% 15%,
                rgba(14, 165, 233, .18),
                transparent 14rem
            ),
            linear-gradient(
                135deg,
                #020617 0%,
                #062f4f 58%,
                #075985 100%
            );
        box-shadow:
            0 14px 38px
            rgba(2, 132, 199, .14);
    }

    .ss-brand-shield,
    .ss-brand-shield-fallback {
        width: 64px;
        height: 64px;
        object-fit: contain;
        filter:
            drop-shadow(
                0 8px 13px
                rgba(14, 165, 233, .28)
            );
    }

    .ss-brand-shield-fallback {
        display: grid;
        place-items: center;
        border-radius: 16px;
        background:
            rgba(255, 255, 255, .08);
        font-size: 2rem;
    }

    .ss-brand-copy {
        min-width: 0;
    }

    .ss-brand-name {
        color: #7dd3fc;
        font-size: .72rem;
        font-weight: 850;
        letter-spacing: .12em;
        text-transform: uppercase;
    }

    .ss-brand-title {
        margin-top: .12rem;
        color: white;
        font-size:
            clamp(1.05rem, 2.2vw, 1.5rem);
        font-weight: 850;
        line-height: 1.15;
        letter-spacing: -.02em;
    }

    .ss-brand-tagline {
        margin-top: .18rem;
        color:
            rgba(226, 232, 240, .78);
        font-size: .78rem;
        line-height: 1.35;
    }

    .ss-star-lockup {
        min-width: max-content;
        text-align: right;
    }

    .ss-stars {
        color: #fbbf24;
        font-size: 1.18rem;
        line-height: 1;
        letter-spacing: .1rem;
        text-shadow:
            0 0 16px
            rgba(251, 191, 36, .28);
    }

    .ss-star-label {
        margin-top: .28rem;
        color:
            rgba(255, 255, 255, .68);
        font-size: .62rem;
        font-weight: 800;
        letter-spacing: .075em;
        text-transform: uppercase;
    }

    .ss-created-by {
        position: fixed;
        right: 14px;
        bottom: 10px;
        z-index: 999999;
        padding: .38rem .66rem;
        border: 1px solid
            rgba(14, 165, 233, .24);
        border-radius: 999px;
        color:
            rgba(226, 232, 240, .88);
        background:
            rgba(2, 6, 23, .86);
        box-shadow:
            0 8px 22px
            rgba(2, 6, 23, .20);
        backdrop-filter: blur(10px);
        font-size: .68rem;
        letter-spacing: .02em;
    }

    .ss-created-by strong {
        color: #7dd3fc;
        font-weight: 850;
    }

    @media (max-width: 700px) {
        .ss-brand-strip {
            grid-template-columns:
                auto minmax(0, 1fr);
            gap: .72rem;
            padding: .72rem .78rem;
            border-radius: 15px;
        }

        .ss-brand-shield,
        .ss-brand-shield-fallback {
            width: 48px;
            height: 48px;
        }

        .ss-star-lockup {
            grid-column: 1 / -1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: .45rem;
            border-top: 1px solid
                rgba(255, 255, 255, .10);
            text-align: left;
        }

        .ss-star-label {
            margin-top: 0;
        }

        .ss-created-by {
            right: 8px;
            bottom: 7px;
            font-size: .61rem;
        }
    }
</style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    (
        '<section class="ss-brand-strip">'

        f'{_ss_shield_markup}'

        '<div class="ss-brand-copy">'
        '<div class="ss-brand-name">'
        'SafeStreets'
        '</div>'

        '<div class="ss-brand-title">'
        'National Referral Calculator'
        '</div>'

        '<div class="ss-brand-tagline">'
        'Protection built with confidence, '
        'accuracy, and a five-star experience.'
        '</div>'
        '</div>'

        '<div class="ss-star-lockup">'
        '<div class="ss-stars" '
        'aria-label="Five stars">'
        '★★★★★'
        '</div>'

        '<div class="ss-star-label">'
        'Five-Star Customer Experience'
        '</div>'
        '</div>'

        '</section>'
    ),
    unsafe_allow_html=True,
)
# SAFESTREETS_CLEAN_BRAND_END

# SAFESTREETS_LOADING_SHIELD_START
st.markdown(
    f"""
    <style>
        /*
        Replace Streamlit's top-right running animation
        with the SafeStreets shield.
        */
        div[data-testid="stStatusWidget"] {{
            position: relative !important;
            width: 44px !important;
            min-width: 44px !important;
            height: 44px !important;
            min-height: 44px !important;
            overflow: visible !important;
        }}

        /*
        Hide Streamlit's running person, bike,
        message, and stop-button artwork.
        */
        div[data-testid="stStatusWidget"] * {{
            visibility: hidden !important;
        }}

        /*
        The status widget only appears while Streamlit
        is running, so the shield spins only during loading.
        */
        div[data-testid="stStatusWidget"]::before {{
            content: "";
            position: absolute;
            z-index: 999999;
            top: 4px;
            right: 4px;
            width: 36px;
            height: 36px;

            background-image:
                url("{_ss_shield_uri}");
            background-repeat: no-repeat;
            background-position: center;
            background-size: contain;

            transform-origin: 50% 50%;
            animation:
                safestreetShieldSpin
                1.15s linear infinite;

            filter:
                drop-shadow(
                    0 0 5px
                    rgba(56, 189, 248, .65)
                )
                drop-shadow(
                    0 5px 8px
                    rgba(2, 132, 199, .30)
                );
        }}

        div[data-testid="stStatusWidget"]::after {{
            content: "";
            position: absolute;
            top: 1px;
            right: 1px;
            width: 42px;
            height: 42px;
            border-radius: 50%;
            border:
                1px solid
                rgba(56, 189, 248, .25);
            box-shadow:
                inset 0 0 12px
                rgba(14, 165, 233, .10);
            animation:
                safestreetShieldGlow
                1.15s ease-in-out infinite;
        }}

        @keyframes safestreetShieldSpin {{
            0% {{
                transform: rotate(0deg) scale(.96);
            }}

            50% {{
                transform: rotate(180deg) scale(1.04);
            }}

            100% {{
                transform: rotate(360deg) scale(.96);
            }}
        }}

        @keyframes safestreetShieldGlow {{
            0%,
            100% {{
                opacity: .45;
                transform: scale(.92);
            }}

            50% {{
                opacity: 1;
                transform: scale(1.05);
            }}
        }}

        @media (max-width: 600px) {{
            div[data-testid="stStatusWidget"] {{
                width: 38px !important;
                min-width: 38px !important;
                height: 38px !important;
                min-height: 38px !important;
            }}

            div[data-testid="stStatusWidget"]::before {{
                width: 31px;
                height: 31px;
                top: 4px;
                right: 3px;
            }}

            div[data-testid="stStatusWidget"]::after {{
                width: 36px;
                height: 36px;
                top: 1px;
                right: 1px;
            }}
        }}

        @media (prefers-reduced-motion: reduce) {{
            div[data-testid="stStatusWidget"]::before {{
                animation:
                    safestreetShieldPulse
                    1.2s ease-in-out infinite;
            }}

            @keyframes safestreetShieldPulse {{
                0%,
                100% {{
                    opacity: .65;
                    transform: scale(.94);
                }}

                50% {{
                    opacity: 1;
                    transform: scale(1.04);
                }}
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True,
)
# SAFESTREETS_LOADING_SHIELD_END






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

        # COMPLETE_ONLY_NAP_MAX_OPTIONS
        if package.name == COMPLETE_RESIDENTIAL_PACKAGE_NAME:
            nap_option = st.checkbox(
                "$7 Nest Aware Plus (NAP) Option",
                help=(
                    "Adds $7 monthly and automatically "
                    "adds 60 package points."
                ),
                key=f"nap_{safe_key(package.name)}",
            )

            max_option = st.checkbox(
                "$10 MMR MAX Option",
                help=(
                    "Adds $10 monthly and automatically "
                    "adds 75 commission points."
                ),
                key=f"max_{safe_key(package.name)}",
            )
        else:
            st.caption(
                "NAP and MAX upgrades are available "
                "from the Complete package."
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



# UNIFIED_PACKAGE_EQUIPMENT_SETUP
categories = allowed_equipment_categories(
    package
)

category_labels = {
    "Security & Life Safety": (
        "🛡️ Security"
        if account_type == "Commercial"
        else "🛡️ Security & Life Safety"
    ),
    "Video": "📹 Video",
    "Automation": "🏠 Automation",
}

package_equipment_messages = {
    "Secure - $53.99": (
        "Secure includes Security & Life Safety equipment."
    ),
    "Smart - $63.99": (
        "Smart includes Security & Life Safety and "
        "Automation equipment."
    ),
    "Complete - $64.99": (
        "Complete includes Security & Life Safety, "
        "Video, and Automation equipment."
    ),
    "Premise Secure+ @49.99": (
        "Premise Secure+ includes Security equipment."
    ),
    "Premise Remote @51.99": (
        "Premise Remote includes Security equipment."
    ),
    "Enterprise View @57.99": (
        "Enterprise View includes Security and Video equipment."
    ),
    "Total Productivity @62.99": (
        "Total Productivity includes Security, Video, "
        "and Automation equipment."
    ),
}

st.caption(
    package_equipment_messages[package.name]
)

category_tabs = st.tabs(
    [
        category_labels[category]
        for category in categories
    ]
)

for tab, category in zip(
    category_tabs,
    categories,
):
    with tab:
        category_items = [
            item
            for item in EQUIPMENT.values()
            if item.category == category
            and equipment_allowed_for_package(
                package,
                item,
            )
        ]

        # COMMERCIAL_EQUIPMENT_FILTER_START
        category_items = [
            item
            for item in category_items
            if equipment_allowed_for_account(
                account_type,
                item.name,
            )
        ]
        # COMMERCIAL_EQUIPMENT_FILTER_END
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

# SAFESTREETS_FOOTER_START
st.markdown(
    (
        '<div class="ss-created-by">'
        'Created by '
        '<strong>Gordon Black</strong>'
        '</div>'
    ),
    unsafe_allow_html=True,
)
# SAFESTREETS_FOOTER_END
