"""Laufbezogene Ausgabe und Statistik."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Thread
from types import SimpleNamespace

from sortiton import output, tasks


def test_run_context_isolates_overlapping_runs():
    barrier = Barrier(2, timeout=5)
    events = [[], []]

    def run(index):
        context = output.RunContext(
            logger=lambda text: events[index].append(("log", text)),
            plan_sink=lambda event: events[index].append(("plan", event)),
            stats_sink=lambda kind, values: events[index].append((kind, values)),
        )

        def action():
            output.report_stats("tags", changed=index + 1)
            barrier.wait()
            output.message(str(index))
            output.report_plan("tags", path=str(index), changes={})
            assert context.last_stats("tags") == {"changed": index + 1}
            return index

        return context.execute(action)

    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(run, range(2)))

    for index, report in enumerate(reports):
        assert report.returncode == index
        assert report.stats == {"tags": {"changed": index + 1}}
        assert events[index] == [
            ("tags", {"changed": index + 1}),
            ("log", str(index)),
            ("plan", output.TagPlanEvent("tags", {"path": str(index), "changes": {}},
                                         str(index), {})),
        ]


def test_file_plan_event_exposes_typed_fields_and_legacy_data():
    events = []
    context = output.RunContext(plan_sink=events.append)

    def action():
        output.report_plan("dedupe", source="a", target="b", keep="c")
        return 0

    context.execute(action)
    event = events[0]
    assert isinstance(event, output.FilePlanEvent)
    assert (event.source, event.target, event.keep) == ("a", "b", "c")
    assert event.data == {"source": "a", "target": "b", "keep": "c"}


def test_pool_submission_propagates_run_context():
    lines = []
    context = output.RunContext(logger=lines.append)

    def action():
        with ThreadPoolExecutor(max_workers=1) as pool:
            output.submit_with_context(pool, output.message, "worker").result(timeout=5)
        return 0

    assert context.execute(action).returncode == 0
    assert lines == ["worker"]


def test_legacy_sink_api_is_gone():
    for name in ("set_logger", "set_progress", "set_plan_sink",
                 "set_stats_sink", "last_stats", "default_run_context"):
        assert not hasattr(output, name), name


def test_explicit_context_keeps_its_own_stats():
    context = output.RunContext()

    def action():
        output.report_stats("tags", changed=1)
        return 0

    report = context.execute(action)
    assert context.last_stats("tags") == {"changed": 1}
    assert report.stats == {"tags": {"changed": 1}}
    context.clear_stats("tags")
    assert context.last_stats("tags") == {}


def test_structured_output_requires_a_context():
    errors = []

    def call():
        try:
            output.report_stats("tags", changed=1)
        except RuntimeError as error:
            errors.append(str(error))

    thread = Thread(target=call)
    thread.start()
    thread.join()
    assert errors and "RunContext" in errors[0]


def test_task_checks_for_a_context_before_touching_files(tmp_path):
    errors = []

    def call():
        try:
            tasks.cmd_tags(SimpleNamespace(folder=str(tmp_path), apply=True,
                                           backup=False))
        except RuntimeError as error:
            errors.append(str(error))

    thread = Thread(target=call)
    thread.start()
    thread.join()
    assert errors and "RunContext" in errors[0]
    assert list(tmp_path.iterdir()) == []


def test_non_logging_sink_failures_do_not_abort_run():
    def broken(*_args):
        raise ValueError("kaputt")

    context = output.RunContext(progress_sink=broken, plan_sink=broken, stats_sink=broken)

    def action():
        output.progress(1, 2)
        output.report_plan("sort", source="a", target="b")
        output.report_stats("sort", changed=1)
        return 0

    report = context.execute(action)
    assert report.stats == {"sort": {"changed": 1}}


def test_all_uses_its_own_stage_counters(monkeypatch, tmp_path):
    barrier = Barrier(2, timeout=5)

    def steps(args):
        def stage(kind):
            def run():
                output.report_stats(kind, files=args.count, changed=args.count,
                                    skipped=0, errors=0)
                if kind == "tags":
                    barrier.wait()
                return 0
            return tasks.Step("task.step.tags", run)
        return [stage("tags"), stage("rename"), stage("sort")]

    monkeypatch.setattr(tasks, "_pipeline_steps", steps)

    def run(count):
        args = SimpleNamespace(source=str(tmp_path), target=str(tmp_path.parent / "target"),
                               pattern="pattern", move=False, apply=False, count=count)
        return output.RunContext(logger=lambda _line: None).execute(
            lambda: tasks.cmd_all(args))

    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(run, (2, 5)))

    for count, report in zip((2, 5), reports):
        assert report.returncode == 0
        assert report.stats["all"]["tags_changed"] == count
        assert report.stats["all"]["renamed"] == count
        assert report.stats["all"]["sorted_files"] == count
