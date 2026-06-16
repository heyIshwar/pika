def answer_quality_metric(example, prediction, trace=None) -> float:
    """Word-overlap score between expected and actual answer."""
    expected = example.answer.strip().lower()
    actual = prediction.answer.strip().lower()

    expected_words = set(expected.split())
    actual_words = set(actual.split())

    if not expected_words:
        return 0.0

    overlap = len(expected_words & actual_words)
    return overlap / len(expected_words)
