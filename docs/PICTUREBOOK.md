# Picture-book look

`config.yaml → look: picturebook` turns every video into a children's storybook, for free and offline.

| Part | What happens | Where |
|---|---|---|
| Pictures | The AI is asked for crayon picture-book art (`picturebook_art_style`) | `config.yaml` |
| Page | Each picture is redrawn as wax crayon on warm paper: flat bright colours, back-and-forth hatching that overshoots, indigo outlines (never black), embossed paper grain | `src/picturebook.py` |
| Line boil | 3 redrawn versions of every page, stepped at 12 fps like hand animation | `stylize()` + `video._pb_scene` |
| Camera | Slow, calm drift (dance mode: the page hops on the beat) | `video._pb_scene` |
| Transitions | A paper page turn with the back of the page and its shadow | `video._turn_frame` |
| Words | Handwriting (Patrick Hand) for English/Spanish on a paper patch; sung words turn coral; the title is written letter by letter. Other scripts keep their Noto font so they shape correctly | `video._write_ass_picturebook` |
| Level 2 clips | Animated GPU clips are stepped to 12 fps and printed onto paper | `video._pb_scene` |
| Shorts | The page sits on a sheet of paper instead of a blurred copy | `video._pb_scene` |

Cost: ₹0. Rendering takes about twice as long as `classic` (the crayon grain is a lot of fine detail); the final bitrate is capped at 8 Mbps.

Credits: the look follows the techniques described in the MIT-licensed [lemo-opuscar](https://github.com/lemomo-ai/lemo-opuscar) crayon-book style guide (no code or assets copied). Patrick Hand font © its authors, SIL Open Font License (`assets/handfont/OFL.txt`).

Switch back any time with `look: classic`.
