# Salt's Site

The personal site for Salt & Vi, hosted on GitHub Pages at [my-music.site](https://my-music.site). It includes a quick-access hub, a few small game tools, a music ratings dashboard, a live multiplayer quiz, and the site's legal pages.

## Pages

| Page | Description |
| --- | --- |
| `index.html` | Quick-access hub linking to the other pages. |
| `calculator.html` | RPM and damage calculator with tabs for damage, RPM, and roll. |
| `talents.html` | Talent picker, linked from the calculator. |
| `autocalc.html` | Weapon stat parser that recalculates RPM. |
| `gods.html`, `legacygods.html` | Random character picker. |
| `gallery.html`, `market.html`, `inventory.html` | Item grids with sorting, search, and a lightbox. |
| `music.html` | Music ratings dashboard (see below). |
| `ToS.html`, `pp.html` | Terms of Service and privacy policy. |

The static pages are self-contained HTML with a shared `style.css`. There's no build step: the folder can be served as-is.

## Game tools

- **Calculator.** Computes damage and RPM from base values, stat and talent percentages, and a roll. Results update as you type.
- **Talents.** A dropdown for choosing a talent, showing the selected and next talent.
- **Weapon stat parser.** Reads weapon stats and talents, then recalculates RPM with the calculator's formulas.
- **Random character picker.** Spins through a list and stops on one.
- **Item grids.** Load item data from a remote source and sort, search, and preview items in a lightbox. Requests go through a public CORS proxy because the source doesn't allow direct browser access.

## Music ratings (`music.html`)

A dashboard for songs rated in Spotify. A Spicetify extension (see the `spicetify-salt-music` repository) exports ratings as JSON, and this page displays them.

### Data sources

1. **GitHub Gist (primary).** The page fetches the ratings file from a Gist and checks for updates every 30 seconds while the tab is open. When newer data appears, a Refresh button lets you load it without losing your place.
2. **`ratings-export.json` (fallback).** Used when the Gist can't be reached.
3. **Manual import.** Choose a JSON file or drag one onto the page. Imported data is never replaced automatically.

The export is an array of rating groups from 0 to 5 in half-star steps. Each group lists its tracks with Spotify URIs, artist, album, and optional release date. Rated playlists go in a top-level `playlists` array.

### Views

- **Home.** Totals, a "Featured today" section, top artists (weighted or plain average), an all-artists grid, and a decade chart.
- **Artist.** A rating breakdown, albums with at least a set number of songs, and a filterable song list.
- **Top Songs.** A carousel of artists above a grid of songs rated 4 or higher.
- **Recently Rated.** Songs in the order they were rated, when the export includes dates.
- **Playlists.** Playlists rated as a whole, with the average of their rated songs.
- **Request.** Visitors can submit a Spotify track, album, or playlist link. Requests that are already in the library or marked rated are hidden.
- **Search.** Combined artist and song suggestions with keyboard navigation.

### Configuration

Near the top of the script in `music.html`, set:

- `RATINGS_GIST`: the Gist ID and filename.
- `GOOGLE_FORM`: the form URL and the entry ID for the link field.
- `GOOGLE_SHEET`: the Sheet ID and tab ID. The Sheet must be shared as "Anyone with the link can view."

## Quiz app (`quiz/`)

A live multiplayer quiz. The host creates a session, adds image questions, and runs the game. Players join with a session code, submit answers, and follow the scores.

- **Stack:** React 18, TypeScript, Vite, React Router, Tailwind CSS, and Supabase (database, realtime updates, and edge functions).
- **Routes:** `/` (landing), `/host/auth` (host sign-in), `/host/dashboard` (run the quiz), and `/player` (join and answer).

To run locally:

```bash
cd quiz
pnpm install   # or npm install
pnpm dev       # start the dev server
pnpm build     # build to quiz/dist
```

Question images must be hosted on imgur.com. The built app is committed in `quiz/dist/`, so rebuild it after changing the source.

## Legal

`ToS.html` and `pp.html` contain the Terms of Service and privacy policy.

## Related repositories

- [`spicetify-salt-music`](https://github.com/BrandonHfx/spicetify-salt-music): the Spicetify extension that exports ratings for the music page.
- `ImgurDownloader`, `Bingo`, and `WebM-Maker-Thing-Idk`: small utilities.

Made by Salt & Vi.
