# Sortiton: UI Handoff

Status: 25 October 2026. Design recommendation; not implemented.

## Decision

Sortiton should feel like a tool for checking and editing a music collection,
not like a long settings page. The recommended layout is a compact, two-column
workspace: operation and rules on the left, preview on the right, and approval
and status at the bottom. Additional window space should show more content
that users can review.

Keep Tkinter for now. The greatest benefit comes from improving the
information architecture, not from new colours or a framework change. Decide
separately on a future PySide6 migration if a large file table, native
accessibility and better desktop integration cannot be achieved adequately
with Tkinter. That would be a separate project involving new dependencies and
packaging work.

## Findings and evidence

The README screenshot, current window layout, design values, preview/result
widgets and existing GUI tests were reviewed. The current application was
measured under Xvfb at 100% UI scaling in three window sizes and captured at
1920 x 1080.

The current UI differs from the README screenshot: it has five pages, page
headings and additional folder/mode fields.

| Window | Form width | Form height | Action row y | Result height |
| --- | ---: | ---: | ---: | ---: |
| 900 x 600 | 841 px | 714 px | 321 px | 176 px |
| 1920 x 1080 | 1120 px | 714 px | 801 px | 176 px |
| 2560 x 1440 | 1120 px | 714 px | 1161 px | 176 px |

These values describe the initial state of the "Clean tags" page. At 900 x 600,
the form is scrollable as expected. At 2560 x 1440, it uses only about 44% of
the window width, leaving roughly 360 px unused between the form and action
row. The result area does not grow.

The width limit and centering are controlled by
[`_resize_content_canvas`](sortiton/gui/mixins/layout.py#L318). The flexible
height is assigned to the content row, while the result has a fixed minimum
height:
[`_build_window`](sortiton/gui/mixins/layout.py#L179). The form and fixed rows
use different width calculations:
[`_content_inset`](sortiton/gui/mixins/layout.py#L47). At 2560 px, the form
starts at x=720 and the action row at x=713. The scrollbar is also at the
outer edge of the window, far from the form.

This explains the poor use of space in large windows. No specific overlap was
found. Maximizing under KDE/Wayland, window decorations, multiple monitors and
HiDPI have not been verified yet.

The dated appearance is a design assessment: many large borders, nested
preview frames, uppercase labels, mostly dark surfaces and scattered actions
give important and secondary information similar visual weight. The preview
remains a small summary block instead of the primary workspace.

## Target layout

Wide desktop window, schematic; numbers and content are sample data:

```text
 Sortiton   Clean tags | Rename | Sort | All | Tools                 [Settings]
 ------------------------------------------------------------------------------
 Operation / 320 px            | Preview                    [Search] [Filter]
                               | 120 files / 198 changes
 Source folder       [Folder]  | ---------------------------------------------
 Target folder       [Folder]  | File       Field       Before       Planned
 Copy | Move                   | Track 01   Artist      SAMPLE BAND  Sample Band
                               | Track 03   Title       Track  03    Track 03
 Rules                         | Track 08   Genre       jpop         J-Pop
 Custom rules       [Edit]     | ... more visible rows ...
 Corrections       [Details]   | ---------------------------------------------
                               | Selected: Track 03
 More options          [v]     | Full values / path / matching rule
 ------------------------------------------------------------------------------
 Ready / Backup on             [Create preview]       [Apply changes]
```

Avoid decorative cards around entire page sections. A narrow divider separates
configuration from the review area. Table rows and group spacing structure the
content. Keep the existing app icon as the visual brand. Do not show album
artwork when reliable cover data is unavailable.

### Navigation and layout

- Keep all five existing functions directly accessible. Use real tabs instead
  of the visually equal, stretched segment bar.
- Use a resizable configuration pane on the left: 320 logical px by default,
  280 minimum and 420 maximum. Long paths must remain accessible in full.
- Let the preview fill the remaining space on the right and grow vertically.
  Its rows scroll; navigation and approval remain visible.
- At 1200 logical px and above, use two columns. Between 900 and 1199 px, make
  configuration collapsible. Below that, place configuration above the
  preview without horizontal scrolling of the entire application.
- Remove the global 1120 px limit. Apply sensible maximum widths only to
  reading text and individual input fields. Place scrollbars directly beside
  the content they scroll.
- After a run, replace the preview header with the result summary. Open logs
  in a separate resizable area on demand. Do not keep an empty, permanently
  176 px-high result block.
- Keep settings in a separate window. Keep restore in its own dialog, reached
  through a recognizable undo action.

### Visual specification

| Element | Specification |
| --- | --- |
| Colour scheme | Auto (system), Light or Dark; selected in settings and applied immediately |
| Background / workspace | `#F4F5F7` / `#FFFFFF` |
| Primary / secondary text | `#20242B` / `#545D6B` |
| Lines | `#D8DDE4`, used sparingly |
| Primary accent | Teal `#006B68`, white text |
| Success / warning / error | `#187346` / `#875400` / `#B42318` |
| Font | Cantarell, then Noto Sans, then the available system font |
| Font sizes | 11 pt base, 15 pt page title, secondary values at least 10 pt |
| Grid | 4 / 8 / 12 / 16 / 24 logical px |
| Controls | 36 px high; icon targets at least 32 x 32 px |
| Table rows | 32 px, fixed height, clear selection state |
| Corners | 4 px for fields and buttons; no pill-shaped status labels |

Never convey status using colour alone: add text and an icon. Check the final
light and dark colour combinations against WCAG AA. Use one consistent icon
set, such as Lucide prepared as PNG assets for Tkinter, instead of mixed
Unicode symbols. Folder, refresh, settings and undo controls need icons,
tooltips and accessible names. Keep text on primary commands. Show keyboard
focus clearly; avoid blinking effects and decorative animations.

## Interaction and safety rules

| State | Display and allowed action |
| --- | --- |
| No operation | Folder fields visible; execution disabled |
| No preview yet | Empty review area; preview is the primary action |
| Analysis running | Show progress and Cancel; prevent parallel execution |
| Preview current | Show file/change counts; Apply is primary |
| Inputs changed | Mark preview stale; disable Apply |
| No changes | Show a clear empty state; do not imply a write run is needed |
| Execution running | Show progress and Cancel; lock configuration |
| Complete / partially failed | Show counters, error details, log and restore |

Keep preview and execution separate. The existing
[`_preview_ready`](sortiton/gui/mixins/run.py#L397) check must not be removed
by the redesign. Changed folders, rules, patterns or modes must continue to
invalidate approval. Show backup status; the existing confirmation shows
scope, target and file operation. Keep the special warnings for moves and
duplicates. Cancellation is not rollback; restore is a separate operation.

Tags: preview by file and tag field. Rename/sort: source path, target path and
operation. All: distinguish the steps clearly. Tools: retain existing
feature-specific options and status values; do not force export and duplicates
into a tag table.

## Implementation handoff

### Package 1: Layout without backend changes

In [`layout.py`](sortiton/gui/mixins/layout.py), move configuration and preview
into a split workspace. The flexible grid row belongs to the preview, not to
an empty canvas area. Replace separate centering formulas with one shared
outer margin. In [`log.py`](sortiton/gui/mixins/log.py), open results and logs
on demand; combine status and approval in a stable bottom row. Keep colours,
spacing and typography centralized in
[`design.py`](sortiton/gui/design.py), and adapt widgets and forms to them.

Initially use the existing aggregated preview and label it clearly as a
summary. Do not offer search or filters that scan only a few examples while
implying completeness.

### Package 2: Complete review view

[`PreviewCard`](sortiton/gui/panels.py#L29) currently shows examples.
[`_absorb_plan`](sortiton/gui/mixins/run.py#L303) aggregates events, and
[`_plan_rows`](sortiton/gui/mixins/run.py#L451) shows only the first example
per tag field and the first path pair for file operations. A complete table
therefore needs more than replacing a widget.

Review plan events from [`output.py`](sortiton/output.py) for usable file and
field information. Then build a separate structured read model with run ID,
path, operation, field, old/new value and a status supported by the evidence.
Show rule provenance only when it is actually supplied. Bound memory use;
page large plans or spill them to temporary storage. Do not create a Tk label
for every change.

Only then enable file-level search, filters and detail view. The table is
read-only initially: selecting a row opens its details; it does not enable
selective execution. Per-change checkboxes are outside this scope and require
their own execution semantics.

### Out of scope

No backend rewrite, new rule engine, CLI changes, automatic file changes or
new music-player functionality. Do not add persisted window layout without a
separate decision. Keep all visible text in both German and English in
[`i18n.py`](sortiton/i18n.py); preserve features and saved options.

## Acceptance

- At 900 x 600, 1280 x 720, 1920 x 1080 and 2560 x 1440, tabs, approval and
  Cancel remain visible; controls do not overlap.
- At 100%, 150% and 200% scaling, use logical measurements. Do not scale fonts
  and widgets twice. Smaller workspaces switch to the narrow layout instead
  of enforcing large minimum widths.
- More window height grows the preview, not empty space between configuration
  and actions. More width improves the review view.
- The form, header and footer share the same outer edges. Scrollbars appear
  only when content overflows and stay beside that content.
- Check all five pages, German/English text and long paths. Full values remain
  accessible through details or tooltips.
- Keyboard operation works, including tab order, focus, page switching,
  confirmation and cancellation. Icons alone need tooltips.
- Tests for current/stale previews, locking during a run, backup, errors and
  restore remain green.
- For Package 2, test 10,000 changes with synthetic data. Search, scrolling
  and cancellation must not noticeably block the UI thread. Completeness and
  counters must match the plan.
- Add layout regression tests to [`test_gui.py`](tests/test_gui.py); currently
  it covers small windows and scrolling, but not a wide adaptive workspace.
  Then run the existing project gate.
- Use only synthetic paths and data for screenshots: wide/narrow layouts,
  light/dark appearance, preview, run and error states. Also test actual
  maximizing under KDE/Wayland and switching monitors.

Handoff goal: approve Package 1 first. Start Package 2 only after layout and
safety are stable and the read model has been agreed.
