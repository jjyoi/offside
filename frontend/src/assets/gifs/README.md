# Optional GIF slots

Drop files with these exact names in this folder to replace the built-in
CSS/SVG animations. If a file isn't present, the CSS/SVG fallback is used
automatically — nothing breaks either way.

| Filename            | Used for                                      | Suggested content |
|---------------------|------------------------------------------------|--------------------|
| `var-review.gif`    | VAR intro screen                                | TV-style "VAR REVIEW" broadcast graphic |
| `coach-running.gif` | Shown while a contested appeal is investigating | Coach/manager sprinting onto the pitch to argue a call |
| `red-card.gif`      | Red card reveal                                 | Referee pulling a red card |
| `yellow-card.gif`   | Yellow card reveal                              | Referee pulling a yellow card |
| `whistle.gif`       | Clean / PLAY ON result                          | Referee blowing whistle / play-on gesture |

Then wire them in `src/lib/gifs.ts` — each export currently resolves to
`null` (meaning "use the CSS fallback"); import the file and return its URL
instead once it exists.
