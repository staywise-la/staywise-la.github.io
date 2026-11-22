# How we work together

A step-by-step guide for the StayWise LA team: get the code, get the data, make changes, and send them for review.

**Short version:**
- Never push to `main`. Work on a branch.
- Open a Pull Request (PR). Joey reviews and approves it.
- After approval, the PR is merged.
- Data stays on Google Drive, never in git.

---

## 1. One-time setup

### 1.1 Accounts and tools

- [ ] **GitHub:** accept the invite to the `staywise-la` organization (check your email or https://github.com/orgs/staywise-la/invitation).
- [ ] **Git:**
  - Mac: `xcode-select --install` or `brew install git`
  - Windows: https://git-scm.com
- [ ] **VS Code** (recommended).
- [ ] **Python 3.10 or newer.**
- [ ] **Git identity:** tell git who you are. Use the email on your GitHub account, so your commits show your name:
  ```bash
  git config --global user.name "Your Name"
  git config --global user.email "you@example.com"
  ```

### 1.2 Get the code

```bash
git clone https://github.com/staywise-la/staywise-la.github.io.git
cd staywise-la.github.io
```

### 1.3 Set up Python (one environment for this project)

Use Python 3.10 or newer. The example below uses 3.11.

```bash
python3.11 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-core.txt   # pandas, pyarrow, scikit-learn, ...
pip install -e .                   # makes `import airbnb` work everywhere
nbstripout --install               # removes notebook outputs before each commit
```

- **Model work:** if your module needs the deep-learning packages (`torch`, `sentence-transformers`, `lightgbm`, ...), also run `pip install -r requirements-ml.txt`. It is a few GB.
- **VS Code:** `Cmd+Shift+P` → "Python: Select Interpreter" → pick `.venv`.
- **Every new terminal:** run `source .venv/bin/activate` first.

### 1.4 Get the data from Google Drive

**Quickest:** download `data/processed/` (cleaned Parquet tables) and load them with `load_processed("listings")`. You only need `data/raw/` if you want to re-run the cleaning yourself (`python -m airbnb.clean`).


1. **Open the shared folder:** use the team Google Drive link (pinned in our group chat).
2. **Download the `data` folder:** it matches the `data/` folder in the repo, so copy its contents into your local `data/`, keeping the same structure:
   ```
   staywise-la.github.io/
   └── data/
       ├── raw/
       │   ├── 2026-09-14/   listings.csv.gz  reviews.csv.gz  calendar.csv.gz  neighbourhoods.geojson
       │   └── <other quarters>/   listings.csv.gz ...
       ├── interim/
       └── processed/
   ```
3. **Keep `.csv.gz` compressed:** the code reads `.csv.gz` directly. If your Mac unzipped them, compress them back with `gzip listings.csv`.
4. **Check that it works:**
   ```bash
   python -c "from airbnb.load import load_listings; print(load_listings('latest').shape)"
   ```
   You should see about `(43781, 95)`.

---

## 2. Every time you work

### Step 1: start from the latest `main`

```bash
git checkout main
git pull
```

### Step 2: create your own branch

Branch name: `<module>/<short-topic>`. Examples:

```bash
git checkout -b price/lasso-baseline
git checkout -b search/bm25
git checkout -b web/map-tab
```

### Step 3: make your changes

- Shared code goes in `src/airbnb/`.
- Module work goes in `modules/<your module>/`.
- Website files go in `web/`.

### Step 4: check what you are about to commit

```bash
git status
```

Look at the list. If you see data, model files, `.env` or `.DS_Store`, **stop** (see section 4).

### Step 5: commit

```bash
git add <files>            # or: git add .  (only after checking git status)
git commit -m "price: add Lasso baseline with grouped CV"
```

- **Commit messages:** start with the module, then say what changed.
- **Size:** keep commits small; one idea per commit.

### Step 6: push your branch

```bash
git push -u origin price/lasso-baseline
```

### Step 7: open a Pull Request

1. Go to https://github.com/staywise-la/staywise-la.github.io. GitHub shows a **"Compare & pull request"** button.
2. Fill in the PR template:
   - what you changed
   - which module it is
   - the checklist
3. Click **Create pull request**. Joey is added as reviewer automatically.

### Step 8: review

- **Joey reviews:**
  - If changes are requested, fix them on the same branch, then `git commit` and `git push` again. The PR updates by itself.
  - Once approved, the PR is merged into `main`.
- **After the merge:**
  - Click **Delete branch** on GitHub.
  - Back on your computer, run `git checkout main && git pull`.

---

## 3. What goes into git (and what does not)

| ✅ Commit these | ❌ Never commit these |
|---|---|
| Python code (`.py`) | Raw or processed data (`.csv`, `.csv.gz`, `.parquet`, `.json` in `data/`) |
| Notebooks (`.ipynb`) with outputs cleared | Model files (`.pkl`, `.pt`, `.joblib`, `.onnx`) |
| README / docs (`.md`) | Downloaded photos |
| Small figures for the report (`reports/figures/*.png`) | `.env`, API keys, tokens, passwords |
| Small summary tables (`reports/*.csv`) | `.DS_Store`, `.venv/`, `__pycache__/`, `.ipynb_checkpoints/` |
| Small website data in `web/data/` (under ~20 MB each) | Anything over ~20 MB |

- **`.gitignore` already blocks most of the "never" list.** If something should be ignored but is not, ask Joey to add it to `.gitignore` in a PR. Do not delete rules from it.
- **Big files you want to share go on Google Drive:**
  - outputs and embeddings go in `data/processed/<module>/`
  - tell the team in the chat

---

## 4. Something went wrong?

- **`git status` shows a data file:**
  - It is not committed yet, so just do not `git add` it.
  - Ask Joey to add a rule to `.gitignore`.
- **You committed a data file but have not pushed:**
  ```bash
  git reset --soft HEAD~1      # undo the last commit, keep your changes
  ```
- **You pushed a data file or a key:**
  - Tell Joey right away.
  - If it is a key, revoke it immediately. Deleting the file is not enough.
- **You see a merge conflict:**
  ```bash
  git checkout main && git pull
  git checkout <your-branch>
  git merge main               # fix the conflicted files, then:
  git add <fixed files> && git commit && git push
  ```
- **`.DS_Store` shows up on Mac:** it is already ignored. If it was added before, run `git rm --cached .DS_Store`.

---

## 5. Asking an AI assistant (Claude Code, Copilot, etc.) to help

You can let an AI do the git steps. Give it clear rules. Copy and adapt these prompts.

**Set up the repo and data:**
> Clone https://github.com/staywise-la/staywise-la.github.io.git, create a Python venv, install requirements.txt and `pip install -e .`, and run `nbstripout --install`. Then check that `data/raw/` has one folder per quarter with listings.csv.gz (and reviews/calendar/geojson in the latest one), and run `load_listings('latest')` to confirm it loads.

**Start a task:**
> Switch to main, pull the latest changes, and create a new branch called `price/lasso-baseline`.

**Before committing:**
> Run git status and git check-ignore. Make sure no files under data/, no .csv/.gz/.parquet, no model files, no .env and no .DS_Store will be committed. List exactly which files will be committed and wait for my OK.

**Commit and push:**
> Commit only the files we just reviewed with the message "price: add Lasso baseline with grouped CV", push this branch, and give me the link to open a pull request into main. Do not push to main.

**Rules to tell the AI every time:**
- Never push to `main`; always use a branch and a PR.
- Never commit anything in `data/`, model files, photos or secrets.
- Do not edit or remove rules in `.gitignore` without asking.
- Load data only through `airbnb.load`.
- Show me the file list before every commit.

---

## 6. Team conventions

- **Notebooks:**
  - Name them `NN_initials_topic.ipynb`.
  - Move reusable code into `.py` files.
- **Random seed:** use `airbnb.config.RANDOM_SEED` (6740).
- **Results:** report numbers through `airbnb.evaluate`, with a 95% confidence interval.
- **No leakage:**
  - Search must not index the amenity list it is tested on.
  - Price uses neighbourhood-grouped CV.
  - Fit scalers on training data only.
- **Ask early:** if you are unsure where something goes, ask in the group chat before committing.
