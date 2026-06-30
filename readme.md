# Graduation Slide Automation Suite

A desktop application designed to automate the preparation of graduation presentation slides for commencement exercises.

The system streamlines the complete workflow of organizing student portraits, generating PowerPoint slides, and performing quality assurance on generated outputs.

---

## Features

### Phase 0 - Manual Calibration Engine

* Configure portrait placement using a `layout_config.json` file.
* Define:

  * Width
  * Height
  * Top position
  * Left position
* Configuration can be modified through the GUI or by editing the JSON file directly.

### Phase 1 - Dynamic Ingestor

* Select source and destination folders through a graphical interface.
* Automatically classify student folders based on program codes.
* Organize images into program-specific directories.

Example:

```text
Raw:
JUAN DELA CRUZ_BMMA/

Output:
Bachelor of Multimedia Arts/
└── JUAN DELA CRUZ_BMMA/
```

### Phase 2 & 3 - Live QA Suite

* Generate draft PowerPoint presentations automatically.
* Preview generated slides inside the application.
* Manually correct portrait crops when automatic detection fails.
* Update only affected slides without regenerating the entire presentation.

---

## Architecture

```text
main.py
│
├── modules/
│   ├── calibration.py
│   ├── ingestor.py
│   ├── crop_engine.py
│   ├── ppt_generator.py
│   ├── qa_controller.py
│   └── metadata_manager.py
│
├── config/
│   └── layout_config.json
│
├── data/
│   └── metadata.json
│
└── assets/
```

The application uses:

* `main.py` as the central controller.
* A modular architecture for maintainability.
* `metadata.json` for storing manual overrides and processing state.

---

## Technologies Used

* Python 3.12+
* Tkinter
* Pillow (PIL)
* OpenCV
* python-pptx
* JSON

---

## Installation

Clone the repository:

```bash
git clone <repository-url>
cd graduation-slide-automation-suite
```

Create and activate a virtual environment:

### Windows

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Application

```bash
python main.py
```

---

## Configuration

The portrait layout is controlled through:

```text
config/layout_config.json
```

Example:

```json
{
    "width_cm": 7.5,
    "height_cm": 9.5,
    "top_cm": 3.0,
    "left_cm": 12.0
}
```

---

## Project Goals

* Reduce manual slide preparation time.
* Improve consistency of graduation presentations.
* Minimize repetitive image editing tasks.
* Provide an efficient quality assurance workflow.

---

## Status

🚧 Project currently under active development.