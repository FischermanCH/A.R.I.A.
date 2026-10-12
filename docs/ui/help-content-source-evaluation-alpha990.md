# Help content source evaluation (Alpha990)

The in-app help remains sourced from `docs/help/` and `docs/wiki/` rather than
rendering `website/content/<lang>/` directly.

The public website pages and the authenticated application help overlap in
subject, but not in navigation or audience. Website Markdown contains
WordPress-oriented frontmatter and relative website links; the in-app help uses
module-owned document IDs, application routes and operational details that are
not appropriate for the public website. Loading website files directly would
therefore either expose irrelevant metadata or require a second link-rewriting
truth.

For Alpha990 the clean boundary is: public overview and onboarding remain in
`website/content/`; operational, version-matched help remains in `docs/help/`
and `docs/wiki/`. Shared facts must be checked during release review, but the
files are not mechanically duplicated or imported at runtime.
