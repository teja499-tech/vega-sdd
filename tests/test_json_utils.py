from universal_sdd.json_utils import extract_json


def test_extract_json_from_fence():
    assert extract_json('text```json\n{"a":1}\n```') == {"a": 1}


def test_extract_json_from_prose():
    assert extract_json('Here it is: [1,2,3] done') == [1, 2, 3]
