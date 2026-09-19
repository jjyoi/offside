// Optional GIF overrides. Drop a file into src/assets/gifs/ with one of the
// names below and it's picked up automatically — no code changes needed.
// If the file doesn't exist, callers get `null` and should fall back to the
// built-in CSS/SVG animation.
const gifModules = import.meta.glob<{ default: string }>("../assets/gifs/*.{gif,webp,png}", { eager: true });

function resolve(name: string): string | null {
  const entry = Object.entries(gifModules).find(([path]) => path.includes(`/${name}`));
  return entry ? entry[1].default : null;
}

export const VAR_REVIEW_GIF = resolve("var-review.gif");
export const COACH_RUNNING_GIF = resolve("coach-running.gif");
export const RED_CARD_GIF = resolve("red-card.gif");
export const YELLOW_CARD_GIF = resolve("yellow-card.gif");
export const WHISTLE_GIF = resolve("whistle.gif");
