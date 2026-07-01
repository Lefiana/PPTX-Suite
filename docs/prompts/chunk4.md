# Proceed to Chunk 4 — Manual Crop & Tilt Editor

Chunk 3 is now complete. Please proceed with **Chunk 4**.

Before implementing:

1. Inspect the current repository state.
2. Verify that Chunk 3 changes are present.
3. Confirm there are no overlapping implementations already in the repository.
4. Preserve the existing architecture and responsibilities.
5. Keep the implementation modular and reusable.

---

## Scope

This chunk introduces the **Manual Crop & Tilt Editor**.

The objective is to allow an operator to manually fine-tune an individual portrait while preserving the existing live PPTX update workflow.

This editor should become the preferred manual adjustment workflow, while reusing the infrastructure completed in Chunks 1 and 2.

---

# Files Allowed To Change

```text
core/
└── image_processor.py

phases/phase23/
├── qa_controller.py
├── preview_panel.py
├── metadata_service.py
└── crop_editor.py        (NEW)
```

Only modify additional files if absolutely necessary and explain why.

---

# Architecture Requirements

Reuse the infrastructure already implemented.

Specifically:

* Continue using `SlideUpdater.replace_slide_image()` as the only PPTX mutation entry point.
* Continue using `QASuiteFrame._apply_corrected_image()` as the reusable orchestration method.
* Continue using `MetadataService` as the only interface for `metadata.json`.
* Do not duplicate existing override logic.

If duplicate logic exists, refactor it carefully into reusable helpers rather than copying code.

---

# Token Optimization Rules

Existing files:

* Output only modified methods or patch/diff style changes.
* Do not print entire files unless more than 50% of the file changes.

New files:

* Provide the complete downloadable file.

Repository edits:

* Prefer direct repository edits whenever possible.

Before running long tests, always output the modified methods first so implementation is not lost if the conversation reaches the token limit.

---

# Functional Requirements

## 1. New Crop Editor Window

Create:

```text
phases/phase23/crop_editor.py
```

Implement:

```python
CropEditorWindow(tk.Toplevel)
```

The editor should contain:

* Original image canvas.
* Draggable crop rectangle.
* Corner resize handles.
* Edge resize handles.
* Locked aspect ratio based on the configured portrait ratio.
* Live preview pane.
* Rotation slider (-15° to +15°).
* Zoom slider (0.5× to 2.0×).
* Reset to Auto button.
* Cancel button.
* Apply & Re-Inject button.

---

## 2. Image Processing

Extend `image_processor.py`.

Add:

```python
crop_with_params(
    image_path,
    crop_params,
    target_ratio
)
```

Where:

```python
crop_params = {
    "x": ...,
    "y": ...,
    "w": ...,
    "h": ...,
    "rotation": ...
}
```

Requirements:

* Rotate first.
* Crop second.
* Preserve aspect ratio.
* Preserve the Chunk 3 zoom guardrails whenever applicable.
* Return a `BytesIO` object compatible with the existing slide update workflow.

Do not break existing APIs.

---

## 3. Metadata

Extend `MetadataService`.

Add accessors for:

* `get_crop_params(student_id)`
* `set_crop_params(student_id, crop_params)`

Continue using `student_id` as the primary key.

Persist:

```json
"crop_params": {
    "x": ...,
    "y": ...,
    "w": ...,
    "h": ...,
    "rotation": ...
}
```

Do not remove or rename existing metadata fields.

---

## 4. QA Integration

Add a new button to the Phase 23 UI:

```
✏️ Manual Crop & Tilt Editor
```

When clicked:

* Open `CropEditorWindow`.
* Load any previously saved `crop_params`.
* Otherwise initialize from the automatic crop.

When Apply is pressed:

* Generate the corrected portrait.
* Call `_apply_corrected_image()`.
* Persist `crop_params`.
* Refresh only the affected preview row.
* Refresh the preview image.
* Refresh review statistics.
* Do not regenerate the PowerPoint.

---

## 5. Refactoring

Review the existing override workflow.

If `_on_apply_override()` and `_on_clear_override()` contain duplicated orchestration logic that can now be replaced by `_apply_corrected_image()`, perform that refactor while preserving behavior.

Avoid unnecessary architectural changes.

---

# Out of Scope

Do not modify:

* Phase 0
* Phase 1
* PPTX engine
* SlideUpdater public APIs
* Main application structure

Do not introduce new workflows outside the Manual Crop Editor.

---

# Deliverables

After implementation provide:

1. Files modified.
2. New files created.
3. Methods modified.
4. Metadata schema additions.
5. Any refactoring performed.
6. Testing performed.
7. Backward compatibility notes.
8. Any technical debt discovered.
9. Recommendations for the next enhancement.

Do not begin any work beyond Chunk 4.
