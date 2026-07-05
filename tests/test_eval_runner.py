from pika.observability.eval import load_questions, validate_questions


def test_load_getting_started_evals():
    questions = load_questions("getting_started")
    assert len(questions) >= 2


def test_validate_questions_structure():
    questions = load_questions("getting_started", limit=1)
    passed, failed, lines = validate_questions(questions)
    assert passed == 1
    assert failed == 0
    assert lines
