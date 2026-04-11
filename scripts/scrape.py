"""
UNDP Photo Sources – data scraper
Writes data.json consumed by index.html
Run locally: python scripts/scrape.py
"""

import asyncio, json, re, time, sys, signal
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; UNDPSourcesBot/1.0)"
})

TIMEOUT = 10
PLAYWRIGHT_TIMEOUT = 15_000  # ms
PLAYWRIGHT_NAV_TIMEOUT = 12_000  # ms for goto
CONCURRENCY = 8  # parallel browser pages

# ─── Source definitions ──────────────────────────────────────────────────────
# Each entry: [country, flickr_url, flickr_nsid, exposure_url, stories_url, blog_url]
# flickr_nsid: the @N0x part needed for the public feed API

OFFICES = [
    ["Afghanistan",                          "https://www.flickr.com/people/undpafghanistan/",        "undpafghanistan",      "https://undpafghanistan.exposure.co/",  "https://www.undp.org/afghanistan/stories",              "https://www.undp.org/afghanistan/blog"],
    ["Regional Bureau for Africa",                  "https://www.flickr.com/people/201539903@N07/",  "201539903@N07",    "", "https://www.undp.org/africa/stories",        "https://www.undp.org/africa/blogs"],
    ["Regional Bureau for Arab States",              "https://www.flickr.com/people/undparabstats/",  "undparabstats",   "", "https://www.undp.org/arab-states/stories",    "https://www.undp.org/arab-states/blogs"],
    ["Regional Bureau for Asia and the Pacific",     "https://www.flickr.com/photos/undp-aprc/",      "undp-aprc",        "", "https://www.undp.org/asia-pacific/stories",   "https://www.undp.org/asia-pacific/blogs"],
    ["Barbados and Eastern Caribbean",       "https://www.flickr.com/people/undpbarbadosec/",         "undpbarbadosec",       "",                                      "https://www.undp.org/barbados/stories",                 "https://www.undp.org/barbados/blog"],
    ["Belize",                               "https://www.flickr.com/people/undpbelize/",             "undpbelize",           "",                                      "https://www.undp.org/belize/stories",                   "https://www.undp.org/belize/blog"],
    ["BMO Phase II UNDP Ukraine",            "https://www.flickr.com/people/194152175@N08/",          "194152175@N08",        "https://undpukraine.exposure.co/",      "",                                                      ""],
    ["Brasil",                               "https://www.flickr.com/people/195696709@N04/",          "195696709@N04",        "",                                      "https://www.undp.org/brazil/stories",                   "https://www.undp.org/brazil/blog"],
    ["Burkina Faso",                         "https://www.flickr.com/people/196676637@N05/",          "196676637@N05",        "",                                      "https://www.undp.org/burkina-faso/stories",             "https://www.undp.org/burkina-faso/blog"],
    ["Climate",                              "https://www.flickr.com/people/undpclimatechangeadaptation/", "undpclimatechangeadaptation", "https://undp-climate.exposure.co/", "",                                             ""],
    ["Colombia",                             "https://www.flickr.com/people/143329027@N03/",          "143329027@N03",        "https://pnudcolombia.exposure.co/",     "https://www.undp.org/colombia/stories",                 "https://www.undp.org/colombia/blog"],
    ["Czech-UNDP Partnership for SDGs",      "https://www.flickr.com/people/188532807@N05/",          "188532807@N05",        "",                                      "",                                                      ""],
    ["Ecuador",                              "https://www.flickr.com/people/pnudecuador/",            "pnudecuador",          "",                                      "https://www.undp.org/ecuador/stories",                  "https://www.undp.org/ecuador/blog"],
    ["Egypt",                                "https://www.flickr.com/people/undpegypt/",              "undpegypt",            "",                                      "https://www.undp.org/egypt/stories",                    "https://www.undp.org/egypt/blog"],
    ["Eurasia",                              "https://www.flickr.com/people/undpeurasia/",            "undpeurasia",          "https://undpeurasia.exposure.co/",      "",                                                      ""],
    ["Guatemala",                            "https://www.flickr.com/people/92899514@N04/",           "92899514@N04",         "",                                      "https://www.undp.org/guatemala/stories",                "https://www.undp.org/guatemala/blog"],
    ["HDRO Human Development Report",        "https://www.flickr.com/people/undp_hdro/",             "undp_hdro",            "",                                      "",                                                      ""],
    ["IEO (independent Evaluation Office)",  "https://www.flickr.com/people/undpevaluation/",        "undpevaluation",       "",                                      "",                                                      ""],
    ["Irak",                                 "https://www.flickr.com/people/undpiraq/",              "undpiraq",             "",                                      "https://www.undp.org/iraq/stories",                     "https://www.undp.org/iraq/blog"],
    ["Kosovo",                               "https://www.flickr.com/people/undpkosovo/",             "undpkosovo",           "https://undpkosovo.exposure.co/",       "https://www.undp.org/kosovo/stories",                   "https://www.undp.org/kosovo/blog"],
    ["Kyrgyz Republic",                      "https://www.flickr.com/people/undpkg/",                "undpkg",               "",                                      "https://www.undp.org/kyrgyzstan/stories",               "https://www.undp.org/kyrgyzstan/blog"],
    ["Latin America & Caribbean",            "https://www.flickr.com/people/undplac/",               "undplac",              "https://undplac.exposure.co/categories/latin-america-and-the-caribbean", "https://www.undp.org/latin-america-caribbean/stories", "https://www.undp.org/latin-america-caribbean/blog"],
    ["Lebanon",                              "https://www.flickr.com/people/undplebanon/",            "undplebanon",          "",                                      "https://www.undp.org/lebanon/stories",                  "https://www.undp.org/lebanon/blog"],
    ["LHSP Lebanon Host Communities",        "https://www.flickr.com/people/undp_lhsp/",             "undp_lhsp",            "",                                      "",                                                      ""],
    ["Mauritius",                            "https://www.flickr.com/people/183529514@N02/",          "183529514@N02",        "",                                      "https://www.undp.org/mauritius/stories",                "https://www.undp.org/mauritius/blog"],
    ["Moldova",                              "https://www.flickr.com/people/undpmoldova/",            "undpmoldova",          "https://undpmoldova.exposure.co/",      "https://www.undp.org/moldova/stories",                  "https://www.undp.org/moldova/blog"],
    ["Mongolia",                             "https://www.flickr.com/people/142250687@N05/",          "142250687@N05",        "",                                      "https://www.undp.org/mongolia/stories",                 "https://www.undp.org/mongolia/blog"],
    ["Montenegro",                           "https://www.flickr.com/people/106991185@N05/",          "106991185@N05",        "https://undpmontenegro.exposure.co/",   "https://www.undp.org/montenegro/stories",               "https://www.undp.org/montenegro/blog"],
    ["Nature Hub",                           "https://www.flickr.com/people/undp-ebd/",              "undp-ebd",             "https://undp-nature.exposure.co/",      "https://www.undp.org/nature/stories",                   "https://www.undp.org/nature/blogs"],
    ["Pacific Office in Fiji",               "https://www.flickr.com/people/undppc/",                "undppc",               "https://pacificundp.exposure.co/",      "https://www.undp.org/pacific/stories",                  "https://www.undp.org/pacific/blog"],
    ["Pakistan",                             "https://www.flickr.com/people/undppakistan/",           "undppakistan",         "https://undp-pakistan.exposure.co/",    "https://www.undp.org/pakistan/stories",                 "https://www.undp.org/pakistan/blog"],
    ["Panamá",                               "https://www.flickr.com/people/155976344@N02/",          "155976344@N02",        "",                                      "https://www.undp.org/panama/stories",                   "https://www.undp.org/panama/blog"],
    ["Papua New Guinea",                     "https://www.flickr.com/people/148279672@N05/",          "148279672@N05",        "",                                      "https://www.undp.org/papua-new-guinea/stories",         "https://www.undp.org/papua-new-guinea/blog"],
    ["Rwanda",                               "https://www.flickr.com/people/undp_rwanda/",            "undp_rwanda",          "https://undp-rwanda.exposure.co/",      "https://www.undp.org/rwanda/stories",                   "https://www.undp.org/rwanda/blog"],
    ["Senegal",                              "https://www.flickr.com/people/194545654@N04/",          "194545654@N04",        "",                                      "https://www.undp.org/senegal/stories",                  "https://www.undp.org/senegal/blog"],
    ["Small Grants Programme",               "https://www.flickr.com/people/160133712@N07/",          "160133712@N07",        "",                                      "",                                                      ""],
    ["Sri Lanka",                            "https://www.flickr.com/people/undpsrilanka/",           "undpsrilanka",         "https://undpsrilanka.exposure.co/",     "https://www.undp.org/sri-lanka/stories",                "https://www.undp.org/sri-lanka/blog"],
    ["Syria",                                "https://www.flickr.com/people/undpsyria/",              "undpsyria",            "",                                      "https://www.undp.org/syria/stories",                    "https://www.undp.org/syria/blog"],
    ["Thailand",                             "https://www.flickr.com/people/122929707@N08/",          "122929707@N08",        "https://undpthailand.exposure.co/",     "https://www.undp.org/thailand/stories",                 "https://www.undp.org/thailand/blog"],
    ["Tokyo",                                "https://www.flickr.com/photos/63970428@N08/",           "63970428@N08",         "",                                      "",                                                      ""],
    ["Turkmenistan (active)",                "https://www.flickr.com/people/193591905@N07/",          "193591905@N07",        "",                                      "https://www.undp.org/turkmenistan/stories",             "https://www.undp.org/turkmenistan/blog"],
    ["Ukraine",                              "https://www.flickr.com/people/undpukraine/",            "undpukraine",          "https://undpukraine.exposure.co/",      "https://www.undp.org/ukraine/stories",                  "https://www.undp.org/ukraine/blog"],
    ["Uzbekistan",                           "https://www.flickr.com/people/90476166@N07/",           "90476166@N07",         "",                                      "https://www.undp.org/uzbekistan/stories",               "https://www.undp.org/uzbekistan/blog"],
    ["Albania",                              "https://www.flickr.com/people/124761789@N08/",          "124761789@N08",        "",                                      "https://www.undp.org/albania/stories",                  "https://www.undp.org/albania/blog"],
    ["Argentina",                            "https://www.flickr.com/photos/131208323@N07/",          "131208323@N07",        "",                                      "https://www.undp.org/argentina/stories",                "https://www.undp.org/argentina/blog"],
    ["Azerbaijan",                           "https://www.flickr.com/people/undp_azerbaijan/",       "undp_azerbaijan",      "",                                      "https://www.undp.org/azerbaijan/stories",               "https://www.undp.org/azerbaijan/blog"],
    ["Bangladesh",                           "https://www.flickr.com/people/98606405@N05/",           "98606405@N05",         "",                                      "https://www.undp.org/bangladesh/stories",               "https://www.undp.org/bangladesh/blog"],
    ["Belarus",                              "https://www.flickr.com/people/99592520@N04/",           "99592520@N04",         "",                                      "https://www.undp.org/belarus/stories",                  "https://www.undp.org/belarus/blog"],
    ["Bissau",                               "https://www.flickr.com/people/undpbissau/",             "undpbissau",           "",                                      "https://www.undp.org/guinea-bissau/stories",            "https://www.undp.org/guinea-bissau/blog"],
    ["Bolivia",                              "https://www.flickr.com/people/152771673@N06/",          "152771673@N06",        "",                                      "https://www.undp.org/bolivia/stories",                  "https://www.undp.org/bolivia/blog"],
    ["Bosnia and Herzegovina",               "https://www.flickr.com/people/undp_bosnia-herzegovina/","undp_bosnia-herzegovina","",                                  "https://www.undp.org/bosnia-herzegovina/stories",       "https://www.undp.org/bosnia-herzegovina/blog"],
    ["Burundi",                              "https://www.flickr.com/people/66132733@N03/",           "66132733@N03",         "",                                      "https://www.undp.org/burundi/stories",                  "https://www.undp.org/burundi/blog"],
    ["Business and Human Rights",            "https://www.flickr.com/people/197823823@N06/",          "197823823@N06",        "",                                      "",                                                      ""],
    ["Cambodia",                             "https://www.flickr.com/people/undpcambodia/",           "undpcambodia",         "",                                      "https://www.undp.org/cambodia/stories",                 "https://www.undp.org/cambodia/blog"],
    ["Chile",                                "https://www.flickr.com/people/pnud_chile/",             "pnud_chile",           "",                                      "https://www.undp.org/chile/stories",                    "https://www.undp.org/chile/blog"],
    ["China",                                "https://www.flickr.com/people/undpchina/",              "undpchina",            "",                                      "https://www.undp.org/china/stories",                    "https://www.undp.org/china/blog"],
    ["Costa Rica",                           "https://www.flickr.com/people/183280342@N05/",          "183280342@N05",        "",                                      "https://www.undp.org/costa-rica/stories",               "https://www.undp.org/costa-rica/blog"],
    ["Cyprus",                               "https://www.flickr.com/people/undp-pff/",              "undp-pff",             "",                                      "",                                                      ""],
    ["El Salvador",                          "https://www.flickr.com/people/pnud_el_salvador/",      "pnud_el_salvador",     "",                                      "https://www.undp.org/el-salvador/stories",              "https://www.undp.org/el-salvador/blog"],
    ["Eritrea",                              "https://www.flickr.com/photos/138144707@N08/",          "138144707@N08",        "",                                      "https://www.undp.org/eritrea/stories",                  "https://www.undp.org/eritrea/blog"],
    ["Ethiopia",                             "https://www.flickr.com/people/undpethiopia/",           "undpethiopia",         "",                                      "https://www.undp.org/ethiopia/stories",                 "https://www.undp.org/ethiopia/blog"],
    ["Regional Bureau for Europe and Central Asia", "https://www.flickr.com/photos/undpeuropeandcis/", "undpeuropeandcis", "", "https://www.undp.org/europe-central-asia/stories", "https://www.undp.org/europe-central-asia/blogs"],
    ["Ghana",                                "https://www.flickr.com/people/42913191@N02/",           "42913191@N02",         "",                                      "https://www.undp.org/ghana/stories",                    "https://www.undp.org/ghana/blog"],
    ["Honduras",                             "https://www.flickr.com/photos/pnudhn/",                "pnudhn",               "",                                      "https://www.undp.org/honduras/stories",                 "https://www.undp.org/honduras/blog"],
    ["India",                                "https://www.flickr.com/photos/undp-india/albums/",      "undp-india",           "https://undp-india.exposure.co/",       "https://www.undp.org/india/stories",                    "https://www.undp.org/india/blog"],
    ["Indonesia",                            "https://www.flickr.com/photos/93491749@N08/",           "93491749@N08",         "https://undpid.exposure.co/",           "https://www.undp.org/indonesia/stories",                "https://www.undp.org/indonesia/blog"],
    ["Jamaica",                              "https://www.flickr.com/people/undpjamaica/",            "undpjamaica",          "https://undpjamaica.exposure.co/",      "https://www.undp.org/jamaica/stories",                  "https://www.undp.org/jamaica/blog"],
    ["Kenya",                                "https://www.flickr.com/people/undpkenya/",              "undpkenya",            "https://undpkenya.exposure.co/",        "https://www.undp.org/kenya/stories",                    "https://www.undp.org/kenya/blog"],
    ["Kuwait",                               "https://www.flickr.com/photos/kwundp/",                "kwundp",               "",                                      "https://www.undp.org/kuwait/stories",                   "https://www.undp.org/kuwait/blog"],
    ["Liberia",                              "https://www.flickr.com/photos/132967828@N08/",          "132967828@N08",        "",                                      "https://www.undp.org/liberia/stories",                  "https://www.undp.org/liberia/blog"],
    ["Malaysia",                             "https://www.flickr.com/people/myundp/",                "myundp",               "",                                      "https://www.undp.org/malaysia/stories",                 "https://www.undp.org/malaysia/blog"],
    ["Maldives",                             "https://www.flickr.com/people/undpmaldives/",           "undpmaldives",         "",                                      "https://www.undp.org/maldives/stories",                 "https://www.undp.org/maldives/blog"],
    ["Mali",                                 "https://www.flickr.com/people/132226887@N03/",          "132226887@N03",        "",                                      "https://www.undp.org/mali/stories",                     "https://www.undp.org/mali/blog"],
    ["Maroc",                                "https://www.flickr.com/people/120267337@N06/",          "120267337@N06",        "",                                      "https://www.undp.org/morocco/stories",                  "https://www.undp.org/morocco/blog"],
    ["México",                               "https://www.flickr.com/photos/pnudmx/",                "pnudmx",               "",                                      "https://www.undp.org/mexico/stories",                   "https://www.undp.org/mexico/blog"],
    ["Nepal",                                "https://www.flickr.com/people/undpnepal/",              "undpnepal",            "https://undpnepal.exposure.co/",        "https://www.undp.org/nepal/stories",                    "https://www.undp.org/nepal/blog"],
    ["Niger",                                "https://www.flickr.com/people/pnudniger/",              "pnudniger",            "",                                      "https://www.undp.org/niger/stories",                    "https://www.undp.org/niger/blog"],
    ["Perú",                                 "https://www.flickr.com/people/pnudperu/",               "pnudperu",             "",                                      "https://www.undp.org/peru/stories",                     "https://www.undp.org/peru/blog"],
    ["Philippines",                          "https://www.flickr.com/people/undpph/",                "undpph",               "",                                      "https://www.undp.org/philippines/stories",              "https://www.undp.org/philippines/blog"],
    ["Programme of Assistance to the Palestinian People", "https://www.flickr.com/people/undp-palestinian/", "undp-palestinian", "", "https://www.undp.org/papp/stories", "https://www.undp.org/papp/blog"],
    ["RDC",                                  "https://www.flickr.com/people/pnudrdc/",               "pnudrdc",              "",                                      "https://www.undp.org/democratic-republic-congo/stories", "https://www.undp.org/democratic-republic-congo/blog"],
    ["Republica Dominicana",                 "https://www.flickr.com/people/pnudrd/",                "pnudrd",               "",                                      "https://www.undp.org/dominican-republic/stories",       "https://www.undp.org/dominican-republic/blog"],
    ["Russia",                               "https://www.flickr.com/people/98900690@N05/",           "98900690@N05",         "",                                      "",                                                      ""],
    ["Samoa",                                "https://www.flickr.com/people/61881570@N05/",           "61881570@N05",         "",                                      "https://www.undp.org/samoa/stories",                    "https://www.undp.org/samoa/blog"],
    ["Seoul Facility Centre",                "https://www.flickr.com/photos/uspc/",                  "uspc",                 "",                                      "",                                                      ""],
    ["Serbia",                               "https://www.flickr.com/photos/undp_serbia/",            "undp_serbia",          "",                                      "https://www.undp.org/serbia/stories",                   "https://www.undp.org/serbia/blog"],
    ["Solomon Islands",                      "https://www.flickr.com/people/193805107@N08/",          "193805107@N08",        "",                                      "https://www.undp.org/solomon-islands/stories",          "https://www.undp.org/solomon-islands/blog"],
    ["Somalia",                              "https://www.flickr.com/people/undpsomalia/",            "undpsomalia",          "https://undpsomalia.exposure.co/",      "https://www.undp.org/somalia/stories",                  "https://www.undp.org/somalia/blog"],
    ["South Sudan",                          "https://www.flickr.com/people/undpsouthsudan/",         "undpsouthsudan",       "",                                      "https://www.undp.org/south-sudan/stories",              "https://www.undp.org/south-sudan/blog"],
    ["Sudan",                                "https://www.flickr.com/people/undpsudan/",              "undpsudan",            "",                                      "https://www.undp.org/sudan/stories",                    "https://www.undp.org/sudan/blog"],
    ["Tchad",                                "https://www.flickr.com/people/199227871@N04/",          "199227871@N04",        "",                                      "https://www.undp.org/chad/stories",                     "https://www.undp.org/chad/blog"],
    ["TimorLeste",                           "https://www.flickr.com/people/155674736@N07/",          "155674736@N07",        "",                                      "https://www.undp.org/timor-leste/stories",              "https://www.undp.org/timor-leste/blog"],
    ["Togo",                                 "https://www.flickr.com/people/pnudtogo/",              "pnudtogo",             "",                                      "https://www.undp.org/togo/stories",                     "https://www.undp.org/togo/blog"],
    ["Tunisia",                              "https://www.flickr.com/people/128649079@N08/",          "128649079@N08",        "",                                      "https://www.undp.org/tunisia/stories",                  "https://www.undp.org/tunisia/blog"],
    ["Uganda",                               "https://www.flickr.com/photos/undpuganda/",             "undpuganda",           "",                                      "https://www.undp.org/uganda/stories",                   "https://www.undp.org/uganda/blog"],
    ["United Nations Development Programme", "https://www.flickr.com/people/unitednationsdevelopmentprogramme/", "unitednationsdevelopmentprogramme", "https://undp.exposure.co/", "", ""],
    ["Uruguay",                              "https://www.flickr.com/people/132265388@N07/",          "132265388@N07",        "",                                      "https://www.undp.org/uruguay/stories",                  "https://www.undp.org/uruguay/blog"],
    ["Vietnam",                              "https://www.flickr.com/people/73471477@N07/",           "73471477@N07",         "https://undpvietnam.exposure.co/",      "https://www.undp.org/viet-nam/stories",                 "https://www.undp.org/viet-nam/blog"],
    ["Zambia",                               "https://www.flickr.com/people/143320674@N04/",          "143320674@N04",        "https://undpinzambia.exposure.co/",     "https://www.undp.org/zambia/stories",                   "https://www.undp.org/zambia/blog"],
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def get(url, **kwargs):
    """GET with timeout and basic error handling. Returns Response or None."""
    try:
        r = SESSION.get(url, timeout=TIMEOUT, **kwargs)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  WARN {url}: {e}", file=sys.stderr)
        return None


def ts_to_iso(ts):
    """Unix timestamp → ISO date string YYYY-MM-DD."""
    try:
        return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d")
    except Exception:
        return None


def flickr_latest(nsid):
    """
    Use Flickr's no-auth public feed to get the most recent upload date + thumbnail.
    Returns (iso_date, photo_page_url, image_url) or (None, None, None).
    """
    feed_url = (
        f"https://www.flickr.com/services/feeds/photos_public.gne"
        f"?id={nsid}&format=atom&nojsoncallback=1"
    )
    r = get(feed_url)
    if not r:
        return None, None, None
    soup = BeautifulSoup(r.text, "xml")
    entry = soup.find("entry")
    if not entry:
        return None, None, None
    pub = entry.find("published") or entry.find("updated")
    link_tag = entry.find("link", rel="alternate") or entry.find("link")
    url = link_tag["href"] if link_tag and link_tag.get("href") else None
    # Flickr Atom feed image: try multiple strategies
    img_url = None

    # 1. <link rel="enclosure" href="https://live.staticflickr.com/...jpg"/>
    enclosure = entry.find("link", rel="enclosure")
    if enclosure and enclosure.get("href", "").lower().endswith((".jpg", ".jpeg", ".png")):
        img_url = enclosure["href"]

    # 2. <media:thumbnail> or <media:content> — BS4 xml parser uses local tag name
    if not img_url:
        for tag_name in ("thumbnail", "media:thumbnail", "content", "media:content"):
            t = entry.find(tag_name)
            if t and t.get("url"):
                img_url = t["url"]
                break

    # 3. Regex on raw XML — staticflickr.com image URLs
    if not img_url:
        m = re.search(r"https://live\.staticflickr\.com/[^\s\"'<>]+\.jpg", r.text)
        if not m:
            m = re.search(r"https://farm\d+\.staticflickr\.com/[^\s\"'<>]+\.jpg", r.text)
        if not m:
            m = re.search(r"https://[^\s\"'<>]+_[bmzc]\.jpg", r.text)
        if m:
            img_url = m.group(0)

    # Prefer larger size: swap _m.jpg → _b.jpg
    if img_url and "_m.jpg" in img_url:
        img_url = img_url.replace("_m.jpg", "_b.jpg")
    title = None
    title_tag = entry.find("title")
    if title_tag and title_tag.text:
        title = title_tag.text.strip()

    if pub:
        try:
            dt = datetime.fromisoformat(pub.text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d"), url, img_url, title
        except Exception:
            pass
    return None, url, img_url, title




async def flickr_photo_page_details(browser, photo_url):
    """
    Use Playwright to scrape a Flickr photo page for album name and dates.
    Returns (album, date_uploaded, date_taken) — all may be None.
    """
    html = await _fetch_html(browser, photo_url)  # No selector wait — just DOM
    if not html:
        return None, None, None
    soup = BeautifulSoup(html, "html.parser")

    # Album: "This photo is in 1 album" section → find the album title link
    album = None
    # Look for the album link — it's an <a> tag near "album" text
    for a in soup.find_all("a", href=True):
        if "/albums/" in a["href"] or "/sets/" in a["href"]:
            txt = a.get_text(strip=True)
            if txt and len(txt) > 2:
                album = txt
                break
    # Fallback: regex on raw HTML
    if not album:
        m = re.search(r'/(?:albums|sets)/\d+[^"]*"[^>]*>\s*([^<]{3,100})\s*<', html)
        if m:
            album = m.group(1).strip()

    # Dates: "Uploaded on ..." and "Taken on ..."
    date_uploaded = None
    date_taken = None
    text = soup.get_text(" ")
    m = re.search(r"Uploaded\s+on\s+([\w]+ \d+,\s*\d{4})", text)
    if m:
        date_uploaded = m.group(1).strip()
    m = re.search(r"Taken\s+on\s+([\w]+ \d+,\s*\d{4})", text)
    if m:
        date_taken = m.group(1).strip()

    return album, date_uploaded, date_taken


# Month name → number map for parsing Exposure's "January 1st, 2025" format
_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

def _parse_exposure_date(text):
    """Parse 'July 1st, 2025' or 'September 17th, 2025' → '2025-07-01'."""
    m = re.search(
        r'(january|february|march|april|may|june|july|august|september|october|november|december)'
        r'\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})',
        text.lower()
    )
    if m:
        month = _MONTH_MAP[m.group(1)]
        day   = m.group(2).zfill(2)
        year  = m.group(3)
        return f"{year}-{month}-{day}"
    return None


async def exposure_latest(browser, base_url):
    """
    Scrape an Exposure.co profile page using a headless browser (it's a JS SPA).
    Finds the most recent story: returns (iso_date, story_url, image_url).
    """
    try:
        browser = _get_browser()
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; UNDPSourcesBot/1.0)"})
        page.goto(base_url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
        # Wait for story cards — Exposure renders <article> or <section> elements
        for sel in ["article a[href]", "section a[href]", ".story a[href]", "a[href*='/']"]:
            try:
                page.wait_for_selector(sel, timeout=8_000)
                break
            except Exception:
                continue
        html = page.content()
        page.close()
    except Exception as e:
        print(f"  WARN playwright exposure {base_url}: {e}", file=sys.stderr)
        return None, base_url, None

    soup = BeautifulSoup(html, "html.parser")
    parsed_url = urlparse(base_url)
    site_origin = f"{parsed_url.scheme}://{parsed_url.netloc}"

    candidates = []

    # Strategy 1: <time datetime="YYYY-MM-DD"> tags (some Exposure sites use these)
    for t in soup.find_all("time", attrs={"datetime": True}):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", t["datetime"])
        if not m:
            continue
        iso = m.group(1)
        # Walk up to find the enclosing story link
        story_url = base_url
        img_url = None
        card = t.find_parent(["article", "section", "li", "div"])
        if card:
            a = card.find("a", href=True)
            if a:
                href = a["href"]
                story_url = href if href.startswith("http") else site_origin + href
            img = card.find("img")
            if img:
                src = img.get("src") or img.get("data-src") or ""
                img_url = src if src.startswith("http") else (site_origin + src if src.startswith("/") else None)
        story_title = None
        heading = card.find(["h1","h2","h3","h4"]) if card else None
        if heading:
            story_title = heading.get_text(strip=True) or None
        candidates.append((iso, story_url, img_url, story_title))

    # Strategy 2: Parse inline date text "Month Nth, YYYY" that appears next to story links
    # Exposure renders each story as a block with a cover image, title, and date string.
    # Walk all <a> tags that look like story links (same domain, non-trivial path)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Only intra-site story links (e.g. /a-growing-business)
        if not (href.startswith("/") and len(href) > 2 and "." not in href.split("/")[-1]):
            continue
        story_url = site_origin + href
        # Look for a date string in the surrounding container
        container = a.find_parent(["article", "section", "li"]) or a.find_parent("div")
        if not container:
            continue
        text = container.get_text(" ", strip=True)
        iso = _parse_exposure_date(text)
        if not iso:
            continue
        # Grab cover image
        img_url = None
        img = container.find("img")
        if img:
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            if src.startswith("http"):
                img_url = src
            elif src.startswith("/"):
                img_url = site_origin + src
        # Try to extract story title from container
        story_title = None
        heading = container.find(["h1","h2","h3","h4"])
        if heading:
            story_title = heading.get_text(strip=True) or None
        candidates.append((iso, story_url, img_url, story_title))

    if candidates:
        # Deduplicate by URL, keep latest date per URL
        seen = {}
        for iso, url, img, ttl in candidates:
            if url not in seen or iso > seen[url][0]:
                seen[url] = (iso, url, img, ttl)
        best = sorted(seen.values(), key=lambda x: x[0], reverse=True)[0]
        return best

    # Strategy 3: image src paths containing a date segment
    dates = []
    imgs_by_date = {}
    for img in soup.find_all("img", src=True):
        m = re.search(r"/(\d{4}-\d{2})/", img["src"])
        if m:
            key = m.group(1) + "-01"
            dates.append(key)
            imgs_by_date[key] = img["src"]
    if dates:
        dates.sort(reverse=True)
        best = dates[0]
        return best, base_url, imgs_by_date.get(best), None

    return None, base_url, None, None


# ─── Async browser helpers ────────────────────────────────────────────────────
async def _new_page(browser):
    page = await browser.new_page()
    await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; UNDPSourcesBot/1.0)"})
    return page


async def _fetch_html(browser, url, wait_sel=None):
    """Navigate to url, optionally wait for a selector, return HTML string or None."""
    page = await _new_page(browser)
    try:
        await page.goto(url, timeout=PLAYWRIGHT_NAV_TIMEOUT, wait_until="domcontentloaded")
        if wait_sel:
            try:
                await page.wait_for_selector(wait_sel, timeout=5_000)
            except Exception:
                pass
        return await page.content()
    except Exception as e:
        print(f"  WARN {url}: {e}", file=sys.stderr)
        return None
    finally:
        await page.close()


async def undp_page_latest(browser, page_url):
    """
    Scrape an undp.org /stories or /blog listing page using a headless browser.
    Returns (iso_date, article_url, image_url) or (None, page_url, None).
    """
    html = await _fetch_html(browser, page_url, wait_sel="time[datetime], [class*='card']")
    if not html:
        return None, page_url, None

    soup = BeautifulSoup(html, "html.parser")

    # Strategy 0: JSON-LD structured data (most reliable when present)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            items = data if isinstance(data, list) else [data]
            candidates = []
            for item in items:
                # Handle ItemList wrapping articles
                if item.get("@type") == "ItemList":
                    for el in item.get("itemListElement", []):
                        it = el.get("item", el)
                        date = it.get("datePublished") or it.get("dateModified", "")
                        url = it.get("url", page_url)
                        img = (it.get("image") or {})
                        img_url = img.get("url") if isinstance(img, dict) else (img if isinstance(img, str) else None)
                        m = re.match(r"(\d{4}-\d{2}-\d{2})", date)
                        if m:
                            candidates.append((m.group(1), url, img_url, it.get("headline") or it.get("name") or None))
                else:
                    date = item.get("datePublished") or item.get("dateModified", "")
                    url = item.get("url", page_url)
                    img = item.get("image") or {}
                    img_url = img.get("url") if isinstance(img, dict) else (img if isinstance(img, str) else None)
                    m = re.match(r"(\d{4}-\d{2}-\d{2})", date)
                    if m:
                        candidates.append((m.group(1), url, img_url, item.get("headline") or item.get("name") or None))
            if candidates:
                candidates.sort(key=lambda x: x[0], reverse=True)
                return candidates[0]
        except Exception:
            pass

    # Strategy 1: <time datetime="YYYY-MM-DD"> — pick the most recent, grab nearby image
    time_dates = []
    for t in soup.find_all("time", attrs={"datetime": True}):
        raw = t["datetime"]
        m = re.match(r"(\d{4}-\d{2}-\d{2})", raw)
        if m:
            parent_a = t.find_parent("a")
            if not parent_a:
                parent = t.find_parent(["article", "li", "div"])
                parent_a = parent.find("a", href=True) if parent else None
            link = ("https://www.undp.org" + parent_a["href"]
                    if parent_a and parent_a.get("href", "").startswith("/")
                    else page_url)
            # Grab image from the same card
            img_url = None
            card = t.find_parent(["article", "li"]) or t.find_parent("div", class_=re.compile(r"card|item|story|post", re.I))
            if card:
                img = card.find("img")
                if img:
                    src = img.get("src") or img.get("data-src") or img.get("data-lazy-src", "")
                    if src.startswith("http"):
                        img_url = src
                    elif src.startswith("/"):
                        img_url = "https://www.undp.org" + src
            # Extract title from nearby heading
            title = None
            card2 = t.find_parent(["article", "li"]) or t.find_parent("div", class_=re.compile(r"card|item|story|post", re.I))
            if card2:
                h = card2.find(["h1","h2","h3","h4"])
                if h:
                    title = h.get_text(strip=True) or None
            time_dates.append((m.group(1), link, img_url, title))

    if time_dates:
        time_dates.sort(key=lambda x: x[0], reverse=True)
        return time_dates[0]

    # Strategy 2: date embedded in image src paths
    dates = []
    article_links = []
    img_by_date = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") and len(href) > 20:
            article_links.append("https://www.undp.org" + href)
    for img in soup.find_all("img", src=True):
        m = re.search(r"/(?:public|files)/(\d{4}-\d{2})/", img["src"])
        if m:
            key = m.group(1) + "-01"
            dates.append(key)
            img_by_date[key] = img["src"]
    if dates:
        dates.sort(reverse=True)
        best = dates[0]
        return best, article_links[0] if article_links else page_url, img_by_date.get(best), None

    # Strategy 3: date in meta tags
    for meta in soup.find_all("meta", attrs={"property": re.compile(r"article:published_time|og:updated_time")}):
        mc = meta.get("content", "")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", mc)
        if m:
            return m.group(1), page_url, None, None

    return None, page_url, None, None


# ─── Main ────────────────────────────────────────────────────────────────────

async def scrape_office(browser, sem, i, total, row):
    """Scrape one office with concurrency limiting. Returns a result dict."""
    country, flickr_url, nsid, exposure_url, stories_url, blog_url = row
    async with sem:
        print(f"[{i+1}/{total}] {country}", flush=True)
        rec = {
            "country":  country,
            "flickr":   {"url": flickr_url,   "date": None, "latest_url": None, "image_url": None, "title": None, "album": None, "date_uploaded": None, "date_taken": None},
            "exposure": {"url": exposure_url,  "date": None, "latest_url": None, "image_url": None, "title": None},
            "stories":  {"url": stories_url,   "date": None, "latest_url": None, "image_url": None, "title": None},
            "blog":     {"url": blog_url,      "date": None, "latest_url": None, "image_url": None, "title": None},
        }
        tasks = []
        if nsid:
            tasks.append(("flickr",   flickr_url,   asyncio.to_thread(flickr_latest, nsid)))
        if exposure_url:
            tasks.append(("exposure", exposure_url, exposure_latest(browser, exposure_url)))
        if stories_url:
            tasks.append(("stories",  stories_url,  undp_page_latest(browser, stories_url)))
        if blog_url:
            tasks.append(("blog",     blog_url,     undp_page_latest(browser, blog_url)))

        for plat, fb_url, coro in tasks:
            try:
                result = await asyncio.wait_for(coro, timeout=25)
                d, lu, img, ttl = result
                rec[plat]["date"]       = d
                rec[plat]["latest_url"] = lu or fb_url
                rec[plat]["image_url"]  = img
                rec[plat]["title"]      = ttl
            except Exception as e:
                print(f"  SKIP {country}/{plat}: {e}", file=sys.stderr)

        # Scrape Flickr photo page for album + dates (using Playwright)
        photo_url = rec["flickr"].get("latest_url")
        if photo_url and "flickr.com/photos/" in photo_url and "/photos/" in photo_url:
            try:
                alb, uploaded, taken = await asyncio.wait_for(
                    flickr_photo_page_details(browser, photo_url),
                    timeout=15
                )
                rec["flickr"]["album"]         = alb
                rec["flickr"]["date_uploaded"] = uploaded
                rec["flickr"]["date_taken"]    = taken
            except Exception as e:
                print(f"  SKIP {country}/flickr-page: {e}", file=sys.stderr)

        return rec


async def scrape_all_async():
    results_map = {}
    total = len(OFFICES)
    sem = asyncio.Semaphore(CONCURRENCY)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
        tasks = [
            scrape_office(browser, sem, i, total, row)
            for i, row in enumerate(OFFICES)
        ]
        done = await asyncio.gather(*tasks, return_exceptions=True)
        await browser.close()

    results = []
    for i, res in enumerate(done):
        if isinstance(res, Exception):
            print(f"  ERROR office {i}: {res}", file=sys.stderr)
            country = OFFICES[i][0]
            results.append({"country": country, "flickr": {}, "exposure": {}, "stories": {}, "blog": {}})
        else:
            results.append(res)

    # Sort to match OFFICES order
    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "offices": results,
    }
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nDone — wrote data.json with {len(results)} offices.")


if __name__ == "__main__":
    asyncio.run(scrape_all_async())
