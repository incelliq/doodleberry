# Research standard and critic loop

Adapted from the bioinformatics.lk film playbook. It applies to every film that makes factual claims; the engine
enforces the process (`research.check`), and agents do the judging.

## Before the storyboard
1. **Treat the brief as leads, not facts.** Its sources and numbers came from a quick sweep.
2. **Read primary sources in full** where they are open. Note the exact figure, table or sentence for each number.
3. **Two independent sources for every number on screen** (paper plus database, or paper plus review). Record a
   `single_source_reason` when only one exists. Prefer the primary source when they disagree, and say why.
4. **Check names, dates and affiliations** on official pages.
5. **Counter-evidence:** a fresh agent (`dbe/critic/counter_evidence.md`) looks only for reasons the main claim is
   wrong, overstated or out of date. Address what it finds in the film or the log.
6. **Original analysis:** real data, its documentation and terms, the access date and version, and a sanity check
   against a published figure. Scripts and cached inputs live in the film folder; charts read their output.
7. **Write it down** in `research_log.md`, with sections Searches, Sources (with a one-line verdict each), Rejected,
   Open questions and Counter-evidence.
8. **Gate:** a fresh fact-check agent (`dbe/critic/fact_gate.md`) reviews `facts.json` against the sources and records
   `ledger.add role=fact_gate verdict=cleared`. Renders refuse to start without it.
9. **Sensitive topics:** if a brief touches a sensitive area, set `brief.sensitive: true` in shots.json. Production then
   waits for a reviewer to record `ledger.add role=safety verdict=cleared`. If a topic is blocked, narrow the brief
   and relaunch rather than forcing it.

10. **Expert review (health, legal, finance):** a brief with `| review | expert (...) |` (written by `plan.brief` for the
   channel's expert fields and keywords) or `shots.json` `brief.review: "expert"` needs, for every fact, what its source
   leaves out (`omits`: e.g. first-line treatments, or "nothing material"), and a qualified reviewer's
   `ledger.add role=expert_review verdict=cleared` (name and qualification in the notes). `research.check` reports it
   pending until then, and the production board refuses approval.
11. **Honest labels:** a fact may carry `label`: "re-analysis", "illustration" or "preliminary". While a line citing it
   plays, the captions show the label in a tag at the top of the text-safe area; a labelled fact no line cites is
   reported.

If the research changes the story, follow the research and say so in the brief.

## facts.json
```json
{"sources": {"nobel": {"url": "https://www.nobelprize.org/..."}, "pmc": {"url": "https://pmc.ncbi.nlm.nih.gov/..."}},
 "facts": [{"id": "F01", "claim": "...", "src": "nobel", "srcs": ["pmc"], "source_sentence": "exact trace from the source",
            "label": "re-analysis | illustration | preliminary (optional)", "single_source_reason": "(optional)"}]}
```
Script lines cite fact ids (`"fact": "F01"` or a list); `"fact": null` marks a line with no claim.

## Critic loop (after the first full render)
1. `critic.pack` builds `build/critic/`: stills every 3 s, contact sheets, transcript with times and fact ids,
   facts.json, the QA and layout report, and a prompt per role.
2. Give each prompt to a **fresh** agent with the packet only (not the builder's notes):
   - **sound-off reader:** what reached them, line by line;
   - **fact checker:** every claim against facts.json and its sources;
   - **director:** hierarchy, pacing, frame, acting, opening.
3. Fix what they find, re-render, and record each verdict with `ledger.add`. Each entry snapshots the QA numbers, so
   `ledger.md` shows before and after. Run at least two rounds.
