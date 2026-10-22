# Demo guide

## The day before (about 20-30 minutes, mostly waiting)

1. Install **Python 3.11 or 3.12** from python.org. On Windows, tick "Add python.exe to PATH".
2. Get a free API key from the Groq console (console.groq.com). Don't paste it into chat or code.
3. Unzip the project and **double-click `run_demo.bat`** (Windows), or run `bash run_demo.sh` (Mac/Linux).
   - The first run installs packages (several minutes) and asks for your Groq key once, saving it to
     `.streamlit/secrets.toml`. Press Enter to skip if you don't have it yet; retrieval still works.
   - It then builds the index, which downloads the embedding model (~90 MB). Use good Wi-Fi.
   - The app opens in your browser.
4. Click each example question once and check you get an answer. **Do this before the demo, not in
   front of your teacher.** Later runs start in seconds.

The knowledge base is the course slides plus chapters 1-18 of the textbook (Silberschatz, Galvin,
Gagne, *Operating System Concepts*, 10th ed., minus chapter 19), split into topic folders under
`data/raw/course/`. The 43 Linux man pages the project started with were moved to
`data/excluded/man/` (licenses in `data/LICENSES/`); move them back into `data/raw/open/` and
rebuild if you want them again.

## Adding more material (5 minutes)

1. Copy slide decks or PDFs into topic folders, for example `data/raw/course/deadlocks/module3.pptx`.
2. Rebuild the index (Dataset tab locally, or `python -m bootup.build`).
3. Add one or two questions about the new material to `DEMO_QUESTIONS` in `bootup/config.py`, and
   check they get answered from it.

## The demo (5-7 minutes)

1. **Ask tab.** Click "What are the four necessary conditions for a deadlock?". Point out the answer
   cites [1], [2] and that the Sources panel shows the exact slide or page for each, with its rank in
   each method. Earlier questions move to the **History** tab.
2. **Grounded vs plain.** Turn on "Compare with plain LLM" and ask
   "What is thrashing and how does the working-set model prevent it?". The plain answer may
   well be correct too. The point is that BootUp's answer is tied to a source you can check, and
   stays within your material. Don't claim the plain answer is wrong unless it actually is.
3. **Compare retrieval tab.** Try a keyword-heavy question such as "Bakery algorithm ticket
   number" or "SSTF starvation". Show how dense, BM25 and hybrid rank passages differently, and
   which passages they share. This is the core idea of the project.
4. **Dataset tab.** Real counts: files, chunks per source type and topic. Browse the chunks of one
   of your slide decks to show how slides were split.
5. **Evaluation tab.** If you haven't run the evaluation, say so: the script is built and tested,
   and running it on a labelled question set is the next step. Don't present numbers you don't have.

## Questions you may get, and honest answers

- **How is this different from ChatGPT with my notes uploaded?** It does a similar job. What I built
  lets me control and inspect retrieval, see which source each answer used, and measure whether
  hybrid retrieval beats either method alone. It's about building and evaluating the pipeline,
  not claiming it beats ChatGPT.
- **Why hybrid retrieval?** Embeddings match meaning; BM25 matches exact terms like `Bakery` or
  `SSTF`. Reciprocal Rank Fusion merges the two rankings without having to compare their scores.
- **Where does the data come from?** The course slides and the course textbook (chapters 1-18).
  Both are copyrighted course material: the public site is behind an access code and the index is
  kept in a private dataset.
- **Did you evaluate it?** Only say yes if you ran `python -m bootup.evaluate` on your own
  labelled questions and the Evaluation tab shows a run without the "NOT reportable" warning.
- **What if the answer isn't in the material?** The model is told to say so instead of guessing.
  Test a question outside the material beforehand so you know how it behaves; it's an
  instruction, not a guarantee.
- **Why not fine-tuning?** RAG needs no GPU or training data, and the knowledge can be updated by
  adding a file and rebuilding the index.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Python was not found" | Reinstall Python and tick "Add python.exe to PATH", then reopen the folder |
| Package install fails | Use Python 3.11 or 3.12; newer versions may not have all packages yet |
| Want to re-run the install | Delete the `.venv` folder and run the launcher again |
| Model download is slow or fails | Needs internet to huggingface.co on the first build; try other Wi-Fi |
| "GROQ_API_KEY is not set" | Delete `.streamlit/secrets.toml` and rerun the launcher to enter it again |
| LLM error mentioning the model name | Groq may have retired the model. Set another model id from the Groq console in `LLM_MODEL` in `bootup/config.py` |
| Changed files but answers didn't change | Dataset tab, click **Build index** |
| "Index was built with ... but the query embedder is ..." | You changed the embedding model: click **Build index** |
