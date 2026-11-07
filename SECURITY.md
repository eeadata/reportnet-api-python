# Security policy

## Reporting a vulnerability

Please do **not** open a public issue for a security problem. Use GitHub's private
reporting instead: on the repository page choose **Security → Report a vulnerability**.
Include what you found, how to reproduce it and which version is affected.

You will get an acknowledgement and a plan for a fix or a reason why none is needed.
Fixes go into the latest release; this is a `0.x` library, so only the latest version
is supported.

## Things worth knowing

- The library does not log credentials or write them to disk (the token is held in
  memory by the client), and a client's `repr` shows the base URL and credential
  scheme only, never the token.
- Responses from Reportnet can contain personal data (for example lead reporters'
  email addresses). Do not paste responses, tokens or API keys into issues.
- Some calls write or delete data. `import_file(replace=True)` needs `confirm=True`,
  but you remain responsible for the dataflow you point the client at.
