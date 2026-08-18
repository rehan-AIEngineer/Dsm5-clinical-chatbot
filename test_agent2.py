"""
test_agent2.py
---------------
Standalone test for Agent 2 (Clinical & Grief Reasoning Engine).
Run from your project root: python test_agent2.py
"""

# --- Import check: confirms agents.py is internally wired correctly ---
try:
    from app.agents import run_agent_2_clinical
except ImportError as e:
    print(f"❌ Could not import run_agent_2_clinical — check app/agents.py for errors: {e}")
    raise

try:
    from app import agents as agents_module
    assert hasattr(agents_module, "_call_gemini_json"), "_call_gemini_json missing"
    assert hasattr(agents_module, "_parse_json_response"), "_parse_json_response missing"
    print("✅ Required helpers found in app/agents.py\n")
except AssertionError as e:
    print(f"❌ Wiring problem in app/agents.py: {e}")
    raise


TEST_CASES = [
    {
        "label": "TC-01: Clinical, unknown diagnosis, short duration",
        "message": "Brother hearing voices for 3 weeks, thinks neighbors are watching him.",
        "context": {
            "feature_mode": "clinical_support",
            "user_role": "caregiver",
            "diagnosis_status": "unknown",
            "clinical_data": {
                "relationship_to_target": "brother",
                "reported_symptoms": ["auditory_hallucinations", "persecutory_delusions"],
                "symptom_duration": "3_weeks",
                "substance_use_history": "none",
            },
        },
        "expected_keys": {"matched_criteria", "timeline_assessment", "ruleouts", "clinical_key_points"},
    },
    {
        "label": "TC-02: Clinical, known diagnosis (should skip timeline checks)",
        "message": "Refusing meds today, paranoid.",
        "context": {
            "feature_mode": "clinical_support",
            "user_role": "caregiver",
            "diagnosis_status": "known",
            "clinical_data": {"confirmed_diagnoses": ["Schizophrenia"]},
        },
        "expected_keys": {"matched_criteria", "timeline_assessment", "ruleouts", "clinical_key_points"},
    },
    {
        "label": "TC-03: Grief, 6 months (should NOT flag PGD)",
        "message": "I saw his jacket and broke down. I feel guilty moving on.",
        "context": {
            "feature_mode": "grief_workbook",
            "grief_data": {
                "user_memory_profile": {
                    "deceased_or_loss": "Brother",
                    "time_since_loss": "6_months",
                    "core_themes_identified": ["survivor_guilt", "isolation"],
                }
            },
        },
        "expected_keys": {"primary_emotions", "pgd_criteria_status", "recommended_response_angle"},
    },
    {
        "label": "TC-04: Grief, 18 months (SHOULD flag possible PGD)",
        "message": "Still can't work, life is meaningless.",
        "context": {
            "feature_mode": "grief_workbook",
            "grief_data": {
                "user_memory_profile": {
                    "deceased_or_loss": "Spouse",
                    "time_since_loss": "18_months",
                }
            },
        },
        "expected_keys": {"primary_emotions", "pgd_criteria_status", "recommended_response_angle"},
    },
]


def run_tests():
    passed = 0
    failed = 0

    for tc in TEST_CASES:
        print(f"\n--- {tc['label']} ---")
        print(f"Input: {tc['message']}")

        result = run_agent_2_clinical(tc["message"], tc["context"])
        print(f"Result: {result}")

        ok = True

        # Schema check
        if set(result.keys()) != tc["expected_keys"]:
            print(f"  ❌ Schema mismatch. Expected keys={tc['expected_keys']}, got={set(result.keys())}")
            ok = False

        # Fail-safe leak check — if this fires, Agent 2 silently failed
        flat_values = str(result.values())
        if "assessment_failed_fail_safe" in flat_values or "unavailable" in flat_values:
            print("  ⚠️  WARNING: fail-safe values detected — Agent 2 likely errored internally. Check logs.")
            ok = False

        if ok:
            print("  ✅ PASS (schema correct, no fail-safe triggered)")
            print("  👉 Manually read the content above — confirm timeline/PGD reasoning is sensible.")
            passed += 1
        else:
            failed += 1

    print(f"\n=== {passed} passed, {failed} failed out of {len(TEST_CASES)} ===")
    print("\nNOTE: Passing here only confirms structure (schema + no crash).")
    print("You must still manually read each 'Result' above to judge whether the")
    print("clinical/grief reasoning itself is accurate — that can't be auto-checked.")


def test_failsafe():
    """Simulates total failure to confirm the fail-safe path returns mode-correct dict."""
    import app.agents as agents_module

    original_keys = agents_module.GEMINI_KEYS
    agents_module.GEMINI_KEYS = []  # force failure inside _call_gemini_json

    print("\n--- Fail-safe test: clinical_support ---")
    result = run_agent_2_clinical("test", {"feature_mode": "clinical_support"})
    print(f"Result: {result}")
    assert result["clinical_key_points"] == ["assessment_failed_fail_safe"]
    print("  ✅ Clinical fail-safe PASS")

    print("\n--- Fail-safe test: grief_workbook ---")
    result = run_agent_2_clinical("test", {"feature_mode": "grief_workbook"})
    print(f"Result: {result}")
    assert result["recommended_response_angle"] == "assessment_failed_fail_safe"
    print("  ✅ Grief fail-safe PASS")

    agents_module.GEMINI_KEYS = original_keys


if __name__ == "__main__":
    run_tests()
    test_failsafe()