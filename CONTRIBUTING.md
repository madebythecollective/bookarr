# Contributing to Bookarr

Thanks for your interest in contributing to Bookarr. Whether you're reporting a bug, suggesting a feature, or submitting code, your help is welcome.

## Reporting bugs

Found something broken? [Open a bug report](https://github.com/madebythecollective/bookarr/issues/new?template=bug_report.yml). Include:

- Your Bookarr version (shown in the sidebar and About page)
- How you installed Bookarr (installer, Docker, or from source)
- Steps to reproduce the issue
- Any relevant log output from `bookarr.log`

**Do not include API keys, passwords, or other credentials in your report.**

## Suggesting features

Have an idea? [Open a feature request](https://github.com/madebythecollective/bookarr/issues/new?template=feature_request.yml). Describe what you'd like, what problem it solves, and any alternatives you've considered.

## Contributing code

Pull requests are welcome. Here's how to get started:

### Setup

1. Fork the repository.
2. Clone your fork:

```bash
git clone https://github.com/YOUR-USERNAME/bookarr.git
cd bookarr
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a branch for your changes:

```bash
git checkout -b your-feature-name
```

### Architecture overview

Bookarr is intentionally simple:

- **`bookarr.py`** — The entire backend. All server logic, API endpoints, database access, search engine, and download management in one file.
- **`templates/index.html`** — The entire frontend. A single-page application with inline CSS and JavaScript.
- **SQLite database** — All state stored in `bookarr.db`.
- **No frameworks** — stdlib HTTP server, raw SQL, vanilla JavaScript.

This is by design. The goal is a single-file application that anyone can read, understand, and modify without learning a framework.

### Guidelines

- **Keep it simple.** Bookarr's strength is its simplicity. Think twice before adding dependencies or abstractions.
- **One file stays one file.** Don't split `bookarr.py` into modules. Don't add a JavaScript build step.
- **Test your changes.** Start Bookarr, click through the UI, verify your feature works and nothing else broke.
- **Match the style.** Look at the existing code and follow the same patterns. Consistency matters more than personal preference.
- **Small PRs are better.** A focused PR that does one thing well is easier to review than a large PR that does many things.

### What makes a good PR

- Solves a real problem or adds a requested feature.
- Includes a clear description of what changed and why.
- Doesn't break existing functionality.
- Follows the existing code style.
- Doesn't add unnecessary dependencies.

### Areas where help is especially welcome

- **Additional notification providers** — Discord webhooks, Telegram, Gotify, etc.
- **Download client support** — SABnzbd, Deluge, rTorrent, etc.
- **Search improvements** — Better scoring heuristics, new search strategies.
- **Accessibility** — Making the web UI more accessible.
- **Documentation** — Fixing errors, adding examples, improving clarity.
- **Bug fixes** — Always welcome.

### Submitting your PR

1. Push your branch to your fork.
2. Open a pull request against `main`.
3. Describe what you changed and why.
4. Link any related issues.

We'll review your PR and provide feedback. Don't be discouraged if we ask for changes — it's part of the process and helps keep the project consistent.

## Code of conduct

Be respectful and constructive. We're all here because we like books and automation. Harassment, discrimination, and unconstructive criticism have no place in this project.

## Questions?

If you're unsure about something, open an issue and ask. We'd rather help you get started than miss out on a contribution.
