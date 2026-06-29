from aria.core.stage_timing import StageTimingLedger
from aria.core.stage_timing import insert_stage_timing_detail_lines


def test_insert_stage_timing_lines_keeps_answer_tail_after_debug_lines():
    timing = StageTimingLedger(enabled=True)
    timing.add("pipeline_wall_time", 42)

    lines = insert_stage_timing_detail_lines(
        [
            "Routing Debug: direct_context_answer kind=docs_search",
            "Bitte zuerst die App oeffnen.",
        ],
        timing,
    )

    assert lines == [
        "Routing Debug: direct_context_answer kind=docs_search",
        "Routing Debug: stage_timing stage=pipeline_wall_time ms=42",
        "Bitte zuerst die App oeffnen.",
    ]


def test_insert_stage_timing_lines_appends_after_source_lines():
    timing = StageTimingLedger(enabled=True)
    timing.add("skill_runtime", 7)

    lines = insert_stage_timing_detail_lines(
        [
            "Quelle: Mill Manual.pdf",
        ],
        timing,
    )

    assert lines == [
        "Quelle: Mill Manual.pdf",
        "Routing Debug: stage_timing stage=skill_runtime ms=7",
    ]
