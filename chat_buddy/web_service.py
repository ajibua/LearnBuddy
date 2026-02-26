import aiohttp
import asyncio
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import quote
import time
from datetime import datetime, timedelta
import json

try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False
    print("Note: feedparser not installed – Google News RSS disabled. Run: pip install feedparser")

# Simple in-memory cache to avoid duplicate requests
search_cache = {}
CACHE_DURATION = 3600  # Cache for 1 hour

def get_cached_search(query):
    """Get cached search results if they exist and are fresh"""
    if query in search_cache:
        cached_time, cached_results = search_cache[query]
        if datetime.now() - cached_time < timedelta(seconds=CACHE_DURATION):
            return cached_results
    return None

def cache_search_results(query, results):
    """Cache search results"""
    search_cache[query] = (datetime.now(), results)


# ---------------------------------------------------------------------------
# Wikipedia helpers
# ---------------------------------------------------------------------------

def search_wikipedia(query):
    """
    Search Wikipedia for information about a topic.
    Returns a dict with title, snippet, url.
    """
    try:
        cached = get_cached_search(f"wiki:{query}")
        if cached:
            return cached

        search_url = "https://en.wikipedia.org/w/api.php"
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; +https://learnbuddy.app)'
        }
        params = {
            'action': 'query',
            'list': 'search',
            'srsearch': query,
            'format': 'json',
            'srlimit': 3
        }

        response = requests.get(search_url, params=params, headers=headers, timeout=8)
        response.raise_for_status()

        data = response.json()
        results = data.get('query', {}).get('search', [])

        if results:
            first_result = results[0]
            title = first_result['title']
            snippet = (first_result.get('snippet', '')
                       .replace('<span class="searchmatch">', '')
                       .replace('</span>', ''))

            result = {
                'title': title,
                'snippet': snippet,
                'url': f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
            }
            cache_search_results(f"wiki:{query}", result)
            return result

        return None

    except Exception as e:
        print(f"Error in search_wikipedia: {e}")
        return None


def get_wikipedia_full_extract(title):
    """
    Fetch the full plain-text extract of a Wikipedia article by its title.
    Returns up to 6 000 characters of text.
    """
    try:
        cached = get_cached_search(f"wiki_extract:{title}")
        if cached:
            return cached

        url = "https://en.wikipedia.org/w/api.php"
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; +https://learnbuddy.app)'
        }
        params = {
            'action': 'query',
            'prop': 'extracts',
            'titles': title,
            'explaintext': True,
            'exsectionformat': 'plain',
            'format': 'json',
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        pages = data.get('query', {}).get('pages', {})
        for page_id, page in pages.items():
            if page_id != '-1':
                extract = page.get('extract', '')
                if extract:
                    extract = extract[:6000]
                    cache_search_results(f"wiki_extract:{title}", extract)
                    return extract

        return None

    except Exception as e:
        print(f"Error fetching Wikipedia extract for '{title}': {e}")
        return None


# ---------------------------------------------------------------------------
# DuckDuckGo Instant Answer
# ---------------------------------------------------------------------------

def search_duckduckgo_instant(query):
    """
    Query the free DuckDuckGo Instant Answer API.
    Returns a structured dict with abstract, infobox, related topics, etc.
    Works well for people, places, organisations, concepts.
    """
    try:
        cached = get_cached_search(f"ddg:{query}")
        if cached:
            return cached

        url = "https://api.duckduckgo.com/"
        params = {
            'q': query,
            'format': 'json',
            'no_html': '1',
            'skip_disambig': '1',
            't': 'learnbuddy'
        }
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; +https://learnbuddy.app)'
        }

        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()

        result = {}

        if data.get('AbstractText'):
            result['abstract'] = data['AbstractText']
            result['abstract_source'] = data.get('AbstractSource', '')
            result['abstract_url'] = data.get('AbstractURL', '')

        if data.get('Answer'):
            result['answer'] = data['Answer']

        if data.get('Definition'):
            result['definition'] = data['Definition']

        # Structured infobox (very useful for people / entities)
        if data.get('Infobox') and data['Infobox'].get('content'):
            infobox = {}
            for item in data['Infobox']['content']:
                label = item.get('label', '').strip()
                value = item.get('value', '').strip()
                if label and value:
                    infobox[label] = value
            if infobox:
                result['infobox'] = infobox

        # Related topics / sub-topics
        if data.get('RelatedTopics'):
            topics = []
            for topic in data['RelatedTopics'][:5]:
                if isinstance(topic, dict) and topic.get('Text'):
                    topics.append(topic['Text'])
            if topics:
                result['related_topics'] = topics

        if result:
            cache_search_results(f"ddg:{query}", result)
            return result

        return None

    except Exception as e:
        print(f"DuckDuckGo instant answer error: {e}")
        return None


# ---------------------------------------------------------------------------
# Unified search_web
# ---------------------------------------------------------------------------

# ---- Query-intent helpers --------------------------------------------------

_MUSIC_TERMS = {
    'singer', 'musician', 'artist', 'rapper', 'songwriter', 'producer',
    'album', 'song', 'track', 'lyrics', 'discography', 'debut', 'gospel',
    'worship', 'music', 'band', 'group', 'concert', 'tour', 'genre',
    'hip hop', 'afrobeats', 'jazz', 'classical', 'r&b', 'pop',
}
_NEWS_TERMS = {
    'news', 'breaking', 'latest', 'today', 'now', 'current', 'happening',
    'update', 'crisis', 'election', 'war', 'protest', 'parliament',
    'president', 'government', 'policy', 'inflation', 'economy',
}
_BOOK_TERMS = {
    'book', 'novel', 'author', 'wrote', 'written by', 'published',
    'literature', 'poetry', 'poem', 'bibliography', 'read', 'chapter',
}

def _query_is_music(q):
    q = q.lower()
    return any(t in q for t in _MUSIC_TERMS)

def _query_is_news(q):
    q = q.lower()
    return any(t in q for t in _NEWS_TERMS)

def _query_is_book(q):
    q = q.lower()
    return any(t in q for t in _BOOK_TERMS)


# ---------------------------------------------------------------------------
# MusicBrainz  – free, no API key required, great for artists/albums
# ---------------------------------------------------------------------------

def search_musicbrainz(query):
    """
    Search MusicBrainz for artist info → releases → recordings.
    Returns a structured dict with biography, albums, and recent songs.
    """
    try:
        cached = get_cached_search(f"mb:{query}")
        if cached:
            return cached

        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI Assistant; learnbuddy@example.com)',
            'Accept': 'application/json',
        }

        # Step 1 – find the artist
        artist_url = "https://musicbrainz.org/ws/2/artist/"
        params = {'query': query, 'fmt': 'json', 'limit': 3}
        r = requests.get(artist_url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        artists = r.json().get('artists', [])

        if not artists:
            return None

        artist = artists[0]
        artist_id = artist.get('id')
        result = {
            'name': artist.get('name'),
            'type': artist.get('type', ''),
            'country': artist.get('country', ''),
            'disambiguation': artist.get('disambiguation', ''),
            'begin_area': artist.get('begin-area', {}).get('name', '') if artist.get('begin-area') else '',
            'tags': [t['name'] for t in artist.get('tags', [])[:8]],
            'life_span': artist.get('life-span', {}),
            'albums': [],
            'recordings': [],
        }

        # Step 2 – fetch releases (albums)
        if artist_id:
            releases_url = "https://musicbrainz.org/ws/2/release/"
            rp = {
                'artist': artist_id,
                'fmt': 'json',
                'limit': 10,
                'type': 'album',
            }
            rr = requests.get(releases_url, params=rp, headers=headers, timeout=10)
            if rr.ok:
                for rel in rr.json().get('releases', [])[:10]:
                    result['albums'].append({
                        'title': rel.get('title'),
                        'date': rel.get('date', ''),
                        'status': rel.get('status', ''),
                    })

            # Step 3 – top recordings
            rec_url = "https://musicbrainz.org/ws/2/recording/"
            rec_p = {'artist': artist_id, 'fmt': 'json', 'limit': 10}
            rc = requests.get(rec_url, params=rec_p, headers=headers, timeout=10)
            if rc.ok:
                for rec in rc.json().get('recordings', [])[:10]:
                    result['recordings'].append(rec.get('title', ''))

        cache_search_results(f"mb:{query}", result)
        return result

    except Exception as e:
        print(f"MusicBrainz search error: {e}")
        return None


# ---------------------------------------------------------------------------
# Wikidata  – free structured knowledge graph, excellent for people/entities
# ---------------------------------------------------------------------------

def search_wikidata(query):
    """
    Search Wikidata for a person / organisation / place.
    Returns structured facts: description, birth date, nationality, occupation, etc.
    """
    try:
        cached = get_cached_search(f"wd:{query}")
        if cached:
            return cached

        headers = {'User-Agent': 'LearnBuddy/1.0 (learnbuddy@example.com)'}

        # Step 1 – entity search
        search_url = "https://www.wikidata.org/w/api.php"
        params = {
            'action': 'wbsearchentities',
            'search': query,
            'language': 'en',
            'format': 'json',
            'limit': 3,
        }
        r = requests.get(search_url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        entities = r.json().get('search', [])

        if not entities:
            return None

        entity = entities[0]
        entity_id = entity.get('id')
        result = {
            'label': entity.get('label', ''),
            'description': entity.get('description', ''),
            'entity_id': entity_id,
            'facts': {},
        }

        if not entity_id:
            cache_search_results(f"wd:{query}", result)
            return result

        # Step 2 – fetch notable claims
        claims_url = "https://www.wikidata.org/w/api.php"
        cp = {
            'action': 'wbgetentities',
            'ids': entity_id,
            'props': 'claims|labels|descriptions|sitelinks',
            'languages': 'en',
            'format': 'json',
        }
        cr = requests.get(claims_url, params=cp, headers=headers, timeout=10)
        if not cr.ok:
            cache_search_results(f"wd:{query}", result)
            return result

        entity_data = cr.json().get('entities', {}).get(entity_id, {})
        claims = entity_data.get('claims', {})

        # Map property IDs to human-readable labels
        prop_map = {
            'P569': 'Date of birth',   'P570': 'Date of death',
            'P19':  'Place of birth',  'P27':  'Country of nationality',
            'P106': 'Occupation',      'P21':  'Gender',
            'P136': 'Genre',           'P264': 'Record label',
            'P18':  'Image',           'P571': 'Inception',
            'P577': 'Publication date','P495': 'Country of origin',
            'P413': 'Position played', 'P54':  'Member of sports team',
        }

        def resolve_value(snak):
            """Pull a readable value out of a Wikidata snak."""
            dv = snak.get('datavalue', {})
            dtype = dv.get('type')
            val = dv.get('value')
            if dtype == 'string':
                return val
            if dtype == 'time':
                # e.g. '+1987-04-25T00:00:00Z'
                raw = val.get('time', '') if isinstance(val, dict) else ''
                return raw.lstrip('+').split('T')[0]
            if dtype == 'wikibase-entityid':
                eid = val.get('id') if isinstance(val, dict) else None
                if eid:
                    # Quick label lookup
                    try:
                        lr = requests.get(
                            "https://www.wikidata.org/w/api.php",
                            params={'action': 'wbgetentities', 'ids': eid,
                                    'props': 'labels', 'languages': 'en', 'format': 'json'},
                            headers=headers, timeout=5
                        )
                        if lr.ok:
                            return (lr.json().get('entities', {})
                                    .get(eid, {})
                                    .get('labels', {})
                                    .get('en', {})
                                    .get('value', eid))
                    except Exception:
                        pass
                return eid
            return str(val) if val else None

        for prop_id, prop_label in prop_map.items():
            if prop_id in claims:
                values = []
                for claim in claims[prop_id][:3]:
                    ms = claim.get('mainsnak', {})
                    v = resolve_value(ms)
                    if v:
                        values.append(v)
                if values:
                    result['facts'][prop_label] = ', '.join(values)

        cache_search_results(f"wd:{query}", result)
        return result

    except Exception as e:
        print(f"Wikidata search error: {e}")
        return None


# ---------------------------------------------------------------------------
# Google News RSS  – free, no API key, current headlines
# ---------------------------------------------------------------------------

def search_google_news(query):
    """
    Fetch current news headlines via Google News RSS feed.
    Returns up to 6 recent articles (title + snippet + url + date).
    Requires: pip install feedparser
    """
    if not FEEDPARSER_AVAILABLE:
        return None
    try:
        cached = get_cached_search(f"gnews:{query}")
        if cached:
            return cached

        rss_url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"
        headers = {'User-Agent': 'LearnBuddy/1.0 (learnbuddy@example.com)'}
        r = requests.get(rss_url, headers=headers, timeout=10)
        r.raise_for_status()

        feed = feedparser.parse(r.text)
        articles = []
        for entry in feed.entries[:6]:
            # Strip HTML tags from summary
            summary = re.sub(r'<[^>]+>', '', entry.get('summary', ''))[:300]
            articles.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'published': entry.get('published', ''),
                'summary': summary,
                'source': entry.get('source', {}).get('title', '') if isinstance(entry.get('source'), dict) else '',
            })

        if articles:
            cache_search_results(f"gnews:{query}", articles)
            return articles

        return None

    except Exception as e:
        print(f"Google News RSS error: {e}")
        return None


# ---------------------------------------------------------------------------
# Reddit JSON API  – free, no key needed for public searches
# ---------------------------------------------------------------------------

def search_reddit(query):
    """
    Search Reddit for community discussions and context.
    Returns up to 5 relevant posts (title + body snippet + subreddit).
    """
    try:
        cached = get_cached_search(f"reddit:{query}")
        if cached:
            return cached

        url = "https://www.reddit.com/search.json"
        params = {
            'q': query,
            'sort': 'relevance',
            'limit': 5,
            't': 'year',
            'type': 'link',
        }
        headers = {
            'User-Agent': 'LearnBuddy/1.0 (Educational AI; learnbuddy@example.com)'
        }

        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        posts = r.json().get('data', {}).get('children', [])

        results = []
        for post in posts:
            d = post.get('data', {})
            title = d.get('title', '')
            selftext = d.get('selftext', '')[:400]
            # Strip spoiler/removed posts
            if selftext in ('[removed]', '[deleted]', ''):
                selftext = ''
            results.append({
                'title': title,
                'subreddit': d.get('subreddit_name_prefixed', ''),
                'body': selftext,
                'score': d.get('score', 0),
                'url': f"https://reddit.com{d.get('permalink', '')}",
            })

        if results:
            # Only cache if we found something useful
            cache_search_results(f"reddit:{query}", results)
            return results

        return None

    except Exception as e:
        print(f"Reddit search error: {e}")
        return None


# ---------------------------------------------------------------------------
# Open Library  – free, no key, books / authors
# ---------------------------------------------------------------------------

def search_open_library(query):
    """
    Search Open Library (Internet Archive) for books and authors.
    Returns up to 5 results with title, author, year, description.
    """
    try:
        cached = get_cached_search(f"ol:{query}")
        if cached:
            return cached

        url = "https://openlibrary.org/search.json"
        params = {
            'q': query,
            'limit': 5,
            'fields': 'title,author_name,first_publish_year,subject,isbn,description',
        }
        headers = {'User-Agent': 'LearnBuddy/1.0 (learnbuddy@example.com)'}

        r = requests.get(url, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        docs = r.json().get('docs', [])

        results = []
        for doc in docs[:5]:
            results.append({
                'title': doc.get('title', ''),
                'authors': doc.get('author_name', [])[:3],
                'year': doc.get('first_publish_year', ''),
                'subjects': doc.get('subject', [])[:5],
            })

        if results:
            cache_search_results(f"ol:{query}", results)
            return results

        return None

    except Exception as e:
        print(f"Open Library search error: {e}")
        return None


def search_web(query, max_results=3):
    """
    Multi-source research engine – pulls from up to 7 sources:
      1. Wikipedia (full article extract)
      2. DuckDuckGo Instant Answer API
      3. MusicBrainz  (artists / albums / recordings – music queries)
      4. Wikidata     (structured facts – any person / place / org)
      5. Google News RSS (current headlines – news queries)
      6. Reddit JSON API (community context – most queries)
      7. Open Library (books / authors – academic queries)
    """
    try:
        cached = get_cached_search(f"web:{query}")
        if cached:
            return cached

        results = {
            'query': query,
            'knowledge': None,
            'full_extract': None,
            'ddg': None,
            'musicbrainz': None,
            'wikidata': None,
            'news': None,
            'reddit': None,
            'books': None,
            'timestamp': datetime.now().isoformat(),
        }

        is_music = _query_is_music(query)
        is_news  = _query_is_news(query)
        is_book  = _query_is_book(query)

        # 1 – Wikipedia (always)
        wiki_result = search_wikipedia(query)
        if wiki_result:
            results['knowledge'] = wiki_result
            full_extract = get_wikipedia_full_extract(wiki_result['title'])
            if full_extract:
                results['full_extract'] = full_extract

        # 2 – DuckDuckGo (always)
        ddg_result = search_duckduckgo_instant(query)
        if ddg_result:
            results['ddg'] = ddg_result

        # 3 – MusicBrainz (music queries OR when Wikipedia/DDG come up short)
        if is_music or (not results['full_extract'] and not (results['ddg'] or {}).get('abstract')):
            mb = search_musicbrainz(query)
            if mb:
                results['musicbrainz'] = mb

        # 4 – Wikidata (people / entities – almost always useful)
        wd = search_wikidata(query)
        if wd:
            results['wikidata'] = wd

        # 5 – Google News (news / current-events queries)
        if is_news:
            news = search_google_news(query)
            if news:
                results['news'] = news

        # 6 – Reddit (general context, skip for pure music/book lookups)
        if not is_book:
            reddit = search_reddit(query)
            if reddit:
                results['reddit'] = reddit

        # 7 – Open Library (books / academic topics)
        if is_book:
            books = search_open_library(query)
            if books:
                results['books'] = books

        cache_search_results(f"web:{query}", results)
        return results

    except Exception as e:
        print(f"Error in search_web: {e}")
        return {
            'query': query,
            'knowledge': None,
            'error': str(e)
        }


def format_search_results_for_ai(search_results):
    """
    Format multi-source research into a concise context block
    that is prepended to the AI prompt.
    """
    if not search_results:
        return ""

    formatted = "\n=== REFERENCE INFORMATION ===\n"
    has_content = False

    # ---- Wikidata structured facts (most authoritative for people/places) ---
    wd = search_results.get('wikidata')
    if wd and (wd.get('description') or wd.get('facts')):
        formatted += f"\n**Wikidata – {wd.get('label', 'Entity')}:**\n"
        if wd.get('description'):
            formatted += f"  Description: {wd['description']}\n"
        for label, value in wd.get('facts', {}).items():
            formatted += f"  {label}: {value}\n"
        has_content = True

    # ---- DuckDuckGo abstract / answer / infobox ----
    ddg = search_results.get('ddg')
    if ddg:
        if ddg.get('answer'):
            formatted += f"\n**Instant Answer:** {ddg['answer']}\n"
            has_content = True
        if ddg.get('abstract'):
            src = ddg.get('abstract_source', 'DDG')
            formatted += f"\n**Overview ({src}):** {ddg['abstract']}\n"
            has_content = True
        if ddg.get('definition'):
            formatted += f"\n**Definition:** {ddg['definition']}\n"
            has_content = True
        if ddg.get('infobox'):
            formatted += "\n**Key Facts (DDG Infobox):**\n"
            for label, value in list(ddg['infobox'].items())[:10]:
                formatted += f"  - {label}: {value}\n"
            has_content = True
        if ddg.get('related_topics'):
            formatted += "\n**Related Topics:**\n"
            for topic in ddg['related_topics']:
                formatted += f"  - {topic}\n"
            has_content = True

    # ---- MusicBrainz (artists) ----
    mb = search_results.get('musicbrainz')
    if mb:
        formatted += f"\n**MusicBrainz – {mb.get('name', '')}:**\n"
        if mb.get('type'):
            formatted += f"  Type: {mb['type']}\n"
        if mb.get('disambiguation'):
            formatted += f"  Note: {mb['disambiguation']}\n"
        if mb.get('tags'):
            formatted += f"  Tags/Genres: {', '.join(mb['tags'])}\n"
        if mb.get('country') or mb.get('begin_area'):
            origin = mb.get('begin_area') or mb.get('country')
            formatted += f"  Origin: {origin}\n"
        if mb.get('life_span'):
            ls = mb['life_span']
            if ls.get('begin'):
                formatted += f"  Active since: {ls['begin']}\n"
        if mb.get('albums'):
            formatted += "  Albums:\n"
            for alb in mb['albums'][:8]:
                date_str = f" ({alb['date']})" if alb.get('date') else ''
                formatted += f"    - {alb['title']}{date_str}\n"
        if mb.get('recordings'):
            formatted += f"  Notable tracks: {', '.join(mb['recordings'][:8])}\n"
        has_content = True

    # ---- Wikipedia full extract ----
    full_extract = search_results.get('full_extract')
    if full_extract:
        knowledge = search_results.get('knowledge', {})
        title = knowledge.get('title', 'Wikipedia') if knowledge else 'Wikipedia'
        formatted += f"\n**Wikipedia – {title}:**\n{full_extract}\n"
        has_content = True
    elif search_results.get('knowledge'):
        knowledge = search_results['knowledge']
        formatted += f"\n**Topic:** {knowledge['title']}\n"
        formatted += f"**Summary:** {knowledge['snippet']}\n"
        has_content = True

    # ---- Google News current headlines ----
    news = search_results.get('news')
    if news:
        formatted += "\n**Recent News Headlines:**\n"
        for article in news[:5]:
            pub = f" [{article['published']}]" if article.get('published') else ''
            src = f" — {article['source']}" if article.get('source') else ''
            formatted += f"  - {article['title']}{src}{pub}\n"
            if article.get('summary'):
                formatted += f"    {article['summary']}\n"
        has_content = True

    # ---- Open Library books ----
    books = search_results.get('books')
    if books:
        formatted += "\n**Related Books (Open Library):**\n"
        for book in books:
            authors = ', '.join(book.get('authors', []))
            year = f" ({book['year']})" if book.get('year') else ''
            formatted += f"  - \"{book['title']}\"{year} by {authors}\n"
            if book.get('subjects'):
                formatted += f"    Topics: {', '.join(book['subjects'][:4])}\n"
        has_content = True

    # ---- Reddit discussions ----
    reddit = search_results.get('reddit')
    if reddit:
        formatted += "\n**Community Discussions (Reddit):**\n"
        for post in reddit[:3]:
            formatted += f"  - [{post['subreddit']}] {post['title']}\n"
            if post.get('body'):
                formatted += f"    {post['body'][:200]}\n"
        has_content = True

    if not has_content:
        return ""

    formatted += "\n=== Use ALL of the above reference information to give a thorough, well-informed answer ===\n"
    return formatted


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------

async def search_web_async(query):
    """Asynchronous version – runs blocking I/O in a thread pool."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, search_web, query)


# ---------------------------------------------------------------------------
# Question classifier
# ---------------------------------------------------------------------------

def is_current_event_question(user_message):
    """
    Returns True when the message is likely to benefit from a real-time
    or reference lookup, including:
      - Time-sensitive queries (news, weather, prices …)
      - Questions about specific people, organisations, or topics
      - General "tell me about" / "who is" / "what is" queries
    """
    # Keywords that almost always need a lookup
    lookup_keywords = [
        # Time-sensitive
        'now', 'today', 'current', 'latest', 'recent', 'happening',
        'news', 'breaking', 'right now', 'this week', 'this month',
        'update on', 'situation', 'event', 'incident', 'crisis',
        'election', 'weather', 'stock', 'crypto',
        'covid', 'pandemic', 'war', 'conflict',
        # Informational / biographical
        'who is', 'who was', 'who are', "who's",
        'what is', "what's", 'what are',
        'tell me about', 'explain', 'describe',
        'biography', 'history of', 'origin of',
        'when was', 'where is', 'how did',
        'discography', 'songs', 'albums', 'minister', 'pastor', 'artist',
        'singer', 'musician', 'actor', 'politician', 'author', 'founder',
    ]

    # Current year references
    current_years = [
        '2023', '2024', '2025', '2026',
        'january', 'february', 'march', 'april',
        'may', 'june', 'july', 'august', 'september',
        'october', 'november', 'december',
    ]

    message_lower = user_message.lower()

    has_lookup_keyword = any(kw in message_lower for kw in lookup_keywords)
    has_time_reference = any(yr in message_lower for yr in current_years)

    return has_lookup_keyword or has_time_reference


# ---------------------------------------------------------------------------
# Legacy helpers kept for backward compatibility
# ---------------------------------------------------------------------------

def search_web_recommendations(query):
    """Kept for backward compatibility. Returns basic resource recommendations."""
    try:
        cached = get_cached_search(f"recommendations:{query}")
        if cached:
            return cached

        results = {'recommendations': []}
        wiki_result = search_wikipedia(query)
        if wiki_result:
            results['recommendations'].append({
                'title': f"{wiki_result['title']} (Wikipedia)",
                'url': wiki_result['url'],
                'type': 'encyclopedia',
                'source': 'Wikipedia'
            })

        cache_search_results(f"recommendations:{query}", results)
        return results

    except Exception as e:
        print(f"Error in search_web_recommendations: {e}")
        return {'recommendations': []}
