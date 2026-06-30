# Phase 23 Enhancement — Chunk 3

## Zoom Guardrails & Image Processing Improvements

Act as an expert Python developer and software architect.

Use the previously provided project handoff as the source of truth for the architecture and completed work.

This is **Chunk 3** of the implementation roadmap.

---

# Before Implementation

Before making any code changes:

1. Inspect the current implementation.
2. Verify that none of the Chunk 3 requirements have already been implemented.
3. If any requirement is partially implemented, adapt the implementation instead of duplicating functionality.
4. Preserve the existing architecture and public APIs wherever possible.
5. Keep changes incremental, modular, and backward compatible.

Briefly provide:

* Implementation approach.
* Files that will change.
* Methods/functions that will change.
* Configuration/schema changes.
* Backward compatibility considerations.

Keep the explanation concise.

---

# Architecture Constraints

Preserve the current architecture.

Responsibilities should remain:

* `config_manager.py`

  * Configuration loading/saving.
* `image_processor.py`

  * Face detection and image cropping only.
* `calibration_ui.py`

  * Configuration editor only.
* No business logic inside the UI.
* No Phase 23 modifications.
* No metadata changes.

Do not restructure unrelated modules.

---

# Files Allowed To Change

```text
core/
├── image_processor.py
└── config_manager.py

phases/phase0/
└── calibration_ui.py
```

Only modify additional files if absolutely necessary and explain why.

---

# Token Optimization Rules

To conserve context and reduce token usage:

## Existing files

* Output only modified methods/classes or patch-style changes.
* Do not print entire files unless more than 50% of the file changes.

## New files

* Provide complete downloadable files.

## Repository edits

* Prefer direct repository edits whenever possible.

## Important

Before running any expensive integration tests, always output the modified methods first so implementation is not lost if token limits are reached.

Do not rerun unrelated integration tests.

Only run tests relevant to this chunk.

---

# Objective

Improve the robustness of the automatic portrait cropping engine while preserving the current workflow.

The purpose is to reduce over-zoomed portraits and make manual overrides produce more natural graduation photos.

This chunk should improve the existing algorithm.

It should **not** introduce new user workflows.

---

# Requirements

## 1. Add `min_crop_fraction`

Extend the face detection configuration with a new parameter:

```json
{
    "min_crop_fraction": 0.55
}
```

Purpose:

Prevent extremely tight crops caused by oversized detected face bounding boxes.

Rules:

* Crop height must never become smaller than:

```text
min_crop_fraction × original_image_height
```

Default value:

```text
0.55
```

The value must remain configurable.

---

## 2. Improve Manual Face Estimate

Locate the manual face estimation logic.

Current behavior:

```python
face_width = image_width * 0.20
```

Update to:

```python
face_width = image_width * 0.13
```

Goal:

Reduce excessive zoom when the operator manually selects a face center.

Maintain the existing public behavior.

---

## 3. Increase Default Bottom Padding

Update the default configuration.

Current:

```text
bottom_padding_factor = 1.8
```

New default:

```text
bottom_padding_factor = 2.8
```

Purpose:

Keep more of the shoulders, graduation gown, and body visible.

The value must still be editable through Phase 0.

---

## 4. Crop Height Guardrail

Modify the crop calculation so that:

* automatic face detection
* manual face override

both respect the minimum crop height.

Implementation requirements:

* preserve the requested aspect ratio;
* avoid changing horizontal framing unnecessarily;
* expand the crop symmetrically whenever possible;
* clamp safely to image boundaries.

Do not introduce image distortion.

---

## 5. Configuration Management

Extend the configuration system to support the new option.

Requirements:

* Auto-create missing values.
* Existing configuration files must continue to work.
* Missing configuration should receive defaults automatically.
* Invalid numeric values should produce descriptive validation errors.

---

## 6. Phase 0 Calibration UI

Expose the following new calibration field:

```text
min_crop_fraction
```

Requirements:

* Behave exactly like existing calibration controls.
* Load from configuration.
* Save to configuration.
* Validate numeric values.
* Match the existing UI style.

---

## 7. Validation

Confirm that:

* Existing projects continue working.
* Existing layout_config.json files remain compatible.
* Missing values are automatically populated.
* No existing configuration fields are removed.
* Existing portrait generation continues to function.

---

# Out of Scope

Do NOT implement:

* Crop Editor
* Rotation
* Zoom slider
* Manual crop box
* crop_params metadata
* Phase 23 UI
* Metadata schema changes
* PPT generation changes
* SlideUpdater changes
* QA controller changes
* Preview panel changes

Those belong to future chunks.

---

# Deliverables

After implementation provide:

## Repository Changes

* Files modified.
* Methods/functions modified.
* Any new helper methods.

## Configuration Changes

* New configuration fields.
* Default values.
* Migration behavior.

## Testing

Run only tests relevant to this chunk.

Include:

* Validation tests.
* Crop behavior tests.
* Backward compatibility tests.

Do not rerun full Phase 23 integration tests unless required.

---

## Final Summary

Provide:

1. Concise implementation summary.
2. Backward compatibility notes.
3. Any technical debt discovered.
4. Recommendations for Chunk 4 (Manual Crop/Tilt Editor).

Do not begin Chunk 4.
Complete only the scope defined above.
