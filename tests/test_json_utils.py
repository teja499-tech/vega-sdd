from universal_sdd.json_utils import extract_json


def test_extract_json_from_fence():
    assert extract_json('text```json\n{"a":1}\n```') == {"a": 1}


def test_extract_json_from_prose():
    assert extract_json('Here it is: [1,2,3] done') == [1, 2, 3]


def test_extract_json_unwraps_encoded_string():
    assert extract_json('{"name":"probe"}') == {"name": "probe"}
    assert extract_json('"{\\"name\\":\\"probe\\"}"') == {"name": "probe"}


def test_parse_structured_skips_inner_object():
    from universal_sdd.json_utils import parse_structured
    text = '{"name":"inner"} then {"product":{"name":"Taskline","summary":"s","users":[],"capabilities":[],"workflows":[],"constraints":[],"assumptions":[],"open_questions":[]},"features":[]}'
    def validate(value):
        if not isinstance(value, dict) or "product" not in value:
            raise ValueError("need product")
        return value
    assert parse_structured(text, validate)["product"]["name"] == "Taskline"
