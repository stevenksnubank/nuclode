# Distill: Security Hardening Plan for DevTools Lite

> **Source**: /Users/steven.kumarsingh/Desktop/devtools-lite-security-hardening-plan.md
> **Distilled**: 2026-03-23
> **Pass**: 1+2
> **Domain**: Enterprise security engineering / developer tooling governance
> **Compressibility**: Medium

---

## Domain Assessment

This is an internal technical proposal — a pre-RFC design document for deploying security hooks into a developer environment provisioning tool at a fintech (Nubank). The domain is enterprise security tooling, specifically the governance layer around AI-assisted coding tools (Claude Code, Cursor). Structure quality is high: well-sectioned, tables throughout, clear separation of capabilities/rollout/risks.

The document is **medium compressibility**. The hook specifications (Section 2.2) carry dense, precision-dependent detail — specific regex patterns, lifecycle events, decision types — that cannot be losslessly summarized. The strategic framing (Sections 1, 5, 6, 7, 8) compresses well.

---

## Core Claims

### Strategic

1. **DevTools Lite is the natural enforcement point for AI tool security because it is the single provisioning entry point for ~10,000 users.**
   - Confidence: **Strong** — logically sound; if the tool installs everything, it can configure everything.
   - Source: Section 1

2. **Today, DevTools Lite installs Claude Code, Cursor, and MCP servers with zero security enforcement — no hooks, no permission boundaries, no egress control.**
   - Confidence: **Asserted without evidence** — no audit output, settings.json dump, or diff is provided to demonstrate the absence. The claim is plausible given the DevTools Lite codebase (which focuses on install, not config), but the document doesn't prove it.
   - Source: Section 1

3. **The proposed hooks are production-tested, standalone, and require zero additional dependencies beyond what DevTools Lite already installs.**
   - Confidence: **Moderate** — "production-tested" is asserted but not quantified. No metrics on how many sessions the hooks have run through, false positive rates, or incident data are provided. The zero-dependency claim is verifiable from the dependency table (Section 3) and appears accurate.
   - Source: Sections 1, 3

### Technical

4. **Network egress control via allowlist/blocklist with fail-secure default (deny unlisted domains) is sufficient to prevent data exfiltration through Claude Code.**
   - Confidence: **Moderate** — the mechanism is sound for URL-based exfiltration. The document does not address: DNS exfiltration via encoded subdomains, data smuggled in git commit messages to allowed repos, exfiltration via MCP server side-channels, or Claude encoding data in tool outputs that the user then copies elsewhere.
   - Source: Section 2.2 (network-guard.sh)

5. **Regex-based SAST scanning across 6 languages with 37 patterns can meaningfully reduce committed vulnerabilities.**
   - Confidence: **Moderate** — the patterns target well-known, high-confidence anti-patterns (eval, innerHTML, SQL concat). Regex SAST will have both false positives (pattern matches in comments, strings, test fixtures) and false negatives (obfuscated patterns, indirect vulnerability chains). The document acknowledges the comment-skipping heuristic but doesn't quantify coverage or false positive rates.
   - Source: Section 2.2 (sast_gate.py, sast_patterns.py)

6. **13 regex patterns for secret detection are sufficient to catch hardcoded credentials before commit.**
   - Confidence: **Moderate** — covers major cloud providers and common patterns. Does not address: base64-encoded secrets, secrets split across multiple lines, secrets in non-standard formats, or Nubank-internal credential patterns. The document notes it scans staged content (not working tree), which is a correct design choice.
   - Source: Section 2.2 (secrets_scan.py)

7. **The teaching loop design (explain → propose → get agreement) is more valuable than silent auto-fix for non-engineer users.**
   - Confidence: **Weak** — pedagogically reasonable assertion, but no evidence is provided. No user research, A/B test, or reference to learning science literature. This is a design philosophy claim, not a tested hypothesis.
   - Source: Section 2.2 (sast_scan.py)

### Operational

8. **Jamf self-healing (15-30 min policy cycle) combined with file immutability flags provides adequate tamper resistance.**
   - Confidence: **Moderate** — the layered approach is sound. The document honestly acknowledges admin users can circumvent controls. The 15-30 minute gap between tamper and restoration is noted but not analyzed for risk (what damage can occur in that window?).
   - Source: Section 5

9. **A 5-phase rollout over ~5 weeks is feasible and appropriate.**
   - Confidence: **Weak** — no resource estimates, no team capacity assessment, no dependency on other teams (AppSec review, Jamf policy creation, SIEM integration) is scheduled. The timeline is aspirational, not planned.
   - Source: Section 6

---

## Key Evidence

The document is a proposal, not a research paper — it presents a design rather than empirical evidence. Evidence provided:

- **Dependency table** (Section 3): Concrete verification that python3, git, jq, bash are already in the DevTools Lite install chain.
- **Pattern database** (Section 2.2): Specific regex patterns, language coverage, and severity tiers. This is the most evidence-dense part of the document.
- **settings.json fragment** (implied in Section 4): Concrete integration path showing how hooks register.
- **Telemetry schema** (Section 2.3): Concrete JSON event format.

Evidence **not** provided:
- False positive/negative rates from existing deployment
- Performance benchmarks (hook execution times)
- User feedback from existing hook users
- Comparison to alternative approaches (managed-settings, pre-commit frameworks, CI-based scanning)

---

## Methods Summary

This is a design document, not an experimental study. The "method" is:
1. Inventory an existing hook suite (from nuclode workspace)
2. Map each hook to the DevTools Lite packaging system
3. Propose a tamper-resistance layer using Jamf (existing MDM)
4. Propose a phased rollout

No formal threat modeling framework is referenced (STRIDE, PASTA, attack trees). The threat model in Section 5.1 is a flat list of 5 tampering vectors, not a systematic analysis.

---

## Spin Check

The document's framing is generally honest. Notable observations:

1. **"Production-tested"** (Section 1) — this phrase implies broad validation, but the hooks come from a single developer's personal workspace (nuclode). There's a meaningful difference between "I've used these" and "these have been validated across diverse environments." The claim isn't false, but it's more confident than the evidence supports.

2. **"Zero additional dependencies"** — accurate and well-supported by Section 3.

3. **Section 5.3 ("Honest limitations")** — the document explicitly acknowledges that admin users can circumvent controls. This is good practice and unusual for a proposal document. No spin detected here.

4. **Section 2.4 ("broader security entry point")** — the table shows "Full" coverage for Claude Code and Git, "Partial" for Cursor, and "Indirect" for MCP/runtimes. The "Future extensions" column lists aspirational items not included in this proposal. This is honest labeling, but a reader might take the table as suggesting more coverage than actually ships in v1.

5. **Rollout timeline** — presented as 5 weeks with no caveats about team capacity, competing priorities, or external dependencies. This is mildly optimistic framing.

---

## Context & Field Position

**Problem addressed:** AI coding tools (Claude Code, Cursor) are being deployed at enterprise scale (~10K users) without security governance. The tools have broad permissions (file access, shell execution, network requests) and the user base includes non-engineers who may not recognize security risks.

**Prior work / field position:**
- Anthropic's Claude Code has a hook API (PreToolUse/PostToolUse/Stop) and supports managed-settings.json for enterprise policy. This proposal uses the hook API but doesn't address managed settings.
- Nubank already has internal research on hooks vs. CLAUDE.md instructions (nubank/swe-ai repo), concluding hooks provide deterministic enforcement while instructions are advisory.
- Risk Engineering has a `vibe-coding-guardrails` plugin (instruction-based). This proposal is hook-based, which is a stronger enforcement mechanism.
- AppSec has produced a "Vibe Coding Security Risks" document identifying the threat landscape. This proposal addresses a subset of those risks.

**Claimed contribution:** First concrete, deployable security package for DevTools Lite that uses Claude Code's hook API for enforcement rather than relying on instructions or user discipline.

---

## What I Don't Know

### 1. Gaps from this pass

- **How well do the regex patterns actually perform?** The document lists patterns but provides no false positive/negative data. Pass 3 would require reading the actual regex implementations and testing them against representative Nubank codebases (heavy Clojure, some Python/JS).
- **What's in `allowed-domains.txt`?** The blocklist is specified (76 domains). The allowlist is described as "to be curated" — this is the most operationally critical config file and it doesn't exist yet.
- **How does the settings.json merge actually work?** The `index.sh` is pseudocode. The merge logic is non-trivial — DevTools Lite already writes MCP config to settings.json, and appending to JSON arrays requires careful handling. A bad merge could break Claude Code.

### 2. Expertise-dependent

- **Jamf policy design:** The tamper-resistance layer assumes Jamf capabilities (recurring policies, Extension Attributes, Smart Groups) that I cannot evaluate without Jamf administration expertise. Are 15-minute recurring policies feasible at scale? What's the Jamf agent load?
- **macOS security model:** The `chflags uchg` approach assumes macOS file flag behavior. Does SIP (System Integrity Protection) interact with this? Do MDM profiles offer stronger alternatives?
- **Claude Code hook API stability:** The hooks depend on a specific JSON contract (tool_name, tool_input on stdin; permissionDecision in response). Is this API stable across Claude Code versions? Is it documented as a stable interface?

### 3. External dependencies

- **AppSec review:** The rollout plan lists this as a Phase 2 task but doesn't name who, how long, or what the review criteria are.
- **Allowed-domains curation:** Requires input from networking/security teams to identify all legitimate outbound destinations. This could be a multi-week effort for a large org.
- **SIEM pipeline:** Phase 5 depends on Datadog/Splunk integration that isn't designed or resourced.

### 4. Unstated assumptions

- **Claude Code is the primary AI tool risk.** The document focuses heavily on Claude Code hooks but notes Cursor coverage is "partial." If Cursor is equally or more widely used, the security posture has a significant gap.
- **Users don't have admin rights.** Layer 2 (file immutability) only works for non-admin users. The document doesn't state what percentage of the 10K target users have admin rights on their machines.
- **Hook execution order is deterministic.** The settings.json fragment lists multiple PreToolUse hooks. The document assumes they all execute (network-guard before secrets_scan before sast_gate) but doesn't verify that Claude Code guarantees execution order or that a failing hook doesn't skip subsequent hooks.
- **The Claude Code hook API processes stdin/stdout correctly for Python hooks.** The `run_with_profile.py` dispatcher reads stdin and writes to stdout. This assumes Claude Code pipes JSON correctly to Python subprocesses, which may behave differently than bash hooks regarding buffering, encoding, and error handling.

### 5. Missing perspectives

- **User experience impact.** No discussion of how blocking hooks affect user flow. When a commit is blocked, what happens? Does the user see a clear message? Can they easily fix the issue? What's the cognitive load for a non-engineer?
- **Alternative approaches.** No comparison to: (a) Anthropic's managed-settings.json for enterprise policy, (b) standard pre-commit frameworks (pre-commit.com), (c) CI/CD-based scanning (shift-right instead of shift-left), (d) GitHub branch protection rules, (e) Santa (macOS binary authorization already in use at Nubank).
- **Cost of maintenance.** Pattern databases need updating as new vulnerability classes emerge. Who maintains `sast_patterns.py`? What's the update cadence?
- **Non-Claude-Code attack vectors.** A user can bypass all hooks by using the terminal directly (not through Claude Code's Bash tool). The hooks only intercept Claude Code's tool calls, not native shell usage. This is a fundamental limitation not discussed.

---

## Comprehension Dashboard

| Dimension      | Level              | Confidence | Notes |
|----------------|--------------------|------------|-------|
| Factual        | ██████████░░ 10/12 | High       | Document is well-structured; all claims are clearly stated and locatable |
| Methodological | ██████░░░░░░  6/12 | Medium     | Design is coherent but no formal threat model, no empirical validation, pseudocode install logic |
| Contextual     | ████████░░░░  8/12 | Medium     | Good understanding of DevTools Lite ecosystem; field position (hook-based vs instruction-based) is clear; missing comparison to alternatives |
| Applied        | ██████░░░░░░  6/12 | Medium     | Could implement from this doc but key operational details are missing (allowed-domains, merge logic, AppSec process) |
| Critical       | ████░░░░░░░░  4/12 | Low        | Identified several unstated assumptions and missing perspectives but cannot evaluate Jamf specifics, Claude Code API stability, or regex performance without deeper investigation |
