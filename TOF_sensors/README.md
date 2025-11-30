# Description

Development of a Makefile capable of managing the entire process of compiling and uploading (both in BOOTSEL mode and through the serial port) an Arduino IDE project.
In this example, the code related to the PicoLowLevel board is used, but the same Makefile can easily be adapted to compile any other `.ino` sketch.

# Important note

The name of the main folder must be identical to the name of the main `.ino` file (top header) that you want to compile, and the Makefile must be located in the same folder as the main `.ino` file (top header).
Furthermore, the project structure must follow the format below:

```bash
my_project/              ← main folder (SKETCH_PATH)
├── my_project.ino       ← main file
├── include/             ← optional header files (.h)
├── lib/                 ← optional custom libraries
│   ├── libA/
│   │   └── src/
│   │       ├── file.cpp
│   │       └── file.h
│   └── libB/
│       └── src/
│           ├── file.cpp
│           └── file.h
├── Makefile             ← this file
└── build/               ← (automatically created)
```

