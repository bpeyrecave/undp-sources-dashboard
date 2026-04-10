"""
UNDP Photo Sources – data scraper
Writes data.json consumed by index.html
Run locally: python scripts/scrape.py
"""

import json, re, time, sys
from datetime import datetime, timezone
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; UNDPSourcesBot/1.0)"
})

TIMEOUT = 15
PLAYWRIGHT_TIMEOUT = 20_000  # ms

# ─── Source definitions ──────────────────────────────────────────────────────
# Each entry: [country, flickr_url, flickr_nsid, exposure_url, stories_url, blog_url]
# flickr_nsid: the @N0x part needed for the public feed API

OFFICES = [
    ["Afghanistan",                          "https://www.flickr.com/people/undpafghanistan/",        "undpafghanistan",      "https://undpafghanistan.exposure.co/",  "https://www.undp.org/afghanistan/stories",              "https://www.undp.org/afghanistan/blog"],
    ["Africa",                               "https://www.flickr.com/people/201539903@N07/",          "201539903@N07",        "",                                      "",                                                      ""],
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
    ["Latin America and the Caribbean",      "https://www.flickr.com/people/undplac/",               "undplac",              "",                                      "https://www.undp.org/latin-america-caribbean/stories",  "https://www.undp.org/latin-america-caribbean/blog"],
    ["Lebanon",                              "https://www.flickr.com/people/undplebanon/",            "undplebanon",          "",                                      "https://www.undp.org/lebanon/stories",                  "https://www.undp.org/lebanon/blog"],
    ["LHSP Lebanon Host Communities",        "https://www.flickr.com/people/undp_lhsp/",             "undp_lhsp",            "",                                      "",                                                      ""],
    ["Mauritius",                            "https://www.flickr.com/people/183529514@N02/",          "183529514@N02",        "",                                      "https://www.undp.org/mauritius/stories",                "https://www.undp.org/mauritius/blog"],
    ["Moldova",                              "https://www.flickr.com/people/undpmoldova/",            "undpmoldova",          "https://undpmoldova.exposure.co/",      "https://www.undp.org/moldova/stories",                  "https://www.undp.org/moldova/blog"],
    ["Mongolia",                             "https://www.flickr.com/people/142250687@N05/",          "142250687@N05",        "",                                      "https://www.undp.org/mongolia/stories",                 "https://www.undp.org/mongolia/blog"],
    ["Montenegro",                           "https://www.flickr.com/people/106991185@N05/",          "106991185@N05",        "https://undpmontenegro.exposure.co/",   "https://www.undp.org/montenegro/stories",               "https://www.undp.org/montenegro/blog"],
    ["Nature",                               "https://www.flickr.com/people/undp-ebd/",              "undp-ebd",             "https://undp-nature.exposure.co/",      "",                                                      ""],
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
    ["Europe and Cis",                       "https://www.flickr.com/photos/undpeuropeandcis/",       "undpeuropeandcis",     "",                                      "",                                                      ""],
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
    # Flickr Atom feed has <media:thumbnail url="..."/> or <media:content url="..."/>
    img_url = None
    thumb = entry.find("thumbnail") or entry.find("content", attrs={"medium": "image"})
    if thumb and thumb.get("url"):
        img_url = thumb["url"]
    if not img_url:
        # fallback: look for _m.jpg or _z.jpg in any tag
        m = re.search(r'https://[^"']+_[mzb]\.jpg', r.text)
        if m:
            img_url = m.group(0)
    if pub:
        try:
            dt = datetime.fromisoformat(pub.text.replace("Z", "+00:00"))
            return dt.strftime("%Y-%m-%d"), url, img_url
        except Exception:
            pass
    return None, url, img_url


def exposure_latest(base_url):
    """
    Exposure doesn't expose RSS, so we scrape the homepage.
    Returns (iso_date, story_url, image_url) or (None, base_url, None).
    """
    r = get(base_url)
    if not r:
        return None, None, None
    soup = BeautifulSoup(r.text, "html.parser")

    # Try <time datetime="..."> tags
    time_tag = soup.find("time", attrs={"datetime": True})
    if time_tag:
        raw = time_tag["datetime"][:10]
        parent_a = time_tag.find_parent("a")
        link = parent_a["href"] if parent_a and parent_a.get("href") else base_url
        # Grab first meaningful image near the story card
        img_url = None
        card = time_tag.find_parent(["article", "li", "div", "section"])
        if card:
            img = card.find("img", src=True)
            if img:
                img_url = img["src"]
        return raw, link, img_url

    # Fallback: extract YYYY-MM from image src paths
    dates = []
    imgs_by_date = {}
    for img in soup.find_all("img", src=True):
        m = re.search(r"/public/(\d{4}-\d{2})/", img["src"])
        if m:
            key = m.group(1) + "-01"
            dates.append(key)
            imgs_by_date[key] = img["src"]
    if dates:
        dates.sort(reverse=True)
        best = dates[0]
        return best, base_url, imgs_by_date.get(best)

    return None, base_url, None


# ─── Shared Playwright browser (lazy-initialised) ────────────────────────────
_pw_instance = None
_pw_browser = None

def _get_browser():
    global _pw_instance, _pw_browser
    if _pw_browser is None:
        _pw_instance = sync_playwright().start()
        _pw_browser = _pw_instance.chromium.launch(headless=True)
    return _pw_browser


def close_browser():
    global _pw_instance, _pw_browser
    if _pw_browser:
        _pw_browser.close()
        _pw_browser = None
    if _pw_instance:
        _pw_instance.stop()
        _pw_instance = None


def undp_page_latest(page_url):
    """
    Scrape an undp.org /stories or /blog listing page using a headless browser.
    Returns (iso_date, article_url, image_url) or (None, page_url, None).
    """
    try:
        browser = _get_browser()
        page = browser.new_page()
        page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (compatible; UNDPSourcesBot/1.0)"})
        page.goto(page_url, timeout=PLAYWRIGHT_TIMEOUT, wait_until="networkidle")
        # Wait for cards to appear — UNDP uses various card/article selectors
        for sel in [
            "[class*='card'] time[datetime]",
            "[class*='story'] time[datetime]",
            "[class*='post'] time[datetime]",
            "article time[datetime]",
            "time[datetime]",
            "[class*='card']",
        ]:
            try:
                page.wait_for_selector(sel, timeout=8_000)
                break
            except Exception:
                continue
        html = page.content()
        page.close()
    except Exception as e:
        print(f"  WARN playwright {page_url}: {e}", file=sys.stderr)
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
                            candidates.append((m.group(1), url, img_url))
                else:
                    date = item.get("datePublished") or item.get("dateModified", "")
                    url = item.get("url", page_url)
                    img = item.get("image") or {}
                    img_url = img.get("url") if isinstance(img, dict) else (img if isinstance(img, str) else None)
                    m = re.match(r"(\d{4}-\d{2}-\d{2})", date)
                    if m:
                        candidates.append((m.group(1), url, img_url))
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
            time_dates.append((m.group(1), link, img_url))

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
        return best, article_links[0] if article_links else page_url, img_by_date.get(best)

    # Strategy 3: date in meta tags
    for meta in soup.find_all("meta", attrs={"property": re.compile(r"article:published_time|og:updated_time")}):
        content = meta.get("content", "")
        m = re.match(r"(\d{4}-\d{2}-\d{2})", content)
        if m:
            return m.group(1), page_url, None

    return None, page_url, None


# ─── Main ────────────────────────────────────────────────────────────────────

def scrape_all():
    results = []
    total = len(OFFICES)
    for i, row in enumerate(OFFICES):
        country, flickr_url, nsid, exposure_url, stories_url, blog_url = row
        print(f"[{i+1}/{total}] {country}")

        rec = {
            "country": country,
            "flickr":   {"url": flickr_url,    "date": None, "latest_url": None, "image_url": None},
            "exposure": {"url": exposure_url,   "date": None, "latest_url": None, "image_url": None},
            "stories":  {"url": stories_url,    "date": None, "latest_url": None, "image_url": None},
            "blog":     {"url": blog_url,       "date": None, "latest_url": None, "image_url": None},
        }

        # Flickr
        if nsid:
            d, lu, img = flickr_latest(nsid)
            rec["flickr"]["date"] = d
            rec["flickr"]["latest_url"] = lu or flickr_url
            rec["flickr"]["image_url"] = img
            time.sleep(0.3)

        # Exposure
        if exposure_url:
            d, lu, img = exposure_latest(exposure_url)
            rec["exposure"]["date"] = d
            rec["exposure"]["latest_url"] = lu or exposure_url
            rec["exposure"]["image_url"] = img
            time.sleep(0.5)

        # UNDP Stories
        if stories_url:
            d, lu, img = undp_page_latest(stories_url)
            rec["stories"]["date"] = d
            rec["stories"]["latest_url"] = lu or stories_url
            rec["stories"]["image_url"] = img
            time.sleep(0.5)

        # UNDP Blog
        if blog_url:
            d, lu, img = undp_page_latest(blog_url)
            rec["blog"]["date"] = d
            rec["blog"]["latest_url"] = lu or blog_url
            rec["blog"]["image_url"] = img
            time.sleep(0.5)

        results.append(rec)

    output = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "offices": results,
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    close_browser()
    print(f"\nDone — wrote data.json with {len(results)} offices.")


if __name__ == "__main__":
    scrape_all()
