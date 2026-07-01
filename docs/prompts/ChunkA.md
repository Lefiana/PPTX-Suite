Act as the Software Architect for this repository.

Continue from the current conversation.

Do NOT re-review the repository.
Do NOT repeat the architecture.
Continue from the current implementation.

Implement Chunk A only.

==========================================================
Chunk A
PowerPoint-style Rotation Handle
==========================================================

Objective

Replace the existing Rotation slider in the Manual Crop & Tilt Editor with a PowerPoint-style interactive rotation handle.

Target UX: The interaction should closely resemble Microsoft PowerPoint's picture rotation behavior. If users are familiar with rotating images in PowerPoint, the crop editor should feel immediately intuitive, including the position of the handle, cursor behavior, snapping, and visual feedback.

----------------------------------------------------------
Scope
----------------------------------------------------------

Touch only the files required.

Expected files are likely:

- phases/phase23/crop_editor.py

Only modify additional files if absolutely necessary.

Do NOT modify unrelated modules.

----------------------------------------------------------
Requirements
----------------------------------------------------------

Remove the Rotation slider completely.

Instead implement a rotation handle.

The rotation handle should:

• appear above the crop rectangle

• be connected by a thin guide line

• behave similarly to PowerPoint

• be draggable

• rotate around the crop rectangle center

----------------------------------------------------------

Interaction

----------------------------------------------------------

Dragging the rotation handle

- rotates the crop rectangle

- rotates all resize handles

- updates the live preview continuously

- updates the current rotation angle

Display the current angle

Examples

0°

3.2°

-5°

near the rotation handle while dragging.

----------------------------------------------------------

Snapping

----------------------------------------------------------

Snap rotation every 5 degrees.

Examples

0

5

10

15

etc.

Holding Shift disables snapping for free rotation.

----------------------------------------------------------

Double Click

----------------------------------------------------------

Double-clicking the rotation handle

should instantly reset

rotation = 0°

Update preview immediately.

----------------------------------------------------------

Existing Behaviour

----------------------------------------------------------

Keep everything else exactly the same.

The crop rectangle must still support

• moving

• resizing

• locked aspect ratio

• zoom

• apply

• cancel

• reset

Continue using

image_processor.crop_with_params()

Continue using

QASuiteFrame._apply_corrected_image()

Do NOT introduce a second rotation implementation.

The rotation handle must update the same rotation variable already used by crop_with_params().

----------------------------------------------------------

Rendering

----------------------------------------------------------

The crop rectangle should rotate visually.

This includes

- border

- resize handles

- rotation handle

The bounding box should remain mathematically correct.

Do not fake the rotation.

The rectangle itself should actually rotate.

----------------------------------------------------------

Performance

----------------------------------------------------------

Dragging should feel smooth.

Avoid unnecessary redraws.

Only redraw the objects that changed.

Avoid recreating the entire canvas every mouse movement.

----------------------------------------------------------

Backward Compatibility

----------------------------------------------------------

Existing metadata.json files

Existing crop_params

Existing rotation values

must continue working without migration.

----------------------------------------------------------

Testing

----------------------------------------------------------

Compile only touched modules.

Run geometry tests for

- snapping

- free rotation

- reset

- resize after rotation

- move after rotation

Verify crop_with_params() still produces identical output.

----------------------------------------------------------

Output Format

----------------------------------------------------------

Existing file (<50% modified)

→ Return only the modified methods / patch.

New file

→ Return the complete file.

Major refactor (>50%)

→ Return the full file.

Everything else

→ Edit directly and summarize.

Finally provide

• files modified

• affected methods

• testing performed

• backward compatibility

• technical debt discovered

Do not implement any other chunk.