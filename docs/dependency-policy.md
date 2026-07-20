# Dependency policy

ContractDelta uses current stable dependencies where they are compatible with the supported
runtimes and build tooling. Weekly Dependabot checks cover Python, npm, and GitHub Actions.

## Runtime choices

- Python 3.14 is used in automation. Python 3.12 remains the compatibility floor so the
  command-line pipeline can run on widely available installations.
- Node.js 24 is the current production LTS line. Node.js 26 is a Current release and is not
  used for deployment until it reaches LTS.
- pip 26 and npm 12 are installed explicitly in automation; the npm version is also recorded
  in `package.json`.

## Compatibility constraints

- TypeScript 6.0.3 is retained because the current stable `@astrojs/check` peer range supports
  TypeScript 5 and 6, but not TypeScript 7. Dependabot ignores TypeScript major-version
  updates until the checker declares support for the next major; minor and patch updates
  remain enabled.
- Python and npm dependencies use upper major-version bounds where a future breaking release
  should be reviewed before adoption.
- npm install scripts are denied by default. The versioned `esbuild` installer required by
  Astro is the only package script approved in `package.json`; the optional `fsevents`
  installer is explicitly denied.
- Workflow actions are pinned to the immutable commit for their current stable release. The
  adjacent version comment allows Dependabot to keep the pins current.

Dependency updates must pass linting, tests, vulnerability audits, the static build, and a
browser check before they are merged.
