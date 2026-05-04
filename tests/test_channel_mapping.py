"""
Tests for src/channel_mapping.py

Validates:
  - auto_suggest_mapping inference rules
  - ChannelMapper.apply() rename logic
  - ChannelMapper.apply() conflict handling (two channels → same target)
  - Profile save/load round-trip
  - UNMAPPED channels keep original name
  - No silent fabrication of canonical names for generic inputs
"""
import json
import os
import tempfile

import numpy as np
import pytest

from src.channel_mapping import (
    CANONICAL_SIGNALS,
    UNMAPPED,
    ChannelMapper,
    apply_rigol_three_phase_defaults,
    auto_suggest_mapping,
    infer_unit_from_header,
)
from src.channel_mapping import ordered_mapping_targets, DIRECT_LINE_TO_LINE_MAPPING_TARGETS
from src.file_ingestion import ImportedDataset


# ──────────────────────────────────────────────────────────────────────────────
# auto_suggest_mapping tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("header,expected_canonical", [
    # Known aliases
    ("Van",       "v_an"),
    ("v_a",       "v_an"),
    ("ia",        "i_a"),
    ("Freq",      "freq"),
    ("Pinv",      "p_mech"),
    ("pinv",      "p_mech"),
    ("frequency", "freq"),
    ("vdc",       "v_dc"),
    # NO mapping expected for generic oscilloscope channels
    ("CH1(V)",    UNMAPPED),
    ("CH2(V)",    UNMAPPED),
    ("CH3(V)",    UNMAPPED),
    ("CH4(V)",    UNMAPPED),
    # NO mapping for totally unknown columns
    ("MySignal",  UNMAPPED),
    ("col_1",     UNMAPPED),
])
def test_auto_suggest_known_aliases(header, expected_canonical):
    result = auto_suggest_mapping([header])
    assert result[header] == expected_canonical, (
        f"Expected '{header}' → '{expected_canonical}', got '{result[header]}'"
    )


def test_auto_suggest_rigol_headers_are_unmapped():
    """CH1/CH2/CH3/CH4 from Rigol must NEVER be silently mapped to phase names."""
    headers = ["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)", "CH4(V)"]
    mapping = auto_suggest_mapping(headers)
    for ch in ("CH1(V)", "CH2(V)", "CH3(V)", "CH4(V)"):
        assert mapping[ch] == UNMAPPED, (
            f"'{ch}' must not be auto-mapped to a canonical name. "
            f"Got '{mapping[ch]}'"
        )


def test_apply_rigol_three_phase_defaults_presets_phase_channels_only():
    headers = ["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)", "CH4(V)"]
    suggested = auto_suggest_mapping(headers)
    updated = apply_rigol_three_phase_defaults(headers, suggested)
    assert updated["CH1(V)"] == "v_an"
    assert updated["CH2(V)"] == "v_bn"
    assert updated["CH3(V)"] == "v_cn"
    assert updated["CH4(V)"] == UNMAPPED


def test_apply_rigol_three_phase_defaults_preserves_existing_user_target():
    headers = ["Time(s)", "CH1(V)", "CH2(V)", "CH3(V)"]
    suggested = {
        "CH1(V)": "v_ab",
        "CH2(V)": UNMAPPED,
        "CH3(V)": UNMAPPED,
    }
    updated = apply_rigol_three_phase_defaults(headers, suggested)
    assert updated["CH1(V)"] == "v_ab"
    assert updated["CH2(V)"] == "v_bn"
    assert updated["CH3(V)"] == "v_cn"


def test_auto_suggest_simulation_excel_pinv():
    headers = ["time", "Pinv"]
    mapping = auto_suggest_mapping(headers)
    assert mapping["Pinv"] == "p_mech"
    # time col: mapped to UNMAPPED (not a canonical signal, it's the time axis)
    # actually auto_suggest doesn't see time col differently; just checks signal
    # aliases. 'time' is not in CANONICAL_SIGNALS so it won't map to anything
    # meaningful for signals — it's not in the alias list for signals.
    # Verify it's not mapped to a voltage/current/power signal.
    assert mapping["time"] not in ("v_an", "v_bn", "v_cn", "i_a", "i_b", "i_c")


# ──────────────────────────────────────────────────────────────────────────────
# infer_unit_from_header tests
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("header,expected_unit", [
    ("CH1(V)",    "V"),
    ("Time(s)",   "s"),
    ("Freq(Hz)",  "Hz"),
    ("Power(W)",  "W"),
    ("I_a(A)",    "A"),
    ("Voltage",   "V"),
    ("Pinv",      None),  # no unit hint
])
def test_infer_unit_from_header(header, expected_unit):
    assert infer_unit_from_header(header) == expected_unit


# ──────────────────────────────────────────────────────────────────────────────
# ChannelMapper.apply() tests
# ──────────────────────────────────────────────────────────────────────────────

def _make_dataset(channels: dict[str, np.ndarray]) -> ImportedDataset:
    n = len(next(iter(channels.values())))
    return ImportedDataset(
        source_type="rigol_csv",
        source_path="/fake/test.csv",
        channels=channels,
        time=np.linspace(0, 1, n),
        sample_rate=float(n - 1),
        duration=1.0,
        raw_headers=list(channels.keys()),
    )


def test_apply_renames_channel():
    ds = _make_dataset({"CH1(V)": np.ones(10), "CH2(V)": np.zeros(10)})
    mapper = ChannelMapper()
    mapping = {"CH1(V)": "v_an", "CH2(V)": UNMAPPED}
    result = mapper.apply(ds, mapping)

    assert "v_an" in result.channels
    assert "CH2(V)" in result.channels   # unmapped → kept as original
    assert "CH1(V)" not in result.channels


def test_apply_keeps_array_values():
    arr = np.array([1.0, 2.0, 3.0])
    ds = _make_dataset({"CH1(V)": arr})
    mapper = ChannelMapper()
    result = mapper.apply(ds, {"CH1(V)": "v_an"})
    assert np.array_equal(result.channels["v_an"], arr)


def test_apply_conflict_second_channel_keeps_original_name():
    """Two channels mapped to the same canonical name: first wins, second kept as-is."""
    ds = _make_dataset({
        "CH1(V)": np.ones(5),
        "CH2(V)": np.ones(5) * 2,
    })
    mapper = ChannelMapper()
    mapping = {"CH1(V)": "v_an", "CH2(V)": "v_an"}  # conflict
    result = mapper.apply(ds, mapping)

    assert "v_an" in result.channels
    # Second conflicting channel must be kept under original name
    assert "CH2(V)" in result.channels


def test_apply_unmapped_channels_warned():
    ds = _make_dataset({"CH1(V)": np.ones(5), "CH2(V)": np.ones(5)})
    mapper = ChannelMapper()
    mapping = {"CH1(V)": UNMAPPED, "CH2(V)": UNMAPPED}
    result = mapper.apply(ds, mapping)
    # A warning should mention unmapped channels
    assert any("unmapped" in w.lower() for w in result.warnings)


def test_apply_preserves_dataset_identity():
    """apply() must not mutate the original dataset."""
    original_arr = np.array([1.0, 2.0])
    ds = _make_dataset({"CH1(V)": original_arr})
    ds_start_channels = dict(ds.channels)
    mapper = ChannelMapper()
    mapper.apply(ds, {"CH1(V)": "v_an"})
    # Original unchanged
    assert list(ds.channels.keys()) == list(ds_start_channels.keys())


# ──────────────────────────────────────────────────────────────────────────────
# Profile persistence tests
# ──────────────────────────────────────────────────────────────────────────────

def test_profile_save_load_round_trip():
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_path = os.path.join(tmpdir, "channel_mappings.json")
        mapper = ChannelMapper(profiles_path=profiles_path)

        mapping = {"CH1(V)": "v_an", "CH2(V)": "v_bn", "CH3(V)": UNMAPPED}
        mapper.save_profile("rigol_3phase", mapping)

        mapper2 = ChannelMapper(profiles_path=profiles_path)
        loaded = mapper2.load_profile("rigol_3phase")

        assert loaded is not None
        assert loaded["CH1(V)"] == "v_an"
        assert loaded["CH2(V)"] == "v_bn"
        assert loaded["CH3(V)"] == UNMAPPED


def test_profile_list_profiles():
    with tempfile.TemporaryDirectory() as tmpdir:
        profiles_path = os.path.join(tmpdir, "channel_mappings.json")
        mapper = ChannelMapper(profiles_path=profiles_path)
        mapper.save_profile("alpha", {"A": "v_an"})
        mapper.save_profile("beta", {"B": "v_bn"})
        names = mapper.list_profiles()
        assert "alpha" in names
        assert "beta" in names


def test_profile_load_nonexistent_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        mapper = ChannelMapper(profiles_path=os.path.join(tmpdir, "cm.json"))
        result = mapper.load_profile("does_not_exist")
        assert result is None


# ──────────────────────────────────────────────────────────────────────────────
# VSM / Arduino telemetry header aliases
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("header,expected", [
    ("p_kw",    "p_mech"),
    ("P_KW",    "p_mech"),
    ("q_kvar",  "q"),
    ("Q_KVAR",  "q"),
    ("pkw",     "p_mech"),
    ("qkvar",   "q"),
    ("q_var",   "q"),
])
def test_vsm_power_aliases(header, expected):
    result = auto_suggest_mapping([header])
    assert result[header] == expected, (
        f"Expected '{header}' → '{expected}', got '{result[header]}'"
    )


def test_vsm_full_header_set_mapping():
    """All VSM telemetry headers map correctly; fault left unmapped."""
    headers = ["t_ms", "vdc", "freq", "p_kw", "q_kvar", "fault"]
    result = auto_suggest_mapping(headers)

    assert result["vdc"]    == "v_dc"
    assert result["freq"]   == "freq"
    assert result["p_kw"]   == "p_mech"
    assert result["q_kvar"] == "q"
    # fault is a boolean flag — should NOT be mapped to any canonical signal
    assert result["fault"]  == UNMAPPED
    # t_ms is the time column — not a signal channel, also unmapped is fine
    assert result["t_ms"]   == UNMAPPED


def test_ordered_mapping_targets_phases_before_line():
    """Ensure primary phase voltages appear before direct line-to-line keys."""
    ordered = ordered_mapping_targets(include_direct_line_to_line=True)
    # Phase voltages present
    for ph in ("v_an", "v_bn", "v_cn"):
        assert ph in ordered
    # Line-to-line present
    for ll in DIRECT_LINE_TO_LINE_MAPPING_TARGETS:
        assert ll in ordered
    # Each phase appears before any line-to-line entry
    for ph in ("v_an", "v_bn", "v_cn"):
        for ll in DIRECT_LINE_TO_LINE_MAPPING_TARGETS:
            assert ordered.index(ph) < ordered.index(ll)


def test_compute_line_to_line_from_phases_exact():
    """Verify derived formulas: v_ab = v_an - v_bn, etc."""
    import numpy as np
    from src.derived_channels import compute_line_to_line_channels

    v_an = np.array([1.0, 2.0, 3.0])
    v_bn = np.array([0.1, 0.2, 0.3])
    v_cn = np.array([0.5, 0.6, 0.7])
    channels = {"v_an": v_an, "v_bn": v_bn, "v_cn": v_cn}
    derived = compute_line_to_line_channels(channels)
    assert "v_ab" in derived and "v_bc" in derived and "v_ca" in derived
    assert np.allclose(derived["v_ab"], v_an - v_bn)
    assert np.allclose(derived["v_bc"], v_bn - v_cn)
    assert np.allclose(derived["v_ca"], v_cn - v_an)
