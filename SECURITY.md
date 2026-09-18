# Security Policy

## Scope

SAAC-JEPA is research code. It trains, evaluates and analyses models locally
against data you supply. There is no network service, no authentication
surface and no deployed component, so most classes of vulnerability do not
apply to this repository.

What does apply:

- **Checkpoints are executable code.** `src/cncjepa/checkpoint.py` and several
  scripts under `scripts/` call `torch.load(..., weights_only=False)`, which
  unpickles arbitrary Python objects. Load only checkpoints you produced
  yourself or otherwise trust: opening an untrusted `.pt` file is equivalent
  to running an untrusted script.
- **Configs are executed as configuration, not sandboxed.** Files under
  `configs/` select code paths and file system locations. Treat a config from
  an untrusted source the same way you would treat a shell script.
- **Dependency vulnerabilities** reachable from the versions pinned in
  `requirements.txt` and `uv.lock`.

## Supported Versions

The project is pre-release: `CITATION.cff` declares `0.1.0` and there are no
tagged releases. Only the current `main` branch receives fixes. There are no
maintained older lines, and no backports.

## Reporting a Vulnerability

Report privately through GitHub, under **Security → Advisories → Report a
vulnerability** on this repository. Please do not open a public issue for a
security report, and do not use the Code of Conduct contact route, which is
public.

If private reporting is unavailable to you, open a public issue that says only
that you have a security report and asks for a private channel, without any
detail about the issue itself.

What to expect:

- An acknowledgement within 7 days.
- If the report is accepted, the fix lands on `main` and is recorded under a
  `Security` heading in `CHANGELOG.md`. You are credited in that entry unless
  you ask not to be.
- If the report is declined — most often because it describes intended
  behaviour of local research code, such as the checkpoint unpickling noted
  above — you get the reasoning in the same thread.
