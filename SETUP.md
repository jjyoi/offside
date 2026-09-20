# Offside setup

How to install Offside, connect it to a repo, and use it. Takes about five minutes.

Offside is a `git push` referee. Once a repo is connected, `git push` pauses, opens a review in your browser, and lets the push through or stops it depending on the result.

## 1. What you need

| | Version | Notes |
|---|---|---|
| Python | 3.11 or newer | |
| Node | 20.19+ or 22.12+ | Vite needs this; Node 18 will not work |
| git | 2.37 or newer | Older versions work, but a plain `git push` on a new branch will need `-u` |
| A browser | any | The review opens here |

Works on macOS and Linux. Windows has not been tried; use WSL.

## 2. Install (once)

Pick **uv** or **pip**. Both give you the same thing.

```sh
git clone git@github.com:jjyoi/offside.git
cd offside
```

**With uv**

```sh
(cd backend && uv venv .venv && uv pip install -e . --python .venv/bin/python)
(cd cli     && uv venv .venv && uv pip install -e . --python .venv/bin/python)
(cd frontend && npm install)
```

**With pip**

```sh
(cd backend && python3 -m venv .venv && .venv/bin/pip install -e .)
(cd cli     && python3 -m venv .venv && .venv/bin/pip install -e .)
(cd frontend && npm install)
```

Then put the `offside` command on your PATH (add this line to your shell profile to keep it):

```sh
export PATH="$PWD/cli/.venv/bin:$PATH"
```

Check it worked:

```sh
offside doctor
```

Outside a git repo it will say "this is not a git repository" on the hook line. That is fine for now; you connect a repo in the next step.

## 3. Connect a repo

Go to any repo you want reviewed and run:

```sh
cd /path/to/your/repo
offside connect
```

The first time, it asks how you want to be reviewed:

| Level | What you get |
|---|---|
| **intern** | A gentler review. Small things pass, only serious problems are red cards, and each finding gets a full walkthrough. |
| **mid** | A balanced review with a short explanation of what is wrong and why it matters. |
| **staff** | A strict, design-focused review with one terse line per finding. |

`offside connect` does three things:

1. Installs a `pre-push` hook in the repo.
2. Sets `push.autoSetupRemote`, so a plain `git push` works on a brand-new branch.
3. Keeps any pre-push hook you already had and still runs it first.

You only do this once per clone.

## 4. Use it

```sh
git push
```

That is all. If Offside is not running yet, the push starts it (this takes a few seconds the first time). Then:

1. The review opens in your browser. Step through the diff, the case against it, the evidence and the verdict. Click, or press Enter, to move on.
2. Each finding gets a card and an HP hit. **Next issue** skips ahead whenever you agree.
3. For each finding you can:
   - **Accept fix** to take the suggested fix. You get half the HP back and can continue. The fix is not part of the push, so apply it afterwards. The terminal lists the fixes you accepted.
   - **Contest** to argue the call is wrong. If you win, you get all the HP back. If you lose, you pay a penalty that is bigger the more sure the referee was. Losing always leaves you worse off than accepting the fix.
   - **Concede, no fix** to agree it is wrong and stop the push.
4. Finish with **Continue Push**. The terminal prints `PUSH ALLOWED` or `PUSH BLOCKED` and git carries on or stops.

**A push is blocked when** a red card is still standing (no accepted fix, no won contest), you concede without a fix, or your HP is 0 or below.

Offside keeps running in the background after the push. Stop it any time with `offside down`, or start it ahead of time with `offside up`.

## 5. Change your level

```sh
offside config level staff        # or intern / mid
offside config level              # show the current one
```

You can also click **Settings** in the review page. The change applies to your next review.

## 6. Share it with the team

To ship the hook in the repo so teammates get it too:

```sh
offside connect --shared
git add .githooks && git commit -m "Add Offside pre-push hook"
```

After they pull, each teammate runs `offside connect` once. Git does not run hooks from a repo automatically, so that one step per clone cannot be skipped.

## 7. Use a real model (optional)

By default Offside uses a built-in rule-based referee. It needs no keys and works offline, but it only knows a fixed list of patterns.

To use an OpenAI model instead, create `backend/.env`:

```sh
OPENAI_API_KEY=sk-...
OPENAI_FAST_MODEL_ID=gpt-4o-mini   # optional, this is the default
OPENAI_DEEP_MODEL_ID=gpt-4o        # optional, this is the default
```

Restart Offside (`offside down`, then push again). **Your diffs are sent to OpenAI when this is on.**

## 8. Commands

| Command | What it does |
|---|---|
| `offside connect` | Connect the current repo (hook + plain `git push`) |
| `offside connect --shared` | Same, but commit the hook so teammates get it |
| `offside doctor` | Check the backend, review page, hook and settings |
| `offside up` / `offside down` | Start or stop the backend and review page |
| `offside config level [intern\|mid\|staff]` | Show or change your level |
| `./demo.sh` | Start everything in the foreground with live status; Ctrl-C stops it |

Settings you can change with environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `OFFSIDE_FAIL_OPEN` | `1` | If Offside is down or cannot start, `1` lets the push through (with a loud warning) and `0` blocks it |
| `OFFSIDE_AUTOSTART` | `1` | Set `0` to stop `git push` from starting Offside itself |
| `OFFSIDE_WAIT_TIMEOUT` | `600` | Seconds to wait for a verdict before giving up |
| `OFFSIDE_BACKEND_URL` | `http://localhost:8000` | Where the backend is |
| `OFFSIDE_FRONTEND_URL` | `http://localhost:3000` | Where the review page is |
| `OFFSIDE_HOME` | (found automatically) | Path to this checkout, if auto-start cannot find it |

## 9. Troubleshooting

**The push went through and no review opened.**
Look for a box that says `OFFSIDE IS NOT RUNNING: this push was NOT reviewed`. Offside could not start, and by default a down Offside lets pushes through. Run `offside doctor` to see why. Set `OFFSIDE_FAIL_OPEN=0` if you would rather block pushes when Offside is down.

**`git push` says "no upstream branch".**
The repo was not connected with `offside connect`. Run it, or push once with `git push -u origin <branch>`.

**Nothing happens on push at all.**
Run `offside doctor` in the repo. If the hook is missing, run `offside connect`. If you use `git push --no-verify` the hook is skipped on purpose. If `git config core.hooksPath` points somewhere unexpected (another hook manager), run `offside connect` again to install there.

**"OFFSIDE CANNOT RUN: the Offside CLI moved or was removed".**
You moved or deleted the Offside folder after connecting. Run `offside connect` again in the repo.

**Auto-start says a service did not come up.**
Look at the logs in your temp folder under `offside-demo/` (`backend.log` and `frontend.log`). Common causes: port 8000 or 3000 is taken by something else, `npm install` was not run, or Node is too old (see section 1).

**The browser did not open.**
The review URL is printed in the terminal after `VAR review:`. Open it by hand.

**The push is stuck waiting.**
It is waiting for you to finish the review in the browser. After `OFFSIDE_WAIT_TIMEOUT` seconds (600 by default) it gives up and follows the fail-open setting.

**Port already in use with `./demo.sh`.**
Pick other ports: `BACKEND_PORT=8811 FRONTEND_PORT=3811 ./demo.sh`, then push with `OFFSIDE_BACKEND_URL=http://localhost:8811 OFFSIDE_FRONTEND_URL=http://localhost:3811 git push`.

## 10. Disconnect a repo

```sh
rm .git/hooks/pre-push
mv .git/hooks/pre-push.offside-prev .git/hooks/pre-push   # only if that file exists: it is your original hook
git config --unset push.autoSetupRemote                   # optional
```

For a shared install, also run `git config --unset core.hooksPath` and remove the `.githooks/` folder.

## 11. Run the tests

```sh
(cd backend && .venv/bin/python -m pytest -q)
(cd cli     && .venv/bin/python -m pytest -q)
(cd frontend && npx tsc -b && npm run build)
```

## Limits

- The hook runs on your machine, so `git push --no-verify` skips it. Making the review mandatory for everyone would need a required status check on the server side, which Offside does not do yet.
- Review sessions live in the backend's memory, so restarting Offside forgets them.
- The backend has no login. Run it only on your own machine.
