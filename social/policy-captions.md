# Policy-maker social kit

Snapshots and captions aimed at **decision-makers** (KPM, state education departments, DOE, NADMA, MetMalaysia, state governments), taken from
https://hazeshaman.vercel.app/ on **14 Oct 2026 (08:00 MYT data)**. Regenerate the images with
`BASE=https://hazeshaman.vercel.app node scripts/make_policy_cards.mjs` (numbers are read from the data files, snapshots from the live site).

## Which finding to lead with

I compared the findings by two questions: *would a policy maker act on it?* and *will a stranger understand it in three seconds?*
(This is judgement from the numbers and from how decision-makers read posts, not a measured A/B test; post, then compare reach and replies.)

| Finding | Policy value | Scroll-stopping | Risk | Use |
|---|---|---|---|---|
| **An early, evidence-backed signal for next-morning decisions** (model flagged 11 of 14 trigger days at the 6 PM run; recorded closures covered 6) | High: it is the actual decision | High: one concrete ratio | Can read as criticism of authorities if worded badly | **Lead post** (portrait card) |
| **Every reading is cross-checked and doubtful ones flagged** (28·32·8 grades, Sarawak 0.87, Sabah 0.79, 12 flags) | High: answers "can I trust the data?", the first question a policy maker asks, and covers Sarawak and Sabah | Medium | Needs one line explaining "unconfirmed is not wrong" | **Second post**, 2-3 days later (landscape card) |
| **Live status** (Unhealthy; 13 of 68 stations at closure risk tomorrow) | Medium: timely | Highest during a haze episode | Goes stale within hours | **Public/share post** while the episode lasts (square card) |
| Best announcement time (3 PM cheapest at default costs; 5:45 PM practice is close) | High but nuanced | Low | Depends on a cost assumption that is the user's, not the model's | Keep for replies and the written notes, not the headline |

**Why the lead is the first row:** policy makers respond to something that fits a decision they already own, stated with evidence and limits.
The first post therefore names the decision (next-morning closure), the evidence (out-of-sample test, independent cross-check) and the honest limit
(decision support, not official). Frame it as *more evidence for your call*, never as "the authorities were late".

**Posting tips:** post during an active haze episode (relevance), lead with the portrait card on LinkedIn, put the link in the first comment,
tag the relevant agencies by their official handles (check them before posting), and reply to the first comments within the hour.

**Claims you can make / should not make**
- Can: "tested on days the model never saw", "cross-checked against an independent source", "flags doubtful reports", "uses KPM's own trigger".
- Should not: "predicts closures", "better than the authorities", "official", or any claim about health outcomes. The 11 of 14 versus 6 of 14 comparison is **not like-for-like** (authorities also weigh health advice, logistics and district-level scope), so always keep that sentence.

## Images

| File | Size | Use |
|---|---|---|
| `policy-card-portrait.png` | 1080x1350 | LinkedIn / Instagram / Facebook, the lead post |
| `trust-card-landscape.png` | 1200x630 | X / LinkedIn / link preview, the data-reliability post |
| `live-card-square.png` | 1080x1080 | Facebook / Instagram / Threads, live status |
| `snapshots/*.png` | 2x crops | raw live screenshots: `overview`, `national-outlook`, `forecast-johor`, `scenarios`, `data-check`, `analysis`, `schools-closures` |

Alt text (policy card): *Dashboard summary: 11 of 14 days the KPM closure trigger was met were flagged by the 6 PM model run the evening before, 28 stations graded A, 32 B and 8 C against an independent source, 66-72% lower error than the base-rate guess; below it a screenshot of a state recommendation with a closure ring at 83%.*

---

## LinkedIn - lead post (English) - attach `policy-card-portrait.png`

> School closures for haze are decided on incomplete information, often within hours.
>
> I built **Hazeshaman** to give decision-makers an early, evidence-based signal for the next morning:
>
> ▸ closure chance for every state and station, using KPM's own trigger (API above 180, or above 150 for three days)
> ▸ the schools, students and teachers behind each state
> ▸ the announcement time that best balances a missed closure against making families wait
> ▸ every DOE reading cross-checked against an independent source, with doubtful reports flagged (Sarawak and Sabah included)
>
> What testing shows (on days the model never saw): 66-72% lower error than always guessing the base rate. In a replay of 6-13 Oct 2026, the 6 PM run flagged 11 of the 14 days the trigger was met the next day; recorded closures covered 6. That is not a like-for-like comparison, because authorities also weigh health advice, logistics and district-level scope. The point is an earlier, shared evidence base, not a replacement for judgement.
>
> It is decision support, not an official forecast. I would value feedback from KPM, state education departments, DOE and NADMA on what would make it fit your workflow.
>
> #Malaysia #Haze #AirQuality #PublicPolicy #OpenData #Education #DataForGood

First comment: `Live dashboard: https://hazeshaman.vercel.app  ·  How to use: https://hazeshaman.vercel.app/guide  ·  Method and caveats: https://github.com/booluckgmie/hazeshaman/tree/main/docs/analysis`

## LinkedIn / X - data-trust post - attach `trust-card-landscape.png`

> "Is the number on the screen right?" is the first question before any school closure.
>
> Hazeshaman cross-checks every DOE station against an independent model (Open-Meteo / Copernicus CAMS) and flags reports it cannot support: 12 flagged in the last 5 days, 7 at closure level.
>
> For Sarawak and Sabah, DOE data agrees with the independent source about as well as the peninsula does (correlation 0.87 and 0.79 vs 0.76). Eight stations are graded "verify before acting".
>
> "Unconfirmed" is not "wrong": a 25 km model cannot see one chimney. It tells you what to verify.
>
> https://hazeshaman.vercel.app  #Malaysia #Haze #OpenData

X version (under 280 characters):
`Before closing schools: is the reading right? Hazeshaman cross-checks every DOE station against an independent model and flags doubtful reports (12 this week). Sarawak/Sabah agree as well as the peninsula. hazeshaman.vercel.app #Malaysia #Haze`

## Facebook / Instagram - live post - attach `live-card-square.png`

```
🌫️ Unhealthy air across Malaysia right now.
13 of 68 stations are at closure risk for tomorrow morning.

Hazeshaman shows, by state and station:
✅ the chance schools must close (KPM's rule: API above 180, or above 150 for 3 days)
✅ how many schools, students and teachers are behind each state
✅ the best time to announce

Model estimate from the hourly DOE data, not an official decision. Always check APIMS and your school's announcement.

Link in bio / comments: hazeshaman.vercel.app
#Haze #Jerebu #Malaysia #IPU #KualitiUdara
```

## Bahasa Malaysia (all platforms)

> Keputusan menutup sekolah akibat jerebu dibuat dengan maklumat yang terhad dan dalam masa singkat.
>
> **Hazeshaman** memberi isyarat awal berasaskan data untuk pagi esok: peluang penutupan bagi setiap negeri dan stesen (mengikut syarat KPM: IPU melebihi 180, atau melebihi 150 selama tiga hari), bilangan sekolah, murid dan guru yang terlibat, serta masa terbaik untuk membuat pengumuman.
>
> Setiap bacaan DOE disemak silang dengan sumber bebas (Open-Meteo), dan laporan yang meragukan ditanda, termasuk Sarawak dan Sabah. Diuji pada hari yang tidak pernah dilihat model.
>
> Ini sokongan keputusan, bukan ramalan rasmi. Sentiasa rujuk APIMS, MetMalaysia dan pengumuman KPM. Maklum balas daripada KPM, jabatan pendidikan negeri, JAS dan NADMA amat dialu-alukan.
>
> hazeshaman.vercel.app  #Jerebu #IPU #Malaysia #Pendidikan

---

## Before you post
- [ ] Refresh the live numbers (`node scripts/make_policy_cards.mjs`) so the snapshot time is within a few hours.
- [ ] Check the official handles of the agencies you tag; I have not guessed any.
- [ ] Keep the sentence "not like-for-like" next to the 11 of 14 versus 6 of 14 figures.
- [ ] Open the link on a phone first.
