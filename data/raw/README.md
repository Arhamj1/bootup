# Put your material here

The folder layout tells BootUp what each file is:

```
data/raw/
  course/                      <- your course material
    deadlocks/                 <- optional topic sub-folder (used as the topic tag)
      module3_slides.pptx
      textbook_ch7.pdf
    scheduling/
      module2_slides.pptx
    lab_manual.pdf             <- no sub-folder: topic = "general"
  open/                        <- open resources
    ostep/
      cpu-sched.pdf            <- OSTEP chapters (topic = "ostep")
    man/                       <- Linux man pages, one folder per topic (moved out to data/excluded/man)
      processes/fork.2.txt     <- topic = "processes"
      scheduling/sched.7.txt
  qa_bank/
    qa.json                    <- your hand-written question/answer pairs (format below)
```

The topic tag is the deepest folder name that isn't `course`, `open`, `qa_bank` or `man`.

Supported: `.pdf`, `.pptx`, `.docx`, `.txt`, `.md`, and `.json` (only inside `qa_bank/`).
Scanned PDFs have no text layer; BootUp reports them as skipped instead of indexing nothing.

`qa_bank/qa.json` format:

```json
[
  {"question": "State the four necessary conditions for deadlock.",
   "answer": "Mutual exclusion, hold and wait, no preemption, circular wait.",
   "topic": "deadlocks", "exam": "CAT-2", "year": "2024"}
]
```

Keep evaluation questions out of the Q&A bank. They must stay out of the index
(the evaluator warns if it finds one). Start with 2-3 topics, not everything.
