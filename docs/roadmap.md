Graduation Slide Automation Suite — Handoff Summary
1. Architecture
graduation_suite/
├── main.py                        # Lightweight: dependency check, ttk styles, phase nav
├── config/layout_config.json      # Auto-created. Portrait position, shape names, fd tuning
├── data/metadata.json             # Auto-created. Session paths + per-student state
├── core/
│   ├── config_manager.py          # layout_config.json I/O + flatten/unflatten
│   ├── metadata_manager.py        # metadata.json raw I/O (index-based)
│   ├── image_processor.py         # OpenCV face detection + PIL cropping
│   └── pptx_engine.py             # Slide duplication, text injection, re-injection
├── phases/
│   ├── phase0/calibration_ui.py   # Scrollable form for layout_config.json
│   ├── phase1/
│   │   ├── ingestor_ui.py         # UI orchestrator (thin)
│   │   ├── folder_classifier.py   # Normalize/parse/3-pass name matching
│   │   ├── file_operations.py     # copy/move execution + Excel+txt reports
│   │   └── mappings.py            # Programme keyword tables, dest labels
│   └── phase23/
│       ├── qa_controller.py       # Orchestrator only — no business logic
│       ├── toolbar.py             # Path rows, Load/Generate, counters, Open Folder
│       ├── preview_panel.py       # Treeview + cropped preview + click canvas
│       ├── slide_updater.py       # ImageProcessor + PPTXEngine glue layer
│       └── metadata_service.py    # All metadata.json access for Phase 2+3
└── ui/
    ├── sidebar.py                 # Extracted sidebar widget
    ├── widgets.py                 # PALETTE, make_card, make_header_bar, make_path_row
    └── dialogs.py                 # Thin filedialog/messagebox wrappers


Key design rules:

app.config_manager → layout config only. app.metadata_manager → session + student state only.
All Phase 2+3 metadata access goes exclusively through MetadataService — no module reads metadata.json directly.
SlideUpdater.replace_slide_image() is the single validated entry point for all PPTX mutations.
QASuiteFrame._apply_corrected_image(image_stream) is the reusable orchestration method for any override operation.
2. Completed Features
Refactor (pre-chunk)
Monolithic files split into the structure above.
config_manager.py and metadata_manager.py separated (previously one class).
ui/ package extracted. Phase 1 matching engine split into folder_classifier.py + file_operations.py.
phase23_qa_suite.py split into 5 focused modules.
Phase 1 Ingestor
Excel roster → fuzzy folder name matching (3-pass: exact → surname-token → difflib).
Handles compound Filipino surnames (De La Pena, Del Rosario, San Pedro), diacritics (Ñ→N).
Dry-run preview + execute with copy/move modes.
4-sheet Excel reconciliation report + missing_records_*.txt.
Chunk 1 — Metadata, Status Tracking, UX Foundation
6-status vocabulary: pending / generated / overridden / placeholder / failed / skipped.
Deterministic student_id field: SURNAME_FIRSTNAME_<excel_index>.
MetadataService ID-based CRUD: get_student(), update_student(), set_status().
get_review_statistics() → full status breakdown dict.
Toolbar: Reviewed: X / Y + Failed: X counters, auto-refreshed after every state change.
📂 Open Output Folder button (cross-platform: os.startfile / open / xdg-open).
Persistent post-generation status message: ✅ PPTX is live at: <path> — Every override updates this file directly.
Chunk 2 — Live PPT Reinjection Infrastructure
pptx_path + last_updated stamped on every student record after generation.
MetadataService: get_slide_info(), set_slide_info(), update_last_updated(), now_iso().
SlideUpdater.replace_slide_image() — validates (FileNotFoundError / RuntimeError / IndexError / ValueError) before touching the file; failed calls leave the PPTX byte-identical.
SlideUpdater.update_student_slide(student_dict, image_stream) — convenience wrapper for callers with a full student record.
reinject_portrait() refactored to delegate to replace_slide_image().
QASuiteFrame._apply_corrected_image(image_stream, new_status) — reusable orchestrator: lookup → update_student_slide → persist slide_info → refresh row + preview + stats.
set_slide_info() called additively in both _on_apply_override() and _on_clear_override().
3. Remaining Chunks (planned, not started)
Chunk 3 — Zoom Guardrail + Image Processing Fixes

Files: core/image_processor.py, core/config_manager.py, phases/phase0/calibration_ui.py

Changes already designed (intentionally reverted during refactor to preserve behavior parity):

bottom_padding_factor default: 1.8 → 2.8
Manual face estimate: img_w × 0.20 → img_w × 0.13
New min_crop_fraction: 0.55 guard in _apply_crop() — crop height ≥ 55% of image height prevents over-zoom
New Phase 0 field row for min_crop_fraction
Chunk 4 — Manual Crop/Tilt Editor

New file: phases/phase23/crop_editor.py (CropEditorWindow(tk.Toplevel))

Planned features:

Draggable/resizable crop box with aspect-ratio lock (from layout_config.json)
Corner + edge handles
Rotation slider (−15° to +15°) via PIL rotate
Zoom slider (0.5× to 2.0×)
Live preview pane (exact PPTX result)
Reset to Auto button
On Apply: produces a BytesIO stream → calls qa_controller._apply_corrected_image(stream)
New image_processor.crop_with_params(image_path, crop_params: dict, target_ratio) where crop_params = {x, y, w, h, rotation}
crop_params persisted to metadata.json per student alongside manual_face_center

Integration point in qa_controller.py: one new ✏️ Manual Crop/Tilt Editor button in preview_panel.py's action bar, opens CropEditorWindow, pre-loads existing crop_params if present.

4. Metadata Schema (current metadata.json)

json

{
  "session": {
    "excel_path": "",
    "template_path": "",
    "output_pptx_path": "",
    "master_dir": "",
    "source_dir": "",
    "dest_dir": ""
  },
  "students": [
    {
      "excel_index": 0,
      "student_id": "DELA_CRUZ_JUAN_0",
      "surname": "DELA CRUZ",
      "firstname": "Juan Manuel",
      "course": "Bachelor of Science in Computer Science",
      "image_path": "/path/to/photo.jpg",
      "slide_index": 0,
      "portrait_shape_id": 6,
      "pptx_path": "/path/to/Final_Graduation.pptx",
      "last_updated": "2026-06-30T14:00:00",
      "status": "generated",
      "manual_face_center": null
    }
  ]
}


Fields added by chunk:

FieldAdded inNotes		
student_id	Chunk 1	SURNAME_FIRSTNAME_<excel_index>, deterministic
status	Chunk 1	One of 6 values, default pending
pptx_path	Chunk 2	Stamped on all students post-generation
last_updated	Chunk 2	ISO-8601, updated on every set_slide_info() call
crop_params	Chunk 4 (planned)	{x, y, w, h, rotation} in original pixel coords
5. Key Methods Reference
MethodLocationPurpose		
replace_slide_image(pptx, slide_idx, shape_id, stream)	SlideUpdater	Single validated PPTX mutation entry point
update_student_slide(student_dict, stream)	SlideUpdater	Wrapper pulling fields from student record
_apply_corrected_image(stream, new_status)	QASuiteFrame	Reusable override orchestrator for all future override mechanisms
get_slide_info(student_id)	MetadataService	Returns {slide_index, pptx_path, last_updated}
set_slide_info(student_id, slide_idx, pptx_path)	MetadataService	Persists mapping + stamps timestamp
get_review_statistics()	MetadataService	Full status breakdown dict for toolbar counters
ensure_student_ids(students)	MetadataService	Idempotent ID assignment, safe to call on restore
_update_review_stats()	QASuiteFrame	Reads disk stats → pushes to toolbar
6. Technical Debt & Future Considerations

Known issue — background thread + Xvfb (non-production): self.after() inside the generation worker thread errors under headless Xvfb when the main loop hasn't started. Not reproducible in real GUI operation. Safe to ignore unless writing automated UI tests — in which case, patch show_info/show_error and drive root.update() in a polling loop.

_on_apply_override is not yet wired through _apply_corrected_image****: The face-click override path still calls slide_updater.reinject_portrait() directly (it needs to crop first, then inject). Once Chunk 3 delivers crop_with_params(), both paths can be unified: crop externally → call _apply_corrected_image(stream). Currently they stay separate to keep Chunk 2 strictly infrastructure-only.

MetadataService.update_student() reads the full list from disk on every call. Acceptable for rosters under ~500 students. For larger rosters, consider an in-memory write-through cache keyed by student_id.

student_id is not yet validated for uniqueness on load. ensure_student_ids() is idempotent but doesn't detect collisions from hand-edited metadata.json. Add a uniqueness assertion if the editor scenario becomes real.

Phase 0 calibration changes are not live-reloaded into a running Phase 2+3 session. SlideUpdater calls cfg.load_layout_config() on every operation, so changes take effect for the next operation — but the current preview does not re-render automatically when Phase 0 is saved. Low priority.