"""Unit tests for the universe builder.

The rows below are invented test fixtures that exercise the rules. They are not
project data and never reach an output file.
"""

import io

import pandas as pd

from whynow import universe as u

CONFIG = {
    "size": {"min_employees": 200, "max_employees": 2000, "min_plants": 1, "max_plants": 6,
             "min_plant_headcount_share": 0.5},
    "selection": {"universe_size": 2, "seed": 1},
    "industries": {
        "food_beverage": ["311", "3121"],
        "plastics": ["3261"],
        "metal_fabrication": ["332"],
        "packaging": ["3222", "32611", "32616", "33243", "327213"],
    },
}

HEADER = (
    "id,establishment_name,establishment_id,ein,company_name,street_address,city,state,"
    "zip_code,naics_code,establishment_type,annual_average_employees,created_timestamp\n"
)


def frame(rows: list[str]) -> pd.DataFrame:
    path = io.StringIO(HEADER + "\n".join(rows) + "\n")
    return u.assign_companies(u.load_establishments(path))


def test_normalize_name_drops_suffixes_and_punctuation():
    assert u.normalize_name("Acme Foods, Inc.") == u.normalize_name("ACME FOODS LLC") == "ACME FOODS"
    assert u.normalize_name("123") == ""
    assert u.normalize_name(None) == ""


def test_longest_prefix_wins():
    assert u.industry_for("326160", CONFIG["industries"]) == "packaging"
    assert u.industry_for("326199", CONFIG["industries"]) == "plastics"
    assert u.industry_for("332431", CONFIG["industries"]) == "packaging"
    assert u.industry_for("336111", CONFIG["industries"]) is None


def test_plants_roll_up_by_ein_and_by_name():
    df = frame([
        # Same company: two share an EIN, the third has no EIN but the same name.
        "1,Plant A,10,12-3456789,Acme Foods Inc,1 St,Columbus,OH,43004,311412,1,150,1",
        "2,Plant B,11,123456789,ACME FOODS,2 St,Dayton,OH,45402,311412,1,120,1",
        "3,Plant C,12,,Acme Foods LLC,3 St,Toledo,OH,43604,311412,1,90,1",
    ])
    assert df["company_key"].nunique() == 1
    out = u.build_candidates(df, CONFIG)
    assert len(out) == 1
    assert out.loc[0, "employees_reported"] == 360
    assert out.loc[0, "plant_count"] == 3
    assert out.loc[0, "industry"] == "food_beverage"


def test_icp_bounds_and_filters():
    df = frame([
        "1,Small,20,111111112,Tiny Metal Co,1 St,Akron,OH,44301,332710,1,60,1",          # too small
        "2,Big,21,111111113,Huge Plastics,1 St,Erie,PA,16501,326199,1,5000,1",           # too big
        "3,Gov,22,111111114,County Works,1 St,Erie,PA,16501,332710,2,400,1",             # government
        "4,Car,23,111111115,Auto Parts Maker,1 St,Flint,MI,48502,336390,1,400,1",        # off-target
        "5,Fit,24,111111116,Good Fabrication,1 St,Tulsa,OK,74103,332312,1,400,1",        # fits
        "6,Fit dup,24,111111116,Good Fabrication,1 St,Tulsa,OK,74103,332312,1,450,2",    # correction
        "7,PR,25,111111117,Island Foods,1 St,San Juan,PR,00901,311412,1,400,1",          # not a state
    ])
    out = u.build_candidates(df, CONFIG)
    assert list(out["company_name"]) == ["Good Fabrication"]
    assert out.loc[0, "employees_reported"] == 450  # latest submission kept


def test_too_many_plants_is_excluded():
    rows = [
        f"{i},Plant {i},{30 + i},222222222,Sprawl Packaging,1 St,Reno,NV,89501,322211,1,50,1"
        for i in range(7)
    ]
    assert u.build_candidates(frame(rows), CONFIG).empty


def test_selection_is_reproducible_and_balanced():
    candidates = pd.DataFrame({
        "company_key": list("abcdef"),
        "company_name": ["A", "B", "C", "D", "E", "F"],
        "industry": ["plastics"] * 5 + ["packaging"],
    })
    first = u.select_universe(candidates, CONFIG)
    second = u.select_universe(candidates, CONFIG)
    assert first.equals(second)
    assert sorted(first["industry"]) == ["packaging", "plastics"]
    assert list(first["account_id"]) == ["A001", "A002"]


def test_mostly_non_manufacturing_company_is_excluded():
    df = frame([
        "1,Field crew,40,333333333,Contractor Co,1 St,Houston,TX,77001,237120,1,500,1",
        "2,Fab shop,41,333333333,Contractor Co,2 St,Houston,TX,77001,332996,1,60,1",
    ])
    assert u.build_candidates(df, CONFIG).empty
