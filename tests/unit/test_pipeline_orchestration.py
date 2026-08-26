import re
import json
from pathlib import Path
import pytest


def parse_hcl_map_to_dict(hcl_text: str) -> dict:
    """Converts a simplified HCL map/jsonencode string into a Python dict."""
    cleaned = re.sub(r"#.*$", "", hcl_text, flags=re.MULTILINE)
    cleaned = re.sub(r"module\.[^\n,]+", '"arn:aws:lambda:mock"', cleaned)
    cleaned = re.sub(r"var\.[^\n,]+", '"mock_var"', cleaned)

    # Convert keys: `Key = value` or `"Key" = value` -> `"Key": value`
    cleaned = re.sub(
        r'^\s*("([^"]+)"|([A-Za-z0-9_.$]+))\s*=',
        lambda m: f'"{m.group(2) or m.group(3)}":',
        cleaned,
        flags=re.MULTILINE,
    )

    lines = [line.rstrip() for line in cleaned.splitlines() if line.strip()]
    processed_lines = []
    for i, line in enumerate(lines):
        if not line.endswith((",", "{", "[")):
            for next_line in lines[i + 1 :]:
                next_stripped = next_line.strip()
                if next_stripped.startswith(('"', "{", "[")):
                    line += ","
                break
        processed_lines.append(line)

    json_str = "\n".join(processed_lines)
    json_str = re.sub(r",\s*([\}\]])", r"\1", json_str)

    return json.loads(json_str)


def extract_step_functions_definition() -> dict:
    tf_file = (
        Path(__file__).resolve().parent.parent.parent
        / "infra"
        / "app"
        / "step_functions.tf"
    )
    content = tf_file.read_text(encoding="utf-8")

    match = re.search(
        r"definition\s*=\s*jsonencode\((\{.*?\n\s*\})\)", content, re.DOTALL
    )
    assert match, "Could not find jsonencode definition block in step_functions.tf"

    return parse_hcl_map_to_dict(match.group(1))


@pytest.fixture(scope="module")
def state_machine_def():
    return extract_step_functions_definition()


class TestStepFunctionsOrchestration:
    def test_state_machine_structure(self, state_machine_def):
        assert "StartAt" in state_machine_def
        assert "States" in state_machine_def
        start_state = state_machine_def["StartAt"]
        assert start_state in state_machine_def["States"]

    def test_states_do_not_wipe_out_payload_for_downstream_tasks(
        self, state_machine_def
    ):
        """
        Regression Test for:
        'Unable to apply Path transformation to null or empty input'

        Ensures intermediate tasks chaining to downstream states do not use
        'OutputPath: $.Payload' which turns the execution state into null if the
        Lambda returns None/empty. Instead, 'ResultPath' must be used.
        """
        states = state_machine_def["States"]

        for state_name, state_config in states.items():
            if state_config.get("Type") == "Task":
                next_state = state_config.get("Next")
                if next_state and states.get(next_state, {}).get("Type") == "Task":
                    output_path = state_config.get("OutputPath")
                    assert output_path != "$.Payload", (
                        f"State '{state_name}' uses 'OutputPath: $.Payload' before next task '{next_state}'. "
                        f"Use 'ResultPath' (e.g., ResultPath: '$.{state_name.lower()}_result') instead "
                        f"to prevent empty/null input propagation errors."
                    )
                    assert "ResultPath" in state_config, (
                        f"State '{state_name}' must specify 'ResultPath' to safely preserve state payload."
                    )

    def test_state_machine_targets_exist(self, state_machine_def):
        """Validates that all Next and Catch targets point to valid existing states."""
        states = state_machine_def["States"]

        for state_name, state_config in states.items():
            next_target = state_config.get("Next")
            if next_target:
                assert next_target in states, (
                    f"State '{state_name}' has invalid Next target: '{next_target}'"
                )

            for catch_rule in state_config.get("Catch", []):
                catch_target = catch_rule.get("Next")
                assert catch_target in states, (
                    f"State '{state_name}' has invalid Catch target: '{catch_target}'"
                )
