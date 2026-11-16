# Third-party material

This repository's own files are under the [MIT License](LICENSE). It also carries copies of other
projects' files, which stay under their own licenses:

| Path | From | License |
| --- | --- | --- |
| `.claude/skills/openfilm/` | [openfilm/openfilm](https://github.com/openfilm/openfilm) | MIT — [`licenses/OpenFilm-LICENSE.txt`](licenses/OpenFilm-LICENSE.txt) |
| `.claude/skills/hyperframes*/`, `media-use/`, `reverse-any-video/`, `style-sampling/` | [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) | Apache-2.0 — [`licenses/HyperFrames-LICENSE.txt`](licenses/HyperFrames-LICENSE.txt) |
| `edit/projects/hf-demo/` | HyperFrames' `warm-grain` example, as scaffolded by `hyperframes init` | Apache-2.0 |

`edit/tools/openfilm/apply-lan-patch.mjs` modifies an installed copy of OpenFilm at install time; it
contains no OpenFilm code beyond the lines it matches. This project is not affiliated with OpenFilm
or HeyGen.
