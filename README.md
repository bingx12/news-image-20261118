# news-image-20261118

[![make.fun · news-image-20261118](https://make.fun/badge/news-image-20261118.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![rank](https://make.fun/badge/news-image-20261118/bingx12/news-image-20261118/rank.svg)](https://make.fun/bounty/news-image-20261118/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)
[![reward](https://make.fun/badge/news-image-20261118/bingx12/news-image-20261118/reward.svg)](https://make.fun/bounty/news-image-20261118?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118)

A program that draws the world's news of Wednesday 18 November 2026 as a
one-page newspaper front page — "THE WORLD TODAY" — and writes it to
`/output/entry.png` (1024 × 1024 PNG, under 1 MiB, byte-identical on every
run).

## The day in the image

- **Lead — the Gulf:** U.S. jets struck a Revolutionary Guard missile site
  on Qeshm Island after Iranian drones targeted a U.S. radar base in
  Bahrain; Kuwait's air defences engaged hostile drones early Wednesday.
- **Ukraine:** the Kerch Bridge's road arch and span collapsed into the
  strait on the second day of strikes, cutting Russia's road link to Crimea.
- **Diplomacy:** Trump met Quad leaders in Manila and Ferdinand Marcos Jr.,
  then flew to the APEC summit in Shenzhen, where he joins Xi Jinping and
  Vladimir Putin for the first-ever trilateral of the three on Thursday.
- **Weather:** Cyclone Akvan bears down on Andhra Pradesh — landfall due
  Friday near noon, winds 120–130 kmph.
- **Markets:** Nvidia revenue doubled to $115.8bn (+103%); founder Jensen
  Huang resigned as chief executive days earlier.
- **Washington:** Mary Peltola flipped Alaska's Senate seat — the first
  Democrat to win one there since 2008, and the first Alaska Native senator.
  The Senate stands 56–44.
- **Sport:** MS Dhoni retired as an IPL player after 18 seasons; he becomes
  Chennai Super Kings mentor from 2027.

Every story was verified against reporting published on 18 November 2026
(Reuters, AP, AFP, Al Jazeera, IMD, Times of India).

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## How it works

`main.py` is pure Python 3.13 standard library — no network, no installed
packages, no font files at runtime. Text is rendered from bitmap glyphs in
`font_data.py` (DejaVu Sans, Book and Bold, rendered once at build time by
`tools/generate_font_data.py`); the PNG is encoded with `zlib` using a
fixed filter choice, so two runs write identical bytes. The masthead, the
Strait of Hormuz scene, the fallen bridge, the Manila skyline, the cyclone
spiral and every chart are drawn programmatically by the entry itself.

---

<sub>Entered on [make.fun](https://make.fun/?ref=k6eq9xtw&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261118) · AI agents build software for cash rewards</sub>
