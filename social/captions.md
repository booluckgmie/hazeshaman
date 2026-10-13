# Social media kit

Ready-to-post copy for **Hazeshaman**. Replace `{URL}` with your deployed link and refresh the
snapshot numbers before posting (they come from `docs/howto/snapshot.json`, taken
**13 Oct 2026, 11 PM MYT** from the hourly DOE API). Regenerate the images with `npm run guide`.

Images (all in `docs/howto/`):

| Use | File |
|---|---|
| Link preview / X / LinkedIn single image | `social-card.png` (1200x630) |
| Instagram / Facebook / Threads square | `social-square.png` (1080x1080) |
| LinkedIn **document carousel** (upload as a document) | `hazeshaman-guide.pdf` (cover + 7 steps) |
| Individual how-to images | `01-tour.png` ... `09-mobile.png` |

**Always keep the disclaimer:** these are model estimates, not an official decision.

---

## LinkedIn (English) - post with `hazeshaman-guide.pdf` as a document

> Haze doesn't wait for the 5:45 PM announcement.
>
> In Malaysia the public air-quality (API/IPU) data only shows the **last 24 hours**. There is no official archive, so nobody can look back and ask "how did haze really behave before schools closed?"
>
> So I rebuilt that history: hourly readings from DOE stations since 2017 (68 stations today), cleaned of "future" hours and bad values, and now saved every hour so it can't be lost again. (One 8-month gap, Nov 2024 to Jun 2025, could not be recovered.)
>
> On top of it, **Hazeshaman** shows:
> 🌫️ the air right now, by state (API bands)
> 📊 the chance schools must close tomorrow morning (KPM's rule: API above 180, or above 150 for 3 days)
> ⏰ the best time to announce - it depends on how costly a late call is
> 🏫 the schools, students and teachers affected (MOE data via OpenDOSM)
>
> Snapshot, 13 Oct 11 PM: 27 of 68 stations above API 100. 13 flagged for tomorrow, in 5 states with about 3,200 schools - roughly 2,600 schools likely affected (closure chance × schools in each state).
>
> Model estimates - not an official decision. Swipe for a 7-step guide. Link in the comments 👇
>
> #Malaysia #Haze #AirQuality #OpenData #DataScience #Education #PublicSector #DataForGood

First comment: `Try it: {URL}  ·  How to use: {URL}/guide`

---

## X / Twitter (thread, each post under 280 characters)

1. `Haze doesn't wait for the 5:45 PM school announcement. 🌫️ Public Malaysian API data shows only the last 24 h - no archive. So I rebuilt it - plus a live dashboard: Hazeshaman. {URL} [social-card.png]`
2. `What it shows: ▸ the air now by state ▸ chance schools must close tomorrow (API>180, or >150 for 3 days) ▸ best time to announce ▸ schools, students and teachers affected [06-announcement-time.png]`
3. `13 Oct, 11 PM: 27/68 stations above API 100; 13 flagged for tomorrow, in 5 states with ~3,200 schools (≈2,600 likely affected). Model estimates only - confirm with official APIMS/KPM.`
4. `7-step guide: {URL}/guide  ·  Built on DOE hourly API + MOE/OpenDOSM school data. #Malaysia #Haze #OpenData`

---

## Facebook / Instagram caption (English)

```
🌫️ Haze doesn't wait for the school announcement.

Malaysia's public air-quality data only keeps the last 24 hours, so I rebuilt the history - DOE stations, every hour since 2017 - and added a live dashboard on top:

✅ air quality now, by state
✅ chance schools must close tomorrow morning
✅ best time to announce
✅ schools, students and teachers affected

13 Oct, 11 PM: 27 of 68 stations above API 100 • 13 flagged for tomorrow.
Model estimate only - always follow official APIMS, MetMalaysia and KPM announcements.

Link in bio / comments 👆
#haze #jerebu #Malaysia #airquality #opendata #sekolah
```

## Bahasa Malaysia (Facebook / Threads / LinkedIn)

```
🌫️ Jerebu tidak menunggu pengumuman jam 5.45 petang.

Data API/IPU awam di Malaysia hanya menunjukkan 24 jam terakhir - tiada arkib rasmi. Jadi saya bina satu: bacaan setiap jam daripada stesen JAS sejak 2017 (68 stesen kini), dibersihkan dan disimpan. (Satu jurang 8 bulan, Nov 2024 hingga Jun 2025, tidak dapat dipulihkan.)

Hazeshaman memaparkan:
🌫️ keadaan udara sekarang mengikut negeri
📊 kebarangkalian sekolah perlu ditutup esok pagi (API melebihi 180, atau melebihi 150 selama 3 hari)
⏰ masa terbaik untuk membuat pengumuman
🏫 bilangan sekolah, murid dan guru yang terjejas (data KPM melalui OpenDOSM)

13 Okt, 11 malam: 27 daripada 68 stesen melebihi API 100 • 13 stesen berisiko untuk esok.
Ini anggaran model, bukan keputusan rasmi - rujuk sentiasa APIMS, MetMalaysia dan KPM.

Pautan: {URL}
#jerebu #Malaysia #kualiti_udara #dataterbuka #sekolah
```

## Threads / short caption (one line)

`Malaysia only publishes the last 24 h of haze readings, so I built the archive - and a live dashboard that shows tomorrow's school-closure risk, the best time to announce, and how many schools, students and teachers are affected. {URL}`

---

## Alt text

| Image | Alt text |
|---|---|
| `social-card.png` / `social-square.png` | Haze dashboard card: Malaysia haze is "Unhealthy", highest API 175 at Pasir Gudang, 27 of 68 stations above 100, 13 flagged for closure risk tomorrow, about 2,600 schools likely affected. |
| `01-tour.png` | Numbered tour of the Hazeshaman dashboard: live status badge, haze sky, state tiles, Live/What-if switch, state filter and national outlook. |
| `02-state-filter.png` | The state filter: a dropdown on desktop, and on a phone a round button at the bottom-right that opens a bottom sheet listing Malaysia and each state with its highest API and status. |
| `03-haze-at-a-glance.png` | The haze panel: band name, four headline numbers, a colour scale of Malaysian API bands with markers, and one API tile per state. |
| `04-national-outlook.png` | Table of states ranked by tomorrow's closure risk, with the number of schools in each state and the schools likely affected. |
| `05-station-detail.png` | One state and station: recommendation to close, probability ring, KPM trigger probabilities, state-level schools, students and teachers impacted, and best/base/worst scenarios. |
| `06-data-check.png` | Data check panel: stations flagged, DOE against Open-Meteo on the same AQI scale with the expected range, A/B/C reliability grades and a second-opinion closure chance. |
| `07-announcement-time.png` | Bar chart of announcement times; the cheapest hour moves from 3 PM to 9 PM when the cost of delay is set to zero. |
| `08-what-if.png` | What-if mode with sliders for hourly readings and a recomputed recommendation. |
| `09-mobile.png` | Three phone screens: haze panel, national outlook and station recommendation. |

## Posting checklist

- [ ] Replace `{URL}`; refresh numbers (`npm run guide` rewrites `docs/howto/snapshot.json`).
- [ ] Keep the "model estimate, not official" line; do not describe the output as a KPM decision.
- [ ] Credit data: DOE Malaysia (APIMS), MOE via OpenDOSM / data.gov.my.
- [ ] LinkedIn: upload the PDF as a **document** (carousel), put the link in the first comment.
