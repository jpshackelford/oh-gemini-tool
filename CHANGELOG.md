# Changelog

## 0.1.0 (2026-10-19)


### Features

* initial release of oh-gemini-tool ([f7cc044](https://github.com/jpshackelford/oh-gemini-tool/commit/f7cc044988912d41578b83298ec6b8afb8acbc11))


### Documentation

* add the ACP path for Gemini and link it from the README ([cd09615](https://github.com/jpshackelford/oh-gemini-tool/commit/cd09615003fb3089b34001bd57bc8bbc1a11707a))
* correct [#4646](https://github.com/jpshackelford/oh-gemini-tool/issues/4646) framing and add the auth-precedence collision ([05356b7](https://github.com/jpshackelford/oh-gemini-tool/commit/05356b7f7bc769823b8168fb14fb90ab3c10d288))
* correct the artifact-size figures and record standalone operation ([e7be150](https://github.com/jpshackelford/oh-gemini-tool/commit/e7be150866d300b5abb74026156ff8356ba7025c))
* record that the Antigravity ACP server is a closed binary ([e7b7581](https://github.com/jpshackelford/oh-gemini-tool/commit/e7b7581f1e4ddd4168043c3a24e0127fb3560406))
* restructure around account type, add the personal-account tutorial ([dd1c8a0](https://github.com/jpshackelford/oh-gemini-tool/commit/dd1c8a0647aa8f9f00197249cc985c2e07296b85))
* separate baking a binary into an image from fetching it at runtime ([cfd5346](https://github.com/jpshackelford/oh-gemini-tool/commit/cfd53462792002dd2059dd27b0fb88fd4ac949c4))
* separate the escape hatch from first-class support ([8c41b86](https://github.com/jpshackelford/oh-gemini-tool/commit/8c41b869c37d602e36f1db9978ee9ee0f7afaf91))

## 0.1.0 (Initial Release)

### Features

* Initial release of oh-gemini-tool
* `gemini_delegate` OpenHands tool for delegating work to the Antigravity CLI
* Dependency-free `agy` client (command construction, execution, envelope parsing)
* Session continuity across delegations via explicit conversation ids
* Model tier selection (`flash_lite`, `flash`, `pro`)
* Configurable per-call timeout
